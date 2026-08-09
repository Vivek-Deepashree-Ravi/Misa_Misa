import os

import requests
from flask import Flask, jsonify, render_template, request

from misa import MISA_ROLE


app = Flask(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/chat")
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Message is required"}), 400

    ollama_response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": MISA_ROLE,
                },
                {
                    "role": "user",
                    "content": message,
                }   
            ],
            "stream": False,

            "options": {
                "temperature": 0.8,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        },
        timeout=120,
    )

    ollama_response.raise_for_status()
    result = ollama_response.json()

    return jsonify({
        "reply": result["message"]["content"]
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True,
    )