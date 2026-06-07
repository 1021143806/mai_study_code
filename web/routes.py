"""Web 路由定义。

注册所有 HTTP 路由：
- / → 监控面板
- /pages/<name> → Bot 自写页面
- /api/stream → SSE 实时数据流
- /api/status → 插件状态
- /api/pages → 页面索引
- /api/theme → 主题读写
- /api/knowledge → 知识库
- /api/cache → 缓存
- /api/sandbox → 沙箱
- /static/theme.css → 主题 CSS
"""

from typing import TYPE_CHECKING

import asyncio
import json
import logging
import os
import time
from typing import TYPE_CHECKING

from aiohttp import web

from ..sandbox import execute_with_safety_check
from .page_builder import PageBuilder

if TYPE_CHECKING:
    from ..plugin import MaiStudyCodePlugin

logger = logging.getLogger("plugin.maibot-team.mai-study-code.web")


def setup_routes(app: web.Application, plugin: "MaiStudyCodePlugin") -> None:
    """注册所有路由。

    Args:
        app: aiohttp Application 实例。
        plugin: 插件实例。
    """
    # 页面路由
    app.router.add_get("/", lambda r: _handle_monitor(r, plugin))
    app.router.add_get("/pages/{name}", lambda r: _handle_bot_page(r, plugin))
    app.router.add_get("/pages/", lambda r: _handle_bot_page_index(r, plugin))

    # API 路由
    app.router.add_get("/api/stream", lambda r: _handle_sse_stream(r, plugin))
    app.router.add_get("/api/status", lambda r: _handle_status(r, plugin))
    app.router.add_get("/api/pages", lambda r: _handle_page_list(r, plugin))
    app.router.add_get("/api/theme", lambda r: _handle_theme_get(r, plugin))
    app.router.add_post("/api/theme", lambda r: _handle_theme_post(r, plugin))
    app.router.add_get("/api/knowledge", lambda r: _handle_knowledge(r, plugin))
    app.router.add_get("/api/cache", lambda r: _handle_cache(r, plugin))
    app.router.add_get("/api/sandbox", lambda r: _handle_sandbox(r, plugin))
    app.router.add_get("/api/debug_log", lambda r: _handle_debug_log(r, plugin))
    app.router.add_get("/api/files", lambda r: _handle_files(r, plugin))
    app.router.add_get("/api/file", lambda r: _handle_file_read(r, plugin))
    app.router.add_post("/api/file/write", lambda r: _handle_file_write(r, plugin))
    app.router.add_post("/api/execute", lambda r: _handle_execute(r, plugin))
    app.router.add_post("/api/reload", lambda r: _handle_reload(r, plugin))

    # 静态文件
    app.router.add_get("/static/theme.css", lambda r: _handle_static_theme(r, plugin))


# ============================================================
# 页面处理
# ============================================================


async def _handle_monitor(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """监控面板首页。"""
    monitor_html = _load_monitor_html(plugin)
    return web.Response(text=monitor_html, content_type="text/html")


async def _handle_bot_page(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """Bot 自写页面。"""
    name = request.match_info.get("name", "index")
    # 安全检查：防止路径遍历
    if ".." in name or "/" in name or "\\" in name:
        raise web.HTTPNotFound()
    page_path = os.path.join(plugin._workspace_dir, "web", "pages", f"{name}.html")
    if not os.path.isfile(page_path):
        raise web.HTTPNotFound(text=f"页面不存在: {name}")
    with open(page_path, "r", encoding="utf-8") as f:
        content = f.read()
    return web.Response(text=content, content_type="text/html")


async def _handle_bot_page_index(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """Bot 页面索引（重定向到第一个页面或显示列表）。"""
    pages_dir = os.path.join(plugin._workspace_dir, "web", "pages")
    if not os.path.isdir(pages_dir):
        raise web.HTTPNotFound(text="暂无页面")
    # 列出所有页面
    builder = PageBuilder(plugin._workspace_dir)
    page_list = builder.list_pages()
    if not page_list:
        raise web.HTTPNotFound(text="暂无页面")
    # 生成简单的索引页
    links = "".join(
        f'<li><a href="/pages/{p["name"]}">{p["title"]}</a></li>'
        for p in page_list
    )
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>麦麦的页面</title>
<link rel="stylesheet" href="/static/theme.css">
</head>
<body style="padding:2rem;font-family:var(--font-sans);background:var(--bg-primary);color:var(--text-primary)">
<h1>📄 麦麦的页面</h1><ul>{links}</ul>
<p><a href="/" style="color:var(--color-info)">← 返回监控面板</a></p>
</body></html>"""
    return web.Response(text=html, content_type="text/html")


# ============================================================
# SSE 实时数据流
# ============================================================


async def _handle_sse_stream(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.StreamResponse:
    """SSE 实时数据流端点。

    事件类型：
    - stats: 每 2 秒全量统计快照
    - log: 操作事件即时推送
    """
    event_bus = plugin._event_bus
    if event_bus is None:
        raise web.HTTPServiceUnavailable(text="事件总线未初始化")

    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    await response.prepare(request)

    queue = event_bus.subscribe()
    try:
        # 立即发送初始统计
        stats = plugin.collect_stats()
        await response.write(
            f"event: stats\ndata: {json.dumps(stats, ensure_ascii=False)}\n\n".encode("utf-8")
        )

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=2.0)
                await response.write(
                    f"event: log\ndata: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")
                )
            except asyncio.TimeoutError:
                # 超时则推送统计快照
                stats = plugin.collect_stats()
                await response.write(
                    f"event: stats\ndata: {json.dumps(stats, ensure_ascii=False)}\n\n".encode("utf-8")
                )
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        event_bus.unsubscribe(queue)
    return response


# ============================================================
# REST API
# ============================================================


async def _handle_status(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """插件状态 API。"""
    stats = plugin.collect_stats()
    return web.json_response(stats)


async def _handle_page_list(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """页面索引 API。"""
    builder = PageBuilder(plugin._workspace_dir)
    pages = builder.list_pages()
    return web.json_response({"pages": pages})


async def _handle_theme_get(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """获取当前主题 CSS。"""
    theme_path = os.path.join(plugin._workspace_dir, "web", "theme.css")
    if os.path.isfile(theme_path):
        with open(theme_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = _default_theme_css()
    return web.Response(text=content, content_type="text/css")


async def _handle_theme_post(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """更新主题 CSS。"""
    body = await request.text()
    theme_path = os.path.join(plugin._workspace_dir, "web", "theme.css")
    os.makedirs(os.path.dirname(theme_path), exist_ok=True)
    with open(theme_path, "w", encoding="utf-8") as f:
        f.write(body)
    plugin._event_bus.publish("theme_update", {"message": "主题已更新"})
    return web.json_response({"success": True, "message": "主题已更新"})


async def _handle_knowledge(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """知识库 API。"""
    if plugin._knowledge_base:
        stats = plugin._knowledge_base.get_stats()
        return web.json_response(stats)
    return web.json_response({"error": "知识库未初始化"}, status=503)


async def _handle_cache(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """缓存 API。"""
    if plugin._cache:
        stats = plugin._cache.get_stats()
        return web.json_response(stats)
    return web.json_response({"error": "缓存未初始化"}, status=503)


async def _handle_sandbox(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """沙箱统计 API。"""
    stats = plugin._sandbox_stats or {}
    return web.json_response(stats)


async def _handle_debug_log(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """调试日志 API。

    Query 参数:
        count: 返回条数（默认 50，最大 200）。
    """
    if not plugin._debug_logger:
        return web.json_response({"error": "调试日志未启用"}, status=503)
    try:
        count = int(request.query.get("count", "50"))
    except (ValueError, TypeError):
        count = 50
    count = max(1, min(count, 200))
    logs = plugin._debug_logger.get_recent(count)
    return web.json_response({"logs": logs, "total": len(logs)})


async def _handle_files(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """工作区文件树 API。

    Query 参数:
        dir: 相对于工作区的子目录（可选，默认根目录）。
    """
    sub_dir = request.query.get("dir", "").strip()
    # 安全检查：防止路径遍历
    if ".." in sub_dir:
        return web.json_response({"error": "禁止访问上级目录"}, status=403)

    base_path = plugin._workspace_dir
    if sub_dir:
        base_path = os.path.join(base_path, sub_dir)
        if not os.path.realpath(base_path).startswith(os.path.realpath(plugin._workspace_dir)):
            return web.json_response({"error": "路径不在工作区内"}, status=403)

    if not os.path.isdir(base_path):
        return web.json_response({"error": "目录不存在"}, status=404)

    tree = _build_file_tree(base_path, plugin._workspace_dir)
    return web.json_response({"tree": tree, "root": sub_dir or "."})


async def _handle_file_read(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """读取工作区文件内容。

    Query 参数:
        path: 相对于工作区的文件路径。
    """
    file_path = request.query.get("path", "").strip()
    if not file_path:
        return web.json_response({"error": "缺少 path 参数"}, status=400)
    if ".." in file_path:
        return web.json_response({"error": "禁止访问上级目录"}, status=403)

    full_path = os.path.join(plugin._workspace_dir, file_path)
    real_path = os.path.realpath(full_path)
    if not real_path.startswith(os.path.realpath(plugin._workspace_dir)):
        return web.json_response({"error": "路径不在工作区内"}, status=403)

    if not os.path.isfile(real_path):
        return web.json_response({"error": "文件不存在"}, status=404)

    try:
        with open(real_path, "r", encoding="utf-8") as f:
            content = f.read()
        return web.json_response({"path": file_path, "content": content})
    except Exception as e:
        return web.json_response({"error": f"读取失败: {e}"}, status=500)


async def _handle_file_write(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """写入工作区文件。

    Body (JSON):
        path: 相对于工作区的文件路径。
        content: 文件内容。
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "请求体不是有效 JSON"}, status=400)

    file_path = str(body.get("path", "") or "").strip()
    content = str(body.get("content", "") or "")
    if not file_path:
        return web.json_response({"error": "缺少 path 参数"}, status=400)
    if ".." in file_path:
        return web.json_response({"error": "禁止访问上级目录"}, status=403)

    full_path = os.path.join(plugin._workspace_dir, file_path)
    real_path = os.path.realpath(full_path)
    if not real_path.startswith(os.path.realpath(plugin._workspace_dir)):
        return web.json_response({"error": "路径不在工作区内"}, status=403)

    try:
        os.makedirs(os.path.dirname(real_path), exist_ok=True)
        with open(real_path, "w", encoding="utf-8") as f:
            f.write(content)
        return web.json_response({"success": True, "path": file_path})
    except Exception as e:
        return web.json_response({"error": f"写入失败: {e}"}, status=500)


async def _handle_execute(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """执行 Python 代码。

    Body (JSON):
        code: Python 源码。
    """
    import asyncio as _asyncio

    try:
        body = await request.json()
    except Exception:
        body = {}

    code = str(body.get("code", "") or "").strip()
    if not code:
        return web.json_response({"error": "代码为空"}, status=400)

    try:
        future = _asyncio.get_running_loop().run_in_executor(
            None,
            lambda: execute_with_safety_check(code),
        )
        result = await _asyncio.wait_for(future, timeout=15)
    except _asyncio.TimeoutError:
        return web.json_response({"error": "执行超时"}, status=504)
    except Exception as e:
        return web.json_response({"error": f"执行异常: {e}"}, status=500)

    # 统计更新
    plugin._update_sandbox_stats(result.success, result.execution_time_ms)

    # 发布事件
    if plugin._event_bus:
        code_preview = code[:80].replace("\n", " ")
        plugin._event_bus.publish("exec", {
            "message": f"WebIDE: {code_preview}... → {'成功' if result.success else '失败'} {result.execution_time_ms:.0f}ms",
            "success": result.success,
            "time_ms": result.execution_time_ms,
        })

    return web.json_response({
        "success": result.success,
        "stdout": result.stdout or "",
        "stderr": result.stderr or "",
        "error": result.error or "",
        "execution_time_ms": result.execution_time_ms,
    })


async def _handle_reload(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """通过插件 SDK 热重载插件（只重载本插件，不重启 Bot 进程）。"""
    try:
        # 使用 SDK 的 component.reload_plugin 能力进行热重载
        result = await plugin.ctx.component.reload_plugin("mai_study_code")
        logger.info("插件热重载请求已发送")
        return web.json_response({"success": True, "message": "插件热重载请求已发送"})
    except Exception as e:
        logger.error(f"插件热重载失败: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def _handle_static_theme(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """静态主题 CSS 文件。"""
    theme_path = os.path.join(plugin._workspace_dir, "web", "theme.css")
    if os.path.isfile(theme_path):
        with open(theme_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = _default_theme_css()
    return web.Response(text=content, content_type="text/css")


# ============================================================
# 辅助函数
# ============================================================


def _load_monitor_html(plugin: "MaiStudyCodePlugin") -> str:
    """加载监控面板 HTML。

    优先从 workspace/web/monitor.html 读取（Bot 可自定义），
    否则使用内置模板。

    Args:
        plugin: 插件实例。

    Returns:
        str: 监控面板 HTML。
    """
    # 优先读取 Bot 自定义的监控面板
    custom_path = os.path.join(plugin._workspace_dir, "web", "monitor.html")
    if os.path.isfile(custom_path):
        with open(custom_path, "r", encoding="utf-8") as f:
            return f.read()

    # 使用内置模板
    builtin_path = os.path.join(os.path.dirname(__file__), "monitor.html")
    if os.path.isfile(builtin_path):
        with open(builtin_path, "r", encoding="utf-8") as f:
            return f.read()

    # 最终降级
    return _fallback_monitor_html()


def _fallback_monitor_html() -> str:
    """降级监控面板（当模板文件丢失时）。"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>麦麦学代码</title></head>
<body>
<h1>🐚 麦麦学代码</h1>
<p>监控面板模板丢失，请检查 web/monitor.html。</p>
</body>
</html>"""


def _default_theme_css() -> str:
    """默认主题 CSS。"""
    return """/* === 麦麦学代码 — 默认主题 === */
:root {
    --bg-primary: #1a1a2e;
    --bg-card: #16213e;
    --bg-input: #0f3460;
    --text-primary: #e0e0e0;
    --text-secondary: #888888;
    --text-muted: #555555;
    --accent: #0f3460;
    --accent-hover: #1a4a7a;
    --color-success: #4ecca3;
    --color-warning: #f0c040;
    --color-danger: #e74c3c;
    --color-info: #3498db;
    --border-color: #2a2a4a;
    --border-radius: 8px;
    --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
    --font-sans: system-ui, -apple-system, sans-serif;
    --spacing-xs: 0.25rem;
    --spacing-sm: 0.5rem;
    --spacing-md: 1rem;
    --spacing-lg: 1.5rem;
    --shadow-card: 0 2px 8px rgba(0, 0, 0, 0.3);
}
"""


def _build_file_tree(base_path: str, workspace_dir: str) -> list:
    """递归构建工作区文件树。

    Args:
        base_path: 要列举的根目录。
        workspace_dir: 工作区根目录（用于计算相对路径）。

    Returns:
        list: 文件/目录节点列表。
    """
    try:
        entries = sorted(os.listdir(base_path))
    except PermissionError:
        return []

    tree = []
    ignored = {".git", "__pycache__", ".pytest_cache", "logs", "backup", "dev", "test", "node_modules"}

    for name in entries:
        if name.startswith(".") and name != ".gitignore":
            continue
        if name in ignored:
            continue

        full_path = os.path.join(base_path, name)
        try:
            rel_path = os.path.relpath(full_path, workspace_dir)
        except ValueError:
            rel_path = name

        node = {
            "name": name,
            "path": rel_path,
            "is_dir": os.path.isdir(full_path),
        }

        if node["is_dir"]:
            node["children"] = _build_file_tree(full_path, workspace_dir)

        tree.append(node)

    return tree