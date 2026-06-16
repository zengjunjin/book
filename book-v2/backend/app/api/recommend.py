from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.recommend import RecommendationResponse, RecommendationItem
from app.models import User
from app.api.deps import get_current_user
from app.services.recommender import get_recommender

router = APIRouter()


def get_cf_recommendations_placeholder(user_id: int, n: int, db: Session):
    """Placeholder CF recommendation"""
    return []


def get_svd_recommendations_placeholder(user_id: int, n: int, db: Session):
    """Placeholder SVD recommendation"""
    return []


def get_hybrid_recommendations_placeholder(user_id: int, n: int, db: Session):
    """Placeholder hybrid recommendation"""
    return [], 0, 0.0


def get_cold_start_recommendations_placeholder(user_id: int, n: int, db: Session):
    """Placeholder cold start recommendation"""
    return []


@router.get("/cf/{user_id}", response_model=RecommendationResponse)
def get_cf_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    recs = get_cf_recommendations_placeholder(user_id, n, db)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="cf"
    )


@router.get("/svd/{user_id}", response_model=RecommendationResponse)
def get_svd_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    recs = get_svd_recommendations_placeholder(user_id, n, db)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="svd"
    )


@router.get("/hybrid/{user_id}", response_model=RecommendationResponse)
def get_hybrid_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    diversity: bool = True,
    db: Session = Depends(get_db)
):
    recs, explore_count, diversity_score = get_hybrid_recommendations_placeholder(user_id, n, db)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="hybrid",
        explore_count=explore_count,
        diversity_score=diversity_score
    )


@router.get("/cold-start/{user_id}", response_model=RecommendationResponse)
def get_cold_start_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    recs = get_cold_start_recommendations_placeholder(user_id, n, db)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="cold_start"
    )


@router.get("/explore/{user_id}", response_model=RecommendationResponse)
def get_explore_recommendations(
    user_id: int,
    n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    recs = []  # Exploration uses random sampling
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="explore"
    )
