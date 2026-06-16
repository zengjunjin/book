# -*- coding: utf-8 -*-
"""环境与模型检测：检查网络 + sentence-transformers 状态"""
import os
import sys
import time

def check_network(url, timeout=10):
    try:
        import urllib.request
        r = urllib.request.urlopen(url, timeout=timeout)
        return True, r.status
    except Exception as e:
        return False, str(e)

def main():
    print('=' * 70)
    print('环境检测：sentence-transformers 模型检测')
    print('=' * 70)

    # 1. 依赖检查
    print()
    print('[1/5] 依赖检查')
    packages = ['sentence_transformers', 'transformers', 'torch', 'faiss', 'sklearn']
    for p in packages:
        try:
            mod = __import__(p)
            ver = getattr(mod, '__version__', 'n/a')
            print(f'  {p:>25s} -> OK (v{ver})')
        except ImportError as e:
            print(f'  {p:>25s} -> MISSING ({e})')

    # 2. 网络检查
    print()
    print('[2/5] 网络检查')
    targets = [
        ('huggingface.co', 'https://huggingface.co'),
        ('cdn-lfs.hf.co', 'https://cdn-lfs.hf.co'),
        ('hf-mirror.com (国内镜像)', 'https://hf-mirror.com'),
        ('pypi.org', 'https://pypi.org'),
    ]
    for name, url in targets:
        ok, info = check_network(url)
        print(f'  {name:>25s} -> {ok} ({info})')

    # 3. 检查本地已有缓存模型
    print()
    print('[3/5] HuggingFace 本地缓存')
    cache_dirs = [
        os.path.expanduser(os.path.join('~', '.cache', 'huggingface')),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'services', '.cache'),
        os.environ.get('HF_HOME', ''),
        os.environ.get('SENTENCE_TRANSFORMERS_HOME', ''),
        os.environ.get('TRANSFORMERS_CACHE', ''),
    ]
    import hashlib
    for d in set(cache_dirs):
        if not d:
            continue
        if os.path.isdir(d):
            print(f'  目录: {d}')
            size = 0
            for root, dirs, files in os.walk(d):
                for f in files:
                    try:
                        size += os.path.getsize(os.path.join(root, f))
                    except Exception:
                        pass
            print(f'    大小: {size / 1024 / 1024:.1f} MB')
            # 显示前10个模型
            models_found = []
            try:
                from huggingface_hub import scan_cache_dir
                info = scan_cache_dir()
                print(f'    缓存模型数: {len(info.repos)}')
                for repo in list(info.repos)[:10]:
                    print(f'      - {repo.repo_id} ({repo.size_on_disk / 1024 / 1024:.1f} MB')
            except Exception:
                pass

    # 4. 尝试小模型加载
    print()
    print('[4/5] 尝试加载 sentence-transformers 小模型')
    test_models = [
        'paraphrase-multilingual-MiniLM-L12-v2',
        'all-MiniLM-L6-v2',
        'paraphrase-MiniLM-L6-v2',
    ]
    from sentence_transformers import SentenceTransformer

    model_ok = False
    loaded_model = None
    for m in test_models:
        print(f'  尝试: {m} ...')
        try:
            t0 = time.time()
            cache_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'services', '.cache')
            loaded_model = SentenceTransformer(
                m,
                cache_folder=cache_folder,
            )
            print(f'    -> OK (用时 {time.time() - t0:.1f}s, 测试编码...')
            vec = loaded_model.encode('Hello world')
            print(f'    向量维度: {len(vec)}')
            model_ok = True
            break
        except Exception as e:
            print(f'    -> 失败: {e}')

    # 5. 检查 Ollama 是否可用（作为替代 embedding 源）
    print()
    print('[5/5] Ollama 检查')
    ollama_api = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
    ok, info = check_network(f'{ollama_api}/api/tags')
    if ok:
        print(f'  Ollama 可用: {ollama_api}')
    else:
        print(f'  Ollama 未检测: {info}')

    print()
    print('=' * 70)
    if model_ok:
        print(f'✅ sentence-transformers 模型加载成功')
    else:
        print('⚠️  所有 sbert 模型都失败，继续使用 TF-IDF fallback')
    print('=' * 70)


if __name__ == '__main__':
    main()
