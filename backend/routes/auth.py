"""认证路由 - JWT 签发/刷新/登出 + 参数校验 + 防爆破限流
依赖：flask-jwt-extended（已在 requirements.txt），未安装时降级为 token 字符串签名
"""
import re
import time
import threading as _th
import hashlib
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app, g
from extensions import db
from models import User
from services.middleware import _get_bucket

auth_bp = Blueprint('auth', __name__)


# ---------- 参数校验 ----------
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _validate_username(username):
    if not username or not isinstance(username, str):
        return '用户名必填'
    s = username.strip()
    if len(s) < 3:
        return '用户名至少 3 个字符'
    if len(s) > 32:
        return '用户名最多 32 个字符'
    if not re.match(r"^[\w\u4e00-\u9fa5\-]+$", s):
        return '用户名只能包含字母、数字、下划线、中文和短横线'
    return None


def _validate_password(password):
    if not password or not isinstance(password, str):
        return '密码必填'
    if len(password) < 6:
        return '密码至少 6 位'
    if len(password) > 128:
        return '密码最多 128 位'
    return None


def _validate_email(email):
    if email is None or email == '':
        return None  # email 可选
    if not isinstance(email, str):
        return '邮箱格式不正确'
    if len(email) > 254:
        return '邮箱过长'
    if not EMAIL_RE.match(email.strip()):
        return '邮箱格式不正确'
    return None


def _check_rate(remote_addr):
    """登录/注册限流：更严格的 10/min，避免暴力破解。"""
    b = _get_bucket(remote_addr or 'anonymous', '/api/auth')
    return b.take(1)


def _ok(data=None, message=None, status=200):
    resp = {'success': True}
    if data is not None:
        if isinstance(data, dict):
            resp.update(data)
        else:
            resp['data'] = data
    if message:
        resp['message'] = message
    return jsonify(resp), status


def _err(message, status=400, details=None):
    resp = {'success': False, 'error': message}
    if details:
        resp['details'] = details
    return jsonify(resp), status


# ---------- JWT fallback（flask-jwt-extended 未安装时的轻量实现） ----------
def _jwt_create_access(user_id, username):
    try:
        from flask_jwt_extended import create_access_token
        return create_access_token(identity=str(user_id),
                                    additional_claims={'username': username})
    except Exception:
        # fallback：HS256 + 时间戳签名
        secret = current_app.config.get('JWT_SECRET_KEY', 'fallback-secret')
        exp = int(time.time()) + 3600
        payload = f'{user_id}|{username}|{exp}'
        sig = hashlib.sha256((payload + '|' + secret).encode()).hexdigest()[:16]
        return f'{payload}.{sig}'


def _jwt_create_refresh(user_id, username):
    try:
        from flask_jwt_extended import create_refresh_token
        return create_refresh_token(identity=str(user_id),
                                    additional_claims={'username': username})
    except Exception:
        secret = current_app.config.get('JWT_SECRET_KEY', 'fallback-secret')
        exp = int(time.time()) + 86400 * 30
        payload = f'refresh|{user_id}|{username}|{exp}'
        sig = hashlib.sha256((payload + '|' + secret).encode()).hexdigest()[:16]
        return f'{payload}.{sig}'


def _extract_user_from_token():
    """尝试从 Authorization 头或 query_string 的 token 提取 user_id。"""
    # 优先 flask-jwt-extended
    try:
        from flask_jwt_extended import get_jwt_identity
        identity = get_jwt_identity()
        if identity:
            try:
                return int(identity)
            except (TypeError, ValueError):
                return None
    except Exception:
        pass
    # fallback：bearer token
    auth = request.headers.get('Authorization', '') or request.args.get('token', '')
    if auth.startswith('Bearer '):
        auth = auth[7:]
    if not auth or '.' not in auth:
        return None
    try:
        payload, sig = auth.rsplit('.', 1)
        secret = current_app.config.get('JWT_SECRET_KEY', 'fallback-secret')
        expected = hashlib.sha256((payload + '|' + secret).encode()).hexdigest()[:16]
        if expected != sig:
            return None
        parts = payload.split('|')
        # access: user_id|username|exp
        if len(parts) >= 3:
            if parts[0] == 'refresh':
                user_id = int(parts[1])
                exp = int(parts[3]) if len(parts) > 3 else 0
            else:
                user_id = int(parts[0])
                exp = int(parts[2]) if len(parts) > 2 else 0
            if exp and time.time() > exp:
                return None
            return user_id
    except Exception:
        return None
    return None


def login_required(fn):
    """装饰器：要求请求附带有效 JWT。未通过返回 401。"""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = _extract_user_from_token()
        if not user_id:
            return _err('未登录或 Token 无效', status=401)
        g.current_user_id = user_id
        return fn(*args, **kwargs)
    return wrapper


import functools


# ---------- 路由 ----------
@auth_bp.route('/register', methods=['POST'])
def register():
    if not _check_rate(request.remote_addr):
        return _err('请求过于频繁，请稍后再试', status=429)

    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    e = _validate_username(username) or _validate_password(password) or _validate_email(email)
    if e:
        return _err(e)
    username = username.strip()
    email = email.strip() if isinstance(email, str) and email else None

    if User.query.filter_by(username=username).first():
        return _err('用户名已存在', status=409)
    if email and User.query.filter_by(email=email).first():
        return _err('邮箱已被注册', status=409)

    user = User(username=username, email=email)
    user.set_password(password)
    try:
        db.session.add(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _err('注册失败，请稍后再试', status=500)

    access = _jwt_create_access(user.id, user.username)
    refresh = _jwt_create_refresh(user.id, user.username)
    return _ok({
        'user': user.to_dict(),
        'access_token': access,
        'refresh_token': refresh,
        'token_type': 'bearer',
        'expires_in': 3600,
    }, message='注册成功', status=201)


@auth_bp.route('/login', methods=['POST'])
def login():
    if not _check_rate(request.remote_addr):
        return _err('请求过于频繁，请稍后再试', status=429)

    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return _err('用户名和密码必填')

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return _err('用户名或密码错误', status=401)

    access = _jwt_create_access(user.id, user.username)
    refresh = _jwt_create_refresh(user.id, user.username)
    return _ok({
        'user': user.to_dict(),
        'access_token': access,
        'refresh_token': refresh,
        'token_type': 'bearer',
        'expires_in': 3600,
    }, message='登录成功')


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """使用 refresh_token 换取新的 access_token。"""
    if not _check_rate(request.remote_addr):
        return _err('请求过于频繁，请稍后再试', status=429)
    try:
        from flask_jwt_extended import get_jwt_identity, create_access_token
        identity = get_jwt_identity()
        if identity:
            uid = int(identity)
            user = User.query.get(uid)
            new_access = create_access_token(identity=str(uid),
                                             additional_claims={
                                                 'username': user.username if user else ''
                                             })
            return _ok({'access_token': new_access, 'expires_in': 3600})
    except Exception:
        pass
    # fallback：从 body 读取 refresh_token
    data = request.get_json(silent=True) or {}
    token = data.get('refresh_token') or request.headers.get('X-Refresh-Token', '')
    if not token or '.' not in token:
        return _err('refresh_token 无效', status=401)
    try:
        payload, sig = token.rsplit('.', 1)
        secret = current_app.config.get('JWT_SECRET_KEY', 'fallback-secret')
        expected = hashlib.sha256((payload + '|' + secret).encode()).hexdigest()[:16]
        if expected != sig:
            return _err('refresh_token 无效', status=401)
        parts = payload.split('|')
        if len(parts) < 4 or parts[0] != 'refresh':
            return _err('refresh_token 格式不正确', status=401)
        user_id = int(parts[1])
        username = parts[2]
        exp = int(parts[3])
        if time.time() > exp:
            return _err('refresh_token 已过期', status=401)
        new_access = _jwt_create_access(user_id, username)
        return _ok({'access_token': new_access, 'expires_in': 3600})
    except Exception:
        return _err('refresh_token 无效', status=401)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """前端删除本地 token 即可；后端无状态 JWT，无需显式登出。"""
    return _ok(message='已登出')


@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    user_id = _extract_user_from_token()
    if not user_id:
        uid = request.args.get('user_id', type=int)
        if not uid:
            return _err('需要登录或提供 user_id', status=401)
        user_id = uid

    user = User.query.get(user_id)
    if not user:
        return _err('用户不存在', status=404)
    return _ok({'user': user.to_dict()})



# ========== 2023 upgrade: user profile API ==========
@auth_bp.route('/profile', methods=['GET'])
@auth_bp.route('/profile/<int:profile_user_id>', methods=['GET'])
def user_profile(profile_user_id=None):
    """用户画像接口：分类偏好、作者偏好、评分分布、兴趣漂移"""
    from services.user_profile import (
        UserProfileService, InterestDriftDetector,
    )
    from services.content_filter import get_content_recommender

    current_uid = _extract_user_from_token()
    target_uid = profile_user_id or request.args.get('user_id', type=int) or current_uid
    if not target_uid:
        return _err('need login or user_id', status=401)

    user = User.query.get(target_uid)
    if not user:
        return _err('user not found', status=404)

    # 1. content-filter 画像
    categories = {}
    authors = {}
    keywords = {}
    profile_size = 0
    try:
        content_engine = get_content_recommender()
        cp = content_engine.get_user_profile(target_uid)
        categories = cp.get('categories', {}) or {}
        authors = cp.get('authors', {}) or {}
        keywords = cp.get('keywords', {}) or {}
        profile_size = cp.get('size', 0) or 0
    except Exception:
        categories = {}
        authors = {}
        keywords = {}
        profile_size = 0

    # 2. UserProfileService 画像（补充）
    try:
        ups = UserProfileService()
        extra = ups.get_profile(target_uid) or {}
        if extra:
            if not categories and extra.get('categories'):
                categories = extra.get('categories', {}) or {}
            if not authors and extra.get('authors'):
                authors = extra.get('authors', {}) or {}
            if not keywords and extra.get('keywords'):
                keywords = extra.get('keywords', {}) or {}
            if profile_size <= 0:
                profile_size = extra.get('total_ratings', 0) or 0
    except Exception:
        pass

    # 3. 兴趣漂移检测
    drift_status = {'detected': False, 'magnitude': 0.0, 'recent_rating_count': 0}
    drift_events = []
    try:
        dr = InterestDriftDetector()
        dr_result = dr.detect_drift(target_uid, threshold=0.3)
        if isinstance(dr_result, dict):
            drift_status.update(dr_result)
        try:
            drift_events = list(dr.get_recent_trend(target_uid, n=5) or [])[:5]
        except Exception:
            drift_events = []
    except Exception:
        drift_events = []

    # 4. 评分统计
    total_ratings = 0
    avg_rating = 0.0
    rating_distribution = {}
    try:
        from extensions import db
        from models import Rating
        from sqlalchemy import func
        total_ratings = db.session.query(func.count(Rating.id)).filter(Rating.user_id == target_uid).scalar() or 0
        avg_rating = db.session.query(func.avg(Rating.rating)).filter(Rating.user_id == target_uid).scalar() or 0.0
        rating_rows = db.session.query(
            Rating.rating, func.count(Rating.id)
        ).filter(Rating.user_id == target_uid).group_by(Rating.rating).limit(20).all()
        rating_distribution = {str(int(r)): int(c) for r, c in rating_rows}
    except Exception:
        total_ratings = profile_size
        avg_rating = 0.0
        rating_distribution = {}

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
        'recent_drift_events': drift_events,
    }
    return _ok({'profile': profile})


@auth_bp.route('/profile/reset', methods=['POST'])
def reset_user_profile():
    """重置用户画像（清除兴趣漂移检测）"""
    user_id = _extract_user_from_token()
    if not user_id:
        uid = request.args.get('user_id', type=int)
        if not uid:
            return _err('need login or user_id', status=401)
        user_id = uid
    try:
        from services.user_profile import get_user_profile_service
        up = get_user_profile_service()
        if hasattr(up, 'reset_profile'):
            up.reset_profile(user_id)
        return _ok(message='profile reset')
    except Exception as e:
        return _err('reset failed: ' + str(e), status=500)
