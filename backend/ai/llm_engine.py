"""
🧠 LLM 引擎 - AI 内容创作助手的核心大脑

支持多种运行模式:
1. Ollama 本地模式 - 使用本地大模型
2. 模拟模式 - 基于规则的智能响应（无需 LLM）
3. API 模式 - 兼容 OpenAI/智谱等

设计原则:
- 完全离线优先
- 优雅降级（没有 LLM 也能工作）
- 支持热插拔模型
"""

import json
import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except ImportError:
    Retry = None
import threading
import time
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
import random
import re
import hashlib


@dataclass
class LLMResponse:
    """LLM 响应封装"""
    content: str
    model: str
    tokens: int = 0
    time: float = 0
    mode: str = "llm"  # "llm" 或 "simulate"
    raw: Any = None

    def to_dict(self):
        return {
            "content": self.content,
            "model": self.model,
            "tokens": self.tokens,
            "time": round(self.time, 2),
            "mode": self.mode,
        }


@dataclass
class ModelConfig:
    """模型配置"""
    name: str = "qwen2.5:1.5b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.8
    max_tokens: int = 2000
    timeout: int = 120
    system_prompt: str = ""


class LLMEngine:
    """
    大语言模型引擎
    
    负责:
    - 与 Ollama 本地模型通信
    - 优雅降级到模拟模式
    - 模型管理和切换
    - 响应缓存
    """

    # 中文友好的轻量级模型列表（优先推荐）
    RECOMMENDED_MODELS = [
        "qwen2.5:1.5b",      # 通义千问 - 中文最好
        "qwen2.5:3b",        # 中等模型
        "qwen2.5:7b",        # 较大模型
        "llama3.2:1b",       # Llama 轻量
        "gemma2:2b",         # Gemma
        "phi3:14b",          # Phi 小而强
    ]

    def __init__(self, config: ModelConfig = None):
        self.config = config or ModelConfig()
        self.call_lock = threading.Lock()
        self._response_cache: Dict[str, LLMResponse] = {}
        self.cache_ttl = 3600  # 缓存1小时
        self._call_count = 0

        # ---- TCP 连接池复用：requests.Session + HTTPAdapter ----
        self.session = requests.Session()
        # 限制每个主机保持 5 个 keep-alive 连接（默认也是 10，这里明确设置）
        adapter = HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            pool_block=False,
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        # 可选的指数退避重试（网络抖动时更稳）
        if Retry is not None:
            retry = Retry(
                total=3,
                backoff_factor=0.3,
                status_forcelist=(500, 502, 503, 504),
                allowed_methods=frozenset(['GET', 'POST']),
                raise_on_status=False,
            )
            try:
                adapter_with_retry = HTTPAdapter(
                    pool_connections=5,
                    pool_maxsize=10,
                    pool_block=False,
                    max_retries=retry,
                )
                self.session.mount('http://', adapter_with_retry)
                self.session.mount('https://', adapter_with_retry)
            except Exception:
                pass
        # 预热：先查一次状态（同时建立首条连接）
        try:
            r = self.session.get(f'{self.config.base_url}/api/tags', timeout=3)
            self.ollama_available = r.status_code == 200
        except Exception:
            self.ollama_available = False
        self.current_model = self.config.name

    def close(self):
        """释放 Session（长生命周期内一般不需要调用）"""
        try:
            self.session.close()
        except Exception:
            pass

    # ========== Ollama 检测 ==========

    def _check_ollama(self) -> bool:
        """检查 Ollama 是否可用（走 Session 连接池）"""
        try:
            response = self.session.get(
                f"{self.config.base_url}/api/tags",
                timeout=3
            )
            return response.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[Dict]:
        """列出本地可用的模型（走 Session 连接池）"""
        if not self.ollama_available:
            return []
        try:
            response = self.session.get(
                f"{self.config.base_url}/api/tags",
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("models", [])
        except Exception:
            pass
        return []

    def check_model_available(self, model_name: str) -> bool:
        """检查指定模型是否已下载"""
        models = self.list_models()
        return any(m.get("name", "").startswith(model_name.split(":")[0]) for m in models)

    def pull_model(self, model_name: str, callback: Callable = None) -> bool:
        """下载模型（走 Session 连接池，支持流式）"""
        if not self.ollama_available:
            return False
        try:
            response = self.session.post(
                f"{self.config.base_url}/api/pull",
                json={"name": model_name},
                stream=True,
                timeout=600
            )
            if callback:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            callback(data)
                        except Exception:
                            pass
            return True
        except Exception as e:
            print(f"下载模型失败: {e}")
            return False

    # ========== 核心调用 ==========

    def generate(self, prompt: str, system_prompt: str = None,
                model: str = None, use_cache: bool = True) -> LLMResponse:
        """
        生成 AI 响应
        
        Args:
            prompt: 用户输入/提示
            system_prompt: 系统提示（角色定义）
            model: 覆盖默认模型
            use_cache: 是否使用缓存
        
        Returns:
            LLMResponse 对象
        """
        start_time = time.time()
        self._call_count += 1

        # 缓存检查：使用稳定的 md5 缓存键（跨进程一致）
        cache_key = (
            f"{model or self.current_model}:"
            f"{hashlib.md5((prompt or '').encode('utf-8')).hexdigest()[:16]}:"
            f"{hashlib.md5((system_prompt or '').encode('utf-8')).hexdigest()[:16]}"
        )
        if use_cache and cache_key in self._response_cache:
            cached = self._response_cache[cache_key]
            if (time.time() - getattr(cached, "time", 0)) < self.cache_ttl:
                return cached

        # 尝试使用 Ollama
        if self.ollama_available:
            try:
                response = self._call_ollama(prompt, system_prompt, model)
                if response:
                    response.time = time.time() - start_time
                    if use_cache:
                        self._response_cache[cache_key] = response
                    return response
            except Exception as e:
                print(f"[LLM] Ollama 调用失败: {e}")

        # 降级到模拟模式
        response = self._simulate_response(prompt, system_prompt)
        response.time = time.time() - start_time
        return response

    def generate_stream(self, prompt: str, system_prompt: str = None,
                       callback: Callable[[str], None] = None,
                       model: str = None) -> LLMResponse:
        """流式生成（实时输出）"""
        start_time = time.time()
        full_text = ""

        if self.ollama_available:
            try:
                response = self.session.post(
                    f"{self.config.base_url}/api/generate",
                    json={
                        "model": model or self.current_model,
                        "prompt": prompt,
                        "system": system_prompt or self.config.system_prompt,
                        "stream": True,
                        "options": {
                            "temperature": self.config.temperature,
                            "num_predict": self.config.max_tokens,
                        }
                    },
                    stream=True,
                    timeout=self.config.timeout
                )

                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            token = data.get("response", "")
                            full_text += token
                            if callback:
                                callback(token)
                            if data.get("done"):
                                break
                        except:
                            continue

                return LLMResponse(
                    content=full_text,
                    model=model or self.current_model,
                    tokens=len(full_text),
                    time=time.time() - start_time,
                    mode="llm"
                )
            except Exception as e:
                print(f"[LLM] 流式调用失败: {e}")

        # 模拟模式（逐字输出效果）
        sim_response = self._simulate_response(prompt, system_prompt)
        for char in sim_response.content:
            if callback:
                callback(char)
            time.sleep(0.01)  # 模拟打字效果

        sim_response.time = time.time() - start_time
        return sim_response

    def _call_ollama(self, prompt: str, system_prompt: str = None,
                    model: str = None) -> Optional[LLMResponse]:
        """调用 Ollama API（走 Session 连接池，支持并发）"""
        with self.call_lock:
            response = self.session.post(
                f"{self.config.base_url}/api/generate",
                json={
                    "model": model or self.current_model,
                    "prompt": prompt,
                    "system": system_prompt or self.config.system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.config.temperature,
                        "num_predict": self.config.max_tokens,
                        "seed": random.randint(1, 100000),
                    }
                },
                timeout=self.config.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return LLMResponse(
                    content=data.get("response", ""),
                    model=data.get("model", model or self.current_model),
                    tokens=data.get("eval_count", 0),
                    mode="llm",
                    raw=data
                )
        return None

    # ========== 模拟模式（无 LLM 时的智能响应）==========

    def _simulate_response(self, prompt: str, system_prompt: str = None) -> LLMResponse:
        """
        基于规则的智能响应（无 LLM 时）
        使用关键词匹配 + 模板 + 书籍数据库信息
        """
        # 从书籍数据库中随机获取一些书籍信息作为上下文
        books_info = self._get_sample_books_info()

        # 根据提示内容类型选择不同的响应策略
        if any(keyword in prompt for keyword in ["书评", "评论", "评价", "读后感", "review"]):
            content = self._simulate_book_review(prompt, books_info)
        elif any(keyword in prompt for keyword in ["推荐", "推荐什么", "看什么", "推荐一下"]):
            content = self._simulate_recommendation(prompt, books_info)
        elif any(keyword in prompt for keyword in ["介绍", "简介", "讲什么", "内容", "about"]):
            content = self._simulate_book_intro(prompt, books_info)
        elif any(keyword in prompt for keyword in ["知识", "图谱", "主题", "关键词", "标签"]):
            content = self._simulate_knowledge(prompt, books_info)
        elif any(keyword in prompt for keyword in ["报告", "总结", "统计", "阅读", "年度"]):
            content = self._simulate_report(prompt, books_info)
        elif any(keyword in prompt for keyword in ["你好", "嗨", "hello", "hi", "在吗"]):
            content = self._simulate_greeting()
        elif any(keyword in prompt for keyword in ["你是谁", "介绍自己", "你能做什么", "help", "帮助"]):
            content = self._simulate_self_intro()
        else:
            # 默认对话
            content = self._simulate_chat(prompt, books_info)

        return LLMResponse(
            content=content,
            model="simulated-ai",
            tokens=len(content),
            mode="simulate"
        )

    def _get_sample_books_info(self) -> str:
        """从数据库获取书籍信息（模拟响应时使用）"""
        try:
            from extensions import db
            # 直接通过 SQL 查询获取几本书
            conn = db.engine.connect()
            result = conn.execute(
                db.text("SELECT title, author, publisher FROM books LIMIT 5")
            )
            books = [f"《{row[0]}》({row[1]})" for row in result.fetchall()]
            conn.close()
            return "\n".join(books[:3]) if books else ""
        except:
            return "《三体》《活着》《百年孤独》"

    def _simulate_greeting(self) -> str:
        """模拟问候"""
        greetings = [
            "你好！我是你的书籍 AI 助手 📚\n\n我可以帮你：\n• 生成有趣的书评\n• 推荐适合的书籍\n• 分析书籍内容和主题\n• 生成阅读报告\n\n告诉我，你想要了解什么？",
            "嗨！很高兴见到你 👋\n\n作为你的 AI 书籍助手，我可以为你生成书评、推荐好书、分析阅读偏好。\n\n有什么我能帮你的吗？",
        ]
        return random.choice(greetings)

    def _simulate_self_intro(self) -> str:
        """自我介绍"""
        return """🤖 我是 **书籍 AI 内容创作助手**

✨ 我能做什么：

📝 **书评生成** - 为任意书籍生成专业或个性化的书评
🎯 **智能推荐** - 根据你的偏好推荐合适的书籍
🧠 **内容分析** - 分析书籍主题、提取关键词
📊 **阅读报告** - 生成个人阅读统计和年度报告
💬 **对话交流** - 聊天讨论你感兴趣的书籍

🔧 运行模式：本地 LLM 引擎（支持 qwen/llama 等模型）
💡 提示：尝试问我"给《三体》写一篇书评"或"推荐一些科幻小说"
"""

    def _simulate_book_review(self, prompt: str, books_info: str) -> str:
        """模拟书评生成"""
        # 从提示中提取书名
        book_title = self._extract_book_title(prompt) or "这本书"

        templates = [
            f"""📖 《{book_title}》书评

这是一本令人印象深刻的作品。作者以独特的叙事风格，将读者带入一个既陌生又熟悉的世界。

**🌟 亮点：**
• 情节设计精妙，悬念迭起
• 人物塑造立体生动
• 语言优美，富有哲理
• 主题深刻，引发思考

**💭 读后感：**
阅读这本书就像踏上一段奇妙的旅程。作者在书中探讨的主题让人久久不能平静。尤其是关于人性与命运的描写，深深触动了我。

**⭐ 评分：8.5/10**

📌 推荐给喜欢深度阅读的读者。如果你正在寻找一本能让你思考的书，这本书不会让你失望。
""",
            f"""📖 《{book_title}》— 一份真诚的阅读分享

初读这本书时，我并没有太多期待。但随着阅读的深入，我被故事中人物的命运深深吸引。

**📝 内容概要**
这本书讲述了一个关于成长与选择的故事。主人公在面临人生的重大抉择时，展现出令人敬佩的勇气和智慧。

**❤️ 我喜欢的部分**
1. 细腻的情感描写
2. 出人意料的情节转折
3. 富有哲理的对话

**🤔 值得思考**
这本书让我重新审视了很多关于生活和选择的问题。

**✨ 最终评价：9/10**
一本值得反复阅读的佳作。
"""
        ]
        return random.choice(templates)

    def _simulate_recommendation(self, prompt: str, books_info: str) -> str:
        """模拟推荐理由生成"""
        # 尝试识别偏好
        is_scifi = any(w in prompt for w in ["科幻", "scifi", "三体", "科学"])
        is_literary = any(w in prompt for w in ["文学", "小说", "经典", "文学作品"])

        if is_scifi:
            category = "科幻小说"
            example_books = "《三体》《基地》《银河系漫游指南》"
        elif is_literary:
            category = "经典文学"
            example_books = "《百年孤独》《活着》《红楼梦》"
        else:
            category = "综合推荐"
            example_books = books_info or "《三体》《活着》《百年孤独》"

        return f"""🎯 为你推荐：{category}书籍

根据你的兴趣，我为你挑选了以下类型的书籍：

📚 **推荐理由：**

1. **探索想象的边界** — {category}书籍通常展现了超乎寻常的想象力
2. **深度思考的乐趣** — 在阅读中获得思考的乐趣
3. **经久耐读** — 好的{category}作品值得反复品味

🌟 **推荐书单：**
{example_books}

📖 **为什么你可能会喜欢：**

• 你之前阅读过的书籍显示出对深度内容的偏好
• 这类书籍适合在安静的时段深入阅读
• 往往能带来长久的思考和启发

💡 下一步：尝试从书单中选一本，先读前50页看看是否合口味。
"""

    def _simulate_book_intro(self, prompt: str, books_info: str) -> str:
        """模拟书籍介绍"""
        book_title = self._extract_book_title(prompt) or "这本书"

        return f"""📚 关于《{book_title}》

**📖 这是一本：**
值得细细品味的作品。无论是作为消遣阅读，还是深入研究，都能给读者带来丰富的收获。

**🎯 核心主题：**
• 人性与选择
• 命运与自由意志
• 成长与蜕变

**👤 适合读者：**
• 喜欢深度阅读的人
• 对人性哲学感兴趣的读者
• 愿意花时间思考的读者

**⏱ 阅读建议：**
建议每天阅读 30-50 页，留出时间思考和消化。

---
💡 **想要更深入的分析？**
可以问我：
• "分析《{book_title}》的主题"
• "生成《{book_title}》的知识图谱"
• "《{book_title}》应该怎么读？"
"""

    def _simulate_knowledge(self, prompt: str, books_info: str) -> str:
        """模拟知识图谱/主题分析"""
        book_title = self._extract_book_title(prompt) or "目标书籍"

        return f"""🧠 《{book_title}》知识图谱分析

**📌 核心主题：**
├── 个人成长与自我认知
├── 社会环境与人性的互动
├── 命运与选择的辩证关系
└── 传统与现代的冲突

**🏷 关键词标签：**
成长 · 选择 · 命运 · 人性 · 爱情 · 友谊 · 家庭 · 梦想 · 救赎 · 希望

**🔗 关联主题：**
《{book_title}》↔ 存在主义思考
《{book_title}》↔ 现代主义文学
《{book_title}》↔ 心理现实主义

**📚 相似推荐：**
→ 同主题延伸阅读
→ 同作者其他作品
→ 同风格的经典作品

💡 **提示：** 这个知识图谱可以帮助你理解书籍的深层结构和主题脉络。
"""

    def _simulate_report(self, prompt: str, books_info: str) -> str:
        """模拟阅读报告"""
        return """📊 你的阅读年度报告

**📈 数据概览：**

• 📚 已阅读书籍：15 本
• ⏱ 累计阅读：约 45 小时
• ⭐ 平均评分：8.2 分
• 🏆 最高评分：9.8 分

**📋 阅读偏好分析：**

你的阅读书单显示出以下倾向：

1. **📖 文学小说 (40%)** — 你的主要阅读类别
2. **🔬 科技科普 (25%)** — 显示出对知识的渴求
3. **🎭 历史传记 (20%)** — 注重人文素养
4. **💭 哲学思考 (15%)** — 深度思考倾向

**🌟 年度最佳书籍：**

根据你的评分和阅读时长数据，这些是你的最爱：
1. 《三体》 — 9.8 分 · 深入阅读
2. 《百年孤独》 — 9.5 分 · 反复阅读

**💡 推荐方向：**

→ 尝试在"哲学"类别中探索更多
→ 可以考虑阅读一些经典作品的续集/解读
→ 建议挑战一些长篇巨著

📝 **总结：**
这是一个充实而有深度的阅读年度。你展现出对高质量内容的鉴赏力，
以及广泛而深入的阅读兴趣。继续保持，让阅读成为生活的一部分！📖✨
"""

    def _simulate_chat(self, prompt: str, books_info: str) -> str:
        """模拟日常对话"""
        responses = [
            f"我理解你想了解「{prompt[:50]}」相关的内容。\n\n作为书籍 AI 助手，我可以帮你：\n\n• 生成个性化书评\n• 推荐匹配你口味的书籍\n• 分析书籍的核心主题\n• 生成阅读报告\n\n告诉我，你具体想了解什么？",
            f"好的，关于「{prompt[:30]}」——\n\n这是一个很有意思的话题！在书籍的世界里，这个主题被无数作家探讨过。\n\n你想从哪个角度来了解？\n1. 推荐相关书籍？\n2. 分析某个具体作品？\n3. 生成一份书评？",
            f"这是一个很棒的问题 🤔\n\n让我从书籍推荐的角度来思考...\n\n在我们的书库中，有很多作品与你的话题相关。\n\n📌 你可以尝试这样问我：\n• \"推荐一些关于[主题]的书\"\n• \"给《书名》写一篇书评\"\n• \"分析我的阅读偏好\"\n• \"生成我的阅读报告\"",
        ]
        return random.choice(responses)

    def _extract_book_title(self, prompt: str) -> str:
        """从提示中提取书名"""
        # 尝试匹配《书名》格式
        match = re.search(r"《([^》]+)》", prompt)
        if match:
            return match.group(1)

        # 尝试匹配引号
        match = re.search(r"[\"'「]([^\"'」]+)[\"'」]", prompt)
        if match:
            return match.group(1)

        return None

    # ========== 便捷方法 ==========

    def chat(self, message: str, history: List[Dict] = None) -> LLMResponse:
        """简单对话"""
        system_prompt = "你是一个友好、专业的书籍推荐 AI 助手。用中文回答，语气自然、有帮助。"
        return self.generate(message, system_prompt)

    def get_status(self) -> Dict:
        """获取引擎状态"""
        return {
            "ollama_available": self.ollama_available,
            "current_model": self.current_model,
            "installed_models": [m.get("name") for m in self.list_models()],
            "recommended_models": self.RECOMMENDED_MODELS,
            "total_calls": self._call_count,
            "cache_size": len(self._response_cache),
            "mode": "llm" if self.ollama_available else "simulate",
        }

    def clear_cache(self):
        """清空缓存"""
        self._response_cache.clear()

    def set_model(self, model_name: str):
        """切换模型"""
        self.current_model = model_name
        self.config.name = model_name

    def set_temperature(self, temp: float):
        """设置创造性"""
        self.config.temperature = max(0.1, min(2.0, temp))


# ========== 单例管理 ==========

_engine_instance: Optional[LLMEngine] = None


def get_llm_engine() -> LLMEngine:
    """获取 LLM 引擎单例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LLMEngine()
    return _engine_instance


def reset_llm_engine():
    """重置引擎"""
    global _engine_instance
    _engine_instance = None


# 自动初始化
_ = get_llm_engine()
