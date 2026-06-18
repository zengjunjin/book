from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.rating import RatingCreate, RatingResponse
from app.models import Rating, Book
from app.api.deps import get_current_user
from app.models import User
from typing import Optional

router = APIRouter()


class RatingRequest(BaseModel):
    book_id: int
    user_id: Optional[int] = None
    rating: int


def update_book_stats(book_id: int):
    """Placeholder for async task - will be implemented in Phase 4"""
    pass


@router.post("/", response_model=RatingResponse)
def create_or_update_rating(
    rating_data: RatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Rating request received: book_id={rating_data.book_id}, rating={rating_data.rating}, type={type(rating_data.rating)}")
    
    book = db.query(Book).filter(Book.id == rating_data.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if rating_data.rating < 1 or rating_data.rating > 10:
        raise HTTPException(status_code=422, detail="评分必须在 1 到 10 之间")

    # 四舍五入到 0.5 的倍数（如 7.3 -> 7.5, 7.7 -> 8.0）
    rounded_rating = round(rating_data.rating * 2) / 2

    existing = db.query(Rating).filter(
        Rating.user_id == current_user.id,
        Rating.book_id == rating_data.book_id
    ).first()

    if existing:
        existing.rating = rounded_rating
        db.commit()
        db.refresh(existing)
    else:
        rating = Rating(
            user_id=current_user.id,
            book_id=rating_data.book_id,
            rating=rounded_rating
        )
        db.add(rating)
        db.commit()
        db.refresh(rating)
        existing = rating

    try:
        update_book_stats(rating_data.book_id)
    except Exception:
        pass

    return existing


@router.get("/user")
def get_user_ratings_by_query(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前登录用户的评分列表（user_id 从 token 自动提取，无需前端传递）"""
    user_id = current_user.id
    query = db.query(Rating).filter(Rating.user_id == user_id).order_by(Rating.created_at.desc())
    total = query.count()
    ratings = query.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for r in ratings:
        book = db.query(Book).filter(Book.id == r.book_id).first()
        result.append({
            **RatingResponse.model_validate(r).model_dump(),
            "book": {
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "image_url": book.image_url
            } if book else None
        })

    return {
        "ratings": result,
        "total": total,
        "page": page,
        "pages": (total + per_page - 1) // per_page
    }


@router.get("/user/{user_id}")
def get_user_ratings(
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """基于路径参数获取用户评分列表（兼容旧格式）- 仅可查看自己的评分"""
    # 安全修复：用户只能查看自己的评分
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限查看他人评分记录")

    query = db.query(Rating).filter(Rating.user_id == user_id).order_by(Rating.created_at.desc())
    total = query.count()
    ratings = query.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for r in ratings:
        book = db.query(Book).filter(Book.id == r.book_id).first()
        result.append({
            **RatingResponse.model_validate(r).model_dump(),
            "book": {
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "image_url": book.image_url
            } if book else None
        })

    return {
        "ratings": result,
        "total": total,
        "page": page,
        "pages": (total + per_page - 1) // per_page
    }
