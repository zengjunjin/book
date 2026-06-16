"""部署脚本 001: 创建 books.title + books.author 的 FULLTEXT 索引

使用方法（首次部署时执行一次即可）:
    python scripts/001_create_fulltext_index.py

作用:
    - 在 books 表上创建 FULLTEXT 索引 ft_books_title_author (title, author)
    - 若已存在则跳过并提示
    - 失败时回退到安全状态，不影响其他表数据

注意:
    - 该脚本只在部署/运维时执行，应用请求层不会做 DDL
    - 修改前请确认 MySQL 配置允许 FULLTEXT 索引 (InnoDB 支持)
"""
import sys
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '.')

from extensions import db
from flask import Flask
from config import Config
from sqlalchemy import text


def main():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        # 1. 先检查 books 表是否存在
        try:
            db.session.execute(text("SELECT COUNT(*) FROM books LIMIT 1")).fetchone()
            print('[OK] books 表存在')
        except Exception as e:
            print(f'[ERR] books 表不存在或无法访问: {e}')
            print('      请先执行数据导入（例如 import_data.py 或 import_bookcrossing.py）')
            return 1

        # 2. 检查 FULLTEXT 索引是否已存在
        try:
            result = db.session.execute(text(
                "SELECT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "  AND TABLE_NAME = 'books' "
                "  AND INDEX_TYPE = 'FULLTEXT' "
                "LIMIT 1"
            )).fetchone()
            if result:
                print(f'[SKIP] FULLTEXT 索引已存在: {result[0]}')
                return 0
        except Exception as e:
            print(f'[WARN] 检查索引失败（可能数据库不支持 information_schema）: {e}')

        # 3. 创建 FULLTEXT 索引
        print('[RUN] 正在创建 FULLTEXT 索引 ft_books_title_author (title, author)...')
        try:
            db.session.execute(
                text("ALTER TABLE books ADD FULLTEXT INDEX ft_books_title_author (title, author)")
            )
            db.session.commit()
            print('[OK] FULLTEXT 索引创建成功')
        except Exception as e:
            err_msg = str(e).lower()
            if 'duplicate' in err_msg or 'exists' in err_msg:
                print('[SKIP] 索引已存在，跳过')
                return 0
            print(f'[ERR] 创建索引失败: {e}')
            db.session.rollback()
            return 1

        # 4. 简单验证
        try:
            test = db.session.execute(text(
                "SELECT id, title FROM books "
                "WHERE MATCH(title, author) AGAINST('Harry' IN BOOLEAN MODE) "
                "LIMIT 3"
            )).fetchall()
            print(f'[OK] 索引验证通过，MATCH 查询命中 {len(test)} 条示例')
            for row in test:
                print(f'     - #{row[0]}: {row[1][:60]}')
        except Exception as e:
            print(f'[WARN] 验证失败，但索引可能已生效: {e}')

        return 0


if __name__ == '__main__':
    code = main()
    sys.exit(code)
