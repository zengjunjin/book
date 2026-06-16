"""
自动生成用户评分数据
------------------------------------
策略：
1. 先查询当前系统中的书籍社区评分
2. 根据社区评分高低，给指定用户（如 user_id=8）生成合理评分
3. 用户评分 = 社区平均评分 + 随机扰动（±2）
4. 过滤掉用户已经评分的书籍
5. 保证生成的评分分布在 1-10 之间
"""
import sys
import os
import random
from datetime import datetime, timedelta

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extensions import db
from models import Book, Rating, User
from app import create_app

app = create_app()

def generate_user_ratings(user_id, num_ratings=30, seed=42):
    """为指定用户生成评分数据"""
    random.seed(seed)

    with app.app_context():
        # 1) 确认用户存在
        user = User.query.get(user_id)
        if not user:
            print(f'❌ 用户 user_id={user_id} 不存在')
            print(f'   正在创建演示用户 user_{user_id}...')
            user = User(id=user_id, username=f'user_{user_id}', email=f'user{user_id}@demo.com')
            user.set_password('123456')
            db.session.add(user)
            db.session.commit()
            print(f'   ✅ 创建用户 user_{user_id}，密码: 123456')

        # 2) 查询用户已评分的书籍，避免重复
        existing = {r.book_id for r in Rating.query.filter_by(user_id=user_id).all()}
        print(f'ℹ️ 用户 user_id={user_id} 已有 {len(existing)} 条评分')

        # 3) 查询有足够社区评分的书籍（> 10人评分过）
        # 直接从数据库计算每本书的平均评分和评分人数
        from sqlalchemy import func
        book_stats = db.session.query(
            Rating.book_id,
            func.avg(Rating.rating).label('avg_rating'),
            func.count(Rating.rating).label('count')
        ).group_by(Rating.book_id).having(func.count(Rating.rating) >= 5).all()

        # 按评分人数排序，优先选择有人口碑的书籍
        book_stats.sort(key=lambda x: x.count, reverse=True)
        print(f'ℹ️ 有足够社区评分的书籍: {len(book_stats)} 本')

        # 4) 过滤掉用户已评分的
        candidates = [(b.book_id, float(b.avg_rating), b.count)
                      for b in book_stats if b.book_id not in existing]
        print(f'ℹ️ 可评分的候选书籍: {len(candidates)} 本')

        if len(candidates) == 0:
            print('❌ 没有可评分的候选书籍')
            return

        # 5) 从候选中选择 num_ratings 本书，按评分人数加权随机选
        # 优先选热门书但也加一些普通书，生成更真实的评分模式
        # 策略：50% 热门高分书，30% 中等评分书，20% 低分/冷门书
        high_quality = [c for c in candidates if c[1] >= 8.0]
        medium = [c for c in candidates if 6.5 <= c[1] < 8.0]
        low = [c for c in candidates if c[1] < 6.5]

        print(f'   - 高评分书籍 (>=8): {len(high_quality)} 本')
        print(f'   - 中等书籍 (6.5-8): {len(medium)} 本')
        print(f'   - 一般书籍 (<6.5): {len(low)} 本')

        # 按比例选择
        targets = []
        n_high = min(int(num_ratings * 0.5), len(high_quality))
        n_medium = min(int(num_ratings * 0.3), len(medium))
        n_low = num_ratings - n_high - n_medium
        n_low = min(n_low, len(low))

        random.shuffle(high_quality)
        random.shuffle(medium)
        random.shuffle(low)

        targets = high_quality[:n_high] + medium[:n_medium] + low[:n_low]
        random.shuffle(targets)

        print(f'\n📝 即将为用户 {user.username} (id={user_id}) 生成 {len(targets)} 条评分')

        # 6) 给每本书生成评分（社区平均评分 ± 随机扰动）
        new_ratings = []
        base_time = datetime.utcnow()

        for i, (book_id, avg_rating, count) in enumerate(targets):
            # 评分 = 社区平均 + 随机扰动
            # 高评分书籍用户给高评分，低评分书籍用户给低评分
            # 加上 ±2 的随机扰动
            noise = random.uniform(-2.0, 2.0)
            user_score = int(round(avg_rating + noise))
            user_score = max(1, min(10, user_score))

            # 时间向后推一些间隔，模拟不同时间评分
            created_at = base_time - timedelta(hours=i * 3)

            rating = Rating(
                user_id=user_id,
                book_id=book_id,
                rating=user_score,
                created_at=created_at
            )
            new_ratings.append(rating)

            # 获取书籍标题用于展示
            book = Book.query.get(book_id)
            title = book.title if book else f'Book #{book_id}'
            if len(title) > 50:
                title = title[:47] + '...'
            print(f'  [{i+1:3d}] 给《{title}》打 {user_score} 分'
                  f' (社区平均: {avg_rating:.1f}, {count} 人评分)')

        # 7) 批量插入
        try:
            db.session.bulk_save_objects(new_ratings)
            db.session.commit()
            print(f'\n✅ 成功插入 {len(new_ratings)} 条评分数据')
        except Exception as e:
            db.session.rollback()
            print(f'\n❌ 插入失败: {e}')
            return

        # 8) 统计展示
        total = Rating.query.filter_by(user_id=user_id).count()
        ratings = [r.rating for r in Rating.query.filter_by(user_id=user_id).all()]
        if ratings:
            print(f'\n📊 用户 {user.username} 评分统计')
            print(f'   总评分数: {total}')
            print(f'   平均评分: {sum(ratings)/len(ratings):.1f}')
            print(f'   最高评分: {max(ratings)}')
            print(f'   最低评分: {min(ratings)}')
            print(f'   评分分布:')
            distribution = {}
            for r in ratings:
                distribution[r] = distribution.get(r, 0) + 1
            for s in sorted(distribution.keys(), reverse=True):
                print(f'     {s} 分: {distribution[s]} 本')


if __name__ == '__main__':
    print('=' * 70)
    print('🎬 自动生成用户评分数据')
    print('=' * 70)
    print()

    # 为 user_id=8（系统中存在的用户）生成评分
    generate_user_ratings(user_id=8, num_ratings=25, seed=42)

    print('\n' + '=' * 70)
    print('完成！现在浏览器中：')
    print('  - 登录用户 user_8 / 123456')
    print('  - 书籍详情页会显示"你已评分 X 分"')
    print('  - 推荐页会根据你的评分推荐书籍')
    print('  - 个人中心页可以看到评分历史')
    print('=' * 70)
