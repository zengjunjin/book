"""
ML 模块配置 - 支持完全离线模式
参考报告: os.environ['TRANSFORMERS_OFFLINE'] = '1'
"""
import os

# 离线模式配置
os.environ['TRANSFORMERS_OFFLINE'] = os.getenv('TRANSFORMERS_OFFLINE', '0')
os.environ['HF_HUB_OFFLINE'] = os.getenv('HF_HUB_OFFLINE', '0')
os.environ['HF_ENDPOINT'] = os.getenv('HF_ENDPOINT', '')

# 模型配置
class MLConfig:
    # 文本 Embedding 模型（使用轻量级模型适配 CPU/GPU）
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')

    # 最大序列长度（参考报告 MAX_LEN=128 的显存优化策略）
    MAX_SEQ_LENGTH = 128

    # 批量大小（参考报告 BATCH_SIZE=4 适配 4GB 显存）
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '16'))

    # 设备配置（参考报告 device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')）
    DEVICE = 'cuda'  # 自动检测

ml_config = MLConfig()
