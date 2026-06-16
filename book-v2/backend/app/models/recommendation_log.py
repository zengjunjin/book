"""
推荐日志模型 - 记录推荐曝光与点击数据
参考报告评估指标体系设计
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class RecommendationLog(Base):
    """推荐日志：记录每次推荐的曝光和反馈"""
    __tablename__ = "recommendation_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)

    # 推荐来源
    source = Column(String(20), nullable=False)  # 'cf', 'svd', 'hybrid', 'cold_start', 'embedding'
    algorithm_version = Column(String(20))

    # 位置信息
    position = Column(Integer)  # 在推荐列表中的位置 (0-indexed)

    # 反馈信息
    displayed = Column(Boolean, default=True)      # 是否曝光
    clicked = Column(Boolean, default=False)        # 是否点击
    rated = Column(Boolean, default=False)          # 是否评分
    liked = Column(Boolean, default=False)          # 是否喜欢

    # 评分（如果有）
    rating = Column(Integer)

    # 上下文
    session_id = Column(String(100))
    device_type = Column(String(20))

    # 时间戳
    recommended_at = Column(DateTime(timezone=True), server_default=func.now())
    clicked_at = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<RecommendationLog user={self.user_id} book={self.book_id} clicked={self.clicked}>"
