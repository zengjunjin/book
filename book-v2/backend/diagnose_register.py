"""
诊断脚本：检查注册 500 错误的具体原因
"""
import sys
import traceback
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.auth import get_password_hash

def test_register():
    db = SessionLocal()
    try:
        # 检查 users 表是否存在
        from sqlalchemy import text
        try:
            result = db.execute(text("SELECT COUNT(*) FROM users"))
            count = result.scalar()
            print(f"✅ users 表存在，当前用户数: {count}")
        except Exception as e:
            print(f"❌ users 表不存在: {e}")
            print("尝试创建表...")
            from app.database import engine
            from app.database import Base
            Base.metadata.create_all(bind=engine)
            print("已执行 create_all")
            return

        # 测试创建一个用户
        test_user = UserCreate(
            username=f"diag_user_{__import__('time').time():.0f}",
            email=f"diag_{__import__('time').time():.0f}@test.com",
            password="Test123456!"
        )

        # 检查是否已存在
        if db.query(User).filter(User.username == test_user.username).first():
            print(f"⚠️ 用户已存在: {test_user.username}")
            return

        print(f"📝 尝试创建用户: {test_user.username}")

        user = User(
            username=test_user.username,
            email=test_user.email,
            password_hash=get_password_hash(test_user.password)
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"✅ 用户创建成功! id={user.id}, username={user.username}")
        print(f"   created_at={user.created_at}")

        # 测试登录
        from app.services.auth import authenticate_user
        auth_user = authenticate_user(db, test_user.username, test_user.password)
        if auth_user:
            print(f"✅ 认证成功: id={auth_user.id}")
        else:
            print(f"❌ 认证失败")

    except Exception as e:
        print(f"❌ 错误: {e}")
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    test_register()
