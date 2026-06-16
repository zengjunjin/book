from app.services.recommender.hybrid_engine import HybridRecommender

_recommender_instance = None


def get_recommender() -> HybridRecommender:
    global _recommender_instance
    if _recommender_instance is None:
        _recommender_instance = HybridRecommender()
    return _recommender_instance
