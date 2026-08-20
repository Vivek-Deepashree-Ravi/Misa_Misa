FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV HF_HOME=/cache/huggingface

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        espeak-ng \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install \
    --index-url https://download.pytorch.org/whl/cpu \
    torch

RUN pip install \
    "kokoro>=0.9.4" \
    flask \
    gunicorn \
    numpy \
    soundfile

WORKDIR /app

COPY server.py /app/server.py

ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:9004", "--workers", "1", "--threads", "2", "--timeout", "300", "server:app"]