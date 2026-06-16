from surprise import SVD, Dataset, Reader
import pandas as pd
import random
from utils.data_loader import prepare_rating_matrix


class SVDRecommendation:
    def __init__(self, max_ratings=100000):
        """SVD推荐引擎 - 限制评分数量以提高训练速度"""
        self.model = None
        self.trainset = None
        self.df = None
        self.user_id_map = None
        self.book_id_map = None
        self.max_ratings = max_ratings
        # 混合推荐权重
        self.cf_weight = 0.3
        self.svd_weight = 0.4
        self.semantic_weight = 0.3
        # 深度学习模型（简化版MLP预测器）
        self.mlp_model = None
        self._load_data()

    def _load_data(self):
        print('  [SVD] 正在加载评分数据...')
        _, self.user_id_map, self.book_id_map, self.df = prepare_rating_matrix()

        if self.df.empty or len(self.df) == 0:
            print('  [SVD] 警告: 没有评分数据可用')
            self.global_mean = 7.5
            return

        # 计算全局均值
        self.global_mean = float(self.df['rating'].mean())

        # 限制评分数量 - 只保留评分最活跃的用户和书籍
        df_train = self.df.copy()

        if len(df_train) > self.max_ratings:
            # 按评分最多的用户优先保留
            user_counts = df_train['user_id'].value_counts()
            top_users = set(user_counts[user_counts >= 3].index)
            df_train = df_train[df_train['user_id'].isin(top_users)]

            if len(df_train) > self.max_ratings:
                df_train = df_train.sample(n=self.max_ratings, random_state=42)

        print(f'  [SVD] 训练数据规模: {len(df_train):,} 条评分')

        # 转换为Surprise格式
        reader = Reader(rating_scale=(1, 10))
        data = Dataset.load_from_df(df_train[['user_id', 'book_id', 'rating']], reader)

        # 构建训练集
        self.trainset = data.build_full_trainset()

        # 训练SVD模型
        print('  [SVD] 正在训练 SVD 模型...')
        self.model = SVD(n_factors=30, n_epochs=20, lr_all=0.005,
                         reg_all=0.05, random_state=42)
        self.model.fit(self.trainset)
        print('  [SVD] 引擎准备就绪')

    def recommend(self, user_id, n_recommendations=10, seed=None):
        """为指定用户生成推荐

        Args:
            user_id: 用户ID
            n_recommendations: 推荐数量
            seed: 随机数种子，None 表示不固定（每次刷新结果不同）
        """
        if self.model is None or user_id not in self.user_id_map:
            return []

        # 获取用户已评分的书籍
        user_ratings = self.df[self.df['user_id'] == user_id]
        rated_books = set(user_ratings['book_id'].tolist())

        # 获取所有书籍
        all_books = set(self.df['book_id'].unique())
        unrated_books = list(all_books - rated_books)

        if not unrated_books:
            return []

        # 设置随机数种子（seed=None 时随机，确保每次刷新结果不同）
        if seed is not None:
            random.seed(seed)

        # 扩大候选书池到 5000 本，增加刷新时的多样性
        sample_size = min(len(unrated_books), 5000)
        unrated_books_sample = random.sample(unrated_books, sample_size)

        # 预测未评分书籍的评分
        predictions = []
        for book_id in unrated_books_sample:
            pred = self.model.predict(user_id, book_id)
            # 加较大的随机扰动 (±1.5)，让排序有显著变化
            jitter = random.uniform(-1.5, 1.5)
            predicted = float(pred.est) + jitter
            predicted = max(1.0, min(10.0, predicted))
            predictions.append({
                'book_id': book_id,
                'predicted_rating': round(predicted, 3)
            })

        # 按预测评分排序
        predictions.sort(key=lambda x: x['predicted_rating'], reverse=True)
        # 关键策略：先取 top-n*3，然后随机 shuffle 后取 n 本
        expanded_pool = predictions[:n_recommendations * 3]
        random.shuffle(expanded_pool)
        return expanded_pool[:n_recommendations]

    def evaluate(self, test_size=0.1):
        """评估模型性能 - 返回 RMSE 和 MAE"""
        if self.model is None or self.df.empty:
            return {'rmse': 0.0, 'mae': 0.0}

        # 用一部分评分数据抽样测试
        test_df = self.df.sample(frac=test_size, random_state=42)

        predictions = []
        actuals = []
        for _, row in test_df.iterrows():
            pred = self.model.predict(row['user_id'], row['book_id'])
            predictions.append(pred.est)
            actuals.append(row['rating'])

        if not predictions:
            return {'rmse': 0.0, 'mae': 0.0}

        import numpy as np
        predictions_arr = np.array(predictions)
        actuals_arr = np.array(actuals)

        rmse = float(np.sqrt(np.mean((predictions_arr - actuals_arr) ** 2)))
        mae = float(np.mean(np.abs(predictions_arr - actuals_arr)))

        return {
            'rmse': round(rmse, 3),
            'mae': round(mae, 3)
        }

    def set_weights(self, cf_weight=None, svd_weight=None, semantic_weight=None):
        """设置混合推荐权重"""
        if cf_weight is not None:
            self.cf_weight = max(0.0, min(1.0, cf_weight))
        if svd_weight is not None:
            self.svd_weight = max(0.0, min(1.0, svd_weight))
        if semantic_weight is not None:
            self.semantic_weight = max(0.0, min(1.0, semantic_weight))

        # 归一化权重
        total = self.cf_weight + self.svd_weight + self.semantic_weight
        if total > 0:
            self.cf_weight /= total
            self.svd_weight /= total
            self.semantic_weight /= total

    def get_user_liked_books(self, user_id, min_rating=7):
        """获取用户喜欢的书籍"""
        if self.df is None or user_id not in self.user_id_map:
            return []

        user_ratings = self.df[self.df['user_id'] == user_id]
        liked = user_ratings[user_ratings['rating'] >= min_rating]
        return liked['book_id'].tolist()

    def hybrid_recommend(self, user_id, n_recommendations=10, seed=None,
                        cf_engine=None, embedding_service=None):
        """
        混合推荐策略 - 结合协同过滤 + SVD + 语义召回

        Args:
            user_id: 用户ID
            n_recommendations: 推荐数量
            seed: 随机数种子
            cf_engine: 协同过滤引擎（可选）
            embedding_service: 语义embedding服务（可选）

        Returns:
            混合推荐列表
        """
        import random as _random
        if seed is not None:
            _random.seed(seed)

        # 获取各类推荐
        svd_recs = self.recommend(user_id, n_recommendations * 3, seed)
        svd_scores = {r['book_id']: r['predicted_rating'] for r in svd_recs}

        # 协同过滤推荐
        cf_scores = {}
        if cf_engine is not None:
            cf_recs = cf_engine.user_based_recommend(user_id, n_recommendations * 3, k=30, seed=seed)
            cf_scores = {r['book_id']: r['predicted_rating'] for r in cf_recs}

        # 语义召回
        semantic_scores = {}
        if embedding_service is not None:
            user_liked = self.get_user_liked_books(user_id)
            if user_liked:
                from models import Book
                candidate_ids = set(svd_scores.keys()) | set(cf_scores.keys())
                if candidate_ids:
                    candidates = Book.query.filter(Book.id.in_(candidate_ids)).all()
                    liked_books = Book.query.filter(Book.id.in_(user_liked)).all()
                    if candidates and liked_books:
                        semantic_results = embedding_service.content_based_recall(
                            liked_books, candidates, top_k=len(candidates)
                        )
                        for item in semantic_results:
                            # 归一化到0-10范围
                            semantic_scores[item['book'].id] = item['score'] * 9.0 + 1.0

        # 合并所有候选书籍
        all_candidates = set(svd_scores.keys()) | set(cf_scores.keys()) | set(semantic_scores.keys())

        # 计算混合分数
        results = []
        for book_id in all_candidates:
            # 归一化分数到0-1
            svd_norm = (svd_scores.get(book_id, 5.0) - 1.0) / 9.0
            cf_norm = (cf_scores.get(book_id, 5.0) - 1.0) / 9.0
            sem_norm = (semantic_scores.get(book_id, 5.0) - 1.0) / 9.0

            # 加权混合
            hybrid_score = self.cf_weight * cf_norm + \
                          self.svd_weight * svd_norm + \
                          self.semantic_weight * sem_norm

            results.append({
                'book_id': book_id,
                'svd_score': svd_scores.get(book_id, 5.0),
                'cf_score': cf_scores.get(book_id, 5.0),
                'semantic_score': round(semantic_scores.get(book_id, 0.0), 3),
                'hybrid_score': round(hybrid_score, 3),
                'predicted_rating': round(hybrid_score * 9.0 + 1.0, 3)
            })

        # 按混合分数排序
        results.sort(key=lambda x: x['hybrid_score'], reverse=True)

        # 随机扰动增加多样性
        top_pool = results[:n_recommendations * 2]
        _random.shuffle(top_pool)
        return top_pool[:n_recommendations]

    def mlp_predict(self, user_id, book_id):
        """
        简化版 MLP 预测（基于用户和书籍特征的简单神经网络）
        这里使用基于统计的模拟预测作为后备实现
        """
        if self.df is None:
            return None

        user_ratings = self.df[self.df['user_id'] == user_id]
        book_ratings = self.df[self.df['book_id'] == book_id]

        if len(user_ratings) == 0 and len(book_ratings) == 0:
            return self.global_mean if hasattr(self, 'global_mean') else 7.5

        user_mean = user_ratings['rating'].mean() if len(user_ratings) > 0 else 7.0
        book_mean = book_ratings['rating'].mean() if len(book_ratings) > 0 else 7.0

        # 简化预测：用户和书籍的平均
        pred = (user_mean + book_mean) / 2
        return max(1.0, min(10.0, pred))
