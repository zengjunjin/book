from flask import Blueprint, request, jsonify
from extensions import db
from models import Rating, Book
import threading as _th
import time as _time

ratings_bp = Blueprint('ratings', __name__)

# ---------- 写操作限流：60/minute ----------
_WRITE_LOCK = _th.Lock()
_WRITE_COUNTER = {}
_WRITE_WINDOW = 60
_WRITE_LIMIT = 60


def _check_write_counter(remote_addr):
    now = _time.time()
    with _WRITE_LOCK:
        bucket = _WRITE_COUNTER.setdefault(remote_addr, [])
        cutoff = now - _WRITE_WINDOW
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= _WRITE_LIMIT:
            return False
        bucket.append(now)
        return True


@ratings_bp.before_request
def _ratings_write_limit_hook():
    if request.method in ('POST', 'PUT', 'DELETE'):
        if not _check_write_counter(request.remote_addr or 'anonymous'):
            return jsonify({'success': False, 'error': '写操作过多，请稍后再试'}), 429
    return None


def _ok(data=None, message=None, status=200):
    resp = {'success': True}
    if data is not None:
        resp.update(data) if isinstance(data, dict) else resp.update({'data': data})
    if message:
        resp['message'] = message
    return jsonify(resp), status


def _err(message, status=400, details=None):
    resp = {'success': False, 'error': message}
    if details:
        resp['details'] = details
    return jsonify(resp), status


@ratings_bp.route('/', methods=['POST'])
def create_rating():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    book_id = data.get('book_id')
    rating_value = data.get('rating')

    if not all([user_id, book_id, rating_value is not None]):
        return _err('缺少必要字段')

    try:
        rating_value = int(rating_value)
    except (ValueError, TypeError):
        return _err('评分必须是整数')

    if not (1 <= rating_value <= 10):
        return _err('评分必须在 1-10 之间')

    existing = Rating.query.filter_by(user_id=user_id, book_id=book_id).first()
    if existing:
        existing.rating = rating_value
        db.session.commit()
        return _ok({'rating': existing.to_dict()}, message='评分已更新')

    rating = Rating(user_id=user_id, book_id=book_id, rating=rating_value)
    db.session.add(rating)
    db.session.commit()

    return _ok({'rating': rating.to_dict()}, message='评分已创建', status=201)


@ratings_bp.route('/user', methods=['GET'])
def get_user_ratings():
    user_id = request.args.get('user_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    # 参数边界保护
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20

    if not user_id:
        return _err('需要用户ID')

    query = Rating.query.filter_by(user_id=user_id).order_by(Rating.created_at.desc())
    total = query.count()
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    result = []
    for r in pagination.items:
        book = Book.query.get(r.book_id)
        rating_dict = r.to_dict()
        rating_dict['book'] = book.to_dict() if book else None
        result.append(rating_dict)

    return _ok({
        'ratings': result,
        'total': total,
        'page': page,
        'pages': (total + per_page - 1) // per_page,
    })
