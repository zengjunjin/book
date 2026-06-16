from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class RatingCreate(BaseModel):
    book_id: int
    rating: int = Field(..., ge=1, le=10)


class RatingResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    rating: int
    created_at: datetime

    class Config:
        from_attributes = True


class RatingWithBook(RatingResponse):
    book: dict  # simplified book info
