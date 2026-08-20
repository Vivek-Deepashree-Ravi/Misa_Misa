import gc
import io
import os
import sys
import threading

import numpy as np
import requests
import soundfile as sf
import torch
from flask import Flask, jsonify, request, send_file

MODEL_PATH = os.getenv("INDICF5_MODEL_PATH", "/model")
OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://ollama:11434",
).rstrip("/")
OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:1.7b",
)

REFERENCE_AUDIO = os.getenv(
    "INDICF5_REFERENCE_AUDIO",
    "/model/prompts/PAN_F_HAPPY_00001.wav",
)

REFERENCE_TEXT = os.getenv(
    "INDICF5_REFERENCE_TEXT",
    (
        "ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ ਕਲਾ ਦੇ "
        "ਵੇਰਵੇ ਗੁੰਝਲਦਾਰ ਅਤੇ ਹੈਰਾਨ ਕਰਨ ਵਾਲੇ ਹਨ, "
        "ਜੋ ਮੈਨੂੰ ਖੁਸ਼ ਕਰਦੇ ਹਨ।"
    ),
)

if MODEL_PATH not in sys.path:
    sys.path.insert(0, MODEL_PATH)

from model import INF5Config, INF5Model

app = Flask(__name__)
generation_lock = threading.Lock()

service_state = {
    "status": "ready",
    "model_loaded": False,
}


def unload_qwen():
    """Ask Ollama to release Qwen's GPU memory."""

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": "",
                "stream": False,
                "keep_alive": 0,
            },
            timeout=(5, 60),
        )
        response.raise_for_status()
        print("Qwen unloaded from GPU.", flush=True)

    except Exception as error:
        print(
            f"Warning: could not unload Qwen: {error}",
            flush=True,
        )


def warm_qwen():
    """Reload Qwen after IndicF5 releases GPU memory."""

    try:
        print("Warming Qwen again...", flush=True)

        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": "",
                "stream": False,
                "keep_alive": "30m",
                "options": {
                    "num_predict": 1,
                },
            },
            timeout=(5, 180),
        )
        response.raise_for_status()

        print("Qwen is warm again.", flush=True)

    except Exception as error:
        print(
            f"Warning: Qwen warmup failed: {error}",
            flush=True,
        )


def release_gpu(model):
    """Delete IndicF5 and return its VRAM to CUDA."""

    del model

    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()

    service_state["model_loaded"] = False

    print("IndicF5 GPU memory released.", flush=True)


def load_indicf5():
    print("Loading IndicF5...", flush=True)

    config = INF5Config.from_pretrained(
        MODEL_PATH,
        local_files_only=True,
    )

    model = INF5Model(config)
    model.eval()

    service_state["model_loaded"] = True

    print("IndicF5 ready.", flush=True)

    return model


@app.get("/health")
def health():
    return jsonify(
        {
            "status": service_state["status"],
            "model_loaded": service_state[
                "model_loaded"
            ],
            "cuda": torch.cuda.is_available(),
            "offline_model": True,
        }
    )


@app.post("/synthesize")
def synthesize():
    body = request.get_json(silent=True) or {}

    text = str(body.get("text", "")).strip()

    if not text:
        return jsonify(
            {
                "error": "JSON field 'text' is required."
            }
        ), 400

    if len(text) > 1000:
        return jsonify(
            {
                "error": "Text must be 1000 characters or less."
            }
        ), 413

    if not generation_lock.acquire(blocking=False):
        return jsonify(
            {
                "error": "TTS generation is already running."
            }
        ), 409

    model = None

    try:
        service_state["status"] = "unloading-llm"
        unload_qwen()

        service_state["status"] = "loading-tts"
        model = load_indicf5()

        service_state["status"] = "generating"

        print(
            f"Generating: {text}",
            flush=True,
        )

        with torch.inference_mode():
            audio = model(
                text,
                ref_audio_path=REFERENCE_AUDIO,
                ref_text=REFERENCE_TEXT,
            )

        audio = np.asarray(
            audio,
            dtype=np.float32,
        ).squeeze()

        if audio.size == 0:
            raise RuntimeError(
                "IndicF5 returned empty audio."
            )

        peak = float(np.max(np.abs(audio)))

        if peak > 1.0:
            audio = audio / peak

        output = io.BytesIO()

        sf.write(
            output,
            audio,
            samplerate=24000,
            format="WAV",
            subtype="PCM_16",
        )

        output.seek(0)

        return send_file(
            output,
            mimetype="audio/wav",
            as_attachment=False,
            download_name="misa-kannada.wav",
        )

    except torch.cuda.OutOfMemoryError:
        return jsonify(
            {
                "error": (
                    "Not enough GPU memory for IndicF5."
                )
            }
        ), 503

    except Exception as error:
        print(
            f"TTS generation failed: {error}",
            flush=True,
        )

        return jsonify(
            {
                "error": str(error)
            }
        ), 500

    finally:
        service_state["status"] = "releasing-tts"

        if model is not None:
            release_gpu(model)

        service_state["status"] = "ready"
        generation_lock.release()

        threading.Thread(
            target=warm_qwen,
            daemon=True,
        ).start()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=9003,
        debug=False,
        threaded=True,
    )
