from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.user_tag import UserTagCreate, UserTagResponse, UserTagListResponse
from app.models import UserTag
from app.api.deps import get_current_user
from app.models import User

router = APIRouter()


@router.get("/tags", response_model=UserTagListResponse)
def get_user_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tags = db.query(UserTag).filter(UserTag.user_id == current_user.id).all()
    return UserTagListResponse(tags=tags, total=len(tags))


@router.post("/tags", response_model=UserTagResponse)
def create_user_tag(
    tag_data: UserTagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if tag already exists
    existing = db.query(UserTag).filter(
        UserTag.user_id == current_user.id,
        UserTag.tag_name == tag_data.tag_name
    ).first()

    if existing:
        # Update weight
        existing.weight = tag_data.weight
        db.commit()
        db.refresh(existing)
        return existing

    # Create new tag
    tag = UserTag(
        user_id=current_user.id,
        tag_name=tag_data.tag_name,
        weight=tag_data.weight
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/tags/{tag_name}")
def delete_user_tag(
    tag_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tag = db.query(UserTag).filter(
        UserTag.user_id == current_user.id,
        UserTag.tag_name == tag_name
    ).first()

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    db.delete(tag)
    db.commit()
    return {"success": True}


@router.get("/profile")
def get_user_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models import Rating, Interaction

    rating_count = db.query(Rating).filter(Rating.user_id == current_user.id).count()
    interaction_count = db.query(Interaction).filter(Interaction.user_id == current_user.id).count()
    tags = db.query(UserTag).filter(UserTag.user_id == current_user.id).all()

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "avatar_url": current_user.avatar_url,
        "rating_count": rating_count,
        "interaction_count": interaction_count,
        "tags": [UserTagResponse.model_validate(t) for t in tags]
    }
