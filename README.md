# 🌸 Misa-Misa Local AI Companion

A private, locally hosted AI companion inspired by Misa Amane. Misa runs through Docker Compose using Flask, Ollama, Qwen3, SQLite, Qdrant, document RAG, and Mem0 long-term memory.

No hosted AI API key is required by the default configuration.

> **Fan project:** This is an unofficial fan-made project. It is not affiliated with or endorsed by the creators, publishers, studios, or rights holders of *Death Note*.

## ✨ Features

- Responsive Misa-inspired chat interface
- Flask HTTP API and real-time WebSocket streaming
- Local Qwen3 1.7B inference through Ollama
- GPU-enabled Ollama container
- SQLite recent conversation history
- Document RAG using Qdrant and `embeddinggemma`
- Mem0 long-term personal memory
- Separate vector collections for documents and personal memories
- Persistent models, vectors, and conversations
- No external AI API key required

## 🏗️ Architecture

```text
Browser
   │ HTTP / WebSocket
   ▼
Flask application (port 8000)
   ├── misa.py
   │     Character identity and behavior
   ├── SQLite: misa_memory.db
   │     Recent complete conversation messages
   ├── long_term_memory.py → Mem0
   │     Durable facts about Sonu
   │                └── Qdrant: misa_personal_memories
   ├── rag.py
   │     Document ingestion and retrieval
   │                └── Qdrant: misa_knowledge
   └── Ollama (port 11434)
         ├── qwen3:1.7b
         └── embeddinggemma
```

Each response combines:

```text
Misa persona
+ relevant Mem0 personal memories
+ relevant document RAG results
+ recent SQLite conversation history
+ current message
→ Qwen response
```

After each response:

```text
Complete exchange → SQLite
Sonu's message    → Mem0 durable-fact extraction
```

Misa's generated reply is deliberately excluded from Mem0 extraction so role-play and hallucinations do not become facts about Sonu.

## 🧠 Memory and knowledge

| System | Storage | Purpose |
| --- | --- | --- |
| Recent conversation | SQLite (`misa_memory.db`) | Recent conversational continuity |
| Long-term memory | Mem0 + Qdrant (`misa_personal_memories`) | Durable preferences, goals, constraints, and decisions |
| Document knowledge | `rag.py` + Qdrant (`misa_knowledge`) | Relevant text retrieved from indexed files |
| Character behavior | `misa.py` | Misa's identity, tone, and behavior |

SQLite stores complete messages. Mem0 stores selected user facts. Document RAG stores file knowledge. They are intentionally separate.

## 🛠️ Technology stack

| Technology | Purpose |
| --- | --- |
| Python 3.11 | Backend runtime |
| Flask / Flask-Sock | HTTP server and WebSockets |
| Ollama | Local model inference |
| Qwen3 1.7B | Conversation and memory extraction |
| embeddinggemma | Vector embeddings |
| SQLite | Recent conversation storage |
| Qdrant | Persistent vector database |
| Mem0 OSS | Long-term personal memory |
| Docker Compose | Service orchestration |

## 📁 Project structure

```text
misa_amane/
├── app.py
├── misa.py
├── rag.py
├── long_term_memory.py
├── misa_memory.db
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── README.md
├── documents/
├── static/
│   ├── css/style.css
│   └── images/misa.jpeg
└── templates/index.html
```

SQLite may create `misa_memory.db-wal` and `misa_memory.db-shm` while running. They are normal WAL support files; do not delete them while Misa is active.

## 🚀 Getting started

### Prerequisites

- [Docker Engine](https://docs.docker.com/engine/)
- [Docker Compose v2](https://docs.docker.com/compose/)
- NVIDIA Container Toolkit for GPU acceleration

```bash
docker --version
docker compose version
```

### Clone and start

```bash
git clone <YOUR_REPOSITORY_URL>
cd misa_amane
docker compose up -d --build
```

The first startup ensures these models are present:

```text
qwen3:1.7b
embeddinggemma
```

`model-pull` and `embedding-pull` exit after completing their commands. `Exited (0)` is expected.

Open:

```text
http://localhost:8000
```

Stop while preserving data:

```bash
docker compose down
```

Do not add `-v` unless you intentionally want to remove named-volume data.

## 🧩 Services

| Service | Container | Purpose | Port |
| --- | --- | --- | --- |
| `misa` | `misa-app` | Flask application | `8000` |
| `ollama` | `misa-ollama` | Local model server | `11434` |
| `qdrant` | `misa-qdrant` | Vector database | `6333` localhost only |
| `model-pull` | `misa-model-pull` | Ensures Qwen exists | None |
| `embedding-pull` | `misa-embedding-pull` | Ensures embedder exists | None |

## 💾 Persistence

| Data | Storage |
| --- | --- |
| Ollama models | `misa_ollama_models` volume |
| Qdrant collections | `misa_qdrant_data` volume |
| Conversation history | Bind-mounted `misa_memory.db` |

Normal restarts and `docker compose down` preserve all three.

## ⚙️ Environment

```yaml
environment:
  OLLAMA_URL: http://ollama:11434
  OLLAMA_MODEL: qwen3:1.7b
  QDRANT_URL: http://qdrant:6333
  QDRANT_HOST: qdrant
  QDRANT_PORT: "6333"
  RAG_EMBED_MODEL: embeddinggemma
  RAG_COLLECTION: misa_knowledge
  MEM0_TELEMETRY: "false"
  MEM0_LLM_MODEL: qwen3:1.7b
  MEM0_EMBED_MODEL: embeddinggemma
  MEM0_COLLECTION: misa_personal_memories
  MEM0_USER_ID: sonu
```

Inside Docker, use service names `ollama` and `qdrant`; `localhost` refers to the current container.

## 📚 Document RAG

RAG reads a file, splits its text into chunks, creates embeddings, and stores them in `misa_knowledge`.

### Ingest

```bash
docker compose exec misa \
  python rag.py ingest /app/documents/example.txt
```

### Search

```bash
docker compose exec misa \
  python rag.py search "What does the document say?"
```

### Count indexed chunks

```bash
docker compose exec misa python -c \
  "from rag import qdrant, COLLECTION_NAME; print(qdrant.count(collection_name=COLLECTION_NAME, exact=True))"
```

RAG context is internal. Ordinary replies should not expose filenames, sources, embeddings, or scores.

## 🧠 Mem0 long-term memory

Mem0 OSS uses Qwen through Ollama for durable-fact extraction, `embeddinggemma` for embeddings, and Qdrant for persistent storage.

### List memories

```bash
docker compose exec misa python -c \
  "from long_term_memory import get_all_personal_memories; import json; print(json.dumps(get_all_personal_memories(), indent=2, default=str))"
```

### Search memories

```bash
docker compose exec misa python -c \
  "from long_term_memory import search_personal_memories; import json; print(json.dumps(search_personal_memories('Which coding language does Sonu prefer?'), indent=2, default=str))"
```

### Add a test memory

```bash
docker compose exec misa python -c \
  "from long_term_memory import add_conversation_memory; import json; print(json.dumps(add_conversation_memory('My preferred programming language is Python.'), indent=2, default=str))"
```

### Back up memories

```bash
docker compose exec misa python -c \
  "from long_term_memory import get_all_personal_memories; import json; print(json.dumps(get_all_personal_memories(), indent=2, default=str))" \
  > mem0_memory_backup.json
```

### Delete Sonu's Mem0 memories

This does not delete SQLite history or document RAG:

```bash
docker compose exec misa python -c \
  "from long_term_memory import memory, MEM0_USER_ID; print(memory.delete_all(user_id=MEM0_USER_ID))"
```

## 🗨️ SQLite conversation history

### Count messages

```bash
docker compose exec misa python -c \
  "import sqlite3; db=sqlite3.connect('/app/misa_memory.db'); print(db.execute('SELECT COUNT(*) FROM messages').fetchone()); db.close()"
```

### View recent messages

```bash
docker compose exec misa python -c \
  "import sqlite3; db=sqlite3.connect('/app/misa_memory.db'); print(db.execute('SELECT role, content, created_at FROM messages ORDER BY id DESC LIMIT 10').fetchall()); db.close()"
```

### Clear recent history

This does not delete Mem0 or document RAG:

```bash
docker compose exec misa python -c \
  "import sqlite3; db=sqlite3.connect('/app/misa_memory.db'); db.execute('DELETE FROM messages'); db.commit(); db.close(); print('Conversation history cleared')"
```

## 🧪 Validation

```bash
docker compose config --quiet
```

```bash
docker compose exec misa python -m py_compile \
  app.py misa.py rag.py long_term_memory.py
```

No output means validation passed.

Test Ollama:

```bash
docker compose exec ollama \
  ollama run qwen3:1.7b "Reply with only: Misa is ready"
```

Test application RAG:

```bash
docker compose exec misa python -c \
  "import app; print(repr(app.build_rag_context('What does the indexed document say?')))"
```

Test application Mem0 retrieval:

```bash
docker compose exec misa python -c \
  "import app; print(app.build_personal_memory_context('Which programming language do I prefer?'))"
```

Test a complete backend response:

```bash
docker compose exec misa python -c \
  "import app; print(app.generate_reply('Which programming language do I prefer?'))"
```

## 🐛 Debugging commands

### Container state and logs

```bash
docker compose ps -a
docker compose logs --tail=100 misa ollama qdrant
docker compose logs -f misa
```

### Helper exit codes

```bash
docker inspect misa-model-pull --format='Exit code: {{.State.ExitCode}}'
docker inspect misa-embedding-pull --format='Exit code: {{.State.ExitCode}}'
```

`Exit code: 0` means successful completion.

### Installed and loaded models

```bash
docker compose exec ollama ollama list
docker compose exec ollama ollama ps
```

### GPU

```bash
nvidia-smi
```

### Service connectivity from Flask

```bash
docker compose exec misa python -c \
  "import requests; print(requests.get('http://ollama:11434/api/tags', timeout=10).status_code)"
```

```bash
docker compose exec misa python -c \
  "import requests; print(requests.get('http://qdrant:6333/collections', timeout=10).json())"
```

### Qdrant collections

```bash
docker compose exec misa python -c \
  "from qdrant_client import QdrantClient; client=QdrantClient(url='http://qdrant:6333'); print([item.name for item in client.get_collections().collections])"
```

Expected:

```text
misa_knowledge
misa_personal_memories
```

### Confirm code visible inside the container

```bash
docker compose exec misa grep -n "minimum_score" /app/app.py
docker compose exec misa grep -n "add_conversation_memory" /app/long_term_memory.py
```

### Restart after Python changes

```bash
docker compose restart misa
docker compose logs --tail=50 misa
```

Rebuild after changing dependencies or the Dockerfile:

```bash
docker compose up -d --build
```

Hard-refresh cached browser assets:

```text
Ctrl + Shift + R
```

### WebSocket close code 1005

This normally means the tab refreshed or closed during streaming. `app.py` should catch `simple_websocket.errors.ConnectionClosed` before its general exception handler.

### Mem0 spaCy and BM25 warnings

Warnings stating that spaCy or FastEmbed is missing do not block semantic search. The base configuration continues using `embeddinggemma`. Optional NLP/BM25 extras can be installed later if needed.

## 🔐 Privacy

The default configuration uses local Mem0 OSS, Ollama, Qdrant, and SQLite. It requires no Mem0 Cloud or hosted AI API.

```yaml
MEM0_TELEMETRY: "false"
```

Do not add a `MEM0_API_KEY`, `OPENAI_API_KEY`, or hosted provider unless external processing is intentional.

## 🎭 Character

`misa.py` defines Misa's identity, background, speaking style, technical behavior, and boundaries. Memory and RAG add relevant context without replacing factual accuracy or technical usefulness.


## 📜 Disclaimer

Misa-Misa is a fan-made, unofficial project inspired by Misa Amane from *Death Note*. It is not affiliated with, sponsored by, or endorsed by the creators, publishers, studios, or rights holders. Related names, imagery, and intellectual property belong to their respective rights holders.

This project is intended for personal, educational, and experimental use.