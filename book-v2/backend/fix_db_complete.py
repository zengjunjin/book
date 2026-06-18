"""
完整数据库修复：
1. 同步 users/books/ratings 序列
2. 创建缺失的表 (interactions, reviews, discussions 等)
3. 验证注册功能
"""
import sys
from app.database import SessionLocal, engine, Base
from sqlalchemy import text
import time


def check_and_create_missing_tables():
    """检查并创建缺失的表"""
    print("=" * 70)
    print("步骤 1: 检查现有表")
    print("=" * 70)

    db = SessionLocal()
    try:
        result = db.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ))
        existing_tables = [r[0] for r in result.fetchall()]
        for t in existing_tables:
            r = db.execute(text(f"SELECT count(*) FROM {t}"))
            print(f"  ✅ {t}: {r.scalar()} 条记录")

        return existing_tables
    finally:
        db.close()


def sync_sequences(existing_tables):
    """同步所有现有表的序列"""
    print("\n" + "=" * 70)
    print("步骤 2: 同步 PostgreSQL 序列")
    print("=" * 70)

    db = SessionLocal()
    try:
        for table_name in existing_tables:
            try:
                # 检查是否有 id 列
                col_check = db.execute(text(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name = '{table_name}' AND column_name = 'id'"
                ))
                if not col_check.fetchone():
                    continue

                max_result = db.execute(text(f"SELECT MAX(id) FROM {table_name}"))
                max_id = max_result.scalar() or 0

                if max_id == 0:
                    print(f"  {table_name}: 空表，跳过")
                    continue

                # 查找关联序列
                seq_result = db.execute(text(
                    f"SELECT sequence_name FROM information_schema.sequences "
                    f"WHERE table_name = '{table_name}'"
                ))
                seq_rows = seq_result.fetchall()

                if not seq_rows:
                    # 尝试用 SERIAL 方式找到
                    try:
                        def_result = db.execute(text(
                            f"SELECT column_default FROM information_schema.columns "
                            f"WHERE table_name = '{table_name}' AND column_name = 'id'"
                        ))
                        default = def_result.scalar()
                        if default and 'nextval' in str(default):
                            import re
                            m = re.search(r"'([^']+)'", str(default))
                            if m:
                                seq_name = m.group(1).split('.')[-1].strip('"')
                                seq_rows = [(seq_name,)]
                    except:
                        pass

                if not seq_rows:
                    print(f"  ⚠️  {table_name}: 无序列信息, max_id={max_id}")
                    continue

                seq_name = seq_rows[0][0]

                try:
                    seq_result = db.execute(text(f"SELECT last_value FROM \"{seq_name}\""))
                    current_seq = seq_result.scalar() or 0
                except:
                    try:
                        seq_result = db.execute(text(f"SELECT nextval('\"{seq_name}\"') - 1"))
                        current_seq = seq_result.scalar() or 0
                    except:
                        current_seq = 0

                if max_id > current_seq:
                    new_value = max_id + 1
                    db.execute(text(f"SELECT setval('\"{seq_name}\"', {new_value}, false)"))
                    db.commit()
                    print(f"  ✅ {table_name}: 序列 {current_seq} -> {new_value} (max_id={max_id})")
                else:
                    print(f"  ✅ {table_name}: 已同步 (max_id={max_id}, seq={current_seq})")

            except Exception as e:
                print(f"  ❌ {table_name}: {e}")
                db.rollback()
    finally:
        db.close()


def create_missing_tables(existing_tables):
    """使用 SQLAlchemy 创建缺失的表"""
    print("\n" + "=" * 70)
    print("步骤 3: 创建缺失的表")
    print("=" * 70)

    # 导入所有模型注册到 Base.metadata
    from app.models.user import User
    from app.models.book import Book
    from app.models.rating import Rating
    from app.models.interaction import Interaction
    from app.models.recommendation_log import RecommendationLog

    # 查找缺失的表
    needed_tables = [t.name for t in Base.metadata.sorted_tables]
    missing = [t for t in needed_tables if t not in existing_tables]

    if missing:
        print(f"  创建 {len(missing)} 个缺失表: {', '.join(missing)}")
        Base.metadata.create_all(bind=engine, tables=[t for t in Base.metadata.sorted_tables if t.name in missing])
        print("  ✅ 创建完成")
    else:
        print("  ✅ 所有必需表已存在")

    # 同步新创建表的序列
    new_existing = check_and_create_missing_tables()
    return new_existing


def test_register():
    """验证注册功能"""
    print("\n" + "=" * 70)
    print("步骤 4: 验证注册功能")
    print("=" * 70)

    db = SessionLocal()
    try:
        from app.models.user import User
        from app.services.auth import get_password_hash

        test_name = f"fix_test_{int(time.time())}"
        test_user = User(
            username=test_name,
            email=f"{test_name}@fix.com",
            password_hash=get_password_hash("Test123!")
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        print(f"  ✅ 创建成功: id={test_user.id}, username={test_user.username}")

        # 清理
        db.delete(test_user)
        db.commit()
        print(f"  ✅ 清理完成")

        return True
    except Exception as e:
        print(f"  ❌ 验证失败: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def main():
    print("\n" + "=" * 70)
    print("数据库完整修复")
    print("=" * 70)

    existing_tables = check_and_create_missing_tables()
    existing_tables = create_missing_tables(existing_tables)
    sync_sequences(existing_tables)
    test_register()

    print("\n" + "=" * 70)
    print("✅ 全部完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
