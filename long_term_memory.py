import os

from mem0 import Memory


OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://ollama:11434",
).rstrip("/")

QDRANT_HOST = os.getenv(
    "QDRANT_HOST",
    "qdrant",
)

QDRANT_PORT = int(
    os.getenv("QDRANT_PORT", "6333")
)

MEM0_LLM_MODEL = os.getenv(
    "MEM0_LLM_MODEL",
    "qwen3:1.7b",
)

MEM0_EMBED_MODEL = os.getenv(
    "MEM0_EMBED_MODEL",
    "embeddinggemma",
)

MEM0_COLLECTION = os.getenv(
    "MEM0_COLLECTION",
    "misa_personal_memories",
)

MEM0_USER_ID = os.getenv(
    "MEM0_USER_ID",
    "sonu",
)


MEM0_CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": MEM0_COLLECTION,
            "host": QDRANT_HOST,
            "port": QDRANT_PORT,
            "embedding_model_dims": 768,
        },
    },
    "llm": {
        "provider": "ollama",
        "config": {
            "model": MEM0_LLM_MODEL,
            "ollama_base_url": OLLAMA_URL,
            "temperature": 0.1,
            "max_tokens": 1000,
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": MEM0_EMBED_MODEL,
            "ollama_base_url": OLLAMA_URL,
        },
    },
}


memory = Memory.from_config(MEM0_CONFIG)

def add_conversation_memory(
    user_message,
    assistant_reply=None,
    user_id=MEM0_USER_ID,
):
    """
    Extract durable facts only from Sonu's message.

    Misa's generated reply is intentionally excluded so that
    persona details, role-play, suggestions, and hallucinations
    cannot become personal memories about Sonu.
    """

    user_message = str(user_message).strip()

    if not user_message:
        return {
            "results": [],
        }

    messages = [
        {
            "role": "user",
            "content": user_message,
        }
    ]

    return memory.add(
        messages,
        user_id=user_id,
    )

def search_personal_memories(
    question,
    user_id=MEM0_USER_ID,
    limit=5,
):
    """
    Search for long-term memories relevant to the question.
    """

    question = str(question).strip()

    if not question:
        return []

    result = memory.search(
        query=question,
        filters={
            "user_id": user_id,
        },
        top_k=limit,
    )

    if isinstance(result, dict):
        return result.get("results", [])

    return result or []


def get_all_personal_memories(
    user_id=MEM0_USER_ID,
):
    """
    Return all long-term memories stored for one user.
    """

    result = memory.get_all(
        filters={
            "user_id": user_id,
        }
    )

    if isinstance(result, dict):
        return result.get("results", [])

    return result or []


def format_personal_memories(memories):
    """
    Format retrieved memories for insertion into Misa's prompt.
    """

    facts = []

    for item in memories:
        if not isinstance(item, dict):
            continue

        fact = str(
            item.get("memory", "")
        ).strip()

        if fact:
            facts.append(f"- {fact}")

    return "\n".join(facts)