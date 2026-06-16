"""缓存服务 - 支持 Redis 和内存缓存降级"""
import json
import time
import functools
from typing import Optional, Any, Callable, Dict
from threading import Lock

# 尝试接入指标监控（缺失时静默降级
try:
    from services.metrics import cache_hit_inc, cache_miss_inc
    _HAS_METRICS = True
except Exception:
    _HAS_METRICS = False


def _record_cache_hit():
    try:
        if _HAS_METRICS:
            cache_hit_inc()
    except Exception:
        pass


def _record_cache_miss():
    try:
        if _HAS_METRICS:
            cache_miss_inc()
    except Exception:
        pass

# 内存缓存（Redis 不可用时使用）
_memory_cache: Dict[str, tuple] = {}  # key -> (value, expire_time)
_memory_lock = Lock()


class CacheService:
    """缓存服务，支持 Redis 和内存缓存自动降级"""

    _instance: Optional['CacheService'] = None
    _redis_client = None
    _use_memory = True  # 默认使用内存缓存

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def init_app(self, app):
        """初始化缓存（优先 Redis，失败则降级到内存）"""
        try:
            import redis
            self._redis_client = redis.Redis(
                host=app.config.get('REDIS_HOST', 'localhost'),
                port=app.config.get('REDIS_PORT', 6379),
                password=app.config.get('REDIS_PASSWORD') or None,
                db=app.config.get('REDIS_DB', 0),
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                socket_keepalive=True,
                encoding='utf-8',
                encoding_errors='strict',
            )
            # 测试连接（强制RESP2避免HELLO协议问题）
            self._redis_client.ping()
            self._use_memory = False
            print("[Cache] Redis 连接成功 ✓")
        except Exception as e:
            self._use_memory = True
            self._redis_client = None
            print(f"[Cache] Redis 不可用，使用内存缓存: {e}")

    def _memory_get(self, key: str) -> Optional[Any]:
        """内存缓存获取"""
        with _memory_lock:
            if key in _memory_cache:
                value, expire_time = _memory_cache[key]
                if expire_time is None or expire_time > time.time():
                    return value
                else:
                    del _memory_cache[key]
            return None

    def _memory_set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """内存缓存设置"""
        with _memory_lock:
            expire_time = None if ttl is None else time.time() + ttl
            _memory_cache[key] = (value, expire_time)
            return True

    def _memory_delete(self, key: str) -> bool:
        """内存缓存删除"""
        with _memory_lock:
            if key in _memory_cache:
                del _memory_cache[key]
            return True

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if self._use_memory:
            value = self._memory_get(key)
            if value is not None:
                _record_cache_hit()
            else:
                _record_cache_miss()
            return value

        try:
            value = self._redis_client.get(key)
            if value:
                _record_cache_hit()
                return json.loads(value)
            _record_cache_miss()
            return None
        except Exception:
            # Redis 错误，降级到内存
            self._use_memory = True
            self._redis_client = None
            value = self._memory_get(key)
            if value is not None:
                _record_cache_hit()
            else:
                _record_cache_miss()
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        serialized = json.dumps(value, default=str)

        if self._use_memory:
            return self._memory_set(key, value, ttl)

        try:
            if ttl:
                return self._redis_client.setex(key, ttl, serialized)
            else:
                return self._redis_client.set(key, serialized)
        except Exception:
            self._use_memory = True
            self._redis_client = None
            return self._memory_set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """删除缓存"""
        if self._use_memory:
            return self._memory_delete(key)

        try:
            self._redis_client.delete(key)
            return True
        except Exception:
            return self._memory_delete(key)

    def invalidate_user_cache(self, user_id: int):
        """清除用户相关缓存"""
        for pattern in [f'user:{user_id}:*', f'recommend:{user_id}:*']:
            if self._use_memory:
                with _memory_lock:
                    keys_to_delete = [k for k in _memory_cache if k.startswith(pattern.replace(':*', ''))]
                    for k in keys_to_delete:
                        del _memory_cache[k]
            else:
                try:
                    for key in self._redis_client.scan_iter(pattern):
                        self._redis_client.delete(key)
                except:
                    pass

    def invalidate_book_cache(self, book_id: int):
        """清除书籍相关缓存"""
        for pattern in [f'book:{book_id}:*']:
            if self._use_memory:
                with _memory_lock:
                    keys_to_delete = [k for k in _memory_cache if k.startswith(f'book:{book_id}:')]
                    for k in keys_to_delete:
                        del _memory_cache[k]
            else:
                try:
                    for key in self._redis_client.scan_iter(pattern):
                        self._redis_client.delete(key)
                except:
                    pass

    def invalidate_recommend_cache(self):
        """清除推荐相关缓存"""
        if self._use_memory:
            with _memory_lock:
                keys_to_delete = [k for k in _memory_cache if 'recommend' in k or 'cf:' in k or 'svd:' in k]
                for k in keys_to_delete:
                    del _memory_cache[k]
        else:
            try:
                for key in self._redis_client.scan_iter('recommend:*'):
                    self._redis_client.delete(key)
                for key in self._redis_client.scan_iter('cf:*'):
                    self._redis_client.delete(key)
                for key in self._redis_client.scan_iter('svd:*'):
                    self._redis_client.delete(key)
            except:
                pass


# 全局单例
cache_service = CacheService()


def make_cache_key(*args) -> str:
    """生成缓存键"""
    return ':'.join(str(arg) for arg in args)


def cached(key_prefix: str, ttl: int = 300):
    """缓存装饰器"""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存 key
            cache_key = f"{key_prefix}:{':'.join(str(a) for a in args)}:{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"

            # 尝试从缓存获取
            cached_value = cache_service.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 执行函数
            result = func(*args, **kwargs)

            # 存入缓存
            if result is not None:
                cache_service.set(cache_key, result, ttl)

            return result
        return wrapper
    return decorator
