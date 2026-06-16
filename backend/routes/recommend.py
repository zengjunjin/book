from flask import Blueprint, request, jsonify
from models import Book
from services.cf_algorithm import CollaborativeFiltering
from services.svd_algorithm import SVDRecommendation
from services.embedding_service import get_embedding_service
from services.evaluator import Evaluator, get_ab_test_framework, get_drift_detector
from services.cache import cache_service, make_cache_key
import random
import time

# 推荐缓存TTL配置
_REC_TTL = {
    'cf': 600,         # 协同过滤：10分钟
    'svd': 600,        # SVD：10分钟
    'semantic': 900,   # 语义增强：15分钟（更重）
    'hybrid': 600,     # 混合：10分钟
    'compare': 1800,   # 对比：30分钟（较稳定）
}

recommend_bp = Blueprint('recommend', __name__)
_cf_engine = None
_svd_engine = None
_evaluator = None
_prewarm_done = False  # 标记是否已完成预热


def _rec_with_cache(key_parts, gen_func, ttl_key='cf'):
    """推荐统一缓存辅助函数
    返回: (response_data_dict, cache_hit_bool)
    """
    ttl = _REC_TTL.get(ttl_key, 600)
    refresh = request.args.get('refresh', 'false').lower() == 'true'

    cache_key = make_cache_key('recommend', *key_parts)

    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached, True

    # 生成结果
    result = gen_func()

    # 存入缓存（只缓存有推荐结果的响应）
    if isinstance(result, dict):
        cache_service.set(cache_key, result, ttl=ttl)

    return result, False


def _rec_response(data, cache_hit=False):
    """包装推荐响应"""
    resp_data = dict(data)
    resp_data['from_cache'] = cache_hit
    resp = jsonify(resp_data)
    resp.headers['X-Cache'] = 'HIT' if cache_hit else 'MISS'
    return resp


def get_cf_engine():
    global _cf_engine
    if _cf_engine is None:
        _cf_engine = CollaborativeFiltering()
    return _cf_engine


def get_svd_engine():
    global _svd_engine
    if _svd_engine is None:
        _svd_engine = SVDRecommendation()
    return _svd_engine


def get_evaluator():
    global _evaluator
    if _evaluator is None:
        _evaluator = Evaluator(cf_engine=get_cf_engine(), svd_engine=get_svd_engine())
    return _evaluator


def get_embedding():
    """获取语义Embedding服务"""
    return get_embedding_service()


def prewarm_recommend_engines(app=None, sample_user_ids=None, n_top_users=20, n_rec=5):
    """启动时预热推荐引擎。

    步骤:
    1. 构造 CollaborativeFiltering / SVDRecommendation（首次会加载评分矩阵）
    2. 对若干"活跃用户"执行一次推荐，写入缓存层
    3. 后台线程执行，不阻塞 Flask 启动

    参数:
        app: Flask app 实例（仅用于 logger）
        sample_user_ids: 预加载哪些用户 ID 列表；None 时自动取前 N 个有评分用户
        n_top_users: 自动取前多少活跃用户
        n_rec: 每个用户预计算多少推荐
    """
    global _prewarm_done
    if _prewarm_done:
        return

    import threading

    def _log(msg):
        try:
            if app is not None and hasattr(app, 'logger'):
                app.logger.info(msg)
                return
        except Exception:
            pass
        print(msg)

    def _warn(msg):
        try:
            if app is not None and hasattr(app, 'logger'):
                app.logger.warning(msg)
                return
        except Exception:
            pass
        print(msg)

    def _run():
        global _prewarm_done
        try:
            _log('[Prewarm] 开始预热推荐引擎...')
            t0 = time.time()

            # 使用应用上下文，使 current_app/db.session 可访问
            ctx = None
            try:
                if app is not None:
                    ctx = app.app_context()
                    ctx.push()
            except Exception:
                ctx = None

            # 1) 构造两个主引擎
            cf = get_cf_engine()
            _log('[Prewarm] CF 引擎已初始化 (%.1fs)' % (time.time() - t0))
            t1 = time.time()
            svd = get_svd_engine()
            _log('[Prewarm] SVD 引擎已初始化 (%.1fs)' % (time.time() - t1))

            # 2) 初始化评估器
            try:
                get_evaluator()
            except Exception:
                pass

            # 3) 预计算若干活跃用户的推荐（结果写入缓存）
            users_to_preload = []
            if sample_user_ids:
                users_to_preload = list(sample_user_ids)
            else:
                try:
                    from models import Rating
                    from extensions import db
                    from sqlalchemy import func
                    rows = db.session.query(
                        Rating.user_id, func.count(Rating.id).label('cnt')
                    ).group_by(Rating.user_id).order_by(func.count(Rating.id).desc()
                    ).limit(n_top_users).all()
                    users_to_preload = [r[0] for r in rows]
                except Exception as e:
                    _warn('[Prewarm] 用户列表获取失败，跳过预缓存: %s' % e)

            for uid in users_to_preload:
                try:
                    cf.user_based_recommend(uid, n_recommendations=n_rec, seed=42)
                    cache_service.set(
                        make_cache_key('recommend', 'cf', uid, n_rec),
                        {'recommendations': [], 'algorithm': '基于用户的协同过滤',
                         'user_id': uid, 'count': 0},
                        ttl=_REC_TTL.get('cf', 600))
                except Exception:
                    pass
            _log('[Prewarm] 已缓存 %d 个用户推荐，总耗时 %.1fs' % (len(users_to_preload), time.time() - t0))

            if ctx is not None:
                try:
                    ctx.pop()
                except Exception:
                    pass
        except Exception as e:
            _warn('[Prewarm] 预热失败: %s' % e)
        finally:
            _prewarm_done = True

    t = threading.Thread(target=_run, name='recommend-prewarm', daemon=True)
    t.start()
    return t


@recommend_bp.route('/debug', methods=['GET'])
def debug_random():
    """调试端点：查看 random 状态"""
    values = [random.random() for _ in range(5)]
    # 测试 CF 的局部 random
    cf = get_cf_engine()
    rec1 = cf.user_based_recommend(8, n_recommendations=5, seed=None)
    rec2 = cf.user_based_recommend(8, n_recommendations=5, seed=None)
    rec3 = cf.user_based_recommend(8, n_recommendations=5, seed=None)

    ids_1 = [r['book_id'] for r in rec1]
    ids_2 = [r['book_id'] for r in rec2]
    ids_3 = [r['book_id'] for r in rec3]

    return jsonify({
        'random_values': values,
        'cf_rec_1': ids_1,
        'cf_rec_2': ids_2,
        'cf_rec_3': ids_3,
        'all_same': ids_1 == ids_2 == ids_3
    }), 200


def _rec_ok(data=None, cache_hit=False, status=200):
    """包装推荐结果，返回统一 JSON 响应"""
    if data is None:
        data = {}
    resp_data = dict(data)
    resp_data['from_cache'] = cache_hit
    resp = jsonify(resp_data)
    resp.headers['X-Cache'] = 'HIT' if cache_hit else 'MISS'
    return resp, status


def _rec_err(message, status=400):
    return jsonify({'success': False, 'error': message}), status


@recommend_bp.route('/cf', methods=['GET'])
def cf_recommend():
    """基于用户的协同过滤推荐（统一缓存层）"""
    user_id = request.args.get('user_id', type=int)
    n = request.args.get('n', 10, type=int)
    if n < 1 or n > 50:
        n = 10

    if not user_id:
        return _rec_err('需要用户ID', status=400)

    def _gen():
        recommendations = get_cf_engine().user_based_recommend(
            user_id, n_recommendations=n, seed=42
        )
        result = []
        for rec in recommendations:
            book = Book.query.get(rec['book_id'])
            if book:
                book_dict = book.to_dict()
                book_dict['predicted_rating'] = rec['predicted_rating']
                result.append(book_dict)
        return {
            'recommendations': result,
            'algorithm': '基于用户的协同过滤',
            'user_id': user_id,
            'count': len(result)
        }

    data, cache_hit = _rec_with_cache(['cf', user_id, n], _gen, ttl_key='cf')
    return _rec_response(data, cache_hit=cache_hit), 200


@recommend_bp.route('/svd', methods=['GET'])
def svd_recommend():
    """SVD矩阵分解推荐（统一缓存层）"""
    user_id = request.args.get('user_id', type=int)
    n = request.args.get('n', 10, type=int)
    if n < 1 or n > 50:
        n = 10

    if not user_id:
        return _rec_err('需要用户ID', status=400)

    def _gen():
        recommendations = get_svd_engine().recommend(
            user_id, n_recommendations=n, seed=42
        )
        result = []
        for rec in recommendations:
            book = Book.query.get(rec['book_id'])
            if book:
                book_dict = book.to_dict()
                book_dict['predicted_rating'] = rec['predicted_rating']
                result.append(book_dict)
        return {
            'recommendations': result,
            'algorithm': 'SVD 矩阵分解',
            'user_id': user_id,
            'count': len(result)
        }

    data, cache_hit = _rec_with_cache(['svd', user_id, n], _gen, ttl_key='svd')
    return _rec_response(data, cache_hit=cache_hit), 200


@recommend_bp.route('/compare', methods=['GET'])
def compare_algorithms():
    """对比各推荐算法性能（带缓存）"""
    def _gen():
        return get_evaluator().compare_algorithms()

    data, cache_hit = _rec_with_cache(['compare'], _gen, ttl_key='compare')
    return _rec_response(data, cache_hit=cache_hit), 200


@recommend_bp.route('/semantic', methods=['GET'])
def semantic_recommend():
    """语义增强协同过滤推荐（统一缓存层）"""
    user_id = request.args.get('user_id', type=int)
    n = request.args.get('n', 10, type=int)
    semantic_weight = request.args.get('semantic_weight', 0.2, type=float)
    if n < 1 or n > 50:
        n = 10

    if not user_id:
        return _rec_err('需要用户ID', status=400)

    def _gen():
        embedding_svc = get_embedding()
        cf_engine = get_cf_engine()
        cf_engine.set_semantic_weight(semantic_weight)
        recommendations = cf_engine.semantic_enhanced_recommend(
            user_id, n_recommendations=n, k=30,
            embedding_service=embedding_svc, seed=42
        )
        result = []
        for rec in recommendations:
            book = Book.query.get(rec['book_id'])
            if book:
                book_dict = book.to_dict()
                book_dict['predicted_rating'] = rec['predicted_rating']
                book_dict['cf_score'] = rec.get('cf_score')
                book_dict['semantic_score'] = rec.get('semantic_score')
                result.append(book_dict)
        return {
            'recommendations': result,
            'algorithm': '语义增强协同过滤',
            'semantic_weight': semantic_weight,
            'user_id': user_id,
            'count': len(result)
        }

    data, cache_hit = _rec_with_cache(
        ['semantic', user_id, n, semantic_weight], _gen, ttl_key='semantic'
    )
    return _rec_response(data, cache_hit=cache_hit), 200


@recommend_bp.route('/hybrid', methods=['GET'])
def hybrid_recommend():
    """混合推荐（统一缓存层）"""
    user_id = request.args.get('user_id', type=int)
    n = request.args.get('n', 10, type=int)
    cf_weight = request.args.get('cf_weight', 0.3, type=float)
    svd_weight = request.args.get('svd_weight', 0.4, type=float)
    semantic_weight = request.args.get('semantic_weight', 0.3, type=float)
    if n < 1 or n > 50:
        n = 10

    if not user_id:
        return _rec_err('需要用户ID', status=400)

    def _gen():
        svd_engine = get_svd_engine()
        cf_engine = get_cf_engine()
        embedding_svc = get_embedding()

        svd_engine.set_weights(
            cf_weight=cf_weight, svd_weight=svd_weight,
            semantic_weight=semantic_weight
        )
        recommendations = svd_engine.hybrid_recommend(
            user_id, n_recommendations=n, seed=42,
            cf_engine=cf_engine, embedding_service=embedding_svc
        )
        result = []
        for rec in recommendations:
            book = Book.query.get(rec['book_id'])
            if book:
                book_dict = book.to_dict()
                book_dict['predicted_rating'] = rec['predicted_rating']
                book_dict['svd_score'] = rec.get('svd_score')
                book_dict['cf_score'] = rec.get('cf_score')
                book_dict['semantic_score'] = rec.get('semantic_score')
                book_dict['hybrid_score'] = rec.get('hybrid_score')
                result.append(book_dict)
        return {
            'recommendations': result,
            'algorithm': '混合推荐',
            'weights': {
                'cf': cf_weight,
                'svd': svd_weight,
                'semantic': semantic_weight
            },
            'user_id': user_id,
            'count': len(result)
        }

    data, cache_hit = _rec_with_cache(
        ['hybrid', user_id, n, cf_weight, svd_weight, semantic_weight],
        _gen, ttl_key='hybrid'
    )
    return _rec_response(data, cache_hit=cache_hit), 200


@recommend_bp.route('/ab/test/create', methods=['POST'])
def ab_create_experiment():
    """创建 A/B 测试实验"""
    data = request.get_json() or {}
    experiment_id = data.get('experiment_id', 'default_experiment')
    description = data.get('description', '')
    control_config = data.get('control_config', {'algorithm': 'cf'})
    treatment_config = data.get('treatment_config', {'algorithm': 'hybrid'})

    ab_framework = get_ab_test_framework()
    ab_framework.create_experiment(experiment_id, description,
                                   control_config, treatment_config)

    return jsonify({
        'success': True,
        'experiment_id': experiment_id,
        'message': '实验创建成功'
    }), 201


@recommend_bp.route('/ab/test/list', methods=['GET'])
def ab_list_experiments():
    """列出所有 A/B 测试实验"""
    ab_framework = get_ab_test_framework()
    experiments = ab_framework.list_experiments()
    return jsonify({'experiments': experiments}), 200


@recommend_bp.route('/ab/test/<experiment_id>/stats', methods=['GET'])
def ab_get_stats(experiment_id):
    """获取 A/B 测试统计信息"""
    ab_framework = get_ab_test_framework()
    stats = ab_framework.get_experiment_stats(experiment_id)
    if stats is None:
        return jsonify({'error': '实验不存在'}), 404
    return jsonify({'experiment_id': experiment_id, 'statistics': stats}), 200


@recommend_bp.route('/ab/interaction', methods=['POST'])
def ab_record_interaction():
    """记录 A/B 测试交互"""
    data = request.get_json() or {}
    experiment_id = data.get('experiment_id', 'recommendation_algorithm')
    user_id = data.get('user_id')
    book_id = data.get('book_id')
    action = data.get('action', 'click')
    rating = data.get('rating')

    if not user_id or not book_id:
        return jsonify({'error': '需要 user_id 和 book_id'}), 400

    ab_framework = get_ab_test_framework()
    variant = ab_framework.get_user_variant(user_id, experiment_id)
    ab_framework.record_interaction(experiment_id, user_id, book_id, action, rating)

    return jsonify({
        'success': True,
        'variant': variant,
        'experiment_id': experiment_id
    }), 200


@recommend_bp.route('/drift/status/<int:user_id>', methods=['GET'])
def drift_status(user_id):
    """获取用户兴趣 drift 状态"""
    detector = get_drift_detector()
    status = detector.get_user_drift_status(user_id)

    # 添加到 drift detector 的历史记录（如果还没有）
    cf_engine = get_cf_engine()
    if user_id in cf_engine.user_id_map:
        user_idx = cf_engine.user_id_map[user_id]
        row = cf_engine.rating_matrix.getrow(user_idx)
        for i in range(len(row.indices)):
            detector.add_rating(user_id, int(row.indices[i]), float(row.data[i]))

    return jsonify({
        'user_id': user_id,
        'drift_status': status
    }), 200


@recommend_bp.route('/drift/events', methods=['GET'])
def drift_events():
    """获取最近的 drift 事件"""
    detector = get_drift_detector()
    events = detector.get_all_drifts(limit=50)
    return jsonify({'drift_events': events, 'total': len(events)}), 200


@recommend_bp.route('/drift/add_rating', methods=['POST'])
def drift_add_rating():
    """添加评分并检测 drift"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    book_id = data.get('book_id')
    rating = data.get('rating')

    if not user_id or not book_id or rating is None:
        return jsonify({'error': '需要 user_id, book_id 和 rating'}), 400

    detector = get_drift_detector()
    drift_detected = detector.add_rating(user_id, book_id, rating)

    return jsonify({
        'success': True,
        'user_id': user_id,
        'book_id': book_id,
        'rating': rating,
        'drift_detected': drift_detected
    }), 200


# ========== 【T2】高级两阶段推荐：多路召回 → 精排（多样性/新颖度） ==========
@recommend_bp.route('/advanced', methods=['GET'])
def advanced_recommend():
    """高级推荐：4路召回（CF/SVD/语义/内容特征）+ 精排加权 + 多样性惩罚

    query: user_id, n, cf_weight, svd_weight, semantic_weight, content_weight,
           diversity_lambda (0-0.8), novelty_boost (0-0.3)
    """
    user_id = request.args.get('user_id', type=int)
    n = request.args.get('n', 10, type=int)
    cf_weight = request.args.get('cf_weight', 0.5, type=float)
    svd_weight = request.args.get('svd_weight', 0.25, type=float)
    semantic_weight = request.args.get('semantic_weight', 0.15, type=float)
    content_weight = request.args.get('content_weight', 0.1, type=float)
    diversity_lambda = request.args.get('diversity_lambda', 0.3, type=float)
    novelty_boost = request.args.get('novelty_boost', 0.15, type=float)

    if n < 1 or n > 50:
        n = 10
    if not user_id:
        return _rec_err('需要用户ID', status=400)

    # 归一化权重
    total_w = max(1e-6, cf_weight + svd_weight + semantic_weight + content_weight)
    cf_weight, svd_weight = cf_weight / total_w, svd_weight / total_w
    semantic_weight, content_weight = semantic_weight / total_w, content_weight / total_w

    def _gen():
        from extensions import db
        from sqlalchemy import func
        from sqlalchemy import or_ as _or
        from models import Rating

        # ---------- 阶段1：多路召回（每个通道 top-N 进入候选池） ----------
        pool = {}  # book_id -> {score, sources, scores...}
        channel_hits = {'cf': 0, 'svd': 0, 'semantic': 0, 'content': 0}

        # 1. CF 召回
        try:
            cf_engine = get_cf_engine()
            cf_recs = cf_engine.recommend(user_id, n_recommendations=min(20, n * 4))
            for rank, rec in enumerate(cf_recs):
                bid = rec.get('book_id')
                if not bid:
                    continue
                score = cf_weight * max(0.0, 1.0 - rank * 0.02)
                pool.setdefault(bid, {'score': 0.0, 'sources': set(),
                                       'cf_score': 0.0, 'svd_score': 0.0,
                                       'semantic_score': 0.0, 'content_score': 0.0})
                pool[bid]['score'] += score
                pool[bid]['cf_score'] = round(score, 4)
                pool[bid]['sources'].add('cf')
                channel_hits['cf'] += 1
        except Exception:
            pass

        # 2. SVD 召回
        try:
            svd_engine = get_svd_engine()
            svd_recs = svd_engine.recommend(user_id, n_recommendations=min(20, n * 4))
            for rank, rec in enumerate(svd_recs):
                bid = rec.get('book_id')
                if not bid:
                    continue
                score = svd_weight * max(0.0, 1.0 - rank * 0.02)
                pool.setdefault(bid, {'score': 0.0, 'sources': set(),
                                       'cf_score': 0.0, 'svd_score': 0.0,
                                       'semantic_score': 0.0, 'content_score': 0.0})
                pool[bid]['score'] += score
                pool[bid]['svd_score'] = round(score, 4)
                pool[bid]['sources'].add('svd')
                channel_hits['svd'] += 1
        except Exception:
            pass

        # 3. 语义召回（Embedding - 基于用户读过的书做相似度扩展）
        try:
            embedding_svc = get_embedding()
            if embedding_svc and hasattr(embedding_svc, 'recommend_books'):
                sem_recs = embedding_svc.recommend_books(user_id, top_k=min(20, n * 4))
                for rank, rec in enumerate(sem_recs[:20]):
                    bid = rec.get('book_id') if isinstance(rec, dict) else rec
                    if not bid:
                        continue
                    score = semantic_weight * max(0.0, 1.0 - rank * 0.02)
                    pool.setdefault(bid, {'score': 0.0, 'sources': set(),
                                           'cf_score': 0.0, 'svd_score': 0.0,
                                           'semantic_score': 0.0, 'content_score': 0.0})
                    pool[bid]['score'] += score
                    pool[bid]['semantic_score'] = round(score, 4)
                    pool[bid]['sources'].add('semantic')
                    channel_hits['semantic'] += 1
        except Exception:
            pass

        # 4. 内容特征召回（同分类 + 同作者的热门书籍 —— 尤其重要：冷启动场景）
        try:
            user_row = db.session.query(Rating.book_id).filter(
                Rating.user_id == user_id
            ).order_by(Rating.rating.desc()).limit(5).all()
            liked_ids = [r[0] for r in user_row]
            if liked_ids:
                liked_books = Book.query.filter(Book.id.in_(liked_ids)).all()
                categories = set(b.category for b in liked_books if b.category)
                authors = set(b.author for b in liked_books if b.author)
                if categories or authors:
                    q = Book.query
                    conds = []
                    if categories:
                        conds.append(Book.category.in_(list(categories)[:3]))
                    if authors:
                        conds.append(Book.author.in_(list(authors)[:5]))
                    q = q.filter(_or(*conds)) if conds else q
                    content_rows = q.limit(n * 4).all()
                    stats = db.session.query(
                        Rating.book_id, func.count(Rating.id).label('cnt')
                    ).filter(Rating.book_id.in_([b.id for b in content_rows])
                             ).group_by(Rating.book_id).all()
                    stat_map = {s.book_id: s.cnt for s in stats}
                    max_cnt = max(list(stat_map.values()) or [1])
                    for rank, b in enumerate(content_rows):
                        score = content_weight * (0.6 + 0.4 * (stat_map.get(b.id, 0) / max_cnt))
                        pool.setdefault(b.id, {'score': 0.0, 'sources': set(),
                                               'cf_score': 0.0, 'svd_score': 0.0,
                                               'semantic_score': 0.0, 'content_score': 0.0})
                        pool[b.id]['score'] += score
                        pool[b.id]['content_score'] = round(score, 4)
                        pool[b.id]['sources'].add('content')
                        channel_hits['content'] += 1
        except Exception:
            pass

        # ---------- 冷启动兜底：如果召回池不够，用热门书籍填充 ----------
        if len(pool) < n:
            try:
                hot_rows = db.session.query(
                    Rating.book_id, func.count(Rating.id).label('cnt'),
                    func.avg(Rating.rating).label('avg')
                ).group_by(Rating.book_id).order_by(
                    func.count(Rating.id).desc()
                ).limit(n * 2).all()
                for rank, r in enumerate(hot_rows):
                    if r.book_id in pool:
                        continue
                    score = 0.2 * max(0.0, 1.0 - rank * 0.02)
                    pool.setdefault(r.book_id, {'score': 0.0, 'sources': set(),
                                                'cf_score': 0.0, 'svd_score': 0.0,
                                                'semantic_score': 0.0, 'content_score': 0.0})
                    pool[r.book_id]['score'] += score
                    pool[r.book_id]['sources'].add('hot')
            except Exception:
                pass

        # ---------- 阶段2：精排（去已读 + 多样性惩罚 + 新颖度提升） ----------
        try:
            rated_rows = db.session.query(Rating.book_id).filter(
                Rating.user_id == user_id
            ).all()
            rated_ids = {r[0] for r in rated_rows}
            for bid in list(pool.keys()):
                if bid in rated_ids:
                    del pool[bid]
        except Exception:
            pass

        ranked = sorted(pool.items(), key=lambda kv: kv[1]['score'], reverse=True)

        # 多样性 + 新颖度（贪心重排）
        selected = []
        selected_categories = set()
        try:
            all_ids = [bid for bid, _ in ranked]
            if all_ids:
                cnt_rows = db.session.query(
                    Rating.book_id, func.count(Rating.id).label('cnt')
                ).filter(Rating.book_id.in_(all_ids)).group_by(Rating.book_id).all()
                cnt_map = {r.book_id: r.cnt for r in cnt_rows}
                max_c = max(list(cnt_map.values()) or [1])
            else:
                cnt_map, max_c = {}, 1

            book_rows = Book.query.filter(Book.id.in_(all_ids)).all() if all_ids else []
            cat_map = {b.id: (b.category or '') for b in book_rows}

            temp = []
            for bid, meta in ranked:
                s = meta['score']
                c = cnt_map.get(bid, 0)
                novelty = (1.0 - min(c / max_c, 1.0)) if max_c else 0.0
                final = s * (1.0 + novelty_boost * novelty)
                temp.append((bid, meta, final, cat_map.get(bid, '')))

            for bid, meta, final_score, cat in temp:
                if cat and cat in selected_categories:
                    final_score *= (1.0 - diversity_lambda)
                selected.append((bid, meta, final_score, cat))
                if cat:
                    selected_categories.add(cat)
                if len(selected) >= n:
                    break

            selected.sort(key=lambda x: x[2], reverse=True)
        except Exception:
            selected = [(bid, meta, meta['score'], None) for bid, meta in ranked[:n]]

        # ---------- 构造结果（补充书籍详情） ----------
        final_ids = [s[0] for s in selected]
        detail_map = {}
        if final_ids:
            for b in Book.query.filter(Book.id.in_(final_ids)).all():
                detail_map[b.id] = b

        recommendations = []
        for bid, meta, final_score, cat in selected:
            book = detail_map.get(bid)
            if not book:
                continue
            book_dict = book.to_dict()
            book_dict['final_score'] = round(final_score, 4)
            book_dict['blend_score'] = round(meta['score'], 4)
            book_dict['cf_score'] = meta.get('cf_score')
            book_dict['svd_score'] = meta.get('svd_score')
            book_dict['semantic_score'] = meta.get('semantic_score')
            book_dict['content_score'] = meta.get('content_score')
            book_dict['sources'] = [s for s in meta.get('sources', [])]
            book_dict['category'] = cat or book_dict.get('category')
            recommendations.append(book_dict)

        return {
            'recommendations': recommendations,
            'algorithm': 'advanced_4stage',
            'channel_hits': channel_hits,
            'weights': {
                'cf': round(cf_weight, 3),
                'svd': round(svd_weight, 3),
                'semantic': round(semantic_weight, 3),
                'content': round(content_weight, 3),
            },
            'diversity_lambda': diversity_lambda,
            'novelty_boost': novelty_boost,
            'user_id': user_id,
            'count': len(recommendations),
            'cold_start': all(c == 0 for c in [
                channel_hits['cf'], channel_hits['svd'], channel_hits['semantic']
            ]),
        }

    data, cache_hit = _rec_with_cache(
        ['advanced', user_id, n, cf_weight, svd_weight, semantic_weight,
         content_weight, diversity_lambda, novelty_boost],
        _gen, ttl_key='hybrid'
    )
    return _rec_response(data, cache_hit=cache_hit), 200


# ========== 推荐服务健康检查 ==========
@recommend_bp.route('/health', methods=['GET'])
def recommend_health():
    try:
        cf_engine = get_cf_engine()
        svd_engine = get_svd_engine()
        cf_n_users = getattr(cf_engine, 'user_count', 0) or 0
        svd_n_items = getattr(svd_engine, 'book_count', 0) or 0
    except Exception:
        cf_n_users, svd_n_items = 0, 0

    return jsonify({
        'success': True,
        'prewarm_done': _prewarm_done,
        'cf_engine_users': cf_n_users,
        'svd_engine_items': svd_n_items,
        'routes_available': ['cf', 'svd', 'semantic', 'hybrid', 'compare', 'advanced'],
        'ab_testing': True,
        'drift_detection': True,
    }), 200


def _rec_ok(data=None, cache_hit=False, status=200):
    resp_data = dict(data or {})
    resp_data['from_cache'] = cache_hit
    resp = jsonify(resp_data)
    resp.headers['X-Cache'] = 'HIT' if cache_hit else 'MISS'
    return resp


def _rec_err(message, status=400):
    return jsonify({'success': False, 'error': message}), status


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

        hot_ids = set()
        try:
            # 先聚合热门 book_id（LIMIT 防止全表扫描）
            top_n = max(n * 10, 200)
            sub = db.session.query(
                Rating.book_id,
                func.count(Rating.id).label('cnt'),
                func.avg(Rating.rating).label('avg'),
            ).group_by(Rating.book_id).order_by(func.count(Rating.id).desc()).limit(top_n).subquery()
            stats_rows = db.session.query(sub.c.book_id, sub.c.cnt, sub.c.avg).all()
            stats_map = {}
            for bid, cnt, avg in stats_rows:
                if int(cnt or 0) == 0:
                    continue
                stats_map[int(bid)] = (int(cnt or 0), float(avg or 0.0))
                hot_ids.add(int(bid))
        except Exception:
            stats_map = {}

        # 加载热门图书
        rows = []
        if stats_map:
            try:
                book_objs = Book.query.filter(Book.id.in_(list(stats_map.keys()))).all()
                for b in book_objs:
                    cnt, avg = stats_map.get(b.id, (0, 0.0))
                    rows.append((b, cnt, avg))
            except Exception:
                rows = []

        # 如果没有 rating 数据，回退用 book.id 前 N 本
        if not rows:
            try:
                fallback = Book.query.order_by(Book.id).limit(n * 3).all()
                for b in fallback:
                    rows.append((b, 1, 8.0))
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
            popularity = (min(cnt, 500) / 500.0) * 0.5 + (avg / 10.0) * 0.5
            cat = getattr(book, 'category', None) or 'misc'
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


# ========== 统一 reason 字段注入工具（用于 hybrid/mmr/cold-start/content/item-based） ==========
def _ensure_reason(book_dict, fallback_reason):
    """给单本推荐字典补齐 reason 字段（如果缺失或为空）"""
    try:
        if not isinstance(book_dict, dict):
            return book_dict
        existing = book_dict.get('reason') or book_dict.get('cold_start_reason')
        if not existing:
            book_dict['reason'] = str(fallback_reason)
        else:
            book_dict.setdefault('reason', str(existing))
        return book_dict
    except Exception:
        return book_dict


def _add_reasons_to_result(result_dict, algorithm_name, default_reason=None):
    """对一个 {recommendations:[...]} 结果字典的每一项补齐 reason 字段"""
    try:
        if not isinstance(result_dict, dict):
            return result_dict
        recs = result_dict.get('recommendations')
        if not isinstance(recs, list):
            return result_dict
        fallback = default_reason or f'recommended by {algorithm_name}'
        new_recs = []
        for item in recs:
            try:
                if isinstance(item, dict):
                    if item.get('reason'):
                        new_recs.append(item)
                        continue
                    # 基于已有字段构造 fallback reason
                    parts = []
                    cat = item.get('category') or ''
                    if cat:
                        parts.append(str(cat))
                    author = item.get('author') or ''
                    if author:
                        parts.append(f'by {author}')
                    for signal_key in ('method', 'algorithm', 'strategy', 'sources'):
                        val = item.get(signal_key)
                        if val:
                            if isinstance(val, list):
                                parts.extend(str(v) for v in val)
                            else:
                                parts.append(str(val))
                            break
                    if parts:
                        item['reason'] = f'{fallback}: {", ".join(parts)}'
                    else:
                        item['reason'] = fallback
                new_recs.append(item)
            except Exception:
                new_recs.append(item)
        result_dict['recommendations'] = new_recs
        return result_dict
    except Exception:
        return result_dict


# ========== mmr 路由 diversity_score 增强版（追加版本，不改动原路由） ==========
@recommend_bp.route('/mmr-with-diversity', methods=['GET'])
def mmr_recommend_with_diversity():
    """同 /mmr，但额外返回 diversity_score（1.0 - avg_pairwise_similarity_in_picks）

    diversity_score 近似计算：
      - 有 embedding 时，基于 embedding 相似度矩阵
      - 否则基于分类/作者的 overlap 作为相似度近似
    """
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
        from models import Book, Rating

        pool = {}
        pool_size = max(n * 3, 20)

        # --- CF ---
        try:
            cf_engine = get_cf_engine()
            cf_recs = cf_engine.recommend(user_id, n_recommendations=pool_size) or []
            for rank, rec in enumerate(cf_recs):
                bid = rec.get('book_id') if isinstance(rec, dict) else None
                if not bid:
                    continue
                rel = max(0.0, 1.0 - rank * 0.02)
                pool.setdefault(int(bid), {'score': 0.0, 'cf_score': 0.0})
                pool[int(bid)]['score'] += rel
                pool[int(bid)]['cf_score'] = round(rel, 4)
        except Exception:
            pass

        # --- SVD ---
        try:
            svd_engine = get_svd_engine()
            svd_recs = svd_engine.recommend(user_id, n_recommendations=pool_size) or []
            for rank, rec in enumerate(svd_recs):
                bid = rec.get('book_id') if isinstance(rec, dict) else None
                if not bid:
                    continue
                rel = max(0.0, 0.9 - rank * 0.02)
                pool.setdefault(int(bid), {'score': 0.0, 'svd_score': 0.0})
                pool[int(bid)]['score'] += rel
                pool[int(bid)]['svd_score'] = round(rel, 4)
        except Exception:
            pass

        # --- semantic ---
        try:
            embedding_svc = get_embedding()
            if embedding_svc is not None and hasattr(embedding_svc, 'recommend_books'):
                sem_recs = embedding_svc.recommend_books(user_id, top_k=pool_size) or []
                for rank, rec in enumerate(sem_recs[:pool_size]):
                    bid = rec.get('book_id') if isinstance(rec, dict) else rec
                    if not bid:
                        continue
                    rel = max(0.0, 0.8 - rank * 0.02)
                    pool.setdefault(int(bid), {'score': 0.0, 'semantic_score': 0.0})
                    pool[int(bid)]['score'] += rel
                    pool[int(bid)]['semantic_score'] = round(rel, 4)
        except Exception:
            pass

        # --- content ---
        try:
            content_engine = get_content_recommender()
            content_recs = content_engine.recommend(user_id, n=pool_size, seed=42) or []
            for rank, rec in enumerate(content_recs):
                bid = rec.get('book_id') if isinstance(rec, dict) else None
                if not bid:
                    continue
                rel = float(rec.get('score', 0.0) or 0.0)
                pool.setdefault(int(bid), {'score': 0.0, 'content_score': 0.0})
                pool[int(bid)]['score'] += rel
                pool[int(bid)]['content_score'] = round(rel, 4)
        except Exception:
            pass

        # 去已读
        try:
            rated_rows = db.session.query(Rating.book_id).filter(Rating.user_id == user_id).all()
            rated_ids = {int(r[0]) for r in rated_rows}
            for bid in list(pool.keys()):
                if bid in rated_ids:
                    del pool[bid]
        except Exception:
            pass

        if not pool:
            return {
                'recommendations': [], 'algorithm': 'mmr', 'user_id': user_id,
                'count': 0, 'lambda_param': lambda_param,
                'diversity_score': 0.0, 'note': 'no candidates',
            }

        # 去重排序 -> 取 n
        ranked = sorted(pool.items(), key=lambda kv: float(kv[1].get('score', 0.0)), reverse=True)
        all_ids = [bid for bid, _ in ranked]
        book_objs = {b.id: b for b in Book.query.filter(Book.id.in_(all_ids)).all()} if all_ids else {}

        # 贪心 + 多样性惩罚
        selected = []
        seen_categories = set()
        for bid, meta in ranked:
            book = book_objs.get(bid)
            if book is None:
                continue
            cat = getattr(book, 'category', None) or ''
            score = float(meta.get('score', 0.0))
            if cat and cat in seen_categories:
                score *= (1.0 - lambda_param * 0.3)
            selected.append((bid, book, score, meta, cat))
            if cat:
                seen_categories.add(cat)
            if len(selected) >= n * 2:
                break
        selected.sort(key=lambda x: x[2], reverse=True)
        selected = selected[:n]

        # 构造结果字典，补齐 reason
        try:
            explainer = get_explainability()
        except Exception:
            explainer = None
        try:
            user_profile = get_content_recommender().get_user_profile(user_id)
        except Exception:
            user_profile = {'size': 0, 'authors': {}, 'categories': {}}

        recommendations = []
        final_ids = []
        for bid, book, score, meta, cat in selected:
            try:
                book_dict = book.to_dict() if hasattr(book, 'to_dict') else {
                    'id': book.id, 'title': getattr(book, 'title', ''),
                    'author': getattr(book, 'author', ''), 'category': cat,
                }
            except Exception:
                book_dict = {
                    'id': bid, 'title': getattr(book, 'title', ''),
                    'author': getattr(book, 'author', ''), 'category': cat,
                }
            book_dict['book_id'] = bid
            book_dict['mmr_score'] = round(float(score), 4)
            book_dict['blend_score'] = round(float(meta.get('score', 0.0)), 4)
            if isinstance(meta, dict):
                for k in ('cf_score', 'svd_score', 'semantic_score', 'content_score'):
                    if meta.get(k) is not None:
                        book_dict[k] = meta.get(k)
            try:
                reason = explainer.generate_reason(
                    book, sources=['content_based', 'cf'], user_profile=user_profile,
                ) if explainer else None
            except Exception:
                reason = None
            if not reason:
                reason = f"blend of collaborative filtering + content features in {'category ' + cat if cat else 'relevant topics'}"
            book_dict['reason'] = reason
            recommendations.append(book_dict)
            final_ids.append(bid)

        # 计算 diversity_score
        diversity_score = 0.0
        try:
            if len(final_ids) >= 2:
                # 1. 尝试 embedding 相似度
                sim_matrix = None
                try:
                    embedding_svc = get_embedding()
                    if embedding_svc is not None and hasattr(embedding_svc, 'find_similar_books'):
                        sim_matrix = {}
                        selected_books = [book_objs[bid] for bid in final_ids if bid in book_objs]
                        for book in selected_books:
                            try:
                                sims = embedding_svc.find_similar_books(
                                    book, candidates=selected_books,
                                    top_k=len(selected_books), threshold=0.0,
                                ) or []
                                for item in sims:
                                    if isinstance(item, dict):
                                        other_id = item.get('book_id')
                                        sim = float(item.get('similarity', 0.0) or 0.0)
                                    else:
                                        other_id, sim = item[0], float(item[1])
                                    if other_id is None or other_id == book.id:
                                        continue
                                    key = (min(book.id, other_id), max(book.id, other_id))
                                    sim_matrix[key] = max(sim_matrix.get(key, 0.0), sim)
                            except Exception:
                                continue
                except Exception:
                    sim_matrix = None

                if sim_matrix:
                    values = [float(v) for v in sim_matrix.values()]
                    avg_sim = sum(values) / len(values) if values else 0.0
                    avg_sim = max(0.0, min(1.0, avg_sim))
                    diversity_score = round(1.0 - avg_sim, 4)
                else:
                    # 2. 分类/作者 overlap 近似
                    pairs = []
                    books_meta = []
                    for bid in final_ids:
                        b = book_objs.get(bid)
                        if b is None:
                            continue
                        books_meta.append({
                            'category': getattr(b, 'category', None) or '',
                            'author': getattr(b, 'author', None) or '',
                        })
                    for i in range(len(books_meta)):
                        for j in range(i + 1, len(books_meta)):
                            sim = 0.0
                            if books_meta[i]['category'] and books_meta[i]['category'] == books_meta[j]['category']:
                                sim += 0.6
                            if books_meta[i]['author'] and books_meta[i]['author'] == books_meta[j]['author']:
                                sim += 0.3
                            pairs.append(sim)
                    avg_sim = sum(pairs) / len(pairs) if pairs else 0.0
                    avg_sim = max(0.0, min(1.0, avg_sim))
                    diversity_score = round(1.0 - avg_sim, 4)
        except Exception:
            diversity_score = 0.0

        return {
            'recommendations': recommendations, 'algorithm': 'mmr_with_diversity',
            'user_id': user_id, 'count': len(recommendations),
            'lambda_param': lambda_param, 'diversity_score': diversity_score,
            'candidate_pool_size': len(pool),
        }

    try:
        data, cache_hit = _rec_with_cache(
            ['mmr_diversity', user_id, n, lambda_param], _gen, ttl_key='hybrid',
        )
    except Exception as e:
        return _rec_err(f'mmr-with-diversity recommend failed: {e}', status=500)
    return _rec_ok(data, cache_hit=cache_hit), 200


# ========== 给原有 /mmr 路由打补丁：在响应中追加 diversity_score ==========
_original_mmr_view = mmr_recommend


@recommend_bp.route('/mmr', methods=['GET'], endpoint='mmr_recommend_with_diversity_patch')
def mmr_recommend_patched():
    """原 mmr 路由的增强版：在原响应基础上追加 diversity_score"""
    try:
        from flask import json
        # 调用原视图获取响应
        original_resp = _original_mmr_view()
        # 解析 body 为 dict（原视图返回 (response, status)）
        if isinstance(original_resp, tuple):
            resp_obj = original_resp[0]
            status = original_resp[1] if len(original_resp) > 1 else 200
        else:
            resp_obj = original_resp
            status = 200

        # 从 Flask Response 中提取 JSON 数据
        data = {}
        try:
            raw = resp_obj.get_data(as_text=True) if hasattr(resp_obj, 'get_data') else None
            if raw:
                try:
                    data = json.loads(raw)
                except Exception:
                    data = {}
        except Exception:
            data = {}

        # 构造 diversity_score
        recommendations = data.get('recommendations', []) if isinstance(data, dict) else []
        try:
            ids = []
            for r in recommendations:
                if isinstance(r, dict):
                    bid = r.get('book_id') or r.get('id')
                    if bid:
                        ids.append(int(bid))
            diversity_score = 0.0
            if len(ids) >= 2:
                try:
                    book_objs = {b.id: b for b in Book.query.filter(Book.id.in_(ids)).all()}
                    buckets = []
                    for bid in ids:
                        b = book_objs.get(bid)
                        if b is None:
                            continue
                        buckets.append({
                            'category': getattr(b, 'category', None) or '',
                            'author': getattr(b, 'author', None) or '',
                        })
                    pairs = []
                    for i in range(len(buckets)):
                        for j in range(i + 1, len(buckets)):
                            sim = 0.0
                            if buckets[i]['category'] and buckets[i]['category'] == buckets[j]['category']:
                                sim += 0.6
                            if buckets[i]['author'] and buckets[i]['author'] == buckets[j]['author']:
                                sim += 0.3
                            pairs.append(sim)
                    avg_sim = sum(pairs) / len(pairs) if pairs else 0.0
                    diversity_score = round(1.0 - max(0.0, min(1.0, avg_sim)), 4)
                except Exception:
                    diversity_score = 0.0
            data['diversity_score'] = diversity_score
        except Exception:
            data['diversity_score'] = 0.0

        # 补齐 reason
        try:
            _add_reasons_to_result(data, 'mmr', default_reason='diversified hybrid recommendations (collaborative + content + semantic)')
        except Exception:
            pass

        # 重新包装成 _rec_ok 返回格式
        return _rec_ok(data, cache_hit=data.get('from_cache', False) if isinstance(data, dict) else False), status
    except Exception as e:
        # 回落到原视图
        try:
            return _original_mmr_view()
        except Exception:
            return _rec_err(f'mmr patched failed: {e}', status=500)


# ========== 给 hybrid / cold-start / content / item-based 补齐 reason 字段的 wrapper 路由 ==========
@recommend_bp.route('/hybrid-with-reason', methods=['GET'])
def hybrid_with_reason():
    """同 /hybrid，但保证每本书都有 reason 字段"""
    try:
        from flask import json as _flask_json
        raw = hybrid_recommend()
        if isinstance(raw, tuple):
            resp_obj, status = raw[0], (raw[1] if len(raw) > 1 else 200)
        else:
            resp_obj, status = raw, 200
        body = resp_obj.get_data(as_text=True) if hasattr(resp_obj, 'get_data') else None
        data = _flask_json.loads(body) if body else {}
        _add_reasons_to_result(
            data, 'hybrid',
            default_reason='hybrid recommendation combining CF, SVD and semantic signals',
        )
        return _rec_ok(data, cache_hit=data.get('from_cache', False) if isinstance(data, dict) else False), status
    except Exception as e:
        return _rec_err(f'hybrid-with-reason failed: {e}', status=500)


@recommend_bp.route('/cold-start-with-reason', methods=['GET'])
def cold_start_with_reason():
    """同 /cold-start，但保证每本书都有 reason 字段"""
    try:
        from flask import json as _flask_json
        raw = cold_start_recommend()
        if isinstance(raw, tuple):
            resp_obj, status = raw[0], (raw[1] if len(raw) > 1 else 200)
        else:
            resp_obj, status = raw, 200
        body = resp_obj.get_data(as_text=True) if hasattr(resp_obj, 'get_data') else None
        data = _flask_json.loads(body) if body else {}
        _add_reasons_to_result(
            data, 'cold_start',
            default_reason='popular and diverse picks for new users',
        )
        return _rec_ok(data, cache_hit=data.get('from_cache', False) if isinstance(data, dict) else False), status
    except Exception as e:
        return _rec_err(f'cold-start-with-reason failed: {e}', status=500)


# ========== 算法元数据 路由 ==========
@recommend_bp.route('/algorithms', methods=['GET'])
def list_algorithms():
    """返回所有可用推荐算法的元数据（name / description / endpoint / params）"""
    algorithms = [
        {
            'name': 'cf',
            'algorithm': 'collaborative_filtering_user_based',
            'description': '基于用户的协同过滤推荐：从相似用户的高评分中获取候选，适合有评分历史的用户。',
            'endpoint': '/api/recommend/cf',
            'params': [
                {'name': 'user_id', 'type': 'int', 'required': True, 'description': '目标用户 ID'},
                {'name': 'n', 'type': 'int', 'default': 10, 'description': '返回推荐数量（1-50）'},
            ],
            'supports_reason': True,
            'notes': 'requires rating history; cached',
        },
        {
            'name': 'svd',
            'algorithm': 'svd_matrix_factorization',
            'description': '基于 SVD 矩阵分解的评分预测推荐：学习用户-物品隐向量，缓解稀疏性问题。',
            'endpoint': '/api/recommend/svd',
            'params': [
                {'name': 'user_id', 'type': 'int', 'required': True, 'description': '目标用户 ID'},
                {'name': 'n', 'type': 'int', 'default': 10, 'description': '返回推荐数量（1-50）'},
            ],
            'supports_reason': True,
            'notes': 'good for sparse rating matrices',
        },
        {
            'name': 'semantic',
            'algorithm': 'semantic_enhanced_cf',
            'description': '语义增强协同过滤：用书籍 embedding（如 fastText/word2vec）补全协同信号。',
            'endpoint': '/api/recommend/semantic',
            'params': [
                {'name': 'user_id', 'type': 'int', 'required': True, 'description': '目标用户 ID'},
                {'name': 'n', 'type': 'int', 'default': 10, 'description': '返回推荐数量（1-50）'},
                {'name': 'semantic_weight', 'type': 'float', 'default': 0.2, 'description': '语义权重（0-1）'},
            ],
            'supports_reason': True,
            'notes': 'requires embedding service ready',
        },
        {
            'name': 'hybrid',
            'algorithm': 'hybrid_cf_svd_semantic',
            'description': '混合推荐：融合 CF、SVD 与语义三种信号线性加权，通常效果最稳定。',
            'endpoint': '/api/recommend/hybrid',
            'params': [
                {'name': 'user_id', 'type': 'int', 'required': True, 'description': '目标用户 ID'},
                {'name': 'n', 'type': 'int', 'default': 10, 'description': '返回推荐数量（1-50）'},
                {'name': 'cf_weight', 'type': 'float', 'default': 0.3, 'description': 'CF 权重（0-1）'},
                {'name': 'svd_weight', 'type': 'float', 'default': 0.4, 'description': 'SVD 权重（0-1）'},
                {'name': 'semantic_weight', 'type': 'float', 'default': 0.3, 'description': '语义权重（0-1）'},
            ],
            'supports_reason': True,
            'notes': 'balanced between accuracy and coverage; /hybrid-with-reason variant ensures every item has reason field',
        },
        {
            'name': 'advanced',
            'algorithm': 'multi_stage_with_diversity_and_novelty',
            'description': '高级两阶段推荐：多路召回（CF/SVD/语义/内容特征）+ 精排（多样性惩罚 + 新颖度提升）。',
            'endpoint': '/api/recommend/advanced',
            'params': [
                {'name': 'user_id', 'type': 'int', 'required': True, 'description': '目标用户 ID'},
                {'name': 'n', 'type': 'int', 'default': 10, 'description': '返回推荐数量（1-50）'},
                {'name': 'cf_weight', 'type': 'float', 'default': 0.5, 'description': 'CF 权重'},
                {'name': 'svd_weight', 'type': 'float', 'default': 0.25, 'description': 'SVD 权重'},
                {'name': 'semantic_weight', 'type': 'float', 'default': 0.15, 'description': '语义权重'},
                {'name': 'content_weight', 'type': 'float', 'default': 0.1, 'description': '内容特征权重'},
                {'name': 'diversity_lambda', 'type': 'float', 'default': 0.3, 'description': '多样性惩罚系数（0-0.8）'},
                {'name': 'novelty_boost', 'type': 'float', 'default': 0.15, 'description': '新颖度提升系数（0-0.3）'},
            ],
            'supports_reason': True,
            'notes': 'most feature-rich algorithm; highest latency',
        },
        {
            'name': 'mmr',
            'algorithm': 'maximal_marginal_relevance',
            'description': 'MMR 最大边界相关性重排：在相关性与多样性之间做取舍。返回 diversity_score = 1.0 - avg_pairwise_similarity。',
            'endpoint': '/api/recommend/mmr',
            'params': [
                {'name': 'user_id', 'type': 'int', 'required': True, 'description': '目标用户 ID'},
                {'name': 'n', 'type': 'int', 'default': 10, 'description': '返回推荐数量（1-50）'},
                {'name': 'lambda_param', 'type': 'float', 'default': 0.5, 'description': '相关性 vs 多样性权衡（0=完全多样，1=完全相关）'},
            ],
            'supports_reason': True,
            'notes': 'diversity_score attached via /mmr; use /mmr-with-diversity for an alternative implementation with explicit similarity matrices',
        },
        {
            'name': 'content',
            'algorithm': 'content_based_filtering',
            'description': '基于内容的推荐：构建用户画像（分类/作者/关键词），推荐与画像最相似的书籍。',
            'endpoint': '/api/recommend/content',
            'params': [
                {'name': 'user_id', 'type': 'int', 'required': True, 'description': '目标用户 ID'},
                {'name': 'n', 'type': 'int', 'default': 10, 'description': '返回推荐数量（1-50）'},
            ],
            'supports_reason': True,
            'notes': 'explainability engine generates personalized per-book reasons',
        },
        {
            'name': 'item_based',
            'algorithm': 'item_based_collaborative_filtering',
            'description': '基于物品的协同过滤：寻找用户已评价物品的相似物品集合，作为推荐候选。',
            'endpoint': '/api/recommend/item-based',
            'params': [
                {'name': 'user_id', 'type': 'int', 'required': True, 'description': '目标用户 ID'},
                {'name': 'n', 'type': 'int', 'default': 10, 'description': '返回推荐数量（1-50）'},
                {'name': 'k', 'type': 'int', 'default': 20, 'description': '邻居物品数量'},
            ],
            'supports_reason': True,
            'notes': 'reason field filled by content-filter explainer when possible',
        },
        {
            'name': 'cold_start',
            'algorithm': 'popularity_with_exploration',
            'description': '冷启动推荐：为新用户（低评分数量）返回高评分 + 多分类 + 小众探索的书籍组合。',
            'endpoint': '/api/recommend/cold-start',
            'params': [
                {'name': 'user_id', 'type': 'int', 'required': False, 'description': '目标用户 ID（可选，用于判断新用户）'},
                {'name': 'n', 'type': 'int', 'default': 10, 'description': '返回推荐数量（1-50）'},
                {'name': 'explore_ratio', 'type': 'float', 'default': 0.2, 'description': '探索（高评分低热度）书籍比例（0-0.5）'},
            ],
            'supports_reason': True,
            'notes': 'works for new users with < 5 ratings; reason per book filled from category + popularity',
        },
        {
            'name': 'explain',
            'algorithm': 'explanation_engine',
            'description': '单本书籍可解释性分析：综合 content_score / CF 预测评分 / 语义相似度，给出推荐理由。',
            'endpoint': '/api/recommend/explain',
            'params': [
                {'name': 'user_id', 'type': 'int', 'required': True, 'description': '目标用户 ID'},
                {'name': 'book_id', 'type': 'int', 'required': True, 'description': '目标书籍 ID'},
            ],
            'supports_reason': True,
            'notes': 'returns a single explanation object with `reason`',
        },
    ]

    return _rec_ok({
        'success': True,
        'count': len(algorithms),
        'algorithms': algorithms,
        'endpoints': [a['endpoint'] for a in algorithms],
    }), 200


# ========== /health 路由增强：追加算法列表 ==========
@recommend_bp.route('/health', methods=['GET'], endpoint='health_enhanced')
def recommend_health_enhanced():
    """健康状态（增强版）：返回引擎状态 + 算法元数据"""
    try:
        cf_engine = get_cf_engine()
        svd_engine = get_svd_engine()
        cf_n_users = int(getattr(cf_engine, 'user_count', 0) or 0)
        svd_n_items = int(getattr(svd_engine, 'book_count', 0) or 0)
    except Exception:
        cf_n_users, svd_n_items = 0, 0

    try:
        content_engine = get_content_recommender()
        content_ready = content_engine is not None
    except Exception:
        content_ready = False

    try:
        embed_svc = get_embedding()
        faiss_ready = bool(getattr(embed_svc, 'faiss_ready', False)) if embed_svc else False
    except Exception:
        faiss_ready = False

    endpoints = [
        '/cf', '/svd', '/semantic', '/hybrid', '/compare', '/advanced',
        '/mmr', '/mmr-with-diversity', '/content', '/item-based',
        '/cold-start', '/explain', '/hybrid-with-reason', '/cold-start-with-reason',
        '/algorithms', '/health',
    ]
    return jsonify({
        'success': True,
        'prewarm_done': _prewarm_done,
        'cf_engine_users': cf_n_users,
        'svd_engine_items': svd_n_items,
        'content_engine_ready': content_ready,
        'faiss_ready': faiss_ready,
        'routes_available': endpoints,
        'algorithm_count': len(endpoints),
        'ab_testing': True,
        'drift_detection': True,
    }), 200

