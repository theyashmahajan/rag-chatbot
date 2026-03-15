from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.chat import Chat
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentOut
from app.services.deps import get_current_user
from app.services.tasks import enqueue_document_ingestion

router = APIRouter(prefix="/chats/{chat_id}/documents", tags=["documents"])

ALLOWED_MIME_PREFIXES = (
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "image/png",
    "image/jpeg",
)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    chat_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Document:
    settings = get_settings()
    chat = db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    doc_count = db.scalar(select(func.count(Document.id)).where(Document.chat_id == chat_id))
    if (doc_count or 0) >= settings.max_files_per_chat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {settings.max_files_per_chat} documents allowed per chat",
        )

    if file.content_type not in ALLOWED_MIME_PREFIXES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

    raw = await file.read()
    size_mb = len(raw) / (1024 * 1024)
    if size_mb > settings.max_file_size_mb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size is {settings.max_file_size_mb} MB",
        )

    storage_root = Path(settings.file_storage_path).resolve()
    safe_name = file.filename or "document"
    unique_name = f"{uuid4()}_{safe_name}"
    user_chat_path = storage_root / user.id / chat_id
    user_chat_path.mkdir(parents=True, exist_ok=True)
    file_path = user_chat_path / unique_name
    file_path.write_bytes(raw)

    doc = Document(
        chat_id=chat_id,
        user_id=user.id,
        file_name=safe_name,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(raw),
        storage_path=str(file_path),
        status="uploaded",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    try:
        enqueue_document_ingestion(doc.id)
    except Exception:  # noqa: BLE001
        # Keep upload successful even if worker queue is temporarily unavailable.
        pass
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(chat_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Document]:
    chat = db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return list(
        db.scalars(select(Document).where(Document.chat_id == chat_id, Document.user_id == user.id).order_by(Document.created_at.desc()))
    )
