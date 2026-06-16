"""
统一中间件：令牌桶限流 + 熔断器 + 结构化日志
---------------------------------------------
- TokenBucket：纯 Python 实现，无需额外依赖，支持 per-IP + per-endpoint 分级
- CircuitBreaker：简易熔断器（失败次数超过阈值则打开，半开时允许探测）
- StructuredLogger：JSON 结构化日志，便于 ELK/Grafana/Loki 采集
"""
import time
import json
import threading
import functools
import logging
from collections import defaultdict, deque
from flask import request, jsonify, g, current_app


# ========== 令牌桶（每 IP 每 endpoint 独立） ==========
class TokenBucket:
    """纯 Python 令牌桶：capacity 令牌，refill_per_second 每秒补充"""

    def __init__(self, capacity=60, refill_per_second=1.0):
        self.capacity = float(capacity)
        self.refill_per_second = float(refill_per_second)
        self._tokens = float(capacity)
        self._last_ts = time.time()
        self._lock = threading.Lock()

    def take(self, n=1):
        with self._lock:
            now = time.time()
            elapsed = now - self._last_ts
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_second)
            self._last_ts = now
            if self._tokens >= n:
                self._tokens -= n
                return True
            return False


# 全局桶注册表：key = (remote_addr, method, path_prefix)
_BUCKETS_LOCK = threading.Lock()
_BUCKETS = {}

# 不同接口的限流策略（(capacity, refill_per_second)）
_RATE_POLICIES = {
    '/api/auth':     (10, 10 / 60),   # 登录/注册：10 次/分钟，极慢恢复
    '/api/ai':       (30, 30 / 60),   # AI：30 次/分钟
    '/api/ratings':  (60, 60 / 60),   # 写操作：60 次/分钟
    '/api/reviews':  (60, 60 / 60),
    '/api/social':   (60, 60 / 60),
    '/api/recommend':(120, 120 / 60), # 推荐：120 次/分钟
    '/api/books':    (300, 300 / 60), # 读操作：300 次/分钟
}
_DEFAULT_POLICY = (200, 200 / 60)  # 默认 200 次/分钟


def _get_bucket(remote_addr, path):
    for prefix, policy in _RATE_POLICIES.items():
        if path.startswith(prefix):
            cap, refill = policy
            break
    else:
        cap, refill = _DEFAULT_POLICY
    key = (remote_addr, path.split('/')[2] if len(path.split('/')) > 2 else 'default')
    with _BUCKETS_LOCK:
        b = _BUCKETS.get(key)
        if b is None:
            b = TokenBucket(capacity=cap, refill_per_second=refill)
            _BUCKETS[key] = b
        return b


def rate_limit_middleware(response_or_call=None):
    """Flask before_request 钩子。返回 None=放行，tuple=拒绝(429)。"""
    remote = request.remote_addr or 'anonymous'
    b = _get_bucket(remote, request.path)
    if not b.take(1):
        resp = jsonify({
            'success': False,
            'error': 'Too Many Requests',
            'hint': '请稍后重试或降低请求频率'
        })
        resp.status_code = 429
        resp.headers['Retry-After'] = '10'
        return resp
    return None


# ========== 熔断器（对外部依赖 /api/recommend 等调用保护） ==========
class CircuitBreaker:
    """
    简易熔断器：
      CLOSED -> 正常通过
      OPEN   -> 失败过多，直接拒绝
      HALF_OPEN -> 超时后放行一个探测请求
    """
    CLOSED, OPEN, HALF_OPEN = 'CLOSED', 'OPEN', 'HALF_OPEN'

    def __init__(self, name='default', failure_threshold=5, recovery_timeout=15):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = self.CLOSED
        self._failures = deque(maxlen=failure_threshold * 2)  # 记录最近失败时间
        self._opened_at = 0
        self._lock = threading.Lock()

    def call(self, fn, fallback=None, *args, **kwargs):
        """执行 fn，失败或熔断时调用 fallback 或抛异常。"""
        with self._lock:
            state = self._state
            if state == self.OPEN:
                if time.time() - self._opened_at >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
                else:
                    # 直接熔断
                    if fallback is not None:
                        return fallback(*args, **kwargs)
                    raise RuntimeError(f'CircuitBreaker[{self.name}]: OPEN')

        try:
            result = fn(*args, **kwargs)
            # 成功：如果是 HALF_OPEN -> 关闭；清空最近失败
            with self._lock:
                if self._state == self.HALF_OPEN:
                    self._state = self.CLOSED
                    self._failures.clear()
                elif self._failures:
                    # 正常状态下，也定期清理旧失败
                    pass
            return result
        except Exception as e:
            with self._lock:
                self._failures.append(time.time())
                if len(self._failures) >= self.failure_threshold:
                    self._state = self.OPEN
                    self._opened_at = time.time()
            if fallback is not None:
                return fallback(*args, **kwargs)
            raise

    def status(self):
        with self._lock:
            return {
                'name': self.name,
                'state': self._state,
                'recent_failures': len(self._failures),
                'threshold': self.failure_threshold,
                'recovery_timeout': self.recovery_timeout,
            }


# 全局熔断器注册表（推荐服务等外部依赖）
_CB_LOCK = threading.Lock()
_CIRCUIT_BREAKERS = {}


def get_circuit_breaker(name='recommend', failure_threshold=5, recovery_timeout=15):
    with _CB_LOCK:
        cb = _CIRCUIT_BREAKERS.get(name)
        if cb is None:
            cb = CircuitBreaker(name=name, failure_threshold=failure_threshold,
                                recovery_timeout=recovery_timeout)
            _CIRCUIT_BREAKERS[name] = cb
        return cb


# ========== 结构化日志 ==========
class _JSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            'level': record.levelname,
            'logger': record.name,
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(record.created)),
            'msg': record.getMessage(),
        }
        # 附加 http 上下文
        try:
            from flask import has_request_context
            if has_request_context():
                payload.update({
                    'method': request.method,
                    'path': request.path,
                    'remote': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', '')[:128],
                })
                if getattr(g, 'request_id', None):
                    payload['request_id'] = g.request_id
        except Exception:
            pass
        if record.exc_info:
            payload['exc'] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def get_structured_logger(name='app'):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler()
    handler.setFormatter(_JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


# ========== 请求 ID 中间件 ==========
def request_id_middleware():
    """before_request：给每个请求分配一个 request_id，便于链路追踪。"""
    import uuid
    g.request_id = uuid.uuid4().hex[:12]


def inject_headers(response):
    """after_request：注入响应头。"""
    elapsed = getattr(request, '_start_time', None)
    if elapsed:
        response.headers['X-Response-Time'] = f'{(time.time() - elapsed) * 1000:.0f}ms'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    rid = getattr(g, 'request_id', None)
    if rid:
        response.headers['X-Request-Id'] = rid
    return response
