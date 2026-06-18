"""
AI 书籍助手 API (v2)
基于 v1 ai/routes.py 迁移到 FastAPI
"""
import os
import re
import time
import logging
from typing import List, Dict, Optional, Tuple
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import json

from app.database import get_db
from app.models import Book, Rating
from app.ml.embedding_service import BookEmbeddingService

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str


# ============ 配置 ============
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "60"))
SEARCH_TOP_K = 15
RECOMMEND_TOP_K = 6

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


def detect_intent(text: str) -> str:
    t = (text or "").strip().lower()
    if not t:
        return "unknown"
    for intent, kws in _INTENT_RULES:
        for kw in kws:
            if kw.lower() in t:
                return intent
    if re.search(r"[《「\"']", text):
        return "detail"
    if len(t) < 6 and not any(p in t for p in ["？", "?", "吗"]):
        return "detail"
    return "search"


def extract_book_keyword(text: str) -> str:
    m = re.search(r"[《「\"'](.{1,80}?)[》」\"']", text or "")
    if m:
        return m.group(1).strip()
    cleaned = re.sub(
        r"(你好|请问|帮我|告诉|一下|介绍|推荐|我想知道|我想找|这本书|那本书|有什么|有哪些|吗|呢|啊|呀|的书|关于|关于这本书)",
        "", text or "", flags=re.IGNORECASE
    ).strip()
    cleaned = re.sub(r"[《》「」\"'？?,，。.!！]", "", cleaned).strip()
    return cleaned[:60]


# ============ 书籍检索 ============
def search_by_title(db: Session, keyword: str, top_k: int = 5) -> List[Dict]:
    if not keyword:
        return []
    try:
        rows = db.query(Book).filter(Book.title.ilike(f"%{keyword}%")).limit(top_k).all()
        return [_book_to_card(r, match_reason=f"书名包含关键词「{keyword[:20]}」") for r in rows]
    except Exception as e:
        logger.warning(f"search_by_title 失败: {e}")
        return []


def search_by_author(db: Session, keyword: str, top_k: int = 5) -> List[Dict]:
    if not keyword:
        return []
    try:
        rows = db.query(Book).filter(Book.author.ilike(f"%{keyword}%")).limit(top_k).all()
        return [_book_to_card(r, match_reason=f"作者名包含「{keyword[:20]}」") for r in rows]
    except Exception as e:
        logger.warning(f"search_by_author 失败: {e}")
        return []


def search_by_category(db: Session, keyword: str, top_k: int = 5) -> List[Dict]:
    if not keyword:
        return []
    try:
        rows = db.query(Book).filter(Book.category.ilike(f"%{keyword}%")).limit(top_k).all()
        return [_book_to_card(r, match_reason=f"分类包含「{keyword[:20]}」") for r in rows]
    except Exception as e:
        logger.warning(f"search_by_category 失败: {e}")
        return []


def search_popular(db: Session, top_k: int = 6) -> List[Dict]:
    """图书馆热门高分书籍"""
    try:
        rows = (
            db.query(Book, func.avg(Rating.rating).label("avg_r"), func.count(Rating.id).label("cnt"))
            .outerjoin(Rating, Rating.book_id == Book.id)
            .group_by(Book.id)
            .order_by(func.count(Rating.id).desc(), func.avg(Rating.rating).desc())
            .limit(top_k * 3)
            .all()
        )
        rows_sorted = sorted(rows, key=lambda r: (-(r[1] or 0), -(r[2] or 0)))[:top_k]
        return [_book_to_card(book, avg_rating=avg_r, rating_count=cnt, match_reason="图书馆热门高分")
                for book, avg_r, cnt in rows_sorted]
    except Exception as e:
        logger.warning(f"search_popular 失败: {e}")
        return []


def get_book_by_id(db: Session, book_id: int) -> Optional[Dict]:
    try:
        row = db.query(Book).filter(Book.id == book_id).first()
        if not row:
            return None
        return _book_to_card(row, match_reason="书籍详情")
    except Exception as e:
        logger.warning(f"get_book_by_id 失败: {e}")
        return None


def _book_to_card(book: Book, avg_rating=None, rating_count=None,
                  similarity=None, match_reason=None) -> Dict:
    """Book 模型转前端卡片格式"""
    if avg_rating is None or rating_count is None:
        try:
            stats = db.query(
                func.avg(Rating.rating), func.count(Rating.id)
            ).filter(Rating.book_id == book.id).first()
            avg_rating = stats[0] if stats else 0.0
            rating_count = stats[1] if stats else 0
        except Exception:
            avg_rating = 0.0
            rating_count = 0

    return {
        "book_id": book.id,
        "title": book.title or "",
        "author": book.author or "",
        "category": book.category or "未分类",
        "year": book.year or 0,
        "publisher": book.publisher or "",
        "image_url": book.image_url or "",
        "avg_rating": round(float(avg_rating or 0.0), 2),
        "rating_count": int(rating_count or 0),
        "similarity": round(float(similarity), 3) if similarity is not None else None,
        "match_reason": match_reason,
    }


def _tokenize_query(query: str) -> List[str]:
    """极简分词"""
    raw = [x for x in re.split(r"[\s\-_/\\,，。.!！?？；;：:()（）\[\]【】《》\"'`~]+",
                                query or "") if x]
    tokens = []
    for piece in raw:
        if re.match(r"^[A-Za-z0-9]+$", piece) and len(piece) >= 2:
            tokens.append(piece)
        else:
            for L in (3, 2):
                for i in range(0, max(0, len(piece) - L + 1)):
                    tokens.append(piece[i:i + L])
    seen = set()
    out = []
    for t in tokens:
        if t not in seen and 2 <= len(t) <= 30:
            seen.add(t)
            out.append(t)
        if len(out) >= 10:
            break
    return out


def semantic_search(db: Session, query: str, top_k: int = None) -> List[Dict]:
    """语义 + 关键词混合搜索"""
    if top_k is None:
        top_k = SEARCH_TOP_K

    seen_ids = set()
    combined: List[Dict] = []

    def _extend(cards: List[Dict], reason_override: str = None):
        for c in cards:
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

    q = (query or "").strip()
    if q:
        _extend(search_by_title(db, q, top_k=top_k), reason_override=f"书名匹配「{q[:24]}」")
        if len(combined) < top_k:
            _extend(search_by_author(db, q, top_k=top_k // 2), reason_override=f"作者匹配「{q[:24]}」")
        if len(combined) < top_k:
            _extend(search_by_category(db, q, top_k=top_k // 2), reason_override=f"分类匹配「{q[:24]}」")

    tokens = _tokenize_query(query)
    for tok in tokens:
        if len(combined) >= top_k:
            break
        _extend(search_by_title(db, tok, top_k=top_k // 2))
        if len(combined) < top_k:
            _extend(search_by_author(db, tok, top_k=max(1, top_k // 3)))
        if len(combined) < top_k:
            _extend(search_by_category(db, tok, top_k=max(1, top_k // 3)))

    # FAISS 语义搜索补充（如果有 embedding_service）
    if len(combined) < top_k:
        try:
            # TODO: 集成 v2 embedding_service
            pass
        except Exception as e:
            logger.info(f"FAISS 语义搜索不可用: {e}")

    if len(combined) < max(3, top_k // 2):
        _extend(search_popular(db, top_k=top_k))

    return combined[:top_k]


# ============ LLM 调用 ============
def ollama_available() -> bool:
    try:
        import requests
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def ollama_generate(prompt: str, system: str = None,
                   temperature: float = 0.7, max_tokens: int = 800) -> str:
    if not prompt:
        return ""
    try:
        import requests
        payload = {
            "model": OLLAMA_MODEL,
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
        r = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            return (data.get("response") or "").strip()
    except Exception as e:
        logger.warning(f"ollama_generate 失败: {e}")
    return ""


# ============ 提示词构建 ============
def build_prompt_for_recommend(user_message: str, books: List[Dict]) -> Tuple[str, str]:
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


def build_prompt_for_detail(user_message: str, book: Dict) -> Tuple[str, str]:
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
        "只使用下方「基本资料」里的信息来回答，不要编造不存在的内容。"
        "回答结构：先一句话推荐，再简要概述主题/内容，最后说明适合人群。"
        "中文回答，控制在 250 字以内。"
    )
    prompt = (
        f"用户想了解：「{user_message}」\n\n"
        f"该书的基本资料：\n{info_block}\n\n"
        f"请基于以上资料，用自然、有吸引力的中文介绍这本书。"
    )
    return system, prompt


def build_prompt_for_search(user_message: str, books: List[Dict]) -> Tuple[str, str]:
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


# ============ 模板回复 ============
def template_reply(intent: str, user_message: str, books: List[Dict]) -> str:
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


# ============ RAG 主流程 ============
def rag_chat(user_message: str, db: Session) -> Dict:
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

    intent = detect_intent(msg)
    keyword = extract_book_keyword(msg)
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
        books = search_popular(db, top_k=3)
        retrieved_count = len(books)

    elif intent == "thanks":
        reply = "不客气！祝你阅读愉快 📖。如果还想找别的书，随时告诉我。"

    elif intent == "detail":
        title_matches = search_by_title(db, keyword, top_k=3)
        author_matches = [] if not keyword else search_by_author(db, keyword, top_k=3)
        combined = title_matches + [b for b in author_matches if b["book_id"] not in
                                     {x["book_id"] for x in title_matches}]
        retrieved_count = len(combined)
        if combined:
            books = [combined[0]]
        else:
            books = semantic_search(db, msg, top_k=3)
            retrieved_count = len(books)

    elif intent in ("recommend", "similar"):
        semantic = semantic_search(db, msg, top_k=SEARCH_TOP_K)
        retrieved_count = len(semantic)
        if semantic:
            scored = sorted(
                semantic,
                key=lambda b: (-(b.get("similarity") or 0),
                               -(b.get("rating_count") or 0),
                               -(b.get("avg_rating") or 0))
            )
            books = scored[:RECOMMEND_TOP_K]
        else:
            books = search_popular(db, top_k=RECOMMEND_TOP_K)
            retrieved_count = len(books)

    else:
        books = semantic_search(db, msg, top_k=RECOMMEND_TOP_K)
        retrieved_count = len(books)

    # ---- 生成分支 ----
    if reply:
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
        system, prompt = None, None
        if intent == "detail":
            system, prompt = build_prompt_for_detail(msg, books[0])
        elif intent in ("recommend", "similar"):
            system, prompt = build_prompt_for_recommend(msg, books)
        else:
            system, prompt = build_prompt_for_search(msg, books)

        llm_text = ""
        if prompt and ollama_available():
            llm_text = ollama_generate(prompt, system=system, temperature=0.7)

        if llm_text and len(llm_text) > 10:
            reply = llm_text
        else:
            reply = template_reply(intent, msg, books)

    return {
        "success": True,
        "intent": intent,
        "reply": reply,
        "books": books,
        "retrieved_count": retrieved_count,
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


# ============ API 路由 ============
@router.get("/ai/status")
def ai_status(db: Session = Depends(get_db)):
    """AI 引擎状态"""
    result = {
        "success": True,
        "ollama": {
            "available": ollama_available(),
            "model": OLLAMA_MODEL,
        },
        "library": {"total_books": 0, "total_ratings": 0},
        "version": "2.2.0",
    }
    try:
        result["library"]["total_books"] = db.query(Book).count()
        result["library"]["total_ratings"] = db.query(Rating).count()
    except Exception:
        pass
    return result


@router.post("/ai/chat")
def ai_chat(chat_req: ChatRequest, db: Session = Depends(get_db)):
    """AI 对话主入口"""
    message = (chat_req.message or "").strip()
    if not message:
        return {"success": False, "error": "message 必填"}
    return rag_chat(message, db)


@router.get("/ai/search")
def ai_search(q: str = Query(...), limit: int = Query(15, ge=1, le=50), db: Session = Depends(get_db)):
    """语义搜索书籍"""
    books = semantic_search(db, q, top_k=limit)
    return {"success": True, "query": q, "books": books, "count": len(books)}


@router.get("/ai/popular")
def ai_popular(limit: int = Query(10, ge=1, le=30), db: Session = Depends(get_db)):
    """热门书籍推荐"""
    books = search_popular(db, top_k=limit)
    return {"success": True, "books": books, "count": len(books)}


@router.get("/ai/health")
def ai_health():
    """健康检查"""
    return {"success": True, "ollama": ollama_available(), "service": "ai-assistant", "version": "2.2.0"}
