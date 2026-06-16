from pydantic import BaseModel
from typing import List
from datetime import datetime


class UserTagCreate(BaseModel):
    tag_name: str
    weight: float = 1.0


class UserTagResponse(BaseModel):
    id: int
    user_id: int
    tag_name: str
    weight: float
    created_at: datetime

    class Config:
        from_attributes = True


class UserTagListResponse(BaseModel):
    tags: List[UserTagResponse]
    total: int
