from datetime import datetime

from pydantic import BaseModel, Field


class ChatCreate(BaseModel):
    title: str = Field(default="New Chat", min_length=1, max_length=255)


class ChatOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}

