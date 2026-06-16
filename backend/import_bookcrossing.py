"""高效导入Book-Crossing数据集到MySQL"""
import sys
import pandas as pd
import time

sys.path.insert(0, '.')

from app import create_app, db
from models import Book, User, Rating

data_dir = r'C:\Users\15116\Desktop\book\backend\data'

app = create_app()

def main():
    with app.app_context():
        # 1. 清空现有数据
        print("=" * 60)
        print("Step 1: Clearing existing data...")
        db.session.query(Rating).delete()
        db.session.query(Book).delete()
        db.session.query(User).delete()
        db.session.commit()
        print("  OK - All tables cleared")

        # 2. 导入书籍数据
        print("\n" + "=" * 60)
        print("Step 2: Loading books from BX-Books.csv...")
        start_time = time.time()

        books_df = pd.read_csv(
            data_dir + r'\BX-Books.csv',
            sep=';',
            encoding='latin-1',
            on_bad_lines='skip',
            nrows=5000  # 导入前5000本
        )
        print(f"  Read {len(books_df)} books from CSV")

        # 批量插入
        print("  Inserting into MySQL...")
        batch_size = 500
        count = 0
        for start in range(0, len(books_df), batch_size):
            batch = books_df.iloc[start:start+batch_size]
            books_to_insert = []
            for _, row in batch.iterrows():
                try:
                    year_val = int(row['Year-Of-Publication']) if pd.notna(row['Year-Of-Publication']) and str(row['Year-Of-Publication']).isdigit() else None
                except:
                    year_val = None

                book = Book(
                    isbn=str(row['ISBN'])[:20],
                    title=str(row['Book-Title'])[:255],
                    author=str(row['Book-Author'])[:255] if pd.notna(row['Book-Author']) else None,
                    year=year_val,
                    publisher=str(row['Publisher'])[:255] if pd.notna(row['Publisher']) else None,
                    image_url=str(row['Image-URL-L'])[:500] if pd.notna(row['Image-URL-L']) else None,
                    category=None  # 原数据集没有分类字段
                )
                books_to_insert.append(book)
            db.session.bulk_save_objects(books_to_insert)
            count += len(books_to_insert)
            if count % 1000 == 0:
                print(f"  ...{count} books inserted")

        db.session.commit()
        elapsed = time.time() - start_time
        print(f"  Completed: {Book.query.count()} books in {elapsed:.1f}s")

        # 3. 建立ISBN到book_id的映射
        print("\n" + "=" * 60)
        print("Step 3: Building ISBN to book_id mapping...")
        books = Book.query.all()
        isbn_to_id = {b.isbn: b.id for b in books}
        print(f"  Built map with {len(isbn_to_id)} books")

        # 4. 导入评分数据 (只导入有对应书籍的评分)
        print("\n" + "=" * 60)
        print("Step 4: Loading ratings from BX-Book-Ratings.csv...")
        start_time = time.time()

        ratings_df = pd.read_csv(
            data_dir + r'\BX-Book-Ratings.csv',
            sep=';',
            encoding='latin-1',
            on_bad_lines='skip'
        )
        print(f"  Read {len(ratings_df)} ratings from CSV")

        # 过滤: 只保留显性评分 (rating > 0) 和有对应书籍的记录
        ratings_df = ratings_df[ratings_df['Book-Rating'] > 0]
        ratings_df = ratings_df[ratings_df['ISBN'].isin(isbn_to_id.keys())]
        print(f"  Filtered to {len(ratings_df)} explicit ratings with matching books")

        # 取前30万条评分限制计算规模
        ratings_df = ratings_df.head(300000)
        print(f"  Using {len(ratings_df)} ratings for the system")

        # 5. 创建用户 (从评分数据中提取用户ID)
        print("\n" + "=" * 60)
        print("Step 5: Creating user accounts...")
        unique_user_ids = set(ratings_df['User-ID'].values)
        print(f"  Creating {len(unique_user_ids)} users")

        users_to_insert = []
        for uid in unique_user_ids:
            user = User(
                id=uid,
                username=f"user_{uid}",
                email=f"user_{uid}@bookcrossing.com"
            )
            user.set_password("password123")
            users_to_insert.append(user)

        # 批量插入用户
        batch_size = 2000
        for start in range(0, len(users_to_insert), batch_size):
            batch = users_to_insert[start:start+batch_size]
            db.session.bulk_save_objects(batch)
            db.session.commit()
            if (start + batch_size) % 10000 == 0:
                print(f"  ...{min(start + batch_size, len(users_to_insert))} users inserted")

        print(f"  Total users in DB: {User.query.count()}")

        # 6. 插入评分
        print("\n" + "=" * 60)
        print("Step 6: Inserting ratings into MySQL...")

        batch_size = 5000
        total_inserted = 0
        ratings_to_insert = []

        for _, row in ratings_df.iterrows():
            book_id = isbn_to_id.get(str(row['ISBN']))
            if not book_id:
                continue

            rating = Rating(
                user_id=int(row['User-ID']),
                book_id=book_id,
                rating=int(row['Book-Rating'])
            )
            ratings_to_insert.append(rating)

            if len(ratings_to_insert) >= batch_size:
                db.session.bulk_save_objects(ratings_to_insert)
                db.session.commit()
                total_inserted += len(ratings_to_insert)
                ratings_to_insert = []
                if total_inserted % 50000 == 0:
                    print(f"  ...{total_inserted} ratings inserted")

        # 插入剩余的
        if ratings_to_insert:
            db.session.bulk_save_objects(ratings_to_insert)
            db.session.commit()
            total_inserted += len(ratings_to_insert)

        elapsed = time.time() - start_time
        print(f"  Total ratings in DB: {Rating.query.count()} (in {elapsed:.1f}s)")

        # 7. 汇总统计
        print("\n" + "=" * 60)
        print("=== DATA IMPORT COMPLETE ===")
        print("=" * 60)
        print(f"Total Books:    {Book.query.count():>8,}")
        print(f"Total Users:    {User.query.count():>8,}")
        print(f"Total Ratings:  {Rating.query.count():>8,}")

        # 评分分布
        from sqlalchemy import func
        dist = db.session.query(Rating.rating, func.count(Rating.id))\
            .group_by(Rating.rating).order_by(Rating.rating).all()
        print("\nRating Distribution:")
        for score, cnt in dist:
            bar = '█' * (cnt // 500)
            print(f"  {score:>2} stars: {cnt:>8,}  {bar}")

        # 平均评分
        avg_rating = db.session.query(func.avg(Rating.rating)).scalar()
        print(f"\nAverage rating: {avg_rating:.2f}")

        # 热门书籍
        print("\nTop Rated Books (min 5 ratings):")
        result = db.session.query(
            Book.title,
            func.avg(Rating.rating).label('avg_rating'),
            func.count(Rating.id).label('rating_count')
        ).join(Rating, Book.id == Rating.book_id)\
         .group_by(Book.id, Book.title)\
         .having(func.count(Rating.id) >= 5)\
         .order_by(func.avg(Rating.rating).desc())\
         .limit(10).all()

        for title, avg, cnt in result:
            print(f"  {avg:.1f} ({cnt:>4} ratings) - {title[:50]}")

        print("\n" + "=" * 60)
        print("Login with any user (user_XXXX) and password: password123")
        print("Or register a new account in the frontend!")
        print("=" * 60)


if __name__ == '__main__':
    main()
