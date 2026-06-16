"""
快速导入所有用户和评分数据
- 使用 INSERT IGNORE 跳过已存在
- 已导入 271,046 本书，继续导入用户和评分
"""
import pandas as pd
import time
import pymysql
from datetime import datetime
from werkzeug.security import generate_password_hash

data_dir = r'C:\Users\15116\Desktop\book\backend\data'

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='123456',
    database='book_recommend',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

start_time = time.time()

try:
    with conn.cursor() as cursor:
        # ========== 导入评分 ==========
        print("=" * 70)
        print("Step 1: Importing ratings from BX-Book-Ratings.csv")
        print("=" * 70)

        print("  Reading CSV...")
        ratings_df = pd.read_csv(
            data_dir + r'\BX-Book-Ratings.csv',
            sep=';',
            encoding='latin-1',
            on_bad_lines='skip'
        )
        print(f"  Read {len(ratings_df):,} ratings")

        # 只保留显式评分
        ratings_df = ratings_df[ratings_df['Book-Rating'] > 0].copy()
        print(f"  Explicit ratings: {len(ratings_df):,}")

        # 建立 ISBN -> book_id 映射
        print("  Building ISBN to book_id map...")
        cursor.execute("SELECT isbn, id FROM books")
        isbn_to_bookid = {}
        for row in cursor.fetchall():
            isbn_to_bookid[row['isbn']] = row['id']
        print(f"  Map size: {len(isbn_to_bookid):,}")

        # 过滤
        ratings_df['book_id'] = ratings_df['ISBN'].map(isbn_to_bookid)
        ratings_df = ratings_df[ratings_df['book_id'].notna()].copy()
        print(f"  Ratings with matching books: {len(ratings_df):,}")

        # 获取所有用户 ID
        unique_users = sorted(set(ratings_df['User-ID'].values))
        print(f"  Unique users: {len(unique_users):,}")

        # ========== 导入用户 ==========
        print(f"\nStep 2: Inserting {len(unique_users):,} users...")
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        password_hash = generate_password_hash('password123')
        print(f"  Password hash: {password_hash[:80]}...")

        user_batch_size = 3000
        user_count = 0
        created_count = 0

        for i in range(0, len(unique_users), user_batch_size):
            batch_users = unique_users[i:i+user_batch_size]

            # 检查已存在用户
            placeholders = ','.join(['%s'] * len(batch_users))
            cursor.execute(f"SELECT id FROM users WHERE id IN ({placeholders})", batch_users)
            existing_ids = {row['id'] for row in cursor.fetchall()}

            # 只插入不存在的
            new_users = [uid for uid in batch_users if uid not in existing_ids]
            if new_users:
                insert_data = [
                    (uid, f'user_{uid}', f'user_{uid}@bookcrossing.com', password_hash, created_at)
                    for uid in new_users
                ]
                sql = "INSERT INTO users (id, username, email, password_hash, created_at) VALUES (%s, %s, %s, %s, %s)"
                cursor.executemany(sql, insert_data)
                created_count += len(new_users)

            user_count += len(batch_users)

            # 进度和提交
            if (i // user_batch_size) % 3 == 0:
                conn.commit()
                print(f"    Users: {user_count:,} / {len(unique_users):,}, New: {created_count:,}")

        conn.commit()
        print(f"  -> Created {created_count:,} new users")

        # ========== 插入评分 ==========
        print(f"\nStep 3: Inserting {len(ratings_df):,} ratings...")
        rating_batch_size = 5000
        new_ratings = 0
        rating_count = 0

        # 构建评分数据
        ratings_data = [
            (int(row['User-ID']), int(row['book_id']), int(row['Book-Rating']), created_at)
            for _, row in ratings_df.iterrows()
        ]

        for i in range(0, len(ratings_data), rating_batch_size):
            batch = ratings_data[i:i+rating_batch_size]
            sql = "INSERT IGNORE INTO ratings (user_id, book_id, rating, created_at) VALUES (%s, %s, %s, %s)"
            cursor.executemany(sql, batch)
            new_ratings += cursor.rowcount
            rating_count += len(batch)

            if (i // rating_batch_size) % 3 == 0:
                conn.commit()
                print(f"    Ratings: {rating_count:,} / {len(ratings_data):,}, New: {new_ratings:,}")

        conn.commit()
        print(f"  -> Total ratings now in DB: {new_ratings:,}")

        # ========== 最终统计 ==========
        print()
        print("=" * 70)
        print("FINAL STATISTICS")
        print("=" * 70)

        cursor.execute("SELECT COUNT(*) as cnt FROM books")
        final_books = cursor.fetchone()['cnt']
        cursor.execute("SELECT COUNT(*) as cnt FROM users")
        final_users = cursor.fetchone()['cnt']
        cursor.execute("SELECT COUNT(*) as cnt FROM ratings")
        final_ratings = cursor.fetchone()['cnt']
        cursor.execute("SELECT AVG(rating) as avg_r FROM ratings")
        avg_rating = cursor.fetchone()['avg_r']

        # 评分分布
        cursor.execute("SELECT rating, COUNT(*) as cnt FROM ratings GROUP BY rating ORDER BY rating")
        dist = cursor.fetchall()

        # 热门书籍
        cursor.execute("""
            SELECT b.title, COUNT(*) as rc, AVG(r.rating) as ar
            FROM ratings r JOIN books b ON r.book_id = b.id
            GROUP BY b.id, b.title ORDER BY rc DESC LIMIT 5
        """)
        top_books = cursor.fetchall()

        elapsed = time.time() - start_time
        print(f"\n  Total Books:    {final_books:>10,}")
        print(f"  Total Users:    {final_users:>10,}")
        print(f"  Total Ratings:  {final_ratings:>10,}")
        print(f"  Average Rating: {avg_rating:.2f}")
        print(f"  Total Time:     {elapsed:.1f}s")

        print(f"\n  Rating Distribution:")
        for row in dist:
            bar = '█' * max(1, row['cnt'] // 2000)
            print(f"    {row['rating']:>2}: {row['cnt']:>8,}  {bar}")

        print(f"\n  Most Rated Books:")
        for row in top_books:
            print(f"    {row['ar']:.1f} ({row['rc']:>5}) {str(row['title'])[:60]}")

        print()
        print("=" * 70)
        print("DATA IMPORT COMPLETE!")
        print(f"  Login with: username = user_XXXXX, password = password123")
        print(f"  Time: {elapsed:.1f}s")
        print("=" * 70)

finally:
    conn.close()
