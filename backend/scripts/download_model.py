# -*- coding: utf-8 -*-
"""
通过 hf-mirror.com 国内镜像下载 sentence-transformers 模型
Usage: python scripts/download_model.py [--model paraphrase-multilingual-MiniLM-L12-v2]
"""
import os
import sys
import argparse

# 设置镜像源优先
HF_ENDPOINT = os.environ.get('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ['HF_ENDPOINT'] = HF_ENDPOINT
os.environ['HF_MIRROR'] = HF_ENDPOINT
print(f'  [镜像] 使用 endpoint: {HF_ENDPOINT}')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

parser = argparse.ArgumentParser(description='Download sentence-transformers model via hf-mirror')
parser.add_argument('--model', default='paraphrase-multilingual-MiniLM-L12-v2',
                    help='模型名称 (默认: paraphrase-multilingual-MiniLM-L12-v2)')
parser.add_argument('--cache', default=None,
                    help='缓存目录 (默认: services/.cache)')
args = parser.parse_args()

MODEL_NAME = args.model
CACHE_DIR = args.cache or os.path.join(BASE_DIR, 'services', '.cache')
os.makedirs(CACHE_DIR, exist_ok=True)

print('=' * 70)
print(f'下载模型: {MODEL_NAME}')
print(f'缓存目录: {CACHE_DIR}')
print(f'镜像源: {HF_ENDPOINT}')
print('=' * 70)

import time
t0 = time.time()

try:
    from sentence_transformers import SentenceTransformer
    print()
    print(f'正在下载模型（首次约 80-400MB）...')
    print('(可通过 Ctrl+C 中断，已下载部分保存在缓存中)')
    print()
    model = SentenceTransformer(
        MODEL_NAME,
        cache_folder=CACHE_DIR,
        device='cpu',
    )
    elapsed = time.time() - t0
    print()
    print('=' * 70)
    print(f'✅ 模型下载成功！')
    print(f'   模型: {MODEL_NAME}')
    print(f'   向量维度: {model.get_sentence_embedding_dimension()}')
    print(f'   用时: {elapsed:.1f}s')
    print(f'   缓存: {CACHE_DIR}')
    print('=' * 70)

    # 快速测试
    print()
    print('快速编码测试:')
    vec = model.encode(['Hello world', '你好世界', 'science fiction novel'])
    for i, v in enumerate(vec):
        print(f'  [{i}] len={len(v)}, first3={v[:3].round(3)}')

    # 打印缓存目录内容
    print()
    print('缓存目录内容:')
    total = 0
    for root, dirs, files in os.walk(CACHE_DIR):
        for f in files:
            fp = os.path.join(root, f)
            sz = os.path.getsize(fp)
            total += sz
            rel = os.path.relpath(fp, CACHE_DIR)
            print(f'  {sz // 1024:>8d} KB  {rel}')
    print(f'  总计: {total / 1024 / 1024:.1f} MB')

except KeyboardInterrupt:
    print()
    print('中断，已下载内容保存在:', CACHE_DIR)
    sys.exit(0)
except Exception as e:
    print()
    print(f'❌ 下载失败: {e}')
    print()
    print('备选方案:')
    print(f'  1. 手动设置镜像: set HF_ENDPOINT=https://hf-mirror.com')
    print(f'  2. 或使用 Ollama embedding（已有 Ollama 运行中）')
    sys.exit(1)
