import numpy as np
import time
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from services.cf_algorithm import CollaborativeFiltering
from services.svd_algorithm import SVDRecommendation


class Evaluator:
    def __init__(self, cf_engine=None, svd_engine=None):
        """
        评估器 - 可复用已初始化的 CF/SVD 引擎
        Args:
            cf_engine: 已初始化的 CollaborativeFiltering 实例
            svd_engine: 已初始化的 SVDRecommendation 实例
        """
        print('  [评估器] 正在初始化...')
        self.cf = cf_engine if cf_engine is not None else CollaborativeFiltering()
        self.svd = svd_engine if svd_engine is not None else SVDRecommendation()
        print('  [评估器] 初始化完成')

    def evaluate_cf(self, n_samples=300):
        """评估协同过滤算法: RMSE, MAE"""
        df = self.cf.df
        if df.empty or len(df) == 0:
            return {'rmse': None, 'mae': None, 'n_evaluated': 0}

        # 采样部分数据作为测试集
        test_df = df.sample(n=min(n_samples, len(df)), random_state=42)

        predictions = []
        actuals = []

        for _, row in test_df.iterrows():
            pred = self.cf.predict_single(row['user_id'], row['book_id'])
            if pred is not None:
                predictions.append(pred)
                actuals.append(row['rating'])

        if not predictions:
            return {'rmse': None, 'mae': None, 'n_evaluated': 0}

        pred_arr = np.array(predictions)
        actual_arr = np.array(actuals)
        rmse = float(np.sqrt(np.mean((pred_arr - actual_arr) ** 2)))
        mae = float(np.mean(np.abs(pred_arr - actual_arr)))

        return {
            'rmse': round(rmse, 3),
            'mae': round(mae, 3),
            'n_evaluated': len(predictions)
        }

    def compute_ranking_metrics(self, k_list=None, n_test_users=30):
        """
        计算排名质量指标:
        - Precision@K: 推荐列表中用户实际喜欢的书籍比例
        - Recall@K: 用户喜欢的书籍中被推荐出来的比例
        - Coverage: 推荐系统能覆盖多少不同的书籍
        """
        if k_list is None:
            k_list = [5, 10, 20]

        df = self.cf.df
        if df.empty:
            return {}

        # 取评分活跃的用户用于测试 (至少有 k 条评分)
        user_counts = df['user_id'].value_counts()
        valid_users = user_counts[user_counts >= max(k_list)].index.tolist()
        if len(valid_users) == 0:
            valid_users = user_counts.index.tolist()[:n_test_users]

        test_users = np.random.choice(
            valid_users,
            size=min(n_test_users, len(valid_users)),
            replace=False
        )

        # 定义"喜欢"为评分 >= 7
        LIKE_THRESHOLD = 7

        all_recommended_books_cf = set()
        all_recommended_books_svd = set()
        cf_precision = {k: [] for k in k_list}
        cf_recall = {k: [] for k in k_list}
        svd_precision = {k: [] for k in k_list}
        svd_recall = {k: [] for k in k_list}

        for user_id in test_users:
            user_ratings = df[df['user_id'] == user_id]
            liked_books = set(user_ratings[user_ratings['rating'] >= LIKE_THRESHOLD]['book_id'].tolist())
            if len(liked_books) == 0:
                continue

            # CF 推荐
            cf_recs = self.cf.user_based_recommend(user_id, n_recommendations=max(k_list))
            cf_rec_books = [r['book_id'] for r in cf_recs]

            # SVD 推荐
            svd_recs = self.svd.recommend(user_id, n_recommendations=max(k_list))
            svd_rec_books = [r['book_id'] for r in svd_recs]

            all_recommended_books_cf.update(cf_rec_books)
            all_recommended_books_svd.update(svd_rec_books)

            for k in k_list:
                cf_top = set(cf_rec_books[:k])
                svd_top = set(svd_rec_books[:k])

                # Precision@K: 推荐中正确的比例
                cf_hit = len(cf_top & liked_books)
                svd_hit = len(svd_top & liked_books)
                cf_precision[k].append(cf_hit / max(len(cf_top), 1))
                svd_precision[k].append(svd_hit / max(len(svd_top), 1))

                # Recall@K: 正确推荐占用户喜欢总数的比例
                cf_recall[k].append(cf_hit / len(liked_books))
                svd_recall[k].append(svd_hit / len(liked_books))

        # 覆盖率: 推荐系统能推荐的不同书籍占总书籍的比例
        total_books = df['book_id'].nunique()
        all_recommended = all_recommended_books_cf | all_recommended_books_svd
        coverage = len(all_recommended) / total_books if total_books > 0 else 0

        result = {
            'coverage': round(coverage, 4),
            'n_test_users': int(len(test_users))
        }

        for k in k_list:
            result[f'cf_precision@{k}'] = round(float(np.mean(cf_precision[k])) if cf_precision[k] else 0, 4)
            result[f'cf_recall@{k}'] = round(float(np.mean(cf_recall[k])) if cf_recall[k] else 0, 4)
            result[f'svd_precision@{k}'] = round(float(np.mean(svd_precision[k])) if svd_precision[k] else 0, 4)
            result[f'svd_recall@{k}'] = round(float(np.mean(svd_recall[k])) if svd_recall[k] else 0, 4)

        return result

    def compare_algorithms(self):
        """对比所有算法 - 返回完整的评估结果"""
        print('  [评估器] 评估 CF (RMSE/MAE)...')
        cf_results = self.evaluate_cf(n_samples=300)
        print(f'  [评估器] CF: RMSE={cf_results.get("rmse")}, MAE={cf_results.get("mae")}, n={cf_results.get("n_evaluated")}')

        print('  [评估器] 评估 SVD...')
        svd_results_raw = self.svd.evaluate()
        svd_results = {
            'rmse': round(float(svd_results_raw.get('rmse', 0)), 3),
            'mae': round(float(svd_results_raw.get('mae', 0)), 3)
        }
        print(f'  [评估器] SVD: RMSE={svd_results["rmse"]}, MAE={svd_results["mae"]}')

        print('  [评估器] 计算排名指标 (Precision/Recall@K)...')
        ranking = self.compute_ranking_metrics(k_list=[5, 10, 20], n_test_users=30)
        print(f'  [评估器] 覆盖率={ranking.get("coverage")}')

        comparison = {
            'rmse': {
                'cf': cf_results.get('rmse'),
                'svd': svd_results.get('rmse')
            },
            'mae': {
                'cf': cf_results.get('mae'),
                'svd': svd_results.get('mae')
            }
        }

        # 添加排名指标
        for key, val in ranking.items():
            comparison[key] = val

        return {
            'collaborative_filtering': cf_results,
            'svd': svd_results,
            'ranking_metrics': ranking,
            'comparison': comparison
        }


class ABTestFramework:
    """
    实时 A/B 测试框架
    用于对比不同推荐算法的效果
    """

    def __init__(self):
        # 实验配置
        self.experiments = {}
        # 用户分配记录
        self.user_assignments = {}
        # 实验结果
        self.experiment_results = defaultdict(lambda: {
            'control': [],
            'treatment': []
        })
        # 实验开始时间
        self.experiment_start_times = {}

    def _hash_user(self, user_id, experiment_id):
        """将用户哈希到实验组/对照组"""
        hash_str = f"{experiment_id}:{user_id}"
        hash_val = int(hashlib.md5(hash_str.encode()).hexdigest(), 16)
        return 'treatment' if hash_val % 2 == 0 else 'control'

    def create_experiment(self, experiment_id, description="",
                        control_config=None, treatment_config=None):
        """
        创建新的 A/B 实验

        Args:
            experiment_id: 实验ID
            description: 实验描述
            control_config: 对照组配置 {'algorithm': 'cf', ...}
            treatment_config: 实验组配置 {'algorithm': 'hybrid', ...}
        """
        if control_config is None:
            control_config = {'algorithm': 'cf'}
        if treatment_config is None:
            treatment_config = {'algorithm': 'hybrid'}

        self.experiments[experiment_id] = {
            'description': description,
            'control': control_config,
            'treatment': treatment_config,
            'active': True
        }
        self.experiment_start_times[experiment_id] = time.time()
        print(f'  [A/B Test] 创建实验: {experiment_id}')
        return True

    def get_user_variant(self, user_id, experiment_id):
        """获取用户所属的实验变体"""
        key = f"{experiment_id}:{user_id}"
        if key not in self.user_assignments:
            self.user_assignments[key] = self._hash_user(user_id, experiment_id)
        return self.user_assignments[key]

    def record_interaction(self, experiment_id, user_id, book_id, action,
                          rating=None, timestamp=None):
        """
        记录用户与推荐的交互

        Args:
            experiment_id: 实验ID
            user_id: 用户ID
            book_id: 书籍ID
            action: 交互类型 ('click', 'view', 'rating')
            rating: 评分（如果是 rating 动作）
            timestamp: 时间戳
        """
        if experiment_id not in self.experiments:
            return False

        if timestamp is None:
            timestamp = time.time()

        variant = self.get_user_variant(user_id, experiment_id)

        result = {
            'user_id': user_id,
            'book_id': book_id,
            'action': action,
            'timestamp': timestamp
        }
        if rating is not None:
            result['rating'] = rating

        self.experiment_results[experiment_id][variant].append(result)
        return True

    def get_experiment_stats(self, experiment_id, min_samples=10):
        """
        获取实验统计信息

        Returns:
            {
                'n_control': int,
                'n_treatment': int,
                'control_ctr': float,  # 点击率
                'treatment_ctr': float,
                'control_avg_rating': float,
                'treatment_avg_rating': float,
                'significant': bool,
                'confidence': float
            }
        """
        if experiment_id not in self.experiments:
            return None

        control = self.experiment_results[experiment_id]['control']
        treatment = self.experiment_results[experiment_id]['treatment']

        stats = {
            'n_control': len(control),
            'n_treatment': len(treatment),
            'control_ctr': 0.0,
            'treatment_ctr': 0.0,
            'control_avg_rating': 0.0,
            'treatment_avg_rating': 0.0,
            'significant': False,
            'confidence': 0.0
        }

        if len(control) < min_samples or len(treatment) < min_samples:
            return stats

        # 计算点击率 (click-through rate)
        control_clicks = sum(1 for r in control if r['action'] in ('click', 'rating'))
        treatment_clicks = sum(1 for r in treatment if r['action'] in ('click', 'rating'))

        stats['control_ctr'] = control_clicks / len(control) if len(control) > 0 else 0
        stats['treatment_ctr'] = treatment_clicks / len(treatment) if len(treatment) > 0 else 0

        # 计算平均评分
        control_ratings = [r['rating'] for r in control if r['action'] == 'rating' and 'rating' in r]
        treatment_ratings = [r['rating'] for r in treatment if r['action'] == 'rating' and 'rating' in r]

        if control_ratings:
            stats['control_avg_rating'] = np.mean(control_ratings)
        if treatment_ratings:
            stats['treatment_avg_rating'] = np.mean(treatment_ratings)

        # 简化的显著性检验 (Z-test for proportions)
        if stats['control_ctr'] > 0 and stats['treatment_ctr'] > 0:
            p1, p2 = stats['control_ctr'], stats['treatment_ctr']
            n1, n2 = len(control), len(treatment)
            pooled_p = (control_clicks + treatment_clicks) / (n1 + n2)
            se = np.sqrt(pooled_p * (1 - pooled_p) * (1/n1 + 1/n2))
            if se > 0:
                z_score = (p2 - p1) / se
                stats['confidence'] = min(1.0, abs(z_score) / 2.0)  # 简化的置信度
                stats['significant'] = stats['confidence'] > 0.95

        return stats

    def list_experiments(self):
        """列出所有实验及其状态"""
        result = []
        for exp_id, config in self.experiments.items():
            stats = self.get_experiment_stats(exp_id)
            result.append({
                'experiment_id': exp_id,
                'description': config['description'],
                'active': config['active'],
                'duration_seconds': time.time() - self.experiment_start_times.get(exp_id, 0),
                'statistics': stats
            })
        return result

    def stop_experiment(self, experiment_id):
        """停止实验"""
        if experiment_id in self.experiments:
            self.experiments[experiment_id]['active'] = False
            return True
        return False


class UserInterestDriftDetector:
    """
    用户兴趣 drift 检测器
    检测用户兴趣是否发生显著变化
    """

    def __init__(self, window_size=20, threshold=0.15):
        """
        Args:
            window_size: 用于比较的评分窗口大小
            threshold: drift 检测阈值
        """
        self.window_size = window_size
        self.threshold = threshold
        # 用户历史评分记录
        self.user_rating_history = defaultdict(list)
        # 用户兴趣向量
        self.user_profiles = {}
        # 检测到的 drift 事件
        self.drift_events = []

    def add_rating(self, user_id, book_id, rating, timestamp=None):
        """添加新的评分记录"""
        if timestamp is None:
            timestamp = time.time()

        self.user_rating_history[user_id].append({
            'book_id': book_id,
            'rating': rating,
            'timestamp': timestamp
        })

        # 检测 drift
        drift_detected = self._check_drift(user_id)

        return drift_detected

    def _compute_profile(self, ratings):
        """计算用户兴趣特征（简化版：评分分布）"""
        if not ratings:
            return None

        recent = ratings[-self.window_size:]
        ratings_only = [r['rating'] for r in recent]

        # 计算特征：平均评分、方差、评分分布
        mean = np.mean(ratings_only)
        std = np.std(ratings_only)

        # 高分比例 (>=7)
        high_ratio = sum(1 for r in ratings_only if r >= 7) / len(ratings_only)

        # 低分比例 (<=4)
        low_ratio = sum(1 for r in ratings_only if r <= 4) / len(ratings_only)

        return {
            'mean': mean,
            'std': std,
            'high_ratio': high_ratio,
            'low_ratio': low_ratio,
            'n_ratings': len(ratings_only)
        }

    def _check_drift(self, user_id):
        """检测用户兴趣是否发生 drift"""
        history = self.user_rating_history.get(user_id, [])

        if len(history) < self.window_size * 2:
            return False

        old_profile = self._compute_profile(history[:-self.window_size])
        new_profile = self._compute_profile(history[-self.window_size:])

        if old_profile is None or new_profile is None:
            return False

        # 计算特征差异
        mean_diff = abs(new_profile['mean'] - old_profile['mean'])
        high_ratio_diff = abs(new_profile['high_ratio'] - old_profile['high_ratio'])

        # 综合 drift 分数
        drift_score = (mean_diff / 5.0) * 0.5 + high_ratio_diff * 0.5

        if drift_score > self.threshold:
            self.drift_events.append({
                'user_id': user_id,
                'timestamp': history[-1]['timestamp'],
                'drift_score': drift_score,
                'old_profile': old_profile,
                'new_profile': new_profile
            })
            return True

        return False

    def get_user_drift_status(self, user_id):
        """获取用户的 drift 状态"""
        history = self.user_rating_history.get(user_id, [])

        if len(history) < self.window_size:
            return {
                'has_enough_data': False,
                'recent_drift': False,
                'drift_score': 0.0,
                'profile': None
            }

        current_profile = self._compute_profile(history[-self.window_size:])
        recent_drifts = [e for e in self.drift_events if e['user_id'] == user_id]

        last_drift = recent_drifts[-1] if recent_drifts else None

        return {
            'has_enough_data': True,
            'recent_drift': last_drift is not None and \
                          (time.time() - last_drift['timestamp']) < 86400 * 7,  # 7天内
            'drift_score': last_drift['drift_score'] if last_drift else 0.0,
            'profile': current_profile,
            'last_drift': last_drift
        }

    def get_all_drifts(self, limit=50):
        """获取最近的 drift 事件"""
        sorted_events = sorted(self.drift_events,
                             key=lambda x: x['timestamp'],
                             reverse=True)
        return sorted_events[:limit]

    def recommend_with_drift_adaptation(self, user_id, base_recommendations,
                                       cf_engine=None, embedding_service=None):
        """
        结合 drift 检测的自适应推荐

        如果检测到用户兴趣 drift，增加探索性，减少保守推荐
        """
        drift_status = self.get_user_drift_status(user_id)

        if not drift_status['has_enough_data']:
            return base_recommendations

        # 如果没有 drift，使用正常推荐
        if not drift_status['recent_drift']:
            return base_recommendations

        # 检测到 drift，增加语义召回权重
        drift_score = drift_status['drift_score']

        # 根据 drift 程度调整：drift 越大，越依赖语义召回
        semantic_weight = min(0.5, 0.2 + drift_score * 0.3)

        # 调整 CF 引擎的语义权重
        if cf_engine is not None:
            cf_engine.set_semantic_weight(semantic_weight)

        return base_recommendations


# 全局 A/B 测试和 Drift 检测实例
_ab_test_framework = None
_drift_detector = None


def get_ab_test_framework():
    global _ab_test_framework
    if _ab_test_framework is None:
        _ab_test_framework = ABTestFramework()
        # 创建默认实验
        _ab_test_framework.create_experiment(
            'recommendation_algorithm',
            description='推荐算法对比实验',
            control_config={'algorithm': 'cf'},
            treatment_config={'algorithm': 'hybrid'}
        )
    return _ab_test_framework


def get_drift_detector():
    global _drift_detector
    if _drift_detector is None:
        _drift_detector = UserInterestDriftDetector()
    return _drift_detector
