from sqlalchemy import Column, Integer, String, Text, ARRAY, Float, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    isbn = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    author = Column(String(255))
    year = Column(Integer)
    publisher = Column(String(255))
    image_url = Column(String(500))
    description = Column(Text)
    category = Column(String(100))
    tags = Column(ARRAY(String), default=[])
    avg_rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    ratings = relationship("Rating", back_populates="book", cascade="all, delete-orphan")
    interactions = relationship("Interaction", back_populates="book", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="book", cascade="all, delete-orphan")
    discussions = relationship("Discussion", back_populates="book", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Book {self.title}>"
