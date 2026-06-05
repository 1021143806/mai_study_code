# 调试日志推送功能 — 实现计划

## 概述

方案 C：独立日志文件 + 交互时推送（混合方案）

- 关键日志写入 `workspace/debug.log` 持久化
- Web 面板新增 `/api/debug_log` 端点查看
- 当 super_user 与 Bot 交互时，在回复末尾附带积压的调试日志摘要

---

## 详细步骤

### 1. 新增 `[debug_log]` 配置段（config.toml）

```toml
[debug_log]
# 是否启用调试日志（写入文件 + 交互推送）
enabled = false

# 日志文件路径（相对于插件目录）
log_file = "workspace/debug.log"

# 日志文件最大大小（MB），超过后轮转
max_file_size_mb = 5

# 保留的轮转文件数
backup_count = 2

# 推送级别: info / warning / error
# info: 启动、操作、缓存等常规日志
# warning: 警告级别及以上
# error: 仅错误日志
push_level = "info"

# 交互推送时附带的最大日志条数
push_max_lines = 10

# 是否推送启动日志
notify_startup = true

# 是否推送操作日志（工具调用）
notify_operations = true

# 是否推送缓存状态
notify_cache_status = true

# 缓存状态推送冷却时间（秒），避免频繁推送
cache_status_cooldown = 300
```

### 2. 新增 `DebugLogConfig` 配置类（plugin.py）

在 `plugin.py` 中新增配置类，添加到 `MaiStudyCodeConfig`：

```python
class DebugLogConfig(PluginConfigBase):
    """调试日志配置。"""
    __ui_label__ = "调试日志"
    __ui_icon__ = "bug"
    __ui_order__ = 8

    enabled: bool = Field(default=False, description="是否启用调试日志")
    log_file: str = Field(default="workspace/debug.log", description="日志文件路径")
    max_file_size_mb: int = Field(default=5, description="日志文件最大大小 (MB)")
    backup_count: int = Field(default=2, description="保留的轮转文件数")
    push_level: str = Field(default="info", description="推送级别: info/warning/error")
    push_max_lines: int = Field(default=10, description="交互推送最大日志条数")
    notify_startup: bool = Field(default=True, description="是否推送启动日志")
    notify_operations: bool = Field(default=True, description="是否推送操作日志")
    notify_cache_status: bool = Field(default=True, description="是否推送缓存状态")
    cache_status_cooldown: int = Field(default=300, description="缓存状态推送冷却时间（秒）")
```

### 3. 创建 `debug_log/` 模块

新建 `debug_log/__init__.py` 和 `debug_log/logger.py`：

```
debug_log/
├── __init__.py      # 导出 DebugLogger
└── logger.py        # DebugLogger 核心实现
```

**DebugLogger 核心功能：**

- `log(level, category, message, details=None)` — 记录日志
  - level: "info" / "warning" / "error"
  - category: "startup" / "operation" / "cache" / "error" / "knowledge" / "emergency"
  - message: 简短描述
  - details: 可选的详细数据字典
- `get_recent(count)` — 获取最近 N 条日志
- `get_pending_summary()` — 获取待推送摘要（返回后清空待推送标记）
- `_write_to_file(entry)` — 写入日志文件
- `_rotate_if_needed()` — 日志轮转

**日志条目格式（写入文件）：**
```
[2026-05-18 13:16:31] [INFO] [startup] 插件加载完成，权限等级: root，工作区: /path/to/workspace
[2026-05-18 13:16:45] [INFO] [operation] execute_python: print('hello') → 成功 (15ms)
[2026-05-18 13:16:50] [INFO] [cache] 缓存命中率: 75% (15/20), 内存估算: 0.1M/1M 10%
[2026-05-18 13:17:00] [ERROR] [operation] execute_shell: rm -rf /tmp/test → 权限不足
```

**交互推送摘要格式（发送给 super_user）：**
```
📋 [mai_study 调试日志]
[13:16:31] ✅ 插件加载完成 | 权限: root | Web端口: 8701
[13:16:45] 🔍 execute_python 成功 (15ms) | print('hello')
[13:16:50] 💾 缓存: 15/500 (3%) | 命中率: 75%
[13:17:00] ❌ execute_shell 失败 | 权限不足
```

### 4. 在 plugin.py 集成 DebugLogger

**`__init__` 中新增：**
```python
self._debug_logger: Optional[DebugLogger] = None
self._last_cache_status_time: float = 0.0
```

**`on_load` 中初始化：**
```python
if self.config.debug_log.enabled:
    from .debug_log import DebugLogger
    log_path = os.path.join(plugin_dir, self.config.debug_log.log_file)
    self._debug_logger = DebugLogger(
        log_path=log_path,
        max_file_size_mb=self.config.debug_log.max_file_size_mb,
        backup_count=self.config.debug_log.backup_count,
        push_level=self.config.debug_log.push_level,
    )
    self._debug_logger.log("info", "startup", 
        f"插件加载完成，权限等级: {self.config.permissions.granted_level}，"
        f"工作区: {self._workspace_dir}"
        + (f"，Web 端口: {self._web_port}" if self._web_port else ""))
```

**`on_unload` 中清理：**
```python
if self._debug_logger:
    self._debug_logger.log("info", "startup", "插件正在卸载...")
    self._debug_logger = None
```

### 5. 在关键位置插入调试日志调用

需要在以下位置添加 `self._debug_logger.log(...)` 调用：

| 位置 | 类别 | 级别 | 内容 |
|------|------|------|------|
| `on_load` 完成 | startup | info | 插件加载完成信息 |
| `on_unload` | startup | info | 插件卸载 |
| `execute_python` 成功 | operation | info | 代码预览 + 耗时 |
| `execute_python` 失败 | operation | error | 代码预览 + 错误信息 |
| `execute_shell` 成功 | operation | info | 命令预览 + 耗时 |
| `execute_shell` 失败 | operation | error | 命令预览 + 错误信息 |
| `read_file` | operation | info | 文件路径 |
| `write_file` | operation | info | 文件路径 + 大小 |
| 缓存命中 | cache | info | 命中信息 |
| 缓存状态（冷却） | cache | info | 使用率统计 |
| 知识库新增 | knowledge | info | 笔记标题 |
| 紧急停止 | emergency | warning | 触发关键词 |
| 风险阻止 | operation | warning | 风险原因 |
| 权限拒绝 | operation | warning | 拒绝原因 |

### 6. Web 面板新增 `/api/debug_log` 端点

在 `web/routes.py` 中新增：

```python
app.router.add_get("/api/debug_log", lambda r: _handle_debug_log(r, plugin))
```

```python
async def _handle_debug_log(request: web.Request, plugin: "MaiStudyCodePlugin") -> web.Response:
    """调试日志 API。"""
    if not plugin._debug_logger:
        return web.json_response({"error": "调试日志未启用"}, status=503)
    count = int(request.query.get("count", "50"))
    logs = plugin._debug_logger.get_recent(min(count, 200))
    return web.json_response({"logs": logs, "total": len(logs)})
```

### 7. 交互推送机制

在 `handle_code_intent` EventHandler 中，处理完用户消息后，检查是否有待推送的调试日志：

```python
# 在 handle_code_intent 返回前
if self._debug_logger and self.config.debug_log.enabled:
    user_id = message.get("user_id", "") if isinstance(message, dict) else ""
    if user_id in self.config.permissions.super_users:
        summary = self._debug_logger.get_pending_summary(
            max_lines=self.config.debug_log.push_max_lines
        )
        if summary:
            await self.ctx.send.text(summary, stream_id)
```

### 8. 更新 .gitignore

```
workspace/debug.log
workspace/debug.log.*
```

### 9. 更新 README.md

在架构设计和配置说明中新增调试日志模块文档。

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `config.toml` | 修改 | 新增 `[debug_log]` 段 |
| `plugin.py` | 修改 | 新增 `DebugLogConfig`、集成 `DebugLogger`、插入日志调用 |
| `debug_log/__init__.py` | 新建 | 模块导出 |
| `debug_log/logger.py` | 新建 | `DebugLogger` 核心实现 |
| `web/routes.py` | 修改 | 新增 `/api/debug_log` 端点 |
| `.gitignore` | 修改 | 忽略调试日志文件 |
| `README.md` | 修改 | 新增调试日志文档 |
