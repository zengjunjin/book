"""
📝 书评路由 - 书籍评论和评分系统（含写操作限流）
"""

from flask import Blueprint, request, jsonify, current_app
from extensions import db
from models import User, Book, Rating
from datetime import datetime
import random

reviews_bp = Blueprint('reviews', __name__)

# ---------- 写操作限流：内存计数器（60/minute）----------
import threading as _th
import time as _time
_WRITE_LOCK = _th.Lock()
_WRITE_COUNTER = {}  # key -> list[timestamp]
_WRITE_WINDOW = 60   # 秒
_WRITE_LIMIT = 60    # 每窗口最多 60 次写操作


def _check_write_counter(remote_addr):
    """返回 True 表示可放行，False 表示超过限制"""
    now = _time.time()
    with _WRITE_LOCK:
        bucket = _WRITE_COUNTER.setdefault(remote_addr, [])
        # 清掉已过期条目
        cutoff = now - _WRITE_WINDOW
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= _WRITE_LIMIT:
            return False
        bucket.append(now)
        return True


@reviews_bp.before_request
def _reviews_write_limit_hook():
    if request.method in ('POST', 'PUT', 'DELETE'):
        if not _check_write_counter(request.remote_addr or 'anonymous'):
            return jsonify({'success': False, 'error': '写操作过多，请稍后再试'}), 429
    return None



# ========== 书评模型 ==========
class Review(db.Model):
    """书评表"""
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Float, nullable=False)  # 1-10
    likes = db.Column(db.Integer, default=0)
    dislikes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = db.relationship('User', backref='reviews')
    book = db.relationship('Book', backref='reviews')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else '未知',
            'book_id': self.book_id,
            'book_title': self.book.title if self.book else '未知',
            'content': self.content,
            'rating': self.rating,
            'likes': self.likes,
            'dislikes': self.dislikes,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
        }


class Comment(db.Model):
    """评论表"""
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    user = db.relationship('User', backref='comments')
    review = db.relationship('Review', backref='comments')

    def to_dict(self):
        return {
            'id': self.id,
            'review_id': self.review_id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else '未知',
            'content': self.content,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
        }


class ReviewLike(db.Model):
    """书评点赞表"""
    __tablename__ = 'review_likes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False)
    is_like = db.Column(db.Boolean, default=True)  # True=点赞, False=踩
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 复合唯一键
    __table_args__ = (
        db.UniqueConstraint('user_id', 'review_id', name='unique_user_review_like'),
    )


# ========== 书评 API ==========
@reviews_bp.route('', methods=['GET'])
def get_reviews():
    """获取书评列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    sort = request.args.get('sort', 'latest')
    book_id = request.args.get('book_id', type=int)

    if page < 1: page = 1
    if per_page < 1 or per_page > 100: per_page = 20

    query = Review.query

    if book_id:
        query = query.filter_by(book_id=book_id)

    # 排序
    if sort == 'hot':
        query = query.order_by(Review.likes.desc())
    elif sort == 'helpful':
        query = query.order_by((Review.likes - Review.dislikes).desc())
    else:  # latest
        query = query.order_by(Review.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'reviews': [r.to_dict() for r in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
    })


@reviews_bp.route('', methods=['POST'])
def create_review():
    """发布书评"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    book_id = data.get('book_id')
    content = data.get('content', '').strip()
    rating = data.get('rating', 0)

    if not all([user_id, book_id, content]):
        return jsonify({'success': False, 'error': '缺少必要参数'}), 400

    if not content or len(content) < 10:
        return jsonify({'success': False, 'error': '书评内容至少10个字'}), 400

    if rating < 1 or rating > 10:
        return jsonify({'success': False, 'error': '评分需在1-10之间'}), 400

    # 检查用户和书籍是否存在
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': '用户不存在'}), 404
    book = Book.query.get(book_id)
    if not book:
        return jsonify({'success': False, 'error': '书籍不存在'}), 404

    # 检查是否已评分
    existing = Review.query.filter_by(user_id=user_id, book_id=book_id).first()
    if existing:
        return jsonify({'success': False, 'error': '已发布过书评'}), 400

    try:
        review = Review(
            user_id=user_id,
            book_id=book_id,
            content=content,
            rating=rating
        )
        db.session.add(review)

        # 同时创建评分记录
        rating_record = Rating.query.filter_by(user_id=user_id, book_id=book_id).first()
        if rating_record:
            rating_record.rating = rating
        else:
            rating_record = Rating(user_id=user_id, book_id=book_id, rating=rating)
            db.session.add(rating_record)

        db.session.commit()
        return jsonify({'success': True, 'review': review.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@reviews_bp.route('/<int:review_id>', methods=['GET'])
def get_review(review_id):
    """获取书评详情"""
    review = Review.query.get_or_404(review_id)
    return jsonify({'success': True, 'review': review.to_dict()})


@reviews_bp.route('/<int:review_id>', methods=['PUT'])
def update_review(review_id):
    """更新书评（归属校验：只能修改自己的书评）"""
    data = request.get_json() or {}
    caller_user_id = data.get('user_id')
    if not caller_user_id:
        return jsonify({'success': False, 'error': '需要用户ID'}), 400

    review = Review.query.get_or_404(review_id)
    # 归属校验
    if review.user_id != caller_user_id:
        return jsonify({'success': False, 'error': '无权限修改他人书评'}), 403

    if 'content' in data:
        content = data['content'].strip()
        if len(content) < 10:
            return jsonify({'success': False, 'error': '书评内容至少10个字'}), 400
        review.content = content
    if 'rating' in data:
        r = data['rating']
        if 1 <= r <= 10:
            review.rating = r
        else:
            return jsonify({'success': False, 'error': '评分需在1-10之间'}), 400

    db.session.commit()
    return jsonify({'success': True, 'review': review.to_dict()})


@reviews_bp.route('/<int:review_id>', methods=['DELETE'])
def delete_review(review_id):
    """删除书评（归属校验：只能删除自己的书评）"""
    data = request.get_json() or {}
    caller_user_id = request.args.get('user_id', type=int) or data.get('user_id')
    if not caller_user_id:
        return jsonify({'success': False, 'error': '需要用户ID'}), 400

    review = Review.query.get_or_404(review_id)
    if review.user_id != caller_user_id:
        return jsonify({'success': False, 'error': '无权限删除他人书评'}), 403

    db.session.delete(review)
    db.session.commit()
    return jsonify({'success': True})


# ========== 点赞/踩 ==========
@reviews_bp.route('/<int:review_id>/like', methods=['POST'])
def like_review(review_id):
    """点赞/踩书评"""
    data = request.get_json()
    user_id = data.get('user_id')
    is_like = data.get('is_like', True)  # True=点赞, False=踩

    review = Review.query.get_or_404(review_id)

    # 检查是否已点赞
    existing = ReviewLike.query.filter_by(user_id=user_id, review_id=review_id).first()

    if existing:
        if existing.is_like == is_like:
            # 取消点赞
            if is_like:
                review.likes = max(0, review.likes - 1)
            else:
                review.dislikes = max(0, review.dislikes - 1)
            db.session.delete(existing)
            action = 'removed'
        else:
            # 切换点赞状态
            if existing.is_like:
                review.likes = max(0, review.likes - 1)
                review.dislikes += 1
            else:
                review.dislikes = max(0, review.dislikes - 1)
                review.likes += 1
            existing.is_like = is_like
            action = 'changed'
    else:
        # 新增点赞
        like = ReviewLike(user_id=user_id, review_id=review_id, is_like=is_like)
        db.session.add(like)
        if is_like:
            review.likes += 1
        else:
            review.dislikes += 1
        action = 'added'

    db.session.commit()
    return jsonify({
        'success': True,
        'action': action,
        'likes': review.likes,
        'dislikes': review.dislikes
    })


# ========== 评论 ==========
@reviews_bp.route('/<int:review_id>/comments', methods=['GET'])
def get_comments(review_id):
    """获取书评的评论"""
    comments = Comment.query.filter_by(review_id=review_id).order_by(Comment.created_at.desc()).all()
    return jsonify({
        'success': True,
        'comments': [c.to_dict() for c in comments]
    })


@reviews_bp.route('/<int:review_id>/comments', methods=['POST'])
def create_comment(review_id):
    """评论书评"""
    data = request.get_json()
    user_id = data.get('user_id')
    content = data.get('content', '').strip()

    if not content or len(content) < 2:
        return jsonify({'success': False, 'error': '评论内容至少2个字'}), 400

    comment = Comment(
        review_id=review_id,
        user_id=user_id,
        content=content
    )
    db.session.add(comment)
    db.session.commit()

    return jsonify({'success': True, 'comment': comment.to_dict()})
