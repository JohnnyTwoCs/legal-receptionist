"""
Pinecone RAG pipeline — chunk, embed, upsert, query.

Uses OpenAI text-embedding-3-small for embeddings and Pinecone for vector storage.
Retrieves top-k relevant chunks per user message for Claude context injection.
"""

import os
import re
import hashlib
from pathlib import Path

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

from app.config import (
    PINECONE_INDEX_NAME,
    PINECONE_NAMESPACE,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    RAG_TOP_K,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)


def _openai_client():
    return OpenAI(api_key=os.environ.get("OPEN_AI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", ""))


def _pinecone_client():
    return Pinecone(api_key=os.environ.get("PINECONE_API_KEY", ""))


def ensure_index():
    """Create the Pinecone index if it doesn't exist."""
    pc = _pinecone_client()
    existing = [idx.name for idx in pc.list_indexes()]
    if PINECONE_INDEX_NAME not in existing:
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIMENSIONS,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    return pc.Index(PINECONE_INDEX_NAME)


def get_index():
    """Get a reference to the Pinecone index."""
    pc = _pinecone_client()
    return pc.Index(PINECONE_INDEX_NAME)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks by paragraph boundaries."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            # Start new chunk; include overlap from end of previous
            if chunks and overlap > 0:
                prev = chunks[-1]
                overlap_text = prev[-overlap:] if len(prev) > overlap else prev
                current = f"{overlap_text}\n\n{para}"
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


def chunk_markdown(text, source_file=""):
    """Split markdown by headers, then chunk each section."""
    sections = re.split(r"(?=^#{1,3}\s)", text, flags=re.MULTILINE)
    chunks = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        header_match = re.match(r"^(#{1,3})\s+(.+)", section)
        header = header_match.group(2).strip() if header_match else ""

        section_chunks = chunk_text(section)
        for i, chunk in enumerate(section_chunks):
            chunk_id = hashlib.md5(
                f"{source_file}:{header}:{i}".encode()
            ).hexdigest()[:12]
            chunks.append({
                "id": f"{chunk_id}",
                "text": chunk,
                "metadata": {
                    "source": source_file,
                    "section": header,
                    "chunk_index": i,
                },
            })

    return chunks


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_texts(texts):
    """Embed a list of texts using OpenAI text-embedding-3-small."""
    client = _openai_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def embed_single(text):
    """Embed a single text string."""
    return embed_texts([text])[0]


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def upsert_chunks(chunks, namespace=PINECONE_NAMESPACE):
    """Embed and upsert a list of chunk dicts into Pinecone.

    Each chunk: {"id": str, "text": str, "metadata": dict}
    """
    if not chunks:
        return 0

    index = ensure_index()
    texts = [c["text"] for c in chunks]

    # Batch embeddings (OpenAI max 2048 per call; our docs are small)
    batch_size = 100
    total_upserted = 0

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        batch_texts = texts[i : i + batch_size]
        embeddings = embed_texts(batch_texts)

        vectors = []
        for chunk, embedding in zip(batch, embeddings):
            meta = chunk.get("metadata", {})
            meta["text"] = chunk["text"][:1000]  # Store truncated text in metadata
            vectors.append({
                "id": chunk["id"],
                "values": embedding,
                "metadata": meta,
            })

        index.upsert(vectors=vectors, namespace=namespace)
        total_upserted += len(vectors)

    return total_upserted


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def query(text, top_k=RAG_TOP_K, namespace=PINECONE_NAMESPACE):
    """Query Pinecone for the most relevant chunks to a user message.

    Returns list of dicts: [{"text": str, "score": float, "source": str, "section": str}]
    """
    embedding = embed_single(text)
    index = get_index()

    results = index.query(
        vector=embedding,
        top_k=top_k,
        namespace=namespace,
        include_metadata=True,
    )

    hits = []
    for match in results.get("matches", []):
        meta = match.get("metadata", {})
        hits.append({
            "text": meta.get("text", ""),
            "score": match.get("score", 0.0),
            "source": meta.get("source", ""),
            "section": meta.get("section", ""),
        })

    return hits


def build_rag_context(user_message, top_k=RAG_TOP_K):
    """Query RAG and format results as context for the system prompt."""
    hits = query(user_message, top_k=top_k)

    if not hits:
        return ""

    context_parts = []
    for i, hit in enumerate(hits, 1):
        source_label = f"[{hit['source']}]" if hit['source'] else ""
        section_label = f" > {hit['section']}" if hit['section'] else ""
        context_parts.append(
            f"--- Reference {i} {source_label}{section_label} (relevance: {hit['score']:.2f}) ---\n"
            f"{hit['text']}"
        )

    return "\n\n".join(context_parts)


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

def ingest_directory(directory, namespace=PINECONE_NAMESPACE):
    """Index all markdown files in a directory into Pinecone."""
    dir_path = Path(directory)
    all_chunks = []

    for md_file in sorted(dir_path.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        chunks = chunk_markdown(text, source_file=md_file.name)
        all_chunks.extend(chunks)
        print(f"  Chunked {md_file.name}: {len(chunks)} chunks")

    if all_chunks:
        count = upsert_chunks(all_chunks, namespace=namespace)
        print(f"  Upserted {count} total chunks to namespace '{namespace}'")

    return len(all_chunks)


def delete_namespace(namespace=PINECONE_NAMESPACE):
    """Delete all vectors in a namespace."""
    index = get_index()
    try:
        index.delete(delete_all=True, namespace=namespace)
        print(f"  Deleted all vectors in namespace '{namespace}'")
    except Exception:
        print(f"  Namespace '{namespace}' is empty or doesn't exist, skipping delete")
