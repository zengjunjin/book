from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    rating = Column(Float, nullable=False)  # 评分 1-5
    likes = Column(Integer, default=0)  # 点赞数
    dislikes = Column(Integer, default=0)  # 踩数
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="reviews")
    book = relationship("Book", back_populates="reviews")
    comments = relationship("Comment", back_populates="review", cascade="all, delete-orphan")
    likes_records = relationship("ReviewLike", back_populates="review", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_reviews_book_created", "book_id", "created_at"),
        Index("ix_reviews_user_book", "user_id", "book_id"),
    )

    def __repr__(self):
        return f"<Review {self.id} by User {self.user_id} on Book {self.book_id}>"


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="comments")
    review = relationship("Review", back_populates="comments")

    def __repr__(self):
        return f"<Comment {self.id} by User {self.user_id}>"


class ReviewLike(Base):
    """记录用户对书评的点赞/踩"""
    __tablename__ = "review_likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    is_like = Column(Integer, default=1)  # 1=点赞, 0=踩
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User")
    review = relationship("Review", back_populates="likes_records")

    __table_args__ = (
        Index("ix_review_likes_user_review", "user_id", "review_id", unique=True),
    )

    def __repr__(self):
        return f"<ReviewLike user={self.user_id} review={self.review_id} like={self.is_like}>"


class Follow(Base):
    __tablename__ = "follows"

    follower_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    following_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    follower = relationship("User", foreign_keys=[follower_id], back_populates="following")
    following = relationship("User", foreign_keys=[following_id], back_populates="followers")

    def __repr__(self):
        return f"<Follow follower={self.follower_id} following={self.following_id}>"


class Discussion(Base):
    __tablename__ = "discussions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="discussions")
    book = relationship("Book", back_populates="discussions")
    replies = relationship("DiscussionReply", back_populates="discussion", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_discussions_book_created", "book_id", "created_at"),
    )

    def __repr__(self):
        return f"<Discussion {self.id}: {self.title}>"


class DiscussionReply(Base):
    __tablename__ = "discussion_replies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    discussion_id = Column(Integer, ForeignKey("discussions.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="discussion_replies")
    discussion = relationship("Discussion", back_populates="replies")

    def __repr__(self):
        return f"<DiscussionReply {self.id} by User {self.user_id}>"
