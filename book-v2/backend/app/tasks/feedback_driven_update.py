"""
用户反馈驱动的模型更新任务
参考报告技术:
- 用户标记反馈 → 记录反馈数据 → 定期重新训练 → 模型迭代更新
- 在线学习框架设计
"""
from celery import shared_task
from sqlalchemy import func
from app.database import SessionLocal
from app.models import RecommendationLog, Interaction, Rating
from app.services.recommender import get_recommender
from app.celery_app import celery_app


@celery_app.task
def retrain_on_feedback():
    """
    基于用户反馈定期重训练推荐模型
    参考报告: 定期重新训练策略
    """
    db = SessionLocal()
    try:
        # 统计近期反馈数据量
        recent_feedback_count = db.query(RecommendationLog).filter(
            RecommendationLog.clicked == True
        ).count()

        if recent_feedback_count < 100:
            return {
                "status": "skipped",
                "reason": f"反馈数据不足 ({recent_feedback_count}/100)",
                "action": "等待更多用户反馈"
            }

        # 获取推荐系统实例
        recommender = get_recommender()

        # 重新加载模型
        recommender.cf_engine.load_data()
        recommender.svd_engine.load_model()

        # 清除旧缓存
        recommender.redis_client.flushdb()

        return {
            "status": "success",
            "feedback_count": recent_feedback_count,
            "action": "模型已重训练，缓存已清除"
        }

    finally:
        db.close()


@celery_app.task
def record_recommendation_feedback(
    user_id: int,
    book_id: int,
    action: str,
    source: str = "hybrid"
):
    """
    记录推荐反馈
    参考报告: 用户反馈数据收集
    """
    db = SessionLocal()
    try:
        log = RecommendationLog(
            user_id=user_id,
            book_id=book_id,
            source=source,
            displayed=True
        )

        if action == "click":
            log.clicked = True
        elif action == "like":
            log.liked = True
        elif action == "rating":
            log.rated = True

        db.add(log)
        db.commit()

        return {"status": "success", "log_id": log.id}
    finally:
        db.close()
