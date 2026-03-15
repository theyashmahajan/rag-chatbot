from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from docx import Document as DocxDocument
from PIL import Image
from pypdf import PdfReader
from pytesseract import image_to_string
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from worker.celery_app import celery_app
from worker.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def _split_chunks(text: str, size: int = 700, overlap: int = 120) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + size, len(normalized))
        chunks.append(normalized[start:end])
        if end == len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


def _extract_text(file_path: str, mime_type: str) -> str:
    path = Path(file_path)
    if mime_type in {"text/plain", "text/markdown"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if mime_type == "application/pdf":
        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = DocxDocument(file_path)
        return "\n".join(para.text for para in doc.paragraphs)

    if mime_type in {"image/png", "image/jpeg"}:
        return image_to_string(Image.open(file_path))

    return ""


def _embed_text(text: str) -> list[float]:
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


def _ensure_collection(qdrant: QdrantClient, vector_size: int) -> None:
    try:
        qdrant.get_collection(settings.qdrant_collection)
    except Exception:  # noqa: BLE001
        qdrant.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
        )


def _upsert_vectors(doc: Document, chunks: list[str]) -> None:
    qdrant = QdrantClient(url=settings.qdrant_url, timeout=30.0)
    embeddings: list[list[float]] = [_embed_text(chunk) for chunk in chunks]
    if not embeddings:
        return
    _ensure_collection(qdrant, len(embeddings[0]))

    qdrant.delete(
        collection_name=settings.qdrant_collection,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="document_id", match=qmodels.MatchValue(value=doc.id))]
            )
        ),
    )

    points: list[qmodels.PointStruct] = []
    for idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        payload: dict[str, Any] = {
            "document_id": doc.id,
            "chat_id": doc.chat_id,
            "user_id": doc.user_id,
            "file_name": doc.file_name,
            "chunk_index": idx,
            "text": chunk,
        }
        points.append(
            qmodels.PointStruct(
                id=f"{doc.id}:{idx}",
                vector=vector,
                payload=payload,
            )
        )
    qdrant.upsert(collection_name=settings.qdrant_collection, points=points)


@celery_app.task(name="ingestion.process_document")
def process_document(document_id: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        doc = db.scalar(select(Document).where(Document.id == document_id))
        if not doc:
            return {"document_id": document_id, "status": "not_found"}

        doc.status = "processing"
        db.commit()

        text = _extract_text(doc.storage_path, doc.mime_type)
        chunks = _split_chunks(text)
        if not chunks:
            doc.status = "failed"
            db.commit()
            return {"document_id": document_id, "status": "failed"}

        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        for idx, chunk in enumerate(chunks):
            db.add(DocumentChunk(document_id=document_id, chunk_index=idx, text=chunk))
        db.flush()

        _upsert_vectors(doc=doc, chunks=chunks)

        doc.status = "indexed"
        db.commit()
        return {"document_id": document_id, "status": "indexed"}
    except Exception:
        failed_doc = db.scalar(select(Document).where(Document.id == document_id))
        if failed_doc:
            failed_doc.status = "failed"
            db.commit()
        return {"document_id": document_id, "status": "failed"}
    finally:
        db.close()

