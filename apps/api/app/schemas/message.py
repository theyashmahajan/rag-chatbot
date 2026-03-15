from datetime import datetime

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CitationOut(BaseModel):
    file_name: str
    chunk_index: int
    score: float


class ChatResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
    citations: list[CitationOut] = []
