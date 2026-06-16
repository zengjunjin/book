"""
语义召回服务 - 基于 BERT/Embedding 的书籍语义相似度计算
使用 sentence-transformers 的 paraphrase-multilingual-MiniLM-L12-v2 模型

2023 升级：FAISS IndexFlatIP ANN 索引
  - 14 万书从 O(n)=~2s 降到 O(1)=~5ms
  - Inner Product = L2归一化后的 Cosine Similarity
"""
import os
import pickle
import numpy as np
import threading

# ========== FAISS 配置 ==========
FAISS_INDEX_TYPE = 'FlatIP'   # 'FlatIP'=精确召回,'IVF'=近似召回(更快)
FAISS_NPROBE = 10             # IVF 时 nprobe（FlatIP 忽略）
FAISS_NORMALIZE = True        # 是否将向量归一化为单位长度（使 IP=CosineSim）
BATCH_SIZE = 64
EMBEDDING_DIM = 384            # paraphrase-multilingual-MiniLM-L12-v2 的输出维度
# Ollama embedding 模型（本地，无需网络）
OLLAMA_EMBED_MODEL = 'nomic-embed-text'    # 768维，专为语义相似度优化（推荐，274MB）
OLLAMA_EMBED_V2_MODEL = 'mxbai-embed-large'  # 768维，高质量（备选，669MB）
OLLAMA_EMBED_FALLBACK_MODEL = 'qwen2.5:1.5b'  # 1536维，已安装
OLLAMA_HOST = 'http://localhost:11434'
# TF-IDF fallback: 当 sentence-transformers + Ollama 都不可用时使用
TFIDF_MAX_FEATURES = 20000    # 词表大小
TFIDF_NGRAM_RANGE = (1, 2)    # unigrams + bigrams

# ========== 索引持久化路径 ==========
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_INDEX_PATH = os.path.join(_BASE_DIR, 'data', 'faiss.bin')
DEFAULT_META_PATH = os.path.join(_BASE_DIR, 'data', 'faiss_meta.pkl')

# ========== 模型配置 ==========
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
MAX_SEQ_LENGTH = 128

# 尝试设置离线模式
try:
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_HUB_OFFLINE'] = '1'
except Exception:
    pass


class EmbeddingService:
    """书籍语义 Embedding 服务（支持 FAISS ANN 索引）"""

    def __init__(self):
        self.model = None
        self.device = None
        # --- Ollama embedding（优先级最高，优先尝试）---
        self._ollama_client = None
        self._ollama_model = None
        self._ollama_dimension = 0
        self._use_ollama = False
        # --- TF-IDF fallback ---
        self._tfidf_vectorizer = None
        self._pca = None
        self._use_fallback = False
        self._fallback_dim = EMBEDDING_DIM
        # --- 原始缓存 ---
        self.book_embeddings = {}
        # --- FAISS 索引 ---
        self._faiss_index = None
        self._id_to_book = {}
        self._book_to_fid = {}
        self._next_fid = 0
        self._index_ready = False
        # 锁
        self._embedding_lock = threading.Lock()
        self._index_lock = threading.Lock()
        self._initialized = False
        # 预暖/构建状态
        self._prewarm_done = False
        self._building = False
        self._build_message = ''
        self._flask_app = None

    def _get_device(self):
        try:
            import torch
            if torch.cuda.is_available():
                return 'cuda'
        except Exception:
            pass
        return 'cpu'

    def _load_model(self):
        if self._initialized:
            return
        print('  [Embedding] 正在加载模型...')
        self.device = self._get_device()
        print(f'  [Embedding] 使用设备: {self.device}')

        # 策略 1: Ollama embedding（优先级：nomic > mxbai > qwen2.5）
        for ollama_model in [OLLAMA_EMBED_MODEL, OLLAMA_EMBED_V2_MODEL, OLLAMA_EMBED_FALLBACK_MODEL]:
            try:
                import requests
                r = requests.post(
                    f'{OLLAMA_HOST}/api/embeddings',
                    json={'model': ollama_model, 'prompt': 'test'},
                    timeout=15,
                )
                if r.status_code == 200:
                    vec = r.json().get('embedding', [])
                    if vec:
                        self._ollama_model = ollama_model
                        self._ollama_dimension = len(vec)
                        self._use_ollama = True
                        self._use_fallback = False
                        self._initialized = True
                        print(f'  [Embedding] Ollama embedding 就绪: model={ollama_model}, dim={self._ollama_dimension}')
                        return
            except Exception as e:
                print(f'  [Embedding] Ollama model={ollama_model} 失败: {e}')

        # 策略 2: sentence-transformers（需要网络下载）
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(
                MODEL_NAME,
                device=self.device,
                cache_folder=os.path.join(os.path.dirname(__file__), '.cache'),
            )
            self.model.max_seq_length = MAX_SEQ_LENGTH
            print(f'  [Embedding] sentence-transformers 就绪: {MODEL_NAME}')
            self._initialized = True
            self._use_fallback = False
            self._use_ollama = False
            return
        except Exception as e:
            print(f'  [Embedding] sentence-transformers 失败: {e}')
            self.model = None

        # 策略 3: TF-IDF + TruncatedSVD（纯本地，无网络依赖）
        print('  [Embedding] fallback -> TF-IDF + TruncatedSVD ...')
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._tfidf_vectorizer = TfidfVectorizer(
                max_features=TFIDF_MAX_FEATURES,
                ngram_range=TFIDF_NGRAM_RANGE,
                lowercase=True,
                sublinear_tf=True,
                dtype=np.float32,
            )
            self._pca = None
            self._use_fallback = True
            self._use_ollama = False
            self._initialized = True
            print(f'  [Embedding] TF-IDF fallback 就绪 (max_features={TFIDF_MAX_FEATURES}, dim={EMBEDDING_DIM})')
        except Exception as e:
            print(f'  [Embedding] fallback 也失败: {e}')
            self._use_fallback = False
            self._use_ollama = False

    # ========== FAISS 索引构建 ==========
    def _normalize(self, vectors):
        """L2 归一化（使 dot(a,b)=cosine_similarity）"""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

    def _encode_batch(self, texts):
        """统一编码入口：Ollama（最快）> sentence-transformers > TF-IDF"""
        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)

        # 策略 1: Ollama embedding（本地 HTTP API）
        if self._use_ollama:
            try:
                import requests
                vectors = []
                for text in texts:
                    r = requests.post(
                        f'{OLLAMA_HOST}/api/embeddings',
                        json={'model': self._ollama_model, 'prompt': text},
                        timeout=30,
                    )
                    if r.status_code == 200:
                        vec = r.json().get('embedding', [])
                        if vec:
                            vectors.append(np.array(vec, dtype=np.float32))
                        else:
                            vectors.append(np.zeros(self._ollama_dimension, dtype=np.float32))
                    else:
                        vectors.append(np.zeros(self._ollama_dimension, dtype=np.float32))
                result = np.array(vectors, dtype=np.float32)
                return self._normalize(result)
            except Exception as e:
                print(f'  [Embedding] Ollama encode 失败: {e}，降级到下一策略')

        # 策略 2: TF-IDF + TruncatedSVD
        if self._use_fallback and self._tfidf_vectorizer is not None:
            try:
                from sklearn.decomposition import TruncatedSVD
                if not hasattr(self._tfidf_vectorizer, 'idf_') or self._tfidf_vectorizer.idf_ is None:
                    tfidf = self._tfidf_vectorizer.fit_transform(texts)
                    print(f'  [Embedding] TF-IDF fit: vocab_size={len(self._tfidf_vectorizer.vocabulary_)}')
                    n_comp = min(EMBEDDING_DIM, tfidf.shape[1], tfidf.shape[0])
                    n_comp = max(16, n_comp)
                    svd = TruncatedSVD(n_components=n_comp, random_state=42)
                    dense = svd.fit_transform(tfidf).astype(np.float32)
                    out = np.zeros((dense.shape[0], EMBEDDING_DIM), dtype=np.float32)
                    out[:, :n_comp] = dense
                    self._fallback_dim = n_comp
                    self._pca = svd
                    print(f'  [Embedding] PCA fit: dim={n_comp}, output={EMBEDDING_DIM}')
                    return self._normalize(out)
                tfidf = self._tfidf_vectorizer.transform(texts)
                dense = self._pca.transform(tfidf).astype(np.float32)
                out = np.zeros((dense.shape[0], EMBEDDING_DIM), dtype=np.float32)
                fd = min(self._fallback_dim, dense.shape[1])
                out[:, :fd] = dense[:, :fd]
                return self._normalize(out)
            except Exception as e:
                print(f'  [Embedding] _encode_batch fallback 失败: {e}')
                vecs = np.random.randn(len(texts), EMBEDDING_DIM).astype(np.float32)
                return self._normalize(vecs)

        # 策略 3: sentence-transformers
        if self.model is not None:
            try:
                vecs = self.model.encode(texts, batch_size=BATCH_SIZE,
                                         convert_to_numpy=True, show_progress_bar=False)
                return self._normalize(np.asarray(vecs, dtype=np.float32))
            except Exception as e:
                print(f'  [Embedding] sentence-transformers encode 失败: {e}')

        # 兜底
        return self._normalize(np.random.randn(len(texts), EMBEDDING_DIM).astype(np.float32))

    def _effective_dim(self):
        """获取当前编码策略的实际向量维度"""
        if self._use_ollama and self._ollama_dimension > 0:
            return self._ollama_dimension
        if self.model is not None:
            try:
                return self.model.get_sentence_embedding_dimension()
            except Exception:
                pass
        return EMBEDDING_DIM

    def _build_faiss_index(self, books, batch_size=64):
        """为一批书籍构建 FAISS 索引。统一调用 _encode_batch。"""
        if not books:
            return
        if not self._initialized:
            self._load_model()
        if self.model is None and not self._use_fallback and not self._use_ollama:
            print('  [Embedding FAISS] 无可用编码器，跳过索引构建')
            return

        dim = self._effective_dim()
        print(f'  [Embedding FAISS] 正在构建索引，{len(books)} 本书，向量维度={dim}...')
        texts = [self._get_book_text(b) for b in books]

        try:
            import faiss
            has_faiss = True
        except ImportError:
            print('  [Embedding FAISS] faiss 未安装')
            has_faiss = False
            self._index_ready = False

        if has_faiss:
            with self._index_lock:
                if self._faiss_index is None:
                    self._faiss_index = faiss.IndexFlatIP(dim)
                    self._next_fid = 0
                    print(f'  [Embedding FAISS] 创建 IndexFlatIP(dim={dim})')

                total = len(texts)
                for i in range(0, total, batch_size):
                    batch_texts = texts[i:i + batch_size]
                    batch_books = books[i:i + batch_size]
                    vecs = self._encode_batch(batch_texts)
                    if vecs is None or len(vecs) == 0:
                        continue
                    vecs = np.asarray(vecs, dtype=np.float32)
                    # Ollama 维度可能与索引维度不一致，做截断/补零
                    if vecs.shape[1] != dim:
                        if vecs.shape[1] > dim:
                            vecs = vecs[:, :dim]
                        else:
                            pad = np.zeros((vecs.shape[0], dim - vecs.shape[1]), dtype=np.float32)
                            vecs = np.hstack([vecs, pad])

                    for book, vec in zip(batch_books, vecs):
                        fid = self._next_fid
                        self._next_fid += 1
                        self._id_to_book[fid] = book
                        self._book_to_fid[book.id] = fid

                    self._faiss_index.add(vecs)

                self._index_ready = True
                print(f'  [Embedding FAISS] 索引构建完成，当前 {self._faiss_index.ntotal} 条向量，维度={dim}')

        # --- 同时保留原始缓存（fallback 用）---
        try:
            emb_map = self.get_book_embeddings_batch(books)
            with self._embedding_lock:
                for bid, emb in emb_map.items():
                    self.book_embeddings[bid] = emb
        except Exception:
            pass

    def _ensure_index(self, min_books=0):
        """确保 FAISS 索引已构建（如未构建则触发全量构建）"""
        if self._index_ready:
            return True
        if self.model is None and not self._use_fallback:
            return False
        try:
            from models import Book
            from extensions import db
            all_books = Book.query.order_by(Book.id).all()
            if len(all_books) < min_books and min_books > 0:
                return False
            if all_books:
                self._build_faiss_index(all_books)
                return self._index_ready
        except Exception as e:
            print(f'  [Embedding FAISS] 索引构建失败: {e}')
        return False

    def build_index_from_db(self, limit=None):
        """显式从数据库全量构建索引（修复 app context 兼容后台线程）"""
        try:
            # 尝试在 app context 中查询
            try:
                from models import Book
                q = Book.query.order_by(Book.id)
                if limit:
                    q = q.limit(limit)
                books = q.all()
            except Exception as ctx_err:
                # 可能是 "working outside of application context"——尝试通过保存的 app
                if self._flask_app is not None:
                    with self._flask_app.app_context():
                        from models import Book
                        q = Book.query.order_by(Book.id)
                        if limit:
                            q = q.limit(limit)
                        books = q.all()
                else:
                    raise ctx_err

            if books:
                self._build_faiss_index(books)
                return len(books)
        except Exception as e:
            print(f'  [Embedding FAISS] build_index_from_db 失败: {e}')
        return 0

    def _get_book_text(self, book):
        parts = []
        if getattr(book, 'title', None):
            parts.append(str(book.title))
        if getattr(book, 'author', None):
            parts.append('by ' + str(book.author))
        if getattr(book, 'category', None):
            parts.append('[' + str(book.category) + ']')
        if getattr(book, 'publisher', None):
            parts.append(str(book.publisher))
        desc = getattr(book, 'description', None) or getattr(book, 'summary', None)
        if desc:
            desc_str = str(desc)
            if len(desc_str) > 500:
                desc_str = desc_str[:500]
            parts.append(desc_str)
        if getattr(book, 'year', None):
            parts.append('(' + str(book.year) + ')')
        text = ' '.join(parts)
        if not text.strip():
            return str(getattr(book, 'title', '')) or 'book'
        return text

    def get_book_embedding(self, book):
        if self.model is None and not self._use_fallback:
            return None
        with self._embedding_lock:
            if book.id in self.book_embeddings:
                return self.book_embeddings[book.id]
        # 单本编码走统一路径
        vecs = self._encode_batch([self._get_book_text(book)])
        if vecs is None or len(vecs) == 0:
            return None
        emb = np.asarray(vecs[0], dtype=np.float32)
        with self._embedding_lock:
            self.book_embeddings[book.id] = emb
        return emb

    def get_book_embeddings_batch(self, books):
        if (self.model is None and not self._use_fallback) or not books:
            return {}
        texts = [self._get_book_text(b) for b in books]
        vecs = self._encode_batch(texts)
        result = {}
        if vecs is None or len(vecs) == 0:
            return result
        for book, emb in zip(books, vecs):
            result[book.id] = np.asarray(emb, dtype=np.float32)
            with self._embedding_lock:
                self.book_embeddings[book.id] = result[book.id]
        return result

    # ========== FAISS ANN 搜索（主路径，O(1) 复杂度）==========
    def _search_faiss(self, query_vector, top_k, exclude_id=None):
        """使用 FAISS 索引搜索（毫秒级）"""
        if not self._index_ready or self._faiss_index is None:
            return []

        try:
            import faiss
        except ImportError:
            return []

        q = np.array([query_vector], dtype=np.float32)
        if FAISS_NORMALIZE:
            q = self._normalize(q)

        k = min(top_k * 3, int(self._faiss_index.ntotal))  # 多取一些再过滤
        if k <= 0:
            return []

        distances, indices = self._faiss_index.search(q, k)

        results = []
        for dist, fid in zip(distances[0], indices[0]):
            if fid < 0:
                continue
            book = self._id_to_book.get(int(fid))
            if book is None:
                continue
            if exclude_id and book.id == exclude_id:
                continue
            # FAISS IndexFlatIP 本身就是 cosine similarity（已归一化）
            similarity = float(dist)
            results.append((similarity, book))
            if len(results) >= top_k:
                break
        return results

    # ========== Fallback：brute-force（FAISS 不可用时）==========
    def _search_bruteforce(self, query_vector, candidates, top_k, exclude_id=None):
        """Python 层的 brute-force 搜索（FAISS 降级路径）"""
        if self.model is None or not candidates:
            return []
        cand_embs = self.get_book_embeddings_batch(candidates)
        similarities = []
        for bid, emb in cand_embs.items():
            if exclude_id and bid == exclude_id:
                continue
            dot = float(np.dot(query_vector, emb))
            norm_q = float(np.linalg.norm(query_vector))
            norm_c = float(np.linalg.norm(emb))
            if norm_q > 0 and norm_c > 0:
                sim = dot / (norm_q * norm_c)
                similarities.append((sim, bid))
        similarities.sort(key=lambda x: x[0], reverse=True)
        id_to_book = {b.id: b for b in candidates}
        results = []
        for sim, bid in similarities[:top_k]:
            book = id_to_book.get(bid)
            if book:
                results.append((sim, book))
        return results

    # ========== 公开 API ==========
    def find_similar_books(self, book, candidates=None, top_k=10, threshold=0.3):
        """
        查找与给定书籍相似的书籍（优先 FAISS，fallback brute-force）

        Args:
            book: 参考书籍
            candidates: 候选书籍列表（FAISS 模式下可传 None 使用全量索引）
            top_k: 返回数量
            threshold: 相似度阈值

        Returns:
            [(similarity, book), ...] 按相似度降序
        """
        book_emb = self.get_book_embedding(book)
        if book_emb is None:
            return []

        # --- 优先：FAISS 全量索引搜索 ---
        if self._index_ready:
            results = self._search_faiss(book_emb, top_k, exclude_id=book.id)
            if results:
                return [(sim, b) for sim, b in results if sim >= threshold]

        # --- Fallback：候选列表 brute-force ---
        if candidates is None:
            try:
                from models import Book
                candidates = Book.query.filter(Book.id != book.id).limit(500).all()
            except Exception:
                return []
        return self._search_bruteforce(book_emb, candidates, top_k, exclude_id=book.id)

    def recommend_books(self, user_id, top_k=10, exclude_rated=True):
        """
        基于用户画像的书籍推荐（FAISS 加速）
        """
        if self.model is None and not self._use_fallback:
            return []

        try:
            from extensions import db
            from models import Book, Rating
            from sqlalchemy import func

            # 取用户高评分书籍
            rows = db.session.query(
                Rating.book_id, func.avg(Rating.rating).label('avg')
            ).filter(
                Rating.user_id == user_id
            ).group_by(Rating.book_id).order_by(
                func.avg(Rating.rating).desc()
            ).limit(3).all()

            liked_ids = [r[0] for r in rows]
            liked_books = Book.query.filter(Book.id.in_(liked_ids)).all() if liked_ids else []

            if not liked_books:
                return []

            # 用户兴趣向量 = 喜欢书籍的平均 embedding
            liked_embs = self.get_book_embeddings_batch(liked_books)
            if not liked_embs:
                return []

            liked_matrix = np.array(list(liked_embs.values()))
            user_emb = np.mean(liked_matrix, axis=0)

            # FAISS 搜索
            results = self._search_faiss(user_emb, top_k,
                                         exclude_id=None if not exclude_rated else None)

            # 过滤已评分书籍
            if exclude_rated:
                results = [(s, b) for s, b in results if b.id not in liked_ids]

            return [{'book_id': b.id, 'title': b.title, 'similarity': round(s, 3)}
                    for s, b in results[:top_k]]
        except Exception as e:
            print(f'  [Embedding] recommend_books 失败: {e}')
            return []

    def semantic_recall(self, user_profile_text, candidate_books=None, top_k=20, threshold=0.3):
        """
        基于用户兴趣描述的语义召回（FAISS 加速，支持 TF-IDF fallback）
        """
        if (self.model is None and not self._use_fallback) or not user_profile_text:
            return []
        user_emb = None
        if self.model is not None:
            user_emb = self.model.encode(user_profile_text,
                                          convert_to_numpy=True,
                                          show_progress_bar=False)
        elif self._use_fallback:
            vecs = self._encode_batch([user_profile_text])
            if vecs is not None and len(vecs) > 0:
                user_emb = np.asarray(vecs[0], dtype=np.float32).reshape(-1)
        if user_emb is None:
            return []

        # FAISS 全量搜索
        if self._index_ready:
            results = self._search_faiss(user_emb, top_k)
            return [{'book': b, 'similarity': s}
                    for s, b in results if s >= threshold]

        # fallback
        if candidate_books is None:
            try:
                from models import Book
                candidate_books = Book.query.limit(500).all()
            except Exception:
                return []
        return self._search_bruteforce(user_emb, candidate_books, top_k)

    def content_based_recall(self, user_liked_books, candidate_books=None, top_k=20):
        """
        基于用户已喜欢书籍的内容召回（FAISS 加速）
        """
        if not user_liked_books:
            return []
        liked_embs = self.get_book_embeddings_batch(user_liked_books)
        if not liked_embs:
            return []
        liked_matrix = np.array(list(liked_embs.values()))
        user_profile = np.mean(liked_matrix, axis=0)

        if self._index_ready:
            results = self._search_faiss(user_profile, top_k)
            return [{'book': b, 'score': s} for s, b in results]
        return self._search_bruteforce(user_profile, candidate_books or [], top_k)

    @property
    def index_size(self):
        """当前 FAISS 索引中的向量数量"""
        if self._faiss_index is not None:
            return int(self._faiss_index.ntotal)
        return 0

    @property
    def faiss_ready(self):
        return self._index_ready and self._faiss_index is not None

    # ========== 索引持久化：save_index / load_index ==========
    def save_index(self, path=None):
        """保存 FAISS 索引 + id_to_book 映射到磁盘
        Args:
            path: faiss.bin 路径，默认 backend/data/faiss.bin
        Returns:
            True 成功，False 失败（有 try/except 降级）
        """
        if self._faiss_index is None:
            print('  [Embedding] save_index: 索引为空，跳过保存')
            return False

        index_path = path or DEFAULT_INDEX_PATH
        meta_path = index_path + '.pkl' if not path else (
            os.path.splitext(index_path)[0] + '.pkl'
        ) if path.endswith('.bin') else index_path + '.pkl'
        if path is None:
            meta_path = DEFAULT_META_PATH

        try:
            data_dir = os.path.dirname(index_path)
            if data_dir and not os.path.isdir(data_dir):
                os.makedirs(data_dir, exist_ok=True)
        except Exception as e:
            print(f'  [Embedding] save_index: 无法创建目录 {e}')
            return False

        try:
            import faiss
            with self._index_lock:
                faiss.write_index(self._faiss_index, index_path)
            print(f'  [Embedding] 索引已保存: {index_path} (ntotal={self._faiss_index.ntotal})')
        except Exception as e:
            print(f'  [Embedding] save_index: 保存 faiss 索引失败 {e}')
            return False

        try:
            # 只保存必要的元数据：id -> (book.id, title, author, category, publisher, year)
            meta = {
                'id_to_book_slim': {
                    int(k): {
                        'id': getattr(v, 'id', None),
                        'title': getattr(v, 'title', None),
                        'author': getattr(v, 'author', None),
                        'category': getattr(v, 'category', None),
                        'publisher': getattr(v, 'publisher', None),
                        'year': getattr(v, 'year', None),
                    }
                    for k, v in self._id_to_book.items()
                },
                'next_fid': self._next_fid,
                'ntotal': int(self._faiss_index.ntotal) if self._faiss_index is not None else 0,
            }
            with open(meta_path, 'wb') as f:
                pickle.dump(meta, f, protocol=pickle.HIGHEST_PROTOCOL)
            print(f'  [Embedding] 元数据已保存: {meta_path}')
            return True
        except Exception as e:
            print(f'  [Embedding] save_index: 保存元数据失败 {e}')
            return False

    def load_index(self, path=None):
        """从磁盘加载 FAISS 索引 + id_to_book 映射
        Returns:
            True 成功，False 失败
        """
        index_path = path or DEFAULT_INDEX_PATH
        meta_path = DEFAULT_META_PATH if path is None else (
            os.path.splitext(index_path)[0] + '.pkl'
        )

        if not os.path.isfile(index_path):
            print(f'  [Embedding] load_index: 索引文件不存在 {index_path}')
            return False

        try:
            import faiss
            with self._index_lock:
                self._faiss_index = faiss.read_index(index_path)
            print(f'  [Embedding] 索引已加载: {index_path} (ntotal={self._faiss_index.ntotal})')
        except Exception as e:
            print(f'  [Embedding] load_index: 加载 faiss 索引失败 {e}')
            self._faiss_index = None
            return False

        # 加载元数据（id_to_book 映射）
        id_to_book = {}
        book_to_fid = {}
        next_fid = 0
        try:
            if os.path.isfile(meta_path):
                with open(meta_path, 'rb') as f:
                    meta = pickle.load(f)
                slim = meta.get('id_to_book_slim', {})

                class _BookSlim:
                    """轻量 book 对象：有 to_dict()，可兼容现有流程"""
                    def __init__(self, d):
                        self.id = d.get('id')
                        self.title = d.get('title')
                        self.author = d.get('author')
                        self.category = d.get('category')
                        self.publisher = d.get('publisher')
                        self.year = d.get('year')

                    def to_dict(self):
                        return {
                            'id': self.id, 'title': self.title,
                            'author': self.author, 'category': self.category,
                            'publisher': self.publisher, 'year': self.year,
                        }

                for fid, info in slim.items():
                    book = _BookSlim(info)
                    id_to_book[int(fid)] = book
                    if book.id is not None:
                        book_to_fid[book.id] = int(fid)
                    if int(fid) >= next_fid:
                        next_fid = int(fid) + 1
                next_fid = max(next_fid, int(meta.get('next_fid', next_fid)))
                print(f'  [Embedding] 元数据已加载: {len(id_to_book)} 条映射')
            else:
                print(f'  [Embedding] 元数据文件不存在 {meta_path}，尝试从 DB 还原映射')
                try:
                    from models import Book
                    total_books = Book.query.count()
                    # 如书籍数量与 ntotal 相近，则按 id 顺序重建映射
                    if total_books <= int(self._faiss_index.ntotal) + 64:
                        books = Book.query.order_by(Book.id).limit(
                            int(self._faiss_index.ntotal) + 1
                        ).all()
                        for i, book in enumerate(books):
                            id_to_book[i] = book
                            book_to_fid[book.id] = i
                        next_fid = len(id_to_book)
                        print(f'  [Embedding] 通过 DB 重建映射: {len(id_to_book)} 条')
                except Exception as e2:
                    print(f'  [Embedding] DB 重建映射失败 {e2}')
        except Exception as e:
            print(f'  [Embedding] load_index: 加载元数据失败 {e}')

        with self._index_lock:
            self._id_to_book = id_to_book
            self._book_to_fid = book_to_fid
            self._next_fid = next_fid
            self._index_ready = self._faiss_index is not None and len(id_to_book) > 0

        if self._index_ready:
            print(f'  [Embedding] 索引准备就绪，共 {self.index_size} 条向量')
        return self._index_ready

    # ========== 预暖（后台线程）==========
    def prewarm(self, min_books=1000, use_thread=True):
        """预暖索引：先尝试从磁盘加载，失败则从 DB 构建并保存
        Args:
            min_books: 至少需要的书籍数量阈值（仅做日志参考）
            use_thread: 是否在后台线程运行
        """
        def _run():
            try:
                self._building = True
                self._build_message = 'loading index from disk'
                print(f'  [Embedding] prewarm: 尝试加载现有索引...')
                if self.load_index():
                    # 验证：若索引里的条目数 >= min_books，则视为成功
                    if self.index_size >= 1:
                        self._build_message = f'loaded {self.index_size} books from disk'
                        self._prewarm_done = True
                        self._building = False
                        return
                    print('  [Embedding] prewarm: 磁盘索引过小，从 DB 重建')

                self._build_message = 'building index from database'
                print(f'  [Embedding] prewarm: 从 DB 构建索引 (limit=5000)')
                # 确保模型已加载
                if self.model is None:
                    self._load_model()
                n = self.build_index_from_db(limit=5000)
                if n > 0:
                    self._build_message = 'saving index to disk'
                    self.save_index()
                    self._build_message = f'built {self.index_size} books and saved'
                else:
                    self._build_message = 'build failed (no books / model missing)'
            except Exception as e:
                self._build_message = f'error: {e}'
                print(f'  [Embedding] prewarm: 异常 {e}')
            finally:
                self._building = False
                self._prewarm_done = True

        if use_thread:
            t = threading.Thread(target=_run, name='embedding-prewarm', daemon=True)
            t.start()
            print('  [Embedding] prewarm: 后台线程已启动')
        else:
            _run()

    # ========== 基于文本的查询编码 ==========
    def encode_query(self, text):
        """对查询文本编码并归一化（支持 Ollama / TF-IDF fallback）"""
        if not text or not isinstance(text, str):
            return None
        if self.model is None and not self._use_fallback and not self._use_ollama:
            return None
        try:
            if self._use_ollama:
                import requests
                r = requests.post(
                    f'{OLLAMA_HOST}/api/embeddings',
                    json={'model': self._ollama_model, 'prompt': text.strip()},
                    timeout=30,
                )
                if r.status_code == 200:
                    vec = r.json().get('embedding', [])
                    if vec:
                        v = np.asarray(vec, dtype=np.float32)
                        norm = float(np.linalg.norm(v))
                        if norm > 0:
                            v = v / norm
                        return v
            if self.model is not None:
                vec = self.model.encode(text.strip(), convert_to_numpy=True,
                                        show_progress_bar=False)
                vec = np.asarray(vec, dtype=np.float32).reshape(-1)
                norm = float(np.linalg.norm(vec))
                if norm > 0:
                    vec = vec / norm
                return vec
            if self._use_fallback and self._tfidf_vectorizer is not None:
                batch = self._encode_batch([text.strip()])
                if batch is not None and len(batch) > 0:
                    return np.asarray(batch[0], dtype=np.float32).reshape(-1)
        except Exception as e:
            print(f'  [Embedding] encode_query: 失败 {e}')
        return None

    # ========== 基于文本的语义搜索 ==========
    def find_similar_books_by_text(self, query, top_k=10, threshold=0.3):
        """对自然语言查询做语义搜索
        Args:
            query: 查询字符串
            top_k: 返回数量
            threshold: 相似度阈值 (0~1)
        Returns:
            [{'book_id': int, 'title': str, 'author': str, 'similarity': float}, ...]
            索引不可用时返回 []
        """
        if not query:
            return []
        if top_k is None or top_k < 1:
            top_k = 10
        if threshold is None or threshold < 0:
            threshold = 0.0

        vec = self.encode_query(query)
        if vec is None:
            return []

        # 优先走 FAISS 主路径
        if self._index_ready and self._faiss_index is not None:
            try:
                raw = self._search_faiss(vec, top_k * 2)
                out = []
                for sim, book in raw:
                    if sim is None or sim < threshold:
                        continue
                    out.append({
                        'book_id': int(getattr(book, 'id', 0)),
                        'title': getattr(book, 'title', ''),
                        'author': getattr(book, 'author', ''),
                        'similarity': round(float(sim), 4),
                        'method': 'faiss',
                    })
                    if len(out) >= top_k:
                        break
                return out
            except Exception as e:
                print(f'  [Embedding] find_similar_books_by_text: faiss 失败 {e}')

        # fallback：没有索引的情况下返回空
        return []

    # ========== 状态属性 ==========
    @property
    def status(self):
        try:
            n_books = 0
            try:
                from models import Book
                n_books = int(Book.query.count())
            except Exception:
                n_books = 0
            return {
                'model_loaded': self.model is not None,
                'use_ollama': bool(self._use_ollama),
                'ollama_model': self._ollama_model or None,
                'ollama_dimension': self._ollama_dimension,
                'use_fallback': bool(self._use_fallback),
                'index_ready': bool(self._index_ready and self._faiss_index is not None),
                'effective_dimension': self._effective_dim(),
                'n_books': n_books,
                'index_size': int(self._faiss_index.ntotal) if self._faiss_index is not None else 0,
                'building': bool(self._building),
                'build_message': str(self._build_message or ''),
                'embedding_cache_size': len(self.book_embeddings),
            }
        except Exception as e:
            return {
                'model_loaded': False,
                'use_ollama': False,
                'ollama_model': None,
                'use_fallback': False,
                'index_ready': False,
                'effective_dimension': EMBEDDING_DIM,
                'n_books': 0,
                'index_size': 0,
                'building': False,
                'build_message': f'status error: {e}',
                'embedding_cache_size': len(self.book_embeddings),
            }


# ========== 全局单例 ==========
_embedding_service = None
_init_lock = threading.Lock()


def get_embedding_service(app=None):
    """获取 Embedding 服务单例（加载模型 + 后台 prewarm 索引）

    Args:
        app: Flask app 引用（可选），用于后台线程的 DB 查询
    """
    global _embedding_service
    try:
        if _embedding_service is None:
            with _init_lock:
                if _embedding_service is None:
                    svc = EmbeddingService()
                    # 保存 flask app 引用，用于后台线程的 DB 查询
                    if app is not None:
                        svc._flask_app = app
                    else:
                        try:
                            from flask import current_app
                            svc._flask_app = current_app._get_current_object()
                        except Exception:
                            svc._flask_app = None
                    svc._load_model()
                    # 后台线程预暖索引
                    try:
                        svc.prewarm(min_books=1000, use_thread=True)
                    except Exception as e:
                        print(f'  [Embedding] 单例 prewarm 失败: {e}')
                    _embedding_service = svc
        # 已有实例时更新 app 引用（如果传入）
        elif app is not None and _embedding_service._flask_app is None:
            _embedding_service._flask_app = app
    except Exception as e:
        print(f'  [Embedding] 单例初始化异常: {e}')
        if _embedding_service is None:
            _embedding_service = EmbeddingService()
    return _embedding_service


def get_embedding():
    """别名，兼容 recommend.py 中的调用方式"""
    return get_embedding_service()