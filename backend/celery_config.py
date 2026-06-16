"""Celery 配置与初始化

用法:
    # 在 Flask app 中:
    celery = make_celery(app)
    # 启动 worker:
    celery -A app.celery worker --loglevel=info --concurrency=4
    # 启动定时任务调度:
    celery -A app.celery beat
"""
from celery import Celery
from kombu import Exchange, Queue


def make_celery(app):
    """创建并配置 Celery 实例（绑定到 Flask app）

    Args:
        app: Flask 应用实例

    Returns:
        已配置的 Celery 实例
    """
    broker = app.config.get(
        'CELERY_BROKER_URL',
        'redis://localhost:6379/1'
    )
    backend = app.config.get(
        'CELERY_RESULT_BACKEND',
        'redis://localhost:6379/2'
    )

    celery = Celery(
        app.import_name,
        broker=broker,
        backend=backend,
        include=['celery_tasks']
    )

    # 时区和序列化配置
    celery.conf.update(
        task_serializer=app.config.get('CELERY_TASK_SERIALIZER', 'json'),
        result_serializer=app.config.get('CELERY_RESULT_SERIALIZER', 'json'),
        accept_content=app.config.get('CELERY_ACCEPT_CONTENT', ['json']),
        timezone=app.config.get('CELERY_TIMEZONE', 'Asia/Shanghai'),
        enable_utc=app.config.get('CELERY_ENABLE_UTC', False),
        task_track_started=True,
        task_time_limit=30 * 60,  # 任务硬限制30分钟
        task_soft_time_limit=25 * 60,  # 任务软限制25分钟
        worker_prefetch_multiplier=4,
        worker_max_tasks_per_child=1000,
        result_expires=3600,  # 结果过期时间1小时
        # 队列配置
        task_queues=(
            Queue('default', routing_key='task.#'),
            Queue('ai', routing_key='ai.#'),
            Queue('recommend', routing_key='rec.#'),
        ),
        task_default_queue='default',
        task_default_routing_key='task.default',
    )

    # 让 Celery 任务能访问 Flask app context
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    return celery
