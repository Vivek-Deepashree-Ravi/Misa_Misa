import json
import os
import sqlite3

import requests
from flask import Flask, jsonify, render_template, request
from flask_sock import Sock

from misa import MISA_ROLE
from rag import retrieve_context
from simple_websocket.errors import ConnectionClosed


app = Flask(__name__)
sock = Sock(app)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
DATABASE_PATH = os.getenv("DATABASE_PATH", "misa_memory.db")
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))

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


def build_messages(user_message):
    knowledge = build_rag_context(user_message)

    if knowledge:
        system_prompt = (
            "Use the retrieved facts only when they directly answer the "
            "user's current question. If they are unrelated, ignore them. "
            "Never mention RAG, retrieval, documents, filenames, sources, "
            "or the knowledge base.\n\n"
            f"RETRIEVED FACTS:\n{knowledge}\n\n"
            f"PERSONALITY:\n{MISA_ROLE}"
        )
    else:
        system_prompt = MISA_ROLE

    return [
        {"role": "system", "content": system_prompt},
        *get_chat_history(),
        {"role": "user", "content": user_message},
    ]

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


init_database()


@app.get("/")
def home():
    return render_template("index.html")


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

            save_conversation(message, full_reply)
            send_socket(ws, "done", reply=full_reply)

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