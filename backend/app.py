import os
import time
import logging
import random
import hashlib
from logging.handlers import RotatingFileHandler
from flask import Flask, send_from_directory, send_file, request, jsonify, Response, g
from flask_cors import CORS
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from extensions import db
from sqlalchemy import text
from services.middleware import (
    request_id_middleware, rate_limit_middleware, inject_headers,
    get_structured_logger, get_circuit_breaker,
)

# 尝试导入 JWT（可选）
try:
    from flask_jwt_extended import JWTManager
    _JWT_AVAILABLE = True
except Exception:
    JWTManager = None
    _JWT_AVAILABLE = False

# 尝试导入 metrics 模块（缺失时静默降级）
try:
    from services import metrics as _metrics
    _METRICS_AVAILABLE = True
except Exception:
    _metrics = None
    _METRICS_AVAILABLE = False

# ========== 统一响应包装器 ==========
def ok(data=None, message=None, status=200):
    """成功响应统一格式"""
    resp = {'success': True}
    if data is not None:
        resp.update(data) if isinstance(data, dict) else resp.update({'data': data})
    if message:
        resp['message'] = message
    return jsonify(resp), status


def err(message, status=400, details=None):
    """错误响应统一格式"""
    resp = {'success': False, 'error': message}
    if details:
        resp['details'] = details
    return jsonify(resp), status


def task_result_template(task_type, user_id=None, success=True, data=None, error=None):
    """统一任务返回结构"""
    return {
        'task_type': task_type,
        'user_id': user_id,
        'success': success,
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'data': data or {},
        'error': error,
    }


def create_app():
    # 优先使用 ./static 作为前端静态文件目录
    static_folder = getattr(Config, 'STATIC_FOLDER', None)
    app = Flask(
        __name__,
        static_folder=static_folder if os.path.isdir(static_folder) else None,
        static_url_path='/'
    )
    app.config.from_object(Config)

    db.init_app(app)

    # ========== MySQL 连接池预热 ==========
    try:
        warmup_count = app.config.get('POOL_WARMUP_COUNT', 3)
        if warmup_count and warmup_count > 0:
            with app.app_context():
                try:
                    # 先释放旧连接，确保从干净状态开始
                    try:
                        db.engine.dispose()
                    except Exception:
                        pass
                    warmed = 0
                    for i in range(warmup_count):
                        try:
                            conn = db.engine.connect()
                            # 执行一次简单查询，确保连接真的可用
                            conn.execute(text("SELECT 1"))
                            conn.close()
                            warmed += 1
                        except Exception as inner_e:
                            app.logger.warning(f'[PoolWarmup] 第{i+1}个连接预热失败: {inner_e}')
                            continue
                    app.logger.info(f'[PoolWarmup] 连接池预热完成: {warmed}/{warmup_count}')
                except Exception as e:
                    app.logger.warning(f'[PoolWarmup] 预热过程异常: {e}')
    except Exception as e:
        # 预热失败不阻塞启动
        app.logger.warning(f'[PoolWarmup] 预热跳过: {e}')

    CORS(app, origins=Config.CORS_ORIGINS)

    # ========== JWT 认证 ==========
    if _JWT_AVAILABLE:
        try:
            jwt_mgr = JWTManager(app)

            @jwt_mgr.expired_token_loader
            def _on_expired(jwt_header, jwt_payload):
                return jsonify({'success': False, 'error': 'Token 已过期'}), 401

            @jwt_mgr.invalid_token_loader
            def _on_invalid(reason):
                return jsonify({'success': False, 'error': f'Token 无效: {reason}'}), 401

            @jwt_mgr.unauthorized_loader
            def _on_unauth(reason):
                return jsonify({'success': False, 'error': '缺少 Token'}), 401

            app.logger.info('[JWT] flask-jwt-extended 已注册')
        except Exception as e:
            app.logger.warning(f'[JWT] 注册失败，将使用 fallback token: {e}')
    else:
        app.logger.info('[JWT] flask-jwt-extended 未安装，使用 fallback token')

    # ========== 压缩（可选，失败不阻塞） ==========
    try:
        Compress(app)
    except Exception:
        pass

    # ========== 统一 before_request / after_request ==========
    @app.before_request
    def _before():
        request._start_time = time.time()
        request_id_middleware()
        # 限流（读/写分别分级）
        rl = rate_limit_middleware()
        if rl is not None:
            return rl
        if request.path.startswith('/api/'):
            try:
                app.logger.info(f'[REQ] {request.method} {request.path} from {request.remote_addr}')
            except Exception:
                pass

    @app.after_request
    def _after(response):
        response = inject_headers(response)
        # GET 请求增加 Cache-Control + ETag（静态聚合页）
        if request.method == 'GET' and response.status_code < 400:
            path = request.path
            if path in ('/api/home', '/api/books/categories',
                        '/api/books/filters', '/api/books/hot-search'):
                response.headers['Cache-Control'] = 'public, max-age=300, stale-while-revalidate=600'
                try:
                    body = response.get_data(as_text=False) or b''
                    if body:
                        etag = '"' + hashlib.md5(body).hexdigest()[:16] + '"'
                        inm = request.headers.get('If-None-Match')
                        if inm and etag in inm:
                            response.status_code = 304
                            response.set_data(b'')
                        else:
                            response.headers['ETag'] = etag
                except Exception:
                    pass
        return response

    # ========== Prometheus 指标监控 ==========
    # 在 app context 中注册 metrics（db.engine 需要 context）
    try:
        with app.app_context():
            engine_for_metrics = db.engine
    except Exception:
        engine_for_metrics = None

    try:
        if _METRICS_AVAILABLE:
            _metrics.register_metrics_middleware(app, db_engine=engine_for_metrics)
            app.logger.info('[Metrics] 监控中间件已注册')

            @app.route('/metrics')
            def _metrics_route():
                try:
                    body = _metrics.render_metrics()
                    ctype = _metrics.metrics_content_type()
                    return Response(body, mimetype=ctype)
                except Exception as e:
                    app.logger.warning(f'[Metrics] /metrics 渲染失败: {e}')
                    return Response(f'# error: {e}\n', mimetype='text/plain; charset=utf-8')
        else:
            # prometheus_client 不可用时，提供一个最小化 /metrics 响应
            @app.route('/metrics')
            def _metrics_route():
                return Response('# prometheus_client not installed\n',
                                mimetype='text/plain; charset=utf-8')
            app.logger.info('[Metrics] prometheus_client 未安装，使用降级模式')
    except Exception as e:
        # 兜底：即便 metrics 中间件注册失败，仍暴露 /metrics 路由
        app.logger.warning(f'[Metrics] 注册失败: {e}')
        try:
            @app.route('/metrics')
            def _metrics_route_fallback():
                from flask import current_app
                app_name = getattr(current_app, 'name', 'app')
                body = [
                    f'# TYPE http_requests_total counter',
                    f'http_requests_total{{app="{app_name}",note="fallback"}} 0',
                ]
                return Response('\n'.join(body) + '\n', mimetype='text/plain; charset=utf-8')
        except Exception:
            pass
    
    # ========== 推荐引擎预热（后台线程，不阻塞启动） ==========
    try:
        from routes.recommend import prewarm_recommend_engines
        prewarm_recommend_engines(app=app, n_top_users=20, n_rec=5)
    except Exception as e:
        app.logger.warning(f'[Prewarm] 推荐引擎预热调度失败: {e}')

    # ========== FAISS 索引预热（后台构建，不阻塞启动） ==========
    def _build_faiss_bg():
        try:
            import time as _time
            _time.sleep(5)  # 等引擎预热完成后再开始构建索引
            with app.app_context():
                from services.embedding_service import get_embedding_service
                svc = get_embedding_service()
                n = svc.build_index_from_db(limit=20000)  # 先构建 2 万本
                app.logger.info(f'[FAISS] 索引构建完成，共 {n} 本书，size={svc.index_size}')
        except Exception as e:
            app.logger.warning(f'[FAISS] 索引构建失败: {e}')

    import threading as _th
    _th.Thread(target=_build_faiss_bg, daemon=True, name='faiss-index-build').start()

    # ========== 首页聚合 API ==========
    @app.route('/api/home', methods=['GET'])
    def _home_api():
        """首页聚合接口：一次性返回热门搜索、热门书籍、分类

        前端用 5 分钟浏览器缓存 + ETag 复用，减少重复请求
        """
        try:
            from routes.books import (
                _hot_search_terms, _HISTORY_MAX_TERM_LEN, _add_history, _get_history
            )
            from models import Book, Rating
            from extensions import db
            from sqlalchemy import func

            # 1) 热门搜索词
            hot_search = list(_hot_search_terms[:10])

            # 2) 热门书籍（JOIN 聚合评分）
            hot_limit = request.args.get('limit', 10, type=int)
            hot_limit = max(1, min(50, hot_limit))
            try:
                rows = db.session.query(
                    Book.id, Book.title, Book.author, Book.category, Book.year,
                    func.count(Rating.id).label('rating_count'),
                    func.avg(Rating.rating).label('avg_rating')
                ).join(Rating, Rating.book_id == Book.id, isouter=True).group_by(Book.id).order_by(
                    func.count(Rating.id).desc()
                ).limit(hot_limit).all()
                hot_books = []
                for r in rows:
                    b = {
                        'id': r.id, 'title': r.title, 'author': r.author,
                        'category': r.category, 'year': r.year,
                        'rating_count': r.rating_count or 0,
                        'avg_rating': round(float(r.avg_rating), 1) if r.avg_rating else None,
                    }
                    hot_books.append(b)
            except Exception:
                # 降级：只查 Book 表（不关联评分）
                hot_books = [{'id': b.id, 'title': b.title, 'author': b.author,
                               'category': b.category, 'year': b.year}
                              for b in Book.query.limit(hot_limit).all()]

            # 3) 分类列表（去重）
            try:
                cat_rows = db.session.query(Book.category).filter(
                    Book.category.isnot(None), Book.category != ''
                ).distinct().order_by(Book.category).all()
                categories = [c[0] for c in cat_rows if c and c[0]]
            except Exception:
                categories = []

            # 4) 用户当前搜索历史（可选）
            user_id = request.args.get('user_id', type=int)
            recent_history = None
            if user_id:
                try:
                    recent_history = _get_history(user_id)
                except Exception:
                    recent_history = []

            return jsonify({
                'success': True,
                'hot_search': hot_search,
                'hot_books': hot_books,
                'categories': categories,
                'recent_history': recent_history,
                'generated_at': int(time.time()),
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ========== 健康检查 / 版本 ==========
    @app.route('/api/health', methods=['GET'])
    def _health():
        try:
            from extensions import db as _health_db
            _health_db.engine.execute(text('SELECT 1'))
            db_ok = True
        except Exception:
            db_ok = False
        return jsonify({'success': True, 'db': db_ok, 'time': time.time()})

    @app.route('/api/version', methods=['GET'])
    def _version():
        return jsonify({'success': True, 'version': '1.0.0'})

    # ========== API 性能优化 ==========
    # 响应压缩
    try:
        Compress(app)
    except:
        pass
    
    # 请求限流（Redis 不可用时使用内存）
    try:
        import redis
        test_redis = redis.Redis(
            host=app.config.get('REDIS_HOST', 'localhost'),
            port=app.config.get('REDIS_PORT', 6379),
            password=app.config.get('REDIS_PASSWORD') or None,
            db=app.config.get('REDIS_DB', 0),
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        test_redis.ping()
        storage_uri = app.config.get('RATELIMIT_STORAGE_URL')
    except Exception:
        # Redis 不可用，使用内存存储
        storage_uri = "memory://"
        app.logger.warning('[Limiter] Redis 不可用，使用内存限流')
    
    try:
        limiter = Limiter(
            key_func=get_remote_address,
            app=app,
            default_limits=[app.config.get('RATELIMIT_DEFAULT', '200/minute')],
            storage_uri=storage_uri,
            strategy=app.config.get('RATELIMIT_STRATEGY', 'fixed-window'),
            headers_enabled=app.config.get('RATELIMIT_HEADERS_ENABLED', True)
        )
        # 注册写操作专用限流策略
        _WRITE_LIMIT = app.config.get('RATELIMIT_WRITE', '60/minute')
        _AI_LIMIT = app.config.get('RATELIMIT_AI', '30/minute')
        _AUTH_LIMIT = app.config.get('RATELIMIT_AUTH', '10/minute')

        # 记录到 app 配置里供路由层使用
        app.config['_WRITE_LIMIT'] = _WRITE_LIMIT
        app.config['_AI_LIMIT'] = _AI_LIMIT
        app.config['_AUTH_LIMIT'] = _AUTH_LIMIT
        # 保存 limiter 实例引用供路由层使用
        app.extensions['limiter'] = limiter
    except Exception:
        limiter = None
    
    # ========== 日志规范化：控制台 + 旋转文件 ==========
    log_dir = app.config.get('LOG_DIR')
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        pass

    log_level_name = app.config.get('LOG_LEVEL', 'INFO')
    log_level = getattr(logging, log_level_name, logging.INFO)
    app.logger.setLevel(log_level)

    # 移除Flask默认handler避免重复
    for h in list(app.logger.handlers):
        app.logger.removeHandler(h)

    fmt = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台日志
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(fmt)
    app.logger.addHandler(ch)

    # 文件日志（5MB * 5份）
    try:
        fh = RotatingFileHandler(
            os.path.join(log_dir, 'app.log'),
            maxBytes=app.config.get('LOG_MAX_BYTES', 5 * 1024 * 1024),
            backupCount=app.config.get('LOG_BACKUP_COUNT', 5),
            encoding='utf-8'
        )
        fh.setLevel(log_level)
        fh.setFormatter(fmt)
        app.logger.addHandler(fh)
    except Exception:
        pass

    app.logger.info(f'[app] 日志初始化完成 level={log_level_name}')
    
    # 初始化缓存服务
    from services.cache import cache_service
    cache_service.init_app(app)

    # 延迟导入模型和路由
    from models import User, Book, Rating

    from routes.auth import auth_bp
    from routes.books import books_bp
    from routes.ratings import ratings_bp
    from routes.recommend import recommend_bp
    from routes.reviews import reviews_bp
    from routes.social import social_bp

    # 为不同模块设置分级限流
    _auth_hits = {}
    _ai_hits = {}

    @auth_bp.before_request
    def _auth_rate_limit():
        # 认证接口：10次/分钟（防爆破）
        key = f'auth:{get_remote_address()}'
        now = int(time.time())
        _auth_hits[key] = _auth_hits.get(key, []) + [now]
        _auth_hits[key] = [t for t in _auth_hits[key] if now - t < 60]
        if len(_auth_hits[key]) > 10:
            return err('Too many auth attempts', status=429, details={'limit': '10/min'})

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(books_bp, url_prefix='/api/books')
    app.register_blueprint(ratings_bp, url_prefix='/api/ratings')
    app.register_blueprint(recommend_bp, url_prefix='/api/recommend')
    app.register_blueprint(reviews_bp, url_prefix='/api/reviews')
    app.register_blueprint(social_bp, url_prefix='/api/social')

    # === AI 内容创作助手模块 ===
    try:
        from ai.routes import ai_bp, init_ai_module

        @ai_bp.before_request
        def _ai_rate_limit():
            # AI接口：30次/分钟（昂贵操作）
            key = f'ai:{get_remote_address()}'
            now = int(time.time())
            _ai_hits[key] = _ai_hits.get(key, []) + [now]
            _ai_hits[key] = [t for t in _ai_hits[key] if now - t < 60]
            if len(_ai_hits[key]) > 30:
                return err('AI rate limit exceeded', status=429, details={'limit': '30/min'})

        app.register_blueprint(ai_bp, url_prefix='/api/ai')
        init_ai_module()

        # 初始化 AI 相关数据库表
        with app.app_context():
            try:
                from ai.models import init_ai_db
                init_ai_db()
            except Exception as e:
                app.logger.warning(f'[AI] DB init: {e}')
    except Exception as e:
        app.logger.warning(f'[AI] module load: {e}')

    # ========== v2.0 推荐中心入口页 ==========
    @app.route('/recommend-center')
    def recommend_center_v2():
        rc_path = os.path.join(static_folder, 'recommend-center.html')
        if os.path.isfile(rc_path):
            return send_file(rc_path)
        return ('recommend-center.html 不存在', 404)

    # ========== Celery 异步任务初始化 ==========
    celery = None  # 默认为 None，表示 celery worker 未启动
    try:
        from celery_config import make_celery
        celery = make_celery(app)
        app.celery = celery  # 暴露给 celery worker 启动时使用
        app.logger.info('[Celery] 初始化完成')

        # 注册异步任务
        @celery.task(name='tasks.calc_recommend', bind=True)
        def calc_recommend_task(self, user_id, n=10):
            """异步计算推荐结果"""
            try:
                from services.cf_algorithm import CollaborativeFiltering
                engine = CollaborativeFiltering()
                recs = engine.user_based_recommend(user_id, n_recommendations=n)

                # 取完整书籍信息
                from models import Book
                result = []
                for rec in recs:
                    book = Book.query.get(rec['book_id'])
                    if book:
                        d = book.to_dict()
                        d['predicted_rating'] = rec['predicted_rating']
                        result.append(d)

                return task_result_template('recommend', user_id=user_id, success=True,
                                            data={'recommendations': result, 'count': len(result)})
            except Exception as e:
                return task_result_template('recommend', user_id=user_id, success=False,
                                            error=str(e))

        @celery.task(name='tasks.update_hot_books', bind=True)
        def update_hot_books_task(self, limit=20):
            """异步更新热门书籍（可定时触发）"""
            try:
                from models import Book, Rating
                from sqlalchemy import func
                hot_books = db.session.query(
                    Book.id, Book.title, Book.author,
                    func.count(Rating.id).label('rating_count'),
                    func.avg(Rating.rating).label('avg_rating')
                ).join(Rating).group_by(Book.id).order_by(
                    func.count(Rating.id).desc(),
                    func.avg(Rating.rating).desc()
                ).limit(limit).all()

                books_data = [{
                    'id': b.id, 'title': b.title, 'author': b.author,
                    'rating_count': b.rating_count,
                    'avg_rating': round(float(b.avg_rating), 1) if b.avg_rating else None
                } for b in hot_books]

                # 写入缓存
                try:
                    from services.cache import cache_service
                    cache_service.set('hot_books_async', books_data, ttl=3600)
                except Exception:
                    pass

                return task_result_template('hot_books', success=True,
                                            data={'books': books_data, 'count': len(books_data)})
            except Exception as e:
                return task_result_template('hot_books', success=False, error=str(e))

        @celery.task(name='tasks.rebuild_profile', bind=True)
        def rebuild_profile_task(self, user_id):
            """异步重建用户画像"""
            try:
                from models import User, Rating, Book
                user = User.query.get(user_id)
                if not user:
                    return task_result_template('profile', user_id=user_id,
                                                success=False, error='User not found')

                ratings = Rating.query.filter_by(user_id=user_id).all()
                profile = {
                    'user_id': user_id,
                    'username': user.username,
                    'total_ratings': len(ratings),
                    'avg_rating': round(
                        sum(r.rating for r in ratings) / len(ratings), 2
                    ) if ratings else 0,
                }

                try:
                    from services.cache import cache_service
                    cache_service.set(f'user_profile:{user_id}', profile, ttl=3600)
                except Exception:
                    pass

                return task_result_template('profile', user_id=user_id, success=True,
                                            data=profile)
            except Exception as e:
                return task_result_template('profile', user_id=user_id, success=False,
                                            error=str(e))

        app.logger.info('[Celery] 任务注册完成: calc_recommend, update_hot_books, rebuild_profile')
    except Exception as e:
        app.logger.warning(f'[Celery] 初始化跳过: {e}')

    # ========== 异步任务 API 端点 ==========
    try:
        from flask import Blueprint
        tasks_bp = Blueprint('tasks', __name__)

        @tasks_bp.route('/recommend/async', methods=['POST'])
        def async_recommend():
            """发起异步推荐计算
            POST /api/tasks/recommend/async
            body: {user_id: 8, n: 10}
            """
            if not celery:
                return err('Celery 未启动（请先启动 celery worker）', status=503)
            data = request.get_json() or {}
            user_id = data.get('user_id')
            n = int(data.get('n', 10))
            if not user_id:
                return err('需要 user_id')
            if n < 1 or n > 50:
                n = 10

            try:
                task = calc_recommend_task.apply_async(args=[user_id, n], queue='recommend')
                return ok({
                    'task_id': task.id,
                    'user_id': user_id,
                    'n': n,
                    'status_url': f'/api/tasks/{task.id}'
                }, status=202)
            except Exception as e:
                return err(f'异步任务队列不可用: {e}', status=503)

        @tasks_bp.route('/hot-books/async', methods=['POST'])
        def async_hot_books():
            """发起异步热门书籍更新"""
            if not celery:
                return err('Celery 未启动', status=503)
            data = request.get_json() or {}
            limit = int(data.get('limit', 20))
            if limit < 1 or limit > 100:
                limit = 20

            try:
                task = update_hot_books_task.apply_async(args=[limit], queue='default')
                return ok({
                    'task_id': task.id,
                    'limit': limit,
                    'status_url': f'/api/tasks/{task.id}'
                }, status=202)
            except Exception as e:
                return err(f'异步任务队列不可用: {e}', status=503)

        @tasks_bp.route('/profile/async', methods=['POST'])
        def async_profile():
            """发起异步用户画像重建"""
            if not celery:
                return err('Celery 未启动', status=503)
            data = request.get_json() or {}
            user_id = data.get('user_id')
            if not user_id:
                return err('需要 user_id')

            try:
                task = rebuild_profile_task.apply_async(args=[user_id], queue='default')
                return ok({
                    'task_id': task.id,
                    'user_id': user_id,
                    'status_url': f'/api/tasks/{task.id}'
                }, status=202)
            except Exception as e:
                return err(f'异步任务队列不可用: {e}', status=503)

        @tasks_bp.route('/<task_id>', methods=['GET'])
        def task_status(task_id):
            """查询任务状态"""
            if not celery:
                return err('Celery 未启动', status=503)
            try:
                task = celery.AsyncResult(task_id)
                state_info = {
                    'task_id': task.id,
                    'state': task.state,  # PENDING / STARTED / SUCCESS / FAILURE / RETRY
                }

                if task.state == 'SUCCESS':
                    state_info['result'] = task.result
                elif task.state == 'FAILURE':
                    try:
                        state_info['error'] = str(task.info) if task.info else 'unknown'
                    except Exception:
                        state_info['error'] = 'task failed'
                elif task.state == 'STARTED':
                    state_info['started_at'] = task.info.get('start_time') if task.info else None

                return ok(state_info, status=200)
            except Exception as e:
                return err(f'查询任务状态失败: {e}', status=503)

        @tasks_bp.route('/<task_id>', methods=['DELETE'])
        def task_cancel(task_id):
            """取消任务"""
            if not celery:
                return err('Celery 未启动', status=503)
            try:
                task = celery.AsyncResult(task_id)
                if task.state in ('PENDING', 'STARTED', 'RETRY'):
                    task.revoke(terminate=True)
                    return ok({'task_id': task.id, 'revoked': True})
                return err('任务已完成或不存在', status=400)
            except Exception as e:
                return err(f'取消任务失败: {e}', status=503)

        @tasks_bp.route('/health', methods=['GET'])
        def tasks_health():
            """异步任务健康检查"""
            return ok({
                'celery_available': celery is not None,
                'queues': ['default', 'recommend', 'ai'],
                'endpoints': {
                    'recommend_async': 'POST /api/tasks/recommend/async',
                    'hot_books_async': 'POST /api/tasks/hot-books/async',
                    'profile_async': 'POST /api/tasks/profile/async',
                    'task_status': 'GET /api/tasks/<task_id>',
                    'task_cancel': 'DELETE /api/tasks/<task_id>',
                }
            })

        app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
        app.logger.info('[Celery] 异步任务 API 已注册: /api/tasks/*')
    except Exception as e:
        app.logger.warning(f'[Celery] API 端点注册跳过: {e}')

    # 健康检查与版本（下方有更详细的实现，此处保留占位以免编译报错）

    # ========== 请求日志 + 响应头 + 统一错误处理 ==========
    @app.before_request
    def log_request():
        request._start_time = time.time()
        if request.path.startswith('/api/'):
            app.logger.info(f'[REQ] {request.method} {request.path} from {request.remote_addr}')

    @app.after_request
    def add_response_headers(response):
        elapsed = getattr(request, '_start_time', None)
        if elapsed:
            try:
                response.headers['X-Response-Time'] = f'{(time.time() - elapsed) * 1000:.0f}ms'
            except Exception:
                pass

        if request.path.startswith('/api/'):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'

            # GET / HEAD 静态/可缓存 API：添加 Cache-Control
            if request.method in ('GET', 'HEAD') and response.status_code < 400:
                path = request.path
                if path in ('/api/home', '/api/books/categories', '/api/books/filters', '/api/books/hot-search'):
                    # 静态聚合页：浏览器 5 分钟、CDN 30 分钟、允许复用
                    response.headers['Cache-Control'] = 'public, max-age=300, s-maxage=1800, stale-while-revalidate=600'
                    if hasattr(response, 'get_data'):
                        try:
                            body = response.get_data(as_text=False) or b''
                            if body:
                                import hashlib
                                etag = '"' + hashlib.md5(body).hexdigest()[:16] + '"'
                                response.headers['ETag'] = etag
                                # 支持 If-None-Match 304
                                inm = request.headers.get('If-None-Match')
                                if inm and etag in inm:
                                    response.status_code = 304
                                    response.set_data(b'')
                        except Exception:
                            pass
                elif path.startswith('/api/books/') and path != '/api/books/':
                    # 具体书籍详情：浏览器 1 分钟
                    response.headers['Cache-Control'] = 'public, max-age=60'
                else:
                    # 默认：不缓存
                    response.headers['Cache-Control'] = 'no-store, private'

            if response.status_code >= 400:
                try:
                    app.logger.warning(f'[RSP] {request.method} {request.path} status={response.status_code}')
                except Exception:
                    pass
        return response

    @app.errorhandler(404)
    def _not_found(error):
        if request.path.startswith('/api/'):
            return err('API endpoint not found', status=404, details={'path': request.path})
        return error

    @app.errorhandler(500)
    def _internal_error(error):
        app.logger.error(f'[500] {request.method} {request.path}: {error}')
        if request.path.startswith('/api/'):
            return err('Internal server error', status=500)
        return error

    @app.errorhandler(429)
    def _ratelimit_handler(error):
        if request.path.startswith('/api/'):
            return err('Rate limit exceeded', status=429,
                       details={'limit': str(getattr(error, 'description', 'unknown'))})
        return error

    # === 前端静态文件路由 ===
    # 策略：凡是 /api/ 开头的由后端处理；
    # 其它请求交给前端（包括不存在的静态文件、路由 404 交给前端 SPA
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        """支持 Vue Router history 模式

        1) 如果 static_folder 配置不存在：返回说明信息
        2) 如果请求的是具体的静态资源文件：直接返回
        3) 否则返回 index.html（交给前端路由
        """
        # 如果是 /api/ 开头的请求，不应该到这里来（已由 blueprint 处理）
        # 但为了安全起见，明确拒绝
        if path and path.startswith('api/'):
            return {'success': False, 'error': 'API endpoint not found'}, 404

        if not static_folder or not os.path.isdir(static_folder):
            return ('未找到前端构建文件，请先运行 build_frontend.py 脚本', 404)

        # 1) 如果是具体文件（如 assets/xxx.js, favicon.ico)，直接返回
        if path:
            target_file = os.path.join(static_folder, path)
            if os.path.isfile(target_file):
                return send_file(target_file)

        # 2) 其他所有情况返回 index.html（由前端路由处理）
        index_path = os.path.join(static_folder, 'index.html')
        if os.path.isfile(index_path):
            return send_file(index_path)
        return ('index.html 不存在，请重新构建前端', 404)

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()

    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = (os.environ.get('FLASK_ENV') == 'development' or
             os.environ.get('FLASK_DEBUG') == '1')

    # 优先使用 waitress（生产级WSGI服务器），不可用则回退到Flask自带
    try:
        from waitress import serve
        threads = int(os.environ.get('WAITRESS_THREADS', 8))
        app.logger.info(f'[app] 使用 waitress 启动: {host}:{port} (threads={threads})')
        serve(app, host=host, port=port, threads=threads)
    except Exception as e:
        app.logger.warning(f'[app] waitress不可用({e})，回退到Flask开发服务器')
        app.run(debug=debug, port=port, host=host)
