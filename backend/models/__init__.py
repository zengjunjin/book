from extensions import db
from .user import User
from .book import Book
from .rating import Rating

__all__ = ['User', 'Book', 'Rating', 'db']
