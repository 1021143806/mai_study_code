"""Web 服务模块。

提供插件内嵌 HTTP 服务器，包括：
- 实时监控面板（SSE 推送）
- Bot 自写页面托管
- 主题皮肤系统
- REST API
"""

from .event_bus import EventBus
from .page_builder import PageBuilder
from .server import PluginWebServer

__all__ = ["EventBus", "PageBuilder", "PluginWebServer"]
