import os
import re
import sys
import uuid
from pathlib import Path

import requests
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)


# ---------------------------------------------------------
# RAG configuration
# ---------------------------------------------------------

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://ollama:11434",
).rstrip("/")

EMBED_MODEL = os.getenv(
    "RAG_EMBED_MODEL",
    "embeddinggemma",
)

QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "http://qdrant:6333",
)

COLLECTION_NAME = os.getenv(
    "RAG_COLLECTION",
    "misa_knowledge",
)

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
}


# Connect to the local Qdrant container.
qdrant = QdrantClient(
    url=QDRANT_URL,
    timeout=30,
)


# ---------------------------------------------------------
# Document reading
# ---------------------------------------------------------

def read_document(file_path):
    """Read text from a PDF, TXT, or Markdown file."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Document does not exist: {path}"
        )

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Supported document types are PDF, TXT, and MD."
        )

    if extension == ".pdf":
        reader = PdfReader(path)

        text = "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )
    else:
        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    # Remove excessive spaces while preserving readable text.
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        raise ValueError(
            f"No readable text was found in {path.name}."
        )

    return text


# ---------------------------------------------------------
# Text chunking
# ---------------------------------------------------------

def split_text(text, chunk_size=800, overlap=120):
    """
    Split a document into overlapping chunks.

    Overlap helps preserve information that crosses
    the boundary between two chunks.
    """

    if overlap >= chunk_size:
        raise ValueError(
            "Chunk overlap must be smaller than chunk size."
        )

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(
            start + chunk_size,
            text_length,
        )

        # Avoid cutting through the middle of a word.
        if end < text_length:
            last_space = text.rfind(
                " ",
                start,
                end,
            )

            if last_space > start:
                end = last_space

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = max(
            end - overlap,
            start + 1,
        )

    return chunks


# ---------------------------------------------------------
# Ollama embeddings
# ---------------------------------------------------------

def create_embeddings(texts):
    """Convert one or more strings into embedding vectors."""

    if not texts:
        return []

    response = requests.post(
        f"{OLLAMA_URL}/api/embed",
        json={
            "model": EMBED_MODEL,
            "input": texts,
            "truncate": True,

            # Keep the embedding model loaded.
            "keep_alive": -1,
        },
        timeout=(10, 300),
    )

    response.raise_for_status()

    embeddings = response.json().get(
        "embeddings",
        [],
    )

    if len(embeddings) != len(texts):
        raise RuntimeError(
            "Ollama returned an unexpected number "
            "of embeddings."
        )

    return embeddings


# ---------------------------------------------------------
# Qdrant collection
# ---------------------------------------------------------

def ensure_collection(vector_size):
    """Create the Qdrant collection when first needed."""

    if qdrant.collection_exists(COLLECTION_NAME):
        return

    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
    )


def remove_existing_document(source):
    """Remove old chunks before re-indexing a document."""

    if not qdrant.collection_exists(COLLECTION_NAME):
        return

    qdrant.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="source",
                    match=MatchValue(
                        value=source,
                    ),
                )
            ]
        ),
        wait=True,
    )


# ---------------------------------------------------------
# Document ingestion
# ---------------------------------------------------------

def ingest_document(file_path):
    """
    Read, chunk, embed, and store one document.
    """

    path = Path(file_path).resolve()
    text = read_document(path)
    chunks = split_text(text)

    print(
        f"Creating embeddings for "
        f"{len(chunks)} chunks..."
    )

    embeddings = create_embeddings(chunks)

    if not embeddings:
        raise RuntimeError(
            "No embeddings were generated."
        )

    ensure_collection(
        vector_size=len(embeddings[0])
    )

    source = path.name

    # Replacing a document won't create duplicate chunks.
    remove_existing_document(source)

    points = []

    for index, (chunk, vector) in enumerate(
        zip(chunks, embeddings)
    ):
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "source": source,
                    "chunk_index": index,
                    "text": chunk,
                },
            )
        )

    qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True,
    )

    return {
        "source": source,
        "chunks": len(points),
    }


# ---------------------------------------------------------
# Semantic retrieval
# ---------------------------------------------------------

def retrieve_context(
    question,
    limit=4,
    minimum_score=0.30,
):
    """
    Find document chunks related to a question.
    """

    question = question.strip()

    if not question:
        return []

    if not qdrant.collection_exists(COLLECTION_NAME):
        return []

    query_vector = create_embeddings(
        [question]
    )[0]

    result = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        score_threshold=minimum_score,
        with_payload=True,
    )

    matches = []

    for point in result.points:
        payload = point.payload or {}

        matches.append({
            "text": payload.get("text", ""),
            "source": payload.get(
                "source",
                "Unknown source",
            ),
            "chunk_index": payload.get(
                "chunk_index",
                0,
            ),
            "score": point.score,
        })

    return matches


# ---------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------

def main():
    """
    Usage:

    python rag.py ingest documents/example.pdf
    python rag.py search "What does the document say?"
    """

    if len(sys.argv) < 3:
        print(
            "Usage:\n"
            "  python rag.py ingest <document>\n"
            "  python rag.py search <question>"
        )

        raise SystemExit(1)

    command = sys.argv[1].lower()
    value = " ".join(sys.argv[2:])

    if command == "ingest":
        result = ingest_document(value)

        print(
            f"Indexed {result['source']} "
            f"into {result['chunks']} chunks."
        )

        return

    if command == "search":
        matches = retrieve_context(value)

        if not matches:
            print("No relevant knowledge found.")
            return

        for number, match in enumerate(
            matches,
            start=1,
        ):
            print(
                f"\nResult {number}\n"
                f"Source: {match['source']}\n"
                f"Score: {match['score']:.3f}\n"
                f"Text: {match['text']}"
            )

        return

    print(f"Unknown command: {command}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()