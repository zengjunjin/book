# -*- coding: utf-8 -*-
"""用户画像 + 兴趣漂移检测 + 用户反馈闭环服务"""
import time
import math
from typing import Optional, Dict, List, Any
from collections import defaultdict
from threading import Lock

try:
    from extensions import db
    from models import Book, Rating
    _HAS_DB = True
except Exception:
    db = None
    Book = None
    Rating = None
    _HAS_DB = False


# ---------------- 内存缓存 ----------------
_profile_cache: Dict[int, Dict[str, Any]] = {}
_profile_ttl: Dict[int, float] = {}
_cache_lock = Lock()
_PROFILE_TTL = 600


def _empty_profile(user_id: int) -> Dict[str, Any]:
    return {
        'user_id': user_id,
        'total_ratings': 0,
        'avg_rating': 0.0,
        'preferred_authors': [],
        'preferred_categories': [],
        'year_distribution': {},
        'rating_history': [],
        'cold_start': True,
    }


class UserProfileService:
    """用户画像服务 - 单例"""

    _instance: Optional['UserProfileService'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _cache_get(self, user_id: int) -> Optional[Dict[str, Any]]:
        with _cache_lock:
            expire = _profile_ttl.get(user_id, 0)
            if expire and expire > time.time():
                return _profile_cache.get(user_id)
            if user_id in _profile_cache:
                del _profile_cache[user_id]
                _profile_ttl.pop(user_id, None)
            return None

    def _cache_set(self, user_id: int, profile: Dict[str, Any]):
        with _cache_lock:
            _profile_cache[user_id] = profile
            _profile_ttl[user_id] = time.time() + _PROFILE_TTL

    def get_profile(self, user_id: int) -> Dict[str, Any]:
        try:
            cached = self._cache_get(user_id)
            if cached is not None:
                return cached
            profile = self.rebuild_profile(user_id)
            self._cache_set(user_id, profile)
            return profile
        except Exception:
            return _empty_profile(user_id)

    def rebuild_profile(self, user_id: int) -> Dict[str, Any]:
        try:
            if not _HAS_DB:
                return _empty_profile(user_id)

            ratings = (
                db.session.query(Rating)
                .filter(Rating.user_id == user_id)
                .order_by(Rating.created_at.desc())
                .all()
            )
            if not ratings:
                profile = _empty_profile(user_id)
                self._cache_set(user_id, profile)
                return profile

            book_ids = [r.book_id for r in ratings]
            books = {b.id: b for b in db.session.query(Book).filter(Book.id.in_(book_ids)).all()}

            total_ratings = len(ratings)
            avg_rating = round(sum(r.rating for r in ratings) / total_ratings, 2)

            author_scores: Dict[str, float] = defaultdict(float)
            author_counts: Dict[str, int] = defaultdict(int)
            category_scores: Dict[str, float] = defaultdict(float)
            category_counts: Dict[str, int] = defaultdict(int)
            year_distribution: Dict[str, int] = defaultdict(int)

            rating_history = []
            for r in ratings[:20]:
                b = books.get(r.book_id)
                entry = {
                    'rating_id': r.id,
                    'book_id': r.book_id,
                    'rating': r.rating,
                    'created_at': r.created_at.isoformat() if r.created_at else None,
                    'title': b.title if b else None,
                    'author': b.author if b else None,
                    'category': b.category if b else None,
                }
                rating_history.append(entry)

            for r in ratings:
                b = books.get(r.book_id)
                if not b:
                    continue
                if b.author:
                    author_scores[b.author] += r.rating
                    author_counts[b.author] += 1
                if b.category:
                    category_scores[b.category] += r.rating
                    category_counts[b.category] += 1
                if b.year:
                    decade = f"{(b.year // 10) * 10}s"
                    year_distribution[decade] += 1

            def top_items(scores: Dict[str, float], counts: Dict[str, int], top: int = 5):
                items = []
                for name, score in scores.items():
                    cnt = counts.get(name, 1)
                    items.append({'name': name, 'score': round(score / cnt, 2), 'count': cnt})
                items.sort(key=lambda x: (-x['score'], -x['count']))
                return items[:top]

            preferred_authors = top_items(author_scores, author_counts)
            preferred_categories = top_items(category_scores, category_counts)

            profile = {
                'user_id': user_id,
                'total_ratings': total_ratings,
                'avg_rating': avg_rating,
                'preferred_authors': preferred_authors,
                'preferred_categories': preferred_categories,
                'year_distribution': dict(year_distribution),
                'rating_history': rating_history,
                'cold_start': total_ratings < 5,
            }
            self._cache_set(user_id, profile)
            return profile
        except Exception:
            return _empty_profile(user_id)

    def is_cold_start(self, user_id: int) -> bool:
        try:
            profile = self.get_profile(user_id)
            return profile.get('cold_start', True)
        except Exception:
            return True

    def invalidate_cache(self, user_id: int):
        try:
            with _cache_lock:
                _profile_cache.pop(user_id, None)
                _profile_ttl.pop(user_id, None)
        except Exception:
            pass


user_profile_service = UserProfileService()


# ---------------- 兴趣漂移检测 ----------------
def _cosine_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a.keys()) | set(b.keys())
    if not keys:
        return 0.0
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _extract_category_scores(ratings_list, books_map) -> Dict[str, float]:
    scores: Dict[str, float] = defaultdict(float)
    counts: Dict[str, int] = defaultdict(int)
    for r in ratings_list:
        b = books_map.get(r.book_id)
        if not b or not b.category:
            continue
        scores[b.category] += r.rating
        counts[b.category] += 1
    return {c: scores[c] / counts[c] for c in scores}


class InterestDriftDetector:
    """兴趣漂移检测器 - 单例"""

    _instance: Optional['InterestDriftDetector'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_user_ratings(self, user_id: int):
        try:
            if not _HAS_DB:
                return []
            ratings = (
                db.session.query(Rating)
                .filter(Rating.user_id == user_id)
                .order_by(Rating.created_at.asc())
                .all()
            )
            return ratings or []
        except Exception:
            return []

    def detect_drift(self, user_id: int, threshold: float = 0.3) -> Dict[str, Any]:
        try:
            ratings = self._get_user_ratings(user_id)
            if len(ratings) < 10:
                return {'drift': False, 'similarity': 1.0, 'threshold': threshold, 'reason': ''}

            mid = len(ratings) // 2
            first_half = ratings[:mid]
            second_half = ratings[mid:]

            book_ids = {r.book_id for r in ratings}
            books_map = {b.id: b for b in db.session.query(Book).filter(Book.id.in_(book_ids)).all()}

            first_scores = _extract_category_scores(first_half, books_map)
            second_scores = _extract_category_scores(second_half, books_map)

            if not first_scores or not second_scores:
                return {'drift': False, 'similarity': 1.0, 'threshold': threshold, 'reason': ''}

            sim = _cosine_similarity(first_scores, second_scores)
            drift = sim < (1.0 - threshold)
            reason = self._build_reason(first_scores, second_scores) if drift else ''

            return {
                'drift': drift,
                'similarity': round(sim, 4),
                'threshold': threshold,
                'first_half_count': len(first_half),
                'second_half_count': len(second_half),
                'first_categories': sorted(first_scores.items(), key=lambda x: -x[1])[:5],
                'second_categories': sorted(second_scores.items(), key=lambda x: -x[1])[:5],
                'reason': reason,
            }
        except Exception:
            return {'drift': False, 'similarity': 1.0, 'threshold': threshold, 'reason': ''}

    def _build_reason(self, first_scores: Dict[str, float], second_scores: Dict[str, float]) -> str:
        first_top = sorted(first_scores.items(), key=lambda x: -x[1])[:3]
        second_top = sorted(second_scores.items(), key=lambda x: -x[1])[:3]
        if not first_top or not second_top:
            return ''
        new_set = {c for c, _ in second_top}
        old_set = {c for c, _ in first_top}
        new_interests = new_set - old_set
        faded_interests = old_set - new_set

        if new_interests and faded_interests:
            return (f"您最近偏好{''.join(new_interests)}小说，"
                    f"而之前更喜爱{''.join(faded_interests)}")
        if new_interests:
            return f"您最近开始关注{''.join(new_interests)}类书籍"
        if faded_interests:
            return f"您对{''.join(faded_interests)}类书籍的兴趣有所下降"
        return f"您的阅读偏好由{first_top[0][0]}转向{second_top[0][0]}"

    def get_drift_reason(self, user_id: int) -> str:
        try:
            result = self.detect_drift(user_id)
            return result.get('reason', '')
        except Exception:
            return ''

    def get_recent_trend(self, user_id: int, n: int = 5) -> List[Dict[str, Any]]:
        try:
            ratings = self._get_user_ratings(user_id)
            if not ratings:
                return []
            recent = sorted(ratings, key=lambda r: r.created_at or '', reverse=True)[:max(n * 3, 10)]

            book_ids = {r.book_id for r in recent}
            books_map = {b.id: b for b in db.session.query(Book).filter(Book.id.in_(book_ids)).all()}

            trend_scores: Dict[str, float] = defaultdict(float)
            trend_counts: Dict[str, int] = defaultdict(int)
            for r in recent:
                b = books_map.get(r.book_id)
                if not b or not b.category:
                    continue
                trend_scores[b.category] += r.rating
                trend_counts[b.category] += 1

            items = [
                {'category': c, 'avg_rating': round(trend_scores[c] / trend_counts[c], 2), 'count': trend_counts[c]}
                for c in trend_scores
            ]
            items.sort(key=lambda x: (-x['avg_rating'], -x['count']))
            return items[:n]
        except Exception:
            return []


interest_drift_detector = InterestDriftDetector()


# ---------------- 用户反馈 ----------------
_valid_feedback_types = {'dislike', 'skip', 'click', 'not_interested_category', 'not_interested_author'}

_feedback_store: Dict[int, List[Dict[str, Any]]] = {}
_feedback_lock = Lock()


def _empty_feedback(user_id: int) -> Dict[str, Any]:
    return {'user_id': user_id, 'items': [], 'count': 0}


class UserFeedbackService:
    """用户反馈服务 - 内存双层存储，单例"""

    _instance: Optional['UserFeedbackService'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def record_feedback(self, user_id: int, book_id: int, feedback_type: str, reason: str = '') -> bool:
        try:
            if feedback_type not in _valid_feedback_types:
                return False
            item = {
                'user_id': user_id,
                'book_id': book_id,
                'feedback_type': feedback_type,
                'reason': reason,
                'created_at': time.time(),
            }
            with _feedback_lock:
                _feedback_store.setdefault(user_id, []).append(item)
            return True
        except Exception:
            return False

    def get_feedback(self, user_id: int) -> Dict[str, Any]:
        try:
            with _feedback_lock:
                items = list(_feedback_store.get(user_id, []))
            items.sort(key=lambda x: x.get('created_at', 0), reverse=True)
            return {'user_id': user_id, 'items': items, 'count': len(items)}
        except Exception:
            return _empty_feedback(user_id)

    def get_disliked_book_ids(self, user_id: int) -> List[int]:
        try:
            with _feedback_lock:
                items = _feedback_store.get(user_id, [])
                return [i['book_id'] for i in items if i.get('feedback_type') == 'dislike']
        except Exception:
            return []

    def get_not_interested_categories(self, user_id: int) -> List[str]:
        try:
            categories = set()
            with _feedback_lock:
                items = list(_feedback_store.get(user_id, []))
            for item in items:
                if item.get('feedback_type') == 'not_interested_category' and item.get('reason'):
                    categories.add(item['reason'])
            if _HAS_DB:
                disliked_books = [i['book_id'] for i in items if i.get('feedback_type') in ('dislike', 'skip')]
                if disliked_books:
                    for b in db.session.query(Book).filter(Book.id.in_(disliked_books)).all():
                        if b.category:
                            categories.add(b.category)
            return list(categories)
        except Exception:
            return []

    def get_not_interested_authors(self, user_id: int) -> List[str]:
        try:
            authors = set()
            with _feedback_lock:
                items = list(_feedback_store.get(user_id, []))
            for item in items:
                if item.get('feedback_type') == 'not_interested_author' and item.get('reason'):
                    authors.add(item['reason'])
            return list(authors)
        except Exception:
            return []

    def clear_feedback(self, user_id: int) -> bool:
        try:
            with _feedback_lock:
                _feedback_store.pop(user_id, None)
            return True
        except Exception:
            return False


user_feedback_service = UserFeedbackService()
