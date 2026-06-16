from typing import List, Dict, Tuple, Set
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Book, Rating, Interaction
from app.services.recommender.base import BaseRecommender
from app.services.recommender.cf_engine import CFEngine
from app.services.recommender.svd_engine import SVDEngine
from app.services.recommender.cold_start import ColdStartHandler
from app.services.recommender.diversity import DiversitySampler


class HybridRecommender(BaseRecommender):
    """Hybrid recommendation engine combining multiple strategies"""

    def __init__(self):
        super().__init__()
        self.cf_engine = CFEngine()
        self.svd_engine = SVDEngine()
        self.cold_start = ColdStartHandler()
        self.diversity = DiversitySampler(explore_ratio=0.15)

    def is_cold_start(self, db, user_id: int) -> bool:
        """Check if user is in cold start state"""
        rating_count = db.query(Rating).filter(Rating.user_id == user_id).count()
        return rating_count < 5

    def apply_interaction_adjustment(
        self,
        recommendations: List[Dict],
        user_prefs: Dict
    ) -> List[Dict]:
        """Adjust recommendation scores based on user interactions"""
        liked = user_prefs.get("liked_books", set())
        disliked = user_prefs.get("disliked_books", set())
        wanted = user_prefs.get("wanted_books", set())

        for rec in recommendations:
            book_id = rec["book_id"]

            if book_id in liked:
                rec["score"] += 1.5
            if book_id in disliked:
                rec["score"] -= 2.0
            if book_id in wanted:
                rec["score"] += 1.0

            rec["score"] = max(0, rec["score"])

        return recommendations

    def cf_recommend(self, user_id: int, n: int = 20) -> List[Dict]:
        """Get CF-only recommendations"""
        db = SessionLocal()
        try:
            user_prefs = self.get_user_preferences(db, user_id)
            recs = self.cf_engine.recommend(user_id, n * 2)
            recs = self.apply_interaction_adjustment(recs, user_prefs)
            return sorted(recs, key=lambda x: x["score"], reverse=True)[:n]
        finally:
            db.close()

    def svd_recommend(self, user_id: int, n: int = 20) -> List[Dict]:
        """Get SVD-only recommendations"""
        db = SessionLocal()
        try:
            user_prefs = self.get_user_preferences(db, user_id)
            recs = self.svd_engine.recommend(user_id, n * 2)
            recs = self.apply_interaction_adjustment(recs, user_prefs)
            return sorted(recs, key=lambda x: x["score"], reverse=True)[:n]
        finally:
            db.close()

    def cold_start_recommend(self, user_id: int, n: int = 20) -> List[Dict]:
        """Get cold start recommendations based on user tags"""
        return self.cold_start.get_tag_based_recommendations(user_id, n)

    def hybrid_recommend(
        self,
        user_id: int,
        n: int = 20,
        diversity: bool = True
    ) -> Tuple[List[Dict], int, float]:
        """Get hybrid recommendations with diversity"""
        db = SessionLocal()
        try:
            # Check cold start
            if self.is_cold_start(db, user_id):
                recs = self.cold_start_recommend(user_id, n)
                return recs, 0, self.diversity._calculate_diversity(recs)

            # Get user preferences
            user_prefs = self.get_user_preferences(db, user_id)
            interacted = (
                user_prefs["rated_books"].keys() |
                user_prefs["liked_books"] |
                user_prefs["disliked_books"] |
                user_prefs["wanted_books"]
            )

            # Get recommendations from multiple sources
            cf_recs = self.cf_engine.recommend(user_id, n * 2)
            svd_recs = self.svd_engine.recommend(user_id, n * 2)

            # Merge and deduplicate
            all_recs = {r["book_id"]: r for r in cf_recs + svd_recs}

            # Average scores for duplicate books
            for bid in all_recs:
                sources = [r for r in cf_recs + svd_recs if r["book_id"] == bid]
                if len(sources) > 1:
                    avg_score = sum(s["score"] for s in sources) / len(sources)
                    all_recs[bid]["score"] = avg_score

            recommendations = list(all_recs.values())

            # Apply interaction adjustment
            recommendations = self.apply_interaction_adjustment(recommendations, user_prefs)

            # Sort by score
            recommendations.sort(key=lambda x: x["score"], reverse=True)

            if diversity:
                # Apply diversity sampling
                final_recs, explore_count, diversity_score = self.diversity.sample(
                    recommendations, n, interacted
                )
                return final_recs, explore_count, diversity_score

            return recommendations[:n], 0, 0.0
        finally:
            db.close()
