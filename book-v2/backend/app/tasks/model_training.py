from celery import shared_task
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Book, Rating
from app.celery_app import celery_app


@celery_app.task
def update_book_stats(book_id: int):
    """Update book statistics after rating changes"""
    db = SessionLocal()
    try:
        ratings = db.query(Rating).filter(Rating.book_id == book_id).all()
        count = len(ratings)
        avg = sum(r.rating for r in ratings) / count if count > 0 else 0

        book = db.query(Book).filter(Book.id == book_id).first()
        if book:
            book.rating_count = count
            book.avg_rating = round(avg, 2)
            db.commit()

        # Clear recommendation cache
        from app.services.recommender import get_recommender
        try:
            recommender = get_recommender()
            pattern = f"user:*:recommendations:*"
            keys = recommender.redis_client.keys(pattern)
            if keys:
                recommender.redis_client.delete(*keys)
        except Exception:
            pass

        return {"book_id": book_id, "rating_count": count, "avg_rating": avg}
    finally:
        db.close()


@celery_app.task
def retrain_models():
    """Retrain recommendation models (scheduled task)"""
    from app.services.recommender import get_recommender
    try:
        recommender = get_recommender()

        # Reload CF model
        recommender.cf_engine.load_data()

        # Reload SVD model
        recommender.svd_engine.load_model()

        # Clear all caches
        recommender.redis_client.flushdb()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    return {"status": "success", "message": "Models retrained and cache cleared"}


@celery_app.task
def update_popular_books():
    """Update popular books cache"""
    db = SessionLocal()
    try:
        books = db.query(Book).filter(
            Book.rating_count > 0
        ).order_by(
            Book.avg_rating.desc(),
            Book.rating_count.desc()
        ).limit(100).all()

        from app.services.recommender import get_recommender
        try:
            recommender = get_recommender()
            cache_key = "popular:books"
            recommender.redis_client.delete(cache_key)

            for i, book in enumerate(books):
                recommender.redis_client.zadd(cache_key, {str(book.id): book.avg_rating})

            recommender.redis_client.expire(cache_key, 3600)
        except Exception:
            pass

        return {"status": "success", "count": len(books)}
    finally:
        db.close()


@celery_app.task
def refresh_all_book_stats():
    """Batch refresh all book statistics (for initialization)"""
    db = SessionLocal()
    try:
        books = db.query(Book).all()
        updated_count = 0

        for book in books:
            ratings = db.query(Rating).filter(Rating.book_id == book.id).all()
            count = len(ratings)
            avg = sum(r.rating for r in ratings) / count if count > 0 else 0

            if book.rating_count != count or abs(book.avg_rating - avg) > 0.01:
                book.rating_count = count
                book.avg_rating = round(avg, 2)
                updated_count += 1

        db.commit()

        return {"status": "success", "total_books": len(books), "updated_count": updated_count}
    finally:
        db.close()
