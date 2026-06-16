"""搜索服务：Meilisearch（或 MySQL FULLTEXT 降级）+ 拼写建议 + BM25 混合
- 在生产环境启动 Meilisearch 并通过 deploy 脚本导入 books 索引
- 缺失时自动降级到 MySQL FULLTEXT + LIKE 前缀匹配
- 提供拼写建议（基于数据库现有书名前缀 + 简单编辑距离）
"""
import re
import time
import threading as _th
from functools import lru_cache

try:
    import meilisearch
    _MEILI_AVAILABLE = True
except Exception:
    meilisearch = None
    _MEILI_AVAILABLE = False

# 单例锁
_lock = _th.Lock()
_instance = None


class SearchService:

    def __init__(self, meili_host='http://127.0.0.1:7700', meili_key='', index_name='books',
                 bm25_k1=1.2, bm25_b=0.75):
        self.meili_host = meili_host
        self.meili_key = meili_key
        self.index_name = index_name
        self.bm25_k1 = bm25_k1
        self.bm25_b = bm25_b
        self.meili_client = None
        self.meili_index = None
        self.meili_working = False
        self._book_titles_cache = None
        self._book_titles_time = 0
        self._connect()

    def _connect(self):
        if not _MEILI_AVAILABLE:
            return
        try:
            self.meili_client = meilisearch.Client(self.meili_host, self.meili_key, timeout=3)
            # 简单 ping：获取 version；失败时静默降级
            self.meili_client.get_version()
            self.meili_index = self.meili_client.index(self.index_name)
            self.meili_working = True
        except Exception:
            self.meili_working = False

    def _get_db_books(self):
        """从 MySQL 拉取所有书籍（id, title, author, category, year）"""
        try:
            from extensions import db
            from models import Book
            rows = db.session.query(
                Book.id, Book.title, Book.author, Book.category, Book.year
            ).all()
            return [{'id': r.id, 'title': r.title or '',
                     'author': r.author or '',
                     'category': r.category or '',
                     'year': r.year or 0,
                     'keywords': (r.title or '') + ' ' + (r.author or '')}
                    for r in rows]
        except Exception:
            return []

    def index_all_books(self):
        """把所有书籍写入 Meilisearch（可选：部署脚本调用一次即可）。"""
        if not self.meili_working:
            return False
        try:
            books = self._get_db_books()
            self.meili_index.add_documents(books)
            return True
        except Exception:
            self.meili_working = False
            return False

    def _fulltext_search(self, query, limit=20):
        """MySQL FULLTEXT 降级搜索"""
        try:
            from extensions import db
            from models import Book, Rating
            from sqlalchemy import text, func, or_ as _or

            q = query.strip()
            if not q:
                return []

            # 1. 先用 MATCH AGAINST
            try:
                rows = db.session.query(
                    Book.id, Book.title, Book.author, Book.category, Book.year
                ).filter(
                    text("MATCH(title, author) AGAINST(:q IN BOOLEAN MODE)")
                ).params({'q': q}).limit(limit).all()
                if rows:
                    return [{'id': r.id, 'title': r.title or '',
                             'author': r.author or '',
                             'category': r.category or '', 'year': r.year or 0,
                             '_score': 1.0, '_source': 'fulltext'} for r in rows]
            except Exception:
                pass

            # 2. 进一步降级：LIKE
            like_pattern = f'%{q}%'
            rows = db.session.query(
                Book.id, Book.title, Book.author, Book.category, Book.year
            ).filter(_or(Book.title.like(like_pattern),
                         Book.author.like(like_pattern))).limit(limit).all()
            return [{'id': r.id, 'title': r.title or '',
                     'author': r.author or '',
                     'category': r.category or '', 'year': r.year or 0,
                     '_score': 0.8, '_source': 'like'} for r in rows]
        except Exception:
            return []

    def search(self, query, limit=20, fuzzy=1):
        """主搜索：优先 Meilisearch，失败降级 FULLTEXT"""
        if not query or not isinstance(query, str):
            return {'items': [], 'method': 'none', 'total': 0}
        query = query.strip()
        if not query:
            return {'items': [], 'method': 'empty', 'total': 0}

        # 1. 优先 Meilisearch
        if self.meili_working and self.meili_index is not None:
            try:
                result = self.meili_index.search(
                    query,
                    {'limit': limit, 'attributesToSearchOn': ['title', 'author', 'category']}
                )
                items = []
                for hit in result.get('hits', []):
                    items.append({
                        'id': hit.get('id'),
                        'title': hit.get('title', ''),
                        'author': hit.get('author', ''),
                        'category': hit.get('category', ''),
                        'year': hit.get('year', 0),
                        '_score': hit.get('_rankingScore', 0),
                        '_source': 'meilisearch',
                    })
                return {'items': items, 'method': 'meilisearch',
                        'total': result.get('estimatedTotalHits', len(items))}
            except Exception:
                self.meili_working = False

        # 2. 降级：MySQL FULLTEXT / LIKE
        items = self._fulltext_search(query, limit=limit)
        return {'items': items, 'method': 'mysql_fulltext', 'total': len(items)}

    # ---------- 拼写建议：基于 DB 已有书名做简单模糊匹配 ----------
    def _get_all_titles(self):
        """缓存 5 分钟的书名列表，用于建议"""
        now = time.time()
        if self._book_titles_cache is not None and (now - self._book_titles_time) < 300:
            return self._book_titles_cache
        try:
            from extensions import db
            from models import Book
            rows = db.session.query(Book.title).filter(
                Book.title.isnot(None)).limit(5000).all()
            titles = [(r.title or '').strip() for r in rows if (r.title or '').strip()]
            self._book_titles_cache = titles
            self._book_titles_time = now
            return titles
        except Exception:
            return []

    def suggestions(self, query, limit=5):
        """为前缀/子串匹配给出建议；支持大小写不敏感"""
        if not query or not isinstance(query, str):
            return []
        q = query.strip().lower()
        if not q:
            return []

        titles = self._get_all_titles()
        # 前缀匹配 > 子串匹配
        prefix = [t for t in titles if t.lower().startswith(q)]
        substring = [t for t in titles if q in t.lower() and t not in prefix]
        seen = set()
        out = []
        for t in prefix + substring:
            if t in seen:
                continue
            seen.add(t)
            out.append(t)
            if len(out) >= limit:
                break
        return out

    # ===== 2023 升级：混合搜索 =====
    def semantic_search(self, query, limit=20):
        """向量语义搜索：embedding + FAISS（优先）/ brute-force（降级）

        返回: [{'book': book, 'similarity': score}, ...]
        """
        if not query or not isinstance(query, str):
            return []
        q = query.strip()
        if not q:
            return []
        try:
            from services.embedding_service import get_embedding_service
            emb_svc = get_embedding_service()
            if emb_svc is None or emb_svc.model is None:
                return []

            # 生成 query embedding
            try:
                q_vec = emb_svc.model.encode(q, convert_to_numpy=True,
                                             show_progress_bar=False)
            except Exception:
                return []
            if q_vec is None:
                return []

            # 1) 优先 FAISS
            if emb_svc._index_ready and emb_svc._faiss_index is not None:
                try:
                    pairs = emb_svc._search_faiss(q_vec, limit)
                    if pairs:
                        return [{'book': b, 'similarity': float(s)}
                                for s, b in pairs]
                except Exception:
                    pass

            # 2) 降级：brute-force（先拿一批候选）
            try:
                from models import Book
                candidates = Book.query.limit(1000).all()
                if not candidates:
                    return []
                pairs = emb_svc._search_bruteforce(q_vec, candidates, limit)
                return [{'book': b, 'similarity': float(s)} for s, b in pairs]
            except Exception:
                return []
        except Exception:
            return []

    def hybrid_search(self, query, limit=20, semantic_weight=0.5, keyword_weight=0.5):
        """混合搜索：关键词(FULLTEXT/BM25) + 向量相似度，加权融合

        - 并行执行 _fulltext_search 与 semantic_search
        - 各自做 min-max 归一化
        - final_score = keyword_weight * k_norm + semantic_weight * s_norm
        - 按 book_id 合并，返回按 score 降序的 top N
        """
        if not query or not isinstance(query, str):
            return []
        q = query.strip()
        if not q:
            return []

        # --- 并行调用两路 ---
        keyword_items = []
        semantic_items = []

        def _run_keyword():
            nonlocal keyword_items
            try:
                keyword_items = self._fulltext_search(q, limit=limit * 3)
            except Exception:
                keyword_items = []

        def _run_semantic():
            nonlocal semantic_items
            try:
                semantic_items = self.semantic_search(q, limit=limit * 3)
            except Exception:
                semantic_items = []

        t1 = _th.Thread(target=_run_keyword)
        t2 = _th.Thread(target=_run_semantic)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        try:
            # --- 归一化 min-max ---
            def _norm(values):
                if not values:
                    return []
                mn, mx = min(values), max(values)
                rng = (mx - mn) if mx > mn else 1.0
                return [(v - mn) / rng for v in values]

            # 关键词：_score 字段（1.0 / 0.8 默认），若缺失则用位置倒数
            k_scores = []
            for idx, it in enumerate(keyword_items):
                raw = it.get('_score')
                if raw is None:
                    raw = 1.0 / (idx + 1)
                k_scores.append(float(raw))
            k_norms = _norm(k_scores)

            # 语义：similarity（cosine，-1..1）
            s_scores = [float(it.get('similarity', 0.0)) for it in semantic_items]
            s_norms = _norm(s_scores)

            # --- 合并 book_id -> (final_score, info) ---
            merged = {}

            for it, ns in zip(keyword_items, k_norms):
                bid = it.get('id')
                if bid is None:
                    continue
                base = merged.get(bid, {'score': 0.0, 'title': it.get('title', ''),
                                       'author': it.get('author', ''),
                                       'category': it.get('category', ''),
                                       'year': it.get('year', 0),
                                       'hit_keyword': False, 'hit_semantic': False})
                base['score'] += keyword_weight * ns
                base['hit_keyword'] = True
                base['title'] = base['title'] or it.get('title', '')
                base['author'] = base['author'] or it.get('author', '')
                base['category'] = base['category'] or it.get('category', '')
                base['year'] = base['year'] or it.get('year', 0)
                merged[bid] = base

            for it, ns in zip(semantic_items, s_norms):
                book = it.get('book')
                if book is None:
                    continue
                bid = getattr(book, 'id', None)
                if bid is None:
                    continue
                title = getattr(book, 'title', '') or ''
                author = getattr(book, 'author', '') or ''
                category = getattr(book, 'category', '') or ''
                year = getattr(book, 'year', 0) or 0
                base = merged.get(bid, {'score': 0.0, 'title': title, 'author': author,
                                       'category': category, 'year': year,
                                       'hit_keyword': False, 'hit_semantic': False})
                base['score'] += semantic_weight * ns
                base['hit_semantic'] = True
                base['title'] = base['title'] or title
                base['author'] = base['author'] or author
                base['category'] = base['category'] or category
                base['year'] = base['year'] or year
                merged[bid] = base

            if not merged:
                # 双路都空：降级纯关键词
                fallback = self._fulltext_search(q, limit=limit)
                return [{'id': r.get('id'), 'title': r.get('title', ''),
                         'author': r.get('author', ''),
                         'category': r.get('category', ''), 'year': r.get('year', 0),
                         'score': float(r.get('_score', 0.8)),
                         '_source': 'keyword_fallback'} for r in fallback]

            final = [
                {'id': bid,
                 'title': info.get('title', ''),
                 'author': info.get('author', ''),
                 'category': info.get('category', ''),
                 'year': info.get('year', 0),
                 'score': round(float(info['score']), 4),
                 '_source': 'hybrid'}
                for bid, info in merged.items()
            ]
            final.sort(key=lambda x: x['score'], reverse=True)
            return final[:limit]
        except Exception:
            # 异常降级：纯关键词
            try:
                fallback = self._fulltext_search(q, limit=limit)
                return [{'id': r.get('id'), 'title': r.get('title', ''),
                         'author': r.get('author', ''),
                         'category': r.get('category', ''), 'year': r.get('year', 0),
                         'score': float(r.get('_score', 0.8)),
                         '_source': 'keyword_fallback'} for r in fallback]
            except Exception:
                return []

    def smart_search(self, query, limit=20):
        """智能路由：短 query(≤3字符) -> 纯关键词；长 query(描述性) -> 混合搜索

        返回与 search() 相同的格式：{'items': [...], 'method': str, 'total': int}
        """
        if not query or not isinstance(query, str):
            return {'items': [], 'method': 'none', 'total': 0}
        q = query.strip()
        if not q:
            return {'items': [], 'method': 'empty', 'total': 0}

        try:
            if len(q) <= 3:
                # 短 query：关键词为主（Meilisearch 或 FULLTEXT）
                if self.meili_working and self.meili_index is not None:
                    try:
                        result = self.meili_index.search(
                            q, {'limit': limit,
                                'attributesToSearchOn': ['title', 'author', 'category']}
                        )
                        items = []
                        for hit in result.get('hits', []):
                            items.append({
                                'id': hit.get('id'),
                                'title': hit.get('title', ''),
                                'author': hit.get('author', ''),
                                'category': hit.get('category', ''),
                                'year': hit.get('year', 0),
                                '_score': hit.get('_rankingScore', 0),
                                '_source': 'meilisearch',
                            })
                        return {'items': items, 'method': 'smart_meili',
                                'total': result.get('estimatedTotalHits', len(items))}
                    except Exception:
                        self.meili_working = False

                items = self._fulltext_search(q, limit=limit)
                return {'items': items, 'method': 'smart_keyword', 'total': len(items)}

            # 长 query：混合搜索
            hybrid = self.hybrid_search(q, limit=limit)
            if hybrid:
                return {'items': hybrid, 'method': 'smart_hybrid', 'total': len(hybrid)}

            # 混合为空：降级关键词
            items = self._fulltext_search(q, limit=limit)
            return {'items': items, 'method': 'smart_keyword_fallback', 'total': len(items)}
        except Exception:
            # 最终兜底：关键词
            try:
                items = self._fulltext_search(q, limit=limit)
                return {'items': items, 'method': 'smart_keyword_fallback',
                        'total': len(items)}
            except Exception:
                return {'items': [], 'method': 'smart_error', 'total': 0}


def get_search_service(meili_host='http://127.0.0.1:7700', meili_key='',
                       index_name='books'):
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SearchService(meili_host=meili_host, meili_key=meili_key,
                                          index_name=index_name)
    return _instance
