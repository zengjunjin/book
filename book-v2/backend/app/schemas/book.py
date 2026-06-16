from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class BookBase(BaseModel):
    title: str
    author: Optional[str] = None
    category: Optional[str] = None


class BookResponse(BookBase):
    id: int
    isbn: str
    year: Optional[int] = None
    publisher: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    avg_rating: float = 0.0
    rating_count: int = 0

    class Config:
        from_attributes = True


class BookListResponse(BaseModel):
    books: List[BookResponse]
    total: int
    page: int
    pages: int


class BookDetailResponse(BookResponse):
    community_rating: dict  # avg_rating, rating_count, distribution, most_common_rating
    user_rating: Optional[int] = None
    user_interactions: dict = {}  # liked, disliked, wanted
