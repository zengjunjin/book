import numpy as np
from scipy import sparse
from sqlalchemy import func
from typing import List, Dict
from app.database import SessionLocal
from app.models import Rating, Book
from app.services.recommender.base import BaseRecommender


class CFEngine(BaseRecommender):
    """User-based Collaborative Filtering Engine"""

    def __init__(self):
        super().__init__()
        self.rating_matrix = None
        self.user_map = {}
        self.item_map = {}
        self.reverse_user_map = {}
        self.reverse_item_map = {}
        self.load_data()

    def load_data(self):
        """Load rating data and build matrices"""
        db = SessionLocal()
        try:
            # Get all ratings
            ratings = db.query(Rating).all()

            # Build mappings
            user_ids = sorted(set(r.user_id for r in ratings))
            book_ids = sorted(set(r.book_id for r in ratings))

            self.user_map = {uid: idx for idx, uid in enumerate(user_ids)}
            self.item_map = {bid: idx for idx, bid in enumerate(book_ids)}
            self.reverse_user_map = {idx: uid for uid, idx in self.user_map.items()}
            self.reverse_item_map = {idx: bid for bid, idx in self.item_map.items()}

            # Build sparse rating matrix
            n_users = len(user_ids)
            n_items = len(book_ids)
            rows = [self.user_map[r.user_id] for r in ratings]
            cols = [self.item_map[r.book_id] for r in ratings]
            values = [r.rating for r in ratings]

            self.rating_matrix = sparse.csr_matrix(
                (values, (rows, cols)),
                shape=(n_users, n_items),
                dtype=np.float32
            )

            # Compute item means for normalization
            self.item_means = np.array(self.rating_matrix.sum(axis=0) / (self.rating_matrix > 0).sum(axis=0)).flatten()
            self.item_means = np.nan_to_num(self.item_means, nan=0)

        finally:
            db.close()

    def cosine_similarity(self, user_idx: int, candidate_indices: List[int]) -> List[float]:
        """Calculate cosine similarity between user and candidates"""
        user_vector = self.rating_matrix[user_idx].toarray().flatten()
        user_nonzero = user_vector > 0

        similarities = []
        for item_idx in candidate_indices:
            item_vector = self.rating_matrix[:, item_idx].toarray().flatten()
            item_nonzero = item_vector > 0

            # Overlap-based similarity
            overlap = np.logical_and(user_nonzero, item_nonzero).sum()
            if overlap < 1:
                similarities.append(0.0)
            else:
                user_rated = user_vector[user_nonzero]
                item_ratings = item_vector[item_nonzero]

                norm_user = np.sqrt(np.sum(user_rated ** 2))
                norm_item = np.sqrt(np.sum(item_ratings ** 2))

                if norm_user > 0 and norm_item > 0:
                    sim = np.dot(user_rated, item_ratings) / (norm_user * norm_item)
                    similarities.append(sim)
                else:
                    similarities.append(0.0)

        return similarities

    def recommend(self, user_id: int, n: int = 20) -> List[Dict]:
        """Generate CF recommendations"""
        # Check cache
        cache_key = f"user:{user_id}:recommendations:cf"
        cached = self.get_cache(cache_key)
        if cached:
            return cached[:n]

        if user_id not in self.user_map:
            return []

        user_idx = self.user_map[user_id]

        # Get unrated items
        user_ratings = self.rating_matrix[user_idx].toarray().flatten()
        unrated_mask = user_ratings == 0
        unrated_indices = np.where(unrated_mask)[0]

        if len(unrated_indices) == 0:
            return []

        # Calculate similarities and predict
        similarities = self.cosine_similarity(user_idx, unrated_indices)

        # Weighted average prediction
        predictions = []
        for i, item_idx in enumerate(unrated_indices):
            sim = similarities[i]
            if sim > 0:
                # Get ratings from similar users
                item_ratings = self.rating_matrix[:, item_idx].toarray().flatten()
                rated_mask = item_ratings > 0
                if rated_mask.sum() > 0:
                    # Weighted prediction
                    weight = sim * (item_ratings[rated_mask] - self.item_means[item_idx])
                    pred = self.item_means[item_idx] + np.sum(weight) / (np.sum(np.abs(similarities[i])) + 0.1)
                    pred = max(1, min(10, pred))
                    predictions.append((item_idx, pred, sim))

        # Sort by prediction score
        predictions.sort(key=lambda x: x[1], reverse=True)
        top_predictions = predictions[:n * 3]  # Get more for diversity

        # Get book details
        db = SessionLocal()
        try:
            results = []
            seen_books = set()
            for item_idx, score, sim in top_predictions:
                book_id = self.reverse_item_map[item_idx]
                if book_id in seen_books:
                    continue
                seen_books.add(book_id)

                book = db.query(Book).filter(Book.id == book_id).first()
                if book:
                    results.append({
                        "book_id": book.id,
                        "title": book.title,
                        "author": book.author,
                        "image_url": book.image_url,
                        "score": round(score, 2),
                        "reason": "与你口味相似的用户喜欢",
                        "source": "cf"
                    })

                if len(results) >= n:
                    break

            # Cache results
            self.set_cache(cache_key, results, ttl=300)

            return results
        finally:
            db.close()
