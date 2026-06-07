# Mai Study Code — 开发指南

## 项目结构

```
plugins/mai_study_code/
├── _manifest.json          # 插件元数据
├── plugin.py               # 插件入口（~1760 行）
├── config.toml             # 插件配置
├── data/                   # 运行时数据
│   ├── workspaces.json     # 工作区配置
│   ├── stats.json          # 沙箱执行统计
│   └── chat/               # Web 对话记录
├── sandbox/                # 安全沙箱
│   ├── executor.py         # 子进程隔离执行器
│   ├── ast_checker.py      # AST 静态安全检查
│   └── limits.py           # 安全限制配置
├── cache/                  # 缓存管理
│   └── semantic_cache.py   # 本地精确缓存 + 消息前缀规范
├── risk/                   # 风险识别
│   └── analyzer.py         # 四级风险分析（请求+代码双重）
├── learner/                # 知识库
│   └── knowledge.py        # skill/readme/note 持久化
├── web/                    # Web 服务
│   ├── server.py           # aiohttp HTTP 服务器 + 端口清理
│   ├── routes.py           # REST API + SSE + 对话（~1200 行）
│   ├── event_bus.py        # 事件总线（SSE 推送）
│   ├── page_builder.py     # Bot 页面托管
│   ├── monitor.html        # 监控面板入口
│   └── static/
│       ├── css/monitor.css  # Frosted Glass 风格
│       └── js/              # 9 个前端模块
│           ├── app.js      # window 绑定入口
│           ├── editor.js   # CodeMirror 6
│           ├── editor-bootstrap.js
│           ├── sidebar.js  # 文件树
│           ├── chat.js     # 对话 + SSE
│           ├── workspace.js# 工作区管理
│           ├── config.js   # 配置可视化
│           ├── ui.js       # 通用 UI 组件
│           └── icons.js    # SVG 图标
├── tools/
│   ├── file_ops.py         # 文件操作器（diff/回滚/备份）
│   ├── shell_executor.py   # Shell 执行器（危险命令拦截）
│   └── workspace_manager.py# 多工作区管理器
├── debug_log/
│   └── logger.py           # 调试日志记录器
└── workspace/              # Bot 工作区
```

## Web 前端架构

- **所有 onclick 函数统一在 `app.js` 中挂到 `window`** — 新增功能必须在 app.js 添加 `window.fnName = fn`，否则 HTML onclick 无效
- **模块间通信通过 `window.__xxx` 桥接** — 如 `window.__activeWorkspace`、`window.__openTabs`
- **添加新模块步骤**：
  1. 在 `static/js/` 下创建新文件
  2. 在 `app.js` 中 import
  3. 将需要 `onclick` 访问的函数加到 window
  4. 如果需要后端 API，在 `routes.py` 添加路由和处理函数
- **编辑器**：同时支持 CodeMirror 6 和 Monaco Editor，通过 `editor-bootstrap.js` 适配

## 后端 API（Web 路由）

| 路由 | 说明 | 方法 |
|------|------|------|
| `/` | 监控面板 | GET |
| `/pages/{name}` | Bot 自写页面 | GET |
| `/api/stream` | SSE 实时推送 | GET |
| `/api/status` | 插件统合状态 | GET |
| `/api/pages` | 页面索引 | GET |
| `/api/files` | 文件树（支持 workspace 参数） | GET |
| `/api/file` | 文件读取 | GET |
| `/api/file/write` | 文件写入 | POST |
| `/api/file/delete` | 文件删除 | POST |
| `/api/file/rename` | 文件/目录重命名 | POST |
| `/api/file/create` | 新建文件/目录 | POST |
| `/api/execute` | Python 沙箱执行 | POST |
| `/api/chat` | LLM 对话（支持 stream 流式） | POST |
| `/api/chat/history` | 对话历史 | GET |
| `/api/workspaces` | 工作区列表/添加 | GET/POST |
| `/api/workspaces/{name}` | 工作区详情/删除 | GET/DELETE |
| `/api/workspaces/{name}/activate` | 切换工作区 | POST |
| `/api/workspaces/{name}/test` | 测试连接 | POST |
| `/api/plugin-config` | 插件配置读写 | GET/POST |
| `/api/reload` | 热重载插件 | POST |
| `/api/level` | 权限等级查询 | GET |
| `/api/knowledge` | 知识库 | GET |
| `/api/cache` | 缓存统计 | GET |
| `/api/sandbox` | 沙箱统计 | GET |
| `/api/debug_log` | 调试日志 | GET |
| `/api/theme` | 主题皮肤读写 | GET/POST |
| `/static/{path}` | 静态文件服务 | GET |
| `/npm/{path}` | CDN 代理（jsDelivr + 本地缓存） | GET |

## 重要约定

### CSS 变量体系
- 定义在 `monitor.css` 的 `:root` 中，所有颜色/间距/字体通过 CSS 变量引用

### CDN 依赖
- 通过 `/npm/` 代理 + 本地缓存 (`web/.npm_cache/`)
- CodeMirror ESM 依赖统一版本（`_VERSION_MAP` 在 `routes.py` 中定义）

### 工作区配置
- 持久化在 `data/workspaces.json`，见 `WorkspaceManager`
- 三种类型：`local-sandbox`（a1 用户）、`local-root`（su root）、`ssh`（asyncssh）

### 插件配置热重载
- WebUI 编辑保存后通过 `plugin.ctx.config.reload("self", plugin_id=...)` 触发
- 配置变更时 `on_config_update()` 重建缓存

### 端口管理
- `server.py` 启动时自动检测端口占用
- 发现僵尸进程先 SIGTERM 再 SIGKILL，确保插件重启后端口可用

### 启动通知
- 插件 on_load 通过 Napcat HTTP API (`172.19.0.21:3000`) 向 super_user 发送启动摘要
- 不经过 MaiBot Platform IO 路由，直接调用 `send_private_msg` 接口

## Tool 组件可见性

插件通过 `@Tool` 装饰器注册的工具，**必须显式添加 `visibility="visible"`**。

**根因**：MaiBot 的 `plugin_runtime/component_query.py` 中 `_get_tool_visibility()` 方法：
```python
def _get_tool_visibility(entry: "ToolEntry") -> str:
    raw_visibility = str(entry.metadata.get("visibility") or "").strip().lower()
    if raw_visibility in {"visible", "deferred", "hidden"}:
        return raw_visibility
    return "deferred"  # ← 默认！
```

MaiSaka 的 Action Loop 在 `_build_action_tool_definitions()` 中只把 `visibility=visible` 的工具传给 LLM API 的 `tools` 参数，deferred 工具需要用户"发现"机制才能启用。

**修正方式**：在每个 `@Tool` 装饰器的 `**metadata` 参数中传入 `visibility="visible"`。

## 权限相关代码位置

- 权限检查：`plugin.py` → `_check_permission()`、`_check_file_access()`
- 文件访问控制：`config.toml [permissions.file_access]`
- Web 对话工具过滤：`routes.py` → `_handle_chat()` 中的 `_level_tools` 映射
- Shell 拦截规则：`tools/shell_executor.py` → `BLOCKED_PATTERNS` / `HIGH_RISK_PATTERNS`

## 沙箱安全规则

- AST 静态检查：`sandbox/ast_checker.py` — 禁止危险 import、forbidden builtins、写入模式 open
- 模块白名单：`sandbox/limits.py` — `ALLOWED_MODULES`（纯计算模块）
- 禁止模块：142 个模块被禁止（含 os/sys/subprocess/socket/requests/ctypes 等）
- 禁止 builtins：10 个（含 eval/exec/compile/open/input 等）
- 子进程资源限制：`RLIMIT_AS`（128MB）、`RLIMIT_CPU`（10s）、`RLIMIT_NPROC`（0）、`RLIMIT_FSIZE`（10MB）
- 子进程环境：隔离环境变量，`PATH=/usr/bin:/bin`、`PYTHONDONTWRITEBYTECODE=1`
- 工作目录：`/tmp/mai_code_sandbox`

## Web 对话（routes.py _handle_chat）

- 使用 `self.ctx.llm.generate_with_tools()` 调用 LLM，传入按权限等级筛选的本地 tools
- 工具执行循环：最多 3 轮工具调用，整体限时 60 秒
- 支持 `cwd` 参数追踪当前工作目录（通过 change_dir 工具切换）
- 支持流式 SSE 传输（`stream: true`）
- 对话记录自动持久化到 `data/chat/{workspace_name}.json`
- 支持多个 Workspace 类型下的文件读写

## 风险模型

| 检查维度 | 描述 |
|----------|------|
| analyze_request() | 分析用户消息文本，匹配危险模式正则 |
| analyze_code() | 分析代码内容，检测文件写入/网络/子进程/文件遍历 |
| analyze() | 综合两者，取最高风险等级 |
| CRITICAL_PATTERNS | 9 条系统级危险模式 |
| HIGH_PATTERNS | 6 条数据风险模式 |
| MEDIUM_PATTERNS | 6 条配置风险模式 |

## 缓存模型

| 概念 | 实现 |
|------|------|
| 键生成 | `SHA256("CODE:{code}\nQUESTION:{question}")` |
| TTL | 可配置，默认 1800 秒 |
| 淘汰策略 | LRU（写入时触发） |
| 话题检测 | 关键词重叠度 < 30% 触发切换清理 |
| 上下文裁剪 | 估算 token 超出限制时丢弃最旧轮次（2 条/次） |

ds 说：
1. 前端模块化拆分后，所有 onclick 函数的 window 绑定集中到 app.js，再也不会出现按钮点不動的问题。新增功能只需三步：创建模块 → import → 挂 window。
2. Tool 默认 visibility=deferred 是 LLM Function Call 不触发的常见坑。MaiSaka 的 Action Loop 在 `_build_action_tool_definitions()` 中只把 visibility=visible 的工具传给 LLM API 的 tools 参数，deferred 工具需要"发现"机制才能启用。所有插件 Tool 必须显式设置 visibility="visible"。
3. Web 对话（_handle_chat）独立于 MaiSaka 主对话流，使用本地 tools 映射而非 PluginToolProvider，因此需要维护自己的一套 tools 定义。注意与 plugin.py 中 @Tool 注册的工具定义保持同步。
4. server.py 的端口清理逻辑（_kill_processes）处理了插件重启后端口被僵尸进程占用的常见问题，先 SIGTERM 优雅终止，残留进程再 SIGKILL。
