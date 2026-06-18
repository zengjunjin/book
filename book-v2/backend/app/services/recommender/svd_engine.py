import random
import numpy as np
import pandas as pd
from surprise import SVD, Dataset, Reader
from sqlalchemy import func
from typing import List, Dict
from app.database import SessionLocal
from app.models import Rating, Book
from app.services.recommender.base import BaseRecommender


class SVDEngine(BaseRecommender):
    """SVD Matrix Factorization Engine"""

    def __init__(self):
        super().__init__()
        self.model = None
        self.all_book_ids = []
        self.load_model()

    def load_model(self):
        """Load or train SVD model"""
        db = SessionLocal()
        try:
            # Get all ratings
            ratings = db.query(Rating).all()
            if len(ratings) < 100:
                self.model = None
                self.all_book_ids = []
                return

            # Prepare data for surprise
            reader = Reader(rating_scale=(1, 10))
            ratings_data = [(r.user_id, r.book_id, r.rating) for r in ratings]
            df = pd.DataFrame(ratings_data, columns=['user_id', 'book_id', 'rating'])
            data = Dataset.load_from_df(df, reader)
            trainset = data.build_full_trainset()

            # Train SVD
            self.model = SVD(n_factors=100, n_epochs=20, random_state=42)
            self.model.fit(trainset)

            # Get all book IDs
            self.all_book_ids = list(set(r.book_id for r in ratings))

        finally:
            db.close()

    def recommend(self, user_id: int, n: int = 20, seed: int = None) -> List[Dict]:
        """Generate SVD recommendations"""
        if self.model is None:
            return []

        # Check cache
        cache_key = f"user:{user_id}:recommendations:svd"
        cached = self.get_cache(cache_key)
        if cached and seed is not None:
            random.seed(seed)
            random.shuffle(cached)
            return cached[:n]
        elif cached:
            return cached[:n]

        db = SessionLocal()
        try:
            # Get user's rated books
            rated = set(r.book_id for r in db.query(Rating).filter(Rating.user_id == user_id).all())

            # Predict for all unrated books
            predictions = []
            for book_id in self.all_book_ids:
                if book_id in rated:
                    continue

                pred = self.model.predict(user_id, book_id)
                score = max(1, min(10, pred.est + random.uniform(-1.0, 1.0)))
                predictions.append((book_id, score))

            # Sort by score
            predictions.sort(key=lambda x: x[1], reverse=True)

            # Get top candidates and shuffle for diversity
            top_candidates = predictions[:n * 3]
            random.shuffle(top_candidates)
            top_predictions = top_candidates[:n]

            # Get book details
            results = []
            for book_id, score in top_predictions:
                book = db.query(Book).filter(Book.id == book_id).first()
                if book:
                    user_rating_record = db.query(Rating).filter(
                        Rating.user_id == user_id,
                        Rating.book_id == book.id
                    ).first()
                    book_avg_rating = db.query(func.avg(Rating.rating)).filter(
                        Rating.book_id == book.id
                    ).scalar()
                    results.append({
                        "book_id": book.id,
                        "id": book.id,
                        "title": book.title,
                        "author": book.author,
                        "image_url": book.image_url,
                        "score": round(score, 2),
                        "predicted_rating": round(score, 2),
                        "user_rating": float(user_rating_record.rating) if user_rating_record else None,
                        "avg_rating": float(book_avg_rating) if book_avg_rating else None,
                        "reason": "基于你评分模式的预测",
                        "source": "svd"
                    })

            # Cache results
            self.set_cache(cache_key, results, ttl=300)

            return results
        finally:
            db.close()
