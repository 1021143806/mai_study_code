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
import signal
import socket

from aiohttp import web

from .routes import setup_routes

if TYPE_CHECKING:
    from ..plugin import MaiStudyCodePlugin

logger = logging.getLogger("plugin.maibot-team.mai-study-code.web")


def _find_processes_on_port(port: int) -> list[int]:
    """查找占用指定端口的所有进程 PID。

    不排除当前进程。当前进程此时尚未 bind 端口，
    不会出现在 lsof 结果中。而僵尸进程正是需要被清理的目标。

    Args:
        port: 目标端口。

    Returns:
        list[int]: PID 列表，如果没有则返回空列表。
    """
    try:
        result = os.popen(f"lsof -ti :{port} 2>/dev/null").read().strip()
        if result:
            return [int(pid) for pid in result.split()]
    except Exception:
        pass
    return []


def _kill_processes(pids: list[int], port: int) -> bool:
    """尝试终止指定 PID 列表的所有进程。

    先对所有进程发 SIGTERM，等待后检查；残留进程再发 SIGKILL。
    不排除当前进程——僵尸进程本来就是之前的自身。

    Args:
        pids: 进程 PID 列表。
        port: 端口号（仅用于日志）。

    Returns:
        bool: 是否成功释放端口。
    """
    if not pids:
        return True

    logger.warning(f"端口 {port} 被以下进程占用: {pids}，尝试终止...")

    # 第一轮：SIGTERM
    import time

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception as e:
            logger.error(f"发送 SIGTERM 到 PID {pid} 失败: {e}")

    time.sleep(2)

    # 检查是否还有残留进程
    remaining = []
    for pid in pids:
        try:
            os.kill(pid, 0)  # 空信号检测进程是否存在
            remaining.append(pid)
        except OSError:
            pass

    if remaining:
        logger.warning(f"以下进程未响应 SIGTERM: {remaining}，发送 SIGKILL...")
        for pid in remaining:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error(f"发送 SIGKILL 到 PID {pid} 失败: {e}")
        time.sleep(1)

    return True


def resolve_port(port: int) -> int:
    """检查并准备指定端口。

    如果端口被占用，尝试找到并终止占用进程。
    如果无法释放端口，则抛出 RuntimeError。

    Args:
        port: 配置的固定端口。

    Returns:
        int: 确认可用的端口号。

    Raises:
        RuntimeError: 端口被占用且无法释放，或释放后仍被占用。
    """
    if port <= 0:
        raise RuntimeError(f"无效的端口号: {port}，必须 > 0")

    # 检查端口是否可用
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if s.connect_ex(("127.0.0.1", port)) != 0:
            return port  # 端口可用

    # 端口被占用，查找并清理僵尸进程
    pids = _find_processes_on_port(port)
    _kill_processes(pids, port)

    # 再次检查端口
    import time

    time.sleep(0.5)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if s.connect_ex(("127.0.0.1", port)) != 0:
            logger.info(f"端口 {port} 已释放")
            return port

    raise RuntimeError(f"端口 {port} 被占用，且无法自动释放")


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
        site = web.TCPSite(self._runner, host, port, reuse_address=True)
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
