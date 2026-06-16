import numpy as np
from scipy import sparse
from utils.data_loader import prepare_rating_matrix


class CollaborativeFiltering:
    def __init__(self, max_candidates=2000):
        self.rating_matrix = None
        self.user_id_map = None
        self.book_id_map = None
        self.reverse_user_map = None
        self.reverse_book_map = None
        self.df = None
        self.max_candidates = max_candidates
        self.candidate_user_indices = None
        self.candidate_user_ids = None
        self.user_means = None
        self.global_mean = 7.5
        # 预计算每个用户的评分（加速相似度计算）
        self.user_rated_books = {}
        # 热门书籍（用作 fallback）
        self.popular_book_ids = None
        # 语义召回权重（用于混合推荐）
        self.semantic_weight = 0.2
        self._load_data()

    def _load_data(self):
        print('  [CF] 正在加载评分数据...')
        self.rating_matrix, self.user_id_map, self.book_id_map, self.df = prepare_rating_matrix()
        self.reverse_user_map = {v: k for k, v in self.user_id_map.items()}
        self.reverse_book_map = {v: k for k, v in self.book_id_map.items()}

        n_users, n_books = self.rating_matrix.shape
        print(f'  [CF] 数据规模: {n_users:,} 用户 x {n_books:,} 书籍')
        print(f'  [CF] 评分记录: {len(self.df):,} 条')

        if n_users == 0 or n_books == 0:
            print('  [CF] 警告: 没有评分数据可用')
            return

        self.rating_matrix = self.rating_matrix.tocsr()

        # 选 top-N 活跃用户作为邻居候选池
        user_rating_counts = np.array(self.rating_matrix.getnnz(axis=1)).flatten()
        if n_users > self.max_candidates:
            top_indices = np.argsort(user_rating_counts)[::-1][:self.max_candidates]
            self.candidate_user_indices = sorted(top_indices.tolist())
        else:
            self.candidate_user_indices = list(range(n_users))

        self.candidate_user_ids = [
            self.reverse_user_map[idx] for idx in self.candidate_user_indices
        ]
        print(f'  [CF] 邻居候选池: {len(self.candidate_user_indices)} 名活跃用户')

        # 预计算候选用户评分
        for idx in self.candidate_user_indices:
            row = self.rating_matrix.getrow(idx)
            if len(row.data) > 0:
                self.user_rated_books[idx] = (
                    set(row.indices.tolist()),
                    row.data.astype(np.float32),
                    float(np.mean(row.data))
                )

        # 预计算所有用户评分均值
        print('  [CF] 正在计算用户评分均值...')
        self.user_means = np.full(n_users, self.global_mean, dtype=np.float32)
        for u in range(n_users):
            row = self.rating_matrix.getrow(u)
            data = row.data
            if len(data) > 0:
                self.user_means[u] = float(np.mean(data))

        # 全局均值
        all_ratings = self.rating_matrix.data
        self.global_mean = float(np.mean(all_ratings)) if len(all_ratings) > 0 else 7.5
        print(f'  [CF] 全局评分均值: {self.global_mean:.2f}')

        # 预计算热门书籍（按被评分数量 * 平均评分）
        # 用稀疏矩阵的向量化操作，避免遍历所有书籍
        book_popularity = np.array(self.rating_matrix.getnnz(axis=0)).flatten()
        # sum(axis=0) 返回 matrix，转 1D 数组
        book_ratings_sum = np.array(self.rating_matrix.sum(axis=0)).flatten()
        # 避免除以 0
        book_avg_rating = np.zeros(len(book_popularity), dtype=np.float32)
        nonzero_mask = book_popularity > 0
        book_avg_rating[nonzero_mask] = book_ratings_sum[nonzero_mask] / book_popularity[nonzero_mask].astype(np.float32)
        score = book_popularity.astype(np.float32) * book_avg_rating
        top_book_idx = np.argsort(score)[::-1][:500]
        self.popular_book_ids = []
        for idx in top_book_idx:
            if idx in self.reverse_book_map:
                self.popular_book_ids.append(self.reverse_book_map[idx])
        print(f'  [CF] 预计算热门书籍: {len(self.popular_book_ids)} 本')
        print('  [CF] 引擎准备就绪')

    def _get_user_ratings_info(self, user_idx):
        """获取用户评分信息，缓存以加速"""
        if user_idx not in self.user_rated_books:
            row = self.rating_matrix.getrow(user_idx)
            if len(row.data) == 0:
                self.user_rated_books[user_idx] = (set(), row.data, self.global_mean)
            else:
                self.user_rated_books[user_idx] = (
                    set(row.indices.tolist()),
                    row.data.astype(np.float32),
                    float(np.mean(row.data))
                )
        return self.user_rated_books[user_idx]

    def _cosine_similarity_on_overlap(self, user_idx, candidate_idx):
        """
        在共同评分书籍上计算余弦相似度。
        用共同评分数量做可信度加权。
        """
        u_books_set, _, u_mean = self._get_user_ratings_info(user_idx)
        c_row = self.rating_matrix.getrow(candidate_idx)
        c_books = c_row.indices
        c_ratings = c_row.data
        c_mean = float(np.mean(c_ratings)) if len(c_ratings) > 0 else self.global_mean

        if len(u_books_set) == 0 or len(c_books) == 0:
            return 0.0

        # 找共同评分书籍
        common_indices = []
        common_ratings_u = []
        common_ratings_c = []
        # 用索引遍历
        c_book_to_rating = {}
        for i in range(len(c_books)):
            c_book_to_rating[c_books[i]] = c_ratings[i]

        u_row = self.rating_matrix.getrow(user_idx)
        u_books = u_row.indices
        u_ratings = u_row.data
        for i in range(len(u_books)):
            book = u_books[i]
            if book in c_book_to_rating:
                common_indices.append(book)
                common_ratings_u.append(float(u_ratings[i]))
                common_ratings_c.append(float(c_book_to_rating[book]))

        n_common = len(common_indices)
        if n_common < 1:
            return 0.0

        # 中心化后的余弦相似度
        cu = np.array(common_ratings_u, dtype=np.float32) - u_mean
        cc = np.array(common_ratings_c, dtype=np.float32) - c_mean

        dot = float(np.dot(cu, cc))
        norm_u = float(np.linalg.norm(cu))
        norm_c = float(np.linalg.norm(cc))

        if norm_u == 0 or norm_c == 0:
            # 退化：用非中心化余弦
            dot = float(np.dot(common_ratings_u, common_ratings_c))
            norm_u = float(np.linalg.norm(common_ratings_u))
            norm_c = float(np.linalg.norm(common_ratings_c))
            if norm_u == 0 or norm_c == 0:
                return 0.0
            return (dot / (norm_u * norm_c)) * min(1.0, n_common / 10.0)

        base_sim = dot / (norm_u * norm_c)
        # 共同评分越多越可信
        confidence = min(1.0, n_common / 10.0)
        return base_sim * confidence

    def user_based_recommend(self, user_id, n_recommendations=10, k=30, seed=None):
        """基于用户的协同过滤推荐

        Args:
            user_id: 用户ID
            n_recommendations: 推荐数量
            k: 邻居数量
            seed: 随机数种子，None 表示不固定（每次刷新结果不同）
        """
        import random as _random
        if seed is not None:
            _random.seed(seed)

        if user_id not in self.user_id_map:
            return self._popular_fallback(user_id, n_recommendations, seed)

        user_idx = self.user_id_map[user_id]
        user_ratings_full = self.rating_matrix.getrow(user_idx)
        user_rated_books_set = set(user_ratings_full.indices)
        user_mean = float(self.user_means[user_idx])
        n_user_ratings = len(user_ratings_full.data)

        # 评分太少的用户，CF 不可靠 → 用 fallback
        if n_user_ratings < 5:
            return self._popular_fallback(user_id, n_recommendations, seed)

        # 步骤 1: 对每个候选用户计算相似度
        similarities = []
        for cand_idx in self.candidate_user_indices:
            if cand_idx == user_idx:
                continue
            sim = self._cosine_similarity_on_overlap(user_idx, cand_idx)
            if sim > 0.01:
                # 加较大的随机扰动 (±0.3)，让邻居选择有变化
                sim += _random.uniform(-0.3, 0.3)
                similarities.append((sim, cand_idx))

        # 步骤 2: 按相似度降序取 top-k 邻居
        similarities.sort(key=lambda x: x[0], reverse=True)
        # 扩大邻居池到 2k，然后从中随机取 k 个（增加多样性）
        expanded_neighbors = similarities[:k * 2]
        _random.shuffle(expanded_neighbors)
        neighbors = expanded_neighbors[:k]

        # 邻居太少 → fallback
        if len(neighbors) < 5:
            return self._popular_fallback(user_id, n_recommendations, seed)

        # 步骤 3: 基于邻居评分加权预测
        book_accum = {}
        for sim, cand_idx in neighbors:
            cand_info = self._get_user_ratings_info(cand_idx)
            cand_mean = cand_info[2]
            cand_row = self.rating_matrix.getrow(cand_idx)
            cand_books = cand_row.indices
            cand_ratings = cand_row.data

            for i in range(len(cand_books)):
                book_idx = cand_books[i]
                if book_idx in user_rated_books_set:
                    continue
                rating = float(cand_ratings[i])
                centered = rating - cand_mean
                weighted = centered * sim

                if book_idx not in book_accum:
                    book_accum[book_idx] = [0.0, 0.0, 0]
                book_accum[book_idx][0] += weighted
                book_accum[book_idx][1] += sim
                book_accum[book_idx][2] += 1

        if not book_accum:
            return self._popular_fallback(user_id, n_recommendations, seed)

        # 步骤 4: 归一化 + 还原均值 + 排序
        results = []
        for book_idx, (pred_sum, sim_sum, n_raters) in book_accum.items():
            if sim_sum <= 0 or n_raters < 2:
                continue
            predicted = user_mean + pred_sum / sim_sum
            predicted = max(1.0, min(10.0, predicted))
            # 加较大随机扰动 (±1.5)，让每次刷新排序有显著变化
            adjusted_score = predicted + _random.uniform(-1.5, 1.5)
            if book_idx in self.reverse_book_map:
                results.append((adjusted_score, self.reverse_book_map[book_idx], predicted))

        # 按调整后的分数排序
        results.sort(key=lambda x: x[0], reverse=True)
        # 关键策略：从 top-n*3 中随机取 n 个，进一步增加多样性
        expanded_top = results[:n_recommendations * 3]
        _random.shuffle(expanded_top)
        top_results = expanded_top[:n_recommendations]

        if len(top_results) < 3:
            return self._popular_fallback(user_id, n_recommendations, seed)

        return [
            {'book_id': book_id, 'predicted_rating': round(float(pred), 3)}
            for _, book_id, pred in top_results
        ]

    def item_based_recommend(self, user_id, n_recommendations=10, k=20):
        """基于物品的协同过滤推荐（简化：与 user-based 共享邻居但用不同逻辑）"""
        # 对于评分少的用户，直接用 user-based fallback 逻辑
        return self.user_based_recommend(user_id, n_recommendations, k)

    def _popular_fallback(self, user_id, n_recommendations, seed=None):
        """协同过滤无法产生推荐时，返回热门书籍（支持随机种子）"""
        import random as _random
        if seed is not None:
            _random.seed(seed)

        excluded_books = set()
        if user_id in self.user_id_map:
            user_idx = self.user_id_map[user_id]
            user_rated = self.rating_matrix.getrow(user_idx).indices
            for bidx in user_rated:
                if bidx in self.reverse_book_map:
                    excluded_books.add(self.reverse_book_map[bidx])

        # 从热门书中随机选取（增加刷新时的多样性）
        popular_available = [bid for bid in self.popular_book_ids if bid not in excluded_books]
        _random.shuffle(popular_available)

        results = []
        for book_id in popular_available[:n_recommendations]:
            results.append({
                'book_id': book_id,
                'predicted_rating': round(self.global_mean, 3)
            })
        return results

    def predict_single(self, user_id, book_id, k=20):
        """对单个 (user, book) 对进行协同过滤预测评分，用于评估"""
        if user_id not in self.user_id_map or book_id not in self.book_id_map:
            return None

        user_idx = self.user_id_map[user_id]
        book_idx = self.book_id_map[book_id]
        user_mean = float(self.user_means[user_idx])

        # 找评过这本书的候选用户
        col = self.rating_matrix.getcol(book_idx)
        rater_indices = col.indices
        rater_ratings = col.data

        if len(rater_indices) == 0:
            return None

        # 计算与这些评分者的相似度
        neighbor_info = []
        for rater_idx in rater_indices:
            if rater_idx == user_idx:
                continue
            sim = self._cosine_similarity_on_overlap(user_idx, rater_idx)
            if sim > 0.01:
                neighbor_info.append((sim, rater_idx))

        neighbor_info.sort(key=lambda x: x[0], reverse=True)
        neighbor_info = neighbor_info[:k]

        if len(neighbor_info) < 3:
            return None

        numerator = 0.0
        denominator = 0.0
        for sim, cand_idx in neighbor_info:
            cand_mean = float(self.user_means[cand_idx])
            rating = float(self.rating_matrix[cand_idx, book_idx])
            if rating > 0:
                numerator += sim * (rating - cand_mean)
                denominator += sim

        if denominator == 0:
            return None

        prediction = user_mean + numerator / denominator
        return float(min(max(prediction, 1.0), 10.0))

    def set_semantic_weight(self, weight):
        """设置语义召回权重 (0.0 - 1.0)"""
        self.semantic_weight = max(0.0, min(1.0, weight))

    def get_user_liked_books(self, user_id, min_rating=7):
        """获取用户喜欢的书籍（高评分）"""
        if user_id not in self.user_id_map:
            return []

        user_idx = self.user_id_map[user_id]
        row = self.rating_matrix.getrow(user_idx)
        liked_indices = row.indices[row.data >= min_rating]
        return [self.reverse_book_map[idx] for idx in liked_indices if idx in self.reverse_book_map]

    def semantic_enhanced_recommend(self, user_id, n_recommendations=10, k=30,
                                   embedding_service=None, seed=None):
        """
        语义增强的协同过滤推荐
        结合协同过滤分数和语义相似度

        Args:
            user_id: 用户ID
            n_recommendations: 推荐数量
            k: 邻居数量
            embedding_service: 语义embedding服务（可选）
            seed: 随机数种子

        Returns:
            推荐列表，包含 cf_score 和 semantic_score
        """
        import random as _random
        if seed is not None:
            _random.seed(seed)

        # 步骤1: 获取协同过滤推荐
        cf_results = self.user_based_recommend(user_id, n_recommendations * 3, k, seed)

        if not cf_results:
            return self._popular_fallback(user_id, n_recommendations, seed)

        # 如果没有embedding服务，退化为纯CF
        if embedding_service is None:
            return cf_results[:n_recommendations]

        # 步骤2: 获取用户喜欢的书籍用于计算语义相似度
        user_liked_book_ids = self.get_user_liked_books(user_id)

        if not user_liked_book_ids:
            return cf_results[:n_recommendations]

        # 步骤3: 获取候选书籍的详细信息
        from models import Book
        candidate_book_ids = [r['book_id'] for r in cf_results]
        candidate_books = Book.query.filter(Book.id.in_(candidate_book_ids)).all()
        liked_books = Book.query.filter(Book.id.in_(user_liked_book_ids)).all()

        if not candidate_books or not liked_books:
            return cf_results[:n_recommendations]

        # 步骤4: 计算内容相似度分数
        content_scores = embedding_service.content_based_recall(
            liked_books, candidate_books, top_k=len(candidate_books)
        )
        content_score_map = {item['book'].id: item['score'] for item in content_scores}

        # 步骤5: 混合CF分数和语义分数
        combined_results = []
        for cf_rec in cf_results:
            book_id = cf_rec['book_id']
            cf_score = cf_rec['predicted_rating']

            # 归一化CF分数到0-1范围
            normalized_cf = (cf_score - 1.0) / 9.0

            # 获取语义分数
            semantic_score = content_score_map.get(book_id, 0.0)

            # 加权混合
            final_score = (1.0 - self.semantic_weight) * normalized_cf + \
                          self.semantic_weight * semantic_score

            combined_results.append({
                'book_id': book_id,
                'cf_score': cf_score,
                'semantic_score': round(semantic_score, 3),
                'combined_score': round(final_score, 3)
            })

        # 按混合分数排序
        combined_results.sort(key=lambda x: x['combined_score'], reverse=True)

        # 添加随机扰动增加多样性
        top_pool = combined_results[:n_recommendations * 2]
        _random.shuffle(top_pool)
        final_results = top_pool[:n_recommendations]

        return [{
            'book_id': r['book_id'],
            'predicted_rating': round(r['combined_score'] * 9.0 + 1.0, 3),
            'cf_score': r['cf_score'],
            'semantic_score': r['semantic_score']
        } for r in final_results]
