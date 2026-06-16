# -*- coding: utf-8 -*-
"""
使用 Ollama embedding 构建 FAISS 向量索引
（完全本地，无需网络，速度快，质量高）
Usage: python scripts/build_faiss.py --limit=15000
"""
import sys
import os
import argparse
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

parser = argparse.ArgumentParser(description='Build FAISS index with Ollama embedding')
parser.add_argument('--limit', type=int, default=15000, help='max books to index')
args = parser.parse_args()

print('=' * 70)
print(f'Ollama FAISS 索引构建：最多 {args.limit} 本书')
print('=' * 70)

# 删除旧索引
idx_path = os.path.join(BASE_DIR, 'data', 'faiss.bin')
meta_path = os.path.join(BASE_DIR, 'data', 'faiss_meta.pkl')
for p in [idx_path, meta_path]:
    if os.path.isfile(p):
        try:
            os.remove(p)
            print(f'  删除旧文件: {os.path.basename(p)}')
        except Exception:
            pass

from app import create_app
app = create_app()
ctx = app.app_context()
ctx.push()

t0 = time.time()

# 创建 EmbeddingService（不走单例，避免启动后台 prewarm 冲突）
import importlib
from services import embedding_service as em
importlib.reload(em)

esvc = em.EmbeddingService()
esvc._flask_app = app

# 强制走 Ollama 路径（跳过 sentence-transformers 和 TF-IDF）
print()
print('[1/3] 初始化 Ollama embedding...')
esvc.device = 'cpu'
for ollama_model in [em.OLLAMA_EMBED_MODEL, em.OLLAMA_EMBED_FALLBACK_MODEL]:
    try:
        import requests
        r = requests.post(
            f'{em.OLLAMA_HOST}/api/embeddings',
            json={'model': ollama_model, 'prompt': 'test'},
            timeout=15,
        )
        if r.status_code == 200:
            vec = r.json().get('embedding', [])
            if vec:
                esvc._ollama_model = ollama_model
                esvc._ollama_dimension = len(vec)
                esvc._use_ollama = True
                esvc._use_fallback = False
                esvc._initialized = True
                print(f'  Ollama 就绪: model={ollama_model}, dim={len(vec)}')
                break
    except Exception as e:
        print(f'  {ollama_model} 失败: {e}')
else:
    print('  ⚠️  Ollama 不可用，降级到 TF-IDF')
    from sklearn.feature_extraction.text import TfidfVectorizer
    esvc._tfidf_vectorizer = TfidfVectorizer(
        max_features=em.TFIDF_MAX_FEATURES,
        ngram_range=em.TFIDF_NGRAM_RANGE,
        lowercase=True,
        sublinear_tf=True,
        dtype=np.float32,
    )
    esvc._use_fallback = True
    esvc._use_ollama = False
    esvc._initialized = True

# 构建索引
print()
print(f'[2/3] 构建 FAISS 索引 (limit={args.limit})...')
dim = esvc._effective_dim()
print(f'  向量维度: {dim}')
num_built = esvc.build_index_from_db(limit=args.limit)
print(f'  构建完成: {num_built} 本书')

# 保存
print()
print(f'[3/3] 保存索引...')
saved_ok = False
if num_built > 0 and esvc._faiss_index is not None:
    try:
        saved_ok = esvc.save_index()
        print(f'  保存: {"成功" if saved_ok else "失败"}')
    except Exception as e:
        print(f'  保存失败: {e}')

# 状态
print()
print('=' * 70)
print('状态报告')
print('=' * 70)
st = esvc.status
print(f'  use_ollama        = {st.get("use_ollama")}')
print(f'  ollama_model      = {st.get("ollama_model")}')
print(f'  ollama_dimension  = {st.get("ollama_dimension")}')
print(f'  use_fallback      = {st.get("use_fallback")}')
print(f'  effective_dim     = {st.get("effective_dimension")}')
print(f'  index_size        = {st.get("index_size")}')
print(f'  index_ready       = {st.get("index_ready")}')

# 搜索验证
print()
print('语义搜索验证 (Ollama embedding):')
queries = [
    'magic adventure and love story',
    'artificial intelligence and robots',
    'history of ancient civilizations',
    'python programming tutorial',
]
for q in queries:
    results = esvc.find_similar_books_by_text(q, top_k=3)
    print(f'  query="{q}"')
    for r in results:
        print(f'    sim={r.get("similarity"):.4f} | {str(r.get("title",""))[:65]}')
    if not results:
        print(f'    (无结果)')
    print()

print(f'总耗时: {time.time() - t0:.1f}s')
print(f'构建: {num_built} 本 / 保存: {saved_ok}')
ctx.pop()
