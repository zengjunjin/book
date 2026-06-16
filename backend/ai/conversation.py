"""
💬 对话管理系统 v2.0

负责:
- 对话历史管理
- 上下文理解
- 用户偏好记忆
- 多轮对话的连贯性
- 对话历史数据库持久化
"""

import json
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime

from .llm_engine import get_llm_engine, LLMResponse


@dataclass
class Message:
    """单条消息"""
    role: str                    # "user" / "assistant" / "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
            "time": datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S"),
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class Conversation:
    """一次完整对话"""
    id: str
    user_id: Optional[int] = None
    messages: List[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    preferences: Dict = field(default_factory=dict)  # 用户偏好
    context: Dict = field(default_factory=dict)       # 当前上下文（正在讨论的书籍等）

    def add_message(self, message: Message):
        """添加消息"""
        self.messages.append(message)
        self.last_updated = time.time()

    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """获取最近 N 条消息"""
        return self.messages[-limit:]

    def clear(self):
        """清空对话（保留偏好）"""
        self.messages = []

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": datetime.fromtimestamp(self.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            "last_updated": datetime.fromtimestamp(self.last_updated).strftime("%Y-%m-%d %H:%M:%S"),
            "message_count": len(self.messages),
            "preferences": self.preferences,
            "context": self.context,
        }


class ConversationManager:
    """
    对话管理器 v2.0 - 负责管理所有用户的对话

    特性:
    - 自动创建对话
    - 上下文理解
    - 多轮对话连贯
    - 智能识别用户意图
    - 对话历史数据库持久化
    - 用户偏好学习
    """

    MAX_HISTORY = 20  # 每轮对话保留的消息数

    # 意图关键词
    INTENT_KEYWORDS = {
        "review": ["书评", "写书评", "评论", "读后感", "评价这本书"],
        "recommend": ["推荐", "看什么", "读什么", "推荐一下", "有什么好书"],
        "analyze": ["分析", "主题", "结构", "讲什么", "内容分析"],
        "knowledge": ["知识图谱", "思维导图", "关键词", "标签"],
        "report": ["报告", "总结", "年度", "统计", "阅读报告"],
        "introduce": ["介绍", "简介", "是什么", "讲什么", "about"],
        "help": ["帮助", "help", "你能做什么", "功能"],
        "compare": ["对比", "比较", "vs", "哪个好"],
        "search": ["搜索", "找", "查找", "search"],
        "summary": ["摘要", "概括", "总结一下", "简介是什么"],
    }

    def __init__(self, db=None):
        self.conversations: Dict[str, Conversation] = {}
        self.engine = get_llm_engine()
        self.db = db
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        try:
            from .models import AIConversation, AIMessage, UserBookInteraction
            print("[ConvDB] 对话数据库模块已加载 ✓")
        except Exception as e:
            print(f"[ConvDB] 数据库模块加载: {e}")

    def _save_to_database(self, conv: Conversation):
        """保存对话到数据库"""
        if not self.db:
            return

        try:
            from .models import AIConversation, AIMessage
            from extensions import db as _db

            # 查找或创建对话记录
            db_conv = AIConversation.query.filter_by(conv_id=conv.id).first()
            if not db_conv:
                db_conv = AIConversation(
                    conv_id=conv.id,
                    user_id=conv.user_id,
                    title=f"对话 {datetime.now().strftime('%m-%d %H:%M')}",
                    message_count=len(conv.messages)
                )
                _db.session.add(db_conv)
            else:
                db_conv.last_updated = datetime.utcnow()
                db_conv.message_count = len(conv.messages)

            # 添加新消息
            for msg in conv.messages[-5:]:  # 只保存最近5条
                existing = AIMessage.query.filter_by(
                    conversation_id=db_conv.id,
                    timestamp=datetime.fromtimestamp(msg.timestamp)
                ).first()

                if not existing:
                    db_msg = AIMessage(
                        conversation_id=db_conv.id,
                        role=msg.role,
                        content=msg.content,
                        intent=msg.metadata.get('intent'),
                        model=msg.metadata.get('model'),
                        tokens=msg.metadata.get('tokens'),
                        metadata=msg.metadata
                    )
                    _db.session.add(db_msg)

            _db.session.commit()
        except Exception as e:
            print(f"[ConvDB] 保存失败: {e}")

    def _load_from_database(self, conv_id: str) -> Optional[Conversation]:
        """从数据库加载对话"""
        if not self.db:
            return None

        try:
            from .models import AIConversation, AIMessage

            db_conv = AIConversation.query.filter_by(conv_id=conv_id).first()
            if not db_conv:
                return None

            # 重建对话
            conv = Conversation(
                id=db_conv.conv_id,
                user_id=db_conv.user_id,
                created_at=db_conv.created_at.timestamp(),
                last_updated=db_conv.last_updated.timestamp()
            )

            # 加载消息
            db_messages = AIMessage.query.filter_by(
                conversation_id=db_conv.id
            ).order_by(AIMessage.timestamp).all()

            for db_msg in db_messages:
                conv.messages.append(Message(
                    role=db_msg.role,
                    content=db_msg.content,
                    timestamp=db_msg.timestamp.timestamp(),
                    metadata=db_msg.metadata or {}
                ))

            return conv

        except Exception as e:
            print(f"[ConvDB] 加载失败: {e}")
            return None

    # ========== 对话管理 ==========

    def get_or_create(self, conv_id: str, user_id: int = None) -> Conversation:
        """获取或创建对话"""
        # 尝试从数据库加载
        if conv_id not in self.conversations:
            db_conv = self._load_from_database(conv_id)
            if db_conv:
                self.conversations[conv_id] = db_conv
            else:
                self.conversations[conv_id] = Conversation(
                    id=conv_id,
                    user_id=user_id
                )
        return self.conversations[conv_id]

    def delete(self, conv_id: str) -> bool:
        """删除对话"""
        if conv_id in self.conversations:
            del self.conversations[conv_id]
            # 从数据库删除
            try:
                from .models import AIConversation
                from extensions import db as _db
                db_conv = AIConversation.query.filter_by(conv_id=conv_id).first()
                if db_conv:
                    _db.session.delete(db_conv)
                    _db.session.commit()
            except:
                pass
            return True
        return False

    def clear_user_conversations(self, user_id: int):
        """清空用户的所有对话"""
        to_delete = [cid for cid, c in self.conversations.items() if c.user_id == user_id]
        for cid in to_delete:
            del self.conversations[cid]

    # ========== 核心对话处理 ==========

    def handle_message(self, conv_id: str, user_message: str,
                       user_id: int = None) -> Dict:
        """
        处理用户消息，生成响应
        
        步骤:
        1. 获取/创建对话
        2. 识别用户意图
        3. 构建系统提示 + 上下文
        4. 生成响应
        5. 更新对话历史
        """
        conv = self.get_or_create(conv_id, user_id)

        # 添加用户消息
        conv.add_message(Message(role="user", content=user_message))

        # 识别意图
        intent = self._detect_intent(user_message)

        # 构建提示
        system_prompt, enhanced_prompt = self._build_prompt(conv, user_message, intent)

        # 生成响应
        response = self.engine.generate(
            prompt=enhanced_prompt,
            system_prompt=system_prompt,
            use_cache=False  # 对话不缓存，保持新鲜感
        )

        # 添加 AI 响应
        conv.add_message(Message(
            role="assistant",
            content=response.content,
            metadata={
                "intent": intent,
                "model": response.model,
                "tokens": response.tokens,
                "mode": response.mode,
                "time": response.time,
            }
        ))

        # 更新上下文
        self._update_context(conv, user_message, response.content, intent)

        # 保存到数据库
        self._save_to_database(conv)

        return {
            "conversation": conv.to_dict(),
            "response": response.to_dict(),
            "intent": intent,
            "suggested_actions": self._get_suggested_actions(intent, conv),
        }

    def handle_message_stream(self, conv_id: str, user_message: str,
                              callback, user_id: int = None) -> Dict:
        """流式处理（用于前端实时打字效果）"""
        conv = self.get_or_create(conv_id, user_id)
        conv.add_message(Message(role="user", content=user_message))

        intent = self._detect_intent(user_message)
        system_prompt, enhanced_prompt = self._build_prompt(conv, user_message, intent)

        full_content = []

        def stream_callback(token):
            full_content.append(token)
            callback(token)

        response = self.engine.generate_stream(
            prompt=enhanced_prompt,
            system_prompt=system_prompt,
            callback=stream_callback
        )

        conv.add_message(Message(
            role="assistant",
            content="".join(full_content),
            metadata={"intent": intent}
        ))

        self._update_context(conv, user_message, response.content, intent)

        return {
            "conversation": conv.to_dict(),
            "response": response.to_dict(),
            "intent": intent,
        }

    # ========== 意图识别 ==========

    def _detect_intent(self, message: str) -> str:
        """简单的意图识别（基于关键词）"""
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in message.lower():
                    return intent
        return "chat"  # 默认闲聊

    # ========== 提示构建 ==========

    def _build_prompt(self, conv: Conversation, user_message: str, intent: str):
        """构建系统提示和增强提示"""
        from .prompts import PROMPTS

        # 基础角色定义
        system_prompt = PROMPTS["system"]["role"]

        # 根据意图选择不同的提示模板
        if intent in PROMPTS:
            intent_template = PROMPTS[intent]["user"]
            enhanced_prompt = f"{intent_template}\n\n用户输入: {user_message}"
        else:
            # 默认对话
            enhanced_prompt = user_message

        # 添加对话上下文
        if len(conv.messages) > 1:
            context = self._build_context_from_history(conv)
            if context:
                enhanced_prompt = f"{context}\n\n当前用户输入: {user_message}"

        return system_prompt, enhanced_prompt

    def _build_context_from_history(self, conv: Conversation) -> str:
        """从历史消息构建上下文"""
        recent = conv.get_recent_messages(limit=6)
        if len(recent) < 2:
            return ""

        history = ["对话历史（供参考）:"]
        for msg in recent[-5:]:  # 只取最近5条
            role = "用户" if msg.role == "user" else "AI"
            history.append(f"{role}: {msg.content[:100]}")

        # 当前上下文（正在讨论的书籍）
        if conv.context.get("current_book"):
            history.append(f"\n当前讨论的书籍: {conv.context['current_book']}")

        return "\n".join(history)

    # ========== 上下文更新 ==========

    def _update_context(self, conv: Conversation, user_message: str,
                       ai_response: str, intent: str):
        """更新对话上下文（追踪讨论的书籍、主题等）"""
        import re

        # 检测书名《书名》
        book_match = re.search(r"《([^》]+)》", user_message)
        if book_match:
            conv.context["current_book"] = book_match.group(1)

        # 检测用户偏好
        if "喜欢" in user_message or "爱读" in user_message:
            conv.preferences["likes"] = conv.preferences.get("likes", [])
            conv.preferences["likes"].append(user_message)

    # ========== 建议操作 ==========

    def _get_suggested_actions(self, intent: str, conv: Conversation) -> List[Dict]:
        """根据当前意图建议下一步操作"""
        current_book = conv.context.get("current_book", "这本书")

        action_map = {
            "review": [
                {"text": f"生成《{current_book}》的推荐理由", "icon": "📝"},
                {"text": "分析这本书的主题", "icon": "🧠"},
                {"text": "推荐类似书籍", "icon": "📚"},
            ],
            "recommend": [
                {"text": "给我推荐更多类型", "icon": "🎯"},
                {"text": "分析我的阅读偏好", "icon": "📊"},
                {"text": "生成阅读报告", "icon": "📈"},
            ],
            "analyze": [
                {"text": "生成知识图谱", "icon": "🧠"},
                {"text": "写一篇书评", "icon": "📝"},
                {"text": "推荐相关书籍", "icon": "📚"},
            ],
            "chat": [
                {"text": "帮我写一篇书评", "icon": "📝"},
                {"text": "推荐一些好书", "icon": "🎯"},
                {"text": "生成我的阅读报告", "icon": "📊"},
                {"text": "你能做什么？", "icon": "❓"},
            ],
        }

        return action_map.get(intent, action_map["chat"])

    # ========== 查询和统计 ==========

    def get_conversation(self, conv_id: str) -> Optional[Dict]:
        """获取对话"""
        if conv_id in self.conversations:
            return self.conversations[conv_id].to_dict()
        return None

    def list_conversations(self, user_id: int = None) -> List[Dict]:
        """列出所有对话"""
        convs = []
        for conv in self.conversations.values():
            if user_id is None or conv.user_id == user_id:
                convs.append({
                    "id": conv.id,
                    "message_count": len(conv.messages),
                    "last_updated": datetime.fromtimestamp(conv.last_updated).strftime("%Y-%m-%d %H:%M:%S"),
                    "preview": conv.messages[-1].content[:50] if conv.messages else "",
                })
        return sorted(convs, key=lambda x: x["last_updated"], reverse=True)

    def get_stats(self) -> Dict:
        """统计信息"""
        total_messages = sum(len(c.messages) for c in self.conversations.values())
        return {
            "total_conversations": len(self.conversations),
            "total_messages": total_messages,
            "engine_status": self.engine.get_status(),
        }


# ========== 单例 ==========

_conv_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    global _conv_manager
    if _conv_manager is None:
        _conv_manager = ConversationManager()
    return _conv_manager
