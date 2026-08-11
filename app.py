import os

import requests
from flask import Flask, jsonify, render_template, request

from misa import MISA_ROLE

import sqlite3


app = Flask(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")

DATABASE_PATH = "misa_memory.db"


def init_database():
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()

init_database()

def save_message(role, content):
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)",
            (role, content),
        )
        connection.commit()


def get_chat_history(limit=20):
    with sqlite3.connect(DATABASE_PATH) as connection:
        rows = connection.execute(
            """
            SELECT role, content
            FROM messages
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    rows.reverse()

    return [
        {"role": role, "content": content}
        for role, content in rows
    ]

@app.get("/")
def home():
    return render_template("index.html")


@app.post("/chat")
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Message is required"}), 400


    # Save the user's valid message
    save_message("user", message)
    chat_history = get_chat_history()

    ollama_response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": MISA_ROLE,
                },
                *chat_history,
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

    reply = result["message"]["content"]

    # Save Misa's response
    save_message("assistant", reply)

    return jsonify({
        "reply": reply
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True,
    )