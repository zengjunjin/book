import pandas as pd
import numpy as np
from extensions import db
from models import Book, Rating, User


def prepare_rating_matrix():
    """从数据库准备用户-物品评分矩阵"""
    ratings = Rating.query.all()

    if not ratings:
        return (
            np.zeros((0, 0), dtype=np.float32),
            {},
            {},
            pd.DataFrame(columns=['user_id', 'book_id', 'rating'])
        )

    data = []
    for r in ratings:
        data.append({
            'user_id': r.user_id,
            'book_id': r.book_id,
            'rating': r.rating
        })

    df = pd.DataFrame(data)

    # 聚合：对同一 (user_id, book_id) 对的多条评分取均值
    # 防止数据库重复记录导致评分异常（被累加）
    if len(df) > 0:
        df = df.groupby(['user_id', 'book_id'], as_index=False)['rating'].mean()
        df['rating'] = df['rating'].clip(1, 10)  # 确保评分范围合理

    # 创建用户和书籍的ID映射
    user_ids = sorted(df['user_id'].unique().tolist())
    book_ids = sorted(df['book_id'].unique().tolist())

    user_id_map = {uid: i for i, uid in enumerate(user_ids)}
    book_id_map = {bid: i for i, bid in enumerate(book_ids)}

    n_users = len(user_ids)
    n_books = len(book_ids)

    # 使用稀疏矩阵节省内存
    from scipy import sparse
    row_indices = [user_id_map[u] for u in df['user_id']]
    col_indices = [book_id_map[b] for b in df['book_id']]
    values = df['rating'].astype(np.float32).values

    rating_matrix = sparse.csr_matrix(
        (values, (row_indices, col_indices)),
        shape=(n_users, n_books),
        dtype=np.float32
    )

    return rating_matrix, user_id_map, book_id_map, df


def load_book_crossing_data(books_path, ratings_path, users_path=None):
    """加载Book-Crossing数据集文件"""
    books_df = pd.read_csv(books_path, sep=';', encoding='latin-1', on_bad_lines='skip')
    books_df.columns = ['isbn', 'title', 'author', 'year', 'publisher',
                        'image_url_s', 'image_url_m', 'image_url_l']

    ratings_df = pd.read_csv(ratings_path, sep=';', encoding='latin-1')
    ratings_df.columns = ['user_id', 'isbn', 'rating']

    # 只保留显性评分 (>0)
    ratings_df = ratings_df[ratings_df['rating'] > 0]

    return books_df, ratings_df


def import_books_to_db(books_df, batch_size=1000):
    """批量导入书籍数据"""
    from sqlalchemy.dialects.mysql import insert

    books_to_insert = []
    for _, row in books_df.iterrows():
        book_data = {
            'isbn': str(row['isbn']),
            'title': str(row['title']) if pd.notna(row['title']) else '',
            'author': str(row['author']) if pd.notna(row['author']) else None,
            'year': None,
            'publisher': str(row['publisher']) if pd.notna(row['publisher']) else None,
            'image_url': str(row['image_url_l']) if pd.notna(row['image_url_l']) else None,
            'category': None
        }

        try:
            year_val = row['year']
            if pd.notna(year_val):
                year_str = str(year_val)
                if year_str.isdigit() and len(year_str) == 4:
                    book_data['year'] = int(year_str)
        except Exception:
            pass

        books_to_insert.append(book_data)

    total = len(books_to_insert)
    for i in range(0, total, batch_size):
        batch = books_to_insert[i:i + batch_size]
        stmt = insert(Book).values(batch)
        stmt = stmt.on_duplicate_key_update(
            title=stmt.inserted.title,
            author=stmt.inserted.author
        )
        db.session.execute(stmt)
        db.session.commit()
        print(f'  已导入 {min(i + batch_size, total)} / {total} 本书')

    print(f'  共导入 {Book.query.count()} 本书')


def import_ratings_to_db(ratings_df, batch_size=5000):
    """批量导入评分数据"""
    from sqlalchemy.dialects.mysql import insert

    # 建立 ISBN -> book_id 映射
    isbns = ratings_df['isbn'].unique().tolist()
    book_map = {}
    for b in Book.query.filter(Book.isbn.in_([str(x) for x in isbns])).all():
        book_map[b.isbn] = b.id

    # 过滤出有对应书籍的评分
    valid_ratings = ratings_df[ratings_df['isbn'].astype(str).isin(book_map.keys())].copy()
    print(f'  有效评分记录: {len(valid_ratings)}')

    # 创建用户和评分
    user_ids = sorted(valid_ratings['user_id'].unique().tolist())

    # 批量插入用户
    users_to_insert = [{'id': int(uid), 'username': f'user_{uid}', 'email': None, 'password_hash': ''}
                       for uid in user_ids]

    for i in range(0, len(users_to_insert), batch_size):
        batch = users_to_insert[i:i + batch_size]
        stmt = insert(User).values(batch)
        stmt = stmt.prefix_with('IGNORE')
        db.session.execute(stmt)
        db.session.commit()
        print(f'  已导入 {min(i + batch_size, len(users_to_insert))} / {len(users_to_insert)} 个用户')

    # 批量插入评分
    ratings_to_insert = []
    for _, row in valid_ratings.iterrows():
        book_id = book_map.get(str(row['isbn']))
        if book_id is None:
            continue
        ratings_to_insert.append({
            'user_id': int(row['user_id']),
            'book_id': book_id,
            'rating': int(row['rating'])
        })

    total = len(ratings_to_insert)
    for i in range(0, total, batch_size):
        batch = ratings_to_insert[i:i + batch_size]
        stmt = insert(Rating).values(batch)
        stmt = stmt.prefix_with('IGNORE')
        db.session.execute(stmt)
        db.session.commit()
        print(f'  已导入 {min(i + batch_size, total)} / {total} 条评分')

    print(f'  共导入 {Rating.query.count()} 条评分')
