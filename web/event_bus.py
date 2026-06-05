"""插件内事件总线。

收集操作日志供 SSE 实时推送，各 Tool handler 在执行操作时发布事件。
"""

from typing import Any, Dict, List

import asyncio
import time
from collections import deque


class EventBus:
    """插件内事件总线。

    收集操作日志供 SSE 推送。使用 deque 限制内存占用。
    """

    def __init__(self, max_events: int = 200) -> None:
        """初始化事件总线。

        Args:
            max_events: 最大保留事件数。
        """
        self._events: deque = deque(maxlen=max_events)
        self._subscribers: List[asyncio.Queue] = []

    def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """发布事件，通知所有 SSE 订阅者。

        Args:
            event_type: 事件类型（如 "exec", "cache_hit", "topic_switch"）。
            data: 事件数据。
        """
        event = {
            "type": event_type,
            "timestamp": time.time(),
            "data": data,
        }
        self._events.append(event)
        # 通知所有订阅者
        dead_queues = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
            except Exception:
                dead_queues.append(queue)
        # 清理已失效的订阅者
        for queue in dead_queues:
            self._subscribers.remove(queue)

    def subscribe(self) -> asyncio.Queue:
        """创建新的订阅队列。

        Returns:
            asyncio.Queue: 事件队列，最大 100 条。
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """取消订阅。

        Args:
            queue: 要取消的订阅队列。
        """
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    def get_recent(self, count: int = 50) -> List[Dict[str, Any]]:
        """获取最近的事件。

        Args:
            count: 返回的事件数量。

        Returns:
            List[Dict]: 最近的事件列表。
        """
        events = list(self._events)
        return events[-count:]
