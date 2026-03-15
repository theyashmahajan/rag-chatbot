import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chat import Chat
from app.models.message import Message
from app.models.user import User
from app.schemas.message import ChatResponse, CitationOut, MessageCreate, MessageOut
from app.services.deps import get_current_user
from app.services.rag import generate_assistant_answer, prepare_streaming_answer
from app.services.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/chats/{chat_id}/messages", tags=["messages"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def create_message(
    chat_id: str,
    payload: MessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    enforce_rate_limit(request, scope="chat_message", limit=40, window_seconds=60)
    chat = db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    user_message = Message(chat_id=chat_id, role="user", content=payload.content)
    db.add(user_message)
    db.flush()

    assistant_content, citations = generate_assistant_answer(
        db=db, user_id=user.id, chat_id=chat_id, prompt=payload.content
    )
    assistant_message = Message(chat_id=chat_id, role="assistant", content=assistant_content)
    db.add(assistant_message)
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    return ChatResponse(
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
        citations=[CitationOut.model_validate(citation) for citation in citations],
    )


@router.post("/stream")
def create_message_stream(
    chat_id: str,
    payload: MessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    enforce_rate_limit(request, scope="chat_message", limit=40, window_seconds=60)
    chat = db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    user_message = Message(chat_id=chat_id, role="user", content=payload.content)
    db.add(user_message)
    db.commit()

    stream_iter, citations = prepare_streaming_answer(
        db=db,
        user_id=user.id,
        chat_id=chat_id,
        prompt=payload.content,
    )

    def event_stream():
        assistant_parts: list[str] = []
        try:
            for token in stream_iter:
                assistant_parts.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            assistant_text = "".join(assistant_parts)
            if assistant_text:
                db.add(Message(chat_id=chat_id, role="assistant", content=assistant_text))
                db.commit()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("", response_model=list[MessageOut])
def list_messages(chat_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Message]:
    chat = db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return list(db.scalars(select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc())))
