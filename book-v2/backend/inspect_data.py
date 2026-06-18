"""检查 Book 表数据分布"""
from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

print("=== Book 表检查 ===")
r = db.execute(text("SELECT MIN(id), MAX(id), COUNT(*) FROM books"))
min_id, max_id, count = r.fetchone()
print(f"id 范围: {min_id} ~ {max_id}, 总数: {count}")

print("\n前 10 个 id:")
r = db.execute(text("SELECT id, title FROM books ORDER BY id LIMIT 10"))
for row in r.fetchall():
    print(f"  id={row[0]:8d}  {str(row[1])[:60]}")

print("\n后 10 个 id:")
r = db.execute(text("SELECT id, title FROM books ORDER BY id DESC LIMIT 10"))
for row in r.fetchall():
    print(f"  id={row[0]:8d}  {str(row[1])[:60]}")

print("\n=== 检查 category 字段 ===")
r = db.execute(text("SELECT COUNT(*) FROM books WHERE category IS NOT NULL AND category != ''"))
cat_count = r.scalar()
print(f"有 category 的书籍数: {cat_count} / {count}")

print("\n=== 检查 author 字段 ===")
r = db.execute(text("SELECT COUNT(*) FROM books WHERE author IS NOT NULL AND author != ''"))
author_count = r.scalar()
print(f"有 author 的书籍数: {author_count} / {count}")

if author_count > 0:
    r = db.execute(text("SELECT author, COUNT(*) as cnt FROM books "
                        "WHERE author IS NOT NULL AND author != '' "
                        "GROUP BY author ORDER BY cnt DESC LIMIT 10"))
    print("\n热门作者:")
    for row in r.fetchall():
        print(f"  {row[0][:50]:50s}  {row[1]} 本")

db.close()
