# 🌸 Misa-Misa Local AI Companion

A **locally hosted AI companion** inspired by Misa Amane, powered by **Ollama** and **Qwen3 1.7B**.

Misa-Misa provides a simple web-based chat interface built with Flask. Everything runs locally through Docker Compose, so **no external AI API key is required**.

> ⚠️ **Fan Project:** This is an unofficial fan-made project inspired by a fictional character. It is not affiliated with or endorsed by the creators, publishers, or rights holders of *Death Note*.

---

## ✨ Features

* 🌸 Misa-inspired AI companion interface
* 💬 Responsive desktop and mobile chat UI
* 🤖 Local AI inference using Ollama
* 🧠 Qwen3 1.7B language model
* 🐍 Flask web application
* 🔌 Flask JSON chat API
* 🐳 Complete Docker Compose setup
* 💾 Persistent Ollama model storage
* 🔐 No external AI API key required
* 🛡️ HTML-safe message rendering using `textContent`
* ⚡ Optimized configuration for CPU-based inference
* 🔄 Model remains available between container restarts


## 🏗️ Architecture

```text
                    ┌─────────────────────┐
                    │      Browser        │
                    │  Desktop / Mobile   │
                    └──────────┬──────────┘
                               │
                               │ HTTP
                               ▼
                    ┌─────────────────────┐
                    │     Misa Flask      │
                    │      Web App        │
                    │      Port 8000      │
                    └──────────┬──────────┘
                               │
                               │ HTTP
                               ▼
                    ┌─────────────────────┐
                    │       Ollama        │
                    │      Port 11434     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    Qwen3 1.7B       │
                    │    Local Model      │
                    └─────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Docker Volume       │
                    │ misa_ollama_models  │
                    └─────────────────────┘
```

---

## 🛠️ Technology Stack

| Technology     | Purpose                       |
| -------------- | ----------------------------- |
| Python 3.11    | Backend runtime               |
| Flask          | Web server and JSON API       |
| Ollama         | Local LLM inference           |
| Qwen3 1.7B     | Language model                |
| HTML           | Web interface                 |
| CSS            | UI styling                    |
| JavaScript     | Chat interaction              |
| Docker         | Containerization              |
| Docker Compose | Multi-container orchestration |

---

## 📁 Project Structure

```text
misa_amane/
│
├── app.py
├── persona.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
│
├── static/
│   ├── css/
│   │   └── style.css
│   │
│   └── images/
│       └── misa.jpeg
│
└── templates/
    └── index.html
```

---

# 🚀 Getting Started

## Prerequisites

Make sure the following are installed:

* [Docker Engine](https://docs.docker.com/engine/)
* [Docker Compose v2](https://docs.docker.com/compose/)

Verify your installation:

```bash
docker --version
docker compose version
```

---

## 📥 Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd misa_amane
```

Replace `<YOUR_REPOSITORY_URL>` with your GitHub repository URL.

---

# ▶️ Run the Application

Build and start all services:

```bash
docker compose up --build
```

On the first startup, the `model-pull` service downloads:

```text
qwen3:1.7b
```

The model is approximately **1.4 GB**.

The initial startup may take some time depending on your internet connection and hardware.

Once downloaded, the model is stored in a persistent Docker volume and does not need to be downloaded again.

---

## 🌐 Open the Application

Once the containers are running, open:

```text
http://localhost:8000
```

Ollama is also exposed locally at:

```text
http://localhost:11434
```

---

# 💤 Run in Background

To run the application in detached mode:

```bash
docker compose up --build -d
```

View the logs:

```bash
docker compose logs -f misa ollama
```

Stop the application:

```bash
docker compose down
```

> `docker compose down` stops and removes the containers but **does not delete the downloaded model**.

---

# 🧩 Services

| Service      | Container         | Purpose                        | Port    |
| ------------ | ----------------- | ------------------------------ | ------- |
| `misa`       | `misa-app`        | Flask web application          | `8000`  |
| `ollama`     | `misa-ollama`     | Local model server             | `11434` |
| `model-pull` | `misa-model-pull` | Ensures the model is available | None    |

---

# 💾 Model Storage

Ollama stores the downloaded model in the named Docker volume:

```text
misa_ollama_models
```

The model persists across:

```bash
docker compose down
```

container restarts, and Flask image rebuilds.

The `model-pull` service checks whether the model already exists before downloading it.

---

## 🔍 Inspect the Model Volume

Inspect the Docker volume:

```bash
docker volume inspect misa_ollama_models
```

List installed Ollama models:

```bash
docker compose exec ollama ollama list
```

---

# 🧪 Test Ollama Directly

You can test the model without using the Flask interface:

```bash
docker compose exec ollama ollama run qwen3:1.7b "Reply with only: Misa is ready"
```

Expected response:

```text
Misa is ready
```

> Use the exact model name `qwen3:1.7b`.
> `MODEL_NAME` is only an example placeholder and should not be used as a command argument.

Check which models are currently loaded:

```bash
docker compose exec ollama ollama ps
```

---

# ⚙️ Configuration

The Flask container receives the following environment variables from `docker-compose.yml`:

```yaml
environment:
  OLLAMA_URL: http://ollama:11434
  OLLAMA_MODEL: qwen3:1.7b
```

The Python application can read these values using:

```python
import os

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_URL",
    "http://ollama:11434"
)

OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:1.7b"
)
```

---

# ⚡ Qwen3 CPU Optimization

For CPU-only inference, response times can be improved by disabling extended thinking and limiting the generated output.

Example configuration:

```python
payload = {
    "model": OLLAMA_MODEL,
    "stream": False,
    "think": False,
    "keep_alive": "10m",
    "messages": messages,
    "options": {
        "num_predict": 250,
        "temperature": 0.8,
    },
}
```

### Why these options?

| Option             | Purpose                            |
| ------------------ | ---------------------------------- |
| `think: false`     | Disables extended reasoning        |
| `keep_alive: 10m`  | Keeps the model loaded             |
| `num_predict: 250` | Limits response length             |
| `temperature: 0.8` | Controls response creativity       |
| `stream: false`    | Returns one complete JSON response |

---

# 🔧 Development

The project directory is bind-mounted into `/app`, allowing changes to HTML, CSS, Python, and persona files to appear inside the Flask container.

After modifying Python code, restart Flask:

```bash
docker compose restart misa
```

Follow only the Flask logs:

```bash
docker compose logs -f misa
```

For HTML/CSS/JavaScript changes, simply refresh the browser.

If the browser is using cached files:

```text
Ctrl + Shift + R
```

---

# 🐛 Troubleshooting

## Chat Request Returns HTTP 500 or Times Out

Check the running containers:

```bash
docker compose ps
```

Then inspect the logs:

```bash
docker compose logs -f misa ollama
```

Check that the model is installed:

```bash
docker compose exec ollama ollama list
```

Test the model directly:

```bash
docker compose exec ollama ollama run qwen3:1.7b "Reply with only: Misa is ready"
```

The first response may be slow because Ollama needs to load the model into memory.

CPU-only inference will also be slower than GPU inference.

Recommended settings:

```text
keep_alive = 10m
num_predict = 250
timeout = (10, 300)
```

Your Flask application should also handle:

```python
requests.exceptions.ReadTimeout
```

so that slow model responses return a clear JSON error instead of an unhandled Flask exception.

---

## ❌ Flask Cannot Connect to Ollama

Inside Docker, the Flask application must connect to:

```text
http://ollama:11434
```

Do **not** use:

```text
http://localhost:11434
```

from inside the Flask container.

Why?

Inside Docker:

```text
localhost
```

refers to the **current container**, not the Ollama container.

Docker Compose provides service-to-service networking, so Flask should use the service name:

```text
ollama
```

---

# ✅ Validate Docker Compose

Before starting the application, you can validate your Compose configuration:

```bash
docker compose config
```

This is useful for detecting YAML formatting and configuration errors.

---

# 📋 Useful Commands

### Start and build

```bash
docker compose up --build
```

### Start in background

```bash
docker compose up --build -d
```

### Show container status

```bash
docker compose ps
```

### Follow application and Ollama logs

```bash
docker compose logs -f misa ollama
```

### Restart Flask

```bash
docker compose restart misa
```

### List installed models

```bash
docker compose exec ollama ollama list
```

### Show loaded models

```bash
docker compose exec ollama ollama ps
```

### Stop containers while preserving the model

```bash
docker compose down
```

---

# 🔐 Privacy

Misa-Misa is designed for **local AI inference**.

Your prompts and generated responses are processed by the local Ollama server running in Docker.

No hosted AI API is required by the default setup.

However, review any additional integrations or external services you add before using sensitive or private information.

---

# 🎭 Character

Misa-Misa is designed as a fictional AI companion inspired by **Misa Amane** from *Death Note*.

The `persona.py` file contains the character/personality configuration used by the application.

You can modify the persona to experiment with different:

* Personalities
* Speaking styles
* Greetings
* Response behavior
* Character traits

---

# 🗺️ Roadmap

Potential future improvements:

* [ ] Streaming responses
* [ ] Conversation history
* [ ] Long-term memory
* [ ] Voice input
* [ ] Text-to-speech
* [ ] Wake-word activation
* [ ] Multiple AI personalities
* [ ] Model selection from the UI
* [ ] GPU acceleration
* [ ] Authentication
* [ ] PWA/mobile support
* [ ] Custom avatar animations
* [ ] Emotion/state system

---


# 📜 Disclaimer

Misa-Misa is a **fan-made, unofficial project** inspired by the fictional character Misa Amane from *Death Note*.

This project is **not affiliated with, sponsored by, or endorsed by** the creators, publishers, studios, or rights holders of *Death Note*.

All related character names, imagery, and intellectual property belong to their respective rights holders.

This project is intended for **personal, educational, and experimental use**.

---

