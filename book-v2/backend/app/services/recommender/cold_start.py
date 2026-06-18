from sqlalchemy import func
from app.database import SessionLocal
from app.models import Book, UserTag, Rating
from app.services.recommender.base import BaseRecommender


class ColdStartHandler(BaseRecommender):
    """Handle cold start recommendations for new users"""

    def __init__(self):
        super().__init__()

    def get_tag_based_recommendations(self, user_id: int, n: int = 20) -> list:
        """Recommend books based on user's interest tags"""
        db = SessionLocal()
        try:
            # Get user tags
            user_tags = db.query(UserTag).filter(UserTag.user_id == user_id).all()
            tag_names = [t.tag_name for t in user_tags]

            if not tag_names:
                # Fallback to popular books
                return self.get_popular_recommendations(n)

            # Get user's rated books
            rated_book_ids = set(r.book_id for r in db.query(Rating).filter(Rating.user_id == user_id).all())

            # Find books matching user tags
            query = db.query(Book).filter(
                Book.tags.overlap(tag_names),
                Book.id.notin_(rated_book_ids),
                Book.avg_rating > 0
            ).order_by(Book.avg_rating.desc(), Book.rating_count.desc())

            books = query.limit(n).all()

            if len(books) < n:
                # Add popular books
                popular = self.get_popular_recommendations(n - len(books))
                for p in popular:
                    if len(books) >= n:
                        break
                    books.append(p)

            results = []
            for book in books[:n]:
                matching_tags = [t for t in (book.tags or []) if t in tag_names]
                user_rating_record = db.query(Rating).filter(
                    Rating.user_id == user_id,
                    Rating.book_id == book.id
                ).first()
                results.append({
                    "book_id": book.id,
                    "id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "image_url": book.image_url,
                    "score": book.avg_rating,
                    "predicted_rating": book.avg_rating,
                    "user_rating": float(user_rating_record.rating) if user_rating_record else None,
                    "avg_rating": book.avg_rating,
                    "reason": f"匹配你的兴趣: {', '.join(matching_tags[:2])}" if matching_tags else "热门推荐",
                    "source": "cold_start"
                })

            return results
        finally:
            db.close()

    def recommend(self, user_id: int, n: int = 20) -> list:
        """Generate cold start recommendations for a user"""
        return self.get_tag_based_recommendations(user_id, n)

    def get_popular_recommendations(self, n: int = 20) -> list:
        """Get popular books as fallback"""
        db = SessionLocal()
        try:
            # Check cache
            cache_key = "popular:books"
            cached = self.redis_client.zrevrange(cache_key, 0, n - 1, withscores=True)
            if cached:
                book_ids = [int(bid) for bid, score in cached]
                books = db.query(Book).filter(Book.id.in_(book_ids)).all()
                book_map = {b.id: b for b in books}
                results = []
                for bid, score in cached:
                    bid_int = int(bid)
                    if bid_int in book_map:
                        b = book_map[bid_int]
                        results.append({
                            "book_id": b.id,
                            "id": b.id,
                            "title": b.title,
                            "author": b.author,
                            "image_url": b.image_url,
                            "score": b.avg_rating,
                            "predicted_rating": b.avg_rating,
                            "user_rating": None,
                            "avg_rating": b.avg_rating,
                            "reason": "热门推荐",
                            "source": "popular"
                        })
                return results

            # Query popular books
            books = db.query(Book).filter(
                Book.rating_count > 0
            ).order_by(
                Book.avg_rating.desc(),
                Book.rating_count.desc()
            ).limit(n).all()

            results = [
                {
                    "book_id": book.id,
                    "id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "image_url": book.image_url,
                    "score": book.avg_rating,
                    "predicted_rating": book.avg_rating,
                    "user_rating": None,
                    "avg_rating": book.avg_rating,
                    "reason": "热门推荐",
                    "source": "popular"
                }
                for book in books
            ]

            # Cache in Redis
            for book in books:
                self.redis_client.zadd(cache_key, {str(book.id): book.avg_rating})
            self.redis_client.expire(cache_key, 600)

            return results
        finally:
            db.close()
