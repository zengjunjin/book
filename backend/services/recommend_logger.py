# -*- coding: utf-8 -*-
"""推荐日志与质量指标服务
- RecommendationLogger: 单例，记录 impression/click/conversion，内存存储 + 可选日志文件
- ABTestService: 增强版 A/B 实验服务，hash 分配，两组对比统计
"""

import os
import time
import json
import hashlib
import logging
import threading
from collections import deque, defaultdict
from typing import Optional, List, Dict, Any


# ============ RecommendationLogger ============

class RecommendationLogger:
    """推荐日志与质量指标服务（单例）
    - 内存存储：dict + deque（不依赖 DB）
    - 可选日志文件：LOG_FILE 存在时追加 JSON 行
    - TTL 缓存：metrics 缓存 N 秒，降低计算开销
    """
    _instance = None
    _lock = threading.Lock()

    MAX_EVENTS = 10000
    METRICS_CACHE_TTL = 5.0

    LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
    LOG_FILE = os.path.abspath(os.path.join(LOG_DIR, 'recommend.log'))

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._events_lock = threading.Lock()
        self._impressions: deque = deque(maxlen=self.MAX_EVENTS)
        self._clicks: deque = deque(maxlen=self.MAX_EVENTS)
        self._conversions: deque = deque(maxlen=self.MAX_EVENTS)
        self._click_key = set()      # (user_id, book_id, algorithm) 去重 click
        self._conv_key = set()       # (user_id, book_id) 去重 conversion
        self._metrics_cache = {}     # cache_key -> (ts, value)
        self._logger = None
        try:
            os.makedirs(self.LOG_DIR, exist_ok=True)
            logger = logging.getLogger('recommend_logger')
            logger.setLevel(logging.INFO)
            if not logger.handlers:
                try:
                    fh = logging.FileHandler(self.LOG_FILE, encoding='utf-8')
                    fh.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
                    logger.addHandler(fh)
                except Exception:
                    pass
            self._logger = logger
        except Exception:
            self._logger = None

    # -------- 写入 --------
    def _write_log(self, payload: dict):
        try:
            if self._logger is not None:
                self._logger.info(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    def log_impression(self, user_id, book_ids, algorithm):
        try:
            uid = int(user_id)
            algo = str(algorithm or 'unknown')
            if uid <= 0 or not book_ids:
                return False
            ts = time.time()
            ids = [int(b) for b in book_ids if int(b) > 0]
            if not ids:
                return False
            with self._events_lock:
                self._impressions.append({
                    'ts': ts, 'user_id': uid, 'book_ids': ids, 'algorithm': algo,
                })
                self._invalidate_cache()
            self._write_log({'type': 'impression', 'user_id': uid, 'book_ids': ids, 'algorithm': algo})
            return True
        except Exception:
            return False

    def log_click(self, user_id, book_id, algorithm):
        try:
            uid = int(user_id)
            bid = int(book_id)
            algo = str(algorithm or 'unknown')
            if uid <= 0 or bid <= 0:
                return False
            key = (uid, bid, algo)
            with self._events_lock:
                if key in self._click_key:
                    return True
                self._click_key.add(key)
                self._clicks.append({
                    'ts': time.time(), 'user_id': uid, 'book_id': bid, 'algorithm': algo,
                })
                self._invalidate_cache()
            self._write_log({'type': 'click', 'user_id': uid, 'book_id': bid, 'algorithm': algo})
            return True
        except Exception:
            return False

    def log_conversion(self, user_id, book_id, rating):
        try:
            uid = int(user_id)
            bid = int(book_id)
            r = int(rating)
            if uid <= 0 or bid <= 0 or not (1 <= r <= 10):
                return False
            key = (uid, bid)
            with self._events_lock:
                if key in self._conv_key:
                    return True
                self._conv_key.add(key)
                self._conversions.append({
                    'ts': time.time(), 'user_id': uid, 'book_id': bid, 'rating': r,
                })
                self._invalidate_cache()
            self._write_log({'type': 'conversion', 'user_id': uid, 'book_id': bid, 'rating': r})
            return True
        except Exception:
            return False

    def _invalidate_cache(self):
        self._metrics_cache.clear()

    # -------- 读取 --------
    def get_metrics(self, user_id: Optional[int] = None, algorithm: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        try:
            cache_key = f'metrics:{user_id}:{algorithm}:{limit}'
            now = time.time()
            cached = self._metrics_cache.get(cache_key)
            if cached and (now - cached[0]) < self.METRICS_CACHE_TTL:
                return cached[1]

            with self._events_lock:
                impr_count = 0
                click_count = 0
                conv_count = 0
                recent_books = []
                seen_books = set()

                for ev in list(self._impressions):
                    if user_id is not None and ev['user_id'] != int(user_id):
                        continue
                    if algorithm and ev['algorithm'] != str(algorithm):
                        continue
                    impr_count += len(ev['book_ids'])
                    for b in ev['book_ids']:
                        if b not in seen_books:
                            seen_books.add(b)
                            recent_books.append(b)

                for ev in list(self._clicks):
                    if user_id is not None and ev['user_id'] != int(user_id):
                        continue
                    if algorithm and ev['algorithm'] != str(algorithm):
                        continue
                    click_count += 1

                for ev in list(self._conversions):
                    if user_id is not None and ev['user_id'] != int(user_id):
                        continue
                    conv_count += 1

                ctr = (click_count / impr_count) if impr_count > 0 else 0.0
                result = {
                    'impressions': impr_count,
                    'clicks': click_count,
                    'conversions': conv_count,
                    'ctr': round(ctr, 6),
                    'recent_books': recent_books[:int(limit)],
                }
                self._metrics_cache[cache_key] = (now, result)
                return result
        except Exception:
            return {'impressions': 0, 'clicks': 0, 'conversions': 0, 'ctr': 0.0, 'recent_books': []}

    def get_algorithm_comparison(self) -> List[Dict[str, Any]]:
        try:
            cache_key = 'algo_cmp'
            now = time.time()
            cached = self._metrics_cache.get(cache_key)
            if cached and (now - cached[0]) < self.METRICS_CACHE_TTL:
                return cached[1]

            with self._events_lock:
                stats = defaultdict(lambda: {'impressions': 0, 'clicks': 0, 'conversions': 0})

                for ev in list(self._impressions):
                    stats[ev['algorithm']]['impressions'] += len(ev['book_ids'])
                for ev in list(self._clicks):
                    stats[ev['algorithm']]['clicks'] += 1
                # conversion 没有存 algorithm，按比例均摊计入所有已存在算法
                conv_total = len(self._conversions)
                algo_list = list(stats.keys())
                if conv_total and algo_list:
                    share = conv_total / len(algo_list)
                    for a in algo_list:
                        stats[a]['conversions'] = int(share)

                result = []
                for algo, s in stats.items():
                    impr = s['impressions']
                    clicks = s['clicks']
                    ctr = (clicks / impr) if impr > 0 else 0.0
                    result.append({
                        'algorithm': algo,
                        'impressions': impr,
                        'clicks': clicks,
                        'conversions': s['conversions'],
                        'ctr': round(ctr, 6),
                    })
                result.sort(key=lambda x: x['ctr'], reverse=True)
                self._metrics_cache[cache_key] = (now, result)
                return result
        except Exception:
            return []


# ============ ABTestService ============

class ABTestService:
    """增强版 A/B 实验服务
    - create_experiment / assign_user（hash 50/50）
    - record_result / get_stats（两组 CTR + 转化 + 简易显著性提示）
    - list_experiments
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._mu = threading.Lock()
        self._experiments: Dict[str, Dict[str, Any]] = {}
        self._user_assign: Dict[tuple, str] = {}     # (exp_id, user_id) -> group
        self._results: Dict[str, Dict[str, Dict[str, int]]] = {}
        # results[exp_id][group] = {'impressions':0,'clicks':0,'conversions':0}

    def create_experiment(self, experiment_id: str, control_algorithm: str, treatment_algorithm: str) -> bool:
        try:
            eid = str(experiment_id or '').strip()
            if not eid or not control_algorithm or not treatment_algorithm:
                return False
            with self._mu:
                if eid in self._experiments:
                    return True
                self._experiments[eid] = {
                    'id': eid,
                    'control': str(control_algorithm),
                    'treatment': str(treatment_algorithm),
                    'created_at': time.time(),
                }
                self._results[eid] = {
                    'control': {'impressions': 0, 'clicks': 0, 'conversions': 0},
                    'treatment': {'impressions': 0, 'clicks': 0, 'conversions': 0},
                }
            return True
        except Exception:
            return False

    def assign_user(self, user_id, experiment_id: str) -> Optional[str]:
        try:
            uid = int(user_id)
            eid = str(experiment_id or '').strip()
            if uid <= 0 or not eid:
                return None
            key = (eid, uid)
            with self._mu:
                if key in self._user_assign:
                    return self._user_assign[key]
                if eid not in self._experiments:
                    return None
                h = hashlib.md5(f'{eid}:{uid}'.encode('utf-8')).hexdigest()
                group = 'treatment' if (int(h[:4], 16) % 2 == 0) else 'control'
                self._user_assign[key] = group
                return group
        except Exception:
            return None

    def record_result(self, experiment_id: str, user_id, group: str, clicks: int = 0, ratings: int = 0) -> bool:
        try:
            eid = str(experiment_id or '').strip()
            uid = int(user_id)
            g = str(group or '').strip().lower()
            if not eid or uid <= 0 or g not in ('control', 'treatment'):
                return False
            c = int(clicks or 0)
            r = int(ratings or 0)
            with self._mu:
                if eid not in self._results:
                    self._results[eid] = {
                        'control': {'impressions': 0, 'clicks': 0, 'conversions': 0},
                        'treatment': {'impressions': 0, 'clicks': 0, 'conversions': 0},
                    }
                self._results[eid][g]['impressions'] += 1
                self._results[eid][g]['clicks'] += max(c, 0)
                self._results[eid][g]['conversions'] += max(r, 0)
            return True
        except Exception:
            return False

    @staticmethod
    def _ctr_group(s: Dict[str, int]) -> float:
        impr = s.get('impressions', 0)
        clicks = s.get('clicks', 0)
        return (clicks / impr) if impr > 0 else 0.0

    @staticmethod
    def _conv_group(s: Dict[str, int]) -> float:
        impr = s.get('impressions', 0)
        conv = s.get('conversions', 0)
        return (conv / impr) if impr > 0 else 0.0

    def _significance_hint(self, ctrl: Dict[str, int], trt: Dict[str, int]) -> str:
        try:
            n1 = max(ctrl.get('impressions', 0), 1)
            n2 = max(trt.get('impressions', 0), 1)
            p1 = self._ctr_group(ctrl)
            p2 = self._ctr_group(trt)
            # 两比例 z 检验近似（仅给出相对差异 & 样本量提示）
            diff = p2 - p1
            rel = (diff / p1) if p1 > 0 else 0.0
            if n1 < 30 or n2 < 30:
                return f'样本量不足 (ctrl={n1}, trt={n2})，差异不可靠；相对提升 {rel:+.2%}'
            return f'相对提升 {rel:+.2%}，绝对差异 {diff:+.4f}；样本量 {n1}/{n2}'
        except Exception:
            return 'significance unknown'

    def get_stats(self, experiment_id: str) -> Dict[str, Any]:
        try:
            eid = str(experiment_id or '').strip()
            with self._mu:
                if eid not in self._experiments or eid not in self._results:
                    return {'experiment_id': eid, 'exists': False, 'control': {}, 'treatment': {}}
                exp = self._experiments[eid]
                res = self._results[eid]
                ctrl = dict(res['control'])
                trt = dict(res['treatment'])
                return {
                    'experiment_id': eid,
                    'exists': True,
                    'control_algorithm': exp.get('control'),
                    'treatment_algorithm': exp.get('treatment'),
                    'created_at': exp.get('created_at'),
                    'control': {
                        **ctrl,
                        'ctr': round(self._ctr_group(ctrl), 6),
                        'conversion_rate': round(self._conv_group(ctrl), 6),
                    },
                    'treatment': {
                        **trt,
                        'ctr': round(self._ctr_group(trt), 6),
                        'conversion_rate': round(self._conv_group(trt), 6),
                    },
                    'significance_hint': self._significance_hint(ctrl, trt),
                }
        except Exception:
            return {'experiment_id': experiment_id, 'exists': False}

    def list_experiments(self) -> List[Dict[str, Any]]:
        try:
            with self._mu:
                return [
                    {
                        'id': e['id'],
                        'control': e['control'],
                        'treatment': e['treatment'],
                        'created_at': e['created_at'],
                    }
                    for e in self._experiments.values()
                ]
        except Exception:
            return []
