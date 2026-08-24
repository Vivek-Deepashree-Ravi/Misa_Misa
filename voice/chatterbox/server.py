import io
import os
import threading

import numpy as np
import soundfile as sf
import torch
from chatterbox.tts_turbo import ChatterboxTurboTTS
from flask import Flask, jsonify, request, send_file


app = Flask(__name__)

MAX_TEXT_LENGTH = int(
    os.getenv(
        "MAX_TEXT_LENGTH",
        "1000",
    )
)

TORCH_THREADS = int(
    os.getenv(
        "TORCH_THREADS",
        "8",
    )
)

REFERENCE_AUDIO = os.getenv(
    "CHATTERBOX_REFERENCE_AUDIO",
    "",
).strip()

torch.set_num_threads(
    max(1, TORCH_THREADS)
)

model = None
model_error = None
model_lock = threading.Lock()


def load_model():
    """Load Chatterbox Nano once in the background."""

    global model
    global model_error

    try:
        app.logger.warning(
            "Loading Chatterbox Nano on CPU..."
        )

        model = ChatterboxTurboTTS.from_pretrained(
            device="cpu",
            nano=True,
        )

        app.logger.warning(
            "Chatterbox Nano is ready."
        )

    except Exception as error:
        model_error = str(error)
        app.logger.exception(
            "Unable to load Chatterbox Nano"
        )


threading.Thread(
    target=load_model,
    daemon=True,
).start()


@app.get("/health")
def health():
    if model_error:
        return jsonify(
            {
                "status": "error",
                "model": "chatterbox-nano",
                "device": "cpu",
                "error": model_error,
            }
        ), 500

    if model is None:
        return jsonify(
            {
                "status": "loading",
                "model": "chatterbox-nano",
                "device": "cpu",
            }
        ), 503

    return jsonify(
        {
            "status": "ready",
            "model": "chatterbox-nano",
            "device": "cpu",
            "sample_rate": model.sr,
            "reference_audio": bool(
                REFERENCE_AUDIO
            ),
        }
    )


@app.post("/synthesize")
def synthesize():
    if model_error:
        return jsonify(
            {
                "error": (
                    "Chatterbox Nano could not load: "
                    f"{model_error}"
                )
            }
        ), 503

    if model is None:
        return jsonify(
            {
                "error": (
                    "Chatterbox Nano is still loading."
                )
            }
        ), 503

    body = request.get_json(
        silent=True
    ) or {}

    text = str(
        body.get(
            "text",
            "",
        )
    ).strip()

    if not text:
        return jsonify(
            {
                "error": "JSON field 'text' is required."
            }
        ), 400

    if len(text) > MAX_TEXT_LENGTH:
        return jsonify(
            {
                "error": (
                    f"Text must be {MAX_TEXT_LENGTH} "
                    "characters or less."
                )
            }
        ), 413

    generation_options = {}

    if REFERENCE_AUDIO:
        if not os.path.isfile(
            REFERENCE_AUDIO
        ):
            return jsonify(
                {
                    "error": (
                        "Configured reference audio "
                        "does not exist."
                    )
                }
            ), 500

        generation_options[
            "audio_prompt_path"
        ] = REFERENCE_AUDIO

    try:
        with model_lock:
            with torch.inference_mode():
                waveform = model.generate(
                    text,
                    **generation_options,
                )

        audio = waveform.detach().cpu().float()
        audio = np.asarray(
            audio.squeeze().numpy(),
            dtype=np.float32,
        )

        if audio.size == 0:
            raise RuntimeError(
                "Chatterbox returned an empty waveform."
            )

        output = io.BytesIO()

        sf.write(
            output,
            audio,
            samplerate=model.sr,
            format="WAV",
            subtype="PCM_16",
        )

        output.seek(0)

        return send_file(
            output,
            mimetype="audio/wav",
            as_attachment=False,
            download_name="chatterbox-nano.wav",
            max_age=0,
        )

    except Exception as error:
        app.logger.exception(
            "Chatterbox synthesis failed"
        )

        return jsonify(
            {
                "error": (
                    "Chatterbox synthesis failed: "
                    f"{error}"
                )
            }
        ), 500
