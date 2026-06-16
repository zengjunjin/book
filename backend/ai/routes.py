"""
AI 内容创作助手 - API 路由 (Blueprint)
"""

import time
import hashlib
import json
import logging
import random
from flask import Blueprint, request, jsonify, current_app, Response
from flask_limiter.util import get_remote_address

# 创建 AI blueprint
ai_bp = Blueprint('ai', __name__)

logger = logging.getLogger(__name__)

# ========== AI缓存工具 ==========
# AI响应缓存TTL配置（秒）
_AI_TTL = {
    'review': 3600,      # 书评：1小时
    'summary': 3600,     # 摘要：1小时
    'analyze': 3600,     # 分析：1小时
    'knowledge': 7200,   # 知识图谱：2小时（较稳定）
    'search': 600,       # 搜索：10分钟（较动态）
    'report': 1800,      # 阅读报告：30分钟
    'recommend': 1800,   # 推荐理由：30分钟
}


def _ai_cache_key(prefix, *args):
    """生成可复现的缓存键
    格式: ai:review:5001:personal
    """
    key = f"ai:{prefix}:" + ":".join(str(a) for a in args)
    # 过长时做hash保护
    if len(key) > 200:
        key = key[:150] + ':' + hashlib.md5(key.encode()).hexdigest()
    return key


def _try_get_cache(key):
    """从缓存读取"""
    try:
        from services.cache import cache_service
        return cache_service.get(key)
    except Exception:
        return None


def _try_set_cache(key, value, ttl=3600):
    """写入缓存"""
    try:
        from services.cache import cache_service
        cache_service.set(key, value, ttl=ttl)
    except Exception:
        pass


def _with_cache(prefix, key_args, data_func, ttl=None):
    """统一的缓存辅助函数
    返回: (result_dict, cache_hit_bool)
    """
    if ttl is None:
        ttl = _AI_TTL.get(prefix, 3600)
    
    # 支持 refresh=true 强制刷新
    refresh = request.args.get('refresh', '').lower() == 'true' or \
              (request.is_json and (request.get_json() or {}).get('refresh', False))
    
    cache_key = _ai_cache_key(prefix, *key_args)
    
    if not refresh:
        cached = _try_get_cache(cache_key)
        if cached is not None:
            return cached, True
    
    # 未命中，执行实际生成
    result = data_func()
    
    # 成功才缓存
    if result and isinstance(result, dict) and result.get('success', False):
        _try_set_cache(cache_key, result, ttl=ttl)
    
    return result, False


def _ai_response(data, cache_hit=False):
    """包装AI响应，加入X-Cache头信息"""
    resp = jsonify(data)
    resp.headers['X-Cache'] = 'HIT' if cache_hit else 'MISS'
    return resp


# ========== 状态检查 ==========
@ai_bp.route('/status', methods=['GET'])
def ai_status():
    """获取 AI 引擎运行状态 + FAISS 索引状态"""
    try:
        from .llm_engine import get_llm_engine
        from services.embedding_service import get_embedding_service
        llm_status = get_llm_engine().get_status()
        svc = get_embedding_service()
        faiss_info = {
            'model_loaded': svc.model is not None,
            'faiss_ready': svc.faiss_ready,
            'faiss_index_size': svc.index_size,
            'embedding_cache_size': len(svc.book_embeddings),
        }
        return {'success': True, 'llm': llm_status, 'faiss': faiss_info}
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500


# ========== AI 对话流式生成（SSE） ==========
@ai_bp.route('/chat/stream', methods=['POST'])
def ai_chat_stream():
    """流式 AI 对话 - Server-Sent Events
    POST JSON: {prompt, user_id, model}
    返回: text/event-stream
      data: [START]
      data: <chunk>
      ...
      data: [DONE]
    """
    data = request.get_json() or {}
    prompt = (data.get('prompt') or data.get('message') or '').strip()
    user_id = data.get('user_id')
    model = data.get('model')

    def _emit(event_data: str) -> bytes:
        return f'data: {event_data}\n\n'.encode('utf-8')

    def _generate():
        # 1) 首事件 [START]
        try:
            yield _emit('[START]')
        except Exception:
            return

        if not prompt:
            yield _emit('[ERROR] prompt 不能为空')
            return

        # 2) 逐步生成响应内容
        try:
            from .llm_engine import get_llm_engine
            engine = get_llm_engine()

            # 尝试使用 LLM 引擎的流式接口
            engine_ok = False
            try:
                if engine and hasattr(engine, 'ollama_available') and engine.ollama_available and hasattr(engine, 'generate_stream'):
                    engine_ok = True
            except Exception:
                engine_ok = False

            collected_chunks = []

            if engine_ok:
                try:
                    def _on_token(token: str):
                        collected_chunks.append(token)

                    llm_resp = engine.generate_stream(prompt, model=model, callback=_on_token)
                    full_text = getattr(llm_resp, 'content', '') or ''.join(collected_chunks)

                    if not full_text and collected_chunks:
                        full_text = ''.join(collected_chunks)

                    # 按每 3-8 个字符切块，模拟流式逐步输出
                    chunk_size = random.randint(3, 8)
                    pos = 0
                    while pos < len(full_text):
                        piece = full_text[pos:pos + chunk_size]
                        yield _emit(piece)
                        pos += chunk_size
                        chunk_size = random.randint(3, 8)
                        time.sleep(0.02)

                except Exception as e:
                    yield _emit(f'[ERROR] LLM 流式调用失败: {e}')
                    return
            else:
                # 降级到普通 generate 再切片流式输出
                try:
                    llm_resp = engine.generate(prompt, model=model) if engine else None
                    full_text = getattr(llm_resp, 'content', '') if llm_resp else ''
                    if not full_text:
                        # 再次降级：本地规则回复
                        full_text = (
                            f"你好！我收到了你的问题：「{prompt[:80]}」。\n"
                            f"作为书籍 AI 助手，我可以帮你：\n"
                            f"• 生成个性化书评\n"
                            f"• 推荐匹配的书籍\n"
                            f"• 分析书籍内容与主题\n"
                            f"• 生成你的阅读报告\n"
                            f"\n你可以进一步告诉我，你希望从哪个角度入手？"
                        )
                    chunk_size = random.randint(3, 8)
                    pos = 0
                    while pos < len(full_text):
                        piece = full_text[pos:pos + chunk_size]
                        yield _emit(piece)
                        pos += chunk_size
                        chunk_size = random.randint(3, 8)
                        time.sleep(0.02)
                except Exception as e:
                    yield _emit(f'[ERROR] LLM 调用失败: {e}')
                    return
        except Exception as e:
            yield _emit(f'[ERROR] 生成失败: {e}')
            return

        # 3) 结束事件 [DONE]
        yield _emit('[DONE]')

    try:
        return Response(_generate(), mimetype='text/event-stream')
    except Exception as e:
        return Response(f'data: [ERROR] 初始化失败: {e}\n\n', mimetype='text/event-stream')


# ========== 对话功能 ==========
@ai_bp.route('/chat', methods=['POST'])
def ai_chat():
    """处理用户消息并返回 AI 响应"""
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    conv_id = data.get('conversation_id') or f'conv_{int(time.time() * 1000)}'
    user_id = data.get('user_id')

    if not message:
        return {'success': False, 'error': '消息不能为空'}, 400

    try:
        from .conversation import get_conversation_manager
        conv_manager = get_conversation_manager()
        result = conv_manager.handle_message(conv_id, message, user_id)
        return {'success': True, **result}
    except Exception as e:
        return {'success': False, 'error': f'对话处理失败: {str(e)}'}, 500


# ========== 书评生成 ==========
@ai_bp.route('/review/<int:book_id>', methods=['GET', 'POST'])
def ai_review(book_id):
    """为指定书籍生成个性化书评（带缓存）"""
    data = request.get_json() or {}
    style = data.get('style', 'personal')
    # GET请求也支持 style 参数
    if request.method == 'GET':
        style = request.args.get('style', style)

    def _gen():
        try:
            from .review_generator import get_review_generator
            review_gen = get_review_generator()
            review = review_gen.generate(book_id, style=style)
            return {'success': True, 'review': review.to_dict()}
        except Exception as e:
            return {'success': False, 'error': f'书评生成失败: {str(e)}'}

    result, cache_hit = _with_cache('review', [book_id, style], _gen)
    status = 500 if not result.get('success', False) else 200
    return _ai_response(result, cache_hit=cache_hit), status


# ========== 知识图谱 ==========
@ai_bp.route('/knowledge/<int:book_id>', methods=['GET', 'POST'])
def ai_knowledge(book_id):
    """生成书籍的知识图谱/思维导图（带缓存）"""
    def _gen():
        try:
            from .knowledge_graph import get_knowledge_graph_generator
            kg_gen = get_knowledge_graph_generator()
            graph = kg_gen.generate(book_id)
            mermaid = kg_gen.to_mermaid(graph)
            return {'success': True, 'graph': graph.to_dict(), 'mermaid': mermaid}
        except Exception as e:
            return {'success': False, 'error': f'知识图谱生成失败: {str(e)}'}

    result, cache_hit = _with_cache('knowledge', [book_id], _gen)
    status = 500 if not result.get('success', False) else 200
    return _ai_response(result, cache_hit=cache_hit), status


# ========== 阅读报告 ==========
@ai_bp.route('/report/<int:user_id>', methods=['GET', 'POST'])
def ai_report(user_id):
    """为用户生成个性化阅读报告（带缓存）"""
    def _gen():
        try:
            from .report_generator import get_report_generator
            report_gen = get_report_generator()
            report = report_gen.generate_report(user_id, use_llm=True)
            return {'success': True, 'report': report.to_dict()}
        except Exception as e:
            return {'success': False, 'error': f'阅读报告生成失败: {str(e)}'}

    result, cache_hit = _with_cache('report', [user_id], _gen)
    status = 500 if not result.get('success', False) else 200
    return _ai_response(result, cache_hit=cache_hit), status


# ========== 智能推荐理由 ==========
@ai_bp.route('/recommend', methods=['POST'])
def ai_recommend_route():
    """生成个性化推荐理由（带缓存）"""
    data = request.get_json() or {}
    user_id = data.get('user_id', 8)

    def _gen():
        try:
            from .llm_engine import get_llm_engine
            engine = get_llm_engine()
            prompt = f"请为用户{user_id}推荐3-5本适合的书籍，包含书名、推荐理由和匹配度评分。"
            response = engine.generate(prompt)
            return {'success': True, 'recommendation': response.to_dict()}
        except Exception as e:
            return {'success': False, 'error': f'推荐生成失败: {str(e)}'}

    result, cache_hit = _with_cache('recommend', [user_id], _gen)
    status = 500 if not result.get('success', False) else 200
    return _ai_response(result, cache_hit=cache_hit), status


# ========== 书籍摘要 ==========
@ai_bp.route('/summary/<int:book_id>', methods=['GET', 'POST'])
def ai_summary(book_id):
    """为指定书籍生成智能摘要（带缓存）"""
    def _gen():
        try:
            from .book_analyzer import get_book_analyzer
            analyzer = get_book_analyzer()
            summary = analyzer.generate_summary(book_id)
            if summary:
                return {'success': True, 'summary': summary.to_dict(), '_status': 200}
            else:
                return {'success': False, 'error': '未找到书籍', '_status': 404}
        except Exception as e:
            return {'success': False, 'error': f'摘要生成失败: {str(e)}', '_status': 500}

    result, cache_hit = _with_cache('summary', [book_id], _gen)
    status = result.pop('_status', 200) if result.get('success', False) else result.pop('_status', 500)
    return _ai_response(result, cache_hit=cache_hit), status


# ========== 书籍搜索 ==========
@ai_bp.route('/search', methods=['GET'])
def ai_search():
    """搜索书籍（带缓存）"""
    query = request.args.get('q', '').strip()
    limit = int(request.args.get('limit', 10))
    # 参数边界保护
    if limit < 1:
        limit = 5
    if limit > 50:
        limit = 50

    if not query:
        return {'success': False, 'error': '搜索词不能为空'}, 400

    def _gen():
        try:
            from .book_analyzer import get_book_analyzer
            analyzer = get_book_analyzer()
            books = analyzer.search_books(query, limit)
            return {'success': True, 'books': books, 'count': len(books)}
        except Exception as e:
            return {'success': False, 'error': f'搜索失败: {str(e)}'}

    result, cache_hit = _with_cache('search', [query, limit], _gen)
    status = 500 if not result.get('success', False) else 200
    return _ai_response(result, cache_hit=cache_hit), status


# ========== 书籍详情分析 ==========
@ai_bp.route('/analyze/<int:book_id>', methods=['GET', 'POST'])
def ai_analyze(book_id):
    """完整分析一本书（画像 + 摘要 + 相似书籍）（带缓存）"""
    data = request.get_json() or {}
    use_llm = data.get('use_llm', True)
    if request.method == 'GET':
        use_llm = request.args.get('use_llm', 'true').lower() != 'false'

    def _gen():
        try:
            from .book_analyzer import get_book_analyzer
            analyzer = get_book_analyzer()
            analysis = analyzer.analyze_book(book_id, use_llm=use_llm)
            if 'error' in analysis:
                return {'success': False, 'error': analysis['error'], '_status': 404}
            return {'success': True, 'analysis': analysis, '_status': 200}
        except Exception as e:
            return {'success': False, 'error': f'分析失败: {str(e)}', '_status': 500}

    result, cache_hit = _with_cache('analyze', [book_id, 'llm' if use_llm else 'nolllm'], _gen)
    status = result.pop('_status', 200) if result.get('success', False) else result.pop('_status', 500)
    return _ai_response(result, cache_hit=cache_hit), status


# ========== T5：RAG 推荐（检索 + 生成 + 引用溯源） ==========
@ai_bp.route('/rag-recommend', methods=['GET', 'POST'])
def ai_rag_recommend():
    """基于 RAG 的可解释推荐：
    - 先从数据库 / 推荐引擎 检索 top-N 候选书籍（检索）
    - 再把候选塞进提示词，交给 LLM 生成带引用的推荐理由（生成）
    - 每个返回的推荐项附带 source_book_ids，可溯源
    """
    if request.method == 'POST':
        data = request.get_json() or {}
    else:
        data = {
            'user_id': request.args.get('user_id', type=int),
            'query': request.args.get('query', ''),
            'top_k': request.args.get('top_k', 3, type=int),
        }

    user_id = data.get('user_id')
    query = (data.get('query') or '').strip()
    top_k = int(data.get('top_k', 3))
    top_k = max(1, min(10, top_k))

    if not user_id and not query:
        return _ai_response({'success': False, 'error': '需要 user_id 或 query'}), 400

    def _gen():
        try:
            from .llm_engine import get_llm_engine
            from extensions import db
            from models import Book, Rating
            from sqlalchemy import func

            # ---------- 1) 检索：获取 top-N 候选书籍 ----------
            candidates = []

            # 有 user_id：先从 recommend advanced 拿候选（如果能），否则 fallback 到高评分
            if user_id:
                try:
                    # 直接从评分最高的同分类+高评分书籍中取 top-20 候选
                    liked = db.session.query(
                        Rating.book_id, func.avg(Rating.rating).label('avg')
                    ).filter(Rating.user_id == user_id
                             ).group_by(Rating.book_id).order_by(func.avg(Rating.rating).desc()
                                                                  ).limit(5).all()
                    liked_ids = [r[0] for r in liked]
                    # 同分类候选
                    if liked_ids:
                        categories = db.session.query(Book.category).filter(
                            Book.id.in_(liked_ids), Book.category.isnot(None)
                        ).distinct().limit(3).all()
                        cats = [c[0] for c in categories if c and c[0]]
                        if cats:
                            rated_avg = db.session.query(
                                Rating.book_id, func.count(Rating.id).label('cnt'),
                                func.avg(Rating.rating).label('avg_r')
                            ).group_by(Rating.book_id).subquery()
                            rows = db.session.query(
                                Book, rated_avg.c.avg_r
                            ).outerjoin(rated_avg, Book.id == rated_avg.c.book_id
                                         ).filter(Book.category.in_(cats)
                                                  ).filter(Book.id.notin_(liked_ids)
                                                           ).order_by(rated_avg.c.avg_r.desc().nullslast()
                                                                      ).limit(top_k * 3).all()
                            for b, avg_r in rows:
                                candidates.append({
                                    'book_id': b.id,
                                    'title': b.title or '',
                                    'author': b.author or '',
                                    'category': b.category or '',
                                    'year': b.year or 0,
                                    'avg_rating': round(float(avg_r), 1) if avg_r is not None else None,
                                })
                except Exception:
                    pass

            # 如果候选不够：用 query 搜索 + 热门补齐
            if len(candidates) < top_k and query:
                try:
                    from services.search_service import get_search_service
                    svc = get_search_service()
                    res = svc.search(query, limit=top_k * 3)
                    for item in res['items']:
                        candidates.append({
                            'book_id': item['id'],
                            'title': item.get('title', ''),
                            'author': item.get('author', ''),
                            'category': item.get('category', ''),
                            'year': item.get('year', 0),
                        })
                except Exception:
                    pass

            # 仍然不够？热门 book top-N 兜底
            if len(candidates) < top_k:
                try:
                    rows = db.session.query(
                        Book, func.avg(Rating.rating).label('avg')
                    ).outerjoin(Rating, Book.id == Rating.book_id
                                ).group_by(Book.id).order_by(
                                    func.count(Rating.id).desc()
                                ).limit(top_k * 3).all()
                    exists_ids = {c['book_id'] for c in candidates}
                    for b, avg in rows:
                        if b.id in exists_ids:
                            continue
                        candidates.append({
                            'book_id': b.id,
                            'title': b.title or '',
                            'author': b.author or '',
                            'category': b.category or '',
                            'year': b.year or 0,
                            'avg_rating': round(float(avg), 1) if avg is not None else None,
                        })
                        if len(candidates) >= top_k * 3:
                            break
                except Exception:
                    pass

            # 最终限制为 top_k * 2 个候选（给 LLM 做挑选）
            candidates = candidates[: max(3, top_k * 2)]

            if not candidates:
                return {'success': False, 'error': '未检索到可供推荐的书籍', '_status': 404}

            # ---------- 2) 生成：把候选作为知识上下文，交给 LLM 选 top_k 本 ----------
            candidate_text = '\n'.join(
                f"- id={c['book_id']} 《{c['title']}》 作者: {c['author']} "
                f"分类: {c['category']} "
                f"{'评分: ' + str(c['avg_rating']) if c.get('avg_rating') else ''}"
                for c in candidates
            )

            intro = f"用户 #{user_id}" if user_id else "访客"
            if query:
                intro += f"，搜索关键词：{query}"

            prompt = (
                f"你是一位资深书探。以下是从图书馆检索到的候选书籍列表：\n"
                f"{candidate_text}\n\n"
                f"请从上述候选中为{intro}挑选 {top_k} 本最值得推荐的书。"
                f"要求：\n"
                f"1) 每本书必须引用它的 id\n"
                f"2) 每本书给出 1-2 句个性化推荐理由\n"
                f"3) 用简洁友好的中文回答。\n\n"
                f"输出格式（严格 JSON）：[{{\"book_id\": <int>, \"title\": \"...\", \"reason\": \"...\", \"score\": <0-1 浮点数>}}]"
            )

            engine = get_llm_engine()
            llm_resp = engine.generate(prompt)

            # 解析 LLM 输出：优先 JSON 失败则提取文本直接返回
            recommendations = []
            source_ids = [c['book_id'] for c in candidates]
            try:
                import json as _json
                text = (getattr(llm_resp, 'content', '') or '').strip()
                # 寻找第一个 '[' 与最后一个 ']'
                start = text.find('[')
                end = text.rfind(']')
                if 0 <= start < end:
                    parsed = _json.loads(text[start:end + 1])
                    if isinstance(parsed, list):
                        seen_ids = set()
                        for item in parsed:
                            if not isinstance(item, dict):
                                continue
                            bid = int(item.get('book_id', 0) or 0)
                            if bid <= 0 or bid in seen_ids:
                                continue
                            seen_ids.add(bid)
                            recommendations.append({
                                'book_id': bid,
                                'title': item.get('title', ''),
                                'reason': item.get('reason', ''),
                                'score': round(float(item.get('score', 0.5)), 3),
                            })
                            if len(recommendations) >= top_k:
                                break
            except Exception:
                pass

            if not recommendations:
                # 兜底：直接返回候选书籍（取 top_k），并把 LLM 的原始响应作为 explanation
                for c in candidates[:top_k]:
                    recommendations.append({
                        'book_id': c['book_id'],
                        'title': c['title'],
                        'reason': '候选库推荐',
                        'score': 0.6,
                    })

            return {
                'success': True,
                'recommendations': recommendations,
                'explanation': getattr(llm_resp, 'content', ''),
                'candidates_retrieved': len(candidates),
                'sources': source_ids,
                'retrieval_mode': 'rag',
                '_status': 200,
            }

        except Exception as e:
            return {'success': False, 'error': f'RAG 推荐生成失败: {str(e)}', '_status': 500}

    result, cache_hit = _with_cache(
        'rag_recommend',
        [user_id or 'guest', hash(query), top_k],
        _gen
    )
    status = result.pop('_status', 200) if result.get('success', False) else result.pop('_status', 500)
    return _ai_response(result, cache_hit=cache_hit), status


# ========== 对话式推荐：关键词识别 + 多策略推荐 + LLM 自然语言回复 ==========

_RECOMMEND_KEYWORDS = [
    '推荐', '找书', '想看', '类似', '好书', '推荐书',
    '有什么', 'recommend', 'suggest', 'book for me',
    '推荐一本', '什么书', '类似的书',
]


def _is_recommend_intent(message: str) -> bool:
    """判断一条消息是否为推荐意图（关键词匹配）"""
    try:
        if not message:
            return False
        text = str(message).strip().lower()
        if not text:
            return False
        for kw in _RECOMMEND_KEYWORDS:
            if kw.lower() in text:
                return True
        return False
    except Exception:
        return False


def _run_recommend(user_id, n_recommendations=5):
    """内部调用推荐服务（MMR 为主，失败回落 cold-start）

    返回 (recommendations_list, strategy_used)
    recommendations_list 的每项至少包含 book_id / title / reason / score
    """
    if n_recommendations is None or n_recommendations <= 0:
        n_recommendations = 5
    try:
        n_recommendations = int(n_recommendations)
    except Exception:
        n_recommendations = 5
    n_recommendations = max(1, min(20, n_recommendations))

    # ----- 策略 1：MMR -----
    try:
        from services.content_filter import (
            get_content_recommender, get_item_based_cf,
        )
        from services.embedding_service import get_embedding_service
        from services.cf_algorithm import CollaborativeFiltering
        from services.svd_algorithm import SVDRecommendation
        from extensions import db
        from sqlalchemy import func
        from models import Book, Rating

        pool = {}
        pool_size = max(n_recommendations * 3, 20)

        try:
            cf_engine = CollaborativeFiltering()
            cf_recs = cf_engine.recommend(user_id, n_recommendations=pool_size) or []
            for rank, rec in enumerate(cf_recs):
                bid = rec.get('book_id') if isinstance(rec, dict) else None
                if not bid:
                    continue
                rel_score = max(0.0, 1.0 - rank * 0.02)
                pool.setdefault(int(bid), {'score': 0.0})
                pool[int(bid)]['score'] += rel_score
        except Exception:
            pass

        try:
            svd_engine = SVDRecommendation()
            svd_recs = svd_engine.recommend(user_id, n_recommendations=pool_size) or []
            for rank, rec in enumerate(svd_recs):
                bid = rec.get('book_id') if isinstance(rec, dict) else None
                if not bid:
                    continue
                rel_score = max(0.0, 0.9 - rank * 0.02)
                pool.setdefault(int(bid), {'score': 0.0})
                pool[int(bid)]['score'] += rel_score
        except Exception:
            pass

        try:
            embed_svc = get_embedding_service()
            if embed_svc is not None and hasattr(embed_svc, 'recommend_books'):
                sem_recs = embed_svc.recommend_books(user_id, top_k=pool_size) or []
                for rank, rec in enumerate(sem_recs[:pool_size]):
                    bid = rec.get('book_id') if isinstance(rec, dict) else rec
                    if not bid:
                        continue
                    rel_score = max(0.0, 0.8 - rank * 0.02)
                    pool.setdefault(int(bid), {'score': 0.0})
                    pool[int(bid)]['score'] += rel_score
        except Exception:
            pass

        try:
            content_engine = get_content_recommender()
            content_recs = content_engine.recommend(user_id, n=pool_size, seed=42) or []
            for rank, rec in enumerate(content_recs):
                bid = rec.get('book_id') if isinstance(rec, dict) else None
                if not bid:
                    continue
                rel_score = float(rec.get('score', 0.0) or 0.0)
                pool.setdefault(int(bid), {'score': 0.0})
                pool[int(bid)]['score'] += rel_score
        except Exception:
            pass

        # 去已读
        try:
            rated_rows = db.session.query(Rating.book_id).filter(Rating.user_id == user_id).all()
            rated_ids = {int(r[0]) for r in rated_rows}
            for bid in list(pool.keys()):
                if bid in rated_ids:
                    del pool[bid]
        except Exception:
            pass

        if pool:
            # 简单贪心 MMR（按 score 排序 + 保证分类多样性）
            ranked = sorted(pool.items(), key=lambda kv: float(kv[1]['score']), reverse=True)
            all_ids = [bid for bid, _ in ranked]
            book_map = {b.id: b for b in Book.query.filter(Book.id.in_(all_ids)).all()} if all_ids else {}

            selected = []
            seen_categories = set()
            for bid, meta in ranked:
                book = book_map.get(bid)
                if book is None:
                    continue
                cat = getattr(book, 'category', None) or ''
                score = float(meta.get('score', 0.0))
                # 简单多样性惩罚：已出现过的分类降权
                if cat and cat in seen_categories:
                    score *= 0.75
                selected.append((bid, book, score, cat))
                if cat:
                    seen_categories.add(cat)
                if len(selected) >= n_recommendations * 2:
                    break
            selected.sort(key=lambda x: x[2], reverse=True)
            selected = selected[:n_recommendations]

            if selected:
                from services.content_filter import get_explainability
                explainer = get_explainability()
                user_profile = {}
                try:
                    user_profile = get_content_recommender().get_user_profile(user_id)
                except Exception:
                    user_profile = {'size': 0, 'authors': {}, 'categories': {}}

                recommendations = []
                for bid, book, score, cat in selected:
                    try:
                        reason = explainer.generate_reason(
                            book, sources=['content_based', 'cf'],
                            user_profile=user_profile,
                        )
                    except Exception:
                        reason = f'based on your interest in {cat or "similar"} books'
                    try:
                        book_dict = book.to_dict() if hasattr(book, 'to_dict') else {
                            'id': getattr(book, 'id', bid),
                            'title': getattr(book, 'title', ''),
                            'author': getattr(book, 'author', ''),
                            'category': cat,
                        }
                    except Exception:
                        book_dict = {
                            'id': bid, 'title': getattr(book, 'title', ''),
                            'author': getattr(book, 'author', ''), 'category': cat,
                        }
                    book_dict['book_id'] = bid
                    book_dict['reason'] = reason
                    book_dict['score'] = round(float(score), 3)
                    recommendations.append(book_dict)
                return recommendations, 'mmr_hybrid'
    except Exception:
        pass

    # ----- 策略 2：cold-start 兜底 -----
    try:
        from extensions import db
        from sqlalchemy import func
        from models import Book, Rating

        top_n = max(n_recommendations * 5, 50)
        try:
            sub = db.session.query(
                Rating.book_id,
                func.count(Rating.id).label('cnt'),
                func.avg(Rating.rating).label('avg'),
            ).group_by(Rating.book_id).order_by(
                func.count(Rating.id).desc()
            ).limit(top_n).subquery()
            stats = db.session.query(sub.c.book_id, sub.c.cnt, sub.c.avg).all()
            stats_map = {}
            for bid, cnt, avg in stats:
                try:
                    bid = int(bid)
                    if int(cnt or 0) <= 0:
                        continue
                    stats_map[bid] = (int(cnt or 0), float(avg or 0.0))
                except Exception:
                    continue
        except Exception:
            stats_map = {}

        books = []
        if stats_map:
            try:
                book_objs = Book.query.filter(Book.id.in_(list(stats_map.keys()))).all()
                for b in book_objs:
                    cnt, avg = stats_map.get(b.id, (0, 0.0))
                    books.append((b, cnt, avg))
            except Exception:
                books = []
        if not books:
            try:
                for b in Book.query.order_by(Book.id).limit(n_recommendations * 3).all():
                    books.append((b, 1, 8.0))
            except Exception:
                books = []

        if books:
            # 保证分类多样性
            buckets = {}
            for b, cnt, avg in books:
                cat = getattr(b, 'category', None) or 'misc'
                buckets.setdefault(cat, []).append((b, cnt, avg))
            picks = []
            for cat, items in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
                items_sorted = sorted(items, key=lambda x: x[2], reverse=True)
                if items_sorted:
                    picks.append((items_sorted[0][0], items_sorted[0][1], items_sorted[0][2], cat))
            # 剩余用高分补齐
            all_sorted = sorted(books, key=lambda x: x[2], reverse=True)
            seen_ids = {p[0].id for p in picks}
            for b, cnt, avg in all_sorted:
                if b.id in seen_ids:
                    continue
                picks.append((b, cnt, avg, 'popular'))
                seen_ids.add(b.id)
                if len(picks) >= n_recommendations:
                    break

            recommendations = []
            for b, cnt, avg, cat in picks[:n_recommendations]:
                try:
                    book_dict = b.to_dict() if hasattr(b, 'to_dict') else {
                        'id': b.id, 'title': getattr(b, 'title', ''),
                        'author': getattr(b, 'author', ''), 'category': cat,
                    }
                except Exception:
                    book_dict = {
                        'id': b.id, 'title': getattr(b, 'title', ''),
                        'author': getattr(b, 'author', ''), 'category': cat,
                    }
                book_dict['book_id'] = b.id
                book_dict['reason'] = f'popular {cat or "category"} book with high community ratings'
                book_dict['score'] = round(float(avg) / 10.0, 3) if avg else 0.7
                recommendations.append(book_dict)
            if recommendations:
                return recommendations, 'cold_start'
    except Exception:
        pass

    return [], 'none'


def _build_llm_reply(message, user_id, recommendations) -> str:
    """基于推荐结果，调用 LLM 生成自然语言回复"""
    try:
        from .llm_engine import get_llm_engine
        engine = get_llm_engine()
        if engine is None:
            raise RuntimeError('llm engine unavailable')

        items_text = []
        for idx, r in enumerate(recommendations[:10], start=1):
            title = r.get('title') or r.get('book_title') or f'Book #{r.get("book_id", idx)}'
            author = r.get('author') or ''
            reason = r.get('reason') or 'recommended for you'
            score = r.get('score') or r.get('content_score') or 0.7
            try:
                score_f = float(score)
                rating = round(score_f * 5, 1) if score_f <= 1 else round(score_f, 1)
            except Exception:
                rating = 4.0
            items_text.append(
                f"{idx}. 《{title}》{(' by ' + author) if author else ''}\n"
                f"   理由: {reason}\n"
                f"   匹配评分: {rating}/5.0"
            )

        prompt = (
            f"用户说：「{message[:200]}」\n\n"
            f"以下是为用户 #{user_id if user_id else 'guest'} 推荐的书籍：\n"
            f"{chr(10).join(items_text)}\n\n"
            f"请你作为一位友好的书店导购，用自然的中文回复用户：\n"
            f"1) 先回应用户的请求；\n"
            f"2) 简洁列出每本书的书名、推荐理由和匹配评分；\n"
            f"3) 最后给一句鼓励性的结束语。\n"
            f"不要输出 JSON，直接输出对话文本。"
        )

        try:
            resp = engine.generate(prompt)
            text = getattr(resp, 'content', None)
            if text:
                return str(text).strip()
        except Exception:
            pass
    except Exception:
        pass

    # 降级：模板化回复
    lines = ['你好！根据你的需求，我为你精选了以下几本书：\n']
    for idx, r in enumerate(recommendations[:10], start=1):
        title = r.get('title') or f'Book #{r.get("book_id", idx)}'
        reason = r.get('reason') or 'recommended for you'
        try:
            score_f = float(r.get('score') or 0.7)
            rating = round(score_f * 5, 1) if score_f <= 1 else round(score_f, 1)
        except Exception:
            rating = 4.0
        lines.append(f"{idx}. 《{title}》\n   理由: {reason}\n   评分: {rating}/5.0\n")
    lines.append('希望其中有你喜欢的一本，祝你阅读愉快！')
    return '\n'.join(lines)


@ai_bp.route('/conversational-recommend', methods=['POST'])
def ai_conversational_recommend():
    """对话式推荐：识别推荐意图 -> 多路召回 -> LLM 自然语言回复"""
    try:
        data = request.get_json() or {}
        message = (data.get('message') or '').strip()
        user_id = data.get('user_id')
        conversation_id = data.get('conversation_id') or f'conv_{int(time.time() * 1000)}'
        n_recommendations = data.get('n_recommendations', 5)

        is_intent = _is_recommend_intent(message)
        if not message:
            return jsonify({
                'success': False,
                'error': 'message is required',
                'is_recommend_intent': False,
                'conversation_id': conversation_id,
                'reply': '',
                'recommendations': [],
            }), 400

        # 非推荐意图：直接走 LLM 闲聊回复
        if not is_intent:
            try:
                from .llm_engine import get_llm_engine
                engine = get_llm_engine()
                resp = engine.generate(message) if engine else None
                reply_text = getattr(resp, 'content', None) or (
                    f'我收到了你的消息：「{message[:80]}」，'
                    f'如果你想让我为你推荐书籍，请包含"推荐"、"找书"等关键词，'
                    f'我会为你挑选最合适的书。'
                )
            except Exception:
                reply_text = (
                    f'我收到了你的消息：「{message[:80]}」，'
                    f'如果你想让我为你推荐书籍，请包含"推荐"、"找书"等关键词。'
                )
            return jsonify({
                'success': True,
                'is_recommend_intent': False,
                'conversation_id': conversation_id,
                'reply': str(reply_text),
                'recommendations': [],
            }), 200

        # 推荐意图：调用多路召回
        try:
            recommendations, strategy = _run_recommend(user_id, n_recommendations)
        except Exception:
            recommendations, strategy = [], 'none'

        # 如果为空，再尝试一次 cold-start 兜底
        if not recommendations:
            try:
                recommendations, strategy = _run_recommend(user_id, n_recommendations)
            except Exception:
                recommendations, strategy = [], 'none'

        reply_text = _build_llm_reply(message, user_id, recommendations)

        return jsonify({
            'success': True,
            'is_recommend_intent': True,
            'conversation_id': conversation_id,
            'reply': reply_text,
            'recommendations': recommendations[: int(n_recommendations or 5)],
            'strategy_used': strategy,
        }), 200

    except Exception as e:
        logger.exception('conversational-recommend failed')
        return jsonify({
            'success': False,
            'error': str(e),
            'is_recommend_intent': False,
            'conversation_id': (request.get_json() or {}).get('conversation_id') or '',
            'reply': '抱歉，推荐服务暂时不可用，请稍后再试。',
            'recommendations': [],
        }), 500


# ========== AI + FAISS + Recommend 健康状态汇总 ==========
@ai_bp.route('/recommend-status', methods=['GET'])
def ai_recommend_status():
    """返回 AI / FAISS / Recommend 三套服务的健康状态"""
    status = {
        'success': True,
        'llm': {'available': False, 'error': None, 'details': {}},
        'faiss': {'available': False, 'error': None, 'details': {}},
        'recommend': {'available': False, 'error': None, 'details': {}},
    }

    # LLM 状态
    try:
        from .llm_engine import get_llm_engine
        engine = get_llm_engine()
        if engine is not None and hasattr(engine, 'get_status'):
            details = engine.get_status() or {}
            status['llm']['details'] = details
            status['llm']['available'] = bool(details.get('available')) or bool(details.get('ollama_available'))
        else:
            status['llm']['available'] = engine is not None
    except Exception as e:
        status['llm']['error'] = str(e)

    # FAISS / embedding 状态
    try:
        from services.embedding_service import get_embedding_service
        svc = get_embedding_service()
        if svc is not None:
            details = {
                'model_loaded': getattr(svc, 'model', None) is not None,
                'faiss_ready': bool(getattr(svc, 'faiss_ready', False)),
                'faiss_index_size': int(getattr(svc, 'index_size', 0) or 0),
                'embedding_cache_size': int(len(getattr(svc, 'book_embeddings', {}) or {})),
            }
            status['faiss']['details'] = details
            status['faiss']['available'] = bool(details['model_loaded']) and bool(details['faiss_ready'])
    except Exception as e:
        status['faiss']['error'] = str(e)

    # Recommend 状态
    try:
        from services.cf_algorithm import CollaborativeFiltering
        from services.svd_algorithm import SVDRecommendation
        from services.content_filter import (
            get_content_recommender, get_item_based_cf,
        )

        cf_engine = CollaborativeFiltering()
        svd_engine = SVDRecommendation()
        content_engine = get_content_recommender()
        ibcf = get_item_based_cf()

        details = {
            'cf_users': int(getattr(cf_engine, 'user_count', 0) or 0),
            'svd_items': int(getattr(svd_engine, 'book_count', 0) or 0),
            'content_engine_ready': content_engine is not None,
            'item_based_cf_ready': ibcf is not None,
        }
        status['recommend']['details'] = details
        status['recommend']['available'] = (
            details['cf_users'] > 0 or details['svd_items'] > 0
            or details['content_engine_ready']
        )
    except Exception as e:
        status['recommend']['error'] = str(e)

    return jsonify(status), 200


# ========== 修改现有 /chat/stream：识别推荐意图并注入推荐内容 ==========
def _patched_ai_chat_stream():
    """流式对话：检测到推荐意图时先跑推荐，再让 LLM 基于推荐结果回复"""
    data = request.get_json() or {}
    prompt = (data.get('prompt') or data.get('message') or '').strip()
    user_id = data.get('user_id')
    conversation_id = data.get('conversation_id') or f'conv_{int(time.time() * 1000)}'

    def _emit(event_data: str) -> bytes:
        return f'data: {event_data}\n\n'.encode('utf-8')

    def _generate():
        try:
            yield _emit('[START]')
        except Exception:
            return

        if not prompt:
            yield _emit('[ERROR] prompt 不能为空')
            return

        # 推荐意图：先获取推荐结果，再让 LLM 基于推荐回复
        enhanced_prompt = prompt
        recommendations = []
        is_intent = _is_recommend_intent(prompt)
        if is_intent:
            try:
                recommendations, _ = _run_recommend(user_id, 5)
            except Exception:
                recommendations = []
            if recommendations:
                items_text = []
                for idx, r in enumerate(recommendations[:10], start=1):
                    title = r.get('title') or f'Book #{r.get("book_id", idx)}'
                    author = r.get('author') or ''
                    reason = r.get('reason') or 'recommended for you'
                    score = r.get('score') or 0.7
                    try:
                        rating = round(float(score) * 5, 1) if float(score) <= 1 else round(float(score), 1)
                    except Exception:
                        rating = 4.0
                    items_text.append(
                        f"{idx}. 《{title}》{' by ' + author if author else ''}\n"
                        f"   理由: {reason}\n"
                        f"   匹配评分: {rating}/5.0"
                    )
                enhanced_prompt = (
                    f"用户请求：「{prompt[:200]}」（这是一个找书/推荐请求）\n\n"
                    f"推荐系统已为用户 #{user_id if user_id else 'guest'} 返回以下书籍：\n"
                    f"{chr(10).join(items_text)}\n\n"
                    f"请你作为友好的书店导购，基于上述推荐结果，用自然中文回复用户：\n"
                    f"1) 先礼貌回应用户；\n"
                    f"2) 列出每本书的书名、推荐理由与评分（保留原始推荐信息）；\n"
                    f"3) 最后给一句鼓励性结束语。\n"
                    f"直接输出对话文本。"
                )
                # 先把"识别到推荐意图"作为首块文本输出
                try:
                    yield _emit('好的，我来为你挑选几本书——\n\n')
                except Exception:
                    pass

        # ---------- 原始流式生成逻辑 ----------
        try:
            from .llm_engine import get_llm_engine
            engine = get_llm_engine()

            engine_ok = False
            try:
                if engine and hasattr(engine, 'ollama_available') and engine.ollama_available and hasattr(engine, 'generate_stream'):
                    engine_ok = True
            except Exception:
                engine_ok = False

            collected_chunks = []

            if engine_ok:
                try:
                    def _on_token(token: str):
                        collected_chunks.append(token)
                    llm_resp = engine.generate_stream(enhanced_prompt, callback=_on_token)
                    full_text = getattr(llm_resp, 'content', '') or ''.join(collected_chunks)
                    if not full_text and collected_chunks:
                        full_text = ''.join(collected_chunks)

                    chunk_size = random.randint(3, 8)
                    pos = 0
                    while pos < len(full_text):
                        piece = full_text[pos:pos + chunk_size]
                        yield _emit(piece)
                        pos += chunk_size
                        chunk_size = random.randint(3, 8)
                        time.sleep(0.02)
                except Exception as e:
                    yield _emit(f'[ERROR] LLM 流式调用失败: {e}')
                    return
            else:
                try:
                    llm_resp = engine.generate(enhanced_prompt) if engine else None
                    full_text = getattr(llm_resp, 'content', '') if llm_resp else ''
                    if not full_text:
                        if is_intent and recommendations:
                            # 基于推荐结果的模板化流式输出
                            parts = ['根据你的需求，我为你精选了以下几本书：\n\n']
                            for idx, r in enumerate(recommendations[:10], start=1):
                                title = r.get('title') or f'Book #{r.get("book_id", idx)}'
                                reason = r.get('reason') or 'recommended for you'
                                try:
                                    rating = round(float(r.get('score') or 0.7) * 5, 1)
                                except Exception:
                                    rating = 4.0
                                parts.append(f"{idx}. 《{title}》\n   理由: {reason}\n   评分: {rating}/5.0\n\n")
                            parts.append('希望其中有你喜欢的一本，祝你阅读愉快！')
                            full_text = ''.join(parts)
                        else:
                            full_text = (
                                f"你好！我收到了你的问题：「{prompt[:80]}」。\n"
                                f"作为书籍 AI 助手，我可以帮你生成个性化书评、"
                                f"推荐匹配的书籍、分析书籍内容与主题，以及生成你的阅读报告。\n"
                                f"\n你可以进一步告诉我，你希望从哪个角度入手？"
                            )
                    chunk_size = random.randint(3, 8)
                    pos = 0
                    while pos < len(full_text):
                        piece = full_text[pos:pos + chunk_size]
                        yield _emit(piece)
                        pos += chunk_size
                        chunk_size = random.randint(3, 8)
                        time.sleep(0.02)
                except Exception as e:
                    yield _emit(f'[ERROR] LLM 调用失败: {e}')
                    return
        except Exception as e:
            yield _emit(f'[ERROR] 生成失败: {e}')
            return

        yield _emit('[DONE]')

    try:
        return Response(_generate(), mimetype='text/event-stream')
    except Exception as e:
        return Response(f'data: [ERROR] 初始化失败: {e}\n\n', mimetype='text/event-stream')


# ========== 修改现有 /chat：识别推荐意图并注入推荐内容 ==========
def _patched_ai_chat():
    """对话：检测到推荐意图时先跑推荐，再让 LLM 基于推荐结果回复"""
    data = request.get_json() or {}
    message = (data.get('message') or data.get('prompt') or '').strip()
    conversation_id = data.get('conversation_id') or f'conv_{int(time.time() * 1000)}'
    user_id = data.get('user_id')

    if not message:
        return {'success': False, 'error': '消息不能为空'}, 400

    is_intent = _is_recommend_intent(message)
    recommendations = []

    # 推荐意图：先内部调用推荐，再交给 LLM 基于结果生成回复
    if is_intent:
        try:
            recommendations, _ = _run_recommend(user_id, 5)
        except Exception:
            recommendations = []

        # 让 LLM 基于推荐结果回复
        try:
            from .llm_engine import get_llm_engine
            engine = get_llm_engine()
            items_text = []
            if recommendations:
                for idx, r in enumerate(recommendations[:10], start=1):
                    title = r.get('title') or f'Book #{r.get("book_id", idx)}'
                    author = r.get('author') or ''
                    reason = r.get('reason') or 'recommended for you'
                    try:
                        score_f = float(r.get('score') or 0.7)
                        rating = round(score_f * 5, 1) if score_f <= 1 else round(score_f, 1)
                    except Exception:
                        rating = 4.0
                    items_text.append(
                        f"{idx}. 《{title}》{' by ' + author if author else ''}\n"
                        f"   理由: {reason}\n"
                        f"   匹配评分: {rating}/5.0"
                    )
            prompt = (
                f"用户请求：「{message[:200]}」（这是一个找书/推荐请求）\n\n"
                f"推荐系统已为用户 #{user_id if user_id else 'guest'} 返回以下书籍：\n"
                f"{chr(10).join(items_text) if items_text else '(暂无推荐结果，请稍后再试)'}\n\n"
                f"请你作为友好的书店导购，基于上述推荐结果用自然中文回复用户。"
            ) if recommendations else (
                f"用户说：「{message[:200]}」。请作为友好的书店导购回复用户，"
                f"告知暂时没有可用的个性化推荐，但可以基于热门书籍做推荐，或请用户补充阅读偏好。"
            )

            try:
                resp = engine.generate(prompt) if engine else None
                reply_text = getattr(resp, 'content', None)
                if not reply_text:
                    # 模板化兜底
                    lines = ['你好！根据你的需求，我为你精选了以下几本书：\n']
                    for idx, r in enumerate(recommendations[:10], start=1):
                        title = r.get('title') or f'Book #{r.get("book_id", idx)}'
                        reason = r.get('reason') or 'recommended for you'
                        try:
                            rating = round(float(r.get('score') or 0.7) * 5, 1)
                        except Exception:
                            rating = 4.0
                        lines.append(f"{idx}. 《{title}》\n   理由: {reason}\n   评分: {rating}/5.0\n")
                    lines.append('希望其中有你喜欢的一本，祝你阅读愉快！')
                    reply_text = '\n'.join(lines)
                return {
                    'success': True,
                    'reply': str(reply_text).strip(),
                    'message': message,
                    'conversation_id': conversation_id,
                    'is_recommend_intent': True,
                    'recommendations': recommendations,
                }
            except Exception as e:
                # LLM 失败：模板化回复 + 保留推荐结果
                lines = ['你好！根据你的需求，我为你精选了以下几本书：\n']
                for idx, r in enumerate(recommendations[:10], start=1):
                    title = r.get('title') or f'Book #{r.get("book_id", idx)}'
                    reason = r.get('reason') or 'recommended for you'
                    try:
                        rating = round(float(r.get('score') or 0.7) * 5, 1)
                    except Exception:
                        rating = 4.0
                    lines.append(f"{idx}. 《{title}》\n   理由: {reason}\n   评分: {rating}/5.0\n")
                lines.append(f'(LLM 暂时不可用: {e}) 希望其中有你喜欢的一本，祝你阅读愉快！')
                return {
                    'success': True,
                    'reply': '\n'.join(lines),
                    'message': message,
                    'conversation_id': conversation_id,
                    'is_recommend_intent': True,
                    'recommendations': recommendations,
                }
        except Exception as e:
            return {'success': False, 'error': f'对话处理失败: {str(e)}'}, 500

    # 非推荐意图：走原有逻辑（conversation_manager / 或 LLM 直接回复）
    try:
        from .conversation import get_conversation_manager
        conv_manager = get_conversation_manager()
        result = conv_manager.handle_message(conversation_id, message, user_id)
        result['conversation_id'] = conversation_id
        result['is_recommend_intent'] = False
        result['recommendations'] = []
        return {'success': True, **result}
    except Exception:
        # conversation_manager 也不可用：直接让 LLM 回复
        try:
            from .llm_engine import get_llm_engine
            engine = get_llm_engine()
            resp = engine.generate(message) if engine else None
            text = getattr(resp, 'content', None) or (
                f'你好，我收到了你的消息：「{message[:80]}」。'
                f'如果你想让我为你推荐书籍，请告诉我你的阅读偏好，'
                f'或直接包含"推荐"、"找书"等关键词。'
            )
            return {
                'success': True,
                'reply': str(text),
                'message': message,
                'conversation_id': conversation_id,
                'is_recommend_intent': False,
                'recommendations': [],
            }
        except Exception as e:
            return {'success': False, 'error': f'对话处理失败: {str(e)}'}, 500


# 将 /chat/stream 与 /chat 切换为增强版路由（在 blueprint 中覆盖）
ai_bp.add_url_rule('/chat/stream', 'ai_chat_stream_enhanced', _patched_ai_chat_stream, methods=['POST'])
ai_bp.add_url_rule('/chat', 'ai_chat_enhanced', _patched_ai_chat, methods=['POST'])


# ========== 模块初始化 ==========
def init_ai_module():
    """初始化 AI 模块（预热引擎等）"""
    try:
        from .llm_engine import get_llm_engine
        from .conversation import get_conversation_manager
        from .review_generator import get_review_generator
        from .knowledge_graph import get_knowledge_graph_generator
        from .report_generator import get_report_generator

        _ = get_llm_engine()
        _ = get_conversation_manager()
        _ = get_review_generator()
        _ = get_knowledge_graph_generator()
        _ = get_report_generator()

        print("[AI] 模块初始化完成 ✓")
        return True
    except Exception as e:
        print(f"[AI] 模块初始化警告: {e}")
        return False


__all__ = ['ai_bp', 'init_ai_module']
