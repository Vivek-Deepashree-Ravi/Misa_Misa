import argparse
import json
import sys
import wave

import numpy as np
import torch


def load_wav(path):
    """
    Load a mono or stereo 16-bit PCM WAV file.

    IndicConformer expects:
    - 16,000 Hz sample rate
    - floating-point samples
    - shape: [batch, samples]
    """

    with wave.open(path, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()

        audio_bytes = wav_file.readframes(
            frame_count
        )

    if sample_width != 2:
        raise ValueError(
            "Audio must use signed 16-bit PCM samples."
        )

    if sample_rate != 16000:
        raise ValueError(
            "Audio must use a 16000 Hz sample rate. "
            f"Received: {sample_rate} Hz."
        )

    audio = np.frombuffer(
        audio_bytes,
        dtype=np.int16,
    ).astype(np.float32)

    if channels > 1:
        audio = audio.reshape(
            -1,
            channels,
        ).mean(axis=1)

    audio /= 32768.0

    waveform = torch.from_numpy(
        audio
    ).unsqueeze(0)

    return waveform


def load_local_model(model_path):
    """
    Load IndicConformer directly from local model files.

    This bypasses the model repository's from_pretrained()
    method because that method always calls Hugging Face's
    snapshot_download(), even when a local directory is used.
    """

    sys.path.insert(
        0,
        model_path,
    )

    from model_onnx import (
        IndicASRConfig,
        IndicASRModel,
    )

    config_path = (
        f"{model_path}/config.json"
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
        ts_folder=model_path,
        **config_values,
    )

    model = IndicASRModel(
        config
    )

    model.eval()

    return model


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run AI4Bharat IndicConformer "
            "using local offline model files."
        )
    )

    parser.add_argument(
        "--model",
        required=True,
        help=(
            "Path to the local IndicConformer "
            "model directory."
        ),
    )

    parser.add_argument(
        "--audio",
        required=True,
        help=(
            "Path to a 16 kHz, 16-bit PCM "
            "WAV audio file."
        ),
    )

    parser.add_argument(
        "--language",
        default="kn",
        help=(
            "Language code. Use 'kn' for Kannada."
        ),
    )

    parser.add_argument(
        "--decoder",
        choices=(
            "ctc",
            "rnnt",
        ),
        default="ctc",
        help=(
            "IndicConformer decoding method."
        ),
    )

    args = parser.parse_args()

    print(
        "Loading IndicConformer from local files..."
    )

    model = load_local_model(
        args.model
    )

    print(
        f"Loading audio: {args.audio}"
    )

    waveform = load_wav(
        args.audio
    )

    print(
        f"Transcribing Kannada with "
        f"{args.decoder.upper()}..."
    )

    with torch.inference_mode():
        transcript = model(
            waveform,
            args.language,
            args.decoder,
        )

    print(
        f"Transcript: {transcript}"
    )


if __name__ == "__main__":
    main()