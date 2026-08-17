import io
import json
import os
import sys
import threading
import wave

import numpy as np
import torch
from flask import Flask, jsonify, request


MODEL_PATH = os.getenv(
    "INDIC_MODEL_PATH",
    "/model",
)

LANGUAGE = os.getenv(
    "INDIC_LANGUAGE",
    "kn",
)

DECODER = os.getenv(
    "INDIC_DECODER",
    "ctc",
)

app = Flask(__name__)

app.json.ensure_ascii = False

app.config["MAX_CONTENT_LENGTH"] = (
    16 * 1024 * 1024
)

model_lock = threading.Lock()


def load_wav_bytes(audio_bytes):
    """
    Convert a 16 kHz, 16-bit PCM WAV file into a
    [batch, samples] float tensor.
    """

    with wave.open(
        io.BytesIO(audio_bytes),
        "rb",
    ) as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()

        pcm_bytes = wav_file.readframes(
            frame_count
        )

    if sample_width != 2:
        raise ValueError(
            "Audio must use signed 16-bit PCM."
        )

    if sample_rate != 16000:
        raise ValueError(
            "Audio must use a 16000 Hz sample rate."
        )

    audio = np.frombuffer(
        pcm_bytes,
        dtype=np.int16,
    ).astype(np.float32)

    if channels > 1:
        audio = audio.reshape(
            -1,
            channels,
        ).mean(axis=1)

    audio /= 32768.0

    return torch.from_numpy(
        audio
    ).unsqueeze(0)


def load_model():
    """
    Load the downloaded model directly without
    contacting Hugging Face.
    """

    sys.path.insert(
        0,
        MODEL_PATH,
    )

    from model_onnx import (
        IndicASRConfig,
        IndicASRModel,
    )

    config_path = (
        f"{MODEL_PATH}/config.json"
    )

    with open(
        config_path,
        "r",
        encoding="utf-8",
    ) as config_file:
        config_values = json.load(
            config_file
        )

    config = IndicASRConfig(
        ts_folder=MODEL_PATH,
        **config_values,
    )

    loaded_model = IndicASRModel(
        config
    )

    loaded_model.eval()

    return loaded_model


print(
    "Loading IndicConformer into memory..."
)

model = load_model()

print(
    "IndicConformer is ready."
)


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ready",
            "language": LANGUAGE,
            "decoder": DECODER,
            "offline": True,
        }
    )


@app.post("/transcribe")
def transcribe():
    uploaded_audio = request.files.get(
        "audio"
    )

    if uploaded_audio is None:
        return jsonify(
            {
                "error": (
                    "Multipart field 'audio' is required."
                )
            }
        ), 400

    try:
        waveform = load_wav_bytes(
            uploaded_audio.read()
        )

        with model_lock:
            with torch.inference_mode():
                transcript = model(
                    waveform,
                    LANGUAGE,
                    DECODER,
                )

        return jsonify(
            {
                "text": str(transcript).strip(),
                "language": LANGUAGE,
                "decoder": DECODER,
            }
        )

    except (ValueError, wave.Error) as error:
        return jsonify(
            {
                "error": str(error)
            }
        ), 400

    except Exception:
        app.logger.exception(
            "Kannada transcription failed"
        )

        return jsonify(
            {
                "error": "Transcription failed."
            }
        ), 500