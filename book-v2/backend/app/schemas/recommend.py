from pydantic import BaseModel
from typing import List, Optional


class RecommendationItem(BaseModel):
    book_id: int
    title: str
    author: Optional[str] = None
    image_url: Optional[str] = None
    score: float
    reason: Optional[str] = None
    source: str  # 'cf', 'svd', 'hybrid', 'cold_start', 'explore'


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: List[RecommendationItem]
    total: int
    source: str
    explore_count: int = 0
    diversity_score: float = 0.0
