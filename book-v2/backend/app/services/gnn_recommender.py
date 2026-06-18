"""
GNN 图神经网络推荐模块
参考报告技术:
- LightGCN 图卷积神经网络
- 用户-书籍交互图建模
- 图嵌入表示学习
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Tuple, Optional
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import User, Book, Rating
from app.services.recommender.cf_engine import CFEngine


class GNNRecommender:
    """
    基于简化 LightGCN 的图神经网络推荐
    参考报告: LightGCN 算法设计
    """

    def __init__(self, n_factors: int = 64, n_layers: int = 3):
        self.n_factors = n_factors
        self.n_layers = n_layers
        self.user_embedding = None
        self.book_embedding = None
        self.user_map = {}  # user_id -> index
        self.book_map = {}  # book_id -> index
        self.reverse_user_map = {}
        self.reverse_book_map = {}
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None

    def load_data(self, db: Session, min_ratings: int = 5):
        """加载用户-书籍交互数据构建图"""
        # 获取活跃用户和有评分的书籍
        user_counts = db.query(
            Rating.user_id,
            func.count(Rating.id).label('count')
        ).group_by(Rating.user_id).having(func.count(Rating.id) >= min_ratings).all()

        active_users = {u.user_id: i for i, u in enumerate(user_counts)}
        self.user_map = active_users
        self.reverse_user_map = {v: k for k, v in active_users.items()}

        # 获取被评分的书籍
        rated_books = db.query(Rating.book_id).distinct().all()
        self.book_map = {b.book_id: i for i, b in enumerate(rated_books)}
        self.reverse_book_map = {v: k for k, v in self.book_map.items()}

        n_users = len(self.user_map)
        n_books = len(self.book_map)

        if n_users == 0 or n_books == 0:
            print("警告: 没有足够的交互数据构建图")
            return

        # 初始化嵌入
        self.user_embedding = nn.Embedding(n_users, self.n_factors)
        self.book_embedding = nn.Embedding(n_books, self.n_factors)

        # Xavier 初始化
        nn.init.xavier_uniform_(self.user_embedding.weight)
        nn.init.xavier_uniform_(self.book_embedding.weight)

        # 构建邻接矩阵
        self.edge_index = self._build_edge_index(db)

        print(f"✓ GNN 图构建完成: {n_users} 用户, {n_books} 书籍, {self.edge_index.shape[1]} 边")

    def _build_edge_index(self, db: Session) -> torch.Tensor:
        """构建用户-书籍交互边索引"""
        edges = []

        ratings = db.query(Rating).filter(
            Rating.user_id.in_(self.user_map.keys()),
            Rating.book_id.in_(self.book_map.keys())
        ).all()

        for r in ratings:
            user_idx = self.user_map.get(r.user_id)
            book_idx = self.book_map.get(r.book_id)
            if user_idx is not None and book_idx is not None:
                # 双向边: 用户->书籍 和 书籍->用户
                edges.append([user_idx, n_users + book_idx])
                edges.append([n_users + book_idx, user_idx])

        if not edges:
            return torch.zeros((2, 0), dtype=torch.long)

        return torch.tensor(edges, dtype=torch.long).t().contiguous()

    def train(self, db: Session, epochs: int = 50, lr: float = 0.01):
        """训练 GNN 模型"""
        if self.user_embedding is None:
            self.load_data(db)

        n_users = len(self.user_map)
        n_books = len(self.book_map)

        if n_users == 0 or n_books == 0:
            return

        # 准备正样本和负样本
        pos_edges = []
        neg_edges = []

        ratings = db.query(Rating).filter(
            Rating.user_id.in_(self.user_map.keys()),
            Rating.book_id.in_(self.book_map.keys())
        ).all()

        for r in ratings:
            user_idx = self.user_map[r.user_id]
            book_idx = self.book_map[r.book_id]
            pos_edges.append([user_idx, n_users + book_idx])

            # 负采样
            neg_book = np.random.randint(0, n_books)
            while neg_book in [self.book_map.get(r.book_id) for r in db.query(Rating).filter(Rating.user_id == r.user_id).all()]:
                neg_book = np.random.randint(0, n_books)
            neg_edges.append([user_idx, n_users + neg_book])

        pos_edges = torch.tensor(pos_edges, dtype=torch.long).t()
        neg_edges = torch.tensor(neg_edges, dtype=torch.long).t()

        # BPR 损失优化
        optimizer = torch.optim.Adam(
            list(self.user_embedding.parameters()) +
            list(self.book_embedding.parameters()),
            lr=lr
        )

        self.model = self.LightGCNLayer(n_users + n_books, self.n_factors, self.n_layers)

        for epoch in range(epochs):
            optimizer.zero_grad()

            # 获取嵌入
            embeddings = self.model(self.user_embedding.weight, self.book_embedding.weight, self.edge_index)

            # 正样本分数
            pos_scores = torch.sum(
                embeddings[pos_edges[0]] * embeddings[pos_edges[1]],
                dim=-1
            )

            # 负样本分数
            neg_scores = torch.sum(
                embeddings[neg_edges[0]] * embeddings[neg_edges[1]],
                dim=-1
            )

            # BPR 损失
            loss = -torch.mean(torch.log(torch.sigmoid(pos_scores - neg_scores) + 1e-8))

            loss.backward()
            optimizer.step()

            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")

        print("✓ GNN 模型训练完成")

    def recommend(self, db: Session, user_id: int, n: int = 10) -> List[Dict]:
        """为用户生成 GNN 推荐"""
        if user_id not in self.user_map:
            return []

        user_idx = self.user_map[user_id]
        n_users = len(self.user_map)

        # 获取用户已交互的书籍
        interacted = set(
            r.book_id for r in db.query(Rating).filter(Rating.user_id == user_id).all()
        )

        # 计算用户对所有书籍的分数
        user_emb = self.user_embedding.weight[user_idx]
        scores = torch.matmul(self.book_embedding.weight, user_emb)

        # 排序（排除已交互的）
        scores = scores.cpu().detach().numpy()
        book_indices = np.argsort(scores)[::-1]

        results = []
        for book_idx in book_indices:
            if len(results) >= n:
                break

            book_id = self.reverse_book_map.get(book_idx)
            if book_id and book_id not in interacted:
                book = db.query(Book).filter(Book.id == book_id).first()
                if book:
                        user_rating_record = db.query(Rating).filter(
                            Rating.user_id == user_id,
                            Rating.book_id == book_id
                        ).first()
                        book_avg_rating = db.query(func.avg(Rating.rating)).filter(
                            Rating.book_id == book_id
                        ).scalar()
                        results.append({
                            "book_id": book_id,
                            "id": book_id,
                            "title": book.title,
                            "author": book.author,
                            "category": book.category,
                            "image_url": book.image_url,
                            "score": float(scores[book_idx]),
                            "predicted_rating": float(scores[book_idx]),
                            "user_rating": float(user_rating_record.rating) if user_rating_record else None,
                            "avg_rating": float(book_avg_rating) if book_avg_rating else None
                        })

        return results

    class LightGCNLayer(nn.Module):
        """LightGCN 层"""
        def __init__(self, n_nodes: int, n_factors: int, n_layers: int):
            super().__init__()
            self.n_layers = n_layers
            self.weight = nn.Parameter(torch.randn(n_factors, n_factors))
            nn.init.xavier_uniform_(self.weight)

        def forward(self, user_emb, book_emb, edge_index):
            embeddings = torch.cat([user_emb, book_emb], dim=0)

            # 图卷积传播
            for _ in range(self.n_layers):
                embeddings = embeddings + torch.spmm(
                    self._normalize(edge_index, embeddings.shape[0]),
                    embeddings
                )

            return F.normalize(embeddings, p=2, dim=-1)

        def _normalize(self, edge_index, n_nodes):
            """图拉普拉斯归一化"""
            edge_weight = torch.ones(edge_index.shape[1])
            deg = torch.zeros(n_nodes)
            deg.scatter_add_(0, edge_index[0], edge_weight)
            deg_inv_sqrt = deg.pow(-0.5)
            deg_inv_sqrt[deg_inv_sqrt == float('inf')] = 0

            row, col = edge_index
            norm = deg_inv_sqrt[row] * deg_inv_sqrt[col]
            adj = torch.sparse_coo_tensor(edge_index, norm, (n_nodes, n_nodes))
            return adj


# GNN 推荐服务（带缓存）
_gnn_recommender = None


def get_gnn_recommender() -> GNNRecommender:
    """获取 GNN 推荐器单例"""
    global _gnn_recommender
    if _gnn_recommender is None:
        _gnn_recommender = GNNRecommender()
    return _gnn_recommender


def load_gnn_model(db: Session):
    """加载 GNN 模型"""
    recommender = get_gnn_recommender()
    recommender.load_data(db)
    recommender.train(db, epochs=20)  # 简化训练
    return recommender
