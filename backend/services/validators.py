# -*- coding: utf-8 -*-
"""轻量级输入验证模块（不依赖 pydantic）
- 独立的 validate_* 函数：成功返回 (True, value)，失败返回 (False, message)
- Validator 装饰器 / 上下文管理器：可直接作用于 Flask 路由视图
"""

import re
import threading
from functools import wraps
from typing import Any, Tuple, Dict, Optional


# ============ 独立验证函数 ============

def validate_user_id(value: Any) -> Tuple[bool, Any]:
    try:
        v = int(value)
        if v > 0:
            return True, v
        return False, 'user_id 必须是正整数'
    except (TypeError, ValueError):
        return False, 'user_id 必须是正整数'


def validate_book_id(value: Any) -> Tuple[bool, Any]:
    try:
        v = int(value)
        if v > 0:
            return True, v
        return False, 'book_id 必须是正整数'
    except (TypeError, ValueError):
        return False, 'book_id 必须是正整数'


def validate_rating(value: Any) -> Tuple[bool, Any]:
    try:
        v = int(value)
        if 1 <= v <= 10:
            return True, v
        return False, 'rating 必须是 1-10 的整数'
    except (TypeError, ValueError):
        return False, 'rating 必须是 1-10 的整数'


def validate_limit(value: Any, min_val: int = 1, max_val: int = 50) -> Tuple[bool, Any]:
    try:
        v = int(value)
        if min_val <= v <= max_val:
            return True, v
        return False, f'limit 必须在 {min_val}-{max_val} 之间'
    except (TypeError, ValueError):
        return False, f'limit 必须在 {min_val}-{max_val} 之间'


_SAFE_QUERY_RE = re.compile(r'^[\u4e00-\u9fa5A-Za-z0-9\s\-\_\.\,\!\?\'\"\/\(\)\&\#\@\+\=\:\;\%]+$')


def validate_search_query(value: Any, min_len: int = 1, max_len: int = 200) -> Tuple[bool, Any]:
    try:
        if value is None:
            return False, '搜索词不能为空'
        q = str(value).strip()
        if len(q) < min_len:
            return False, f'搜索词至少 {min_len} 个字符'
        if len(q) > max_len:
            return False, f'搜索词最多 {max_len} 个字符'
        if not _SAFE_QUERY_RE.match(q):
            return False, '搜索词包含非法字符'
        return True, q
    except Exception:
        return False, '搜索词校验失败'


# ============ Validator 统一入口 ============

class ValidationError(Exception):
    def __init__(self, field: str, message: str):
        super().__init__(f'{field}: {message}')
        self.field = field
        self.message = message


class Validator:
    """统一验证入口
    - 作为装饰器使用：@Validator.require(user_id='user_id', book_id='book_id')
    - 作为上下文管理器使用：with Validator() as v: ...
    - 不抛异常，默认降级返回失败响应
    """
    _lock = threading.Lock()

    _FIELD_VALIDATORS = {
        'user_id': validate_user_id,
        'book_id': validate_book_id,
        'rating': validate_rating,
        'limit': lambda v: validate_limit(v),
        'search_query': lambda v: validate_search_query(v),
    }

    def __init__(self):
        self.errors: Dict[str, str] = {}
        self.values: Dict[str, Any] = {}

    # -------- 上下文管理器 --------
    def __enter__(self):
        self.errors.clear()
        self.values.clear()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def check(self, field: str, value: Any, validator=None) -> Optional[Any]:
        vfn = validator or self._FIELD_VALIDATORS.get(field)
        if vfn is None:
            self.values[field] = value
            return value
        ok, result = vfn(value)
        if ok:
            self.values[field] = result
            return result
        self.errors[field] = str(result)
        return None

    def ok(self) -> bool:
        return not self.errors

    # -------- 装饰器 --------
    @classmethod
    def require(cls, **rules):
        """装饰器用法：对 Flask 视图函数的请求参数进行校验
        rules 形如：
            user_id='user_id',           # 字段名 -> 使用默认校验器
            limit=('limit', 1, 50),      # (字段名, min, max)
            search_query=('q', 1, 100),  # (字段名, min, max)
        """
        def decorator(view_fn):
            @wraps(view_fn)
            def wrapper(*args, **kwargs):
                try:
                    from flask import request, jsonify
                except Exception:
                    return view_fn(*args, **kwargs)

                values: Dict[str, Any] = {}
                errors: Dict[str, str] = {}

                for key, rule in rules.items():
                    src_name = None
                    if isinstance(rule, tuple):
                        src_name = rule[0]
                    else:
                        src_name = rule

                    raw = kwargs.get(src_name)
                    if raw is None:
                        raw = request.args.get(src_name)
                    if raw is None and request.is_json:
                        try:
                            raw = request.get_json(silent=True).get(src_name)
                        except Exception:
                            raw = None
                    if raw is None:
                        raw = request.form.get(src_name)

                    vfn = cls._FIELD_VALIDATORS.get(key)
                    if vfn is None:
                        values[key] = raw
                        continue

                    if key == 'limit' and isinstance(rule, tuple) and len(rule) >= 3:
                        try:
                            ok, res = validate_limit(raw, int(rule[1]), int(rule[2]))
                        except Exception:
                            ok, res = vfn(raw)
                    elif key == 'search_query' and isinstance(rule, tuple) and len(rule) >= 3:
                        try:
                            ok, res = validate_search_query(raw, int(rule[1]), int(rule[2]))
                        except Exception:
                            ok, res = vfn(raw)
                    else:
                        ok, res = vfn(raw)

                    if ok:
                        values[key] = res
                    else:
                        errors[key] = str(res)

                if errors:
                    try:
                        return jsonify({'ok': False, 'errors': errors, 'values': values}), 400
                    except Exception:
                        return {'ok': False, 'errors': errors, 'values': values}, 400

                kwargs['_validated'] = values
                return view_fn(*args, **kwargs)
            return wrapper
        return decorator
