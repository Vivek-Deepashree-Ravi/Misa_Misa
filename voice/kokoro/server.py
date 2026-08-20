import io
import os
import threading

import numpy as np
import soundfile as sf
from flask import Flask, jsonify, request, send_file
from kokoro import KPipeline


VOICE = os.getenv(
    "KOKORO_VOICE",
    "af_heart",
)

app = Flask(__name__)
generation_lock = threading.Lock()

print(
    "Loading Kokoro English TTS...",
    flush=True,
)

pipeline = KPipeline(
    lang_code="a",
)

print(
    f"Kokoro is ready. Voice: {VOICE}",
    flush=True,
)


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ready",
            "language": "en",
            "voice": VOICE,
        }
    )


@app.post("/synthesize")
def synthesize():
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

    if len(text) > 1000:
        return jsonify(
            {
                "error": (
                    "Text must be 1000 characters or less."
                )
            }
        ), 413

    if not generation_lock.acquire(
        blocking=False
    ):
        return jsonify(
            {
                "error": (
                    "English speech generation "
                    "is already running."
                )
            }
        ), 409

    try:
        audio_parts = []

        generator = pipeline(
            text,
            voice=VOICE,
            speed=1.0,
            split_pattern=r"\n+",
        )

        for _, _, audio in generator:
            if hasattr(audio, "detach"):
                audio = (
                    audio.detach()
                    .cpu()
                    .numpy()
                )

            audio = np.asarray(
                audio,
                dtype=np.float32,
            ).squeeze()

            if audio.size:
                audio_parts.append(audio)

        if not audio_parts:
            raise RuntimeError(
                "Kokoro returned empty audio."
            )

        audio = np.concatenate(
            audio_parts
        )

        peak = float(
            np.max(
                np.abs(audio)
            )
        )

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
            download_name="misa-english.wav",
        )

    except Exception as error:
        app.logger.exception(
            "Kokoro generation failed"
        )

        return jsonify(
            {
                "error": str(error)
            }
        ), 500

    finally:
        generation_lock.release()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=9004,
        debug=False,
        threaded=True,
    )