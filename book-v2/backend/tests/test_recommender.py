import pytest
from app.services.recommender.hybrid_engine import HybridRecommender


def test_hybrid_recommender_initialization():
    recommender = HybridRecommender()
    assert recommender is not None
    assert recommender.cf_engine is not None
    assert recommender.svd_engine is not None
    assert recommender.cold_start is not None


def test_diversity_sampler():
    from app.services.recommender.diversity import DiversitySampler

    sampler = DiversitySampler(max_same_category=2, max_same_author=1)

    candidates = [
        {"book_id": 1, "title": "Book A", "author": "Author 1", "category": "Sci-Fi", "score": 9.0},
        {"book_id": 2, "title": "Book B", "author": "Author 1", "category": "Sci-Fi", "score": 8.5},
        {"book_id": 3, "title": "Book C", "author": "Author 2", "category": "Sci-Fi", "score": 8.0},
        {"book_id": 4, "title": "Book D", "author": "Author 3", "category": "Fantasy", "score": 7.5},
        {"book_id": 5, "title": "Book E", "author": "Author 4", "category": "Fantasy", "score": 7.0},
    ]

    result, explore_count, diversity = sampler.sample(candidates, 4)

    assert len(result) == 4
    assert diversity > 0


def test_preference_score_calculation():
    from app.services.interaction import InteractionService

    score = InteractionService.calculate_preference_score(
        rating=8,
        liked=True,
        wanted=True
    )

    expected = (8/10) * 0.5 + 0.5 + 0.3
    assert abs(score - expected) < 0.01
