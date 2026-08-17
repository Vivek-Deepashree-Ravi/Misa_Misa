FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    "torch==2.6.0+cpu"

RUN pip install --no-cache-dir \
    "transformers>=4.46,<5" \
    "onnxruntime==1.20.1" \
    "numpy<3" \
    "huggingface_hub>=0.27" \
    "flask>=3.1,<4" \
    "gunicorn>=23,<24"

WORKDIR /app

COPY transcribe.py /app/transcribe.py
COPY server.py /app/server.py

EXPOSE 9001

CMD ["gunicorn", "--bind", "0.0.0.0:9001", "--workers", "1", "--threads", "2", "--timeout", "120", "server:app"]