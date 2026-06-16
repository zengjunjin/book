from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    interaction_type = Column(String(20), nullable=False)  # 'view', 'like', 'dislike', 'want_to_read', 'read'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="interactions")
    book = relationship("Book", back_populates="interactions")

    __table_args__ = (
        UniqueConstraint('user_id', 'book_id', 'interaction_type', name='unique_user_book_interaction'),
    )

    def __repr__(self):
        return f"<Interaction user={self.user_id} book={self.book_id} type={self.interaction_type}>"
