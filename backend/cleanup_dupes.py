from app import create_app
app = create_app()
with app.app_context():
    from models import Rating
    from extensions import db
    from sqlalchemy import func, text

    # 统计现有情况
    total = Rating.query.count()
    print(f'当前总评分记录: {total:,}')

    # 找出所有重复的 (user_id, book_id) 对
    dupes = Rating.query.with_entities(
        Rating.user_id, Rating.book_id, func.count(Rating.id).label('cnt')
    ).group_by(Rating.user_id, Rating.book_id).having(func.count(Rating.id) > 1).all()

    print(f'有重复评分的 (user,book) 对: {len(dupes)}')

    # 对每个重复对，只保留 ID 最小的那条
    deleted_count = 0
    for user_id, book_id, cnt in dupes:
        # 找出所有重复记录，按 id 排序保留第一条
        records = Rating.query.filter_by(
            user_id=user_id, book_id=book_id
        ).order_by(Rating.id).all()

        # 删除除第一条之外的所有
        for r in records[1:]:
            db.session.delete(r)
            deleted_count += 1

        # 每 1000 条提交一次
        if deleted_count % 1000 == 0 and deleted_count > 0:
            db.session.commit()
            print(f'  已删除 {deleted_count:,} 条重复记录...')

    db.session.commit()
    print(f'\n共删除 {deleted_count:,} 条重复记录')

    # 验证
    new_total = Rating.query.count()
    print(f'剩余评分记录: {new_total:,}')

    # 再检查是否还有重复
    dupes_check = Rating.query.with_entities(
        Rating.user_id, Rating.book_id, func.count(Rating.id).label('cnt')
    ).group_by(Rating.user_id, Rating.book_id).having(func.count(Rating.id) > 1).all()

    print(f'剩余重复对: {len(dupes_check)}')

    # 统计评分范围
    stats = Rating.query.with_entities(
        func.min(Rating.rating), func.max(Rating.rating), func.avg(Rating.rating)
    ).first()
    print(f'评分范围: {stats[0]} - {stats[1]}, 平均: {float(stats[2]):.2f}')

    print('\n清理完成！')
