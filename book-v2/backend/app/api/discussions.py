from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from app.database import get_db
from app.schemas.social import (
    DiscussionCreate, DiscussionUpdate, DiscussionResponse, DiscussionListResponse,
    DiscussionReplyCreate, DiscussionReplyResponse, DiscussionReplyListResponse,
)
from app.models import User, Book
from app.models.social import Discussion, DiscussionReply
from app.api.deps import get_current_user

router = APIRouter()


def _build_discussion_with_details(discussion: Discussion, db: Session) -> dict:
    """构建包含用户信息和回复数的讨论对象"""
    user = db.query(User).filter(User.id == discussion.user_id).first()
    reply_count = db.query(DiscussionReply).filter(DiscussionReply.discussion_id == discussion.id).count()
    
    return {
        "id": discussion.id,
        "user_id": discussion.user_id,
        "book_id": discussion.book_id,
        "title": discussion.title,
        "content": discussion.content,
        "created_at": discussion.created_at,
        "updated_at": discussion.updated_at,
        "user": {
            "id": user.id,
            "username": user.username,
            "avatar_url": user.avatar_url
        } if user else None,
        "reply_count": reply_count
    }


@router.get("/books/{book_id}", response_model=DiscussionListResponse)
def get_book_discussions(
    book_id: int,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db)
):
    """获取书籍的讨论列表"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    query = db.query(Discussion).filter(Discussion.book_id == book_id).order_by(desc(Discussion.created_at))
    total = query.count()
    discussions = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return DiscussionListResponse(
        discussions=[_build_discussion_with_details(d, db) for d in discussions],
        total=total,
        page=page,
        pages=(total + per_page - 1) // per_page
    )


@router.get("/{discussion_id}", response_model=DiscussionResponse)
def get_discussion(
    discussion_id: int,
    db: Session = Depends(get_db)
):
    """获取讨论详情"""
    discussion = db.query(Discussion).filter(Discussion.id == discussion_id).first()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    return _build_discussion_with_details(discussion, db)


@router.post("", response_model=DiscussionResponse)
def create_discussion(
    discussion_data: DiscussionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """发布讨论帖"""
    book = db.query(Book).filter(Book.id == discussion_data.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    discussion = Discussion(
        user_id=current_user.id,
        book_id=discussion_data.book_id,
        title=discussion_data.title,
        content=discussion_data.content
    )
    db.add(discussion)
    db.commit()
    db.refresh(discussion)
    
    return _build_discussion_with_details(discussion, db)


@router.put("/{discussion_id}", response_model=DiscussionResponse)
def update_discussion(
    discussion_id: int,
    discussion_data: DiscussionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新讨论帖"""
    discussion = db.query(Discussion).filter(Discussion.id == discussion_id).first()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    if discussion.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this discussion")
    
    if discussion_data.title is not None:
        discussion.title = discussion_data.title
    if discussion_data.content is not None:
        discussion.content = discussion_data.content
    
    db.commit()
    db.refresh(discussion)
    
    return _build_discussion_with_details(discussion, db)


@router.delete("/{discussion_id}")
def delete_discussion(
    discussion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除讨论帖"""
    discussion = db.query(Discussion).filter(Discussion.id == discussion_id).first()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    if discussion.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this discussion")
    
    db.delete(discussion)
    db.commit()
    
    return {"success": True}


@router.get("/{discussion_id}/replies", response_model=DiscussionReplyListResponse)
def get_discussion_replies(
    discussion_id: int,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db)
):
    """获取讨论帖的回复列表"""
    discussion = db.query(Discussion).filter(Discussion.id == discussion_id).first()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    query = db.query(DiscussionReply).filter(
        DiscussionReply.discussion_id == discussion_id
    ).order_by(DiscussionReply.created_at)
    
    total = query.count()
    replies = query.offset((page - 1) * per_page).limit(per_page).all()
    
    result = []
    for r in replies:
        user = db.query(User).filter(User.id == r.user_id).first()
        result.append({
            "id": r.id,
            "user_id": r.user_id,
            "discussion_id": r.discussion_id,
            "content": r.content,
            "created_at": r.created_at,
            "user": {
                "id": user.id,
                "username": user.username,
                "avatar_url": user.avatar_url
            } if user else None
        })
    
    return DiscussionReplyListResponse(
        replies=result,
        total=total,
        page=page,
        pages=(total + per_page - 1) // per_page
    )


@router.post("/{discussion_id}/replies", response_model=DiscussionReplyResponse)
def create_discussion_reply(
    discussion_id: int,
    reply_data: DiscussionReplyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """回复讨论帖"""
    discussion = db.query(Discussion).filter(Discussion.id == discussion_id).first()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    reply = DiscussionReply(
        user_id=current_user.id,
        discussion_id=discussion_id,
        content=reply_data.content
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    
    return {
        "id": reply.id,
        "user_id": reply.user_id,
        "discussion_id": reply.discussion_id,
        "content": reply.content,
        "created_at": reply.created_at,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "avatar_url": current_user.avatar_url
        }
    }


@router.delete("/{discussion_id}/replies/{reply_id}")
def delete_discussion_reply(
    discussion_id: int,
    reply_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除讨论回复"""
    reply = db.query(DiscussionReply).filter(
        DiscussionReply.id == reply_id,
        DiscussionReply.discussion_id == discussion_id
    ).first()
    
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    
    if reply.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this reply")
    
    db.delete(reply)
    db.commit()
    
    return {"success": True}
