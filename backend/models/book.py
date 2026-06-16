from extensions import db


class Book(db.Model):
    __tablename__ = 'books'
    # MySQL FULLTEXT索引（用于MATCH AGAINST全文搜索）
    # 在MySQL中执行: ALTER TABLE books ADD FULLTEXT INDEX ft_books_title_author (title, author);
    __table_args__ = (
        db.Index('idx_books_title', 'title'),
        db.Index('idx_books_author', 'author'),
        db.Index('idx_books_category', 'category'),
        db.Index('idx_books_year', 'year'),
    )

    id = db.Column(db.Integer, primary_key=True)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255))
    year = db.Column(db.Integer)
    publisher = db.Column(db.String(255))
    image_url = db.Column(db.String(500))
    category = db.Column(db.String(100))

    ratings = db.relationship('Rating', backref='book', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'isbn': self.isbn,
            'title': self.title,
            'author': self.author,
            'year': self.year,
            'publisher': self.publisher,
            'image_url': self.image_url,
            'category': self.category
        }
