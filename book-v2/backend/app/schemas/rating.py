from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class RatingCreate(BaseModel):
    book_id: int
    rating: float = Field(..., ge=1, le=10)


class RatingResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    rating: float
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RatingWithBook(RatingResponse):
    book: dict  # simplified book info
