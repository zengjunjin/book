"""
推荐系统评估服务
参考报告技术:
- 多维度评估指标体系（Precision/Recall/F1/Accuracy）
- 混淆矩阵分析
- 分类报告输出
"""
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import RecommendationLog, Rating


class EvaluationService:
    """推荐系统评估指标计算"""

    @staticmethod
    def calculate_ctr(user_id: int = None, start_date=None, end_date=None) -> dict:
        """
        计算点击率 (Click-Through Rate)
        CTR = 点击次数 / 曝光次数
        """
        db = SessionLocal()
        try:
            query = db.query(RecommendationLog)

            if user_id:
                query = query.filter(RecommendationLog.user_id == user_id)

            total_impressions = query.count()
            clicks = query.filter(RecommendationLog.clicked == True).count()

            ctr = (clicks / total_impressions * 100) if total_impressions > 0 else 0

            return {
                "ctr": round(ctr, 2),
                "total_impressions": total_impressions,
                "total_clicks": clicks,
                "formula": "CTR = (点击次数 / 曝光次数) × 100%"
            }
        finally:
            db.close()

    @staticmethod
    def calculate_precision_at_k(user_id: int, k: int = 10) -> float:
        """
        计算 Precision@K
        Precision@K = (推荐列表中用户喜欢的书籍数) / K
        参考报告: Precision@K 指标设计
        """
        db = SessionLocal()
        try:
            # 获取用户的推荐记录（前 k 个）
            recommendations = db.query(RecommendationLog).filter(
                RecommendationLog.user_id == user_id,
                RecommendationLog.position < k
            ).all()

            if not recommendations:
                return 0.0

            # 获取用户实际喜欢的书籍
            liked_books = set(
                r.book_id for r in db.query(Rating).filter(
                    Rating.user_id == user_id,
                    Rating.rating >= 7  # 7分以上视为喜欢
                ).all()
            )

            # 计算命中的推荐
            hits = sum(1 for r in recommendations if r.book_id in liked_books)

            precision = hits / len(recommendations) if recommendations else 0
            return round(precision, 4)
        finally:
            db.close()

    @staticmethod
    def calculate_recall_at_k(user_id: int, k: int = 10) -> float:
        """
        计算 Recall@K
        Recall@K = (推荐命中的书籍数) / (用户喜欢的总书籍数)
        参考报告: Recall@K 指标设计
        """
        db = SessionLocal()
        try:
            # 获取用户喜欢的所有书籍
            liked_books = set(
                r.book_id for r in db.query(Rating).filter(
                    Rating.user_id == user_id,
                    Rating.rating >= 7
                ).all()
            )

            if not liked_books:
                return 0.0

            # 获取推荐命中的书籍
            recommended_books = db.query(RecommendationLog).filter(
                RecommendationLog.user_id == user_id,
                RecommendationLog.position < k
            ).all()

            hits = sum(1 for r in recommended_books if r.book_id in liked_books)

            recall = hits / len(liked_books) if liked_books else 0
            return round(recall, 4)
        finally:
            db.close()

    @staticmethod
    def calculate_diversity_score(user_id: int) -> dict:
        """
        计算推荐多样性分数
        参考报告: 多样性约束设计
        """
        db = SessionLocal()
        try:
            recommendations = db.query(RecommendationLog).filter(
                RecommendationLog.user_id == user_id
            ).limit(20).all()

            from app.models import Book
            from collections import Counter

            book_ids = [r.book_id for r in recommendations]
            books = db.query(Book).filter(Book.id.in_(book_ids)).all()
            book_map = {b.id: b for b in books}

            categories = [book_map[bid].category for bid in book_ids if bid in book_map and book_map[bid].category]
            authors = [book_map[bid].author for bid in book_ids if bid in book_map and book_map[bid].author]

            # 类别多样性: 1 - (最大类别占比)
            category_diversity = 1 - (max(Counter(categories).values()) / len(categories)) if categories else 0

            # 作者多样性
            author_diversity = 1 - (max(Counter(authors).values()) / len(authors)) if authors else 0

            overall_diversity = (category_diversity + author_diversity) / 2

            return {
                "overall_diversity": round(overall_diversity, 3),
                "category_diversity": round(category_diversity, 3),
                "author_diversity": round(author_diversity, 3),
                "unique_categories": len(set(categories)),
                "unique_authors": len(set(authors))
            }
        finally:
            db.close()

    @staticmethod
    def generate_evaluation_report(user_id: int = None) -> dict:
        """
        生成完整的评估报告
        参考报告: classification_report 输出格式
        """
        ctr_data = EvaluationService.calculate_ctr(user_id=user_id)
        diversity = EvaluationService.calculate_diversity_score(user_id) if user_id else None

        report = {
            "evaluation_date": "2026-06-13",
            "metrics": {
                "CTR": ctr_data,
                "Diversity": diversity
            }
        }

        if user_id:
            report["per_user_metrics"] = {
                "Precision@10": EvaluationService.calculate_precision_at_k(user_id, k=10),
                "Recall@10": EvaluationService.calculate_recall_at_k(user_id, k=10),
                "Diversity": diversity
            }

        return report
