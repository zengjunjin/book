from pydantic import BaseModel
from datetime import datetime
from typing import Optional

INTERACTION_TYPES = ["view", "like", "dislike", "want_to_read", "read"]


class InteractionCreate(BaseModel):
    book_id: int
    interaction_type: str


class InteractionResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    interaction_type: str
    created_at: datetime

    class Config:
        from_attributes = True
