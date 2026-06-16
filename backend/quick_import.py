"""快速导入评分 - 精简高效版"""
import sys
import pandas as pd
import time
from sqlalchemy import text

sys.path.insert(0, '.')

from app import create_app, db
from models import User, Rating

data_dir = r'C:\Users\15116\Desktop\book\backend\data'
app = create_app()

def main():
    with app.app_context():
        # 1. 获取已有的ISBN映射
        print("Step 1: Getting ISBN to book_id mapping from DB...")
        result = db.session.execute(text("SELECT isbn, id FROM books")).fetchall()
        isbn_to_id = {row[0]: row[1] for row in result}
        print(f"  Got {len(isbn_to_id)} books in DB")

        # 2. 加载评分CSV (只保留有匹配书籍的)
        print("Step 2: Loading ratings from CSV...")
        ratings_df = pd.read_csv(
            data_dir + r'\BX-Book-Ratings.csv',
            sep=';',
            encoding='latin-1',
            on_bad_lines='skip'
        )
        print(f"  Total in CSV: {len(ratings_df):,}")

        # 只保留显性评分 (1-10)
        ratings_df = ratings_df[ratings_df['Book-Rating'] > 0]
        print(f"  Explicit ratings: {len(ratings_df):,}")

        # 只保留有匹配书籍的评分
        ratings_df = ratings_df[ratings_df['ISBN'].isin(isbn_to_id.keys())]
        print(f"  With matching books: {len(ratings_df):,}")

        # 限制规模 - 取前15万条评分, 保证推荐算法效率
        MAX_RATINGS = 150000
        if len(ratings_df) > MAX_RATINGS:
            ratings_df = ratings_df.head(MAX_RATINGS)
            print(f"  Using first {MAX_RATINGS:,} ratings (for performance)")

        # 3. 准备用户数据
        print("\nStep 3: Creating users...")
        user_ids = sorted(set(ratings_df['User-ID'].values))
        print(f"  Users to create: {len(user_ids):,}")

        # 批量插入用户 (用原生SQL更快)
        batch_size = 2000
        user_batch = []
        for uid in user_ids:
            # 简单密码: password123 的hash (预生成)
            user_batch.append((uid, f"user_{uid}", f"user_{uid}@bookcrossing.com"))

            if len(user_batch) >= batch_size:
                db.session.bulk_insert_mappings(
                    User,
                    [{"id": u[0], "username": u[1], "email": u[2],
                      "password_hash": "pbkdf2:sha256:260000$test$hashed"}
                     for u in user_batch]
                )
                db.session.commit()
                user_batch = []
                print(f"  ...inserted {len(user_ids) if False else ''} users")

        # 插入剩余
        if user_batch:
            db.session.bulk_insert_mappings(
                User,
                [{"id": u[0], "username": u[1], "email": u[2],
                  "password_hash": "pbkdf2:sha256:260000$test$hashed"}
                 for u in user_batch]
            )
            db.session.commit()
        print(f"  Users in DB: {db.session.execute(text('SELECT COUNT(*) FROM users')).fetchone()[0]:,}")

        # 4. 批量插入评分 (最快方式: 原生SQL批量插入)
        print(f"\nStep 4: Inserting {len(ratings_df):,} ratings...")
        start_time = time.time()

        batch_size = 5000
        total = 0
        values_list = []

        for _, row in ratings_df.iterrows():
            book_id = isbn_to_id.get(str(row['ISBN']))
            if book_id:
                values_list.append((int(row['User-ID']), book_id, int(row['Book-Rating'])))

            if len(values_list) >= batch_size:
                db.session.bulk_insert_mappings(
                    Rating,
                    [{"user_id": v[0], "book_id": v[1], "rating": v[2]} for v in values_list]
                )
                db.session.commit()
                total += len(values_list)
                values_list = []
                pct = total / len(ratings_df) * 100
                print(f"  ...{total:,} / {len(ratings_df):,} ({pct:.0f}%)")

        if values_list:
            db.session.bulk_insert_mappings(
                Rating,
                [{"user_id": v[0], "book_id": v[1], "rating": v[2]} for v in values_list]
            )
            db.session.commit()
            total += len(values_list)

        elapsed = time.time() - start_time
        print(f"  Done! {total:,} ratings in {elapsed:.1f}s")

        # 5. 统计信息
        print("\n" + "="*60)
        print("=== IMPORT COMPLETE ===")
        total_books = db.session.execute(text('SELECT COUNT(*) FROM books')).fetchone()[0]
        total_users = db.session.execute(text('SELECT COUNT(*) FROM users')).fetchone()[0]
        total_ratings = db.session.execute(text('SELECT COUNT(*) FROM ratings')).fetchone()[0]
        print(f"Books:    {total_books:,}")
        print(f"Users:    {total_users:,}")
        print(f"Ratings:  {total_ratings:,}")

        # 评分分布
        dist = db.session.execute(text(
            'SELECT rating, COUNT(*) FROM ratings GROUP BY rating ORDER BY rating'
        )).fetchall()
        print("\nRating Distribution:")
        for score, cnt in dist:
            bar = '█' * max(1, cnt // 300)
            print(f"  {score:>2}: {cnt:>6,}  {bar}")

        avg = db.session.execute(text('SELECT AVG(rating) FROM ratings')).fetchone()[0]
        print(f"\nAverage: {avg:.2f}")

        # 热门书籍
        print("\nMost Rated Books:")
        top = db.session.execute(text("""
            SELECT b.title, COUNT(*) as cnt, AVG(r.rating) as avg_r
            FROM ratings r JOIN books b ON r.book_id = b.id
            GROUP BY b.id, b.title ORDER BY cnt DESC LIMIT 5
        """)).fetchall()
        for title, cnt, avg_r in top:
            print(f"  {avg_r:.1f} avg ({cnt} ratings) {title[:60]}")

        print("\n" + "="*60)
        print("READY! Start backend: python app.py")
        print("Start frontend: cd frontend && npm run dev")
        print("="*60)

if __name__ == '__main__':
    main()
