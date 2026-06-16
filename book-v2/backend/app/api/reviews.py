from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_
from typing import Optional
from app.database import get_db
from app.schemas.social import (
    ReviewCreate, ReviewUpdate, ReviewResponse, ReviewWithBook, ReviewListResponse,
    CommentCreate, CommentResponse, CommentListResponse,
    LikeRequest, LikeResponse,
)
from app.models import User, Book
from app.models.social import Review, Comment, ReviewLike
from app.api.deps import get_current_user

router = APIRouter()


def _build_review_with_details(review: Review, db: Session) -> dict:
    """构建包含用户和书籍信息的书评对象"""
    user = db.query(User).filter(User.id == review.user_id).first()
    book = db.query(Book).filter(Book.id == review.book_id).first()
    
    return {
        "id": review.id,
        "user_id": review.user_id,
        "book_id": review.book_id,
        "content": review.content,
        "rating": review.rating,
        "likes": review.likes,
        "dislikes": review.dislikes,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
        "user": {
            "id": user.id,
            "username": user.username,
            "avatar_url": user.avatar_url
        } if user else None,
        "book": {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "image_url": book.image_url
        } if book else None
    }


@router.get("", response_model=ReviewListResponse)
def get_reviews(
    book_id: Optional[int] = None,
    user_id: Optional[int] = None,
    sort: str = Query("latest", regex="^(latest|hot|helpful)$"),
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db)
):
    """
    获取书评列表
    - sort: latest(最新), hot(最热), helpful(最有帮助)
    """
    query = db.query(Review)
    
    if book_id:
        query = query.filter(Review.book_id == book_id)
    if user_id:
        query = query.filter(Review.user_id == user_id)
    
    # 排序
    if sort == "latest":
        query = query.order_by(desc(Review.created_at))
    elif sort == "hot":
        query = query.order_by(desc(Review.likes - Review.dislikes))
    elif sort == "helpful":
        query = query.order_by(desc(Review.likes))
    
    total = query.count()
    reviews = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return ReviewListResponse(
        reviews=[_build_review_with_details(r, db) for r in reviews],
        total=total,
        page=page,
        pages=(total + per_page - 1) // per_page
    )


@router.post("", response_model=ReviewWithBook)
def create_review(
    review_data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """发布书评"""
    # 检查书籍是否存在
    book = db.query(Book).filter(Book.id == review_data.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    review = Review(
        user_id=current_user.id,
        book_id=review_data.book_id,
        content=review_data.content,
        rating=review_data.rating
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    
    return _build_review_with_details(review, db)


@router.get("/{review_id}", response_model=ReviewWithBook)
def get_review(
    review_id: int,
    db: Session = Depends(get_db)
):
    """获取书评详情"""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return _build_review_with_details(review, db)


@router.put("/{review_id}", response_model=ReviewWithBook)
def update_review(
    review_id: int,
    review_data: ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新书评"""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    if review.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this review")
    
    if review_data.content is not None:
        review.content = review_data.content
    if review_data.rating is not None:
        review.rating = review_data.rating
    
    db.commit()
    db.refresh(review)
    
    return _build_review_with_details(review, db)


@router.delete("/{review_id}")
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除书评"""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    if review.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this review")
    
    db.delete(review)
    db.commit()
    
    return {"success": True}


@router.post("/{review_id}/like", response_model=LikeResponse)
def like_review(
    review_id: int,
    like_data: LikeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """点赞/踩书评"""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    # 检查是否已经点赞/踩过
    existing = db.query(ReviewLike).filter(
        ReviewLike.user_id == current_user.id,
        ReviewLike.review_id == review_id
    ).first()
    
    is_like = 1 if like_data.is_like else 0
    
    if existing:
        if existing.is_like == is_like:
            # 取消点赞/踩
            if is_like == 1:
                review.likes = max(0, review.likes - 1)
            else:
                review.dislikes = max(0, review.dislikes - 1)
            db.delete(existing)
        else:
            # 切换点赞/踩
            if is_like == 1:
                review.likes += 1
                review.dislikes = max(0, review.dislikes - 1)
            else:
                review.dislikes += 1
                review.likes = max(0, review.likes - 1)
            existing.is_like = is_like
    else:
        # 新增点赞/踩
        like_record = ReviewLike(
            user_id=current_user.id,
            review_id=review_id,
            is_like=is_like
        )
        db.add(like_record)
        if is_like == 1:
            review.likes += 1
        else:
            review.dislikes += 1
    
    db.commit()
    
    return LikeResponse(success=True, likes=review.likes, dislikes=review.dislikes)


@router.get("/{review_id}/comments", response_model=CommentListResponse)
def get_review_comments(
    review_id: int,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db)
):
    """获取书评的评论列表"""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    query = db.query(Comment).filter(Comment.review_id == review_id).order_by(Comment.created_at)
    total = query.count()
    comments = query.offset((page - 1) * per_page).limit(per_page).all()
    
    result = []
    for c in comments:
        user = db.query(User).filter(User.id == c.user_id).first()
        result.append({
            "id": c.id,
            "user_id": c.user_id,
            "review_id": c.review_id,
            "content": c.content,
            "created_at": c.created_at,
            "user": {
                "id": user.id,
                "username": user.username,
                "avatar_url": user.avatar_url
            } if user else None
        })
    
    return CommentListResponse(
        comments=result,
        total=total,
        page=page,
        pages=(total + per_page - 1) // per_page
    )


@router.post("/{review_id}/comments", response_model=CommentResponse)
def create_comment(
    review_id: int,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """评论书评"""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    comment = Comment(
        user_id=current_user.id,
        review_id=review_id,
        content=comment_data.content
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    return {
        "id": comment.id,
        "user_id": comment.user_id,
        "review_id": comment.review_id,
        "content": comment.content,
        "created_at": comment.created_at,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "avatar_url": current_user.avatar_url
        }
    }


@router.delete("/{review_id}/comments/{comment_id}")
def delete_comment(
    review_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除评论"""
    comment = db.query(Comment).filter(
        Comment.id == comment_id,
        Comment.review_id == review_id
    ).first()
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")
    
    db.delete(comment)
    db.commit()
    
    return {"success": True}
