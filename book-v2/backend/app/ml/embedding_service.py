"""
书籍文本 Embedding 服务
参考报告技术:
- BERT Tokenizer 文本编码流程
- input_ids + attention_mask 输入格式
- 离线模式支持
"""
import os

# 确保优先使用镜像
os.environ['HF_ENDPOINT'] = os.environ.get('HF_ENDPOINT', 'https://hf-mirror.com')

import torch
import numpy as np
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from app.models import Book
from app.ml.config import ml_config


class BookEmbeddingService:
    """书籍文本 Embedding 生成服务"""

    def __init__(self):
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def load_model(self):
        """加载预训练模型（参考报告的模型加载逻辑）"""
        if self.model is None:
            self.model = SentenceTransformer(
                ml_config.EMBEDDING_MODEL,
                device=str(self.device)
            )
            print(f"✓ Embedding 模型加载完成，运行设备: {self.device}")

    def generate_book_text(self, book: Book) -> str:
        """将书籍信息合并为文本"""
        parts = []
        if book.title:
            parts.append(book.title)
        if book.author:
            parts.append(f"作者: {book.author}")
        if book.publisher:
            parts.append(f"出版社: {book.publisher}")
        if book.category:
            parts.append(f"类别: {book.category}")
        # 如果没有描述，使用标题作为主要文本
        if book.description:
            parts.append(f"简介: {book.description}")
        # 添加标签
        if book.tags:
            parts.append(f"标签: {', '.join(book.tags)}")
        return " | ".join(parts)

    def encode_books(self, books: List[Book]) -> np.ndarray:
        """批量编码书籍文本（参考报告的批量预处理）"""
        self.load_model()
        texts = [self.generate_book_text(book) for book in books]
        embeddings = self.model.encode(
            texts,
            batch_size=ml_config.BATCH_SIZE,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        return embeddings

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """计算两个 embedding 的余弦相似度"""
        cos_sim = np.dot(embedding1, embedding2) / (
            np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
        )
        return float(cos_sim)

    def find_similar_books(
        self,
        db: Session,
        book_id: int,
        top_k: int = 10
    ) -> List[Dict]:
        """基于语义相似度找到相似书籍"""
        self.load_model()

        # 获取目标书籍
        target_book = db.query(Book).filter(Book.id == book_id).first()
        if not target_book:
            return []

        # 编码目标书籍
        target_text = self.generate_book_text(target_book)
        target_embedding = self.model.encode([target_text])[0]

        # 获取候选书籍（排除自身）
        candidate_books = db.query(Book).filter(
            Book.id != book_id
        ).limit(500).all()

        if not candidate_books:
            return []

        # 批量编码候选书籍
        candidate_texts = [self.generate_book_text(b) for b in candidate_books]
        candidate_embeddings = self.model.encode(candidate_texts, show_progress_bar=False)

        # 计算相似度
        similarities = []
        for i, book in enumerate(candidate_books):
            sim = self.compute_similarity(target_embedding, candidate_embeddings[i])
            similarities.append((book, sim))

        # 排序并返回 top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        results = []
        for book, sim in similarities[:top_k]:
            results.append({
                "book_id": book.id,
                "title": book.title,
                "author": book.author,
                "image_url": book.image_url,
                "similarity_score": round(sim, 3),
                "reason": "基于书籍内容语义的相似推荐"
            })

        return results
