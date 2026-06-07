"""独立进程 Web 服务。

替代插件体系中的 PluginWebServer + routes.py + 前端全部。
自持 aiohttp 服务器，提供完整的 WebUI 监控面板和管理 API。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import aiohttp
import asyncio
import json
import logging
import os
import time
from aiohttp import web
from pathlib import Path

from .config import AgentConfig
from .llm_client import LLMClient
from .agent_loop import AgentLoop

logger = logging.getLogger("mai-study-code.web")

# 插件目录路径（用于定位前端静态文件和子模块）
_PLUGIN_DIR = Path(__file__).resolve().parent.parent
_WEB_DIR = _PLUGIN_DIR / "web"
_STATIC_DIR = _WEB_DIR / "static"
_NPM_CACHE_DIR = _WEB_DIR / ".npm_cache"


class AgentWebServer:
    """智能体 Web 服务。

    自持 aiohttp 服务器，提供完整功能：
    - 监控面板（前端 React-like SPA）
    - 代码对话 API
    - 管理 API（状态/配置/缓存/沙箱/知识库）
    - 工作区管理
    - 静态文件服务 + CDN 代理
    """

    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._app = web.Application()
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self.port: int = config.port
        self._start_time: float = time.time()

        # LLM 客户端 + AgentLoop
        self._llm_client = LLMClient(config.llm)
        self._agent = AgentLoop(config=config, llm_client=self._llm_client)

        # 注册所有路由
        self._setup_routes()

    def _setup_routes(self) -> None:
        """注册所有路由。"""
        # ── 监控面板 ──
        self._app.router.add_get("/", self._handle_monitor)

        # ── 对话 API ──
        self._app.router.add_post("/api/chat", self._handle_chat)
        self._app.router.add_get("/api/chat/history", self._handle_chat_history)

        # ── 管理 API ──
        self._app.router.add_get("/api/status", self._handle_status)
        self._app.router.add_get("/api/config", self._handle_config)
        self._app.router.add_get("/api/cache", self._handle_cache)
        self._app.router.add_get("/api/sandbox", self._handle_sandbox)
        self._app.router.add_get("/api/knowledge", self._handle_knowledge)
        self._app.router.add_get("/api/token", self._handle_token_stats)
        self._app.router.add_get("/api/debug_log", self._handle_debug_log)

        # ── 文件管理 API ──
        self._app.router.add_get("/api/files", self._handle_files_list)
        self._app.router.add_get("/api/file", self._handle_file_read)
        self._app.router.add_post("/api/file/write", self._handle_file_write)

        # ── 代码执行 API ──
        self._app.router.add_post("/api/execute", self._handle_execute)

        # ── 工作区 API ──
        self._app.router.add_get("/api/workspaces", self._handle_workspaces_list)

        # ── 静态文件 ──
        self._app.router.add_get("/static/{path:.+}", self._handle_static_file)
        self._app.router.add_get("/monaco/{path:.+}", self._handle_monaco_file)
        self._app.router.add_get("/npm/{path:.+}", self._handle_npm_proxy)

    # ── 监控面板 ──

    async def _handle_monitor(self, request: web.Request) -> web.Response:
        """监控面板首页。"""
        html_path = _WEB_DIR / "monitor.html"
        if not html_path.exists():
            return web.Response(text="monitor.html 不存在", status=404)
        return web.FileResponse(str(html_path))

    # ── 对话 API ──

    async def _handle_chat(self, request: web.Request) -> web.Response:
        """对话 API。"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "请求体不是有效 JSON"}, status=400)

        messages = body.get("messages", [])
        if not messages or not isinstance(messages, list):
            return web.json_response({"error": "缺少 messages"}, status=400)

        cwd = str(body.get("cwd", "") or "").strip()
        if ".." in cwd:
            cwd = ""

        result = await self._agent.run(messages, cwd)
        self._save_chat_history(messages)

        return web.json_response({
            "success": True,
            "response": result.get("response", ""),
            "model": result.get("model", ""),
            "tool_results": result.get("tool_results", []),
            "cwd": result.get("cwd", cwd),
        })

    async def _handle_chat_history(self, request: web.Request) -> web.Response:
        """获取聊天记录。"""
        ws_name = request.query.get("workspace", "").strip() or "default"
        safe = ws_name.replace("/", "_").replace(" ", "_").replace("\\", "_")
        path = _PLUGIN_DIR / "data" / "chat" / f"{safe}.json"
        try:
            with open(path) as f:
                data = json.load(f)
            return web.json_response(data)
        except (FileNotFoundError, json.JSONDecodeError):
            return web.json_response({"messages": [], "cwd": ""})

    def _save_chat_history(self, messages: List[Dict[str, Any]]) -> None:
        """保存聊天记录。"""
        try:
            chat_dir = _PLUGIN_DIR / "data" / "chat"
            chat_dir.mkdir(parents=True, exist_ok=True)
            path = chat_dir / "default.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"messages": messages, "cwd": ""}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── 管理 API ──

    async def _handle_status(self, request: web.Request) -> web.Response:
        """状态 API：系统运行状态概览。"""
        token_stats = self._agent.get_token_stats()
        return web.json_response({
            "status": "running",
            "port": self.port,
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "llm_model": self._config.llm.model,
            "llm_base_url": self._config.llm.base_url,
            "sandbox": self._agent.get_sandbox_stats(),
            "token": token_stats,
        })

    async def _handle_config(self, request: web.Request) -> web.Response:
        """配置 API。"""
        return web.json_response(self._config.to_dict())

    async def _handle_cache(self, request: web.Request) -> web.Response:
        """缓存 API。"""
        return web.json_response({
            "note": "缓存由 MaiBot 插件层管理，当前进程为独立智能体",
            "max_entries": self._config.cache.max_entries,
            "ttl_seconds": self._config.cache.ttl_seconds,
        })

    async def _handle_sandbox(self, request: web.Request) -> web.Response:
        """沙箱统计 API。"""
        return web.json_response(self._agent.get_sandbox_stats())

    async def _handle_knowledge(self, request: web.Request) -> web.Response:
        """知识库 API。"""
        from ..learner import KnowledgeBase
        kb = KnowledgeBase(str(_PLUGIN_DIR / self._config.learner.knowledge_dir))
        stats = kb.get_stats()
        return web.json_response(stats)

    async def _handle_token_stats(self, request: web.Request) -> web.Response:
        """Token 统计 API。"""
        return web.json_response(self._agent.get_token_stats())

    async def _handle_debug_log(self, request: web.Request) -> web.Response:
        """调试日志 API。"""
        try:
            count = int(request.query.get("count", "50"))
        except (ValueError, TypeError):
            count = 50
        count = max(1, min(count, 200))
        log_path = _PLUGIN_DIR / self._config.debug_log.log_file
        if not log_path.exists():
            return web.json_response({"logs": [], "total": 0})
        try:
            with open(log_path) as f:
                lines = f.readlines()
            return web.json_response({"logs": lines[-count:], "total": len(lines)})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    # ── 文件管理 API ──

    async def _handle_files_list(self, request: web.Request) -> web.Response:
        """列出工作区文件。"""
        workspaces_dir = _PLUGIN_DIR / "workspace"
        if not workspaces_dir.exists():
            return web.json_response({"files": []})
        try:
            items = []
            for entry in workspaces_dir.iterdir():
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": entry.stat().st_size if entry.is_file() else 0,
                })
            items.sort(key=lambda x: (not x["is_dir"], x["name"]))
            return web.json_response({"files": items})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_file_read(self, request: web.Request) -> web.Response:
        """读取文件。"""
        path_str = request.query.get("path", "").strip()
        if not path_str:
            return web.json_response({"error": "缺少 path 参数"}, status=400)
        safe_path = _PLUGIN_DIR / "workspace" / path_str
        safe_path = safe_path.resolve()
        if not str(safe_path).startswith(str(_PLUGIN_DIR.resolve())):
            return web.json_response({"error": "路径越界"}, status=403)
        if not safe_path.exists():
            return web.json_response({"error": "文件不存在"}, status=404)
        if safe_path.is_dir():
            try:
                items = []
                for entry in safe_path.iterdir():
                    items.append({"name": entry.name, "is_dir": entry.is_dir()})
                items.sort(key=lambda x: (not x["is_dir"], x["name"]))
                return web.json_response({"type": "dir", "files": items})
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)
        try:
            content = safe_path.read_text(encoding="utf-8", errors="replace")
            return web.json_response({"type": "file", "content": content[:50000]})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_file_write(self, request: web.Request) -> web.Response:
        """写入文件。"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "请求体不是 JSON"}, status=400)
        path_str = str(body.get("path", "")).strip()
        content = str(body.get("content", ""))
        if not path_str:
            return web.json_response({"error": "缺少 path"}, status=400)
        safe_path = _PLUGIN_DIR / "workspace" / path_str
        safe_path = safe_path.resolve()
        if not str(safe_path).startswith(str(_PLUGIN_DIR.resolve())):
            return web.json_response({"error": "路径越界"}, status=403)
        try:
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            safe_path.write_text(content, encoding="utf-8")
            return web.json_response({"success": True})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    # ── 代码执行 API ──

    async def _handle_execute(self, request: web.Request) -> web.Response:
        """执行 Python 代码（沙箱）。"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "请求体不是 JSON"}, status=400)
        code = str(body.get("code", "")).strip()
        if not code:
            return web.json_response({"error": "缺少 code"}, status=400)

        from ..sandbox import execute_with_safety_check
        try:
            future = asyncio.get_running_loop().run_in_executor(
                None, lambda: execute_with_safety_check(code),
            )
            result = await asyncio.wait_for(future, timeout=15)
            return web.json_response({
                "success": result.success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": result.error,
                "execution_time_ms": result.execution_time_ms,
            })
        except asyncio.TimeoutError:
            return web.json_response({"success": False, "error": "执行超时"})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)})

    # ── 工作区 API ──

    async def _handle_workspaces_list(self, request: web.Request) -> web.Response:
        """列出工作区。"""
        workspaces_dir = _PLUGIN_DIR / "workspace"
        if not workspaces_dir.exists():
            workspaces_dir.mkdir(parents=True)
        try:
            dirs = []
            for entry in workspaces_dir.iterdir():
                if entry.is_dir():
                    dirs.append(entry.name)
            return web.json_response({"workspaces": sorted(dirs), "active": dirs[0] if dirs else ""})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    # ── 静态文件 ──

    async def _handle_static_file(self, request: web.Request) -> web.Response:
        """静态文件服务。"""
        path = request.match_info.get("path", "")
        file_path = _STATIC_DIR / path
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(_STATIC_DIR.resolve())):
            return web.Response(text="Forbidden", status=403)
        if file_path.exists() and file_path.is_file():
            return web.FileResponse(str(file_path))
        return web.Response(text="Not Found", status=404)

    async def _handle_monaco_file(self, request: web.Request) -> web.Response:
        """Monaco Editor 文件服务。"""
        from ..web.routes import _handle_monaco_file
        return await _handle_monaco_file(request)

    async def _handle_npm_proxy(self, request: web.Request) -> web.Response:
        """npm CDN 代理。"""
        from ..web.routes import _handle_npm_proxy
        return await _handle_npm_proxy(request)

    # ── 服务生命周期 ──

    async def start(self) -> None:
        """启动 HTTP 服务。"""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        host = self._config.host
        port = self._config.port

        self._site = web.TCPSite(self._runner, host, port)
        await self._site.start()

        # 获取实际端口（port=0 时系统分配）
        for sock in self._site._server.sockets:
            self.port = sock.getsockname()[1]
            break

        logger.info(f"Web 服务已启动: http://{host}:{self.port}")

    async def stop(self) -> None:
        """停止 HTTP 服务。"""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        logger.info("Web 服务已停止")
