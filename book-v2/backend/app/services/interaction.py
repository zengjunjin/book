from sqlalchemy.orm import Session
from typing import Dict, Set
from app.models import Interaction


class InteractionService:
    """Handle user interaction business logic"""

    # Weight for preference calculation
    INTERACTION_WEIGHTS = {
        "view": 0.1,
        "like": 0.5,
        "dislike": -0.5,
        "want_to_read": 0.3,
        "read": 0.0,
    }

    @staticmethod
    def calculate_preference_score(
        rating: int = None,
        liked: bool = False,
        disliked: bool = False,
        wanted: bool = False,
        view_count: int = 0
    ) -> float:
        """Calculate preference score from interactions"""
        score = 0.0

        if rating is not None:
            score += (rating / 10) * 0.5

        if liked:
            score += InteractionService.INTERACTION_WEIGHTS["like"]

        if disliked:
            score += InteractionService.INTERACTION_WEIGHTS["dislike"]

        if wanted:
            score += InteractionService.INTERACTION_WEIGHTS["want_to_read"]

        if view_count > 0:
            score += min(view_count / 10, 1) * InteractionService.INTERACTION_WEIGHTS["view"]

        return max(0, min(1, score))

    @staticmethod
    def get_user_interaction_set(db: Session, user_id: int) -> Dict[str, Set[int]]:
        """Get all user interactions as sets"""
        interactions = db.query(Interaction).filter(
            Interaction.user_id == user_id
        ).all()

        result = {
            "liked": set(),
            "disliked": set(),
            "wanted": set(),
            "viewed": set(),
            "read": set(),
        }

        for i in interactions:
            key = {
                "like": "liked",
                "dislike": "disliked",
                "want_to_read": "wanted",
                "view": "viewed",
                "read": "read",
            }.get(i.interaction_type)

            if key:
                result[key].add(i.book_id)

        return result
