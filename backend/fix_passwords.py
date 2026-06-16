"""用 Python 批量更新用户密码 - 确保 hash 格式正确"""
import sys
sys.path.insert(0, '.')

from app import create_app
from models import User
from extensions import db

app = create_app()

with app.app_context():
    # 找到评分最多的用户ID
    from sqlalchemy import text

    top_users = db.session.execute(text("""
        SELECT u.id, COUNT(r.id) as cnt
        FROM users u JOIN ratings r ON u.id = r.user_id
        GROUP BY u.id
        ORDER BY cnt DESC
        LIMIT 5
    """)).fetchall()

    print("Top rated users:")
    for uid, cnt in top_users:
        print(f"  User ID: {uid} ({cnt} ratings)")

    # 更新前 1000 个用户密码（用于演示）
    # 找到有评分的用户
    users_with_ratings = db.session.execute(text("""
        SELECT DISTINCT u.id FROM users u
        JOIN ratings r ON u.id = r.user_id
        LIMIT 5000
    """)).fetchall()

    user_ids = [row[0] for row in users_with_ratings]
    print(f"\nUpdating passwords for {len(user_ids)} users with ratings...")

    # 用 Python 生成正确的 hash
    temp = User(username='_tmp', email='_tmp@test.com')
    temp.set_password('password123')
    hash_val = temp.password_hash
    print(f"Password hash: {hash_val[:80]}...")

    # 批量更新
    update_sql = text("UPDATE users SET password_hash = :hash WHERE id IN :ids")

    # 分批更新
    batch_size = 500
    updated = 0
    for i in range(0, len(user_ids), batch_size):
        batch = tuple(user_ids[i:i+batch_size])
        db.session.execute(
            text(f"UPDATE users SET password_hash = :hash WHERE id IN ({','.join(map(str, batch))})"),
            {"hash": hash_val}
        )
        updated += len(batch)
        print(f"  Updated {updated}/{len(user_ids)}")

    db.session.commit()
    print(f"\nUpdated {updated} users total")

    # 测试
    test_uid = user_ids[0]
    test_user = User.query.get(test_uid)
    print(f"\nTest user {test_user.username}:")
    print(f"  Password check: {test_user.check_password('password123')}")

    print(f"\nDONE! Users can login with: password123")
    print(f"Try user: {test_user.username}")
