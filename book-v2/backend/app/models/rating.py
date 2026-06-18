from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="ratings")
    book = relationship("Book", back_populates="ratings")

    # Constraints
    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 10', name='rating_range_check'),
    )

    def __repr__(self):
        return f"<Rating user_id={self.user_id} book_id={self.book_id} rating={self.rating}>"
