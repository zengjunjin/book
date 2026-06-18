from app.services.recommender.hybrid_engine import HybridRecommender
from app.services.recommender.base import BaseRecommender

_recommender_instance = None


class RecommenderWrapper(HybridRecommender):
    """包装 HybridRecommender，提供缺失的 recommend 方法"""
    def recommend(self, user_id: int, n: int = 10):
        return self.hybrid_recommend(user_id, n, diversity=True)


def get_recommender() -> BaseRecommender:
    global _recommender_instance
    if _recommender_instance is None:
        _recommender_instance = RecommenderWrapper()
    return _recommender_instance
