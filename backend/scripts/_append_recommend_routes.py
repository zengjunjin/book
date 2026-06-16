# -*- coding: utf-8 -*-
"""将新推荐路由代码追加到 routes/recommend.py 文件末尾"""
import sys

APPENDIX = r"""

# ===== 2023 upgrade: Content-Based + Item-Based CF + MMR + Cold-Start + Explain =====
from services.content_filter import (
    get_content_recommender, get_item_based_cf, get_explainability,
)


def _mmr_rerank(pool, lambda_param, n, get_book_fn=None, embedding_svc=None):
    try:
        if not pool or n <= 0:
            return []
        if lambda_param is None:
            lambda_param = 0.5
        lambda_param = max(0.0, min(1.0, float(lambda_param)))

        scores = [float(v.get('score', 0.0)) for v in pool.values()]
        s_max = max(scores) if scores else 1.0
        s_min = min(scores) if scores else 0.0
        s_range = (s_max - s_min) if (s_max - s_min) > 1e-6 else 1.0

        norm_pool = {}
        for bid, meta in pool.items():
            s = float(meta.get('score', 0.0))
            norm_score = (s - s_min) / s_range if s_range else 0.0
            norm_pool[bid] = {**meta, 'relevance': round(norm_score, 4)}

        candidates = sorted(
            norm_pool.items(), key=lambda kv: kv[1]['relevance'], reverse=True,
        )[: max(n * 3, n * 2)]
        candidate_ids = [bid for bid, _ in candidates]
        sim_cache = {}

        if embedding_svc is not None and hasattr(embedding_svc, 'find_similar_books'):
            try:
                bid_to_book = {}
                if get_book_fn is not None:
                    for bid in candidate_ids:
                        b = get_book_fn(bid)
                        if b is not None:
                            bid_to_book[bid] = b
                book_list = list(bid_to_book.values())
                if book_list:
                    for bid, book in bid_to_book.items():
                        try:
                            sims = embedding_svc.find_similar_books(
                                book, candidates=book_list, top_k=len(book_list), threshold=0.0,
                            )
                            for item in sims:
                                if isinstance(item, dict):
                                    other_id = item.get('book_id')
                                    sim = float(item.get('similarity', 0.0) or 0.0)
                                else:
                                    other_id, sim = item[0], float(item[1])
                                if other_id is None or other_id == bid:
                                    continue
                                key = (min(bid, other_id), max(bid, other_id))
                                if sim > sim_cache.get(key, -1.0):
                                    sim_cache[key] = round(sim, 4)
                        except Exception:
                            continue
            except Exception:
                sim_cache = {}

        category_map = {}
        author_map = {}
        if get_book_fn is not None:
            for bid in candidate_ids:
                try:
                    b = get_book_fn(bid)
                    if b is not None:
                        category_map[bid] = getattr(b, 'category', None) or ''
                        author_map[bid] = getattr(b, 'author', None) or ''
                except Exception:
                    continue

        def _pair_sim(i, j):
            key = (min(i, j), max(i, j))
            if key in sim_cache:
                return float(sim_cache[key])
            ci, cj = category_map.get(i, ''), category_map.get(j, '')
            ai, aj = author_map.get(i, ''), author_map.get(j, '')
            score = 0.0
            if ci and cj and ci == cj:
                score += 0.6
            if ai and aj and ai == aj:
                score += 0.3
            return score

        selected = []
        selected_ids = []
        remaining = list(candidate_ids)

        if remaining:
            first = max(remaining, key=lambda x: norm_pool[x]['relevance'])
            selected.append((first, norm_pool[first]['relevance'], norm_pool[first]))
            selected_ids.append(first)
            remaining.remove(first)

        while remaining and len(selected) < n:
            best_mmr = -1e9
            best_bid = None
            best_meta = None
            for bid in remaining:
                rel = norm_pool[bid]['relevance']
                if selected_ids:
                    max_sim = max((_pair_sim(bid, s) for s in selected_ids), default=0.0)
                else:
                    max_sim = 0.0
                mmr = lambda_param * rel - (1 - lambda_param) * max_sim
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_bid = bid
                    best_meta = norm_pool[bid]
            if best_bid is None:
                break
            selected.append((best_bid, round(float(best_mmr), 4), best_meta))
            selected_ids.append(best_bid)
            remaining.remove(best_bid)

        return selected
    except Exception:
        try:
            fallback = sorted(pool.items(), key=lambda kv: float(kv[1].get('score', 0.0)), reverse=True)[:n]
            return [(bid, float(meta.get('score', 0.0)), meta) for bid, meta in fallback]
        except Exception:
            return []


@recommend_bp.route('/content', methods=['GET'])
def content_based_recommend():
    user_id = request.args.get('user_id', type=int)
    n = request.args.get('n', 10, type=int)
    if n < 1 or n > 50:
        n = 10
    if not user_id:
        return _rec_err('need user_id', status=400)

    def _gen():
        recommender = get_content_recommender()
        explainer = get_explainability()
        user_profile = recommender.get_user_profile(user_id)

        raw_recs = recommender.recommend(user_id, n=n, seed=42)
        if not raw_recs:
            return {
                'recommendations': [], 'algorithm': 'content_based',
                'user_id': user_id, 'count': 0,
                'profile_size': user_profile.get('size', 0),
                'note': 'insufficient ratings for content-based recommendations',
            }

        book_ids = [r['book_id'] for r in raw_recs]
        book_objs = {b.id: b for b in Book.query.filter(Book.id.in_(book_ids)).all()}

        recommendations = []
        for rec in raw_recs:
            book = book_objs.get(rec['book_id'])
            if not book:
                continue
            book_dict = book.to_dict()
            book_dict['content_score'] = round(float(rec.get('score', 0.0)), 4)
            try:
                reason = explainer.generate_reason(book, sources=['content_based'], user_profile=user_profile)
            except Exception:
                reason = 'based on your reading preferences'
            book_dict['reason'] = reason
            recommendations.append(book_dict)

        return {
            'recommendations': recommendations, 'algorithm': 'content_based',
            'user_id': user_id, 'count': len(recommendations),
            'profile_size': user_profile.get('size', 0),
            'top_categories': list(user_profile.get('categories', {}).keys())[:5],
            'top_authors': list(user_profile.get('authors', {}).keys())[:5],
        }

    try:
        data, cache_hit = _rec_with_cache(['content', user_id, n], _gen, ttl_key='hybrid')
    except Exception as e:
        return _rec_err(f'content-based recommend failed: {e}', status=500)
    return _rec_ok(data, cache_hit=cache_hit), 200


@recommend_bp.route('/item-based', methods=['GET'])
def item_based_recommend():
    user_id = request.args.get('user_id', type=int)
    n = request.args.get('n', 10, type=int)
    k = request.args.get('k', 20, type=int)
    if n < 1 or n > 50:
        n = 10
    if not user_id:
        return _rec_err('need user_id', status=400)

    def _gen():
        ib = get_item_based_cf()
        raw_recs = ib.recommend(user_id, n=n, k=k, seed=42)
        if not raw_recs:
            return {
                'recommendations': [], 'algorithm': 'item_based_cf',
                'user_id': user_id, 'count': 0, 'note': 'insufficient ratings',
            }

        book_ids = [r['book_id'] for r in raw_recs]
        book_objs = {b.id: b for b in Book.query.filter(Book.id.in_(book_ids)).all()}

        recommendations = []
        for rec in raw_recs:
            book = book_objs.get(rec['book_id'])
            if not book:
                continue
            book_dict = book.to_dict()
            book_dict['predicted_rating'] = rec.get('predicted_rating')
            book_dict['method'] = rec.get('method', 'item_based_cf')
            book_dict['reason'] = 'users who highly rated similar books also liked this one'
            recommendations.append(book_dict)

        return {
            'recommendations': recommendations, 'algorithm': 'item_based_cf',
            'user_id': user_id, 'count': len(recommendations), 'neighbor_users': k,
        }

    try:
        data, cache_hit = _rec_with_cache(['item_based', user_id, n, k], _gen, ttl_key='cf')
    except Exception as e:
        return _rec_err(f'Item-Based CF recommend failed: {e}', status=500)
    return _rec_ok(data, cache_hit=cache_hit), 200


@recommend_bp.route('/mmr', methods=['GET'])
def mmr_recommend():
    user_id = request.args.get('user_id', type=int)
    n = request.args.get('n', 10, type=int)
    lambda_param = request.args.get('lambda_param', 0.5, type=float)
    if n < 1 or n > 50:
        n = 10
    lambda_param = max(0.0, min(1.0, float(lambda_param)))
    if not user_id:
        return _rec_err('need user_id', status=400)

    def _gen():
        from extensions import db
        from sqlalchemy import func
        from models import Rating

        pool = {}
        channel_hits = {'cf': 0, 'svd': 0, 'semantic': 0, 'content': 0}
        pool_size = max(n * 3, 20)

        try:
            cf_engine = get_cf_engine()
            cf_recs = cf_engine.recommend(user_id, n_recommendations=pool_size)
            for rank, rec in enumerate(cf_recs):
                bid = rec.get('book_id')
                if not bid:
                    continue
                rel_score = max(0.0, 1.0 - rank * 0.02)
                pool.setdefault(bid, {'score': 0.0, 'sources': set(), 'cf_score': 0.0, 'svd_score': 0.0, 'semantic_score': 0.0, 'content_score': 0.0})
                pool[bid]['score'] += rel_score
                pool[bid]['cf_score'] = round(rel_score, 4)
                pool[bid]['sources'].add('cf')
                channel_hits['cf'] += 1
        except Exception:
            pass

        try:
            svd_engine = get_svd_engine()
            svd_recs = svd_engine.recommend(user_id, n_recommendations=pool_size)
            for rank, rec in enumerate(svd_recs):
                bid = rec.get('book_id')
                if not bid:
                    continue
                rel_score = max(0.0, 0.9 - rank * 0.02)
                pool.setdefault(bid, {'score': 0.0, 'sources': set(), 'cf_score': 0.0, 'svd_score': 0.0, 'semantic_score': 0.0, 'content_score': 0.0})
                pool[bid]['score'] += rel_score
                pool[bid]['svd_score'] = round(rel_score, 4)
                pool[bid]['sources'].add('svd')
                channel_hits['svd'] += 1
        except Exception:
            pass

        try:
            embedding_svc = get_embedding()
            if embedding_svc is not None and hasattr(embedding_svc, 'recommend_books'):
                sem_recs = embedding_svc.recommend_books(user_id, top_k=pool_size)
                for rank, rec in enumerate(sem_recs[:pool_size]):
                    if isinstance(rec, dict):
                        bid = rec.get('book_id')
                    else:
                        bid = rec
                    if not bid:
                        continue
                    rel_score = max(0.0, 0.8 - rank * 0.02)
                    pool.setdefault(bid, {'score': 0.0, 'sources': set(), 'cf_score': 0.0, 'svd_score': 0.0, 'semantic_score': 0.0, 'content_score': 0.0})
                    pool[bid]['score'] += rel_score
                    pool[bid]['semantic_score'] = round(rel_score, 4)
                    pool[bid]['sources'].add('semantic')
                    channel_hits['semantic'] += 1
        except Exception:
            pass

        try:
            content_engine = get_content_recommender()
            content_recs = content_engine.recommend(user_id, n=pool_size, seed=42)
            for rank, rec in enumerate(content_recs):
                bid = rec.get('book_id')
                if not bid:
                    continue
                rel_score = float(rec.get('score', 0.0))
                pool.setdefault(bid, {'score': 0.0, 'sources': set(), 'cf_score': 0.0, 'svd_score': 0.0, 'semantic_score': 0.0, 'content_score': 0.0})
                pool[bid]['score'] += rel_score
                pool[bid]['content_score'] = round(rel_score, 4)
                pool[bid]['sources'].add('content')
                channel_hits['content'] += 1
        except Exception:
            pass

        try:
            rated_rows = db.session.query(Rating.book_id).filter(Rating.user_id == user_id).all()
            rated_ids = {r[0] for r in rated_rows}
            for bid in list(pool.keys()):
                if bid in rated_ids:
                    del pool[bid]
        except Exception:
            pass

        if len(pool) < n:
            try:
                hot_rows = db.session.query(
                    Rating.book_id, func.count(Rating.id).label('cnt'), func.avg(Rating.rating).label('avg'),
                ).group_by(Rating.book_id).order_by(func.count(Rating.id).desc()).limit(n * 2).all()
                for rank, r in enumerate(hot_rows):
                    if r.book_id in pool:
                        continue
                    rel_score = 0.3 * max(0.0, 1.0 - rank * 0.02)
                    pool.setdefault(r.book_id, {'score': 0.0, 'sources': set(), 'cf_score': 0.0, 'svd_score': 0.0, 'semantic_score': 0.0, 'content_score': 0.0})
                    pool[r.book_id]['score'] += rel_score
                    pool[r.book_id]['sources'].add('hot')
            except Exception:
                pass

        if not pool:
            return {
                'recommendations': [], 'algorithm': 'mmr', 'user_id': user_id, 'count': 0,
                'lambda_param': lambda_param, 'channel_hits': channel_hits, 'note': 'no candidates',
            }

        _all_bids = list(pool.keys())
        _book_map = {b.id: b for b in Book.query.filter(Book.id.in_(_all_bids)).all()}
        def _get_book(bid):
            return _book_map.get(bid)

        embedding_svc = None
        try:
            embedding_svc = get_embedding()
        except Exception:
            embedding_svc = None

        selected = _mmr_rerank(pool=pool, lambda_param=lambda_param, n=n, get_book_fn=_get_book, embedding_svc=embedding_svc)

        recommendations = []
        for bid, mmr_score, meta in selected:
            book = _book_map.get(bid)
            if not book:
                continue
            book_dict = book.to_dict()
            book_dict['mmr_score'] = round(float(mmr_score), 4)
            book_dict['relevance'] = meta.get('relevance')
            book_dict['blend_score'] = round(float(meta.get('score', 0.0)), 4)
            book_dict['cf_score'] = meta.get('cf_score')
            book_dict['svd_score'] = meta.get('svd_score')
            book_dict['semantic_score'] = meta.get('semantic_score')
            book_dict['content_score'] = meta.get('content_score')
            book_dict['sources'] = [s for s in meta.get('sources', [])]
            recommendations.append(book_dict)

        return {
            'recommendations': recommendations, 'algorithm': 'mmr', 'user_id': user_id,
            'count': len(recommendations), 'lambda_param': lambda_param,
            'channel_hits': channel_hits, 'candidate_pool_size': len(pool),
        }

    try:
        data, cache_hit = _rec_with_cache(['mmr', user_id, n, lambda_param], _gen, ttl_key='hybrid')
    except Exception as e:
        return _rec_err(f'MMR recommend failed: {e}', status=500)
    return _rec_ok(data, cache_hit=cache_hit), 200


@recommend_bp.route('/cold-start', methods=['GET'])
def cold_start_recommend():
    user_id = request.args.get('user_id', type=int)
    n = request.args.get('n', 10, type=int)
    explore_ratio = request.args.get('explore_ratio', 0.2, type=float)
    if n < 1 or n > 50:
        n = 10
    explore_ratio = max(0.0, min(0.5, float(explore_ratio)))

    rating_count = 0
    if user_id:
        try:
            from extensions import db
            from models import Rating
            rating_count = db.session.query(Rating.id).filter(Rating.user_id == user_id).count()
        except Exception:
            rating_count = 0

    def _gen():
        from extensions import db
        from sqlalchemy import func
        from models import Rating

        try:
            stats = db.session.query(
                Rating.book_id, func.count(Rating.id).label('cnt'), func.avg(Rating.rating).label('avg'),
            ).group_by(Rating.book_id).subquery()
            rows = db.session.query(Book, stats.c.cnt, stats.c.avg).outerjoin(stats, Book.id == stats.c.book_id).all()
        except Exception:
            rows = []

        buckets = {}
        all_hot = []
        for row in rows:
            try:
                book, cnt, avg = row
            except Exception:
                continue
            if book is None:
                continue
            cnt = int(cnt or 0)
            avg = float(avg or 0.0)
            if cnt == 0 and avg == 0.0:
                continue
            popularity = (min(cnt, 500) / 500.0) * 0.5 + (avg / 10.0) * 0.5
            cat = getattr(book, 'category', None) or '未分类'
            buckets.setdefault(cat, []).append((book, cnt, avg, popularity))
            all_hot.append((book, cnt, avg, popularity))

        diverse_picks = []
        seen_ids = set()
        sorted_buckets = sorted(buckets.items(), key=lambda kv: sum(x[3] for x in kv[1]) / max(len(kv[1]), 1), reverse=True)
        per_cat = max(1, (n - int(n * explore_ratio)) // max(len(sorted_buckets), 1))
        for cat, items in sorted_buckets:
            items_sorted = sorted(items, key=lambda x: x[3], reverse=True)
            picked = 0
            for book, cnt, avg, pop in items_sorted:
                if book.id in seen_ids:
                    continue
                diverse_picks.append((book, cnt, avg, pop, cat))
                seen_ids.add(book.id)
                picked += 1
                if picked >= per_cat:
                    break

        if len(diverse_picks) < n - int(n * explore_ratio):
            all_sorted = sorted(all_hot, key=lambda x: x[3], reverse=True)
            for book, cnt, avg, pop in all_sorted:
                if book.id in seen_ids:
                    continue
                diverse_picks.append((book, cnt, avg, pop, 'hot'))
                seen_ids.add(book.id)
                if len(diverse_picks) >= n - int(n * explore_ratio):
                    break

        explore_picks = []
        try:
            explore_target = int(n * explore_ratio)
            if explore_target > 0:
                niche_rows = sorted(
                    [(b, c, a, p) for b, c, a, p in all_hot if 1 <= (c or 0) <= 30 and (a or 0) >= 7.5],
                    key=lambda x: x[2], reverse=True,
                )[: max(explore_target * 5, 20)]
                _random.shuffle(niche_rows)
                for book, cnt, avg, pop in niche_rows:
                    if book.id in seen_ids:
                        continue
                    explore_picks.append((book, cnt, avg, pop))
                    seen_ids.add(book.id)
                    if len(explore_picks) >= explore_target:
                        break
        except Exception:
            pass

        recommendations = []
        categories_covered = set()
        for book, cnt, avg, pop, cat in diverse_picks:
            book_dict = book.to_dict()
            book_dict['cold_start_reason'] = f'{cat} category hot pick' if cat != 'hot' else 'site-wide popular'
            book_dict['rating_count'] = int(cnt or 0)
            book_dict['avg_rating'] = round(float(avg or 0.0), 2)
            book_dict['popularity'] = round(float(pop), 4)
            book_dict['tier'] = 'popular'
            categories_covered.add(cat)
            recommendations.append(book_dict)

        for book, cnt, avg, pop in explore_picks:
            book_dict = book.to_dict()
            book_dict['cold_start_reason'] = 'niche high-rated discovery'
            book_dict['rating_count'] = int(cnt or 0)
            book_dict['avg_rating'] = round(float(avg or 0.0), 2)
            book_dict['popularity'] = round(float(pop), 4)
            book_dict['tier'] = 'explore'
            recommendations.append(book_dict)

        return {
            'recommendations': recommendations[:n], 'algorithm': 'cold_start',
            'user_id': user_id, 'count': min(len(recommendations), n),
            'user_rating_count': rating_count, 'is_new_user': rating_count < 5,
            'categories_covered': len(categories_covered), 'explore_ratio': explore_ratio,
            'note': 'cold-start: popular + diverse categories + niche high-rated discoveries',
        }

    try:
        data, cache_hit = _rec_with_cache(['cold_start', user_id, n, explore_ratio], _gen, ttl_key='hybrid')
    except Exception as e:
        return _rec_err(f'cold-start recommend failed: {e}', status=500)
    return _rec_ok(data, cache_hit=cache_hit), 200


@recommend_bp.route('/explain', methods=['GET'])
def recommend_explain():
    user_id = request.args.get('user_id', type=int)
    book_id = request.args.get('book_id', type=int)
    if not user_id or not book_id:
        return _rec_err('need user_id and book_id', status=400)

    try:
        book = Book.query.get(book_id)
        if not book:
            return _rec_err(f'book {book_id} not found', status=404)

        content_score = 0.0
        user_profile = {'size': 0, 'authors': {}, 'categories': {}, 'liked_book_ids': []}
        try:
            content_engine = get_content_recommender()
            user_profile = content_engine.get_user_profile(user_id)
            content_score = content_engine.score_book_by_profile(book, user_profile)
        except Exception:
            content_score = 0.0

        cf_predicted = None
        try:
            cf_engine = get_cf_engine()
            if hasattr(cf_engine, 'predict_rating'):
                cf_predicted = cf_engine.predict_rating(user_id, book_id)
        except Exception:
            cf_predicted = None

        if cf_predicted is None:
            try:
                ibcf = get_item_based_cf()
                if hasattr(ibcf, 'recommend'):
                    recs = ibcf.recommend(user_id, n=50, seed=42)
                    for r in recs:
                        if r.get('book_id') == book_id:
                            cf_predicted = r.get('predicted_rating')
                            break
            except Exception:
                cf_predicted = None

        semantic_max = None
        semantic_match_book = None
        try:
            embedding_svc = get_embedding()
            if embedding_svc is not None and hasattr(embedding_svc, 'find_similar_books'):
                liked_ids = user_profile.get('liked_book_ids', [])
                if liked_ids:
                    liked_books = Book.query.filter(Book.id.in_(liked_ids)).all()
                    if liked_books:
                        sims = embedding_svc.find_similar_books(book, candidates=liked_books, top_k=5, threshold=0.0)
                        if sims:
                            top = sims[0]
                            if isinstance(top, dict):
                                semantic_max = float(top.get('similarity', 0.0) or 0.0)
                                match_id = top.get('book_id')
                                if match_id:
                                    semantic_match_book = Book.query.get(match_id)
                            else:
                                semantic_max = float(top[1])
                                semantic_match_book = Book.query.get(top[0])
        except Exception:
            semantic_max = None

        try:
            explainer = get_explainability()
            parts = []
            if content_score and content_score > 0.05:
                parts.append('content_based')
            if cf_predicted is not None and cf_predicted >= 7:
                parts.append('cf')
            if semantic_max is not None and semantic_max >= 0.4:
                parts.append('semantic')
            if not parts:
                parts.append('hybrid')

            if semantic_match_book is not None and semantic_max is not None:
                combined_reason = explainer.generate_reason(book, sources=parts, user_profile=user_profile, similar_book=semantic_match_book, similarity=semantic_max)
            else:
                combined_reason = explainer.generate_reason(book, sources=parts, user_profile=user_profile)
        except Exception:
            combined_reason = 'recommended by combining multiple strategies'

        explanation = {
            'book_id': book_id, 'book_title': getattr(book, 'title', None),
            'book_author': getattr(book, 'author', None), 'book_category': getattr(book, 'category', None),
            'user_id': user_id,
            'content_score': round(float(content_score or 0.0), 4),
            'cf_predicted_rating': round(float(cf_predicted), 2) if cf_predicted is not None else None,
            'semantic_similarity': round(float(semantic_max), 4) if semantic_max is not None else None,
            'semantic_most_similar_book': getattr(semantic_match_book, 'title', None) if semantic_match_book is not None else None,
            'user_profile_size': user_profile.get('size', 0),
            'user_top_categories': list(user_profile.get('categories', {}).keys())[:3],
            'user_top_authors': list(user_profile.get('authors', {}).keys())[:3],
            'reason': combined_reason, 'signals': parts,
        }
        return _rec_ok({'explanation': explanation, 'success': True}), 200
    except Exception as e:
        return _rec_err(f'explain failed: {e}', status=500)
"""

target = r'c:\Users\15116\Desktop\book\backend\routes\recommend.py'
with open(target, 'a', encoding='utf-8') as f:
    f.write(APPENDIX)
print(f'Content appended to {target}')

# Quick syntax check
import subprocess
result = subprocess.run([sys.executable, '-m', 'py_compile', target], capture_output=True, text=True)
if result.returncode == 0:
    print('Syntax: OK')
else:
    print('Syntax errors:')
    print(result.stderr)
