# 方案 A：插件内自起 HTTP 服务器 — 详细设计

> 目标：在 `mai_study_code` 插件内启动一个独立的 HTTP 服务，让 Bot（LLM）可以动态生成网页内容，并通过 MaiBot WebUI 的 iframe 嵌入展示。

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────┐
│  MaiBot WebUI (FastAPI :8001)                       │
│  ┌───────────────────────────────────────────────┐  │
│  │  Dashboard SPA (React)                        │  │
│  │  ┌─────────────────────────────────────────┐  │  │
│  │  │  iframe: /plugin/mai_study_code/        │  │  │
│  │  │  → 代理到 localhost:87xx                │  │  │
│  │  └─────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                          │ proxy pass
                          ▼
┌─────────────────────────────────────────────────────┐
│  插件内 HTTP Server (aiohttp :87xx)                 │
│  ┌───────────────────────────────────────────────┐  │
│  │  /                    → 动态首页（LLM 生成）   │  │
│  │  /api/status          → 插件状态 API          │  │
│  │  /api/knowledge       → 知识库查询 API        │  │
│  │  /api/cache           → 缓存统计 API          │  │
│  │  /api/sandbox/stats   → 沙箱统计 API          │  │
│  │  /api/regenerate      → 触发 LLM 重新生成页面 │  │
│  │  /static/             → 静态资源（CSS/JS）    │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## 2. 端口策略

支持两种模式，优先级从高到低：

### 模式 1：指定固定端口（推荐生产使用）

在 `[web]` 配置中直接指定 `port`，跳过自动发现：

```toml
[web]
port = 8700   # 指定固定端口
```

### 模式 2：自动发现（默认，适合开发）

当 `port = 0` 或不配置时，在端口范围内自动扫描第一个可用端口：

```toml
[web]
port = 0                    # 0 = 自动发现
port_range_start = 8700     # 扫描起始
port_range_end = 8799       # 扫描结束
```

### 端口选择逻辑

```python
import socket

def resolve_port(config: WebConfig) -> int:
    """根据配置决定监听端口。

    优先级：
    1. config.port > 0 → 直接使用指定端口
    2. config.port == 0 → 在 [port_range_start, port_range_end] 自动发现
    """
    if config.port > 0:
        # 检查指定端口是否可用
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", config.port)) == 0:
                raise RuntimeError(f"指定端口 {config.port} 已被占用")
        return config.port

    # 自动发现
    for port in range(config.port_range_start, config.port_range_end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(
        f"端口范围 {config.port_range_start}-{config.port_range_end} 全部被占用"
    )
```

---

## 3. 新增文件结构

```
plugins/mai_study_code/
├── web/                        # 新增：Web 服务模块
│   ├── __init__.py             # 模块入口
│   ├── server.py               # HTTP 服务器（aiohttp）
│   ├── routes.py               # 路由定义
│   └── page_builder.py         # LLM 页面生成器
├── plugin.py                   # 修改：在 on_load/on_unload 中启停服务
├── config.toml                 # 修改：新增 [web] 配置段
└── ...
```

---

## 4. 核心模块设计

### 4.1 `web/server.py` — HTTP 服务器

使用 **aiohttp**（MaiBot 已有依赖），轻量且异步：

```python
from aiohttp import web

class PluginWebServer:
    def __init__(self, plugin: "MaiStudyCodePlugin"):
        self._plugin = plugin
        self._app = web.Application()
        self._runner = None
        self._port = 0

    async def start(self, port: int) -> int:
        """启动服务器，返回实际监听端口"""
        self._setup_routes()
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", port)
        await site.start()
        self._port = port
        return port

    async def stop(self):
        """停止服务器"""
        if self._runner:
            await self._runner.cleanup()
```

### 4.2 `web/routes.py` — 路由定义

| 路由 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 动态首页，由 LLM 生成的 HTML |
| `/api/status` | GET | 插件运行状态（JSON） |
| `/api/knowledge` | GET | 知识库条目列表 |
| `/api/knowledge/search?q=` | GET | 搜索知识库 |
| `/api/cache/stats` | GET | 缓存统计 |
| `/api/sandbox/stats` | GET | 沙箱执行统计 |
| `/api/regenerate` | POST | 触发 LLM 重新生成首页 |
| `/api/page-content` | GET | 获取当前页面内容（供 LLM 读取） |

### 4.3 `web/page_builder.py` — LLM 页面生成器

这是核心亮点：**让 Bot 自己写网页**。

```python
class PageBuilder:
    """由 LLM 驱动的动态页面生成器。

    工作流程：
    1. 用户通过聊天让 Bot "更新你的网页，加一个知识库搜索框"
    2. Bot 调用 execute_shell 或直接操作 workspace/web/index.html
    3. Bot 用 write_file Tool 写入新的 HTML
    4. 网页服务直接 serve workspace/web/ 目录下的文件
    """

    def __init__(self, workspace_dir: str):
        self._web_dir = os.path.join(workspace_dir, "web")
        os.makedirs(self._web_dir, exist_ok=True)

    def get_index_html(self) -> str:
        """获取当前首页 HTML"""
        path = os.path.join(self._web_dir, "index.html")
        if os.path.exists(path):
            return open(path).read()
        return self._default_page()

    def _default_page(self) -> str:
        """默认首页"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>麦麦学代码</title>
    <style>
        body { font-family: system-ui; max-width: 800px; margin: 0 auto; padding: 2rem; }
        .card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
    </style>
</head>
<body>
    <h1>🐚 麦麦学代码</h1>
    <p>这是麦麦的代码学习面板。麦麦可以自己修改这个页面！</p>
    <div id="status" class="card">加载中...</div>
    <script>
        fetch('/api/status').then(r=>r.json()).then(d=>{
            document.getElementById('status').innerHTML =
                `<h3>状态</h3>
                 <p>权限等级: ${d.granted_level}</p>
                 <p>缓存条目: ${d.cache_entries}</p>
                 <p>知识库条目: ${d.knowledge_entries}</p>`;
        });
    </script>
</body>
</html>"""
```

### 4.4 Bot 如何修改网页

Bot 通过已有的 Tool 来操作网页文件：

1. **`read_file`** → 读取 `workspace/web/index.html` 查看当前页面
2. **`write_file`** → 写入新的 `workspace/web/index.html`
3. **`apply_diff`** → 精确修改页面中的某一部分
4. **`execute_shell`** → 重启 web 服务（如果需要）

用户只需在聊天中说：
- "麦麦，给你的网页加一个暗色模式切换"
- "在你的面板上显示最近的缓存命中率"
- "把知识库搜索功能加到你的网页上"

Bot 就会自己修改 `workspace/web/index.html`，页面立即生效。

---

## 5. 配置扩展

在 `config.toml` 中新增 `[web]` 配置段：

```toml
[web]
# 是否启用 Web 服务
enabled = true

# 监听地址（仅本地，安全）
host = "127.0.0.1"

# 监听端口（0 = 自动在范围内发现，>0 = 固定端口）
port = 0

# 自动发现端口范围（仅 port=0 时生效）
port_range_start = 8700
port_range_end = 8799

# 页面自动刷新间隔（秒，0=不刷新）
auto_refresh_sec = 30
```

在 `plugin.py` 的 `MaiStudyCodeConfig` 中新增对应配置类：

```python
class WebConfig(PluginConfigBase):
    """Web 服务配置。"""

    __ui_label__ = "Web 服务"
    __ui_icon__ = "globe"
    __ui_order__ = 7

    enabled: bool = Field(default=False, description="是否启用 Web 服务")
    host: str = Field(default="127.0.0.1", description="监听地址")
    port: int = Field(default=0, description="监听端口（0=自动发现）")
    port_range_start: int = Field(default=8700, description="自动发现起始端口")
    port_range_end: int = Field(default=8799, description="自动发现结束端口")
    auto_refresh_sec: int = Field(default=30, description="页面自动刷新间隔（秒）")
```

---

## 6. 认证方案

由于是 `127.0.0.1` 监听，外部无法直接访问，安全风险较低。两种可选方案：

### 方案 A1：简单共享 secret（推荐）
- 插件启动时生成一个随机 token
- 通过 `bot_config.toml` 或环境变量共享给 WebUI
- 前端 iframe 通过 `?token=xxx` 传递
- 服务端验证 token

### 方案 A2：无认证（最简）
- 仅监听 `127.0.0.1`，依赖操作系统级别的进程隔离
- 适合快速原型阶段

---

## 7. 与 WebUI 集成

### 7.1 前端 iframe 嵌入

在 MaiBot Dashboard 的插件配置页面中，可以通过以下方式嵌入：

1. **插件配置页 iframe**：在 `plugin-config.tsx` 中检测插件是否提供 `web_url`，如果是则渲染 iframe
2. **独立路由**：在 Dashboard 路由中添加 `/plugin/mai_study_code` 路由，内嵌 iframe

但这需要修改 Dashboard 前端代码。如果不想改前端，可以：

3. **直接访问**：用户直接在浏览器访问 `http://host:87xx/`
4. **反向代理**：在 nginx/caddy 中添加 `location /plugin/mai_study_code/ { proxy_pass http://127.0.0.1:87xx/; }`

### 7.2 postMessage 通信（可选）

iframe 内的页面可以通过 `window.parent.postMessage()` 与 Dashboard 通信：

```javascript
// 插件页面 → Dashboard
window.parent.postMessage({
    type: 'mai_study_code.navigate',
    payload: { route: '/config' }
}, '*');
```

---

## 8. 实时监控面板（Dashboard）

类似 Kilo Code 的实时状态窗口，通过 **SSE (Server-Sent Events)** 推送 + **原生 JS 渲染**，无需任何前端框架。

### 8.1 面板布局

```
┌──────────────────────────────────────────────────────────┐
│  🐚 麦麦学代码 — 实时监控                    [端口: 87xx] │
├────────────┬─────────────────────┬────────────────────────┤
│  沙箱状态   │   缓存状态           │   知识库               │
│  ┌────────┐ │  ┌─────────────────┐│  ┌──────────────────┐ │
│  │ 执行次数 │ │  │ 命中率 ████░░  ││  │ 总条目: 42       │ │
│  │   127   │ │  │ 78% (56/72)    ││  │ 分类: note/12... │ │
│  │ 成功 118 │ │  │ 活跃: 34      ││  │ 最近: 列表推导式  │ │
│  │ 失败   9 │ │  │ 过期: 5       ││  │                  │ │
│  │ 平均 3ms│ │  │ 容量: 34/500  ││  │                  │ │
│  └────────┘ │  └─────────────────┘│  └──────────────────┘ │
├────────────┴─────────────────────┴────────────────────────┤
│  上下文窗口                                               │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 轮次: 6/20  │  Token 估算: 3200/8000                 │ │
│  │ ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 40%          │ │
│  └──────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────┤
│  实时日志流 (SSE)                                         │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ [14:32:01] execute_python: print('hello') → 成功 2ms │ │
│  │ [14:32:05] 缓存命中: SHA256=abc123...                │ │
│  │ [14:32:10] 话题切换: 数学计算 → 文件操作              │ │
│  │ [14:32:15] execute_shell: df -h → 成功 150ms         │ │
│  │ [14:32:20] 知识库新增: 列表推导式                     │ │
│  └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 8.2 实时数据推送 — SSE

使用 **Server-Sent Events** 实现服务端到浏览器的单向实时推送：

```
客户端                         服务端
  │                              │
  │──── GET /api/stream ────────>│  (建立 SSE 连接)
  │                              │
  │<──── event: stats ──────────│  (每 2s 推送全量统计)
  │      data: {cache:...,      │
  │             sandbox:...,    │
  │             knowledge:...}  │
  │                              │
  │<──── event: log ───────────│  (事件发生时即时推送)
  │      data: {type: "exec",  │
  │             code: "...",   │
  │             result: "ok"}  │
```

**SSE 端点**：`GET /api/stream`

**事件类型**：

| event 类型 | 触发时机 | 数据内容 |
|-----------|---------|---------|
| `stats` | 每 2 秒定时 | 全量统计快照（缓存、沙箱、知识库、上下文） |
| `log` | 即时 | 操作日志（执行、缓存命中、话题切换、知识库写入等） |
| `heartbeat` | 每 30 秒 | 保活信号 |

### 8.3 数据采集 — 插件内事件钩子

在 `plugin.py` 中增加一个轻量的事件总线，各模块操作时发布事件：

```python
import time
import asyncio
from collections import deque
from typing import Any, Dict, List

class EventBus:
    """插件内事件总线，收集操作日志供 SSE 推送。"""

    def __init__(self, max_events: int = 200):
        self._events: deque = deque(maxlen=max_events)
        self._subscribers: List[asyncio.Queue] = []

    def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """发布事件，通知所有 SSE 订阅者。"""
        event = {
            "type": event_type,
            "timestamp": time.time(),
            "data": data,
        }
        self._events.append(event)
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        """创建新的订阅队列。"""
        queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """取消订阅。"""
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    def get_recent(self, count: int = 50) -> List[Dict]:
        """获取最近的事件。"""
        return list(self._events)[-count:]
```

在 `handle_execute_python`、`handle_execute_shell`、缓存命中/写入、知识库写入等位置调用 `self._event_bus.publish(...)`。

### 8.4 SSE 路由实现

```python
# web/routes.py

async def handle_sse_stream(request: web.Request) -> web.StreamResponse:
    """SSE 实时数据流端点。"""
    plugin = request.app["plugin"]
    event_bus = plugin._event_bus

    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )
    await response.prepare(request)

    queue = event_bus.subscribe()
    try:
        # 立即发送初始统计
        stats = plugin.collect_stats()
        await response.write(
            f"event: stats\ndata: {json.dumps(stats)}\n\n".encode()
        )

        # 定时统计推送
        last_stats_time = time.time()

        while True:
            try:
                # 等待事件或超时
                event = await asyncio.wait_for(queue.get(), timeout=2.0)
                await response.write(
                    f"event: log\ndata: {json.dumps(event)}\n\n".encode()
                )
            except asyncio.TimeoutError:
                # 超时则推送统计快照
                stats = plugin.collect_stats()
                await response.write(
                    f"event: stats\ndata: {json.dumps(stats)}\n\n".encode()
                )
                last_stats_time = time.time()
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        event_bus.unsubscribe(queue)
    return response
```

### 8.5 前端渲染 — 纯原生 JS

默认首页 `workspace/web/index.html` 内嵌完整的监控面板，使用原生 JS + CSS Grid 布局，零依赖：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>麦麦学代码 — 实时监控</title>
    <style>
        :root {
            --bg: #1a1a2e;
            --card-bg: #16213e;
            --text: #e0e0e0;
            --accent: #0f3460;
            --green: #4ecca3;
            --red: #e74c3c;
            --yellow: #f0c040;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            background: var(--bg);
            color: var(--text);
            padding: 1rem;
            min-height: 100vh;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        .header h1 { font-size: 1.2rem; }
        .grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
            margin-bottom: 1rem;
        }
        .card {
            background: var(--card-bg);
            border-radius: 8px;
            padding: 1rem;
        }
        .card h3 {
            font-size: 0.85rem;
            color: #888;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 0.25rem 0;
            font-size: 0.8rem;
        }
        .stat-value { color: var(--green); }
        .stat-value.warn { color: var(--yellow); }
        .stat-value.danger { color: var(--red); }
        .progress-bar {
            height: 6px;
            background: #333;
            border-radius: 3px;
            margin-top: 0.5rem;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: var(--green);
            border-radius: 3px;
            transition: width 0.5s;
        }
        .log-container {
            background: var(--card-bg);
            border-radius: 8px;
            padding: 1rem;
            max-height: 300px;
            overflow-y: auto;
        }
        .log-entry {
            font-size: 0.75rem;
            padding: 0.2rem 0;
            border-bottom: 1px solid #1a1a2e;
            font-family: monospace;
        }
        .log-time { color: #666; }
        .log-type { color: var(--accent); }
        .log-ok { color: var(--green); }
        .log-err { color: var(--red); }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐚 麦麦学代码 — 实时监控</h1>
        <span id="port"></span>
    </div>
    <div class="grid">
        <div class="card" id="sandbox-card">
            <h3>📦 沙箱状态</h3>
            <div id="sandbox-stats">连接中...</div>
        </div>
        <div class="card" id="cache-card">
            <h3>💾 缓存状态</h3>
            <div id="cache-stats">连接中...</div>
        </div>
        <div class="card" id="knowledge-card">
            <h3>📝 知识库</h3>
            <div id="knowledge-stats">连接中...</div>
        </div>
    </div>
    <div class="card" id="context-card">
        <h3>📊 上下文窗口</h3>
        <div id="context-stats">连接中...</div>
        <div class="progress-bar"><div class="progress-fill" id="context-bar" style="width:0%"></div></div>
    </div>
    <div class="log-container" id="log-container">
        <h3>📜 实时日志</h3>
        <div id="log-entries"></div>
    </div>

    <script>
        const logContainer = document.getElementById('log-entries');
        const MAX_LOGS = 100;

        function addLog(entry) {
            const div = document.createElement('div');
            div.className = 'log-entry';
            const time = new Date(entry.timestamp * 1000).toLocaleTimeString();
            div.innerHTML = `<span class="log-time">[${time}]</span> ${entry.data.message || JSON.stringify(entry.data)}`;
            logContainer.prepend(div);
            while (logContainer.children.length > MAX_LOGS) {
                logContainer.removeChild(logContainer.lastChild);
            }
        }

        function updateStats(stats) {
            // 沙箱
            const sb = stats.sandbox || {};
            document.getElementById('sandbox-stats').innerHTML = `
                <div class="stat-row"><span>执行次数</span><span class="stat-value">${sb.total || 0}</span></div>
                <div class="stat-row"><span>成功</span><span class="stat-value">${sb.success || 0}</span></div>
                <div class="stat-row"><span>失败</span><span class="stat-value ${(sb.failed||0) > 0 ? 'danger' : ''}">${sb.failed || 0}</span></div>
                <div class="stat-row"><span>平均耗时</span><span class="stat-value">${sb.avg_time_ms || 0}ms</span></div>
            `;
            // 缓存
            const cache = stats.cache || {};
            const hitRate = cache.total_entries ? Math.round((cache.total_hits || 0) / Math.max(cache.total_entries, 1) * 100) : 0;
            document.getElementById('cache-stats').innerHTML = `
                <div class="stat-row"><span>命中率</span><span class="stat-value">${hitRate}%</span></div>
                <div class="stat-row"><span>活跃条目</span><span class="stat-value">${cache.active_entries || 0}</span></div>
                <div class="stat-row"><span>过期条目</span><span class="stat-value warn">${cache.expired_entries || 0}</span></div>
                <div class="stat-row"><span>容量</span><span class="stat-value">${cache.active_entries || 0}/${cache.max_entries || 500}</span></div>
            `;
            // 知识库
            const kb = stats.knowledge || {};
            document.getElementById('knowledge-stats').innerHTML = `
                <div class="stat-row"><span>总条目</span><span class="stat-value">${kb.total || 0}</span></div>
                <div class="stat-row"><span>分类数</span><span class="stat-value">${kb.categories || 0}</span></div>
                <div class="stat-row"><span>最近更新</span><span class="stat-value">${kb.last_updated || '-'}</span></div>
            `;
            // 上下文
            const ctx = stats.context || {};
            const ctxPct = ctx.context_max_tokens ? Math.round((ctx.context_tokens_estimate || 0) / ctx.context_max_tokens * 100) : 0;
            document.getElementById('context-stats').innerHTML = `
                <div class="stat-row"><span>对话轮次</span><span class="stat-value">${ctx.context_turns || 0}</span></div>
                <div class="stat-row"><span>Token 估算</span><span class="stat-value">${ctx.context_tokens_estimate || 0}/${ctx.context_max_tokens || 8000}</span></div>
                <div class="stat-row"><span>当前话题</span><span class="stat-value">${ctx.current_topic || '无'}</span></div>
            `;
            document.getElementById('context-bar').style.width = ctxPct + '%';
            if (ctxPct > 80) {
                document.getElementById('context-bar').style.background = 'var(--red)';
            } else if (ctxPct > 60) {
                document.getElementById('context-bar').style.background = 'var(--yellow)';
            } else {
                document.getElementById('context-bar').style.background = 'var(--green)';
            }
        }

        // SSE 连接
        const es = new EventSource('/api/stream');
        es.addEventListener('stats', (e) => {
            updateStats(JSON.parse(e.data));
        });
        es.addEventListener('log', (e) => {
            addLog(JSON.parse(e.data));
        });
        es.onerror = () => {
            document.getElementById('sandbox-stats').textContent = '连接断开，重连中...';
        };
    </script>
</body>
</html>
```

### 8.6 统计收集方法

在 `plugin.py` 中新增 `collect_stats()` 方法：

```python
def collect_stats(self) -> Dict[str, Any]:
    """收集所有模块的统计信息，供监控面板使用。"""
    return {
        "sandbox": self._sandbox_stats or {},
        "cache": self._cache.get_stats() if self._cache else {},
        "knowledge": self._knowledge_base.get_stats() if self._knowledge_base else {},
        "context": {
            "context_turns": len(self._cache._context_turns) // 2 if self._cache else 0,
            "context_tokens_estimate": self._cache.estimate_tokens(
                self._cache._context_turns
            ) if self._cache else 0,
            "context_max_tokens": self._cache._context_max_tokens if self._cache else 8000,
            "current_topic": self._cache._current_topic if self._cache else "",
        },
        "server": {
            "port": self._web_port,
            "uptime_seconds": time.time() - self._start_time,
        },
    }
```

---

## 9. 多页面路由 + 主题皮肤系统

### 9.1 设计目标

- **同一端口，多个页面**：监控面板 (`/`) 和 Bot 自写页面 (`/pages/*`) 共享同一个端口
- **导航跳转**：监控面板顶部有导航栏，可跳转到 Bot 自写的任意页面
- **主题皮肤**：Bot 可以修改 `workspace/web/theme.css`，所有页面自动应用
- **不纳入 git**：`workspace/web/` 整个目录加入 `.gitignore`，Bot 的创作完全本地化

### 9.2 路由设计

```
同一端口 (如 :8700)
├── /                          → 监控面板（内置，不可被 Bot 覆盖）
├── /pages/<name>              → Bot 自写页面（从 workspace/web/pages/<name>.html 读取）
├── /pages/                    → Bot 页面索引（列出所有自写页面）
├── /api/stream                → SSE 实时数据流
├── /api/status                → 插件状态 API
├── /api/knowledge             → 知识库 API
├── /api/cache                 → 缓存 API
├── /api/sandbox               → 沙箱 API
├── /api/theme                 → 主题 CSS 内容（GET 获取，POST 更新）
└── /static/theme.css          → 主题 CSS 文件（直接 serve workspace/web/theme.css）
```

### 9.3 文件布局

```
plugins/mai_study_code/
├── web/                        # Web 服务模块（纳入 git）
│   ├── __init__.py
│   ├── server.py
│   ├── routes.py
│   ├── page_builder.py
│   └── monitor.html            # 监控面板 HTML 模板（内置，纳入 git）
├── workspace/                  # 工作区（已在 .gitignore 中）
│   └── web/                    # Bot 的 Web 空间（新增忽略规则）
│       ├── theme.css           # 主题皮肤（Bot 可修改）
│       ├── pages/              # Bot 自写页面目录
│       │   ├── index.html      # Bot 的首页
│       │   ├── about.html      # Bot 写的关于页
│       │   └── ...             # 任意 Bot 创建的页面
│       └── assets/             # Bot 的静态资源（图片等）
└── .gitignore                  # 新增 workspace/web/ 忽略规则
```

### 9.4 主题皮肤系统

**核心思路**：CSS 变量 + 独立 `theme.css` 文件，Bot 通过 Tool 修改。

#### 默认主题 (`workspace/web/theme.css` 初始内容)

```css
/* === 麦麦学代码 — 主题皮肤 ===
 * 麦麦可以修改这个文件来换肤！
 * 所有页面（监控面板 + 自写页面）都会自动应用这些变量。
 */

:root {
    /* 背景色系 */
    --bg-primary: #1a1a2e;
    --bg-card: #16213e;
    --bg-input: #0f3460;

    /* 文字色系 */
    --text-primary: #e0e0e0;
    --text-secondary: #888888;
    --text-muted: #555555;

    /* 强调色 */
    --accent: #0f3460;
    --accent-hover: #1a4a7a;

    /* 状态色 */
    --color-success: #4ecca3;
    --color-warning: #f0c040;
    --color-danger: #e74c3c;
    --color-info: #3498db;

    /* 边框与圆角 */
    --border-color: #2a2a4a;
    --border-radius: 8px;

    /* 字体 */
    --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    --font-sans: system-ui, -apple-system, sans-serif;

    /* 间距 */
    --spacing-xs: 0.25rem;
    --spacing-sm: 0.5rem;
    --spacing-md: 1rem;
    --spacing-lg: 1.5rem;

    /* 阴影 */
    --shadow-card: 0 2px 8px rgba(0, 0, 0, 0.3);
}
```

#### 页面如何引用主题

监控面板和 Bot 自写页面都在 `<head>` 中引用：

```html
<link rel="stylesheet" href="/static/theme.css">
```

所有 CSS 使用变量，例如：

```css
body { background: var(--bg-primary); color: var(--text-primary); }
.card { background: var(--bg-card); border-radius: var(--border-radius); }
.success { color: var(--color-success); }
```

#### Bot 如何修改主题

用户通过聊天让 Bot 换肤：

- "麦麦，把你的面板换成浅色主题"
- "麦麦，把强调色改成紫色"
- "麦麦，字体换成圆体"

Bot 通过以下 Tool 操作：

1. **`read_file`** → 读取 `workspace/web/theme.css` 查看当前主题
2. **`write_file`** → 写入新的 `workspace/web/theme.css`
3. **`apply_diff`** → 精确修改某个 CSS 变量

修改后页面**立即生效**（浏览器下次刷新或通过 SSE 通知热更新）。

#### 主题 API

```
GET  /api/theme          → 返回当前 theme.css 内容
POST /api/theme          → 更新 theme.css（body 为新的 CSS 内容）
```

### 9.5 监控面板导航栏

监控面板顶部增加导航：

```
┌──────────────────────────────────────────────────────────┐
│  🐚 麦麦学代码  [监控] [我的页面▾] [主题]    [端口: 87xx] │
└──────────────────────────────────────────────────────────┘
```

- **[监控]**：当前页，高亮
- **[我的页面▾]**：下拉菜单，动态列出 `workspace/web/pages/` 下所有 `.html` 文件
- **[主题]**：跳转到主题编辑器（一个简单的 CSS 编辑页面）

导航栏 HTML 片段：

```html
<nav class="nav-bar">
    <a href="/" class="nav-brand">🐚 麦麦学代码</a>
    <div class="nav-links">
        <a href="/" class="nav-link active">监控</a>
        <div class="nav-dropdown">
            <span class="nav-link">我的页面 ▾</span>
            <div class="dropdown-menu" id="page-menu">
                <!-- 由 JS 动态填充 -->
            </div>
        </div>
        <a href="/pages/theme-editor" class="nav-link">主题</a>
    </div>
    <span class="nav-port" id="port-display"></span>
</nav>
```

### 9.6 页面索引 API

```
GET /api/pages    → 返回 workspace/web/pages/ 下所有 .html 文件列表
```

响应示例：

```json
{
    "pages": [
        {"name": "index", "title": "麦麦的首页", "path": "index.html"},
        {"name": "about", "title": "关于麦麦", "path": "about.html"},
        {"name": "projects", "title": "麦麦的项目", "path": "projects.html"}
    ]
}
```

页面标题从 HTML 的 `<title>` 标签自动提取。

### 9.7 .gitignore 更新

在 `.gitignore` 中新增：

```gitignore
# Bot 的 Web 空间（Bot 自己创作的内容，不纳入版本控制）
workspace/web/
```

这样 `workspace/web/theme.css`、`workspace/web/pages/` 等全部不会被 git 追踪。

---

## 10. 插件生命周期修改

在 `plugin.py` 中：

```python
# __init__ 中新增
self._web_server: Optional[PluginWebServer] = None
self._web_port: int = 0

# on_load 中新增
if self.config.web.enabled:
    port = resolve_port(self.config.web)  # 优先用指定端口，否则自动发现
    self._web_server = PluginWebServer(self)
    self._web_port = await self._web_server.start(port)
    logger.info(f"Web 服务已启动: http://127.0.0.1:{self._web_port}")

# on_unload 中新增
if self._web_server:
    await self._web_server.stop()
```

---

## 10. 实施步骤

| 步骤 | 内容 | 涉及文件 |
|------|------|----------|
| 1 | 新增 `[web]` 配置段 + `WebConfig` 类 | `config.toml`, `plugin.py` |
| 2 | 更新 `.gitignore`（忽略 `workspace/web/`） | `.gitignore` |
| 3 | 创建 `web/` 模块骨架 | `web/__init__.py`, `web/server.py` |
| 4 | 实现路由：REST API + SSE + 多页面 + 主题 | `web/routes.py` |
| 5 | 实现 SSE 实时数据流端点 | `web/routes.py` |
| 6 | 实现 `EventBus` 事件总线 | `web/event_bus.py` |
| 7 | 在各 Tool handler 中埋点发布事件 | `plugin.py` |
| 8 | 实现 `collect_stats()` 统计收集 | `plugin.py` |
| 9 | 实现 `PageBuilder`（页面索引 + 标题提取） | `web/page_builder.py` |
| 10 | 创建监控面板 HTML 模板（含导航栏） | `web/monitor.html` |
| 11 | 创建默认主题 CSS | `workspace/web/theme.css` |
| 12 | 创建 Bot 默认首页 | `workspace/web/pages/index.html` |
| 13 | 修改插件生命周期（启停 web 服务） | `plugin.py` |
| 14 | 更新 README 文档 | `README.md` |

---

## 12. 依赖

无需新增 pip 依赖。`aiohttp` 已在 MaiBot 的 `pyproject.toml` 依赖中（`aiohttp>=3.12.14`）。

---

## 13. 风险与注意事项

- **端口冲突**：支持固定端口 + 自动发现双模式
- **内存占用**：aiohttp + SSE 连接轻量，EventBus 使用 `deque(maxlen=200)` 限制内存
- **安全性**：仅监听 `127.0.0.1`，外部不可达
- **Bot 写网页的安全性**：Bot 通过 `write_file` Tool 写入，受权限系统控制，仅限 `workspace/web/` 目录
- **SSE 连接数**：每个浏览器标签页一个 SSE 连接，aiohttp 异步模型天然支持高并发连接
- **主题隔离**：`workspace/web/` 整体在 `.gitignore` 中，Bot 的创作不会污染 git 仓库
