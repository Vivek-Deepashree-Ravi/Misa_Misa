import argparse

import numpy as np
import soundfile as sf
import torch
from transformers import AutoModel


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        default="/model",
    )

    parser.add_argument(
        "--text",
        required=True,
    )

    parser.add_argument(
        "--reference-audio",
        default=(
            "/model/prompts/"
            "PAN_F_HAPPY_00001.wav"
        ),
    )

    parser.add_argument(
        "--reference-text",
        default=(
            "ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ "
            "ਕਲਾ ਦੇ ਵੇਰਵੇ ਗੁੰਝਲਦਾਰ ਅਤੇ ਹੈਰਾਨ ਕਰਨ "
            "ਵਾਲੇ ਹਨ, ਜੋ ਮੈਨੂੰ ਖੁਸ਼ ਕਰਦੇ ਹਨ।"
        ),
    )

    parser.add_argument(
        "--output",
        default="/output/misa-kannada.wav",
    )

    args = parser.parse_args()

    print("CUDA available:", torch.cuda.is_available())

    if torch.cuda.is_available():
        print(
            "GPU:",
            torch.cuda.get_device_name(0),
        )

    print("Loading IndicF5 from local files...")

    model = AutoModel.from_pretrained(
        args.model,
        trust_remote_code=True,
        local_files_only=True,
    )

    print("Generating Kannada speech...")

    audio = model(
        args.text,
        ref_audio_path=args.reference_audio,
        ref_text=args.reference_text,
    )

    if audio.dtype == np.int16:
        audio = (
            audio.astype(np.float32)
            / 32768.0
        )
    else:
        audio = np.asarray(
            audio,
            dtype=np.float32,
        )

    sf.write(
        args.output,
        audio,
        samplerate=24000,
    )

    print("Saved:", args.output)


if __name__ == "__main__":
    main()