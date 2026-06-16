"""
🔌 AI 内容创作助手 API 路由

提供所有 AI 功能的 HTTP 接口

端点：
- POST /api/ai/chat - 对话
- POST /api/ai/review/:book_id - 书评生成
- POST /api/ai/recommend - 推荐理由
- POST /api/ai/knowledge/:book_id - 知识图谱
- POST /api/ai/report/:user_id - 阅读报告
- GET  /api/ai/status - 引擎状态
"""

import json
import time
from flask import jsonify, request
from datetime import datetime


def register_routes(app, db):
    """
    注册 AI API 路由

    Args:
        app: Flask 应用
        db: SQLAlchemy 实例
    """

    # ========== 引擎状态 ==========

    @app.route("/api/ai/status", methods=["GET"])
    def ai_status():
        """获取 AI 引擎状态"""
        from .llm_engine import get_llm_engine

        engine = get_llm_engine()
        status = engine.get_status()

        return jsonify({
            "success": True,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "available_features": [
                {"id": "chat", "name": "对话交流", "icon": "💬"},
                {"id": "review", "name": "书评生成", "icon": "📝"},
                {"id": "recommend", "name": "智能推荐", "icon": "🎯"},
                {"id": "knowledge", "name": "知识图谱", "icon": "🧠"},
                {"id": "report", "name": "阅读报告", "icon": "📊"},
                {"id": "analyze", "name": "内容分析", "icon": "🔍"},
            ],
        })

    # ========== 对话接口 ==========

    @app.route("/api/ai/chat", methods=["POST"])
    def ai_chat():
        """与 AI 助手对话"""
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "缺少请求数据"}), 400

        message = data.get("message", "").strip()
        conv_id = data.get("conversation_id") or f"conv_{int(time.time() * 1000)}"
        user_id = data.get("user_id")

        if not message:
            return jsonify({"success": False, "error": "消息不能为空"}), 400

        # 限制消息长度
        if len(message) > 500:
            return jsonify({"success": False, "error": "消息太长"}), 400

        from .conversation import get_conversation_manager

        conv_manager = get_conversation_manager()

        start_time = time.time()
        result = conv_manager.handle_message(conv_id, message, user_id)
        elapsed = time.time() - start_time

        return jsonify({
            "success": True,
            "time": round(elapsed, 2),
            **result
        })

    @app.route("/api/ai/conversations", methods=["GET"])
    def ai_conversations():
        """获取对话列表"""
        user_id = request.args.get("user_id", type=int)

        from .conversation import get_conversation_manager

        conv_manager = get_conversation_manager()
        conversations = conv_manager.list_conversations(user_id)

        return jsonify({
            "success": True,
            "conversations": conversations,
            "total": len(conversations),
        })

    @app.route("/api/ai/conversations/<conv_id>", methods=["GET"])
    def ai_conversation_detail(conv_id):
        """获取单个对话详情"""
        from .conversation import get_conversation_manager

        conv_manager = get_conversation_manager()
        conv = conv_manager.get_conversation(conv_id)

        if not conv:
            return jsonify({"success": False, "error": "对话不存在"}), 404

        return jsonify({"success": True, "conversation": conv})

    @app.route("/api/ai/conversations/<conv_id>", methods=["DELETE"])
    def ai_conversation_delete(conv_id):
        """删除对话"""
        from .conversation import get_conversation_manager

        conv_manager = get_conversation_manager()
        success = conv_manager.delete(conv_id)

        return jsonify({"success": success})

    # ========== 书评生成 ==========

    @app.route("/api/ai/review/<int:book_id>", methods=["POST", "GET"])
    def ai_generate_review(book_id):
        """为指定书籍生成书评"""
        data = request.get_json() or {}
        style = data.get("style", "personal")
        custom_prompt = data.get("custom_prompt")

        from .review_generator import get_review_generator

        review_gen = get_review_generator()

        start_time = time.time()
        review = review_gen.generate(book_id, style=style, custom_prompt=custom_prompt)
        elapsed = time.time() - start_time

        return jsonify({
            "success": True,
            "time": round(elapsed, 2),
            "review": review.to_dict(),
        })

    @app.route("/api/ai/review/styles", methods=["GET"])
    def ai_review_styles():
        """获取可用的书评风格"""
        from .review_generator import get_review_generator

        review_gen = get_review_generator()

        return jsonify({
            "success": True,
            "styles": review_gen.get_available_styles(),
        })

    # ========== 知识图谱 ==========

    @app.route("/api/ai/knowledge/<int:book_id>", methods=["POST", "GET"])
    def ai_knowledge_graph(book_id):
        """生成书籍知识图谱"""
        from .knowledge_graph import get_knowledge_graph_generator

        kg_gen = get_knowledge_graph_generator()

        start_time = time.time()
        graph = kg_gen.generate(book_id)
        elapsed = time.time() - start_time

        # 生成 Mermaid 格式供前端渲染
        mermaid_text = kg_gen.to_mermaid(graph)

        return jsonify({
            "success": True,
            "time": round(elapsed, 2),
            "graph": graph.to_dict(),
            "mermaid": mermaid_text,
        })

    # ========== 阅读报告 ==========

    @app.route("/api/ai/report/<int:user_id>", methods=["POST", "GET"])
    def ai_reading_report(user_id):
        """生成用户阅读报告"""
        data = request.get_json() or {}
        use_llm = data.get("use_llm", True)

        from .report_generator import get_report_generator

        report_gen = get_report_generator()

        start_time = time.time()
        report = report_gen.generate_report(user_id, use_llm=use_llm)
        elapsed = time.time() - start_time

        return jsonify({
            "success": True,
            "time": round(elapsed, 2),
            "report": report.to_dict(),
        })

    # ========== 书籍分析 ==========

    @app.route("/api/ai/analyze/<int:book_id>", methods=["POST", "GET"])
    def ai_analyze_book(book_id):
        """完整分析一本书"""
        from .book_analyzer import get_book_analyzer

        analyzer = get_book_analyzer()

        start_time = time.time()
        analysis = analyzer.analyze_book(book_id)
        elapsed = time.time() - start_time

        return jsonify({
            "success": True,
            "time": round(elapsed, 2),
            "analysis": analysis,
        })

    # ========== 智能推荐 ==========

    @app.route("/api/ai/recommend", methods=["POST"])
    def ai_recommend():
        """AI生成推荐理由"""
        data = request.get_json() or {}
        user_id = data.get("user_id")

        from .llm_engine import get_llm_engine

        engine = get_llm_engine()

        # 获取用户偏好
        user_books = []
        try:
            conn = db.engine.connect()
            result = conn.execute(
                db.text("""
                    SELECT b.id, b.title, b.author, ur.rating
                    FROM user_ratings ur
                    JOIN books b ON ur.book_id = b.id
                    WHERE ur.user_id = :user_id
                    ORDER BY ur.rating DESC
                    LIMIT 10
                """),
                {"user_id": user_id}
            )
            user_books = [
                    {"title": r[1], "rating": float(r[3])}
                    for r in result.fetchall()
            ]
            conn.close()
        except Exception as e:
            pass

        # 构建提示
        prompt = f"""请为这位用户生成个性化推荐。

用户阅读偏好（高分书籍）：
{chr(10).join(f"- 《{b['title']}》: {b['rating']}/10" for b in user_books[:5])}

生成3-5本类似的书籍推荐，包括：
- 书名
- 一句话推荐理由
- 为什么适合这位用户

使用 emojis 增强可读性。
"""

        start_time = time.time()
        response = engine.generate(prompt)
        elapsed = time.time() - start_time

        return jsonify({
            "success": True,
            "time": round(elapsed, 2),
            "recommendation": response.to_dict(),
            "user_preferences": user_books[:5],
        })

    # ========== 搜索所有可用模型管理 ==========

    @app.route("/api/ai/models", methods=["GET"])
    def ai_list_models():
        """列出可用的 LLM 模型"""
        from .llm_engine import get_llm_engine

        engine = get_llm_engine()
        models = engine.list_models()

        return jsonify({
            "success": True,
            "installed_models": [{"name": m.get("name", "Unknown")} for m in models],
            "recommended_models": engine.RECOMMENDED_MODELS if hasattr(engine, 'RECOMMENDED_MODELS') else [],
        })

    @app.route("/api/ai/model", methods=["POST"])
    def ai_set_model():
        """切换模型"""
        data = request.get_json() or {}
        model_name = data.get("model")

        if not model_name:
            return jsonify({"success": False, "error": "缺少模型名"}), 400

        from .llm_engine import get_llm_engine

        engine = get_llm_engine()
        engine.set_model(model_name)

        return jsonify({
            "success": True,
            "current_model": model_name,
        })

    # ========== 提示词模板 ==========

    @app.route("/api/ai/prompts", methods=["GET"])
    def ai_list_prompts():
        """列出所有提示模板"""
        from .prompts import list_prompts

        return jsonify({
            "success": True,
            "prompts": list_prompts(),
        })

    # 返回一个友好的帮助信息
    @app.route("/api/ai", methods=["GET"])
    def ai_help():
        """AI API 使用说明"""
        return jsonify({
            "success": True,
            "message": "书籍 AI 内容创作助手 API",
            "endpoints": [
                {"method": "GET", "path": "/api/ai/status", "desc": "引擎状态"},
                {"method": "POST", "path": "/api/ai/chat", "desc": "对话"},
                {"method": "GET", "path": "/api/ai/conversations", "desc": "对话列表"},
                {"method": "POST", "path": "/api/ai/review/<book_id>", "desc": "生成书评"},
                {"method": "GET", "path": "/api/ai/knowledge/<book_id>", "desc": "知识图谱"},
                {"method": "POST", "path": "/api/ai/report/<user_id>", "desc": "阅读报告"},
                {"method": "POST", "path": "/api/ai/recommend", "desc": "智能推荐"},
            ],
        })
