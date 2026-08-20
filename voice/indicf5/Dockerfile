FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV MPLBACKEND=Agg
ENV PYTHONPATH=/model

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install \
    "transformers==4.49.0" \
    "numpy==1.26.4" \
    accelerate \
    cached_path \
    click \
    datasets \
    ema_pytorch \
    flask \
    hydra-core \
    jieba \
    librosa \
    matplotlib \
    pydub \
    pypinyin \
    requests \
    safetensors \
    soundfile \
    tomli \
    torchdiffeq \
    tqdm \
    transformers_stream_generator \
    vocos \
    wandb \
    "x_transformers>=1.31.14"

WORKDIR /app

COPY generate.py /app/generate.py
COPY server.py /app/server.py

ENTRYPOINT ["python", "/app/generate.py"]