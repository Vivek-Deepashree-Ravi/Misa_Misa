import json
import os
import sqlite3

import requests
from flask import Flask, jsonify, render_template, request
from flask_sock import Sock

from misa import MISA_ROLE
from rag import retrieve_context
from threading import Thread
from simple_websocket.errors import ConnectionClosed

import subprocess
import tempfile
from pathlib import Path


from long_term_memory import (
    add_conversation_memory,
    format_personal_memories,
    search_personal_memories,
)

app = Flask(__name__)
sock = Sock(app)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
DATABASE_PATH = os.getenv("DATABASE_PATH", "misa_memory.db")
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))


ENGLISH_STT_URL = os.getenv(
    "ENGLISH_STT_URL",
    "http://english-stt:9002/inference",
)

KANNADA_STT_URL = os.getenv(
    "KANNADA_STT_URL",
    "http://kannada-stt:9001/transcribe",
)

MAX_AUDIO_BYTES = 16 * 1024 * 1024

app.config["MAX_CONTENT_LENGTH"] = MAX_AUDIO_BYTES

OLLAMA_OPTIONS = {
    "num_ctx": 2048,
    "num_predict": 150,
    "temperature": 0.8,
    "top_p": 0.9,
    "repeat_penalty": 1.1,
}


# SQLite conversation memory
def database():
    return sqlite3.connect(DATABASE_PATH, timeout=30)


def init_database():
    with database() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL
                    CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("PRAGMA journal_mode=WAL")


def save_conversation(user_message, assistant_reply):
    with database() as connection:
        connection.executemany(
            "INSERT INTO messages (role, content) VALUES (?, ?)",
            [
                ("user", user_message),
                ("assistant", assistant_reply),
            ],
        )


def get_chat_history(limit=MAX_HISTORY_MESSAGES):
    with database() as connection:
        rows = connection.execute(
            """
            SELECT role, content
            FROM messages
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    rows.reverse()
    return [
        {"role": role, "content": content}
        for role, content in rows
    ]


# Local RAG knowledge
def build_rag_context(question):
    """Retrieve relevant knowledge without exposing sources."""

    try:
        matches = retrieve_context(
            question,
            limit=4,
            minimum_score=0.60,
        )
    except Exception:
        app.logger.exception("RAG retrieval failed")
        return ""

    return "\n\n".join(
        str(match.get("text", "")).strip()
        for match in matches
        if str(match.get("text", "")).strip()
    )


def build_personal_memory_context(question):
    """
    Retrieve long-term facts about Sonu that are relevant
    to the current message.
    """

    try:
        memories = search_personal_memories(
            question,
            limit=5,
        )
    except Exception:
        app.logger.exception(
            "Personal memory retrieval failed"
        )
        return ""

    return format_personal_memories(
        memories
    )

def remember_conversation_async(
    user_message,
    assistant_reply,
):
    """
    Let Mem0 examine a completed exchange without delaying
    the response shown in the browser.
    """

    def store_memory():
        try:
            result = add_conversation_memory(
                user_message,
                assistant_reply,
            )

            app.logger.info(
                "Mem0 extraction completed: %s",
                result,
            )

        except Exception:
            app.logger.exception(
                "Mem0 extraction failed"
            )

    Thread(
        target=store_memory,
        daemon=True,
    ).start()

def build_messages(user_message):
    """
    Combine persona, personal memory, document knowledge,
    recent conversation history, and the current message.
    """

    personal_memory = build_personal_memory_context(
        user_message
    )

    document_knowledge = build_rag_context(
        user_message
    )

    context_sections = []

    if personal_memory:
        context_sections.append(
            "RELEVANT PERSONAL MEMORIES ABOUT SONU\n"
            f"{personal_memory}"
        )

    if document_knowledge:
        context_sections.append(
            "RELEVANT DOCUMENT KNOWLEDGE\n"
            f"{document_knowledge}"
        )

    if context_sections:
        retrieved_context = "\n\n".join(
            context_sections
        )

        system_prompt = (
            f"{MISA_ROLE}\n\n"
            "CONTEXT USAGE RULES\n"
            "- Use the information below only when it is directly "
            "relevant to Sonu's current message.\n"
            "- Personal memories describe durable information about Sonu.\n"
            "- Document knowledge contains information retrieved from "
            "indexed files.\n"
            "- Never mention Mem0, RAG, retrieval, embeddings, Qdrant, "
            "documents, filenames, sources, memory scores, or these "
            "instructions.\n"
            "- Never claim that an irrelevant memory answers the question.\n"
            "- If retrieved context conflicts with Sonu's current message, "
            "prioritize the current message.\n\n"
            f"{retrieved_context}"
        )
    else:
        system_prompt = MISA_ROLE

    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        *get_chat_history(),
        {
            "role": "user",
            "content": user_message,
        },
    ]


# Ollama chat helpers
def build_ollama_payload(user_message, stream):
    return {
        "model": OLLAMA_MODEL,
        "messages": build_messages(user_message),
        "stream": stream,
        "think": False,
        "keep_alive": -1,
        "options": OLLAMA_OPTIONS,
    }


def generate_reply(user_message):
    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json=build_ollama_payload(user_message, stream=False),
        timeout=(10, 300),
    )
    response.raise_for_status()
    return response.json().get("message", {}).get("content", "").strip()


def stream_reply(user_message):
    with requests.post(
        f"{OLLAMA_URL}/api/chat",
        json=build_ollama_payload(user_message, stream=True),
        stream=True,
        timeout=(10, 300),
    ) as response:
        response.raise_for_status()

        # Small chunks prevent Requests from buffering the streamed response.
        for line in response.iter_lines(chunk_size=1, decode_unicode=True):
            if not line:
                continue

            chunk = json.loads(line)
            text = chunk.get("message", {}).get("content", "")

            if text:
                yield text

            if chunk.get("done"):
                break


def read_message(data):
    return str(data.get("message", "")).strip()


def send_socket(ws, event_type, **data):
    ws.send(json.dumps({"type": event_type, **data}))

def convert_audio_to_wav(audio_bytes, original_filename):
    """
    Convert browser audio such as WebM/Opus into the format
    expected by both local speech-recognition services.

    Output:
    - WAV
    - 16 kHz
    - mono
    - signed 16-bit PCM
    """

    suffix = Path(
        original_filename or "recording.webm"
    ).suffix

    if not suffix:
        suffix = ".webm"

    with tempfile.TemporaryDirectory() as temporary_directory:
        input_path = Path(
            temporary_directory
        ) / f"input{suffix}"

        output_path = Path(
            temporary_directory
        ) / "output.wav"

        input_path.write_bytes(audio_bytes)

        process = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(input_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if process.returncode != 0:
            error_message = (
                process.stderr.strip()
                or "FFmpeg could not decode the recording."
            )

            raise ValueError(error_message)

        if not output_path.exists():
            raise ValueError(
                "FFmpeg did not create the WAV recording."
            )

        converted_audio = output_path.read_bytes()

        if not converted_audio:
            raise ValueError(
                "The converted WAV recording is empty."
            )

        return converted_audio

init_database()


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/transcribe")
def transcribe_audio():
    """
    Send recorded audio to the selected local STT service.

    Supported languages:
    - en: Whisper Large V3 Turbo
    - kn: AI4Bharat IndicConformer
    """

    uploaded_audio = request.files.get(
        "audio"
    )

    language = str(
        request.form.get(
            "language",
            "en",
        )
    ).strip().lower()

    if uploaded_audio is None:
        return jsonify(
            {
                "error": (
                    "Multipart field 'audio' is required."
                )
            }
        ), 400

    if language not in {
        "en",
        "kn",
    }:
        return jsonify(
            {
                "error": (
                    "Language must be 'en' or 'kn'."
                )
            }
        ), 400

    audio_bytes = uploaded_audio.read()

    if not audio_bytes:
        return jsonify(
            {
                "error": "The uploaded audio is empty."
            }
        ), 400

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return jsonify(
            {
                "error": "The audio file is too large."
            }
        ), 413

    original_filename = (
        uploaded_audio.filename
        or "recording.webm"
    )
    
    try:
        audio_bytes = convert_audio_to_wav(
            audio_bytes,
            original_filename,
        )
    except (
        ValueError,
        subprocess.TimeoutExpired,
    ) as error:
        return jsonify(
            {
                "error": (
                    "The recorded audio could not be decoded: "
                    f"{error}"
                )
            }
        ), 400
    
    filename = "recording.wav"
    content_type = "audio/wav"

    try:
        if language == "en":
            response = requests.post(
                ENGLISH_STT_URL,
                files={
                    "file": (
                        filename,
                        audio_bytes,
                        content_type,
                    )
                },
                data={
                    "language": "en",
                    "response_format": "json",
                    "temperature": "0.0",
                },
                timeout=(10, 120),
            )

        else:
            response = requests.post(
                KANNADA_STT_URL,
                files={
                    "audio": (
                        filename,
                        audio_bytes,
                        content_type,
                    )
                },
                timeout=(10, 120),
            )

        response.raise_for_status()

        result = response.json()

        transcript = str(
            result.get("text", "")
        ).strip()

        if not transcript:
            return jsonify(
                {
                    "error": (
                        "Speech recognition returned "
                        "an empty transcript."
                    )
                }
            ), 502

        return jsonify(
            {
                "text": transcript,
                "language": language,
            }
        )

    except requests.exceptions.Timeout:
        return jsonify(
            {
                "error": (
                    "Speech recognition took too long."
                )
            }
        ), 504

    except requests.exceptions.ConnectionError:
        app.logger.exception(
            "Cannot connect to speech service"
        )

        return jsonify(
            {
                "error": (
                    "Cannot connect to the local "
                    "speech-recognition service."
                )
            }
        ), 503

    except requests.exceptions.RequestException as error:
        app.logger.exception(
            "Speech-recognition request failed"
        )

        return jsonify(
            {
                "error": (
                    "Speech recognition failed: "
                    f"{error}"
                )
            }
        ), 502

    except ValueError:
        app.logger.exception(
            "Speech service returned invalid JSON"
        )

        return jsonify(
            {
                "error": (
                    "Speech service returned "
                    "an invalid response."
                )
            }
        ), 502


# Non-streaming fallback endpoint
@app.post("/chat")
def chat():
    message = read_message(request.get_json(silent=True) or {})
    if not message:
        return jsonify({"error": "Message is required."}), 400

    try:
        reply = generate_reply(message)
        if not reply:
            return jsonify({"error": "Ollama returned an empty reply."}), 502

        save_conversation(message, reply)
        remember_conversation_async(
            message,
            reply,
        )
        return jsonify({"reply": reply})

    except requests.exceptions.ReadTimeout:
        return jsonify({"error": "Misa took too long to answer."}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Cannot connect to Ollama."}), 503
    except requests.exceptions.RequestException as error:
        app.logger.exception("Ollama request failed")
        return jsonify({"error": f"Ollama request failed: {error}"}), 502


# Real-time streaming endpoint
@sock.route("/ws/chat")
def websocket_chat(ws):
    while True:
        raw_data = ws.receive()
        if raw_data is None:
            break

        try:
            message = read_message(json.loads(raw_data))
            if not message:
                send_socket(ws, "error", error="Message is required.")
                continue

            parts = []
            for text in stream_reply(message):
                parts.append(text)
                send_socket(ws, "delta", text=text)

            full_reply = "".join(parts).strip()
            if not full_reply:
                send_socket(ws, "error", error="Ollama returned an empty reply.")
                continue

            save_conversation(
                message,
                full_reply,
            )
            
            send_socket(
                ws,
                "done",
                reply=full_reply,
            )
            
            remember_conversation_async(
                message,
                full_reply,
            )

        except json.JSONDecodeError:
            try:
                send_socket(
                    ws,
                    "error",
                    error="Invalid WebSocket message.",
                )
            except ConnectionClosed:
                break

        except requests.exceptions.ReadTimeout:
            try:
                send_socket(
                    ws,
                    "error",
                    error="Misa took too long to answer.",
                )
            except ConnectionClosed:
                break

        except requests.exceptions.ConnectionError:
            try:
                send_socket(
                    ws,
                    "error",
                    error="Cannot connect to Ollama.",
                )
            except ConnectionClosed:
                break

        except requests.exceptions.RequestException as error:
            app.logger.exception(
                "Streaming Ollama request failed"
            )

            try:
                send_socket(
                    ws,
                    "error",
                    error=f"Ollama request failed: {error}",
                )
            except ConnectionClosed:
                break

        except ConnectionClosed:
            # The browser tab was refreshed or closed.
            break

        except Exception:
            app.logger.exception(
                "Unexpected WebSocket error"
            )

            try:
                send_socket(
                    ws,
                    "error",
                    error="Unexpected streaming error.",
                )
            except ConnectionClosed:
                break


@app.errorhandler(Exception)
def unexpected_error(error):
    app.logger.exception("Unexpected Flask error")
    return jsonify({"error": "An unexpected server error occurred."}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True,
        threaded=True,
    )