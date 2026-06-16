"""社交路由 - 关注、粉丝、动态（含写操作限流）"""

from flask import Blueprint, request, jsonify
from extensions import db
from datetime import datetime
import threading as _th
import time as _time

social_bp = Blueprint('social', __name__)

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


@social_bp.before_request
def _social_write_limit_hook():
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


# ========== 关注模型 ==========
class Follow(db.Model):
    """关注关系表"""
    __tablename__ = 'follows'

    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    following_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('follower_id', 'following_id', name='unique_follow'),
    )

    follower = db.relationship('User', foreign_keys=[follower_id], backref='following_relations')
    following = db.relationship('User', foreign_keys=[following_id], backref='follower_relations')


# ========== 关注 API ==========
@social_bp.route('/<int:user_id>/follow', methods=['POST'])
def toggle_follow(user_id):
    """关注/取消关注用户"""
    data = request.get_json() or {}
    follower_id = data.get('follower_id')

    if not follower_id:
        return _err('缺少follower_id')
    if follower_id == user_id:
        return _err('不能关注自己')

    from models import User
    target_user = User.query.get(user_id)
    if not target_user:
        return _err('目标用户不存在', status=404)
    follower_user = User.query.get(follower_id)
    if not follower_user:
        return _err('follower用户不存在', status=404)

    try:
        existing = Follow.query.filter_by(follower_id=follower_id, following_id=user_id).first()

        if existing:
            db.session.delete(existing)
            action = 'unfollowed'
        else:
            follow = Follow(follower_id=follower_id, following_id=user_id)
            db.session.add(follow)
            action = 'followed'

        db.session.commit()

        followers_count = Follow.query.filter_by(following_id=user_id).count()
        following_count = Follow.query.filter_by(follower_id=user_id).count()

        return _ok({
            'action': action,
            'is_following': action == 'followed',
            'followers_count': followers_count,
            'following_count': following_count,
        })
    except Exception as e:
        db.session.rollback()
        return _err(str(e), status=500)


@social_bp.route('/<int:user_id>/followers', methods=['GET'])
def get_followers(user_id):
    """获取粉丝列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20

    follows = Follow.query.filter_by(following_id=user_id).paginate(
        page=page, per_page=per_page, error_out=False
    )

    followers = []
    for f in follows.items:
        followers.append({
            'user_id': f.follower_id,
            'username': f.follower.username if f.follower else '未知',
            'followed_at': f.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    return _ok({
        'followers': followers,
        'total': follows.total,
        'pages': follows.pages,
        'current_page': page,
    })


@social_bp.route('/<int:user_id>/following', methods=['GET'])
def get_following(user_id):
    """获取关注列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20

    follows = Follow.query.filter_by(follower_id=user_id).paginate(
        page=page, per_page=per_page, error_out=False
    )

    following = []
    for f in follows.items:
        following.append({
            'user_id': f.following_id,
            'username': f.following.username if f.following else '未知',
            'followed_at': f.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    return _ok({
        'following': following,
        'total': follows.total,
        'pages': follows.pages,
        'current_page': page,
    })


@social_bp.route('/<int:user_id>/stats', methods=['GET'])
def get_social_stats(user_id):
    """获取用户社交统计"""
    followers_count = Follow.query.filter_by(following_id=user_id).count()
    following_count = Follow.query.filter_by(follower_id=user_id).count()

    from routes.reviews import Review, Comment
    reviews_count = Review.query.filter_by(user_id=user_id).count()
    comments_count = Comment.query.filter_by(user_id=user_id).count()

    return _ok({
        'stats': {
            'followers': followers_count,
            'following': following_count,
            'reviews': reviews_count,
            'comments': comments_count,
        }
    })


@social_bp.route('/<int:user_id>/feed', methods=['GET'])
def get_follow_feed(user_id):
    """获取关注动态（JOIN 优化 + 分页）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20

    from routes.reviews import Review

    # 直接 JOIN follows 与 reviews，一步查询
    query = db.session.query(Review).join(
        Follow, Follow.following_id == Review.user_id
    ).filter(
        Follow.follower_id == user_id
    ).order_by(Review.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    feed = []
    for review in pagination.items:
        feed.append({
            'type': 'review',
            'data': review.to_dict(),
        })

    return _ok({
        'feed': feed,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
    })


@social_bp.route('/me/stats', methods=['GET'])
def my_social_stats():
    """当前用户社交统计"""
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return _err('需要 user_id')

    return get_social_stats(user_id)
