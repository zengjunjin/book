"""AI 书籍助手 - 核心路由 & RAG 引擎

路由结构（由 Flask app 在 /api/ai 下挂载 Blueprint）：
  GET  /status                引擎状态（Ollama / FAISS / 图书馆统计）
  POST /chat                  对话主入口（RAG）
  POST /chat/stream           流式对话（SSE）
  GET  /search?q=...&limit=5  语义搜索
  POST /ask/<book_id>         针对某本书的问答
  GET  /recommend/<user_id>   为指定用户生成推荐
  GET  /health                健康检查

响应 JSON 契约（给前端的）：
  {
    "success": true,
    "intent": "detail|recommend|similar|search|greeting|thanks|unknown",
    "reply": "自然语言回复字符串",
    "books": [              // 推荐 / 详情 / 搜索时返回的书籍卡片列表
      {
        "book_id": 5001,
        "title": "Classical Mythology",
        "author": "Mark P. O. Morford",
        "category": "Fiction",
        "year": 2000,
        "publisher": "...",
        "image_url": "...",
        "avg_rating": 8.5,      // 0~10
        "rating_count": 123,
        "similarity": 0.92,     // 语义匹配度，仅推荐/搜索返回
        "match_reason": "书名包含关键词"   // 给前端展示的提示
      },
      ...
    ],
    "retrieved_count": 15,   // 语义检索命中数
    "elapsed_ms": 340
  }
"""

import os
import re
import sys
import time
import json
import random
import logging
from typing import List, Dict, Optional, Tuple

from flask import Blueprint, request, jsonify, Response

# --- 模块初始化：让本模块也能直接 python ai/routes.py 跑 ---
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_CURRENT_DIR)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

logger = logging.getLogger(__name__)

# ============ 配置 ============
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_OLLAMA_CHAT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
_OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "60"))

SEARCH_TOP_K = 15            # 语义搜索候选数
RECOMMEND_TOP_K = 6          # 展示给用户的推荐数
SIMILARITY_THRESHOLD = 0.3   # 相似度低于该值的结果将不展示（只影响 FAISS 分支）


# ============ 蓝图 ============
# 注意：app.register_blueprint(ai_bp, url_prefix='/api/ai')
# 因此这里的 route('/chat') 实际暴露为 /api/ai/chat
ai_bp = Blueprint("ai_bp", __name__)


# ============ 工具：数据库 & 模型 ============
def _get_db():
    from extensions import db
    return db


def _get_book_model():
    from models import Book
    return Book


def _get_rating_model():
    from models import Rating
    return Rating


def _row_to_book_card(row, avg_rating=None, rating_count=None,
                      similarity=None, match_reason=None):
    """把 SQLAlchemy Book row / dict 统一转换成前端可消费的卡片结构。"""
    book_id = int(getattr(row, "id", 0) or 0)
    title = getattr(row, "title", "") or ""
    author = getattr(row, "author", "") or ""
    category = getattr(row, "category", "") or "未分类"
    year = getattr(row, "year", None) or 0
    publisher = getattr(row, "publisher", "") or ""
    image_url = getattr(row, "image_url", "") or ""

    # 如果评分没传进来，尝试查一下
    if avg_rating is None or rating_count is None:
        try:
            db = _get_db()
            Rating = _get_rating_model()
            from sqlalchemy import func
            stats = db.session.query(
                func.avg(Rating.rating), func.count(Rating.id)
            ).filter(Rating.book_id == book_id).first()
            avg_rating = stats[0]
            rating_count = stats[1]
        except Exception:
            avg_rating = avg_rating or 0.0
            rating_count = rating_count or 0

    card = {
        "book_id": book_id,
        "title": title,
        "author": author,
        "category": category,
        "year": int(year) if year else 0,
        "publisher": publisher,
        "image_url": image_url,
        "avg_rating": round(float(avg_rating or 0.0), 2),
        "rating_count": int(rating_count or 0),
        "similarity": round(float(similarity), 3) if similarity is not None else None,
        "match_reason": match_reason,
    }
    return card


# ============ 意图识别 ============
_INTENT_RULES = [
    ("recommend", ["推荐", "荐书", "有什么书", "给我推荐", "有哪些", "推荐书",
                   "推荐几本", "想读", "想看", "找书", "recommend", "suggest"]),
    ("similar",   ["相似", "类似", "相近", "同类型", "像...这样", "similar", "like"]),
    ("detail",    ["介绍", "详情", "关于这本书", "讲讲", "简介", "什么书", "写什么",
                   "内容", "about", "summary", "介绍一下"]),
    ("greeting",  ["你好", "hello", "hi", "嗨", "您好", "在吗"]),
    ("thanks",    ["谢谢", "thank", "thanks", "不错", "很好"]),
]


def _detect_intent(text: str) -> str:
    t = (text or "").strip().lower()
    if not t:
        return "unknown"
    for intent, kws in _INTENT_RULES:
        for kw in kws:
            if kw.lower() in t:
                return intent
    # 如果包含书名号或引号包裹 -> 视为书籍详情查询
    if re.search(r"[《「\"']", text):
        return "detail"
    # 如果内容很短 (< 6 个字) 也视为直接查询书籍
    if len(t) < 6 and not any(p in t for p in ["？", "?", "吗"]):
        return "detail"
    return "search"


def _extract_book_keyword(text: str) -> str:
    """从用户问题里提取书籍检索关键词。
    优先使用书名号/引号中的内容；否则去掉语气词后作为关键词。"""
    m = re.search(r"[《「\"'](.{1,80}?)[》」\"']", text or "")
    if m:
        return m.group(1).strip()
    # 兜底：去语气词 & 前后缀后返回
    cleaned = re.sub(r"(你好|请问|帮我|告诉|一下|介绍|推荐|我想知道|我想找|这本书|那本书|有什么|有哪些|吗|呢|啊|呀|的书|关于|关于这本书)",
                     "", text or "", flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"[《》「」\"'？?,，。.!！]", "", cleaned).strip()
    return cleaned[:60]


# ============ 检索：书名精确/模糊匹配 ============
def _search_by_title(keyword: str, top_k: int = 5) -> List[Dict]:
    """书名关键词检索，返回卡片。使用 LIKE 做模糊匹配。"""
    if not keyword:
        return []
    try:
        Book = _get_book_model()
        rows = Book.query.filter(Book.title.ilike(f"%{keyword}%")).limit(top_k).all()
        cards = []
        for r in rows:
            cards.append(_row_to_book_card(r, match_reason=f"书名包含关键词“{keyword[:20]}”"))
        return cards
    except Exception as e:
        logger.warning(f"_search_by_title 失败: {e}")
        return []


def _search_by_author(keyword: str, top_k: int = 5) -> List[Dict]:
    if not keyword:
        return []
    try:
        Book = _get_book_model()
        rows = Book.query.filter(Book.author.ilike(f"%{keyword}%")).limit(top_k).all()
        cards = []
        for r in rows:
            cards.append(_row_to_book_card(r, match_reason=f"作者名包含“{keyword[:20]}”"))
        return cards
    except Exception as e:
        logger.warning(f"_search_by_author 失败: {e}")
        return []


def _search_by_category(keyword: str, top_k: int = 5) -> List[Dict]:
    if not keyword:
        return []
    try:
        Book = _get_book_model()
        rows = Book.query.filter(Book.category.ilike(f"%{keyword}%")).limit(top_k).all()
        cards = []
        for r in rows:
            cards.append(_row_to_book_card(r, match_reason=f"分类包含“{keyword[:20]}”"))
        return cards
    except Exception as e:
        logger.warning(f"_search_by_category 失败: {e}")
        return []


# ============ 检索："热门 / 高分" 作为兜底推荐 ============
def _search_popular(top_k: int = 6) -> List[Dict]:
    """图书馆里评分最高、评价人数较多的书。"""
    try:
        from sqlalchemy import func
        Book = _get_book_model()
        Rating = _get_rating_model()
        db = _get_db()
        rows = (
            db.session.query(Book, func.avg(Rating.rating).label("avg_r"), func.count(Rating.id).label("cnt"))
            .join(Rating, Rating.book_id == Book.id, isouter=True)
            .group_by(Book.id)
            .order_by(func.count(Rating.id).desc(), func.avg(Rating.rating).desc())
            .limit(top_k * 3)
            .all()
        )
        # 按 (评分人数, 平均评分) 排序，取 top_k
        rows_sorted = sorted(rows, key=lambda r: (-(r[2] or 0), -(r[1] or 0)))[:top_k]
        cards = []
        for book, avg_r, cnt in rows_sorted:
            cards.append(_row_to_book_card(
                book, avg_rating=avg_r, rating_count=cnt,
                match_reason="图书馆热门高分"
            ))
        return cards
    except Exception as e:
        logger.warning(f"_search_popular 失败: {e}")
        return []


def _search_recent(top_k: int = 6) -> List[Dict]:
    """按出版年份倒序（新版书优先）。"""
    try:
        Book = _get_book_model()
        rows = Book.query.filter(Book.year != None).order_by(Book.year.desc()).limit(top_k).all()
        cards = [_row_to_book_card(r, match_reason=f"{r.year} 年出版") for r in rows]
        return cards
    except Exception as e:
        logger.warning(f"_search_recent 失败: {e}")
        return []


# ============ 检索：FAISS 语义搜索 + 字符串关键词 fallback ============
def _semantic_search(query: str, top_k: int = None) -> List[Dict]:
    """语义 + 关键词混合搜索。
    顺序：
      1) 对整句做书名/作者/分类 LIKE 匹配 —— 对英文书 / 明确关键词最可靠
      2) 对分词后的 tokens 再做一轮 LIKE 匹配
      3) 用 FAISS 向量搜索补充（结果会做信息完整性校验）
      4) 还不够 -> 用热门高分书籍兜底
    """
    if top_k is None:
        top_k = SEARCH_TOP_K

    seen_ids = set()
    combined: List[Dict] = []

    def _extend(cards: List[Dict], reason_override: str = None):
        for c in cards:
            # 基础校验：必须有 book_id 和 title
            if not c.get("book_id") or not c.get("title"):
                continue
            if c["book_id"] in seen_ids:
                continue
            seen_ids.add(c["book_id"])
            if reason_override:
                c["match_reason"] = reason_override
            combined.append(c)
            if len(combined) >= top_k:
                return

    # 1) 整句精确 / 模糊匹配
    q = (query or "").strip()
    if q:
        _extend(_search_by_title(q, top_k=top_k), reason_override=f"书名匹配“{q[:24]}”")
        if len(combined) < top_k:
            _extend(_search_by_author(q, top_k=top_k // 2),
                    reason_override=f"作者匹配“{q[:24]}”")
        if len(combined) < top_k:
            _extend(_search_by_category(q, top_k=top_k // 2),
                    reason_override=f"分类匹配“{q[:24]}”")

    # 2) 分词匹配
    tokens = _tokenize_query(query)
    for tok in tokens:
        if len(combined) >= top_k:
            break
        _extend(_search_by_title(tok, top_k=top_k // 2))
        if len(combined) >= top_k:
            break
        _extend(_search_by_author(tok, top_k=max(1, top_k // 3)))
        if len(combined) >= top_k:
            break
        _extend(_search_by_category(tok, top_k=max(1, top_k // 3)))

    # 3) FAISS 向量搜索（仅做补充，且必须校验结果完整性）
    if len(combined) < top_k:
        try:
            from services.embedding_service import get_embedding_service
            svc = get_embedding_service()
            if svc is not None and getattr(svc, "faiss_ready", False):
                results = svc.find_similar_books_by_text(
                    query, top_k=top_k, threshold=SIMILARITY_THRESHOLD
                ) or []
                valid = []
                for item in results:
                    bid = int(item.get("book_id") or 0)
                    title = (item.get("title") or "").strip()
                    if bid <= 0 or not title:
                        # FAISS 返回的条目缺失基础信息 -> 用数据库补一下
                        if bid > 0:
                            fresh = _get_book_by_id(bid)
                            if fresh and fresh.get("title"):
                                fresh["similarity"] = item.get("similarity")
                                fresh["match_reason"] = "语义搜索"
                                valid.append(fresh)
                        continue
                    valid.append(_row_to_book_card(
                        item,
                        avg_rating=item.get("avg_rating"),
                        rating_count=item.get("rating_count"),
                        similarity=item.get("similarity"),
                        match_reason="语义搜索",
                    ))
                _extend(valid)
        except Exception as e:
            logger.info(f"_semantic_search: FAISS 路径不可用: {e}")

    # 4) 还不够 -> 用热门书兜底（确保至少有推荐）
    if len(combined) < max(3, top_k // 2):
        _extend(_search_popular(top_k=top_k))

    return combined[:top_k]


def _tokenize_query(query: str) -> List[str]:
    """极简分词：按标点、空白切分；英文词直接保留，中文按 2-3 字切出 N-gram。"""
    raw = [x for x in re.split(r"[\s\-_/\\,，。.!！?？；;：:()（）\[\]【】《》\"'`~]+",
                                query or "") if x]
    tokens = []
    for piece in raw:
        if re.match(r"^[A-Za-z0-9]+$", piece) and len(piece) >= 2:
            tokens.append(piece)
        else:
            # 中文/混合文本：生成 2-3 字窗口
            for L in (3, 2):
                for i in range(0, max(0, len(piece) - L + 1)):
                    tokens.append(piece[i:i + L])
    # 去重 + 截断
    seen = set()
    out = []
    for t in tokens:
        if t not in seen and 2 <= len(t) <= 30:
            seen.add(t)
            out.append(t)
        if len(out) >= 10:
            break
    return out


# ============ 检索：按 ID 取单本书详情 ============
def _get_book_by_id(book_id: int) -> Optional[Dict]:
    try:
        Book = _get_book_model()
        row = Book.query.get(int(book_id))
        if not row:
            return None
        return _row_to_book_card(row, match_reason="书籍详情")
    except Exception as e:
        logger.warning(f"_get_book_by_id 失败: {e}")
        return None


# ============ LLM: Ollama 调用 ============
def _ollama_available() -> bool:
    try:
        import requests
        r = requests.get(f"{_OLLAMA_HOST}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _ollama_generate(prompt: str, system: str = None,
                     temperature: float = 0.7, max_tokens: int = 800) -> str:
    if not prompt:
        return ""
    try:
        import requests
        payload = {
            "model": _OLLAMA_CHAT_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 2048,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system
        r = requests.post(f"{_OLLAMA_HOST}/api/generate", json=payload,
                          timeout=_OLLAMA_TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            text = (data.get("response") or "").strip()
            return text
    except Exception as e:
        logger.warning(f"_ollama_generate 失败: {e}")
    return ""


# ============ 提示词构建 ============
def _build_prompt_for_recommend(user_message: str, books: List[Dict]) -> Tuple[str, str]:
    book_lines = []
    for i, b in enumerate(books[:8], start=1):
        line = f"{i}. 《{b['title']}》"
        if b.get("author"):
            line += f"  by {b['author']}"
        if b.get("year"):
            line += f"  ({b['year']})"
        if b.get("category") and b["category"] != "未分类":
            line += f"  [{b['category']}]"
        if b.get("avg_rating"):
            line += f"  评分 {b['avg_rating']}/10 ({b.get('rating_count', 0)}人评价)"
        book_lines.append(line)
    system = (
        "你是一位友善、专业的书店导购员。"
        "只使用用户给你的书籍清单来进行推荐，不要虚构不存在的书。"
        "回答中请把每本书的要点说清楚（作者、主题、适合人群等）。"
        "语言自然，不要机械套模板。中文回答，控制在 300 字以内。"
    )
    prompt = (
        f"用户说：「{user_message}」\n\n"
        f"图书馆里找到了以下相关书籍：\n"
        f"{chr(10).join(book_lines)}\n\n"
        f"请从以上书籍中挑出最合适的 3-5 本，用自然中文推荐给用户，"
        f"简要说明每本书为什么值得读。不要输出不存在的书。"
    )
    return system, prompt


def _build_prompt_for_detail(user_message: str, book: Dict) -> Tuple[str, str]:
    info = []
    info.append(f"书名：《{book.get('title', '')}》")
    if book.get("author"):
        info.append(f"作者：{book['author']}")
    if book.get("year"):
        info.append(f"出版年份：{book['year']}")
    if book.get("publisher"):
        info.append(f"出版社：{book['publisher']}")
    if book.get("category") and book["category"] != "未分类":
        info.append(f"分类：{book['category']}")
    if book.get("avg_rating"):
        info.append(f"平均评分：{book['avg_rating']}/10（{book.get('rating_count', 0)} 人评价）")
    info_block = "\n".join(info)

    system = (
        "你是一位热爱阅读、善于总结的书店导购。"
        "只使用下方“基本资料”里的信息来回答，不要编造不存在的内容。"
        "回答结构：先一句话推荐，再简要概述主题/内容，最后说明适合人群。"
        "中文回答，控制在 250 字以内。"
    )
    prompt = (
        f"用户想了解：「{user_message}」\n\n"
        f"该书的基本资料：\n{info_block}\n\n"
        f"请基于以上资料，用自然、有吸引力的中文介绍这本书。"
    )
    return system, prompt


def _build_prompt_for_search(user_message: str, books: List[Dict]) -> Tuple[str, str]:
    book_lines = [f"{i+1}. 《{b['title']}》  by {b.get('author','')}" for i, b in enumerate(books[:8])]
    system = (
        "你是一位乐于助人的书店导购。基于下面的真实书籍清单，"
        "用简洁的中文为用户总结最相关的 3-5 本，给出简短的推荐理由。"
    )
    prompt = (
        f"用户搜索：「{user_message}」\n\n"
        f"图书馆检索结果：\n{chr(10).join(book_lines)}\n\n"
        f"请向用户推荐最相关的 3-5 本并简述理由。"
    )
    return system, prompt


# ============ RAG 主流程 ============
def _rag_chat(user_message: str) -> Dict:
    t0 = time.time()
    msg = (user_message or "").strip()
    if not msg:
        return {
            "success": False,
            "error": "消息不能为空",
            "reply": "你想聊点什么？可以问我推荐书、或描述你想看的主题～",
            "books": [],
            "intent": "unknown",
            "retrieved_count": 0,
        }

    intent = _detect_intent(msg)
    keyword = _extract_book_keyword(msg)
    books: List[Dict] = []
    retrieved_count = 0
    reply = ""

    # ---- 检索分支 ----
    if intent == "greeting":
        reply = (
            "你好！我是你的图书 AI 助手 📚\n"
            "我可以帮你做这些：\n"
            "• 回答具体某本书的信息，比如「《Harry Potter》讲什么」\n"
            "• 根据主题推荐书，比如「推荐几本关于历史的书」\n"
            "• 找某位作者的作品，比如「找几本 J. K. Rowling 的书」\n"
            "试试看，告诉我你想找什么样的书？"
        )
        books = _search_popular(top_k=3)
        retrieved_count = len(books)

    elif intent == "thanks":
        reply = "不客气！祝你阅读愉快 📖。如果还想找别的书，随时告诉我。"

    elif intent == "detail":
        # 精准书名查询
        title_matches = _search_by_title(keyword, top_k=3)
        author_matches = [] if not keyword else _search_by_author(keyword, top_k=3)
        combined = title_matches + [b for b in author_matches if b["book_id"] not in
                                     {x["book_id"] for x in title_matches}]
        retrieved_count = len(combined)
        if combined:
            books = [combined[0]]  # 详情模式只展示一本最相关的
        else:
            # 完全匹配不到 -> 再试一遍语义/热门
            books = _semantic_search(msg, top_k=3)
            retrieved_count = len(books)

    elif intent in ("recommend", "similar"):
        # 语义搜索 -> 个性化推荐
        semantic = _semantic_search(msg, top_k=SEARCH_TOP_K)
        retrieved_count = len(semantic)
        if semantic:
            # 按评分 & 评价人数二次挑选
            scored = sorted(
                semantic,
                key=lambda b: (-(b.get("similarity") or 0),
                               -(b.get("rating_count") or 0),
                               -(b.get("avg_rating") or 0))
            )
            books = scored[:RECOMMEND_TOP_K]
        else:
            # 搜索不到 -> 用热门兜底
            books = _search_popular(top_k=RECOMMEND_TOP_K)
            retrieved_count = len(books)

    else:  # search / unknown
        books = _semantic_search(msg, top_k=RECOMMEND_TOP_K)
        retrieved_count = len(books)

    # ---- 生成分支 ----
    if reply:  # greeting/thanks 已经写好
        pass
    elif not books:
        reply = (
            f"抱歉，我没能在图书馆找到与「{msg[:40]}」相关的书籍。\n"
            f"你可以试试：\n"
            f"• 换一个关键词（比如书名、作者或主题）\n"
            f"• 问「推荐几本热门的书」，我会帮你推荐高分书籍\n"
            f"• 用英文书名试试，图书馆里英文图书较多"
        )
    else:
        # 先尝试 LLM 生成
        system, prompt = None, None
        if intent == "detail":
            system, prompt = _build_prompt_for_detail(msg, books[0])
        elif intent in ("recommend", "similar"):
            system, prompt = _build_prompt_for_recommend(msg, books)
        else:
            system, prompt = _build_prompt_for_search(msg, books)

        llm_text = ""
        if prompt and _ollama_available():
            llm_text = _ollama_generate(prompt, system=system, temperature=0.7)

        if llm_text and len(llm_text) > 10:
            reply = llm_text
        else:
            # LLM 不可用或回复过短 -> 模板回复（保证功能不依赖 LLM）
            reply = _template_reply(intent, msg, books)

    # ---- 组装返回 ----
    return {
        "success": True,
        "intent": intent,
        "reply": reply,
        "books": books,
        "retrieved_count": retrieved_count,
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


def _template_reply(intent: str, user_message: str, books: List[Dict]) -> str:
    """当 LLM 不可用时，用模板回复兜底。"""
    if not books:
        return "（系统繁忙，暂时无法调用语言模型，请稍后再试。）"

    if intent == "detail":
        b = books[0]
        parts = [f"《{b['title']}》"]
        if b.get("author"):
            parts.append(f"作者是 {b['author']}")
        if b.get("year"):
            parts.append(f"{b['year']} 年出版")
        if b.get("category") and b["category"] != "未分类":
            parts.append(f"属于 {b['category']} 分类")
        if b.get("avg_rating"):
            parts.append(f"平均评分 {b['avg_rating']}/10（{b.get('rating_count', 0)} 人评价）")
        return "这是从图书馆里查到的信息：\n" + "；\n".join(parts) + "。"

    # recommend / similar / search
    lines = ["根据你的需求，我从图书馆里挑出以下几本书：\n"]
    for i, b in enumerate(books[:6], start=1):
        line = f"{i}. 《{b['title']}》"
        if b.get("author"):
            line += f" —— {b['author']}"
        if b.get("category") and b["category"] != "未分类":
            line += f"（{b['category']}）"
        if b.get("avg_rating"):
            line += f"  ⭐ {b['avg_rating']}/10"
        if b.get("match_reason"):
            line += f"  [{b['match_reason']}]"
        lines.append(line)
    return "\n".join(lines)


# ============ 模块初始化（供 app.py 的 init_ai_module 调用） ============
def init_ai_module():
    """惰性初始化：打印一行日志，不做 heavy 操作。"""
    logger.info("[AI] 模块初始化完成")


# ============================================================
#                    F L A S K   路由
# ============================================================
@ai_bp.route("/status", methods=["GET"])
def status_endpoint():
    result = {
        "success": True,
        "ollama": {
            "available": _ollama_available(),
            "model": _OLLAMA_CHAT_MODEL,
        },
        "library": {"total_books": 0, "total_ratings": 0},
        "faiss": {"available": False, "index_size": 0, "model": None},
        "version": "2.1.0",
    }
    try:
        Book = _get_book_model()
        Rating = _get_rating_model()
        result["library"]["total_books"] = int(Book.query.count())
        result["library"]["total_ratings"] = int(Rating.query.count())
    except Exception:
        pass
    try:
        from services.embedding_service import get_embedding_service
        svc = get_embedding_service()
        if svc is not None:
            result["faiss"]["available"] = bool(getattr(svc, "faiss_ready", False))
            result["faiss"]["index_size"] = int(getattr(svc, "index_size", 0) or 0)
            if getattr(svc, "use_ollama", None):
                result["faiss"]["model"] = "ollama-embedding"
            elif getattr(svc, "use_sentence_transformers", None):
                result["faiss"]["model"] = "sentence-transformers"
            else:
                result["faiss"]["model"] = "tf-idf"
    except Exception:
        pass
    return jsonify(result)


@ai_bp.route("/chat", methods=["POST"])
def chat_endpoint():
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"success": False, "error": "message 必填"}), 400
    result = _rag_chat(message)
    # 兼容可能旧前端期望的字段名
    return jsonify(result)


@ai_bp.route("/chat/stream", methods=["POST"])
def chat_stream_endpoint():
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"success": False, "error": "message 必填"}), 400

    rag_result = _rag_chat(message)
    reply_text = rag_result.get("reply") or ""
    books_meta = rag_result.get("books") or []

    def _emit_chunk(chunk: str):
        return (
            f"data: {json.dumps({'type': 'chunk', 'text': chunk}, ensure_ascii=False)}\n\n"
        ).encode("utf-8")

    def _emit_meta(kind: str, payload: Dict):
        return (
            f"data: {json.dumps({'type': kind, 'data': payload}, ensure_ascii=False)}\n\n"
        ).encode("utf-8")

    def _generator():
        yield _emit_meta("status", {
            "intent": rag_result.get("intent"),
            "books": books_meta,
            "retrieved_count": rag_result.get("retrieved_count", 0),
        })

        if _ollama_available():
            # 真实流式：把 Ollama 的 chunks 透传
            try:
                import requests
                system, prompt = _build_prompt_for_recommend(message, books_meta) \
                    if books_meta else (None, message)
                payload = {
                    "model": _OLLAMA_CHAT_MODEL,
                    "prompt": prompt,
                    "stream": True,
                    "options": {"temperature": 0.7, "num_ctx": 2048},
                }
                if system:
                    payload["system"] = system
                r = requests.post(f"{_OLLAMA_HOST}/api/generate", json=payload,
                                  stream=True, timeout=_OLLAMA_TIMEOUT)
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line.decode("utf-8"))
                        chunk = obj.get("response") or ""
                        if chunk:
                            yield _emit_chunk(chunk)
                        if obj.get("done"):
                            break
                    except Exception:
                        continue
                yield _emit_meta("done", {})
                return
            except Exception as e:
                logger.warning(f"流式 LLM 失败: {e}")

        # 无 LLM -> 用打字机效果模拟
        for i in range(0, len(reply_text), 2):
            yield _emit_chunk(reply_text[i:i + 2])
            time.sleep(0.02)
        yield _emit_meta("done", {})

    return Response(_generator(), mimetype="text/event-stream")


@ai_bp.route("/search", methods=["GET"])
def search_endpoint():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"success": False, "error": "q 必填"}), 400
    try:
        limit = max(1, min(50, int(request.args.get("limit", SEARCH_TOP_K))))
    except Exception:
        limit = SEARCH_TOP_K

    books = _semantic_search(q, top_k=limit)
    return jsonify({
        "success": True,
        "query": q,
        "books": books,
        "count": len(books),
    })


@ai_bp.route("/ask/<int:book_id>", methods=["GET", "POST"])
def ask_book_endpoint(book_id: int):
    book = _get_book_by_id(book_id)
    if not book:
        return jsonify({"success": False, "error": f"未找到书籍 ID={book_id}"}), 404

    query = ""
    if request.method == "POST":
        query = ((request.get_json() or {}).get("query") or "").strip()
    else:
        query = (request.args.get("q") or "").strip() or "请简单介绍这本书"

    system, prompt = _build_prompt_for_detail(query, book)
    answer = ""
    if _ollama_available():
        answer = _ollama_generate(prompt, system=system, temperature=0.7)
    if not answer:
        answer = _template_reply("detail", query, [book])

    return jsonify({
        "success": True,
        "book": book,
        "answer": answer,
        "query": query,
    })


@ai_bp.route("/recommend/<int:user_id>", methods=["GET", "POST"])
def recommend_user_endpoint(user_id: int):
    t0 = time.time()
    strategy = "hybrid"
    candidates: List[Dict] = []

    # 1) 协同过滤（若可用）
    try:
        from services.cf_algorithm import CollaborativeFiltering
        cf = CollaborativeFiltering()
        if cf and getattr(cf, "user_count", 0) > 0:
            recs = getattr(cf, "recommend", None)
            if recs:
                raw = recs(user_id, n_recommendations=15)
                seen = set()
                for r in raw:
                    bid = int(r.get("book_id") or r.get("id") or 0)
                    if bid and bid not in seen:
                        detail = _get_book_by_id(bid)
                        if detail:
                            detail["recommend_score"] = round(
                                float(r.get("score") or 0), 3
                            )
                            candidates.append(detail)
                            seen.add(bid)
    except Exception as e:
        logger.info(f"协同过滤不可用: {e}")

    # 2) 用热门 + 语义搜索兜底
    if len(candidates) < 6:
        popular = _search_popular(top_k=10)
        for p in popular:
            if not any(c["book_id"] == p["book_id"] for c in candidates):
                p["recommend_score"] = 0.5
                candidates.append(p)
    if len(candidates) < 6:
        strategy = "popular_fallback"

    # 3) 生成推荐理由
    final_list = candidates[:RECOMMEND_TOP_K]
    llm_summary = ""
    if final_list and _ollama_available():
        try:
            lines = [f"{i+1}. 《{b['title']}》 by {b.get('author','')} [{b.get('category','')}]"
                     for i, b in enumerate(final_list[:5])]
            sys_p = "你是一位有品味的书店导购，用简洁的中文总结推荐理由，100 字以内。"
            user_p = f"为用户 #{user_id} 推荐书籍：\n{chr(10).join(lines)}\n请用 2-3 句话总结。"
            llm_summary = _ollama_generate(user_p, system=sys_p, temperature=0.6)
        except Exception:
            pass
    if not llm_summary:
        llm_summary = (
            f"根据图书馆数据，为你挑选了 {len(final_list)} 本高评分、高人气的书籍，"
            f"覆盖多个不同主题，希望你能喜欢。"
        )

    return jsonify({
        "success": True,
        "user_id": user_id,
        "strategy": strategy,
        "recommendations": final_list,
        "recommendation_summary": llm_summary,
        "count": len(final_list),
        "elapsed_ms": int((time.time() - t0) * 1000),
    })


@ai_bp.route("/popular", methods=["GET"])
def popular_endpoint():
    try:
        limit = max(1, min(30, int(request.args.get("limit", "10"))))
    except Exception:
        limit = 10
    books = _search_popular(top_k=limit)
    return jsonify({"success": True, "books": books, "count": len(books)})


@ai_bp.route("/health", methods=["GET"])
def health_endpoint():
    return jsonify({
        "success": True,
        "ollama": _ollama_available(),
        "service": "ai-assistant",
        "version": "2.1.0",
    })


# ============ 命令行调试 ============
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"[i] Ollama 可用: {_ollama_available()}")
    print(f"[i] 模型: {_OLLAMA_CHAT_MODEL}")
    print("\n交互式对话，输入 exit 退出")
    while True:
        try:
            q = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if q.lower() in ("exit", "quit", ""):
            break
        # 必须在 app context 里运行（要查数据库）
        from app import create_app as _create
        _app = _create()
        with _app.app_context():
            r = _rag_chat(q)
        print(f"AI ({r.get('intent')})> {r.get('reply')}")
        for b in r.get("books") or []:
            print(f"   · 《{b.get('title','')}》 by {b.get('author','')} "
                  f"[评分 {b.get('avg_rating', 0)}]")
        print(f"   检索命中: {r.get('retrieved_count', 0)} 本, "
              f"耗时 {r.get('elapsed_ms', 0)} ms")
