"""
高效导入完整的 Book-Crossing 数据集
- 271,379 本书
- 1,149,780 条评分
- 278,859 用户

使用 pymysql 批量插入，跳过已存在记录
"""
import pandas as pd
import time
import pymysql
from datetime import datetime

data_dir = r'C:\Users\15116\Desktop\book\backend\data'

# 数据库连接
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
        # 1. 导入书籍数据 (INSERT IGNORE 跳过已存在的)
        print("=" * 70)
        print(f"Step 1: Importing books from BX-Books.csv")
        print("=" * 70)

        print("  Reading CSV...")
        books_df = pd.read_csv(
            data_dir + r'\BX-Books.csv',
            sep=';',
            encoding='latin-1',
            on_bad_lines='skip',
            dtype={'ISBN': str, 'Year-Of-Publication': str}
        )
        print(f"  Read {len(books_df):,} books from CSV")

        # 准备数据
        books_data = []
        for _, row in books_df.iterrows():
            isbn = str(row['ISBN'])[:20]
            title = str(row['Book-Title'])[:255]
            author = str(row['Book-Author'])[:255] if pd.notna(row['Book-Author']) else None
            year = row['Year-Of-Publication']
            try:
                year_val = int(year) if year and str(year).isdigit() else None
            except:
                year_val = None
            publisher = str(row['Publisher'])[:255] if pd.notna(row['Publisher']) else None
            image_url = str(row['Image-URL-L'])[:500] if pd.notna(row['Image-URL-L']) else None

            books_data.append((isbn, title, author, year_val, publisher, image_url, None))

        # 批量插入
        batch_size = 2000
        total_inserted = 0
        total_touched = 0

        print(f"  Inserting in batches of {batch_size}...")
        for i in range(0, len(books_data), batch_size):
            batch = books_data[i:i+batch_size]
            sql = """INSERT IGNORE INTO books (isbn, title, author, year, publisher, image_url, category)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            cursor.executemany(sql, batch)
            total_touched += len(batch)
            total_inserted += cursor.rowcount
            if (i // batch_size) % 10 == 0:
                print(f"    Processed {total_touched:,} / {len(books_data):,}, New: {total_inserted:,}")

        conn.commit()
        print(f"  -> Total books now in DB: {total_inserted:,} new")

        # 验证总数
        cursor.execute("SELECT COUNT(*) as cnt FROM books")
        book_count = cursor.fetchone()['cnt']
        print(f"  Total books in DB: {book_count:,}")

        # 2. 导入评分数据
        print()
        print("=" * 70)
        print(f"Step 2: Importing ratings from BX-Book-Ratings.csv")
        print("=" * 70)

        print("  Reading CSV...")
        ratings_df = pd.read_csv(
            data_dir + r'\BX-Book-Ratings.csv',
            sep=';',
            encoding='latin-1',
            on_bad_lines='skip'
        )
        print(f"  Read {len(ratings_df):,} ratings from CSV")

        # 只保留显式评分 (>0)
        ratings_df = ratings_df[ratings_df['Book-Rating'] > 0].copy()
        print(f"  Explicit ratings: {len(ratings_df):,}")

        # 建立 ISBN -> book_id 映射 (从已导入的书籍中)
        print("  Building ISBN to book_id map...")
        cursor.execute("SELECT isbn, id FROM books")
        isbn_to_bookid = {}
        for row in cursor.fetchall():
            isbn_to_bookid[row['isbn']] = row['id']
        print(f"  Map size: {len(isbn_to_bookid):,} books")

        # 过滤：只保留能对应到书籍的评分
        ratings_df['book_id'] = ratings_df['ISBN'].map(isbn_to_bookid)
        ratings_df = ratings_df[ratings_df['book_id'].notna()].copy()
        print(f"  Ratings with matching books: {len(ratings_df):,}")

        # 创建用户列表
        unique_users = sorted(set(ratings_df['User-ID'].values))
        print(f"  Unique users: {len(unique_users):,}")

        # 批量插入用户
        print(f"\n  Inserting {len(unique_users):,} users...")
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 预生成密码 hash (pbkdf2:sha256) - 使用 scrypt 兼容格式
        # 为了简化，这里用 werkzeug 生成的标准 scrypt hash
        # 先用一个空 password_hash，之后用 Python 更新
        # 但由于 scrypt 需要特定参数，我们先插入一个占位，然后批量更新
        # 简单起见，先插入空，之后再用 Python 设置

        # 分批次插入用户
        user_batch_size = 3000
        user_count = 0
        created_count = 0

        for i in range(0, len(unique_users), user_batch_size):
            batch_users = unique_users[i:i+user_batch_size]

            # 先查哪些用户已存在
            placeholders = ','.join(['%s'] * len(batch_users))
            cursor.execute(f"SELECT id FROM users WHERE id IN ({placeholders})", batch_users)
            existing_ids = {row['id'] for row in cursor.fetchall()}

            # 只插入不存在的
            new_users = [uid for uid in batch_users if uid not in existing_ids]
            if not new_users:
                user_count += len(batch_users)
                continue

            # 批量插入新用户
            insert_data = [
                (uid, f'user_{uid}', f'user_{uid}@bookcrossing.com', created_at)
                for uid in new_users
            ]
            sql = """INSERT INTO users (id, username, email, created_at) VALUES (%s, %s, %s, %s)"""
            cursor.executemany(sql, insert_data)
            created_count += len(new_users)
            user_count += len(batch_users)

            if (i // user_batch_size) % 5 == 0:
                print(f"    Users: {user_count:,} / {len(unique_users):,}, New: {created_count:,}")

            # 每 15000 用户提交一次
            if (i // user_batch_size) % 5 == 0:
                conn.commit()

        conn.commit()
        print(f"  -> Total users in DB: created {created_count:,} new")

        # 3. 批量插入评分
        print(f"\n  Inserting {len(ratings_df):,} ratings...")
        rating_batch_size = 5000
        rating_count = 0
        new_ratings = 0
        created_at_rating = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 准备评分数据
        ratings_to_insert = []
        for _, row in ratings_df.iterrows():
            user_id = int(row['User-ID'])
            book_id = int(row['book_id'])
            rating_val = int(row['Book-Rating'])
            ratings_to_insert.append((user_id, book_id, rating_val, created_at_rating))

        # 批量插入
        for i in range(0, len(ratings_to_insert), rating_batch_size):
            batch = ratings_to_insert[i:i+rating_batch_size]
            sql = """INSERT IGNORE INTO ratings (user_id, book_id, rating, created_at)
                     VALUES (%s, %s, %s, %s)"""
            cursor.executemany(sql, batch)
            new_ratings += cursor.rowcount
            rating_count += len(batch)

            if (i // rating_batch_size) % 5 == 0:
                print(f"    Ratings: {rating_count:,} / {len(ratings_to_insert):,}, New: {new_ratings:,}")

            # 每 25000 评分提交一次
            if (i // rating_batch_size) % 5 == 0:
                conn.commit()

        conn.commit()
        print(f"  -> Total ratings now in DB: {new_ratings:,} new")

        # 4. 设置用户密码
        print()
        print("=" * 70)
        print("Step 3: Setting passwords for users")
        print("=" * 70)

        # 使用 werkzeug 生成一个标准 scrypt hash
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash('password123')
        print(f"  Password hash: {password_hash[:80]}...")

        # 更新所有 password_hash 为空或旧格式的用户
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE password_hash IS NULL OR password_hash = '' OR password_hash LIKE '%test%'",
            (password_hash,)
        )
        updated_count = cursor.rowcount
        conn.commit()
        print(f"  Updated {updated_count:,} users with new password")

        # 5. 最终统计
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

        # 平均评分
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
            bar = '█' * (row['cnt'] // 3000)
            print(f"    {row['rating']:>2}: {row['cnt']:>8,}  {bar}")

        print(f"\n  Top Rated Books:")
        for row in top_books:
            print(f"    {row['ar']:.1f} ({row['rc']:>5}) {str(row['title'])[:50]}")

        print()
        print("=" * 70)
        print("DATA IMPORT COMPLETE!")
        print("  All users can login with: password123")
        print(f"  Time: {elapsed:.1f}s")
        print("=" * 70)

finally:
    conn.close()
