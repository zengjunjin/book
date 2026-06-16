from abc import ABC, abstractmethod
from typing import List, Dict, Tuple
import redis
import json
from app.config import settings


class BaseRecommender(ABC):
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

    def get_cache(self, key: str) -> List[Dict]:
        """Get recommendations from cache"""
        cached = self.redis_client.get(key)
        if cached:
            return json.loads(cached)
        return None

    def set_cache(self, key: str, data: List[Dict], ttl: int = 300):
        """Set recommendations cache"""
        self.redis_client.setex(key, ttl, json.dumps(data))

    def clear_user_cache(self, user_id: int):
        """Clear all recommendation caches for a user"""
        pattern = f"user:{user_id}:recommendations:*"
        keys = self.redis_client.keys(pattern)
        if keys:
            self.redis_client.delete(*keys)

    @abstractmethod
    def recommend(self, user_id: int, n: int = 20) -> List[Dict]:
        """Generate recommendations for a user"""
        pass

    def get_user_preferences(self, db, user_id: int) -> Dict:
        """Get user preferences from ratings and interactions"""
        from app.models import Rating, Interaction, UserTag

        # Get ratings
        ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
        rated_books = {r.book_id: r.rating for r in ratings}

        # Get interactions
        interactions = db.query(Interaction).filter(Interaction.user_id == user_id).all()
        liked_books = set()
        disliked_books = set()
        wanted_books = set()

        for i in interactions:
            if i.interaction_type == "like":
                liked_books.add(i.book_id)
            elif i.interaction_type == "dislike":
                disliked_books.add(i.book_id)
            elif i.interaction_type == "want_to_read":
                wanted_books.add(i.book_id)

        # Get user tags
        user_tags = db.query(UserTag).filter(UserTag.user_id == user_id).all()
        tags = [t.tag_name for t in user_tags]

        return {
            "rated_books": rated_books,
            "liked_books": liked_books,
            "disliked_books": disliked_books,
            "wanted_books": wanted_books,
            "tags": tags
        }
