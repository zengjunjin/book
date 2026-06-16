"""
从 V1 数据库迁移数据到 V2
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import SessionLocal, Base, engine
from app.models import User, Book, Rating

# V1 数据库连接
V1_DATABASE_URL = "mysql+pymysql://root:password@localhost:3306/book_v1"


def migrate_data():
    print("开始数据迁移...")

    # 创建新数据库表
    Base.metadata.create_all(bind=engine)
    print("✓ 新数据库表已创建")

    v1_engine = create_engine(V1_DATABASE_URL)
    V1Session = sessionmaker(bind=v1_engine)

    v1_db = V1Session()
    v2_db = SessionLocal()

    try:
        # 迁移用户
        print("迁移用户数据...")
        v1_users = v1_db.execute("SELECT * FROM users").fetchall()
        for u in v1_users:
            existing = v2_db.query(User).filter(User.id == u.id).first()
            if not existing:
                user = User(
                    id=u.id,
                    username=u.username,
                    email=u.email,
                    password_hash=u.password_hash
                )
                v2_db.add(user)
        v2_db.commit()
        print(f"✓ 迁移了 {len(v1_users)} 个用户")

        # 迁移书籍
        print("迁移书籍数据...")
        v1_books = v1_db.execute("SELECT * FROM books").fetchall()
        for b in v1_books:
            existing = v2_db.query(Book).filter(Book.id == b.id).first()
            if not existing:
                book = Book(
                    id=b.id,
                    isbn=b.isbn,
                    title=b.title,
                    author=b.author,
                    year=b.year,
                    publisher=b.publisher,
                    image_url=b.image_url
                )
                v2_db.add(book)
        v2_db.commit()
        print(f"✓ 迁移了 {len(v1_books)} 本书")

        # 迁移评分
        print("迁移评分数据...")
        v1_ratings = v1_db.execute("SELECT * FROM ratings").fetchall()
        for r in v1_ratings:
            existing = v2_db.query(Rating).filter(
                Rating.user_id == r.user_id,
                Rating.book_id == r.book_id
            ).first()
            if not existing:
                rating = Rating(
                    user_id=r.user_id,
                    book_id=r.book_id,
                    rating=r.rating
                )
                v2_db.add(rating)
        v2_db.commit()
        print(f"✓ 迁移了 {len(v1_ratings)} 条评分")

        print("\n数据迁移完成！")

    finally:
        v1_db.close()
        v2_db.close()


if __name__ == "__main__":
    migrate_data()
