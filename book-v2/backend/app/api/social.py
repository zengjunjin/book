from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.schemas.social import (
    FollowResponse, UserSummary, FollowerListResponse,
)
from app.models import User
from app.models.social import Follow, Review
from app.api.deps import get_current_user

router = APIRouter()


@router.post("/{user_id}/follow", response_model=FollowResponse)
def follow_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """关注/取消关注用户"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    existing = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first()
    
    if existing:
        # 取消关注
        db.delete(existing)
        db.commit()
        is_following = False
    else:
        # 关注
        follow = Follow(
            follower_id=current_user.id,
            following_id=user_id
        )
        db.add(follow)
        db.commit()
        is_following = True
    
    # 获取更新后的关注数和粉丝数
    following_count = db.query(Follow).filter(Follow.follower_id == current_user.id).count()
    followers_count = db.query(Follow).filter(Follow.following_id == current_user.id).count()
    
    return FollowResponse(
        success=True,
        following_count=following_count,
        followers_count=followers_count
    )


@router.get("/{user_id}/followers", response_model=FollowerListResponse)
def get_followers(
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db)
):
    """获取用户的粉丝列表"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    query = db.query(Follow).filter(Follow.following_id == user_id)
    total = query.count()
    
    follows = query.offset((page - 1) * per_page).limit(per_page).all()
    
    users = []
    for f in follows:
        follower = db.query(User).filter(User.id == f.follower_id).first()
        if follower:
            users.append(UserSummary(
                id=follower.id,
                username=follower.username,
                avatar_url=follower.avatar_url
            ))
    
    return FollowerListResponse(
        users=users,
        total=total,
        page=page,
        pages=(total + per_page - 1) // per_page
    )


@router.get("/{user_id}/following", response_model=FollowerListResponse)
def get_following(
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db)
):
    """获取用户关注的列表"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    query = db.query(Follow).filter(Follow.follower_id == user_id)
    total = query.count()
    
    follows = query.offset((page - 1) * per_page).limit(per_page).all()
    
    users = []
    for f in follows:
        following = db.query(User).filter(User.id == f.following_id).first()
        if following:
            users.append(UserSummary(
                id=following.id,
                username=following.username,
                avatar_url=following.avatar_url
            ))
    
    return FollowerListResponse(
        users=users,
        total=total,
        page=page,
        pages=(total + per_page - 1) // per_page
    )


@router.get("/{user_id}/stats")
def get_user_social_stats(
    user_id: int,
    db: Session = Depends(get_db)
):
    """获取用户的社交统计数据"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    followers_count = db.query(Follow).filter(Follow.following_id == user_id).count()
    following_count = db.query(Follow).filter(Follow.follower_id == user_id).count()
    reviews_count = db.query(Review).filter(Review.user_id == user_id).count()
    
    return {
        "user_id": user_id,
        "followers_count": followers_count,
        "following_count": following_count,
        "reviews_count": reviews_count
    }


@router.get("/{user_id}/feed")
def get_user_feed(
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db)
):
    """获取关注用户的动态（最近评分和书评）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 获取关注列表
    following_ids = db.query(Follow.following_id).filter(Follow.follower_id == user_id).all()
    following_ids = [f[0] for f in following_ids]
    
    if not following_ids:
        return {
            "feed": [],
            "total": 0,
            "page": page,
            "pages": 0
        }
    
    from app.models import Rating
    from app.models.social import Review
    
    # 获取最近评分
    ratings_query = db.query(Rating).filter(Rating.user_id.in_(following_ids))
    ratings_count = ratings_query.count()
    ratings = ratings_query.order_by(desc(Rating.created_at)).offset((page - 1) * per_page).limit(per_page).all()
    
    # 获取最近书评
    reviews_query = db.query(Review).filter(Review.user_id.in_(following_ids))
    reviews_count = reviews_query.count()
    reviews = reviews_query.order_by(desc(Review.created_at)).offset((page - 1) * per_page).limit(per_page).all()
    
    # 合并并排序
    feed_items = []
    for r in ratings:
        user_obj = db.query(User).filter(User.id == r.user_id).first()
        from app.models import Book
        book = db.query(Book).filter(Book.id == r.book_id).first()
        feed_items.append({
            "type": "rating",
            "id": r.id,
            "user_id": r.user_id,
            "book_id": r.book_id,
            "rating": r.rating,
            "created_at": r.created_at,
            "user": {
                "id": user_obj.id,
                "username": user_obj.username,
                "avatar_url": user_obj.avatar_url
            } if user_obj else None,
            "book": {
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "image_url": book.image_url
            } if book else None
        })
    
    for r in reviews:
        user_obj = db.query(User).filter(User.id == r.user_id).first()
        from app.models import Book
        book = db.query(Book).filter(Book.id == r.book_id).first()
        feed_items.append({
            "type": "review",
            "id": r.id,
            "user_id": r.user_id,
            "book_id": r.book_id,
            "content": r.content,
            "review_rating": r.rating,
            "likes": r.likes,
            "created_at": r.created_at,
            "user": {
                "id": user_obj.id,
                "username": user_obj.username,
                "avatar_url": user_obj.avatar_url
            } if user_obj else None,
            "book": {
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "image_url": book.image_url
            } if book else None
        })
    
    # 按时间排序
    feed_items.sort(key=lambda x: x["created_at"], reverse=True)
    
    total = ratings_count + reviews_count
    
    return {
        "feed": feed_items[:per_page],
        "total": total,
        "page": page,
        "pages": (total + per_page - 1) // per_page if total > 0 else 0
    }


@router.get("/me/stats")
def get_my_social_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的社交统计数据"""
    followers_count = db.query(Follow).filter(Follow.following_id == current_user.id).count()
    following_count = db.query(Follow).filter(Follow.follower_id == current_user.id).count()
    reviews_count = db.query(Review).filter(Review.user_id == current_user.id).count()
    
    return {
        "user_id": current_user.id,
        "followers_count": followers_count,
        "following_count": following_count,
        "reviews_count": reviews_count
    }
