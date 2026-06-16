"""批量更新用户密码"""
import sys
sys.path.insert(0, '.')

from app import create_app
from models import User

app = create_app()

with app.app_context():
    # 生成密码 hash
    password = 'password123'
    temp_user = User(username='_temp', email='_temp@test.com')
    temp_user.set_password(password)
    hash_value = temp_user.password_hash
    print(f"New password hash: {hash_value[:60]}...")

    # 用 SQL 批量更新所有未正确设置密码的用户
    from extensions import db
    from sqlalchemy import text

    # 更新所有用户的密码
    result = db.session.execute(
        text("UPDATE users SET password_hash = :hash WHERE password_hash NOT LIKE :scrypt_prefix"),
        {"hash": hash_value, "scrypt_prefix": "scrypt:%"}
    )
    db.session.commit()
    print(f"Updated {result.rowcount} users")

    # 验证
    total = db.session.execute(text("SELECT COUNT(*) FROM users")).fetchone()[0]
    print(f"Total users: {total}")

    # 测试登录
    test_user = User.query.filter_by(username='user_276729').first()
    if test_user:
        print(f"\nTest user: user_276729")
        print(f"Password check: {test_user.check_password('password123')}")
    else:
        print("\nuser_276729 not found, testing other user...")
        user = User.query.first()
        if user:
            print(f"Found user: {user.username}")
            print(f"Password check: {user.check_password('password123')}")

    # 找到一个有评分的用户
    rating_user = db.session.execute(text("""
        SELECT u.id, u.username, COUNT(r.id) as rating_count
        FROM users u JOIN ratings r ON u.id = r.user_id
        GROUP BY u.id, u.username
        ORDER BY rating_count DESC
        LIMIT 3
    """)).fetchall()

    print("\nTop rated users:")
    for uid, uname, cnt in rating_user:
        print(f"  User {uid} ({uname}): {cnt} ratings")

    print("\nPassword update complete!")
    print("All users can now login with: password123")
