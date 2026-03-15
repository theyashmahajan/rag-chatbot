from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chat import Chat
from app.models.user import User
from app.schemas.chat import ChatCreate, ChatOut
from app.services.deps import get_current_user

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
def create_chat(payload: ChatCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Chat:
    chat = Chat(user_id=user.id, title=payload.title)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@router.get("", response_model=list[ChatOut])
def list_chats(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Chat]:
    return list(db.scalars(select(Chat).where(Chat.user_id == user.id).order_by(Chat.updated_at.desc())))


@router.get("/{chat_id}", response_model=ChatOut)
def get_chat(chat_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Chat:
    chat = db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return chat


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(chat_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    chat = db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    db.delete(chat)
    db.commit()
    return None
