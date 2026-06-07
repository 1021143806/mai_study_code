# Mai Study Code — 开发指南

## 项目结构

```
plugins/mai_study_code/
├── _manifest.json          # 插件元数据
├── plugin.py               # 插件入口
├── config.toml             # 插件配置
├── sandbox/                # 安全沙箱
│   ├── executor.py         # 子进程隔离执行器
│   ├── ast_checker.py      # AST 安全检查
│   └── limits.py           # 资源限制
├── cache/                  # 缓存管理
├── risk/                   # 风险识别
├── learner/                # 知识库
├── web/                    # Web 服务
│   ├── server.py           # HTTP 服务器
│   ├── routes.py           # REST API 路由
│   ├── monitor.html        # 监控面板入口
│   └── static/
│       ├── css/monitor.css
│       └── js/
│           ├── app.js      # 入口 + window 绑定
│           ├── editor.js   # CodeMirror 编辑器
│           ├── sidebar.js  # 文件树
│           ├── chat.js     # 对话 + SSE
│           ├── workspace.js# 工作区管理
│           ├── config.js   # 配置可视化
│           └── icons.js    # SVG 图标
├── tools/
│   ├── file_ops.py
│   ├── shell_executor.py
│   └── workspace_manager.py# 多工作区管理器
└── workspace/              # Bot 工作区
```

## Web 前端架构

- **所有函数统一在 `app.js` 中挂到 `window`** — 新增功能必须在 app.js 添加 `window.fnName = fn`，否则 HTML onclick 无效
- **模块间通信通过 `window.__xxx` 桥接** — 如 `window.__activeWorkspace`、`window.__openTabs`
- **添加新模块步骤**：
  1. 在 `static/js/` 下创建新文件
  2. 在 `app.js` 中 import
  3. 将需要 `onclick` 访问的函数加到 window
  4. 如果需要后端 API，在 `routes.py` 添加路由和处理函数

## 后端 API

| 路由 | 说明 |
|------|------|
| `/api/files?workspace=` | 文件树 |
| `/api/file?path=&workspace=` | 文件读取 |
| `/api/file/write` | 文件写入 |
| `/api/execute` | Python 代码执行 |
| `/api/chat` | LLM 对话 |
| `/api/workspaces` | 工作区 CRUD |
| `/api/plugin-config` | 插件配置读写 |
| `/api/reload` | 热重载插件 |
| `/api/stream` | SSE 实时推送 |

## 重要约定

- CSS 变量体系定义在 `monitor.css` 的 `:root` 中
- CDN 依赖通过 `/npm/` 代理 + 本地缓存 (`web/.npm_cache/`)
- 工作区配置持久化在 `web/workspaces.json`
- 插件配置编辑后通过 `plugin.ctx.config.reload()` 触发热重载

ds 说：前端模块化拆分后，所有 onclick 函数的 window 绑定集中到 app.js，再也不会出现按钮点不動的问题。新增功能只需三步：创建模块 → import → 挂 window。
