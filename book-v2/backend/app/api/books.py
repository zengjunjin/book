from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional
from app.database import get_db
from app.models import Book, Rating
from app.schemas.book import BookResponse, BookListResponse, BookDetailResponse
from app.api.deps import get_current_user
from app.models import User, Interaction
from collections import Counter

router = APIRouter()


@router.get("/", response_model=BookListResponse)
def get_books(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Book)

    if search:
        query = query.filter(
            Book.title.ilike(f"%{search}%") | Book.author.ilike(f"%{search}%")
        )

    if category:
        query = query.filter(Book.category == category)

    total = query.count()
    books = query.offset((page - 1) * per_page).limit(per_page).all()

    return BookListResponse(
        books=[BookResponse.model_validate(b) for b in books],
        total=total,
        page=page,
        pages=(total + per_page - 1) // per_page
    )


@router.get("/{book_id}", response_model=BookDetailResponse)
def get_book(
    book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Get community rating stats
    ratings = db.query(Rating).filter(Rating.book_id == book_id).all()
    rating_count = len(ratings)
    avg_rating = round(sum(r.rating for r in ratings) / rating_count, 1) if rating_count > 0 else None

    # Rating distribution
    distribution = {str(i): 0 for i in range(1, 11)}
    for r in ratings:
        key = str(r.rating)
        if key in distribution:
            distribution[key] += 1

    # Most common rating
    most_common = Counter(r.rating for r in ratings).most_common(1)
    most_common_rating = most_common[0][0] if most_common else None

    # User's rating
    user_rating = db.query(Rating).filter(
        Rating.user_id == current_user.id,
        Rating.book_id == book_id
    ).first()

    # User's interactions
    interactions = db.query(Interaction).filter(
        Interaction.user_id == current_user.id,
        Interaction.book_id == book_id
    ).all()
    user_interactions = {i.interaction_type: True for i in interactions}

    return BookDetailResponse(
        **BookResponse.model_validate(book).model_dump(),
        community_rating={
            "avg_rating": avg_rating,
            "rating_count": rating_count,
            "distribution": distribution,
            "most_common_rating": most_common_rating
        },
        user_rating=user_rating.rating if user_rating else None,
        user_interactions=user_interactions
    )


@router.get("/{book_id}/similar")
def get_similar_books(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Find similar by author or category
    conditions = []
    if book.author:
        conditions.append(Book.author == book.author)
    if book.category:
        conditions.append(Book.category == book.category)

    if conditions:
        similar = db.query(Book).filter(
            Book.id != book_id,
            or_(*conditions)
        ).limit(6).all()
    else:
        similar = db.query(Book).filter(Book.id != book_id).limit(6).all()

    return {"similar_books": [BookResponse.model_validate(b) for b in similar]}
