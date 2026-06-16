from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class ReviewCreate(BaseModel):
    book_id: int
    content: str = Field(..., min_length=1)
    rating: float = Field(..., ge=1, le=5)


class ReviewUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1)
    rating: Optional[float] = Field(None, ge=1, le=5)


class ReviewResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    content: str
    rating: float
    likes: int
    dislikes: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReviewWithBook(BaseModel):
    id: int
    user_id: int
    book_id: int
    content: str
    rating: float
    likes: int
    dislikes: int
    created_at: datetime
    book: Optional[dict] = None
    user: Optional[dict] = None

    class Config:
        from_attributes = True


class ReviewListResponse(BaseModel):
    reviews: List[ReviewWithBook]
    total: int
    page: int
    pages: int


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1)


class CommentResponse(BaseModel):
    id: int
    user_id: int
    review_id: int
    content: str
    created_at: datetime
    user: Optional[dict] = None

    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    comments: List[CommentResponse]
    total: int
    page: int
    pages: int


class LikeRequest(BaseModel):
    is_like: bool = True  # True=点赞, False=踩


class LikeResponse(BaseModel):
    success: bool
    likes: int
    dislikes: int


class FollowResponse(BaseModel):
    success: bool
    following_count: int
    followers_count: int


class UserSummary(BaseModel):
    id: int
    username: str
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class FollowerListResponse(BaseModel):
    users: List[UserSummary]
    total: int
    page: int
    pages: int


class DiscussionCreate(BaseModel):
    book_id: int
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class DiscussionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)


class DiscussionResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    title: str
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    user: Optional[dict] = None
    reply_count: int = 0

    class Config:
        from_attributes = True


class DiscussionListResponse(BaseModel):
    discussions: List[DiscussionResponse]
    total: int
    page: int
    pages: int


class DiscussionReplyCreate(BaseModel):
    content: str = Field(..., min_length=1)


class DiscussionReplyResponse(BaseModel):
    id: int
    user_id: int
    discussion_id: int
    content: str
    created_at: datetime
    user: Optional[dict] = None

    class Config:
        from_attributes = True


class DiscussionReplyListResponse(BaseModel):
    replies: List[DiscussionReplyResponse]
    total: int
    page: int
    pages: int
