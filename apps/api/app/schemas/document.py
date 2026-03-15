from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    file_name: str
    mime_type: str
    size_bytes: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

