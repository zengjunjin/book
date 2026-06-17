from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.interaction import InteractionCreate, InteractionResponse
from app.models import Interaction, Book
from app.api.deps import get_current_user
from app.models import User

router = APIRouter()


@router.post("/", response_model=dict)
def create_interaction(
    interaction_data: InteractionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validate interaction type
    valid_types = ["view", "like", "dislike", "want_to_read", "read"]
    if interaction_data.interaction_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid interaction type. Must be one of: {valid_types}")

    # Check if book exists
    book = db.query(Book).filter(Book.id == interaction_data.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Check if interaction exists
    existing = db.query(Interaction).filter(
        Interaction.user_id == current_user.id,
        Interaction.book_id == interaction_data.book_id,
        Interaction.interaction_type == interaction_data.interaction_type
    ).first()

    if existing:
        # Remove existing (toggle behavior)
        db.delete(existing)
        db.commit()
        return {"success": True, "action": "removed", "type": interaction_data.interaction_type}

    # Create interaction
    interaction = Interaction(
        user_id=current_user.id,
        book_id=interaction_data.book_id,
        interaction_type=interaction_data.interaction_type
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    return {"success": True, "action": "added", "type": interaction_data.interaction_type}


@router.get("/user")
def get_user_interactions(
    interaction_type: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Interaction).filter(Interaction.user_id == current_user.id)

    if interaction_type:
        query = query.filter(Interaction.interaction_type == interaction_type)

    interactions = query.all()
    return {
        "interactions": [InteractionResponse.model_validate(i) for i in interactions],
        "total": len(interactions)
    }


@router.delete("/{interaction_id}")
def delete_interaction(
    interaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    interaction = db.query(Interaction).filter(
        Interaction.id == interaction_id,
        Interaction.user_id == current_user.id
    ).first()

    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")

    db.delete(interaction)
    db.commit()
    return {"success": True}
