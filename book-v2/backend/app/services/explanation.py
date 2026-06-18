"""
推荐系统可解释性模块
参考报告技术:
- 推荐理由生成（基于规则 + LLM）
- 协同过滤的解释：相似用户喜欢
- 基于内容的解释：书籍特征匹配
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models import Book, Rating, User
from app.ml.embedding_service import BookEmbeddingService


class ExplanationService:
    """推荐系统可解释性服务"""

    def __init__(self):
        self.embedding_service = BookEmbeddingService()

    def generate_explanation(
        self,
        db: Session,
        user_id: int,
        book_id: int,
        source: str = "cf"
    ) -> Dict:
        """
        为推荐结果生成解释
        参考报告: 推荐系统可解释性设计
        """
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            return {"explanation": "书籍信息不存在", "confidence": 0}

        explanations = []

        # 1. 基于内容的解释
        content_explanation = self._explain_by_content(book)
        if content_explanation:
            explanations.append(content_explanation)

        # 2. 基于协同过滤的解释
        if source == "cf":
            cf_explanation = self._explain_by_collaborative(db, user_id, book)
            if cf_explanation:
                explanations.append(cf_explanation)

        # 3. 基于评分的解释
        rating_explanation = self._explain_by_ratings(book)
        if rating_explanation:
            explanations.append(rating_explanation)

        # 组合解释
        combined = "；".join(explanations) if explanations else f"这是一本值得阅读的书籍：{book.title}"
        confidence = self._calculate_confidence(book)

        return {
            "explanation": combined,
            "confidence": confidence,
            "reasons": explanations,
            "source": source
        }

    def _explain_by_content(self, book: Book) -> str:
        """基于内容特征生成解释"""
        parts = []

        if book.author:
            parts.append(f"作者是 {book.author}")

        if book.category:
            parts.append(f"属于 {book.category} 类型")

        if book.year and book.year > 0:
            parts.append(f"出版于 {book.year} 年")

        return "这本书" + "，".join(parts) + "。" if parts else ""

    def _explain_by_collaborative(
        self,
        db: Session,
        user_id: int,
        book: Book
    ) -> str:
        """基于协同过滤生成解释"""
        # 获取相似用户喜欢的书籍
        user_ratings = db.query(Rating).filter(
            Rating.user_id == user_id,
            Rating.rating >= 7
        ).limit(10).all()

        if not user_ratings:
            return ""

        # 检查是否有相似类别/作者的书籍
        liked_book_ids = [r.book_id for r in user_ratings]
        similar_books = db.query(Book).filter(
            Book.id.in_(liked_book_ids),
            Book.category == book.category
        ).limit(1).first()

        if similar_books:
            return f"与您喜欢的《{similar_books.title}》类型相同"

        # 检查是否有相同作者的书籍
        if book.author:
            same_author = db.query(Book).filter(
                Book.id.in_(liked_book_ids),
                Book.author == book.author
            ).limit(1).first()

            if same_author:
                return f"与您喜欢的《{same_author.title}》是同一作者"

        return ""

    def _explain_by_ratings(self, book: Book) -> str:
        """基于评分数据生成解释"""
        parts = []

        if book.rating_count > 100:
            parts.append(f"已有 {book.rating_count} 人评分")

        if book.avg_rating and book.avg_rating >= 8:
            parts.append(f"平均评分 {book.avg_rating:.1f}，口碑很好")
        elif book.avg_rating and book.avg_rating >= 6:
            parts.append(f"平均评分 {book.avg_rating:.1f}，评价不错")

        return "，".join(parts) if parts else ""

    def _calculate_confidence(self, book: Book) -> float:
        """计算推荐置信度"""
        score = 0.0

        # 评分数量权重
        if book.rating_count > 1000:
            score += 0.3
        elif book.rating_count > 100:
            score += 0.2
        elif book.rating_count > 10:
            score += 0.1

        # 平均评分权重
        if book.avg_rating:
            score += (book.avg_rating / 10) * 0.4

        # 内容完整性权重
        if book.description:
            score += 0.15
        if book.author:
            score += 0.15

        return min(1.0, score)

    def batch_generate_explanations(
        self,
        db: Session,
        user_id: int,
        recommendations: List[Dict],
        source: str = "cf"
    ) -> List[Dict]:
        """批量为推荐列表生成解释"""
        results = []
        for rec in recommendations:
            explanation = self.generate_explanation(
                db, user_id, rec.get("book_id"), source
            )
            rec["explanation"] = explanation
            results.append(rec)
        return results
