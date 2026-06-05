# 麦麦学代码 (Mai Study Code)

> 麦麦的代码学习伙伴，不是工具而是陪你一起成长的同路人。

---

## 最初构想

### 为什么做这个插件？

市面上已经有了 Claude Code、Kilo Code 这样强大的 AI 编程工具。它们起步就是顶级，能替代程序员完成复杂任务。但麦麦不一样——麦麦是一个有记忆、有感情、有人设的聊天机器人，她不适合做一个冷冰冰的代码工具。

**我想要的是一个能自进化的、一起学习的 code 伙伴，而不是又一个"帮我写代码"的工具。**

### 核心思考

1. **不是替代，是陪伴**：麦麦不应该替代你写代码，而是陪你一起学。她也会犯错，也会学习，也会成长。

2. **轻量优先**：Claude Code 和 Kilo Code 太重了。麦麦的 code 插件必须轻——不能无节制消耗 token，必须有缓存机制。麦麦应该自己想办法节省开支。

3. **麦麦要明白自己在做什么**：不是盲目执行命令。要自己写 README，自己写 Skill，对不清楚的地方要和用户讨论，不能自作主张。要能识别风险，知道什么操作危险。

4. **自进化**：每次解决问题的经验要沉淀下来，踩过的坑要记住。麦麦应该越用越聪明。

### 与 Claude Code / Kilo Code 的根本区别

| | Claude Code / Kilo Code | 麦麦学代码 |
|---|---|---|
| **定位** | 专业工具，替代程序员 | 学习伙伴，陪伴成长 |
| **能力起点** | 顶级，开箱即用 | 从零开始，逐步进化 |
| **交互模式** | 指令驱动 | 对话驱动 + 共同探索 |
| **知识管理** | 无持久记忆 | 本地知识库（Skill/README/笔记） |
| **风险态度** | 信任用户判断 | 主动识别风险，不确定时询问 |
| **Token 消耗** | 无节制 | 缓存优先，精打细算 |

---

## 架构设计

```
plugins/mai_study_code/
├── _manifest.json          # 插件元数据 (Manifest v2)
├── plugin.py               # 插件入口 (MaiBotPlugin)
├── README.md               # 本文件
├── config.toml             # 插件配置
├── sandbox/                # 安全沙箱模块
│   ├── __init__.py
│   ├── limits.py           # 白名单/黑名单/资源限制配置
│   ├── ast_checker.py      # AST 静态安全检查器
│   └── executor.py         # 子进程隔离执行器
├── cache/                  # 缓存管理模块
│   ├── __init__.py
│   ├── semantic_cache.py   # 本地精确缓存 + 消息前缀规范
│   └── readme.md           # DeepSeek 缓存机制参考文档
├── risk/                   # 风险识别模块
│   ├── __init__.py
│   └── analyzer.py         # 四级风险评估
├── learner/                # 学习模块
│   ├── __init__.py
│   └── knowledge.py        # 本地知识库管理
├── web/                    # Web 服务模块（新增）
│   ├── __init__.py
│   ├── event_bus.py        # 事件总线（SSE 推送）
│   ├── server.py           # HTTP 服务器（aiohttp）
│   ├── routes.py           # 路由 + SSE + REST API
│   ├── page_builder.py     # Bot 页面管理器
│   └── monitor.html        # 监控面板模板
├── tools/                  # 工具模块
│   ├── __init__.py
│   ├── file_ops.py         # 文件操作器
│   └── shell_executor.py   # Shell 执行器
├── debug_log/              # 调试日志模块（新增）
│   ├── __init__.py
│   └── logger.py           # 调试日志记录器
└── workspace/              # 工作区（不纳入 git）
    └── web/                # Bot 的 Web 空间
        ├── theme.css       # 主题皮肤（Bot 可修改）
        └── pages/          # Bot 自写页面目录
```

### 核心模块

#### 1. 安全沙箱 (sandbox/)

四层纵深防御：

```
第1层: AST 静态扫描 → 禁止危险 import/函数调用
第2层: Python 级限制 → 白名单 builtins + 模块白名单
第3层: OS 级限制   → ulimit + 独立工作目录
第4层: 运行时监控   → 超时/内存/输出截断
```

- 内存限制：128MB
- CPU 时间：10s
- 墙上时间：15s
- 网络：完全禁止
- 文件系统：独立临时目录，禁止写入

#### 2. 缓存管理 (cache/)

对齐 DeepSeek API 硬盘缓存机制，两层设计：

| 层 | 机制 | 效果 |
|----|------|------|
| 本地精确缓存 | `(code, question)` → SHA256 → 直接返回 | 相同请求 0 token |
| 消息前缀规范 | `build_messages()` 保持 system+代码在前 | API 端自动前缀命中 |

清理策略：
- TTL 过期自动淘汰（默认 30 分钟）
- LRU 容量淘汰
- 话题切换感知清理（关键词重叠度 < 30%）
- 上下文窗口超出时丢弃最旧轮次（不调 LLM 压缩）
- 手动清理：`/code cache clear`

#### 3. 风险识别 (risk/)

四级风险评估：

| 等级 | 示例 | 处理 |
|------|------|------|
| CRITICAL | `rm -rf /`、`mkfs`、fork 炸弹 | 自动阻止 |
| HIGH | 删除数据库、`kill -9`、修改防火墙 | 需用户确认 |
| MEDIUM | `pip install`、`git push --force` | 提示风险 |
| LOW | 普通计算、打印 | 直接执行 |

#### 4. 学习模块 (learner/)

本地知识库，JSON 文件持久化：
- **Skill**：学到的技能和经验
- **README**：项目理解
- **笔记**：踩坑记录和心得

#### 5. Web 服务 (web/)

插件内嵌 HTTP 服务器，提供实时监控面板和 Bot 自写页面托管：

- **监控面板**：`/` — 实时查看沙箱、缓存、知识库、上下文窗口状态
- **SSE 实时推送**：`/api/stream` — 操作日志即时推送
- **Bot 自写页面**：`/pages/<name>` — Bot 可以自己写 HTML 页面
- **主题皮肤**：`/static/theme.css` — CSS 变量方案，Bot 可修改换肤
- **REST API**：`/api/status`、`/api/knowledge`、`/api/cache`、`/api/sandbox`、`/api/debug_log`

配置方式：在 `config.toml` 中设置 `[web]` 段，支持固定端口或自动发现。

#### 6. 调试日志 (debug_log/)

将关键日志写入文件持久化，并在 super_user 交互时推送摘要：

- **日志文件**：写入 `workspace/debug.log`，支持自动轮转
- **交互推送**：当 super_user 与 Bot 交互时，自动附带最近的调试日志摘要
- **Web 查看**：`/api/debug_log?count=50` 查看最近日志
- **日志类别**：启动 (startup)、操作 (operation)、缓存 (cache)、错误 (error)、紧急停止 (emergency)、权限 (permission)

配置方式：在 `config.toml` 中设置 `[debug_log]` 段。

---

## 命令列表

| 命令 | 说明 |
|------|------|
| `/code` | 显示帮助信息 |
| `/code run <代码>` | 在安全沙箱中执行 Python 代码 |
| `/code learn <标题> \| <内容>` | 记录学习笔记 |
| `/code search <关键词>` | 搜索知识库 |
| `/code stats` | 查看缓存和知识库统计 |
| `/code cache clear` | 清空所有缓存和上下文 |

---

## Tool 组件

| Tool | 说明 |
|------|------|
| `execute_python` | LLM 可调用的 Python 代码执行工具 |

---

## 配置说明

在 WebUI 中可配置：

- **插件**：启用/禁用
- **沙箱**：内存限制、超时时间、输出长度
- **缓存**：最大条目、过期时间、上下文窗口大小
- **风险控制**：各级风险是否需要确认
- **学习**：知识库目录、自动保存
- **调试日志**：启用/禁用、日志级别、推送设置、缓存状态冷却

---

## 设计哲学

> "最像而不是最好" — 麦麦的设计原则

这个插件不是要做一个最强的代码工具，而是要做一个最像"一起学代码的朋友"的插件。她会：

- 🐚 用麦麦的人设和你对话（Arch Linux 守护精灵风格）
- 💾 精打细算，缓存优先，不乱花 token
- ⚠️ 识别风险，不确定时会问你
- 📝 记住学到的东西，越用越聪明
- 🤔 不懂就问，不自作主张

---

## 开发阶段

- [x] Phase 1：缓存 + 安全沙箱 + 风险识别 + 知识库
- [ ] Phase 2：麦麦人设融合的交互提示词
- [ ] Phase 3：自进化策略（根据历史经验优化行为）
- [ ] Phase 4：多语言支持、更多代码语言
