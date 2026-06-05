"""插件内嵌 HTTP 服务器。

基于 aiohttp，提供：
- 监控面板（内置 HTML 模板）
- Bot 自写页面托管
- SSE 实时数据流
- REST API
"""

from typing import TYPE_CHECKING, Optional

import logging
import os
import socket

from aiohttp import web

from .routes import setup_routes

if TYPE_CHECKING:
    from ..plugin import MaiStudyCodePlugin

logger = logging.getLogger("plugin.maibot-team.mai-study-code.web")


def resolve_port(port: int, port_range_start: int, port_range_end: int) -> int:
    """根据配置决定监听端口。

    优先级：
    1. port > 0 → 直接使用指定端口
    2. port == 0 → 在 [port_range_start, port_range_end] 自动发现

    Args:
        port: 配置的端口（0=自动发现）。
        port_range_start: 自动发现起始端口。
        port_range_end: 自动发现结束端口。

    Returns:
        int: 可用端口号。

    Raises:
        RuntimeError: 指定端口被占用或范围内无可用端口。
    """
    if port > 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"指定端口 {port} 已被占用")
        return port

    # 自动发现
    for p in range(port_range_start, port_range_end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise RuntimeError(
        f"端口范围 {port_range_start}-{port_range_end} 全部被占用"
    )


class PluginWebServer:
    """插件内嵌 HTTP 服务器。

    在插件 on_load 时启动，on_unload 时停止。
    """

    def __init__(self, plugin: "MaiStudyCodePlugin") -> None:
        """初始化服务器。

        Args:
            plugin: 插件实例引用。
        """
        self._plugin = plugin
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._port: int = 0

    @property
    def port(self) -> int:
        """获取监听端口。"""
        return self._port

    async def start(self, host: str, port: int) -> int:
        """启动 HTTP 服务器。

        Args:
            host: 监听地址。
            port: 监听端口。

        Returns:
            int: 实际监听端口。
        """
        self._app = web.Application()
        self._app["plugin"] = self._plugin

        # 注册路由
        setup_routes(self._app, self._plugin)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, host, port)
        await site.start()
        self._port = port
        logger.info(f"Web 服务已启动: http://{host}:{port}")
        return port

    async def stop(self) -> None:
        """停止 HTTP 服务器。"""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            self._app = None
            logger.info("Web 服务已停止")
