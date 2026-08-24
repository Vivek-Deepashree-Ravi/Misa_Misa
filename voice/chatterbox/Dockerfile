FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV HF_HOME=/cache/huggingface
ENV TORCH_HOME=/cache/torch

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-only PyTorch before Chatterbox so pip does not pull CUDA wheels.
RUN pip install \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.6.0 \
        torchaudio==2.6.0

RUN pip install \
        "git+https://github.com/resemble-ai/chatterbox.git@master" \
        flask==3.1.2 \
        gunicorn==23.0.0 \
        soundfile==0.13.1

COPY server.py /app/server.py

ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:9005", "--workers", "1", "--threads", "2", "--timeout", "600", "--access-logfile", "-", "--error-logfile", "-", "server:app"]
