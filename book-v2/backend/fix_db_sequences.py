"""
数据库修复脚本：
1. 修复所有表的 PostgreSQL 序列同步（解决 users_pkey / books_pkey 冲突）
2. 检查数据库结构一致性
"""
import sys
from app.database import SessionLocal, engine, Base
from sqlalchemy import text

TABLES_TO_CHECK = [
    "users",
    "books",
    "ratings",
    "book_tags",
    "interactions",
    "reviews",
    "discussions",
    "user_tags",
    "follows",
    "comments",
    "discussion_replies",
]


def sync_sequences():
    db = SessionLocal()
    try:
        print("=" * 70)
        print("PostgreSQL 序列同步修复")
        print("=" * 70)

        for table_name in TABLES_TO_CHECK:
            # 检查表是否存在
            try:
                result = db.execute(text(f"SELECT count(*) FROM {table_name}"))
                count = result.scalar()
            except Exception as e:
                print(f"  ⚠️  表 {table_name} 不存在或无法访问: {e}")
                continue

            # 检查序列
            seq_name = f"{table_name}_id_seq"
            try:
                # 获取当前最大 id
                max_result = db.execute(text(f"SELECT MAX(id) FROM {table_name}"))
                max_id = max_result.scalar() or 0

                # 获取当前序列值
                try:
                    seq_result = db.execute(text(f"SELECT last_value FROM \"{seq_name}\""))
                    current_seq = seq_result.scalar() or 0
                except Exception:
                    # 可能序列名不同，尝试查找
                    seq_result = db.execute(text(
                        f"SELECT sequence_name FROM information_schema.sequences "
                        f"WHERE table_name = '{table_name}'"
                    ))
                    seq_rows = seq_result.fetchall()
                    if not seq_rows:
                        print(f"  ⚠️  {table_name}: {count} 条记录, 但找不到序列")
                        continue
                    actual_seq = seq_rows[0][0]
                    seq_result2 = db.execute(text(f"SELECT last_value FROM \"{actual_seq}\""))
                    current_seq = seq_result2.scalar() or 0
                    seq_name = actual_seq

                gap = max_id - current_seq
                print(f"  {table_name}: {count} 条记录, max_id={max_id}, 当前序列={current_seq}, gap={gap}")

                if gap > 0 or (max_id > 0 and current_seq <= max_id):
                    # 需要同步序列
                    new_value = max_id + 1
                    db.execute(text(f"SELECT setval('\"{seq_name}\"', {new_value})"))
                    db.commit()
                    print(f"    ✅ 已同步序列: {current_seq} -> {new_value}")
                else:
                    print(f"    ✅ 序列已同步")

            except Exception as e:
                print(f"  ❌ 处理 {table_name} 时出错: {e}")
                db.rollback()

        print("\n" + "=" * 70)
        print("修复完成!")
        print("=" * 70)

        # 验证修复效果 - 创建一个测试用户
        from app.models.user import User
        from app.services.auth import get_password_hash
        import time

        test_name = f"fix_test_{int(time.time())}"
        try:
            test_user = User(
                username=test_name,
                email=f"{test_name}@fix.com",
                password_hash=get_password_hash("Test123!")
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            print(f"\n✅ 验证成功: 创建测试用户 id={test_user.id}, username={test_user.username}")

            # 清理测试用户
            db.delete(test_user)
            db.commit()
            print(f"✅ 已清理测试用户")
        except Exception as e:
            print(f"\n❌ 验证失败: {e}")
            db.rollback()

    except Exception as e:
        print(f"❌ 致命错误: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    sync_sequences()
