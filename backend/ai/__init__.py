"""
📚 AI 内容创作助手模块

基于本地 LLM 的书籍智能内容生成系统
- 智能书评生成
- 推荐理由生成
- 书籍知识图谱
- 阅读报告
- 对话式交互

核心依赖:
- Ollama (本地 LLM)
- Flask (API)
- 现有书籍数据库
"""

from .llm_engine import LLMEngine, get_llm_engine
from .conversation import ConversationManager
from .prompts import PROMPTS

__version__ = "2.0.0"
__author__ = "Book Recommendation AI"

__all__ = [
    'LLMEngine',
    'get_llm_engine',
    'ConversationManager',
    'PROMPTS',
]
