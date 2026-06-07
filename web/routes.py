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
    app.router.add_post("/api/file/delete", lambda r: _handle_file_delete(r, plugin))
    app.router.add_post("/api/file/rename", lambda r: _handle_file_rename(r, plugin))
    app.router.add_post("/api/file/create", lambda r: _handle_file_create(r, plugin))
    app.router.add_post("/api/execute", lambda r: _handle_execute(r, plugin))
    app.router.add_post("/api/reload", lambda r: _handle_reload(r, plugin))
    app.router.add_post("/api/chat", lambda r: _handle_chat(r, plugin))
    app.router.add_post("/api/token/compress", lambda r: _handle_token_compress(r, plugin))
    app.router.add_post("/api/token/max-tokens", lambda r: _handle_token_max_tokens(r, plugin))

    # 工作区 API
    app.router.add_get("/api/workspaces", lambda r: _handle_workspaces_list(r, plugin))
    app.router.add_get("/api/workspaces/{name}", lambda r: _handle_workspaces_detail(r, plugin))
    app.router.add_post("/api/workspaces", lambda r: _handle_workspaces_save(r, plugin))
    app.router.add_delete("/api/workspaces/{name}", lambda r: _handle_workspaces_delete(r, plugin))
    app.router.add_post("/api/workspaces/{name}/activate", lambda r: _handle_workspaces_activate(r, plugin))
    app.router.add_post("/api/workspaces/{name}/test", lambda r: _handle_workspaces_test(r, plugin))

    # 插件配置 API
    app.router.add_get("/api/plugin-config", lambda r: _handle_plugin_config_get(r, plugin))
    app.router.add_post("/api/plugin-config", lambda r: _handle_plugin_config_save(r, plugin))

    # 权限等级 API
    app.router.add_get("/api/level", lambda r: _handle_level(r, plugin))

    # 聊天记录 API
    app.router.add_get("/api/chat/history", lambda r: _handle_chat_history(r, plugin))

    # 静态文件 & CDN 代理
    app.router.add_get("/static/theme.css", lambda r: _handle_static_theme(r, plugin))
    # 通用静态文件服务（CSS, JS, 图片等）
    app.router.add_get("/static/{path:.+}", lambda r: _handle_static_file(r, plugin))
    # Monaco Editor 服务
    app.router.add_get("/monaco/{path:.+}", lambda r: _handle_monaco_file(r))
    # 代理 jsDelivr /npm/ 路径，用于本地化 CodeMirror ESM 依赖
    app.router.add_get("/npm/{path:.+}", lambda r: _handle_npm_proxy(r))


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
        workspace: 工作区名称（可选，默认当前活动工作区）。
    """
    sub_dir = request.query.get("dir", "").strip()
    ws_name = request.query.get("workspace", "").strip()

    # 如果指定了工作区，使用工作区管理器
    if ws_name or (plugin._workspace_manager and plugin._workspace_manager.get_active()):
        mgr = plugin._workspace_manager
        if mgr is None:
            return web.json_response({"error": "工作区管理器未初始化"}, status=500)
        result = mgr.list_files(path=sub_dir, workspace=ws_name)
        if result.get("success"):
            return web.json_response(result)
        return web.json_response({"error": result.get("error", "未知错误")}, status=500)

    # 旧逻辑（向后兼容）
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
        path: 文件路径。
        workspace: 工作区名称（可选）。
    """
    file_path = request.query.get("path", "").strip()
    if not file_path:
        return web.json_response({"error": "缺少 path 参数"}, status=400)

    ws_name = request.query.get("workspace", "").strip()
    if ws_name or (plugin._workspace_manager and plugin._workspace_manager.get_active()):
        mgr = plugin._workspace_manager
        if mgr is None:
            return web.json_response({"error": "工作区管理器未初始化"}, status=500)
        result = mgr.read_file(path=file_path, workspace=ws_name)
        if result.get("success"):
            return web.json_response({"path": file_path, "content": result.get("content", "")})
        return web.json_response({"error": result.get("error", "读取失败")}, status=500)

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
        path: 文件路径。
        content: 文件内容。
        workspace: 工作区名称（可选）。
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "请求体不是有效 JSON"}, status=400)
    file_path = str(body.get("path", "") or "").strip()
    content = str(body.get("content", "") or "")
    if not file_path:
        return web.json_response({"error": "缺少 path 参数"}, status=400)

    ws_name = str(body.get("workspace", "") or "").strip()
    if ws_name or (plugin._workspace_manager and plugin._workspace_manager.get_active()):
        mgr = plugin._workspace_manager
        if mgr is None:
            return web.json_response({"error": "工作区管理器未初始化"}, status=500)
        result = mgr.write_file(path=file_path, content=content, workspace=ws_name)
        if result.get("success"):
            return web.json_response({"success": True, "path": file_path})
        return web.json_response({"error": result.get("error", "写入失败")}, status=500)

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


async def _handle_file_delete(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """删除文件或目录。"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "请求体不是有效 JSON"}, status=400)
    file_path = str(body.get("path", "") or "").strip()
    if not file_path:
        return web.json_response({"error": "缺少 path 参数"}, status=400)
    ws_name = str(body.get("workspace", "") or "").strip()
    mgr = plugin._workspace_manager
    if ws_name or (mgr and mgr.get_active()):
        ws = mgr.get_workspace(ws_name or mgr.get_active())
        if not ws:
            return web.json_response({"error": "工作区不存在"}, status=404)
        return await _delete_via_workspace(ws, file_path)
    # 旧逻辑向后兼容
    full_path = os.path.join(plugin._workspace_dir, file_path)
    if not os.path.realpath(full_path).startswith(os.path.realpath(plugin._workspace_dir)):
        return web.json_response({"error": "路径不在工作区内"}, status=403)
    return _delete_local(full_path, file_path)


async def _delete_via_workspace(ws, path: str) -> web.Response:
    """通过工作区实例删除文件/目录。"""
    full = ws._resolve(path)
    return _delete_local(full, path)


def _delete_local(full_path: str, display_path: str) -> web.Response:
    try:
        if os.path.isfile(full_path):
            os.remove(full_path)
            return web.json_response({"success": True, "path": display_path})
        elif os.path.isdir(full_path):
            os.rmdir(full_path)  # 只删除空目录
            return web.json_response({"success": True, "path": display_path})
        else:
            return web.json_response({"error": "路径不存在"}, status=404)
    except OSError as e:
        return web.json_response({"error": f"删除失败: {e}", "path": display_path}, status=400)


async def _handle_file_rename(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """重命名文件或目录。"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "请求体不是有效 JSON"}, status=400)
    old_path = str(body.get("path", "") or "").strip()
    new_name = str(body.get("name", "") or "").strip()
    if not old_path or not new_name:
        return web.json_response({"error": "缺少 path 或 name 参数"}, status=400)
    ws_name = str(body.get("workspace", "") or "").strip()
    mgr = plugin._workspace_manager
    if ws_name or (mgr and mgr.get_active()):
        ws = mgr.get_workspace(ws_name or mgr.get_active())
        if not ws:
            return web.json_response({"error": "工作区不存在"}, status=404)
        return await _rename_via_workspace(ws, old_path, new_name)
    full_old = os.path.join(plugin._workspace_dir, old_path)
    parent = os.path.dirname(full_old)
    full_new = os.path.join(parent, new_name)
    if not os.path.realpath(full_old).startswith(os.path.realpath(plugin._workspace_dir)):
        return web.json_response({"error": "路径不在工作区内"}, status=403)
    return _rename_local(full_old, full_new, old_path, new_name)


async def _rename_via_workspace(ws, old_path: str, new_name: str) -> web.Response:
    full_old = ws._resolve(old_path)
    parent = os.path.dirname(full_old)
    full_new = os.path.join(parent, new_name)
    return _rename_local(full_old, full_new, old_path, new_name)


def _rename_local(full_old: str, full_new: str, display_old: str, display_new: str) -> web.Response:
    try:
        os.rename(full_old, full_new)
        return web.json_response({"success": True, "path": display_old, "name": display_new})
    except OSError as e:
        return web.json_response({"error": f"重命名失败: {e}"}, status=400)


async def _handle_file_create(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """新建文件或目录。"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "请求体不是有效 JSON"}, status=400)
    parent_dir = str(body.get("parent", "") or "").strip()
    name = str(body.get("name", "") or "").strip()
    is_dir = body.get("is_dir", False)
    if not name:
        return web.json_response({"error": "缺少 name 参数"}, status=400)
    ws_name = str(body.get("workspace", "") or "").strip()
    mgr = plugin._workspace_manager
    if ws_name or (mgr and mgr.get_active()):
        ws = mgr.get_workspace(ws_name or mgr.get_active())
        if not ws:
            return web.json_response({"error": "工作区不存在"}, status=404)
        return await _create_via_workspace(ws, parent_dir, name, is_dir)
    base = plugin._workspace_dir
    if parent_dir:
        base = os.path.join(base, parent_dir)
    full = os.path.join(base, name)
    if not os.path.realpath(full).startswith(os.path.realpath(plugin._workspace_dir)):
        return web.json_response({"error": "路径不在工作区内"}, status=403)
    return _create_local(full, name, is_dir)


async def _create_via_workspace(ws, parent_dir: str, name: str, is_dir: bool) -> web.Response:
    base = ws._resolve(parent_dir)
    full = os.path.join(base, name)
    return _create_local(full, name, is_dir)


def _create_local(full_path: str, name: str, is_dir: bool) -> web.Response:
    try:
        if is_dir:
            os.makedirs(full_path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            if not os.path.isfile(full_path):
                open(full_path, "a").close()
        return web.json_response({"success": True, "name": name, "is_dir": is_dir})
    except OSError as e:
        return web.json_response({"error": f"创建失败: {e}"}, status=400)


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


async def _handle_chat(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """Claude Code 风格对话（支持读写文件、执行代码）。

    Body (JSON):
        messages: 消息列表 [{role, content}, ...]
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "请求体不是有效 JSON"}, status=400)

    messages = body.get("messages", [])
    if not messages or not isinstance(messages, list):
        return web.json_response({"error": "缺少 messages 或格式错误"}, status=400)

    # 接收前端传入的当前工作目录（相对路径，相对于工作区根）
    cwd = str(body.get("cwd", "") or "").strip()
    # 防止路径遍历
    if ".." in cwd:
        cwd = ""

    # 根据权限等级筛选可用工具
    granted_level = str(plugin.config.permissions.granted_level)
    level_names = {
        "0": "游客", "1": "访客", "2": "开发者",
        "3": "管理员", "4": "超级用户", "root": "超级用户",
    }

    # 等级 → 可用工具映射
    _all_tools = {
        "read_file": {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取文件内容。如果路径是目录会自动列出目录内容。",
                "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "文件或目录路径（相对于当前目录）"}}, "required": ["path"]}
            }
        },
        "list_dir": {
            "type": "function",
            "function": {
                "name": "list_dir",
                "description": "列出指定目录下的文件和子目录",
                "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "目录路径（相对于当前目录，省略则列出当前目录）"}}, "required": []}
            }
        },
        "write_file": {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "创建或覆盖工作区文件",
                "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "文件路径"}, "content": {"type": "string", "description": "文件内容"}}, "required": ["path", "content"]}
            }
        },
        "execute_code": {
            "type": "function",
            "function": {
                "name": "execute_code",
                "description": "在沙箱中执行 Python 代码并返回结果",
                "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "Python 代码"}}, "required": ["code"]}
            }
        },
        "create_dir": {
            "type": "function",
            "function": {
                "name": "create_dir",
                "description": "创建工作区内的目录",
                "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "目录路径（相对于当前目录）"}}, "required": ["path"]}
            }
        },
        "change_dir": {
            "type": "function",
            "function": {
                "name": "change_dir",
                "description": "切换当前工作目录到指定的子目录。后续读写文件操作将基于新目录。",
                "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "目标目录路径（相对于当前目录，使用 .. 返回上级）"}}, "required": ["path"]}
            }
        },
    }
    # 各等级可用的工具名
    _level_tools = {
        "0": [],
        "1": ["read_file"],
        "2": ["read_file", "write_file", "execute_code", "create_dir", "change_dir", "list_dir"],
        "3": ["read_file", "write_file", "execute_code", "create_dir", "change_dir", "list_dir"],
        "4": ["read_file", "write_file", "execute_code", "create_dir", "change_dir", "list_dir"],
        "root": ["read_file", "write_file", "execute_code", "create_dir", "change_dir", "list_dir"],
    }
    allowed = _level_tools.get(granted_level, ["read_file"])
    tools = [_all_tools[name] for name in allowed]

    # 获取工作区根路径
    ws_root = ""
    ws_mgr = plugin._workspace_manager
    if ws_mgr:
        active_ws = ws_mgr.get_active_workspace()
        if active_ws:
            ws_root = active_ws.to_dict().get("path", "") or ""

    try:
        # 注入当前工作目录上下文
        enhanced_messages = list(messages)
        if ws_root:
            context = f"当前工作目录: {ws_root}"
            if cwd:
                context = f"当前工作目录: {ws_root}/{cwd}\n你位于 {cwd} 子目录中。"
                context += "\n读写文件时路径相对于当前目录。使用 change_dir 切换目录，使用 .. 返回上级。"
            else:
                context += "\n你位于工作区根目录。读写文件时使用相对于此目录的路径。"
            enhanced_messages.insert(0, {
                "role": "system",
                "content": context,
            })

        # 工具执行循环：最多 3 轮，整体限时 60 秒
        all_tool_results = []
        final_response = ""
        model = ""
        _token_pricing = getattr(plugin.config, '_token_pricing', {
            "input_price_per_1k": 0.001,
            "output_price_per_1k": 0.002,
            "cache_hit_price_per_1k": 0.0001,
        })

        for _round in range(3):
            import asyncio as _wait
            try:
                result = await _wait.wait_for(
                    plugin.ctx.llm.generate_with_tools(
                        prompt=enhanced_messages,
                        tools=tools,
                        model="replyer",
                    ),
                    timeout=25,
                )
            except _wait.TimeoutError:
                result = {"response": "（生成超时）", "tool_calls": [], "error": "timeout"}

            # ── Token 统计与 SSE 推送 ──
            prompt_tokens = int(result.get("prompt_tokens", 0) or 0)
            completion_tokens = int(result.get("completion_tokens", 0) or 0)
            total_tokens = prompt_tokens + completion_tokens
            cache_hit_tokens = int(result.get("cache_hit_tokens", 0) or 0)
            if prompt_tokens > 0 and total_tokens > 0:
                input_cost = (prompt_tokens / 1000) * _token_pricing["input_price_per_1k"]
                output_cost = (completion_tokens / 1000) * _token_pricing["output_price_per_1k"]
                cost = round(input_cost + output_cost, 6)
                bar_data = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cache_hit_tokens": cache_hit_tokens,
                    "cost": cost,
                    "label": "对话",
                    "model": model or result.get("model", ""),
                }
                # 记录到插件统计缓存
                plugin.record_token_bar(bar_data)
                # 通过 SSE 推送到前端
                if plugin._event_bus:
                    plugin._event_bus.publish("token_bar", bar_data)

            response_text = result.get("response", "") or result.get("content", "")
            model = result.get("model", model)
            tool_calls = result.get("tool_calls", []) or []

            if response_text and not tool_calls:
                # 纯文本回复，没有需要执行的工具 → 这就是最终回复
                final_response = response_text
                break

            # 有工具调用：暂存本轮文本（如果有），后续会被最终回复覆盖
            if response_text:
                final_response = response_text

            if not tool_calls:
                break

            # 执行工具
            ws = plugin._workspace_manager
            ws_name = ws.get_active() if ws else ""
            round_results = []

            for tc in tool_calls:
                func_name = tc.get("function", {}).get("name", "") if isinstance(tc, dict) else getattr(tc, "func_name", "")
                args_raw = tc.get("function", {}).get("arguments", "{}") if isinstance(tc, dict) else "{}"
                try:
                    if isinstance(args_raw, str):
                        import json as _json
                        args = _json.loads(args_raw)
                    else:
                        args = args_raw
                except Exception:
                    args = {}

                def _resolve(p: str) -> str:
                    if not p or p.startswith("/") or "../" in p.replace("\\", "/"):
                        return p
                    return f"{cwd}/{p}" if cwd else p

                result_entry = {"tool": func_name, "input": "", "output": "", "success": False}

                try:
                    if func_name == "read_file" or func_name == "list_dir":
                        path = args.get("path", "") if func_name == "list_dir" else _resolve(args.get("path", ""))
                        if not path:
                            path = cwd or "."
                        else:
                            path = _resolve(path)
                        result_entry["input"] = path
                        if ws:
                            fr = ws.read_file(path, workspace=ws_name)
                            if not fr.get("success") and "不存在" in str(fr.get("error", "")):
                                dir_list = ws.list_files(path, workspace=ws_name)
                                if dir_list.get("success"):
                                    tree = dir_list.get("tree", [])
                                    lines = [f"{'📁' if n.get('is_dir') else '📄'} {n['name']}" for n in tree]
                                    result_entry["output"] = "\n".join(lines) if lines else "(空目录)"
                                    result_entry["success"] = True
                                else:
                                    result_entry["output"] = fr.get("error", "文件不存在")
                            else:
                                result_entry["output"] = fr.get("content", fr.get("error", "未知错误"))[:3000]
                                result_entry["success"] = fr.get("success", False)
                        else:
                            result_entry["output"] = "工作区未初始化"

                    elif func_name == "write_file":
                        path = _resolve(args.get("path", ""))
                        content = args.get("content", "")
                        result_entry["input"] = f"{path} ({len(content)} chars)"
                        if ws:
                            fr = ws.write_file(path, content, workspace=ws_name)
                            result_entry["output"] = "已保存" if fr.get("success") else fr.get("error", "失败")
                            result_entry["success"] = fr.get("success", False)
                        else:
                            result_entry["output"] = "工作区未初始化"

                    elif func_name == "change_dir":
                        target = args.get("path", "")
                        result_entry["input"] = target
                        if target == "..":
                            if cwd:
                                parts = cwd.rstrip("/").split("/")
                                parts.pop()
                                cwd = "/".join(parts)
                        elif target.startswith("/"):
                            cwd = target.lstrip("/")
                        else:
                            cwd = f"{cwd}/{target}".lstrip("/") if cwd else target
                        cwd_parts = []
                        for part in cwd.split("/"):
                            if part == ".." and cwd_parts:
                                cwd_parts.pop()
                            elif part != "..":
                                cwd_parts.append(part)
                        cwd = "/".join(cwd_parts)
                        result_entry["output"] = f"已切换到 {cwd or '(根目录)'}"
                        result_entry["success"] = True

                    elif func_name == "create_dir":
                        dir_path = _resolve(args.get("path", ""))
                        result_entry["input"] = dir_path
                        if ws:
                            fr = ws.write_file(f"{dir_path}/.gitkeep", "", workspace=ws_name)
                            result_entry["output"] = "目录已创建"
                            result_entry["success"] = True
                        else:
                            result_entry["output"] = "工作区未初始化"

                    elif func_name == "execute_code":
                        code = args.get("code", "")
                        result_entry["input"] = code[:100]
                        from ..sandbox import execute_with_safety_check as _exec_check
                        import asyncio as _asyncio
                        try:
                            future = _asyncio.get_running_loop().run_in_executor(None, lambda: _exec_check(code))
                            er = await _asyncio.wait_for(future, timeout=15)
                            result_entry["output"] = er.stdout if er.success else (er.stderr or er.error or "")
                            result_entry["success"] = er.success
                            # 更新统计
                            try:
                                plugin._update_sandbox_stats(er.success, er.execution_time_ms)
                            except Exception:
                                pass
                        except _asyncio.TimeoutError:
                            result_entry["output"] = "执行超时"
                        except Exception as e:
                            result_entry["output"] = f"执行异常: {e}"

                    else:
                        result_entry["output"] = f"未知工具: {func_name}"

                except Exception as e:
                    result_entry["output"] = str(e)

                round_results.append(result_entry)
                all_tool_results.append(result_entry)

            # 将本次工具调用加入对话历史（assistant 消息 + tool 结果）
            assistant_tc_msg = {
                "role": "assistant",
                "content": "",
                "tool_calls": [],
            }
            for tc in tool_calls:
                if isinstance(tc, dict):
                    assistant_tc_msg["tool_calls"].append({
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tc.get("function", {}).get("name", ""),
                            "arguments": tc.get("function", {}).get("arguments", "{}"),
                        },
                    })
            enhanced_messages.append(assistant_tc_msg)

            for i, tr in enumerate(round_results):
                tc_id = ""
                if i < len(tool_calls):
                    tc_id = tool_calls[i].get("id", "") if isinstance(tool_calls[i], dict) else getattr(tool_calls[i], "call_id", "")
                enhanced_messages.append({
                    "role": "tool",
                    "content": f"[{tr['tool']}] {tr['output'][:2000]}",
                    "tool_call_id": tc_id,
                })
        else:
            # 超过 5 轮，用最后一次的回复
            if not final_response:
                final_response = response_text or "(达到最大轮次)"

        error = result.get("error", "")

        # 流式传输支持
        if body.get("stream"):
            import json as _sjson
            import asyncio as _asyncio
            resp = web.StreamResponse(status=200, reason="OK", headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            })
            await resp.prepare(request)
            # 发送工具结果事件
            for tr in all_tool_results:
                line = f"event: tool\ndata: {_sjson.dumps(tr, ensure_ascii=False)}\n\n"
                await resp.write(line.encode("utf-8"))
            # 流式发送文本回复（逐段）
            if final_response:
                text = final_response
                chunks = text.split(" ")
                buf = ""
                for chunk in chunks:
                    buf += chunk + " "
                    if len(buf) >= 30:
                        await resp.write(f"event: text\ndata: {buf}\n\n".encode("utf-8"))
                        buf = ""
                        await _asyncio.sleep(0.02)
                if buf.strip():
                    await resp.write(f"event: text\ndata: {buf}\n\n".encode("utf-8"))
            # 发送完成事件
            await resp.write(f"event: done\ndata: {_sjson.dumps({'cwd': cwd, 'level': granted_level, 'level_name': level_names.get(granted_level, granted_level)}, ensure_ascii=False)}\n\n".encode("utf-8"))
            # 保存聊天记录
            _save_chat_history(messages, cwd, plugin)
            return resp

        # 保存聊天记录
        _save_chat_history(messages, cwd, plugin)

        # 非流式：返回完整 JSON
        return web.json_response({
            "success": True,
            "response": final_response or "",
            "model": model,
            "tool_results": all_tool_results,
            "level": granted_level,
            "level_name": level_names.get(granted_level, granted_level),
            "cwd": cwd,
            "ws_root": ws_root,
        })
    except Exception as e:
        logger.error(f"对话生成失败: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


_CHAT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "chat"))


def _save_chat_history(messages, cwd, plugin):
    """保存聊天记录到 data/chat/{workspace_name}.json"""
    try:
        import json as _json
        ws_name = ""
        if plugin._workspace_manager:
            ws_name = plugin._workspace_manager.get_active() or "default"
        safe_name = ws_name.replace("/", "_").replace(" ", "_").replace("\\", "_")
        os.makedirs(_CHAT_DIR, exist_ok=True)
        path = os.path.join(_CHAT_DIR, f"{safe_name}.json")
        with open(path, "w", encoding="utf-8") as f:
            _json.dump({"messages": messages, "cwd": cwd}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


async def _handle_chat_history(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """获取指定工作区的聊天记录。"""
    ws_name = request.query.get("workspace", "").strip()
    if not ws_name and plugin._workspace_manager:
        ws_name = plugin._workspace_manager.get_active() or ""
    safe_name = ws_name.replace("/", "_").replace(" ", "_").replace("\\", "_")
    path = os.path.join(_CHAT_DIR, f"{safe_name}.json")
    try:
        import json as _json
        with open(path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        return web.json_response(data)
    except (FileNotFoundError, ValueError):
        return web.json_response({"messages": [], "cwd": ""})


def _get_ws(request: web.Request, plugin: "MaiStudyCodePlugin", required: bool = True):
    """从请求中获取工作区管理器及当前工作区名。"""
    mgr = plugin._workspace_manager
    if mgr is None:
        if required:
            raise web.HTTPInternalServerError(text="工作区管理器未初始化")
        return None, ""
    ws_name = request.query.get("workspace", "") or mgr.get_active()
    return mgr, ws_name


async def _handle_workspaces_list(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """列出所有工作区。"""
    mgr = plugin._workspace_manager
    if mgr is None:
        return web.json_response({"workspaces": [], "active": ""})
    return web.json_response({
        "workspaces": mgr.list_workspaces(),
        "active": mgr.get_active(),
    })


async def _handle_workspaces_detail(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """获取单个工作区详情。"""
    mgr = plugin._workspace_manager
    if mgr is None:
        return web.json_response({"error": "工作区管理器未初始化"}, status=500)
    name = request.match_info.get("name", "")
    ws = mgr.get_workspace(name)
    if ws is None:
        return web.json_response({"error": "工作区不存在"}, status=404)
    return web.json_response(ws.to_dict())


async def _handle_workspaces_save(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """添加或更新工作区。"""
    mgr = plugin._workspace_manager
    if mgr is None:
        return web.json_response({"success": False, "error": "工作区管理器未初始化"}, status=500)
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "请求体不是有效 JSON"}, status=400)
    ok, msg = mgr.add_or_update(body)
    return web.json_response({"success": ok, "message": msg})


async def _handle_workspaces_delete(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """删除工作区。"""
    mgr = plugin._workspace_manager
    if mgr is None:
        return web.json_response({"success": False, "error": "工作区管理器未初始化"}, status=500)
    name = request.match_info.get("name", "")
    ok, msg = mgr.remove(name)
    return web.json_response({"success": ok, "message": msg})


async def _handle_workspaces_activate(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """切换活动工作区。"""
    mgr = plugin._workspace_manager
    if mgr is None:
        return web.json_response({"success": False, "error": "工作区管理器未初始化"}, status=500)
    name = request.match_info.get("name", "")
    ok, msg = mgr.set_active(name)
    return web.json_response({"success": ok, "message": msg})


async def _handle_workspaces_test(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """测试工作区连接。"""
    mgr = plugin._workspace_manager
    if mgr is None:
        return web.json_response({"success": False, "error": "工作区管理器未初始化"}, status=500)
    name = request.match_info.get("name", "")
    result = mgr.test_connection(name)
    return web.json_response(result)


_PLUGIN_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_CONFIG_PATH = os.path.join(_PLUGIN_DIR, "config.toml")


async def _handle_plugin_config_get(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """获取插件配置文件内容。"""
    if not os.path.isfile(_CONFIG_PATH):
        return web.json_response({"error": "配置文件不存在"}, status=404)
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return web.json_response({"content": content, "path": _CONFIG_PATH})
    except Exception as e:
        return web.json_response({"error": f"读取失败: {e}"}, status=500)


async def _handle_plugin_config_save(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """保存插件配置文件。"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "请求体不是有效 JSON"}, status=400)
    content = str(body.get("content", "") or "")
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        # 触发热重载
        try:
            await plugin.ctx.config.reload("self", plugin_id=plugin.ctx.plugin_id)
        except Exception:
            pass
        return web.json_response({"success": True, "message": "配置已保存"})
    except Exception as e:
        return web.json_response({"error": f"保存失败: {e}"}, status=500)


async def _handle_level(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """返回当前权限等级。"""
    granted = str(plugin.config.permissions.granted_level)
    level_names = {
        "0": "游客", "1": "访客", "2": "开发者",
        "3": "管理员", "4": "超级用户", "root": "超级用户",
    }
    return web.json_response({
        "level": granted,
        "name": level_names.get(granted, granted),
        "super_users": list(plugin.config.permissions.super_users or []),
    })


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


_NPM_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".npm_cache")

# 版本归一化：将所有 @codemirror/* 子包重定向到同一版本
# 解决多版本共存导致的 instanceof 冲突
_VERSION_MAP = {
    "@codemirror/state": "6.5.2",
    "@codemirror/view": "6.37.2",
    "@codemirror/language": "6.11.1",
    "@codemirror/commands": "6.8.1",
    "@codemirror/search": "6.5.11",
    "@codemirror/autocomplete": "6.18.6",
    "@codemirror/lint": "6.8.5",
    "@lezer/common": "1.2.3",
    "@lezer/highlight": "1.2.1",
    "@lezer/lr": "1.4.0",
    "@marijn/find-cluster-break": "1.0.2",
    "style-mod": "4.1.2",
    "crelt": "1.0.6",
    "w3c-keyname": "2.2.8",
}


def _normalize_npm_path(path: str) -> str:
    """将 @codemirror/* 子包的版本号统一为同一版本。"""
    import re as _re
    for pkg, ver in _VERSION_MAP.items():
        # 匹配 @scope/name@version 或 name@version
        escaped = _re.escape(pkg)
        pattern = rf'^{escaped}@\d+\.\d+\.\d+'
        if _re.match(pattern, path):
            rest = path[len(pkg) + len(_re.search(r'@\d+\.\d+\.\d+', path).group()):]
            return f"{pkg}@{ver}{rest}"
    return path

_STATIC_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "static"))
_MONACO_DIR = os.path.normpath(os.path.join(_STATIC_DIR, "monaco-editor"))


async def _handle_static_file(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """通用静态文件服务。"""
    path = request.match_info.get("path", "")
    full_path = os.path.normpath(os.path.join(_STATIC_DIR, path))
    if not full_path.startswith(_STATIC_DIR):
        raise web.HTTPNotFound()
    if not os.path.isfile(full_path):
        raise web.HTTPNotFound()
    ext_map = {
        ".css": "text/css",
        ".js": "application/javascript",
        ".mjs": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".ttf": "font/ttf",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
    }
    _, ext = os.path.splitext(path)
    ct = ext_map.get(ext.lower(), "application/octet-stream")
    with open(full_path, "rb") as f:
        body = f.read()
    return web.Response(body=body, content_type=ct)


async def _handle_monaco_file(request: web.Request) -> web.Response:
    """服务 Monaco Editor 的静态文件（vs/ 目录下的所有资源）。

    Monaco 使用 AMD require 按需加载模块，所有模块路径相对于
    /monaco/vs/，因此这个路由必须正确处理 vs/ 下所有子路径。
    """
    path = request.match_info.get("path", "")
    full_path = os.path.normpath(os.path.join(_MONACO_DIR, path))
    if not full_path.startswith(_MONACO_DIR):
        raise web.HTTPNotFound()
    if not os.path.isfile(full_path):
        raise web.HTTPNotFound()
    ext_map = {
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".ttf": "font/ttf",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".map": "application/json",
    }
    _, ext = os.path.splitext(path)
    ct = ext_map.get(ext.lower(), "application/octet-stream")
    # Monaco 的 JS 文件是 AMD 格式，不需要 module 类型
    with open(full_path, "rb") as f:
        body = f.read()
    return web.Response(body=body, content_type=ct)


async def _handle_npm_proxy(request: web.Request) -> web.Response:
    """代理 jsDelivr /npm/ 路径（带本地磁盘缓存 + 版本归一化）。

    首次请求从 CDN 拉取并缓存到本地，后续直接从缓存响应。
    版本归一化确保所有 @codemirror/* 子包使用同一版本，避免 instanceof 冲突。
    """
    path = request.match_info.get("path", "")
    # 版本归一化
    normalized_path = _normalize_npm_path(path)
    if normalized_path != path:
        logger.debug(f"版本归一化: {path} → {normalized_path}")
        path = normalized_path
    # 本地缓存路径
    cache_path = os.path.join(_NPM_CACHE_DIR, path.replace("/", "_").replace("@", "_"))
    # 尝试从缓存读取
    if os.path.isfile(cache_path):
        with open(cache_path, "rb") as f:
            body = f.read()
        ct = "application/javascript"
        if path.endswith(".css"):
            ct = "text/css"
        elif path.endswith(".map"):
            ct = "application/json"
        return web.Response(body=body, content_type=ct)

    # 缓存未命中，从 CDN 拉取
    url = f"https://cdn.jsdelivr.net/npm/{path}"
    try:
        import aiohttp as _aiohttp
        async with _aiohttp.ClientSession() as session:
            async with session.get(url, timeout=_aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return web.Response(status=resp.status, text=f"CDN 返回 {resp.status}")
                body = await resp.read()
                # 写入缓存
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, "wb") as f:
                    f.write(body)
                ct = resp.content_type or "application/javascript"
                return web.Response(body=body, content_type=ct)
    except Exception as e:
        logger.error(f"CDN 代理失败 [{path}]: {e}")
        return web.Response(status=502, text=f"CDN 代理失败: {e}")


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


async def _handle_token_compress(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """手动触发缓存压缩。

    Body (JSON) 可选:
        threshold: 压缩阈值百分比（可选，仅调整不压缩）。
        compress: 是否执行压缩（默认 true）。
    """
    import asyncio as _asyncio

    try:
        body = await request.json()
    except Exception:
        body = {}

    do_compress = bool(body.get("compress", True))

    if do_compress and plugin._cache:
        # 记录压缩前状态
        before = plugin._cache.estimate_tokens(plugin._cache._context_turns)
        # 执行上下文裁剪：丢弃最旧轮次直到低于 50% 水位
        max_tokens = plugin._cache._context_max_tokens
        target = max_tokens // 2
        removed = 0
        while plugin._cache._context_turns and plugin._cache.estimate_tokens(plugin._cache._context_turns) > target:
            if len(plugin._cache._context_turns) >= 2:
                plugin._cache._context_turns.pop(0)
                plugin._cache._context_turns.pop(0)
                removed += 1
            else:
                plugin._cache._context_turns.pop(0)
                removed += 1

        after = plugin._cache.estimate_tokens(plugin._cache._context_turns)
        freed = before - after

        # 发布事件
        if plugin._event_bus:
            plugin._event_bus.publish("log", {
                "message": f"🧹 上下文压缩完成，释放 {freed} tok（{removed} 轮次）",
                "level": "info",
            })

        return web.json_response({
            "success": True,
            "freed": max(freed, 0),
            "remaining": after,
            "removed_rounds": removed,
        })

    # 仅查询状态
    used = plugin._cache.estimate_tokens(plugin._cache._context_turns) if plugin._cache else 0
    max_ctx = plugin._cache._context_max_tokens if plugin._cache else 8000
    return web.json_response({
        "success": True,
        "compress": False,
        "used": used,
        "max": max_ctx,
    })


async def _handle_token_max_tokens(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """更新上下文最大 token 数并持久化到 config.toml。

    Body (JSON):
        max_tokens: int — 新的上限值。
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "请求体不是有效 JSON"}, status=400)

    new_max = int(body.get("max_tokens", 0) or 0)
    if new_max < 512 or new_max > 1048576:
        return web.json_response({"success": False, "error": "max_tokens 必须在 512 ~ 1048576 之间"}, status=400)

    # 更新 config.toml
    import os as _os
    import tomllib as _tomllib
    import tomlkit as _tomlkit

    plugin_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    config_path = _os.path.join(plugin_dir, "config.toml")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            doc = _tomlkit.load(f)
        doc.setdefault("cache", {})["context_max_tokens"] = new_max
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(_tomlkit.dumps(doc))
    except Exception as e:
        return web.json_response({"success": False, "error": f"写入配置失败: {e}"}, status=500)

    # 更新运行时缓存配置
    current_config = plugin.get_plugin_config_data()
    if "cache" in current_config and isinstance(current_config["cache"], dict):
        current_config["cache"]["context_max_tokens"] = new_max
    # 如果插件实例有 _cache，直接设置上限
    if plugin._cache:
        plugin._cache._context_max_tokens = new_max

    # 热重载插件配置
    try:
        await plugin.ctx.config.reload("self", plugin_id=plugin.ctx.plugin_id)
    except Exception:
        pass  # 即使重载失败也不影响已写入的配置

    logger.info(f"上下文最大 token 已更新为 {new_max}")

    if plugin._event_bus:
        plugin._event_bus.publish("log", {
            "message": f"⚙️ 上下文上限已更新为 {new_max} tok",
            "level": "info",
        })

    return web.json_response({"success": True, "max_tokens": new_max})