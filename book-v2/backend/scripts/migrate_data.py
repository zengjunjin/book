"""
从 V1 数据库迁移数据到 V2
"""
import sys
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.database import SessionLocal, Base, engine
from app.models.user import User
from app.models.book import Book
from app.models.rating import Rating

V1_DATABASE_URL = "mysql+pymysql://root:123456@localhost:3306/book_recommend?charset=utf8mb4"

BATCH_SIZE = 10000


def migrate_users(v1_db, v2_db):
    print("迁移用户数据...")
    offset = 0
    total = 0
    
    while True:
        v1_users = v1_db.execute(text(
            "SELECT id, username, email, password_hash FROM users LIMIT :limit OFFSET :offset"
        ), {"limit": BATCH_SIZE, "offset": offset}).fetchall()
        
        if not v1_users:
            break
        
        batch_emails = set()
        
        for u in v1_users:
            existing = v2_db.query(User).filter(User.id == u.id).first()
            if not existing:
                base_email = u.email or f'user_{u.id}@example.com'
                email = base_email
                counter = 1
                
                while v2_db.query(User).filter(User.email == email).first() or email in batch_emails:
                    if '@' in base_email:
                        name, domain = base_email.rsplit('@', 1)
                        email = f'{name}_{counter}@{domain}'
                    else:
                        email = f'{base_email}_{counter}'
                    counter += 1
                
                batch_emails.add(email)
                
                user = User(
                    id=u.id,
                    username=u.username or f'user_{u.id}',
                    email=email,
                    password_hash=u.password_hash
                )
                v2_db.add(user)
        
        v2_db.commit()
        total += len(v1_users)
        offset += BATCH_SIZE
        print(f"  已迁移 {total} 个用户...")
    
    print(f"✓ 迁移了 {total} 个用户")
    return total


def safe_string(s):
    if s is None:
        return None
    if isinstance(s, bytes):
        try:
            s = s.decode('utf-8')
        except:
            s = s.decode('latin-1', errors='ignore')
    return s

def migrate_books(v1_db, v2_db):
    print("迁移书籍数据...")
    offset = 0
    total = 0
    
    while True:
        v1_books = v1_db.execute(text(
            "SELECT id, isbn, title, author, year, publisher, image_url FROM books LIMIT :limit OFFSET :offset"
        ), {"limit": BATCH_SIZE, "offset": offset}).fetchall()
        
        if not v1_books:
            break
        
        for b in v1_books:
            existing = v2_db.query(Book).filter(Book.id == b.id).first()
            if not existing:
                book = Book(
                    id=b.id,
                    isbn=safe_string(b.isbn),
                    title=safe_string(b.title),
                    author=safe_string(b.author),
                    year=b.year,
                    publisher=safe_string(b.publisher),
                    image_url=safe_string(b.image_url)
                )
                v2_db.add(book)
        
        v2_db.commit()
        total += len(v1_books)
        offset += BATCH_SIZE
        print(f"  已迁移 {total} 本书...")
    
    print(f"✓ 迁移了 {total} 本书")
    return total


def migrate_ratings(v1_db, v2_db):
    print("迁移评分数据...")
    offset = 0
    total = 0
    
    while True:
        v1_ratings = v1_db.execute(text(
            "SELECT user_id, book_id, rating FROM ratings LIMIT :limit OFFSET :offset"
        ), {"limit": BATCH_SIZE, "offset": offset}).fetchall()
        
        if not v1_ratings:
            break
        
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
        total += len(v1_ratings)
        offset += BATCH_SIZE
        print(f"  已迁移 {total} 条评分...")
    
    print(f"✓ 迁移了 {total} 条评分")
    return total


def migrate_data():
    print("开始数据迁移...")
    print(f"批次大小: {BATCH_SIZE}")

    Base.metadata.create_all(bind=engine)
    print("✓ 新数据库表已创建")

    v1_engine = create_engine(V1_DATABASE_URL)
    V1Session = sessionmaker(bind=v1_engine)

    v1_db = V1Session()
    v2_db = SessionLocal()

    try:
        migrate_users(v1_db, v2_db)
        migrate_books(v1_db, v2_db)
        migrate_ratings(v1_db, v2_db)

        print("\n数据迁移完成！")

    finally:
        v1_db.close()
        v2_db.close()


if __name__ == "__main__":
    migrate_data()
