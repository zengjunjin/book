# -*- coding: utf-8 -*-
"""给 books.py 追加语义搜索接口，给 auth.py 追加用户画像接口"""
import sys
import subprocess

books_appendix = r"""


# ========== 语义搜索接口（2023升级：向量相似度搜索） ==========
@books_bp.route('/semantic-search', methods=['GET'])
def semantic_search():
    """向量语义搜索：输入自然语言，返回语义相似的图书
    参数：
      q: 查询关键词（必填）
      n: 返回条数，默认10
      min_similarity: 最小相似度阈值 0.0-1.0，默认0.1
      use_hybrid: 是否混合全文搜索，默认 false
    """
    from services.embedding_service import get_embedding

    q = request.args.get('q', '').strip()
    n = request.args.get('n', 10, type=int)
    min_sim = request.args.get('min_similarity', 0.1, type=float)
    use_hybrid = request.args.get('hybrid', 'false').lower() == 'true'
    if n < 1:
        n = 10
    if n > 50:
        n = 50
    min_sim = max(0.0, min(1.0, min_sim))
    if not q:
        return _err('请提供查询关键词 q', status=400)

    try:
        embedding_svc = get_embedding()
    except Exception as e:
        return _err(f'向量服务不可用: {e}', status=503)

    if embedding_svc is None:
        return _err('向量服务未初始化', status=503)

    # 1. 向量语义搜索
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

    # 2. 混合模式：叠加全文搜索
    if use_hybrid:
        try:
            ft_rows = Book.query.filter(
                or_(Book.title.contains(q), Book.author.contains(q))
            ).limit(n).all()
            seen_ids = {
                (r.get('book_id') if isinstance(r, dict) else r[0])
                for r in semantic_results
            }
            for book in ft_rows:
                if book.id in seen_ids:
                    continue
                semantic_results.append({'book_id': book.id, 'similarity': 0.3, 'method': 'hybrid_text'})
        except Exception:
            pass

    # 3. 格式化
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
        book_ids.append(int(bid))
        sim_map[int(bid)] = sim
        method_map[int(bid)] = method
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
        'min_similarity': min_sim, 'count': len(recommendations),
        'books': recommendations,
    })


# ========== 图书知识图谱视图（2023升级：相关书/作者/主题） ==========
@books_bp.route('/<int:book_id>/knowledge', methods=['GET'])
def book_knowledge(book_id):
    """返回某本书的知识图谱视图：相似图书、同作者、同分类"""
    book = Book.query.get(book_id)
    if not book:
        return _err('图书不存在', status=404)

    try:
        embedding_svc = get_embedding()
    except Exception:
        embedding_svc = None

    # 相似图书（向量）
    similar_books = []
    if embedding_svc is not None and hasattr(embedding_svc, 'find_similar_books'):
        try:
            sims = embedding_svc.find_similar_books(book, top_k=5, threshold=0.3)
            similar_ids = []
            for s in sims:
                if isinstance(s, dict):
                    similar_ids.append((s.get('book_id'), float(s.get('similarity', 0.0) or 0.0)))
                else:
                    similar_ids.append((s[0], float(s[1])))
            bid_objs = {b.id: b for b in Book.query.filter(Book.id.in_([x[0] for x in similar_ids if x[0]])).all()}
            for bid, sim in similar_ids:
                if bid in bid_objs:
                    b = bid_objs[bid]
                    similar_books.append({'book': b.to_dict(), 'similarity': round(float(sim), 4)})
        except Exception:
            similar_books = []

    # 同作者图书
    author_books = []
    author_name = getattr(book, 'author', None)
    if author_name:
        author_rows = Book.query.filter(Book.author == author_name).filter(Book.id != book.id).limit(5).all()
        author_books = [b.to_dict() for b in author_rows]

    # 同分类图书
    category_books = []
    cat_name = getattr(book, 'category', None)
    if cat_name:
        from sqlalchemy import func as _func
        cat_rows = Book.query.filter(Book.category == cat_name).filter(Book.id != book.id).order_by(_func.random()).limit(5).all()
        category_books = [b.to_dict() for b in cat_rows]

    return _ok({
        'book': book.to_dict(), 'similar_books': similar_books,
        'same_author': author_books, 'same_category': category_books,
    })
"""

auth_appendix = r"""


# ========== 用户画像接口（2023升级：个性化推荐可视化） ==========
@auth_bp.route('/profile', methods=['GET'])
@auth_bp.route('/profile/<int:profile_user_id>', methods=['GET'])
def user_profile(profile_user_id=None):
    """用户画像接口：返回用户的分类偏好、作者偏好、评分分布、兴趣漂移状态
    - GET /api/auth/profile 查看当前用户画像
    - GET /api/auth/profile/{user_id} 查看指定用户画像
    """
    from services.user_profile import get_user_profile_service as _get_up
    from services.content_filter import get_content_recommender
    from models import Rating

    # 用户鉴权
    current_uid = _extract_user_from_token()
    target_uid = profile_user_id or request.args.get('user_id', type=int) or current_uid
    if not target_uid:
        return _err('需要登录或提供 user_id', status=401)
    if target_uid != current_uid:
        # 非自己，限制返回字段；若有管理员角色可开放
        pass

    user = User.query.get(target_uid)
    if not user:
        return _err('用户不存在', status=404)

    # 1. 内容过滤推荐引擎获取的用户画像
    categories = {}
    authors = {}
    keywords = {}
    profile_size = 0
    try:
        content_engine = get_content_recommender()
        cp = content_engine.get_user_profile(target_uid)
        categories = cp.get('categories', {})
        authors = cp.get('authors', {})
        keywords = cp.get('keywords', {})
        profile_size = cp.get('size', 0)
    except Exception:
        categories = {}
        authors = {}
        keywords = {}
        profile_size = 0

    # 2. 用户画像服务的兴趣漂移检测
    drift_status = {'detected': False, 'magnitude': 0.0, 'recent_rating_count': 0}
    drift_events = []
    try:
        up = _get_up()
        if hasattr(up, 'detect_drift'):
            drift_status = up.detect_drift(target_uid, recent_days=30) or drift_status
        if hasattr(up, 'get_recent_events'):
            drift_events_raw = up.get_recent_events(target_uid, limit=5) or []
            drift_events = list(drift_events_raw)
    except Exception:
        pass

    # 3. 评分基本统计
    total_ratings = 0
    avg_rating = 0.0
    rating_distribution = {}
    try:
        from extensions import db
        from sqlalchemy import func
        total_ratings = db.session.query(func.count(Rating.id)).filter(Rating.user_id == target_uid).scalar() or 0
        avg_rating = db.session.query(func.avg(Rating.rating)).filter(Rating.user_id == target_uid).scalar() or 0.0
        rating_rows = db.session.query(
            Rating.rating, func.count(Rating.id)
        ).filter(Rating.user_id == target_uid).group_by(Rating.rating).all()
        rating_distribution = {str(int(r)): int(c) for r, c in rating_rows}
    except Exception:
        total_ratings = profile_size
        avg_rating = 0.0
        rating_distribution = {}

    # 4. 最常阅读分类 Top5
    top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
    top_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)[:5]
    top_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:10]

    profile = {
        'user_id': target_uid,
        'username': getattr(user, 'username', None),
        'location': getattr(user, 'location', None),
        'age': getattr(user, 'age', None),
        'total_ratings': int(total_ratings or profile_size or 0),
        'avg_rating': round(float(avg_rating or 0.0), 2),
        'rating_distribution': rating_distribution,
        'top_categories': [{'name': c, 'score': round(float(s), 4)} for c, s in top_categories],
        'top_authors': [{'name': a, 'score': round(float(s), 4)} for a, s in top_authors],
        'top_keywords': [{'keyword': k, 'score': round(float(s), 4)} for k, s in top_keywords],
        'interest_drift': drift_status,
        'recent_drift_events': drift_events[:5],
    }
    return _ok({'profile': profile})


@auth_bp.route('/profile/reset', methods=['POST'])
def reset_user_profile():
    """重置用户画像（清除兴趣漂移检测，保留评分数据）"""
    user_id = _extract_user_from_token()
    if not user_id:
        uid = request.args.get('user_id', type=int)
        if not uid:
            return _err('需要登录或提供 user_id', status=401)
        user_id = uid
    try:
        from services.user_profile import get_user_profile_service
        up = get_user_profile_service()
        if hasattr(up, 'reset_profile'):
            up.reset_profile(user_id)
        return _ok(message='用户画像已重置')
    except Exception as e:
        return _err(f'重置失败: {e}', status=500)
"""

files = {
    r'c:\Users\15116\Desktop\book\backend\routes\books.py': books_appendix,
    r'c:\Users\15116\Desktop\book\backend\routes\auth.py': auth_appendix,
}

for path, appendix in files.items():
    with open(path, 'a', encoding='utf-8') as f:
        f.write(appendix)
    print(f'[OK] Appended to {path}')
    r = subprocess.run([sys.executable, '-m', 'py_compile', path], capture_output=True, text=True)
    if r.returncode == 0:
        print(f'  Syntax: OK')
    else:
        print(f'  Syntax ERR: {r.stderr}')

print('All done.')
