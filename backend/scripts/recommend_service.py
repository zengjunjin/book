"""独立推荐服务 HTTP 网关
独立入口：cd backend && python scripts/recommend_service.py

让推荐引擎独立为一个可部署的微服务进程，在独立端口启动。
不依赖现有 app.py 的路由系统。
"""
import sys
import os
import time
import threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
from flask_cors import CORS

from config import Config as _DefaultConfig
from extensions import db
from services.cache import cache_service

# 预热推荐引擎
from routes.recommend import recommend_bp, prewarm_recommend_engines


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(config or _DefaultConfig())
    db.init_app(app)
    cache_service.init_app(app)

    # ========== 连接池预热 ==========
    try:
        with app.app_context():
            try:
                db.engine.dispose()
            except Exception:
                pass
            try:
                from sqlalchemy import text
                db.engine.connect().execute(text('SELECT 1')).close()
            except Exception:
                pass
        app.logger.info('[PoolWarmup] 数据库连接已预热')
    except Exception as e:
        print(f'[PoolWarmup] 预热跳过: {e}')

    # ========== 推荐引擎预热 ==========
    try:
        prewarm_recommend_engines(app=app, n_top_users=20, n_rec=5)
    except Exception as e:
        print(f'[Prewarm] 推荐引擎预热调度失败: {e}')

    CORS(app)

    app.register_blueprint(recommend_bp)

    @app.before_request
    def _log_req():
        request._start_time = time.time()

    @app.after_request
    def _add_headers(response):
        elapsed = getattr(request, '_start_time', None)
        if elapsed:
            try:
                response.headers['X-Response-Time'] = f'{(time.time() - elapsed) * 1000:.0f}ms'
            except Exception:
                pass
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.route('/api/recommend/health', methods=['GET'])
    def _health():
        return jsonify({'success': True, 'service': 'recommend', 'time': time.time()})

    return app


if __name__ == '__main__':
    port = int(os.environ.get('RECOMMEND_PORT', 5001))
    app = create_app()
    print(f'[RecommendService] 启动于 http://127.0.0.1:{port}')
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
