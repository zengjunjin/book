from extensions import db
from datetime import datetime


class Rating(db.Model):
    __tablename__ = 'ratings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # 联合唯一约束：同一用户不能为同一本书创建多个评分
    __table_args__ = (
        db.UniqueConstraint('user_id', 'book_id', name='uq_user_book_rating'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'book_id': self.book_id,
            'rating': self.rating,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
