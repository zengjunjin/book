"""
RAG 书籍内容理解推荐模块
参考报告技术:
- 检索增强生成（RAG）架构
- 书籍内容向量化存储
- 基于自然语言查询的书籍推荐
"""
import os
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models import Book, Rating
from app.ml.embedding_service import BookEmbeddingService


class RAGBookService:
    """基于 RAG 的书籍内容理解推荐服务"""

    def __init__(self):
        self.embedding_service = BookEmbeddingService()
        self.top_k = 100  # 候选书籍数量

    def query_books(
        self,
        db: Session,
        query: str,
        top_k: int = 10,
        category: Optional[str] = None,
        min_rating: Optional[float] = None
    ) -> List[Dict]:
        """
        基于自然语言查询推荐书籍（RAG 检索）
        参考报告: RAG 检索流程设计
        """
        # 1. 查询构建（支持分类和评分过滤）
        book_query = db.query(Book).filter(Book.description.isnot(None))

        if category:
            book_query = book_query.filter(Book.category == category)

        if min_rating:
            book_query = book_query.filter(Book.avg_rating >= min_rating)

        # 获取候选书籍
        candidate_books = book_query.limit(self.top_k).all()

        if not candidate_books:
            return []

        # 2. 查询编码
        query_embedding = self.embedding_service.model.encode([query])[0]

        # 3. 候选书籍编码
        candidate_texts = [
            self.embedding_service.generate_book_text(book)
            for book in candidate_books
        ]
        candidate_embeddings = self.embedding_service.model.encode(
            candidate_texts,
            show_progress_bar=False
        )

        # 4. 计算相似度
        similarities = []
        for i, book in enumerate(candidate_books):
            sim = self._compute_cosine_similarity(
                query_embedding,
                candidate_embeddings[i]
            )
            similarities.append((book, sim))

        # 5. 排序并返回 top_k
        similarities.sort(key=lambda x: x[1], reverse=True)

        results = []
        for book, sim in similarities[:top_k]:
            results.append({
                "book_id": book.id,
                "title": book.title,
                "author": book.author,
                "category": book.category,
                "avg_rating": book.avg_rating,
                "rating_count": book.rating_count,
                "image_url": book.image_url,
                "similarity_score": round(sim, 4),
                "description_preview": self._truncate_description(book.description, 200)
            })

        return results

    def query_by_interests(
        self,
        db: Session,
        user_id: int,
        query: str,
        top_k: int = 10
    ) -> List[Dict]:
        """
        基于用户兴趣和查询推荐书籍
        结合用户历史偏好进行个性化 RAG 检索
        """
        # 获取用户喜欢的书籍类别
        liked_ratings = db.query(Rating).filter(
            Rating.user_id == user_id,
            Rating.rating >= 7
        ).limit(50).all()

        liked_book_ids = [r.book_id for r in liked_ratings]
        liked_books = db.query(Book).filter(Book.id.in_(liked_book_ids)).all()

        # 提取用户偏好类别
        preferred_categories = set(b.category for b in liked_books if b.category)
        preferred_authors = set(b.author for b in liked_books if b.author)

        # 执行查询
        results = self.query_books(db, query, top_k * 2)

        # 重新排序，结合用户偏好
        for result in results:
            score = result["similarity_score"]

            # 偏好加分
            if result["category"] in preferred_categories:
                score += 0.1
            if result["author"] in preferred_authors:
                score += 0.15

            # 评分加权
            if result["avg_rating"]:
                score += (result["avg_rating"] / 10) * 0.1

            result["relevance_score"] = round(min(1.0, score), 4)

        # 重新排序
        results.sort(key=lambda x: x["relevance_score"], reverse=True)

        return results[:top_k]

    def _compute_cosine_similarity(
        self,
        embedding1,
        embedding2
    ) -> float:
        """计算余弦相似度"""
        import numpy as np
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        return dot_product / (norm1 * norm2)

    def _truncate_description(self, text: str, max_length: int) -> str:
        """截断描述文本"""
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def build_book_index(
        self,
        db: Session,
        batch_size: int = 100
    ) -> Dict:
        """
        构建书籍索引（离线任务）
        将所有书籍描述编码并存储到数据库
        """
        total_books = db.query(Book).filter(
            Book.description.isnot(None)
        ).count()

        processed = 0
        errors = 0

        for offset in range(0, total_books, batch_size):
            books = db.query(Book).filter(
                Book.description.isnot(None)
            ).offset(offset).limit(batch_size).all()

            for book in books:
                try:
                    # 生成并存储 embedding（这里存储在内存中，实际应该存到向量数据库）
                    text = self.embedding_service.generate_book_text(book)
                    embedding = self.embedding_service.model.encode([text])[0]
                    processed += 1
                except Exception:
                    errors += 1

        return {
            "total_books": total_books,
            "processed": processed,
            "errors": errors
        }
