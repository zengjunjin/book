"""内容过滤推荐服务 - Content-Based + Item-Based CF + 可解释性理由"""
from typing import List, Dict, Any, Optional
from threading import Lock
from collections import Counter
import math
import random as _random

try:
    from extensions import db
    from models import Book, Rating
except Exception:
    db = None
    Book = None
    Rating = None


# ===================== Content-Based 推荐 =====================

class ContentBasedRecommender:
    """基于内容的推荐引擎 - 单例"""

    _instance: Optional['ContentBasedRecommender'] = None
    _lock = Lock()

    AUTHOR_WEIGHT = 0.45
    CATEGORY_WEIGHT = 0.40
    YEAR_WEIGHT = 0.15
    MIN_RATING = 7
    MAX_CANDIDATES = 3000

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def get_user_profile(self, user_id) -> Dict[str, Any]:
        try:
            if Book is None or Rating is None or user_id is None:
                return self._empty_profile()

            liked_books = (
                db.session.query(Book)
                .join(Rating, Rating.book_id == Book.id)
                .filter(Rating.user_id == user_id, Rating.rating >= self.MIN_RATING)
                .all()
            )

            if not liked_books:
                return self._empty_profile()

            author_counts = Counter()
            category_counts = Counter()
            year_list = []

            for b in liked_books:
                if b.author:
                    author_counts[b.author.strip()] += 1
                if b.category:
                    category_counts[b.category.strip()] += 1
                if b.year and 1800 <= int(b.year) <= 2100:
                    year_list.append(int(b.year))

            total_authors = sum(author_counts.values()) or 1
            total_categories = sum(category_counts.values()) or 1

            author_freq = {a: c / total_authors for a, c in author_counts.items()}
            category_freq = {cat: c / total_categories for cat, c in category_counts.items()}

            year_avg = sum(year_list) / len(year_list) if year_list else 2000
            year_std = math.sqrt(sum((y - year_avg) ** 2 for y in year_list) / len(year_list)) if len(year_list) > 1 else 5.0

            return {
                'authors': author_freq,
                'categories': category_freq,
                'year_avg': year_avg,
                'year_std': max(year_std, 1.0),
                'liked_book_ids': [b.id for b in liked_books],
                'liked_books': liked_books,
                'size': len(liked_books),
            }
        except Exception:
            return self._empty_profile()

    def score_book_by_profile(self, book, user_profile: Dict[str, Any]) -> float:
        try:
            if book is None or not user_profile or user_profile.get('size', 0) == 0:
                return 0.0

            score = 0.0

            if book.author:
                score += self.AUTHOR_WEIGHT * user_profile['authors'].get(book.author.strip(), 0.0)

            if book.category:
                score += self.CATEGORY_WEIGHT * user_profile['categories'].get(book.category.strip(), 0.0)

            if book.year:
                try:
                    y = int(book.year)
                    year_avg = user_profile['year_avg']
                    year_std = user_profile['year_std']
                    year_diff = abs(y - year_avg)
                    year_sim = math.exp(-(year_diff ** 2) / (2 * year_std ** 2))
                    score += self.YEAR_WEIGHT * year_sim
                except (ValueError, TypeError):
                    pass

            return round(float(score), 4)
        except Exception:
            return 0.0

    def recommend(self, user_id, n=10, exclude_rated=True, seed=None) -> List[Dict[str, Any]]:
        try:
            if Book is None:
                return []

            profile = self.get_user_profile(user_id)
            if profile['size'] == 0:
                return []

            if seed is not None:
                _random.seed(seed)

            rated_ids = set(profile['liked_book_ids']) if exclude_rated else set()

            candidate_categories = list(profile['categories'].keys())[:10]
            candidate_authors = list(profile['authors'].keys())[:10]

            base_query = Book.query.filter(Book.id.notin_(list(rated_ids))) if rated_ids else Book.query

            candidates = []
            if candidate_categories:
                cat_books = base_query.filter(Book.category.in_(candidate_categories)).limit(self.MAX_CANDIDATES // 2).all()
                candidates.extend(cat_books)
            if candidate_authors:
                seen = {b.id for b in candidates}
                auth_books = base_query.filter(Book.author.in_(candidate_authors)).limit(self.MAX_CANDIDATES // 2).all()
                for b in auth_books:
                    if b.id not in seen:
                        candidates.append(b)

            if len(candidates) < n * 3:
                seen = {b.id for b in candidates}
                extra = base_query.limit(self.MAX_CANDIDATES).all()
                for b in extra:
                    if b.id not in seen:
                        candidates.append(b)

            if not candidates:
                return []

            scored = []
            for book in candidates:
                s = self.score_book_by_profile(book, profile)
                if s > 0.01:
                    scored.append((s + _random.uniform(-0.05, 0.05), book))

            scored.sort(key=lambda x: x[0], reverse=True)

            pool = scored[:n * 3]
            _random.shuffle(pool)
            top = pool[:n]

            return [
                {
                    'book_id': book.id,
                    'score': round(float(s), 4),
                    'method': 'content_based',
                }
                for s, book in top
            ]
        except Exception:
            return []

    def recommend_by_book(self, book, n=10, seed=None) -> List[Dict[str, Any]]:
        try:
            if Book is None or book is None or not hasattr(book, 'id'):
                return []

            if seed is not None:
                _random.seed(seed)

            profile = {
                'authors': {book.author: 1.0} if book.author else {},
                'categories': {book.category: 1.0} if book.category else {},
                'year_avg': int(book.year) if book.year else 2000,
                'year_std': 5.0,
                'liked_book_ids': [book.id],
                'size': 1,
            }

            query = Book.query.filter(Book.id != book.id)
            filters = []
            if book.category:
                filters.append(Book.category == book.category)
            if book.author:
                filters.append(Book.author == book.author)
            if filters:
                from sqlalchemy import or_
                query = query.filter(or_(*filters))

            candidates = query.limit(self.MAX_CANDIDATES).all()

            if not candidates:
                return []

            scored = []
            for cand in candidates:
                s = self.score_book_by_profile(cand, profile)
                if s > 0.01:
                    scored.append((s + _random.uniform(-0.05, 0.05), cand))

            scored.sort(key=lambda x: x[0], reverse=True)
            pool = scored[:n * 3]
            _random.shuffle(pool)
            top = pool[:n]

            return [
                {
                    'book_id': b.id,
                    'score': round(float(s), 4),
                    'method': 'content_based_similar',
                }
                for s, b in top
            ]
        except Exception:
            return []

    def _empty_profile(self) -> Dict[str, Any]:
        return {
            'authors': {},
            'categories': {},
            'year_avg': 2000,
            'year_std': 5.0,
            'liked_book_ids': [],
            'liked_books': [],
            'size': 0,
        }


# ===================== Item-Based CF 推荐 =====================

class ItemBasedCF:
    """基于物品的协同过滤 - 单例"""

    _instance: Optional['ItemBasedCF'] = None
    _lock = Lock()
    MIN_COMMON = 2
    TOP_NEIGHBORS = 50

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def recommend(self, user_id, n=10, k=20, seed=None) -> List[Dict[str, Any]]:
        try:
            if Rating is None or Book is None or user_id is None:
                return []

            if seed is not None:
                _random.seed(seed)

            user_ratings = (
                db.session.query(Rating.book_id, Rating.rating)
                .filter(Rating.user_id == user_id)
                .all()
            )

            if not user_ratings or len(user_ratings) < 3:
                return []

            rated_map = {r.book_id: r.rating for r in user_ratings}
            rated_ids = set(rated_map.keys())
            high_rated = {bid: r for bid, r in rated_map.items() if r >= 7}

            if not high_rated:
                return []

            other_ratings = (
                db.session.query(Rating.user_id, Rating.book_id, Rating.rating)
                .filter(Rating.user_id != user_id, Rating.book_id.in_(list(rated_ids)))
                .all()
            )

            if not other_ratings:
                return []

            user_to_books: Dict[int, Dict[int, int]] = {}
            for uid, bid, r in other_ratings:
                if uid not in user_to_books:
                    user_to_books[uid] = {}
                user_to_books[uid][bid] = r

            similar_user_scores: Dict[int, float] = {}
            for uid, books_map in user_to_books.items():
                common = set(books_map.keys()) & rated_ids
                if len(common) < self.MIN_COMMON:
                    continue
                user_mean = sum(books_map.values()) / len(books_map)
                target_mean = sum(rated_map.values()) / len(rated_map)

                num = 0.0
                den_a = 0.0
                den_b = 0.0
                for bid in common:
                    a = rated_map[bid] - target_mean
                    b = books_map[bid] - user_mean
                    num += a * b
                    den_a += a * a
                    den_b += b * b

                if den_a > 0 and den_b > 0:
                    sim = num / math.sqrt(den_a * den_b)
                    confidence = min(1.0, len(common) / 10.0)
                    similar_user_scores[uid] = sim * confidence

            top_users = sorted(similar_user_scores.items(), key=lambda x: x[1], reverse=True)[:self.TOP_NEIGHBORS]
            if not top_users:
                return []

            candidate_scores: Dict[int, Dict[str, float]] = {}
            for uid, sim in top_users:
                if sim <= 0.01:
                    continue
                other_books = user_to_books.get(uid, {})
                for bid, r in other_books.items():
                    if bid in rated_ids:
                        continue
                    if bid not in candidate_scores:
                        candidate_scores[bid] = {'sum': 0.0, 'sim_sum': 0.0, 'count': 0}
                    candidate_scores[bid]['sum'] += r * sim
                    candidate_scores[bid]['sim_sum'] += abs(sim)
                    candidate_scores[bid]['count'] += 1

            if not candidate_scores:
                return []

            final_scores = []
            for bid, info in candidate_scores.items():
                if info['sim_sum'] <= 0 or info['count'] < 2:
                    continue
                pred = info['sum'] / info['sim_sum']
                pred = max(1.0, min(10.0, pred))
                final_scores.append((pred + _random.uniform(-1.0, 1.0), bid, pred))

            final_scores.sort(key=lambda x: x[0], reverse=True)
            pool = final_scores[:n * 3]
            _random.shuffle(pool)
            top = pool[:n]

            return [
                {
                    'book_id': bid,
                    'predicted_rating': round(float(pred), 3),
                    'method': 'item_based_cf',
                }
                for _, bid, pred in top
            ]
        except Exception:
            return []


# ===================== 可解释性理由生成 =====================

class Explainability:
    """推荐理由生成器 - 单例 / 纯规则实现"""

    _instance: Optional['Explainability'] = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def generate_reason(
        self,
        book: Any,
        sources: List[str],
        user_profile: Optional[Dict[str, Any]] = None,
        similar_book: Any = None,
        similarity: Optional[float] = None,
    ) -> str:
        try:
            if not sources:
                return '根据综合分析为您推荐'

            source = sources[0] if isinstance(sources, list) else str(sources)

            if source == 'content_based' or source == 'content':
                return self._content_based_reason(book, user_profile)

            if source == 'similar' or source == 'content_based_similar':
                return self.generate_similar_reason(book, similar_book, similarity)

            if source == 'cf' or source == 'item_based_cf' or source == 'user_based_cf':
                return '其他读过您评价较高书籍的用户也喜欢这本'

            if source == 'svd' or source == 'matrix_factorization':
                return '根据您的历史评分模式，这本书可能适合您'

            if source == 'semantic' or source == 'embedding':
                return self._semantic_reason(book, user_profile)

            if source == 'popular' or source == 'trending':
                return '这是当下热门书籍，广受读者好评'

            if source == 'hybrid' or source == 'mixed':
                return '综合多种推荐策略为您挑选'

            return '为您推荐'
        except Exception:
            return '为您推荐'

    def generate_similar_reason(self, book: Any, similar_book: Any, similarity: Optional[float]) -> str:
        try:
            if similar_book is None:
                return '与您喜欢的书籍风格相似'

            title = getattr(similar_book, 'title', None) or '您喜欢的书'

            match_parts = []
            if book and similar_book:
                b_cat = getattr(book, 'category', None)
                s_cat = getattr(similar_book, 'category', None)
                if b_cat and s_cat and b_cat == s_cat:
                    match_parts.append(f'同属 {b_cat} 分类')

                b_author = getattr(book, 'author', None)
                s_author = getattr(similar_book, 'author', None)
                if b_author and s_author and b_author == s_author:
                    match_parts.append(f'{b_author} 的作品')

                b_year = getattr(book, 'year', None)
                s_year = getattr(similar_book, 'year', None)
                if b_year and s_year and abs(int(b_year) - int(s_year)) <= 3:
                    match_parts.append('年代相近')

            if match_parts:
                reason = f'与《{title}》' + '、'.join(match_parts)
            else:
                reason = f'与《{title}》主题相似'

            if similarity is not None:
                try:
                    pct = round(float(similarity) * 100)
                    if 0 <= pct <= 100:
                        reason += f'（匹配度 {pct}%）'
                except (ValueError, TypeError):
                    pass

            return reason
        except Exception:
            return '与您喜欢的书籍风格相似'

    def _content_based_reason(self, book: Any, user_profile: Optional[Dict[str, Any]]) -> str:
        try:
            if book is None:
                return '根据您的阅读偏好为您推荐'

            book_author = getattr(book, 'author', None)
            book_category = getattr(book, 'category', None)

            if user_profile and user_profile.get('size', 0) > 0:
                if book_author and book_author in user_profile.get('authors', {}):
                    return f'您读过 {book_author} 的书，这本也是他的作品'

                if book_category and book_category in user_profile.get('categories', {}):
                    return f'您喜欢 {book_category} 类的书，这本也是同类'

                top_cat = self._top_key(user_profile.get('categories', {}))
                if top_cat and book_category:
                    return f'您偏好 {top_cat}，这本书属于 {book_category}'

                top_author = self._top_key(user_profile.get('authors', {}))
                if top_author:
                    return f'您常读 {top_author} 的作品，这本风格相近'

            if book_author:
                return f'来自 {book_author} 的作品'
            if book_category:
                return f'{book_category} 类精选书籍'

            return '根据您的阅读偏好为您推荐'
        except Exception:
            return '根据您的阅读偏好为您推荐'

    def _semantic_reason(self, book: Any, user_profile: Optional[Dict[str, Any]]) -> str:
        try:
            if user_profile and user_profile.get('liked_books'):
                books = user_profile['liked_books']
                if books:
                    recent = books[-1] if hasattr(books, '__getitem__') else None
                    title = getattr(recent, 'title', None) if recent else None
                    if title:
                        return f'与您最近读的《{title}》主题相似'

            if book is not None:
                cat = getattr(book, 'category', None)
                if cat:
                    return f'与 {cat} 类主题相近的书籍'

            return '与您阅读过的书籍主题相似'
        except Exception:
            return '与您阅读过的书籍主题相似'

    def _top_key(self, freq_map: Dict[str, float]) -> Optional[str]:
        if not freq_map:
            return None
        try:
            return max(freq_map.items(), key=lambda x: x[1])[0]
        except Exception:
            return None


def get_content_recommender() -> ContentBasedRecommender:
    return ContentBasedRecommender()


def get_item_based_cf() -> ItemBasedCF:
    return ItemBasedCF()


def get_explainability() -> Explainability:
    return Explainability()
