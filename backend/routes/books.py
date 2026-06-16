from flask import Blueprint, request, jsonify
from extensions import db
from models import Book, Rating
from services.cache import cache_service, make_cache_key
from services.search_service import get_search_service  # T3 搜索服务
from sqlalchemy import func, or_, and_, text
import re

books_bp = Blueprint('books', __name__)


def _ok(data=None, message=None, status=200):
    resp = {'success': True}
    if data is not None:
        resp.update(data) if isinstance(data, dict) else resp.update({'data': data})
    if message:
        resp['message'] = message
    return jsonify(resp), status


def _err(message, status=400, details=None):
    resp = {'success': False, 'error': message}
    if details:
        resp['details'] = details
    return jsonify(resp), status


# ========== FULLTEXT 搜索支持 ==========
# 索引是否存在由 deployment 脚本提前创建，这里只做"存在性探测"
# 禁止在请求处理中执行 ALTER TABLE / DDL
_ft_available = None


def _is_ft_available():
    """探测 books.title + books.author 的 FULLTEXT 索引是否存在。
    只做只读的 SELECT 探测，失败时静默降级到 LIKE '%keyword%'
    """
    global _ft_available
    if _ft_available is not None:
        return _ft_available

    try:
        db.session.execute(
            text("SELECT 1 FROM books WHERE MATCH(title, author) AGAINST(:q IN BOOLEAN MODE) LIMIT 1"),
            {'q': 'test'}
        ).fetchone()
        _ft_available = True
    except Exception:
        # 索引不存在时静默降级 — 不要在请求线程里做 DDL
        _ft_available = False
    return _ft_available


def _search_fulltext(keyword, limit=100):
    """使用 MATCH AGAINST 做全文搜索，失败时降级到 LIKE"""
    if not keyword or not _is_ft_available():
        return None

    try:
        words = [w for w in re.split(r'\s+', keyword.strip()) if w and len(w) > 0]
        if not words:
            return None

        ft_query = ' '.join(f'+{w}*' for w in words)
        result = db.session.execute(
            text("""
                SELECT id, MATCH(title, author) AGAINST(:q IN BOOLEAN MODE) as score
                FROM books
                WHERE MATCH(title, author) AGAINST(:q IN BOOLEAN MODE)
                ORDER BY score DESC
                LIMIT :lim
            """),
            {'q': ft_query, 'lim': limit}
        ).fetchall()

        book_ids = [row[0] for row in result]
        if book_ids:
            return book_ids
    except Exception:
        pass

    return None


# 热门搜索词
_hot_search_terms = [
    'Harry Potter', 'Lord of the Rings', 'Twilight', 'The Da Vinci Code',
    'To Kill a Mockingbird', 'Pride and Prejudice', 'The Great Gatsby',
    '1984', 'Animal Farm', 'Brave New World', 'The Catcher in the Rye'
]

# ========== 搜索历史持久化到 Redis ==========
_HISTORY_MAX = 20          # 每个用户最多保留 20 条
_HISTORY_MAX_TERM_LEN = 128  # 单个搜索词长度上限（超过截断）
_HISTORY_TTL = 60 * 60 * 24 * 7  # 7 天


def _history_key(user_id):
    return f'search_history:{user_id}'


def _get_history(user_id):
    try:
        raw = cache_service.get(_history_key(user_id))
        if isinstance(raw, list):
            return [h for h in raw if isinstance(h, str) and h.strip()]
        if isinstance(raw, str):
            import json
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [h for h in parsed if isinstance(h, str) and h.strip()]
        return []
    except Exception:
        return []


def _add_history(user_id, term):
    try:
        if not isinstance(term, str):
            return
        term = term.strip()
        if not term:
            return
        # 长度上限 + 过滤不可打印字符（避免注入/超大 payload）
        if len(term) > _HISTORY_MAX_TERM_LEN:
            term = term[:_HISTORY_MAX_TERM_LEN]
        term = ''.join(ch for ch in term if ch.isprintable())
        if not term:
            return

        history = _get_history(user_id)
        # 去重（大小写不敏感）
        history = [h for h in history if h.lower() != term.lower()]
        history.append(term)
        # 保留最近 N 条
        history = history[-_HISTORY_MAX:]
        cache_service.set(_history_key(user_id), history, ttl=_HISTORY_TTL)
    except Exception:
        pass


def _clear_history(user_id):
    try:
        cache_service.delete(_history_key(user_id))
    except Exception:
        pass


@books_bp.route('/', methods=['GET'])
def get_books():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    min_rating = request.args.get('min_rating', type=float)
    max_rating = request.args.get('max_rating', type=float)
    author = request.args.get('author', '')
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)
    sort = request.args.get('sort', 'default')
    fuzzy = request.args.get('fuzzy', 'true', type=lambda x: x.lower() == 'true')

    # 参数边界保护
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20
    if per_page > 100:
        per_page = 100

    # 生成唯一缓存键，包含所有筛选条件
    params = [str(page), str(per_page), sort, 'fuzzy' if fuzzy else 'exact']
    for v in [search, category, author]:
        params.append(v or '')
    for v in [min_rating, max_rating, year_from, year_to]:
        params.append('' if v is None else str(v))
    cache_key = make_cache_key('books', *params)

    cached_result = cache_service.get(cache_key)
    if cached_result and isinstance(cached_result, dict):
        resp = jsonify({'from_cache': True, **cached_result})
        resp.headers['X-Cache'] = 'HIT'
        return resp, 200

    query = Book.query
    search_method = 'like'

    # 搜索：T3 接入 services/search_service.py
    if search:
        # 1) 先走 search_service（Meilisearch / FULLTEXT 混合）
        try:
            svc = get_search_service()
            result = svc.search(search, limit=500, fuzzy=1 if fuzzy else 0)
            if result and result['items']:
                search_ids = [item['id'] for item in result['items'] if item.get('id')]
                if search_ids:
                    query = query.filter(Book.id.in_(search_ids))
                    search_method = result.get('method', 'search_service')
        except Exception:
            search_ids = None

        # 2) 如 search_service 无结果，则 fallback 到本地 FULLTEXT / LIKE
        if search_method == 'like':
            like_pattern = f'%{search}%'
            if not fuzzy:
                query = query.filter(or_(Book.title == search, Book.author == search))
            else:
                ft_ids = _search_fulltext(search, limit=500)
                if ft_ids:
                    query = query.filter(Book.id.in_(ft_ids))
                    search_method = 'fulltext'
                else:
                    query = query.filter(or_(Book.title.ilike(like_pattern),
                                             Book.author.ilike(like_pattern)))

    if category:
        query = query.filter(Book.category == category)

    if min_rating is not None or max_rating is not None:
        avg_rating_subquery = db.session.query(
            Rating.book_id,
            func.avg(Rating.rating).label('avg_rating')
        ).group_by(Rating.book_id).subquery()

        query = query.outerjoin(avg_rating_subquery, Book.id == avg_rating_subquery.c.book_id)

        if min_rating is not None:
            query = query.filter(or_(avg_rating_subquery.c.avg_rating >= min_rating,
                                     and_(avg_rating_subquery.c.avg_rating == None, min_rating == 0)))
        if max_rating is not None:
            query = query.filter(or_(avg_rating_subquery.c.avg_rating <= max_rating,
                                     and_(avg_rating_subquery.c.avg_rating == None, max_rating == 10)))

    if author:
        query = query.filter(Book.author.ilike(f'%{author}%'))

    if year_from is not None:
        query = query.filter(Book.year >= year_from)
    if year_to is not None:
        query = query.filter(Book.year <= year_to)

    # 排序
    if sort == 'rating_desc':
        query = query.outerjoin(Rating, Book.id == Rating.book_id).group_by(Book.id).order_by(
            func.coalesce(func.avg(Rating.rating), 0).desc())
    elif sort == 'rating_asc':
        query = query.outerjoin(Rating, Book.id == Rating.book_id).group_by(Book.id).order_by(
            func.coalesce(func.avg(Rating.rating), 0).asc())
    elif sort == 'reviews_desc':
        query = query.outerjoin(Rating, Book.id == Rating.book_id).group_by(Book.id).order_by(
            func.count(Rating.id).desc())
    elif sort == 'year_desc':
        query = query.order_by(Book.year.desc().nullslast())
    elif sort == 'year_asc':
        query = query.order_by(Book.year.asc().nullslast())
    elif sort == 'popularity':
        query = query.outerjoin(Rating, Book.id == Rating.book_id).group_by(Book.id).order_by(
            func.count(Rating.id).desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # N+1 优化：一次性查询所有书的评分统计
    book_ids = [b.id for b in pagination.items]
    rating_map = {}
    if book_ids:
        stats_rows = db.session.query(
            Rating.book_id,
            func.avg(Rating.rating).label('avg_rating'),
            func.count(Rating.id).label('rating_count'),
        ).filter(Rating.book_id.in_(book_ids)).group_by(Rating.book_id).all()
        for r in stats_rows:
            rating_map[r.book_id] = {
                'avg_rating': round(float(r.avg_rating), 1) if r.avg_rating else None,
                'rating_count': r.rating_count or 0,
            }

    books_data = []
    for book in pagination.items:
        book_dict = book.to_dict()
        stats = rating_map.get(book.id, {'avg_rating': None, 'rating_count': 0})
        book_dict['avg_rating'] = stats['avg_rating']
        book_dict['rating_count'] = stats['rating_count']
        books_data.append(book_dict)

    response_data = {
        'books': books_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'search_method': search_method,
        'search_term': search if search else None,
    }

    try:
        cache_service.set(cache_key, response_data, ttl=180)
    except Exception:
        pass

    resp = jsonify(response_data)
    resp.headers['X-Cache'] = 'MISS'
    resp.headers['X-Search-Method'] = search_method
    return resp, 200


@books_bp.route('/<int:book_id>', methods=['GET'])
def get_book(book_id):
    book = Book.query.get(book_id)
    if not book:
        return _err('书籍不存在', status=404)
    book_data = book.to_dict()

    # JOIN 优化：用聚合 SQL 一次性拿到评分统计，避免先拉全部评分再求和
    stats = db.session.query(
        func.count(Rating.id).label('rating_count'),
        func.avg(Rating.rating).label('avg_rating'),
    ).filter(Rating.book_id == book_id).first()

    rating_count = int(stats.rating_count or 0)
    avg_rating = round(float(stats.avg_rating), 1) if stats.avg_rating else None

    # 评分分布（一次 GROUP BY，代替循环每条记录）
    distribution_rows = db.session.query(
        Rating.rating, func.count(Rating.id)
    ).filter(Rating.book_id == book_id).group_by(Rating.rating).all()

    distribution = {str(i): 0 for i in range(1, 11)}
    most_common_rating = None
    max_count = 0
    for r, cnt in distribution_rows:
        key = str(int(r)) if isinstance(r, (int, float)) else str(r)
        if key in distribution:
            distribution[key] = int(cnt or 0)
        if cnt and cnt > max_count:
            max_count = cnt
            most_common_rating = int(r) if isinstance(r, (int, float)) else r

    # 用户对该本书的评分（只查 1 条，不是所有）
    user_id = request.args.get('user_id', type=int)
    user_rating = None
    if user_id:
        ur = db.session.query(Rating.rating).filter(
            Rating.user_id == user_id, Rating.book_id == book_id
        ).first()
        if ur and ur[0] is not None:
            user_rating = ur[0]

    book_data['community_rating'] = {
        'avg_rating': avg_rating,
        'rating_count': rating_count,
        'distribution': distribution,
        'most_common_rating': most_common_rating,
        'user_rating': user_rating,
    }

    return _ok({'book': book_data})


@books_bp.route('/<int:book_id>/similar', methods=['GET'])
def get_similar_books(book_id):
    book = Book.query.get(book_id)
    if not book:
        return _err('书籍不存在', status=404)

    limit = request.args.get('limit', 6, type=int)
    if limit < 1 or limit > 30:
        limit = 6

    # ====== T4：优先走 embedding 向量检索 ======
    try:
        from services.embedding_service import get_embedding_service
        embedding_svc = get_embedding_service()
        if embedding_svc and getattr(embedding_svc, 'model', None) is not None:
            # 取一批候选（全量 + 缓存）用于相似度计算；规模大时可以用 FAISS
            candidate_books = Book.query.filter(Book.id != book_id).limit(200).all()
            if candidate_books:
                sims = embedding_svc.find_similar_books(book, candidate_books,
                                                         top_k=limit, threshold=0.3)
                if sims:
                    out = []
                    for sim, b in sims:
                        d = b.to_dict()
                        d['similarity'] = round(float(sim), 3)
                        d['match_by'] = 'embedding'
                        out.append(d)
                    return _ok({'similar_books': out, 'method': 'embedding'})
    except Exception:
        pass

    # ====== Fallback：分类/作者匹配（原逻辑） ======
    conditions = []
    if book.author:
        conditions.append(Book.author == book.author)
    if book.category:
        conditions.append(Book.category == book.category)

    if conditions:
        similar = Book.query.filter(
            db.and_(Book.id != book_id, db.or_(*conditions))
        ).limit(limit).all()
    else:
        similar = Book.query.filter(Book.id != book_id).limit(limit).all()

    out = []
    for b in similar:
        d = b.to_dict()
        d['match_by'] = 'category_or_author'
        out.append(d)
    return _ok({'similar_books': out, 'method': 'fallback'})


# ============ 搜索优化相关 API ============

@books_bp.route('/suggestions', methods=['GET'])
def get_search_suggestions():
    query = request.args.get('q', '').strip()
    if len(query) < 1:
        return _ok({'suggestions': []})

    limit = request.args.get('limit', 10, type=int)
    if limit < 1 or limit > 50:
        limit = 10

    cache_key = make_cache_key('suggestions', query.lower(), limit)
    cached = cache_service.get(cache_key)
    if cached:
        resp = jsonify({'suggestions': cached, 'from_cache': True, 'success': True})
        resp.headers['X-Cache'] = 'HIT'
        return resp, 200

    ft_ids = _search_fulltext(query, limit=100)
    suggestions = []

    if ft_ids:
        matched = db.session.query(Book.title, Book.author).filter(Book.id.in_(ft_ids)).limit(limit).all()
        for b in matched:
            if b[0]:
                suggestions.append({'type': 'title', 'text': b[0]})
            if b[1]:
                suggestions.append({'type': 'author', 'text': b[1]})
    else:
        like_pattern = f'%{query}%'
        titles = db.session.query(Book.title).filter(Book.title.ilike(like_pattern)).limit(limit).all()
        for t in titles:
            suggestions.append({'type': 'title', 'text': t[0]})

        authors = db.session.query(Book.author).filter(Book.author.ilike(like_pattern), Book.author.isnot(None)
                                                       ).distinct().limit(limit).all()
        for a in authors:
            if a[0]:
                suggestions.append({'type': 'author', 'text': a[0]})

    # 去重
    seen = set()
    unique_suggestions = []
    for s in suggestions:
        key = s['text'].lower()
        if key not in seen:
            seen.add(key)
            unique_suggestions.append(s)
            if len(unique_suggestions) >= limit:
                break

    try:
        cache_service.set(cache_key, unique_suggestions, ttl=600)
    except Exception:
        pass

    resp = jsonify({'suggestions': unique_suggestions, 'success': True})
    resp.headers['X-Cache'] = 'MISS'
    return resp, 200


@books_bp.route('/hot-search', methods=['GET'])
def get_hot_search():
    limit = request.args.get('limit', 10, type=int)
    if limit < 1 or limit > 50:
        limit = 10
    cache_key = make_cache_key('hot_search', limit)
    cached = cache_service.get(cache_key)
    if cached:
        return _ok({'hot_search': cached, 'from_cache': True})

    hot_terms = _hot_search_terms[:limit]
    try:
        cache_service.set(cache_key, hot_terms, ttl=3600)
    except Exception:
        pass
    return _ok({'hot_search': hot_terms})


@books_bp.route('/search-history', methods=['GET', 'POST', 'DELETE'])
def manage_search_history():
    user_id = request.args.get('user_id', type=int)
    if not user_id and request.method != 'GET':
        try:
            data = request.get_json(silent=True) or {}
            raw_uid = data.get('user_id')
            user_id = int(raw_uid) if raw_uid is not None else None
        except (TypeError, ValueError):
            user_id = None

    if not user_id:
        return _err('需要用户ID')

    if request.method == 'GET':
        history = _get_history(user_id)
        return _ok({'history': history})

    elif request.method == 'POST':
        data = request.get_json(silent=True) or {}
        search_term = data.get('term', '').strip()
        if search_term:
            _add_history(user_id, search_term)
        return _ok()

    elif request.method == 'DELETE':
        _clear_history(user_id)
        return _ok()


@books_bp.route('/hot', methods=['GET'])
def get_hot_books():
    limit = request.args.get('limit', 20, type=int)
    if limit < 1 or limit > 100:
        limit = 20

    cache_key = make_cache_key('hot_books', limit)
    cached_result = cache_service.get(cache_key)
    if cached_result and isinstance(cached_result, dict):
        cached_result['from_cache'] = True
        return jsonify(cached_result), 200

    hot_books = db.session.query(
        Book.id, Book.title, Book.author, Book.category, Book.year,
        func.count(Rating.id).label('rating_count'),
        func.avg(Rating.rating).label('avg_rating')
    ).join(Rating).group_by(Book.id).order_by(
        func.count(Rating.id).desc(), func.avg(Rating.rating).desc()
    ).limit(limit).all()

    books_data = []
    for b in hot_books:
        books_data.append({
            'id': b.id,
            'title': b.title,
            'author': b.author,
            'category': b.category,
            'year': b.year,
            'rating_count': b.rating_count,
            'avg_rating': round(float(b.avg_rating), 1) if b.avg_rating else None,
        })

    response_data = {'hot_books': books_data, 'total': len(books_data)}

    try:
        cache_service.set(cache_key, response_data, ttl=3600)
    except Exception:
        pass

    return jsonify(response_data), 200


@books_bp.route('/categories', methods=['GET'])
def get_categories():
    cache_key = make_cache_key('book_categories')
    cached = cache_service.get(cache_key)
    if cached:
        return _ok({'categories': cached, 'from_cache': True})

    categories = db.session.query(Book.category).filter(
        Book.category.isnot(None), Book.category != ''
    ).distinct().order_by(Book.category).all()

    result = [c[0] for c in categories if c[0]]
    try:
        cache_service.set(cache_key, result, ttl=3600)
    except Exception:
        pass
    return _ok({'categories': result})


@books_bp.route('/filters', methods=['GET'])
def get_filter_options():
    cache_key = make_cache_key('book_filters')
    cached = cache_service.get(cache_key)
    if cached:
        return _ok({'from_cache': True, **cached})

    year_range = db.session.query(
        func.min(Book.year).label('min_year'),
        func.max(Book.year).label('max_year')
    ).first()

    categories = db.session.query(Book.category).filter(
        Book.category.isnot(None), Book.category != ''
    ).distinct().order_by(Book.category).all()

    rating_ranges = [
        {'label': '8-10分', 'min': 8, 'max': 10},
        {'label': '6-8分', 'min': 6, 'max': 8},
        {'label': '4-6分', 'min': 4, 'max': 6},
        {'label': '4分以下', 'min': 0, 'max': 4},
    ]

    result = {
        'year_range': {
            'min': year_range.min_year or 1900,
            'max': year_range.max_year or 2024,
        },
        'rating_ranges': rating_ranges,
        'categories': [c[0] for c in categories if c[0]],
    }

    try:
        cache_service.set(cache_key, result, ttl=3600)
    except Exception:
        pass
    return _ok(result)


@books_bp.route('/count', methods=['GET'])
def get_filtered_count():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    min_rating = request.args.get('min_rating', type=float)
    max_rating = request.args.get('max_rating', type=float)
    author = request.args.get('author', '')
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)

    query = Book.query

    if search:
        like_pattern = f'%{search}%'
        query = query.filter(or_(Book.title.ilike(like_pattern), Book.author.ilike(like_pattern)))

    if category:
        query = query.filter(Book.category == category)

    if author:
        query = query.filter(Book.author.ilike(f'%{author}%'))

    if year_from is not None:
        query = query.filter(Book.year >= year_from)
    if year_to is not None:
        query = query.filter(Book.year <= year_to)

    if min_rating is not None or max_rating is not None:
        avg_rating_subquery = db.session.query(
            Rating.book_id, func.avg(Rating.rating).label('avg_rating')
        ).group_by(Rating.book_id).subquery()

        query = query.outerjoin(avg_rating_subquery, Book.id == avg_rating_subquery.c.book_id)

        if min_rating is not None:
            query = query.filter(or_(avg_rating_subquery.c.avg_rating >= min_rating,
                                     and_(avg_rating_subquery.c.avg_rating == None, min_rating == 0)))
        if max_rating is not None:
            query = query.filter(or_(avg_rating_subquery.c.avg_rating <= max_rating,
                                     and_(avg_rating_subquery.c.avg_rating == None, max_rating == 10)))

    count = query.count()
    return _ok({'count': count})



# ========== 2023 upgrade: semantic search + knowledge graph ==========
@books_bp.route('/semantic-search', methods=['GET'])
def semantic_search():
    """向量语义搜索：输入自然语言，返回语义相似的图书
    q: keyword (required); n: default 10; min_similarity: default 0.1; hybrid: bool
    """
    from services.embedding_service import get_embedding

    q = request.args.get('q', '').strip()
    n = request.args.get('n', 10, type=int)
    min_sim = request.args.get('min_similarity', 0.1, type=float)
    use_hybrid = request.args.get('hybrid', 'false').lower() == 'true'
    if n < 1 or n > 50:
        n = 10
    min_sim = max(0.0, min(1.0, min_sim))
    if not q:
        return _err('need query keyword q', status=400)

    try:
        embedding_svc = get_embedding()
    except Exception as e:
        return _err('embedding service unavailable: ' + str(e), status=503)
    if embedding_svc is None:
        return _err('embedding service not initialized', status=503)

    semantic_results = []
    if hasattr(embedding_svc, 'search_by_text'):
        try:
            semantic_results = embedding_svc.search_by_text(q, top_k=n * 2, threshold=min_sim)
        except Exception:
            semantic_results = []
    elif hasattr(embedding_svc, 'find_similar_books_by_text'):
        try:
            semantic_results = embedding_svc.find_similar_books_by_text(q, top_k=n * 2, threshold=min_sim)
        except Exception:
            semantic_results = []

    if use_hybrid:
        try:
            ft_rows = Book.query.filter(
                or_(Book.title.contains(q), Book.author.contains(q))
            ).limit(n).all()
            seen_ids = set()
            for r in semantic_results:
                if isinstance(r, dict):
                    seen_ids.add(int(r.get('book_id')))
                else:
                    try:
                        seen_ids.add(int(r[0]))
                    except Exception:
                        pass
            for book in ft_rows:
                if book.id in seen_ids:
                    continue
                semantic_results.append({'book_id': book.id, 'similarity': 0.3, 'method': 'hybrid_text'})
        except Exception:
            pass

    book_ids = []
    sim_map = {}
    method_map = {}
    for item in semantic_results:
        if isinstance(item, dict):
            bid = item.get('book_id')
            sim = float(item.get('similarity', 0.0) or 0.0)
            method = item.get('method', 'semantic')
        else:
            try:
                bid = item[0]
                sim = float(item[1]) if len(item) > 1 else 0.0
                method = 'semantic'
            except Exception:
                bid = item
                sim = 0.5
                method = 'semantic'
        if bid is None:
            continue
        try:
            bid_int = int(bid)
        except Exception:
            continue
        book_ids.append(bid_int)
        sim_map[bid_int] = sim
        method_map[bid_int] = method
        if len(book_ids) >= n:
            break

    books_objs = {b.id: b for b in Book.query.filter(Book.id.in_(book_ids)).all()}
    recommendations = []
    for bid in book_ids:
        if bid not in books_objs:
            continue
        book = books_objs[bid]
        book_dict = book.to_dict()
        book_dict['similarity'] = round(float(sim_map.get(bid, 0.0)), 4)
        book_dict['method'] = method_map.get(bid, 'semantic')
        recommendations.append(book_dict)

    return _ok({
        'query': q, 'method': 'semantic' + ('+hybrid' if use_hybrid else ''),
        'min_similarity': min_sim, 'count': len(recommendations), 'books': recommendations,
    })


@books_bp.route('/<int:book_id>/knowledge', methods=['GET'])
def book_knowledge(book_id):
    """知识图谱视图：相似图书、同作者、同分类"""
    book = Book.query.get(book_id)
    if not book:
        return _err('book not found', status=404)
    try:
        from services.embedding_service import get_embedding
        embedding_svc = get_embedding()
    except Exception:
        embedding_svc = None

    similar_books = []
    if embedding_svc is not None and hasattr(embedding_svc, 'find_similar_books'):
        try:
            sims = embedding_svc.find_similar_books(book, top_k=5, threshold=0.3)
            s_ids = []
            for s in sims:
                if isinstance(s, dict):
                    s_ids.append((s.get('book_id'), float(s.get('similarity', 0.0) or 0.0)))
                else:
                    try:
                        s_ids.append((s[0], float(s[1])))
                    except Exception:
                        continue
            valid_ids = [x[0] for x in s_ids if x[0]]
            bid_objs = {b.id: b for b in Book.query.filter(Book.id.in_(valid_ids)).all()}
            for bid, sim in s_ids:
                if bid in bid_objs:
                    similar_books.append({'book': bid_objs[bid].to_dict(), 'similarity': round(float(sim), 4)})
        except Exception:
            similar_books = []

    author_books = []
    author_name = getattr(book, 'author', None)
    if author_name:
        author_rows = Book.query.filter(Book.author == author_name).filter(Book.id != book.id).limit(5).all()
        author_books = [b.to_dict() for b in author_rows]

    category_books = []
    cat_name = getattr(book, 'category', None)
    if cat_name:
        try:
            from sqlalchemy import func as _func
            cat_rows = Book.query.filter(Book.category == cat_name).filter(Book.id != book.id).order_by(_func.random()).limit(5).all()
            category_books = [b.to_dict() for b in cat_rows]
        except Exception:
            cat_rows = Book.query.filter(Book.category == cat_name).filter(Book.id != book.id).limit(5).all()
            category_books = [b.to_dict() for b in cat_rows]

    return _ok({
        'book': book.to_dict(), 'similar_books': similar_books,
        'same_author': author_books, 'same_category': category_books,
    })


# ========== 2025 升级：embeddings 后台构建 / 状态 API ==========

@books_bp.route('/embeddings/build', methods=['GET', 'POST'])
def build_embeddings():
    """触发后台构建 FAISS 索引（limit 通过参数控制，默认 5000）
    Query Params:
        limit: int (默认 5000)，0 表示全量
    Returns:
        {'success': true, 'status': {嵌入服务状态对象}
    """
    try:
        limit = request.args.get('limit', 5000, type=int)
    except Exception:
        limit = 5000

    try:
        from services.embedding_service import get_embedding_service
        svc = get_embedding_service()
    except Exception as e:
        return _err('embedding service unavailable: ' + str(e), status=503)

    if svc is None:
        return _err('embedding service not initialized', status=503)

    # 如正在构建，直接返回进度
    try:
        if getattr(svc, '_building', False):
            return _ok({
                'status': 'building',
                'message': getattr(svc, '_build_message', 'in progress'),
                'details': svc.status if hasattr(svc, 'status') else None,
            })

        # 确保模型已加载
        if getattr(svc, 'model', None) is None:
            try:
                svc._load_model()
            except Exception:
                pass

        # 后台线程：从 DB 构建并保存
        def _bg_build():
            try:
                svc._building = True
                svc._build_message = f'building from db (limit={limit})'
                n = svc.build_index_from_db(limit=limit if limit and limit > 0 else None)
                if n > 0:
                    svc._build_message = f'saving index'
                    try:
                        svc.save_index()
                    except Exception:
                        pass
                    svc._build_message = f'built {n} books'
                else:
                    svc._build_message = 'no books / model missing'
            except Exception as e:
                svc._build_message = f'error: {e}'
            finally:
                svc._building = False

        import threading
        t = threading.Thread(target=_bg_build, name='embeddings-build', daemon=True)
        t.start()
        return _ok({
            'status': 'started',
            'message': 'background build started',
            'limit': limit,
            'details': svc.status if hasattr(svc, 'status') else None,
        })
    except Exception as e:
        return _err('build failed: ' + str(e), status=500)


@books_bp.route('/embeddings/status', methods=['GET'])
def get_embeddings_status():
    """返回嵌入服务与 FAISS 索引的运行状态"""
    try:
        from services.embedding_service import get_embedding_service
        svc = get_embedding_service()
    except Exception as e:
        return _err('embedding service unavailable: ' + str(e), status=503)

    if svc is None:
        return _ok({
            'model_loaded': False,
            'index_ready': False,
            'index_size': 0,
            'n_books': 0,
            'building': False,
            'build_message': 'service not initialized',
        })

    try:
        return _ok({
            'status': svc.status if hasattr(svc, 'status') else {
                'model_loaded': svc.model is not None,
                'index_ready': getattr(svc, 'faiss_ready', False),
                'index_size': getattr(svc, 'index_size', 0),
                'n_books': 0,
                'building': False,
                'build_message': '',
            },
        })
    except Exception as e:
        return _err('status check failed: ' + str(e), status=500)
