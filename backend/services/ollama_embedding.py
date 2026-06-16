# -*- coding: utf-8 -*-
"""
Ollama 本地 embedding 集成（作为 sentence-transformers 的备用）
适用于：本地已有 Ollama 运行（localhost:11434），但网络无法访问 HuggingFace 时

用法：
  1. 在 embedding_service.py 中自动检测 Ollama 是否可用
  2. 若可用则优先使用 Ollama（完全本地，无需下载）
  3. 若不可用则 fallback 到 TF-IDF
  4. 若网络恢复则使用 sentence-transformers（质量最高）

支持的 Ollama embedding 模型（需先 pull）：
  ollama pull mxbai-embed-large    # 768维，高质量
  ollama pull nomic-embed-text     # 768维，支持多语言
  ollama pull all-MiniLM-L6-v2     # 384维（需转换为 Ollama 格式）
"""
import numpy as np
import requests
import os
import time

OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
DEFAULT_OLLAMA_MODEL = 'mxbai-embed-large'  # 768维，多语言支持好


class OllamaEmbedding:
    """Ollama 本地 embedding 客户端"""

    def __init__(self, model=None, host=None):
        self.model = model or DEFAULT_OLLAMA_MODEL
        self.host = host or OLLAMA_HOST
        self._dimension = None
        self._available = None

    @property
    def dimension(self):
        if self._dimension is None:
            try:
                # 探测向量维度
                vec = self.encode('test')
                self._dimension = len(vec)
            except Exception:
                self._dimension = 768  # 默认
        return self._dimension

    def is_available(self):
        """检测 Ollama 服务是否可用"""
        if self._available is not None:
            return self._available
        try:
            r = requests.get(f'{self.host}/api/tags', timeout=3)
            if r.status_code == 200:
                models = r.json().get('models', [])
                model_names = [m.get('name', '') for m in models]
                self._available = True
                print(f'  [Ollama] 已连接，可用模型: {model_names}')
                # 检查目标模型是否存在
                if any(self.model in m for m in model_names):
                    print(f'  [Ollama] 目标模型 "{self.model}" 已安装')
                else:
                    print(f'  [Ollama] ⚠️  目标模型 "{self.model}" 未安装，请运行: ollama pull {self.model}')
                return True
        except Exception as e:
            self._available = False
            print(f'  [Ollama] 连接失败: {e}')
        return False

    def encode(self, texts, batch_size=32):
        """
        编码文本列表为向量
        Returns:
            np.ndarray of shape (n, dimension)
        """
        if isinstance(texts, str):
            texts = [texts]

        vectors = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                r = requests.post(
                    f'{self.host}/api/embeddings',
                    json={'model': self.model, 'prompt': batch[0]},
                    timeout=30,
                )
                if r.status_code == 200:
                    vec = r.json().get('embedding', [])
                    vectors.append(np.array(vec, dtype=np.float32))
                else:
                    # fallback: 零向量
                    dim = self.dimension
                    vectors.append(np.zeros(dim, dtype=np.float32))
            except Exception as e:
                print(f'  [Ollama] encode 失败: {e}')
                vectors.append(np.zeros(self.dimension, dtype=np.float32))

        if len(vectors) == 1:
            return vectors[0].reshape(-1)
        return np.array(vectors)

    def encode_batch(self, texts, batch_size=32):
        """批量编码，兼容 sentence-transformers 接口"""
        if isinstance(texts, str):
            texts = [texts]
        return self.encode(texts, batch_size=batch_size)


def check_ollama_models():
    """检查 Ollama 中有哪些 embedding 模型可用"""
    print('=' * 70)
    print('Ollama embedding 模型检查')
    print('=' * 70)
    try:
        r = requests.get(f'{OLLAMA_HOST}/api/tags', timeout=5)
        models = r.json().get('models', [])
        print(f'已安装模型 ({len(models)} 个):')
        for m in models:
            name = m.get('name', '?')
            size = m.get('size', 0)
            print(f'  - {name} ({size / 1024 / 1024:.0f} MB)')
    except Exception as e:
        print(f'无法连接 Ollama: {e}')


def pull_model(model_name=DEFAULT_OLLAMA_MODEL):
    """通过 Ollama API 拉取模型"""
    print(f'正在拉取模型: {model_name}')
    print(f'(可能需要几分钟，取决于网络速度)')
    try:
        r = requests.post(
            f'{OLLAMA_HOST}/api/pull',
            json={'name': model_name, 'stream': False},
            timeout=600,
        )
        if r.status_code == 200:
            print(f'✅ 模型 {model_name} 拉取成功')
            return True
        else:
            print(f'❌ 拉取失败: {r.status_code} {r.text}')
            return False
    except Exception as e:
        print(f'❌ 拉取失败: {e}')
        return False


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true', help='仅检查已安装模型')
    p.add_argument('--pull', default=None, help='拉取指定模型')
    args = p.parse_args()

    if args.check:
        check_ollama_models()
    elif args.pull:
        pull_model(args.pull)
    else:
        # 完整测试
        check_ollama_models()
        print()
        print('Ollama embedding 快速测试:')
        ollama = OllamaEmbedding()
        if ollama.is_available():
            print(f'  向量维度: {ollama.dimension}')
            test_texts = ['Hello world', '你好世界', 'science fiction novel about space']
            vecs = ollama.encode_batch(test_texts)
            for t, v in zip(test_texts, vecs):
                print(f'  "{t[:30]}" -> vec[:3]={v[:3].round(4)}')
