"""Celery 异步任务定义

这些任务会在 celery worker 进程中执行。
注意: 这些任务通过 celery_config.make_celery() 注册到 Flask app
"""
from datetime import datetime
from celery_config import make_celery


# 注意: 真正的任务函数会在 app.py 中使用 @celery.task 装饰器注册
# 这里提供一些可复用的辅助函数和任务实现


def _ensure_celery():
    """尝试获取当前的 celery 实例（用于在 worker 中直接调用）"""
    # worker启动时，app.celery 会被正确设置
    try:
        from app import celery
        return celery
    except Exception:
        return None


def task_result_template(task_type, user_id=None, success=True, data=None, error=None):
    """统一任务返回结构"""
    return {
        'task_type': task_type,
        'user_id': user_id,
        'success': success,
        'generated_at': datetime.now().isoformat(),
        'data': data or {},
        'error': error,
    }
