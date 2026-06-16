"""
📊 阅读报告生成器

为用户生成个性化的阅读数据报告
"""

import random
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .llm_engine import get_llm_engine


@dataclass
class ReadingStats:
    """阅读统计数据"""
    user_id: int
    total_books: int
    total_ratings: int
    avg_rating: float
    highest_rating: float
    lowest_rating: float
    category_distribution: Dict[str, int]
    top_books: List[Dict]
    reading_trend: List[Dict]

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "total_books": self.total_books,
            "total_ratings": self.total_ratings,
            "avg_rating": round(self.avg_rating, 1),
            "highest_rating": round(self.highest_rating, 1),
            "lowest_rating": round(self.lowest_rating, 1),
            "category_distribution": self.category_distribution,
            "top_books": self.top_books,
            "reading_trend": self.reading_trend,
        }


@dataclass
class ReadingReport:
    """完整阅读报告"""
    user_id: int
    stats: ReadingStats
    summary: str
    insights: List[str]
    recommendations: List[Dict]
    personality_type: str
    model: str

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "stats": self.stats.to_dict(),
            "summary": self.summary,
            "insights": self.insights,
            "recommendations": self.recommendations,
            "personality_type": self.personality_type,
            "model": self.model,
        }


class ReportGenerator:
    """
    阅读报告生成器
    
    功能:
    - 从数据库收集用户阅读数据
    - 分析用户阅读偏好和人格类型
    - 生成有温度的个性化报告
    """

    # 阅读者人格类型（基于阅读偏好）
    PERSONALITY_TYPES = [
        {
            "type": "深邃思考者",
            "emoji": "🧠",
            "description": "偏爱哲学、文学和深度内容，追求思想深度",
            "indicators": ["文学", "哲学", "经典", "历史"]
        },
        {
            "type": "想象探索家",
            "emoji": "🚀",
            "description": "热爱科幻、奇幻，享受天马行空的想象",
            "indicators": ["科幻", "奇幻", "冒险"]
        },
        {
            "type": "知识探索者",
            "emoji": "📚",
            "description": "偏爱科普、历史、社科，追求知识广度",
            "indicators": ["科普", "历史", "科技"]
        },
        {
            "type": "情感共鸣者",
            "emoji": "💖",
            "description": "喜欢文学小说、成长故事，注重情感体验",
            "indicators": ["文学", "成长", "情感", "人生"]
        },
        {
            "type": "实用主义者",
            "emoji": "⚡",
            "description": "偏好实用、工具类书籍，追求可操作的建议",
            "indicators": ["商业", "方法", "实用"]
        },
    ]

    def __init__(self, db=None):
        self.db = db
        self.engine = get_llm_engine()

    # ========== 数据收集 ==========

    def get_user_stats(self, user_id: int) -> ReadingStats:
        """获取用户阅读统计数据"""
        stats = ReadingStats(
            user_id=user_id,
            total_books=0,
            total_ratings=0,
            avg_rating=7.5,
            highest_rating=10.0,
            lowest_rating=5.0,
            category_distribution={},
            top_books=[],
            reading_trend=[],
        )

        try:
            from extensions import db
            conn = db.engine.connect()

            # 获取用户评分统计
            result = conn.execute(
                db.text("""
                    SELECT COUNT(*), AVG(rating), MAX(rating), MIN(rating)
                    FROM user_ratings WHERE user_id = :user_id
                """),
                {"user_id": user_id}
            )
            row = result.fetchone()

            if row and row[0] > 0:
                stats.total_ratings = int(row[0])
                stats.avg_rating = float(row[1]) if row[1] else 7.5
                stats.highest_rating = float(row[2]) if row[2] else 10.0
                stats.lowest_rating = float(row[3]) if row[3] else 5.0

                # 获取最高评分的书籍
                result = conn.execute(
                    db.text("""
                        SELECT b.id, b.title, b.author, ur.rating
                        FROM user_ratings ur
                        JOIN books b ON ur.book_id = b.id
                        WHERE ur.user_id = :user_id
                        ORDER BY ur.rating DESC
                        LIMIT 5
                    """),
                    {"user_id": user_id}
                )
                top_rows = result.fetchall()
                stats.top_books = [
                    {"book_id": r[0], "title": r[1], "author": r[2] or "未知", "rating": float(r[3])}
                    for r in top_rows
                ]
                stats.total_books = len(stats.top_books)

            conn.close()

        except Exception as e:
            print(f"[Report] 数据库查询失败: {e}")
            # 用模拟数据兜底
            stats = self._get_mock_stats(user_id)

        # 模拟分类分布（实际应从书籍标签推断）
        categories = ["文学小说", "科幻奇幻", "历史社科", "哲学思想", "科普知识"]
        for i, cat in enumerate(categories):
            stats.category_distribution[cat] = max(1, stats.total_books - i * 2)

        # 模拟阅读趋势（按月）
        months = ["6月", "7月", "8月", "9月", "10月", "11月"]
        for month in months:
            stats.reading_trend.append({
                "month": month,
                "books": random.randint(1, max(3, stats.total_books // 3)),
            })

        return stats

    def _get_mock_stats(self, user_id: int) -> ReadingStats:
        """模拟统计数据（无数据库时）"""
        return ReadingStats(
            user_id=user_id,
            total_books=random.randint(8, 25),
            total_ratings=random.randint(10, 30),
            avg_rating=round(random.uniform(7.0, 9.0), 1),
            highest_rating=round(random.uniform(9.0, 10.0), 1),
            lowest_rating=round(random.uniform(4.0, 7.0), 1),
            category_distribution={
                "文学小说": 5,
                "科幻奇幻": 3,
                "历史社科": 2,
                "哲学思想": 1,
            },
            top_books=[
                {"book_id": i, "title": f"用户喜爱的书{i}",
                 "author": f"作者{i}", "rating": round(random.uniform(8.5, 10.0), 1)}
                for i in range(1, 4)
            ],
            reading_trend=[
                {"month": f"{m}月", "books": random.randint(1, 5)}
                for m in range(6, 12)
            ],
        )

    # ========== 人格分析 ==========

    def analyze_personality(self, stats: ReadingStats) -> Dict:
        """基于阅读数据分析用户的阅读人格"""
        # 根据分类分布推测人格
        total = sum(stats.category_distribution.values()) or 1
        dominant_category = max(
            stats.category_distribution.keys(),
            key=lambda k: stats.category_distribution[k]
        )

        # 匹配人格类型
        best_match = self.PERSONALITY_TYPES[0]
        best_score = 0

        for pt in self.PERSONALITY_TYPES:
            score = 0
            for indicator in pt["indicators"]:
                if any(indicator in cat for cat in stats.category_distribution.keys()):
                    score += stats.category_distribution.get(
                        [c for c in stats.category_distribution if indicator in c][:1][0],
                        0
                    ) if [c for c in stats.category_distribution if indicator in c] else 0

                # 标题关键词匹配
                for book in stats.top_books:
                    if indicator in book["title"]:
                        score += 1

            if score > best_score:
                best_score = score
                best_match = pt

        # 根据评分分布添加特征
        features = []
        if stats.avg_rating > 8.0:
            features.append("你的评分偏高，说明你是一个容易被打动的浪漫读者")
        elif stats.avg_rating < 7.0:
            features.append("你的评分偏低，说明你是一个品味严格的挑剔读者")

        if stats.highest_rating - stats.lowest_rating > 5.0:
            features.append("你的评分跨度大，说明你有鲜明的喜好")

        if not features:
            features.append("你的阅读品味均衡，享受各种类型的书籍")

        return {
            "type": best_match["type"],
            "emoji": best_match["emoji"],
            "description": best_match["description"],
            "features": features,
            "dominant_category": dominant_category,
        }

    # ========== 报告生成 ==========

    def generate_report(self, user_id: int, use_llm: bool = True) -> ReadingReport:
        """生成完整的阅读报告"""
        stats = self.get_user_stats(user_id)
        personality = self.analyze_personality(stats)

        # 生成洞察
        insights = self._generate_insights(stats, personality)

        # 生成推荐
        recommendations = self._generate_recommendations(stats, personality)

        # 生成摘要
        summary = self._generate_summary(stats, personality, insights, use_llm)

        return ReadingReport(
            user_id=user_id,
            stats=stats,
            summary=summary,
            insights=insights,
            recommendations=recommendations,
            personality_type=f"{personality['emoji']} {personality['type']}",
            model=self.engine.current_model,
        )

    def _generate_insights(self, stats: ReadingStats, personality: Dict) -> List[str]:
        """生成数据洞察"""
        insights = []

        # 洞察1：阅读偏好
        dominant = max(
            stats.category_distribution.keys(),
            key=lambda k: stats.category_distribution[k]
        )
        insights.append(
            f"📖 你最喜欢的类型是「{dominant}」，"
            f"占据了你阅读的 {stats.category_distribution[dominant] / max(1, sum(stats.category_distribution.values())) * 100:.0f}%"
        )

        # 洞察2：评分倾向
        if stats.avg_rating > 8.0:
            insights.append("⭐ 你对书籍的评价普遍较高，是一位善于发现美好的读者")
        elif stats.avg_rating < 7.0:
            insights.append("🔍 你对书籍要求严格，是一位品味独特的读者")
        else:
            insights.append("⚖ 你的评分均衡理性，善于客观评价书籍")

        # 洞察3：阅读节奏
        total_months = len(stats.reading_trend) or 1
        avg_per_month = stats.total_books / total_months
        if avg_per_month > 2:
            insights.append(f"🚀 你平均每月阅读 {avg_per_month:.1f} 本书，是一位勤奋的读者！")
        elif avg_per_month < 1:
            insights.append(f"🌱 你每月阅读 {avg_per_month:.1f} 本书，享受慢节奏的阅读")
        else:
            insights.append(f"📚 你每月阅读 {avg_per_month:.1f} 本书，节奏刚刚好")

        # 洞察4：最高分书籍
        if stats.top_books:
            top = stats.top_books[0]
            insights.append(f"🏆 你最爱的书是《{top['title']}》，给了 {top['rating']}/10 的高分")

        # 人格洞察
        insights.append(f"{personality['emoji']} 你的阅读人格：{personality['type']}")

        return insights

    def _generate_recommendations(self, stats: ReadingStats, personality: Dict) -> List[Dict]:
        """生成推荐"""
        dominant_category = max(
            stats.category_distribution.keys(),
            key=lambda k: stats.category_distribution[k]
        )

        rec_books = [
            {
                "title": f"{dominant_category}领域的经典之作",
                "author": "经典作家",
                "reason": f"基于你对{dominant_category}的热爱，这本能满足你的阅读品味",
                "match_score": 92,
            },
            {
                "title": "拓展你阅读边界的书",
                "author": "新锐作家",
                "reason": "尝试一些不同风格的书籍，也许会发现新的喜爱",
                "match_score": 85,
            },
            {
                "title": f"{personality['type']}推荐书单之一",
                "author": "人气作者",
                "reason": f"符合你作为{personality['type']}的阅读偏好",
                "match_score": 88,
            },
        ]

        return rec_books

    def _generate_summary(self, stats: ReadingStats, personality: Dict,
                         insights: List[str], use_llm: bool) -> str:
        """生成报告摘要"""

        if use_llm and self.engine.ollama_available:
            try:
                prompt = f"""请为以下阅读数据写一份个性化、有温度的报告摘要：

用户阅读数据：
- 已读书籍数：{stats.total_books}
- 平均评分：{stats.avg_rating}/10
- 最高评分：{stats.highest_rating}/10
- 最爱书籍：{stats.top_books[0]['title'] if stats.top_books else '未知'}
- 阅读偏好：{personality['type']}
- 主要阅读类型：{max(stats.category_distribution.keys(), key=lambda k: stats.category_distribution[k])}

**要求：**
- 用温暖、鼓励的语气
- 结合数据给用户反馈
- 让用户感觉"被理解"
- 300-400字
- 使用 emojis
"""
                response = self.engine.generate(prompt)
                return response.content
            except:
                pass

        # 模板模式兜底
        return f"""📊 **你的阅读报告**

你在这段时间共读了 **{stats.total_books}** 本书，给 **{stats.total_ratings}** 次评分，平均评分 **{stats.avg_rating}/10**。

{personality['emoji']} **你是一位{personality['type']}**

{personality['description']}。

🌟 **你的阅读偏好分析**

你最偏爱的类型是「{max(stats.category_distribution.keys(), key=lambda k: stats.category_distribution[k])}」，
这说明你在阅读中追求某种特定的满足感。

📖 **高光时刻**

{'- 你最爱的书是《' + (stats.top_books[0]['title'] if stats.top_books else '某本书') + '》，给了很高的评价' if stats.top_books else ''}

📈 **继续保持**

阅读是一段与自己对话的旅程，感谢你记录下这段旅程中的每一个脚步。
继续阅读，继续发现，继续成长吧！
"""


# ========== 单例 ==========

_report_instance: Optional[ReportGenerator] = None


def get_report_generator() -> ReportGenerator:
    global _report_instance
    if _report_instance is None:
        _report_instance = ReportGenerator()
    return _report_instance
