"""
实时流式推荐模块
参考报告技术:
- Kafka 事件流处理
- 实时用户行为捕获
- 即时推荐更新
"""
import json
import time
from typing import Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from queue import Queue, Empty


class EventType(Enum):
    """事件类型枚举"""
    RATING = "rating"
    VIEW = "view"
    LIKE = "like"
    DISLIKE = "dislike"
    WANT_TO_READ = "want_to_read"
    SEARCH = "search"


@dataclass
class UserEvent:
    """用户事件数据结构"""
    event_id: str
    user_id: int
    book_id: int
    event_type: str
    timestamp: float
    metadata: Optional[Dict] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> 'UserEvent':
        data = json.loads(json_str)
        return cls(**data)


class EventStreamProcessor:
    """
    事件流处理器
    参考报告: Kafka 消费者组设计
    """

    def __init__(self):
        self.event_queue = Queue(maxsize=10000)
        self.handlers: Dict[str, List[Callable]] = {
            event_type.value: [] for event_type in EventType
        }
        self.running = False
        self.processor_thread = None

    def publish_event(self, event: UserEvent) -> bool:
        """发布事件到队列"""
        try:
            self.event_queue.put(event, block=False)
            return True
        except:
            return False

    def subscribe(self, event_type: EventType, handler: Callable):
        """订阅事件类型"""
        if event_type.value in self.handlers:
            self.handlers[event_type.value].append(handler)

    def start_processing(self):
        """启动事件处理循环"""
        if self.running:
            return

        self.running = True
        self.processor_thread = threading.Thread(target=self._process_loop)
        self.processor_thread.daemon = True
        self.processor_thread.start()
        print("✓ 事件流处理器已启动")

    def stop_processing(self):
        """停止事件处理"""
        self.running = False
        if self.processor_thread:
            self.processor_thread.join(timeout=5)
        print("✓ 事件流处理器已停止")

    def _process_loop(self):
        """事件处理主循环"""
        while self.running:
            try:
                event = self.event_queue.get(timeout=1)
                self._dispatch_event(event)
            except Empty:
                continue
            except Exception as e:
                print(f"事件处理错误: {e}")

    def _dispatch_event(self, event: UserEvent):
        """分发事件到处理器"""
        handlers = self.handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"处理器执行错误: {e}")


class StreamingRecommender:
    """
    实时流式推荐服务
    参考报告: 即时推荐更新策略
    """

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self.event_processor = EventStreamProcessor()
        self.user_recent_events: Dict[int, List[UserEvent]] = {}
        self.book_popularity: Dict[int, int] = {}
        self.lock = threading.Lock()

        # 注册事件处理器
        self._register_handlers()

    def _register_handlers(self):
        """注册事件处理器"""
        self.event_processor.subscribe(EventType.RATING, self._handle_rating)
        self.event_processor.subscribe(EventType.VIEW, self._handle_view)
        self.event_processor.subscribe(EventType.LIKE, self._handle_like)
        self.event_processor.subscribe(EventType.SEARCH, self._handle_search)

    def _handle_rating(self, event: UserEvent):
        """处理评分事件"""
        with self.lock:
            # 更新用户最近评分
            if event.user_id not in self.user_recent_events:
                self.user_recent_events[event.user_id] = []
            self.user_recent_events[event.user_id].append(event)

            # 触发增量更新
            self._trigger_incremental_update(event.user_id)

    def _handle_view(self, event: UserEvent):
        """处理浏览事件"""
        with self.lock:
            # 更新书籍热度
            self.book_popularity[event.book_id] = \
                self.book_popularity.get(event.book_id, 0) + 1

    def _handle_like(self, event: UserEvent):
        """处理点赞事件"""
        with self.lock:
            # 更新书籍热度
            self.book_popularity[event.book_id] = \
                self.book_popularity.get(event.book_id, 0) + 5

    def _handle_search(self, event: UserEvent):
        """处理搜索事件"""
        with self.lock:
            # 更新搜索趋势
            if event.metadata and 'query' in event.metadata:
                self._update_search_trends(event.metadata['query'])

    def _trigger_incremental_update(self, user_id: int):
        """触发增量更新任务"""
        # 通知 Celery 异步更新推荐
        try:
            from app.tasks.model_training import update_book_stats
            # 获取事件中的书籍 ID
            events = self.user_recent_events.get(user_id, [])
            if events:
                latest_event = events[-1]
                update_book_stats.delay(latest_event.book_id)
        except Exception as e:
            print(f"增量更新触发失败: {e}")

    def _update_search_trends(self, query: str):
        """更新搜索趋势"""
        # 实现搜索趋势分析
        pass

    def get_realtime_recommendations(
        self,
        user_id: int,
        n: int = 10
    ) -> List[Dict]:
        """获取实时推荐（结合实时行为）"""
        with self.lock:
            recent_events = self.user_recent_events.get(user_id, [])

            if not recent_events:
                return []

            # 基于最近行为生成即时推荐
            latest_book_id = recent_events[-1].book_id

            # 获取相似书籍
            from app.services.recommender import get_recommender
            try:
                recommender = get_recommender()
                recs = recommender.cf_recommend(user_id, n)
                return recs
            except:
                return []

    def get_trending_books(self, n: int = 10) -> List[Dict]:
        """获取热门书籍"""
        with self.lock:
            sorted_books = sorted(
                self.book_popularity.items(),
                key=lambda x: x[1],
                reverse=True
            )
            return [{"book_id": bid, "popularity": pop} for bid, pop in sorted_books[:n]]

    def start(self):
        """启动流式推荐服务"""
        self.event_processor.start_processing()
        print("✓ 实时流式推荐服务已启动")

    def stop(self):
        """停止流式推荐服务"""
        self.event_processor.stop_processing()
        print("✓ 实时流式推荐服务已停止")


# 全局流式推荐实例
_streaming_recommender = None


def get_streaming_recommender(db_session_factory) -> StreamingRecommender:
    """获取流式推荐器单例"""
    global _streaming_recommender
    if _streaming_recommender is None:
        _streaming_recommender = StreamingRecommender(db_session_factory)
    return _streaming_recommender
