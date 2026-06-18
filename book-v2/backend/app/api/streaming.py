"""
流式推荐 API
参考报告: 实时推荐接口设计
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.streaming_recommender import EventType, UserEvent, get_streaming_recommender
import uuid

router = APIRouter()


@router.post("/events/rating")
def publish_rating_event(
    user_id: int,
    book_id: int,
    rating: int = Query(..., ge=1, le=10),
    db: Session = Depends(get_db)
):
    """发布评分事件"""
    streaming = get_streaming_recommender(get_db)

    event = UserEvent(
        event_id=str(uuid.uuid4()),
        user_id=user_id,
        book_id=book_id,
        event_type=EventType.RATING.value,
        timestamp=time.time(),
        metadata={"rating": rating}
    )

    success = streaming.event_processor.publish_event(event)

    return {
        "status": "success" if success else "queued",
        "event_id": event.event_id,
        "message": "评分事件已记录"
    }


@router.post("/events/view")
def publish_view_event(
    user_id: int,
    book_id: int,
    db: Session = Depends(get_db)
):
    """发布浏览事件"""
    streaming = get_streaming_recommender(get_db)

    event = UserEvent(
        event_id=str(uuid.uuid4()),
        user_id=user_id,
        book_id=book_id,
        event_type=EventType.VIEW.value,
        timestamp=time.time()
    )

    success = streaming.event_processor.publish_event(event)

    return {
        "status": "success" if success else "queued",
        "event_id": event.event_id,
        "message": "浏览事件已记录"
    }


@router.post("/events/like")
def publish_like_event(
    user_id: int,
    book_id: int,
    db: Session = Depends(get_db)
):
    """发布点赞事件"""
    streaming = get_streaming_recommender(get_db)

    event = UserEvent(
        event_id=str(uuid.uuid4()),
        user_id=user_id,
        book_id=book_id,
        event_type=EventType.LIKE.value,
        timestamp=time.time()
    )

    success = streaming.event_processor.publish_event(event)

    return {
        "status": "success" if success else "queued",
        "event_id": event.event_id,
        "message": "点赞事件已记录"
    }


@router.post("/events/search")
def publish_search_event(
    user_id: int,
    query: str = Query(..., min_length=1),
    db: Session = Depends(get_db)
):
    """发布搜索事件"""
    streaming = get_streaming_recommender(get_db)

    event = UserEvent(
        event_id=str(uuid.uuid4()),
        user_id=user_id,
        book_id=0,
        event_type=EventType.SEARCH.value,
        timestamp=time.time(),
        metadata={"query": query}
    )

    success = streaming.event_processor.publish_event(event)

    return {
        "status": "success" if success else "queued",
        "event_id": event.event_id,
        "message": "搜索事件已记录"
    }


@router.get("/trending")
def get_trending_books(
    n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """获取热门书籍"""
    streaming = get_streaming_recommender(get_db)
    trending = streaming.get_trending_books(n)

    # 补充书籍详细信息
    from app.models import Book
    results = []
    for item in trending:
        book = db.query(Book).filter(Book.id == item["book_id"]).first()
        if book:
            results.append({
                "book_id": book.id,
                "title": book.title,
                "author": book.author,
                "category": book.category,
                "image_url": book.image_url,
                "popularity": item["popularity"]
            })

    return {"trending_books": results}


@router.get("/realtime/{user_id}")
def get_realtime_recommendations(
    user_id: int,
    n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """获取实时推荐（基于最近行为）"""
    streaming = get_streaming_recommender(get_db)
    recs = streaming.get_realtime_recommendations(user_id, n)

    return {
        "user_id": user_id,
        "recommendations": recs,
        "message": "基于您的最近行为推荐"
    }
