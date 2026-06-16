from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.rating import RatingCreate, RatingResponse
from app.models import Rating, Book
from app.api.deps import get_current_user
from app.models import User

router = APIRouter()


def update_book_stats(book_id: int):
    """Placeholder for async task - will be implemented in Phase 4"""
    pass


@router.post("/", response_model=RatingResponse)
def create_or_update_rating(
    rating_data: RatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if book exists
    book = db.query(Book).filter(Book.id == rating_data.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Check if rating exists
    existing = db.query(Rating).filter(
        Rating.user_id == current_user.id,
        Rating.book_id == rating_data.book_id
    ).first()

    if existing:
        existing.rating = rating_data.rating
        db.commit()
        db.refresh(existing)
    else:
        rating = Rating(
            user_id=current_user.id,
            book_id=rating_data.book_id,
            rating=rating_data.rating
        )
        db.add(rating)
        db.commit()
        db.refresh(rating)
        existing = rating

    # Update book stats asynchronously (placeholder)
    try:
        update_book_stats(rating_data.book_id)
    except Exception:
        pass  # Ignore if celery not available

    return existing


@router.get("/user/{user_id}")
def get_user_ratings(
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db)
):
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
