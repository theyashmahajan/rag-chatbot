from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document


def _embed_text(text: str) -> list[float]:
    settings = get_settings()
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"{settings.ollama_url}/api/embed",
            json={"model": settings.embedding_model, "input": text},
        )
        if response.is_success:
            payload = response.json()
            if isinstance(payload.get("embeddings"), list) and payload["embeddings"]:
                first = payload["embeddings"][0]
                if isinstance(first, list):
                    return [float(v) for v in first]
                return [float(v) for v in payload["embeddings"]]

        fallback = client.post(
            f"{settings.ollama_url}/api/embeddings",
            json={"model": settings.embedding_model, "prompt": text},
        )
        fallback.raise_for_status()
        fb_payload = fallback.json()
        vector = fb_payload.get("embedding", [])
        return [float(v) for v in vector]


def retrieve_contexts(user_id: str, chat_id: str, prompt: str, top_k: int = 5) -> list[dict[str, Any]]:
    settings = get_settings()
    vector = _embed_text(prompt)
    qdrant = QdrantClient(url=settings.qdrant_url, timeout=30.0)
    query_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=user_id)),
            qmodels.FieldCondition(key="chat_id", match=qmodels.MatchValue(value=chat_id)),
        ]
    )
    points = qdrant.search(
        collection_name=settings.qdrant_collection,
        query_vector=vector,
        query_filter=query_filter,
        with_payload=True,
        limit=top_k,
    )
    results: list[dict[str, Any]] = []
    for point in points:
        payload = point.payload or {}
        results.append(
            {
                "text": str(payload.get("text", "")),
                "file_name": str(payload.get("file_name", "unknown")),
                "chunk_index": int(payload.get("chunk_index", 0)),
                "score": float(point.score or 0.0),
            }
        )
    return results


def _build_llm_prompt(question: str, contexts: list[dict[str, Any]]) -> str:
    context_block = "\n\n".join(
        [
            (
                f"[Source {idx + 1}] file={ctx['file_name']} chunk={ctx['chunk_index']} "
                f"score={ctx['score']:.4f}\n{ctx['text']}"
            )
            for idx, ctx in enumerate(contexts)
        ]
    )
    return (
        "You are a document-grounded assistant. Use only the provided context. "
        "If information is missing, say so clearly.\n\n"
        f"User Question:\n{question}\n\n"
        f"Context:\n{context_block}\n\n"
        "Answer with concise, factual points."
    )


def _generate_with_ollama(prompt: str) -> str:
    settings = get_settings()
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{settings.ollama_url}/api/generate",
            json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("response", "")).strip()


def stream_generate_with_ollama(prompt: str) -> Iterator[str]:
    settings = get_settings()
    with httpx.Client(timeout=300.0) as client:
        with client.stream(
            "POST",
            f"{settings.ollama_url}/api/generate",
            json={"model": settings.ollama_model, "prompt": prompt, "stream": True},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                payload = json.loads(line)
                token = str(payload.get("response", ""))
                if token:
                    yield token


def generate_assistant_answer(db: Session, user_id: str, chat_id: str, prompt: str) -> tuple[str, list[dict[str, Any]]]:
    doc_count = db.scalar(
        select(func.count(Document.id)).where(Document.user_id == user_id, Document.chat_id == chat_id)
    )
    if not doc_count:
        return ("No documents found in this chat yet. Upload documents first.", [])

    try:
        contexts = retrieve_contexts(user_id=user_id, chat_id=chat_id, prompt=prompt, top_k=5)
    except Exception as exc:  # noqa: BLE001
        return (f"Retrieval failed: {exc}", [])
    if not contexts:
        return ("No relevant indexed context found. Try re-uploading documents or asking a specific question.", [])

    llm_prompt = _build_llm_prompt(prompt, contexts)
    try:
        answer = _generate_with_ollama(llm_prompt)
    except Exception as exc:  # noqa: BLE001
        answer = f"Ollama generation failed: {exc}"
    return (answer, contexts)


def prepare_streaming_answer(
    db: Session, user_id: str, chat_id: str, prompt: str
) -> tuple[Iterator[str], list[dict[str, Any]]]:
    doc_count = db.scalar(
        select(func.count(Document.id)).where(Document.user_id == user_id, Document.chat_id == chat_id)
    )
    if not doc_count:
        return (iter(["No documents found in this chat yet. Upload documents first."]), [])

    contexts = retrieve_contexts(user_id=user_id, chat_id=chat_id, prompt=prompt, top_k=5)
    if not contexts:
        return (iter(["No relevant indexed context found. Try re-uploading documents or asking a specific question."]), [])

    llm_prompt = _build_llm_prompt(prompt, contexts)
    return (stream_generate_with_ollama(llm_prompt), contexts)

