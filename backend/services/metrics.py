"""Prometheus 指标监控模块
- prometheus_client 可用时使用官方 Counter/Gauge/Histogram
- 缺失时使用本地字典降级，保证 /metrics 仍然可用（输出 text/plain 简易指标）
"""

import time
import threading
from typing import Optional

# 优先尝试使用 prometheus_client
_PROMETHEUS_AVAILABLE = False
try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        REGISTRY,
    )
    _PROMETHEUS_AVAILABLE = True
except Exception:
    _PROMETHEUS_AVAILABLE = False


class _LocalMetric:
    """简易降级指标容器（当 prometheus_client 不可用时使用）"""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters = {}
        self._gauges = {}
        self._histograms = {}

    def inc_counter(self, name, labels=None, value=1):
        with self._lock:
            key = (name, self._label_key(labels))
            self._counters[key] = self._counters.get(key, 0) + value

    def set_gauge(self, name, value, labels=None):
        with self._lock:
            key = (name, self._label_key(labels))
            self._gauges[key] = value

    def observe_histogram(self, name, value, labels=None):
        with self._lock:
            key = (name, self._label_key(labels))
            bucket = self._histograms.setdefault(key, {'count': 0, 'sum': 0.0, 'values': []})
            bucket['count'] += 1
            bucket['sum'] += value
            if len(bucket['values']) < 200:
                bucket['values'].append(value)

    @staticmethod
    def _label_key(labels):
        if not labels:
            return ''
        return ','.join(f'{k}={v}' for k, v in sorted(labels.items()))

    def render_text(self) -> bytes:
        """以 Prometheus text exposition 格式输出简易指标"""
        lines = []
        with self._lock:
            # Counters
            for (name, _), value in self._counters.items():
                lines.append(f'{name} {value}')
            # Gauges
            for (name, _), value in self._gauges.items():
                lines.append(f'{name} {value}')
            # Histograms -> 简化为 sum / count
            for (name, _), bucket in self._histograms.items():
                lines.append(f'{name}_count {bucket["count"]}')
                lines.append(f'{name}_sum {bucket["sum"]}')
        body = '\n'.join(lines) + '\n'
        return body.encode('utf-8')


_local = _LocalMetric()


# ========== 统一指标接口（上层代码无感） ==========

def http_request_total_inc(method: str, path: str, status: str):
    """HTTP 请求总数累加"""
    try:
        if _PROMETHEUS_AVAILABLE:
            _HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
        else:
            _local.inc_counter('http_requests_total',
                               labels={'method': method, 'path': path, 'status': status})
    except Exception:
        pass


def http_request_duration_observe(method: str, path: str, seconds: float):
    """HTTP 请求耗时记录"""
    try:
        if _PROMETHEUS_AVAILABLE:
            _HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(seconds)
        else:
            _local.observe_histogram('http_request_duration_seconds', seconds,
                                       labels={'method': method, 'path': path})
    except Exception:
        pass


def cache_hit_inc():
    try:
        if _PROMETHEUS_AVAILABLE:
            _CACHE_HIT.inc()
        else:
            _local.inc_counter('cache_hit_total')
    except Exception:
        pass


def cache_miss_inc():
    try:
        if _PROMETHEUS_AVAILABLE:
            _CACHE_MISS.inc()
        else:
            _local.inc_counter('cache_miss_total')
    except Exception:
        pass


def sample_db_pool(db_engine=None) -> Optional[dict]:
    """采样数据库连接池状态。返回 size/active 字典，供 Prometheus 上报或日志使用。"""
    info = {'size': 0, 'active': 0, 'checked': False}
    try:
        if db_engine is not None:
            pool = getattr(db_engine, 'pool', None)
            if pool is not None:
                try:
                    size = getattr(pool, 'size()', None)
                    if callable(size):
                        info['size'] = size()
                    else:
                        info['size'] = int(getattr(pool, '_pool', None) and len(pool._pool) or 0)
                    # SQLAlchemy QueuePool 没有直接的 active API，通过 status() 推断
                    checkedout = getattr(pool, 'checkedout()', None)
                    if callable(checkedout):
                        info['active'] = checkedout()
                    else:
                        info['active'] = int(getattr(pool, '_checked_out', 0))
                    info['checked'] = True
                except Exception:
                    pass
        if _PROMETHEUS_AVAILABLE:
            _DB_POOL_SIZE.set(int(info.get('size', 0)))
            _DB_POOL_ACTIVE.set(int(info.get('active', 0)))
        else:
            _local.set_gauge('db_pool_size', int(info.get('size', 0)))
            _local.set_gauge('db_pool_active', int(info.get('active', 0)))
    except Exception:
        pass
    return info


# ========== prometheus_client 指标定义（try/except 防重复注册） ==========
_HTTP_REQUESTS_TOTAL = None
_HTTP_REQUEST_DURATION = None
_CACHE_HIT = None
_CACHE_MISS = None
_DB_POOL_SIZE = None
_DB_POOL_ACTIVE = None

if _PROMETHEUS_AVAILABLE:
    try:
        _HTTP_REQUESTS_TOTAL = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'path', 'status']
        )
    except Exception:
        try:
            _HTTP_REQUESTS_TOTAL = REGISTRY._names_to_collectors.get('http_requests_total')
        except Exception:
            _HTTP_REQUESTS_TOTAL = None

    try:
        _HTTP_REQUEST_DURATION = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'path']
        )
    except Exception:
        try:
            _HTTP_REQUEST_DURATION = REGISTRY._names_to_collectors.get('http_request_duration_seconds')
        except Exception:
            _HTTP_REQUEST_DURATION = None

    try:
        _CACHE_HIT = Counter('cache_hit_total', 'Total cache hits')
    except Exception:
        try:
            _CACHE_HIT = REGISTRY._names_to_collectors.get('cache_hit_total')
        except Exception:
            _CACHE_HIT = None

    try:
        _CACHE_MISS = Counter('cache_miss_total', 'Total cache misses')
    except Exception:
        try:
            _CACHE_MISS = REGISTRY._names_to_collectors.get('cache_miss_total')
        except Exception:
            _CACHE_MISS = None

    try:
        _DB_POOL_SIZE = Gauge('db_pool_size', 'DB pool total size')
    except Exception:
        try:
            _DB_POOL_SIZE = REGISTRY._names_to_collectors.get('db_pool_size')
        except Exception:
            _DB_POOL_SIZE = None

    try:
        _DB_POOL_ACTIVE = Gauge('db_pool_active', 'DB pool active (checked-out) connections')
    except Exception:
        try:
            _DB_POOL_ACTIVE = REGISTRY._names_to_collectors.get('db_pool_active')
        except Exception:
            _DB_POOL_ACTIVE = None


# ========== 指标输出 /metrics 路由内容 ==========

def render_metrics() -> bytes:
    """获取当前指标内容（bytes），用于 /metrics 路由响应体"""
    try:
        if _PROMETHEUS_AVAILABLE:
            return generate_latest(REGISTRY)
    except Exception:
        pass
    return _local.render_text()


def metrics_content_type() -> str:
    if _PROMETHEUS_AVAILABLE:
        return CONTENT_TYPE_LATEST
    return 'text/plain; charset=utf-8'


# ========== Flask 中间件封装 ==========

def register_metrics_middleware(app, db_engine=None):
    """注册 before_request / after_request 钩子，以及定期采样 DB 池状态"""
    try:
        @app.before_request
        def _metrics_before_request():
            try:
                from flask import request as _req
                _req._metrics_start_time = time.time()
            except Exception:
                pass

        @app.after_request
        def _metrics_after_request(response):
            try:
                from flask import request as _req
                start = getattr(_req, '_metrics_start_time', None)
                method = _req.method or 'GET'
                path = _req.path or '/'
                status = str(getattr(response, 'status_code', 0))
                if start is not None:
                    http_request_duration_observe(method, path, time.time() - start)
                http_request_total_inc(method, path, status)
            except Exception:
                pass
            return response

        # 启动一个后台线程，定期采样 DB 连接池状态（简单实现，不依赖定时任务框架）
        if db_engine is not None:
            def _sampler_loop():
                while True:
                    try:
                        sample_db_pool(db_engine)
                    except Exception:
                        pass
                    time.sleep(15)

            try:
                t = threading.Thread(target=_sampler_loop, name='metrics-db-pool-sampler', daemon=True)
                t.start()
            except Exception:
                pass
    except Exception:
        pass


# ========== 在缓存层接入 cache_hit / cache_miss 的便捷方法 ==========

def wrap_cache_get(original_get):
    """装饰 CacheService.get()，在读取时触发 hit/miss 指标。"""
    def wrapper(self, key):
        try:
            value = original_get(self, key)
            if value is not None:
                cache_hit_inc()
            else:
                cache_miss_inc()
            return value
        except Exception:
            return original_get(self, key)
    return wrapper
