"""
🤖 AI 对话历史和用户偏好 - 数据库模型

存储:
- AI 对话历史
- 用户书籍交互
- AI 生成内容缓存
"""

from datetime import datetime
from extensions import db


class AIConversation(db.Model):
    """AI 对话记录"""
    __tablename__ = 'ai_conversations'

    id = db.Column(db.Integer, primary_key=True)
    conv_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    title = db.Column(db.String(200), default='新对话')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    message_count = db.Column(db.Integer, default=0)

    # 关联消息（延迟导入避免循环依赖）
    @property
    def messages(self):
        return AIMessage.query.filter_by(conversation_id=self.id).order_by(AIMessage.timestamp)

    def to_dict(self):
        return {
            'id': self.id,
            'conv_id': self.conv_id,
            'user_id': self.user_id,
            'title': self.title,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'last_updated': self.last_updated.strftime('%Y-%m-%d %H:%M'),
            'message_count': self.message_count,
        }


class AIMessage(db.Model):
    """AI 消息记录"""
    __tablename__ = 'ai_messages'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('ai_conversations.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(50), nullable=True)  # 识别的意图类型
    model = db.Column(db.String(50), nullable=True)  # 使用的模型
    tokens = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    metadata = db.Column(db.JSON, nullable=True)  # 额外元数据

    # 关联（延迟导入避免循环依赖）
    @property
    def conversation(self):
        return AIConversation.query.get(self.conversation_id)

    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content,
            'intent': self.intent,
            'model': self.model,
            'tokens': self.tokens,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'metadata': self.metadata,
        }


class UserBookInteraction(db.Model):
    """用户与书籍的 AI 相关交互"""
    __tablename__ = 'user_book_interactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False, index=True)
    interaction_type = db.Column(db.String(50), nullable=False)  # 'ai_chat', 'review_request', 'knowledge_graph'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    metadata = db.Column(db.JSON, nullable=True)  # 交互详情

    # 关联（延迟导入避免循环依赖）
    @property
    def user(self):
        from models import User
        return User.query.get(self.user_id)

    @property
    def book(self):
        from models import Book
        return Book.query.get(self.book_id)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'book_id': self.book_id,
            'interaction_type': self.interaction_type,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'metadata': self.metadata,
        }


class AIContentCache(db.Model):
    """AI 生成内容缓存（避免重复生成）"""
    __tablename__ = 'ai_content_cache'

    id = db.Column(db.Integer, primary_key=True)
    cache_key = db.Column(db.String(200), unique=True, nullable=False, index=True)
    content_type = db.Column(db.String(50), nullable=False)  # 'review', 'knowledge', 'summary'
    content = db.Column(db.Text, nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)  # 缓存过期时间

    # 关联（延迟导入避免循环依赖）
    @property
    def book(self):
        from models import Book
        return Book.query.get(self.book_id) if self.book_id else None

    @property
    def user(self):
        from models import User
        return User.query.get(self.user_id) if self.user_id else None

    def is_expired(self):
        return self.expires_at and self.expires_at < datetime.utcnow()

    def to_dict(self):
        return {
            'id': self.id,
            'cache_key': self.cache_key,
            'content_type': self.content_type,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'is_expired': self.is_expired(),
        }


def init_ai_db():
    """初始化 AI 相关数据库表"""
    db.create_all()
    print('[AI DB] 数据库表已创建 ✓')
