"""推荐服务 - 独立微服务（轻量 HTTP + 内存缓存）

设计思路：
- 主进程监听 RECOMMEND_PORT（默认 6000）
- 启动时连接 MySQL 获取用户评分矩阵
- 暴露 /api/recommend/<alg>/<user_id> 供主站 Flask 调用
- 内部维护协同过滤 / SVD / 混合算法的内存缓存
- 主站 Flask 不需要改动 routes/recommend.py 中的逻辑；它可以继续走自己的路由；
  本服务用于"计算密集"场景，独立部署减轻主站 CPU/内存压力

启动方式（独立进程）：
    python recommend_service.py
或：
    gunicorn recommend_service:app -w 4 -k gevent -b 0.0.0.0:6000
"""

import os
import json
import time
import math
import random
import threading
from typing import List, Dict, Any, Optional, Tuple

try:
    from flask import Flask, jsonify, request, Response
    from flask_cors import CORS
    USE_FLASK = True
except Exception as e:
    print(f'[RecommendService] Flask 不可用: {e}')
    USE_FLASK = False

# 可选依赖
try:
    import pymysql
    HAS_PYMYSQL = True
except Exception:
    HAS_PYMYSQL = False

try:
    import redis as _redis
    HAS_REDIS = True
except Exception:
    HAS_REDIS = False


# ====================================================================
# 配置（可通过环境变量覆盖）
# ====================================================================
class Config:
    HOST = os.environ.get('RECOMMEND_HOST', '0.0.0.0')
    PORT = int(os.environ.get('RECOMMEND_PORT', 6000))
    DEBUG = os.environ.get('RECOMMEND_DEBUG', '1') == '1'

    # MySQL
    DB_HOST = os.environ.get('RECOMMEND_DB_HOST', 'localhost')
    DB_PORT = int(os.environ.get('RECOMMEND_DB_PORT', 3306))
    DB_USER = os.environ.get('RECOMMEND_DB_USER', 'root')
    DB_PASSWORD = os.environ.get('RECOMMEND_DB_PASSWORD', '123456')
    DB_DATABASE = os.environ.get('RECOMMEND_DB_NAME', 'book_recommend')

    # Redis 缓存（可选）
    REDIS_HOST = os.environ.get('RECOMMEND_REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('RECOMMEND_REDIS_PORT', 6379))
    REDIS_DB = int(os.environ.get('RECOMMEND_REDIS_DB', 4))
    CACHE_TTL = int(os.environ.get('RECOMMEND_CACHE_TTL', 600))

    # 模型刷新周期（秒），默认每 10 分钟重算一次
    REFRESH_INTERVAL = int(os.environ.get('RECOMMEND_REFRESH', 600))

    # 推荐数量上下限
    MAX_N = 50
    DEFAULT_N = 10


# ====================================================================
# 内存缓存（推荐服务内轻量 KV）
# ====================================================================
class _MemCache:
    def __init__(self):
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            v = self._store.get(key)
            if v is None:
                return None
            value, expire = v
            if expire and expire < time.time():
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        with self._lock:
            expire = time.time() + ttl if ttl > 0 else 0
            self._store[key] = (value, expire)

    def invalidate(self, pattern: str) -> int:
        with self._lock:
            keys = [k for k in self._store.keys() if pattern in k]
            for k in keys:
                del self._store[k]
            return len(keys)


_mem_cache = _MemCache()
_redis_client = None
if HAS_REDIS:
    try:
        _redis_client = _redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=2,
        )
        _redis_client.ping()
        print(f'[RecommendService] Redis 缓存已连接 -> {Config.REDIS_HOST}:{Config.REDIS_PORT}')
    except Exception as e:
        _redis_client = None
        print(f'[RecommendService] Redis 不可用，回退到内存缓存: {e}')


def _cache_get(key: str):
    if _redis_client:
        try:
            raw = _redis_client.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    return _mem_cache.get(key)


def _cache_set(key: str, value: Any, ttl: int = 300) -> None:
    try:
        if _redis_client:
            _redis_client.setex(key, ttl, json.dumps(value, default=str))
            return
    except Exception:
        pass
    _mem_cache.set(key, value, ttl)


# ====================================================================
# 评分数据模型（从 MySQL 加载）
# ====================================================================
class RatingStore:
    def __init__(self):
        self.user_ratings: Dict[int, Dict[int, float]] = {}   # user_id -> {book_id: rating}
        self.book_ratings: Dict[int, Dict[int, float]] = {}  # book_id -> {user_id: rating}
        self.book_ids: List[int] = []
        self.user_ids: List[int] = []
        self.avg_rating: float = 0.0
        self.global_rating_count: int = 0
        self._lock = threading.RLock()
        self._last_refresh: float = 0.0

    def refresh(self) -> bool:
        """从数据库加载所有评分到内存；失败静默返回 False"""
        if not HAS_PYMYSQL:
            print('[RecommendService] pymysql 未安装，跳过数据库加载')
            return False

        try:
            conn = pymysql.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_DATABASE,
                charset='utf8mb4',
                connect_timeout=5,
                cursorclass=pymysql.cursors.DictCursor,
            )
            try:
                with conn.cursor() as cur:
                    cur.execute('SELECT user_id, book_id, rating FROM ratings LIMIT 200000')
                    rows = cur.fetchall()
            finally:
                conn.close()

            new_user_ratings: Dict[int, Dict[int, float]] = {}
            new_book_ratings: Dict[int, Dict[int, float]] = {}
            total = 0.0
            count = 0
            for r in rows:
                u = int(r['user_id'])
                b = int(r['book_id'])
                v = float(r['rating'])
                new_user_ratings.setdefault(u, {})[b] = v
                new_book_ratings.setdefault(b, {})[u] = v
                total += v
                count += 1

            with self._lock:
                self.user_ratings = new_user_ratings
                self.book_ratings = new_book_ratings
                self.user_ids = sorted(new_user_ratings.keys())
                self.book_ids = sorted(new_book_ratings.keys())
                self.avg_rating = total / count if count else 0.0
                self.global_rating_count = count
                self._last_refresh = time.time()

            print(f'[RecommendService] 评分数据加载完成: users={len(self.user_ids)}, '
                  f'books={len(self.book_ids)}, ratings={count}, avg={self.avg_rating:.2f}')
            return True
        except Exception as e:
            print(f'[RecommendService] 评分数据加载失败: {e}')
            return False

    def get_user_books(self, user_id: int) -> Dict[int, float]:
        with self._lock:
            return dict(self.user_ratings.get(user_id, {}))

    def get_book_ratings(self, book_id: int) -> Dict[int, float]:
        with self._lock:
            return dict(self.book_ratings.get(book_id, {}))

    def get_book_popularity(self, book_id: int) -> float:
        with self._lock:
            ratings = self.book_ratings.get(book_id, {})
            if not ratings:
                return 0.0
            avg = sum(ratings.values()) / len(ratings)
            count = len(ratings)
            # 评分数量 * 平均得分 -> 流行度
            return avg * math.log(count + 1)


store = RatingStore()


# ====================================================================
# 推荐算法
# ====================================================================
def _cosine_similarity(a: Dict[int, float], b: Dict[int, float]) -> float:
    common = set(a.keys()) & set(b.keys())
    if not common:
        return 0.0
    dot = sum(a[k] * b[k] for k in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def recommend_cf(user_id: int, n: int = 10) -> List[Dict[str, Any]]:
    """基于用户的协同过滤 - 主算法"""
    user_ratings = store.get_user_books(user_id)
    if not user_ratings:
        # 冷启动：返回热门书籍
        return _popular_books(n)

    # 找到与当前用户相似的 top-K 用户
    sim_scores: List[Tuple[int, float]] = []
    for other_uid in store.user_ids:
        if other_uid == user_id:
            continue
        other_ratings = store.get_user_books(other_uid)
        if not other_ratings:
            continue
        sim = _cosine_similarity(user_ratings, other_ratings)
        if sim > 0:
            sim_scores.append((other_uid, sim))

    sim_scores.sort(key=lambda x: x[1], reverse=True)
    top_neighbors = sim_scores[:50]

    # 加权聚合邻居的评分，过滤已评分书籍
    scored: Dict[int, float] = {}
    weight_sum: Dict[int, float] = {}
    for neighbor_uid, sim in top_neighbors:
        neighbor_books = store.get_user_books(neighbor_uid)
        for book_id, rating in neighbor_books.items():
            if book_id in user_ratings:
                continue
            scored[book_id] = scored.get(book_id, 0) + sim * rating
            weight_sum[book_id] = weight_sum.get(book_id, 0) + sim

    ranked = [
        {
            'book_id': bid,
            'score': (scored[bid] / weight_sum[bid]) if weight_sum[bid] > 0 else 0,
            'neighbor_count': int(sum(1 for x, _ in top_neighbors if bid in store.get_user_books(x))),
        }
        for bid in scored.keys()
    ]
    ranked.sort(key=lambda r: r['score'], reverse=True)
    return ranked[:n]


def recommend_svd(user_id: int, n: int = 10) -> List[Dict[str, Any]]:
    """SVD 近似（用评分均值做基线，不做真实 SVD 分解）"""
    user_ratings = store.get_user_books(user_id)
    if not user_ratings:
        return _popular_books(n)

    # 简易 SVD：按"评分距离全局均值"加权
    global_avg = store.avg_rating
    candidates: Dict[int, float] = {}

    for book_id in store.book_ids:
        if book_id in user_ratings:
            continue
        book_r = store.get_book_ratings(book_id)
        if not book_r or len(book_r) < 3:
            continue
        book_avg = sum(book_r.values()) / len(book_r)
        # 偏差 + 数量置信
        candidates[book_id] = book_avg + 0.1 * math.log(len(book_r) + 1)

    ranked = [
        {'book_id': bid, 'score': score, 'neighbor_count': int(len(store.get_book_ratings(bid)))}
        for bid, score in candidates.items()
    ]
    ranked.sort(key=lambda r: r['score'], reverse=True)
    return ranked[:n]


def recommend_hybrid(user_id: int, n: int = 10,
                      cf_w: float = 0.4, svd_w: float = 0.35,
                      pop_w: float = 0.25) -> List[Dict[str, Any]]:
    """混合推荐：协同过滤 + SVD + 热度加权"""
    cf_results = recommend_cf(user_id, n * 4)
    svd_results = recommend_svd(user_id, n * 4)
    pop_results = _popular_books(n * 4)

    cf_scores = {r['book_id']: r['score'] for r in cf_results}
    svd_scores = {r['book_id']: r['score'] for r in svd_results}
    pop_scores = {r['book_id']: r['score'] for r in pop_results}

    all_books = set(cf_scores) | set(svd_scores) | set(pop_scores)
    user_read = set(store.get_user_books(user_id).keys())

    # 归一化每一路的最大得分
    cf_max = max(cf_scores.values()) if cf_scores else 1
    svd_max = max(svd_scores.values()) if svd_scores else 1
    pop_max = max(pop_scores.values()) if pop_scores else 1

    combined = []
    for bid in all_books:
        if bid in user_read:
            continue
        cf_n = cf_scores.get(bid, 0) / cf_max
        svd_n = svd_scores.get(bid, 0) / svd_max if svd_max else 0
        pop_n = pop_scores.get(bid, 0) / pop_max if pop_max else 0
        final = cf_w * cf_n + svd_w * svd_n + pop_w * pop_n
        combined.append({'book_id': bid, 'score': final, 'cf': cf_n, 'svd': svd_n, 'popularity': pop_n})

    combined.sort(key=lambda r: r['score'], reverse=True)
    return combined[:n]


def _popular_books(n: int = 10) -> List[Dict[str, Any]]:
    """按流行度排序（冷启动 fallback）"""
    pop = []
    for book_id in store.book_ids:
        s = store.get_book_popularity(book_id)
        if s > 0:
            pop.append({'book_id': book_id, 'score': s, 'neighbor_count': int(len(store.get_book_ratings(book_id)))})
    pop.sort(key=lambda r: r['score'], reverse=True)
    return pop[:n]


def compare_algorithms(user_id: int, n: int = 10) -> Dict[str, Any]:
    """对比三种算法的输出，便于前端展示"""
    cf = recommend_cf(user_id, n)
    svd = recommend_svd(user_id, n)
    hybrid = recommend_hybrid(user_id, n)
    return {
        'cf': cf,
        'svd': svd,
        'hybrid': hybrid,
        'user_id': user_id,
        'total_users': len(store.user_ids),
        'total_books': len(store.book_ids),
    }


# ====================================================================
# 后台：周期性刷新评分数据
# ====================================================================
def _bg_refresh_loop() -> None:
    while True:
        try:
            store.refresh()
            # 刷新后让旧缓存失效
            _mem_cache.invalidate('rec:')
        except Exception as e:
            print(f'[RecommendService] 刷新循环异常: {e}')
        time.sleep(Config.REFRESH_INTERVAL)


# ====================================================================
# HTTP 应用（独立启动）
# ====================================================================
if USE_FLASK:
    rec_app = Flask(__name__)
    CORS(rec_app)

    @rec_app.before_request
    def _track_start():
        request._start = time.time()

    @rec_app.after_request
    def _track_end(resp):
        elapsed = (time.time() - getattr(request, '_start', time.time())) * 1000
        resp.headers['X-Service'] = 'recommend-service'
        resp.headers['X-Latency-Ms'] = f'{elapsed:.1f}'
        return resp

    @rec_app.route('/health', methods=['GET'])
    def health():
        return jsonify({
            'status': 'ok',
            'users': len(store.user_ids),
            'books': len(store.book_ids),
            'ratings': store.global_rating_count,
            'avg_rating': round(store.avg_rating, 3),
            'last_refresh_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(store._last_refresh)),
            'redis': _redis_client is not None,
        })

    @rec_app.route('/api/recommend/cf/<int:user_id>', methods=['GET'])
    def api_cf(user_id: int):
        n = min(int(request.args.get('n', Config.DEFAULT_N)), Config.MAX_N)
        cache_key = f'rec:cf:{user_id}:{n}'
        cached = _cache_get(cache_key)
        if cached:
            return jsonify({'from_cache': True, 'algorithm': 'cf', 'user_id': user_id, 'recommendations': cached})
        result = recommend_cf(user_id, n)
        _cache_set(cache_key, result, Config.CACHE_TTL)
        return jsonify({'from_cache': False, 'algorithm': 'cf', 'user_id': user_id, 'recommendations': result})

    @rec_app.route('/api/recommend/svd/<int:user_id>', methods=['GET'])
    def api_svd(user_id: int):
        n = min(int(request.args.get('n', Config.DEFAULT_N)), Config.MAX_N)
        cache_key = f'rec:svd:{user_id}:{n}'
        cached = _cache_get(cache_key)
        if cached:
            return jsonify({'from_cache': True, 'algorithm': 'svd', 'user_id': user_id, 'recommendations': cached})
        result = recommend_svd(user_id, n)
        _cache_set(cache_key, result, Config.CACHE_TTL)
        return jsonify({'from_cache': False, 'algorithm': 'svd', 'user_id': user_id, 'recommendations': result})

    @rec_app.route('/api/recommend/hybrid/<int:user_id>', methods=['GET'])
    def api_hybrid(user_id: int):
        n = min(int(request.args.get('n', Config.DEFAULT_N)), Config.MAX_N)
        cf_w = float(request.args.get('cf_w', 0.4))
        svd_w = float(request.args.get('svd_w', 0.35))
        pop_w = float(request.args.get('pop_w', 0.25))
        cache_key = f'rec:hybrid:{user_id}:{n}:{cf_w}:{svd_w}:{pop_w}'
        cached = _cache_get(cache_key)
        if cached:
            return jsonify({'from_cache': True, 'algorithm': 'hybrid', 'user_id': user_id, 'recommendations': cached})
        result = recommend_hybrid(user_id, n, cf_w, svd_w, pop_w)
        _cache_set(cache_key, result, Config.CACHE_TTL)
        return jsonify({'from_cache': False, 'algorithm': 'hybrid', 'user_id': user_id, 'recommendations': result})

    @rec_app.route('/api/recommend/compare/<int:user_id>', methods=['GET'])
    def api_compare(user_id: int):
        n = min(int(request.args.get('n', Config.DEFAULT_N)), Config.MAX_N)
        cache_key = f'rec:cmp:{user_id}:{n}'
        cached = _cache_get(cache_key)
        if cached:
            return jsonify({'from_cache': True, **cached})
        result = compare_algorithms(user_id, n)
        _cache_set(cache_key, result, Config.CACHE_TTL)
        return jsonify({'from_cache': False, **result})

    @rec_app.route('/api/recommend/popular', methods=['GET'])
    def api_popular():
        n = min(int(request.args.get('n', Config.DEFAULT_N)), Config.MAX_N)
        cache_key = f'rec:popular:{n}'
        cached = _cache_get(cache_key)
        if cached:
            return jsonify({'from_cache': True, 'algorithm': 'popular', 'recommendations': cached})
        result = _popular_books(n)
        _cache_set(cache_key, result, Config.CACHE_TTL)
        return jsonify({'from_cache': False, 'algorithm': 'popular', 'recommendations': result})

    @rec_app.route('/api/admin/refresh', methods=['POST'])
    def api_refresh():
        ok = store.refresh()
        _mem_cache.invalidate('rec:')
        return jsonify({'success': ok, 'users': len(store.user_ids), 'books': len(store.book_ids)})

    @rec_app.route('/metrics', methods=['GET'])
    def api_metrics():
        """简易 Prometheus 风格指标"""
        lines = [
            f'recommend_users_total {len(store.user_ids)}',
            f'recommend_books_total {len(store.book_ids)}',
            f'recommend_ratings_total {store.global_rating_count}',
            f'recommend_avg_rating {store.avg_rating:.4f}',
        ]
        return Response('\n'.join(lines) + '\n', content_type='text/plain; charset=utf-8')

    # 启动时先加载一次，然后后台周期刷新
    store.refresh()
    _t = threading.Thread(target=_bg_refresh_loop, name='rec-refresh', daemon=True)
    _t.start()
    print(f'[RecommendService] 启动在 {Config.HOST}:{Config.PORT}')

    # 为了在被 import 时不自动启动服务器，仅当直接运行才启动
    if __name__ == '__main__':
        rec_app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)
