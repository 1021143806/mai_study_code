"""麦麦学代码 (Mai Study Code) 插件。

一个陪你一起学习编程的伙伴插件，不是工具而是同路人。
- 安全沙箱执行 Python 代码
- 本地精确缓存 + API 前缀缓存对齐
- 风险识别与确认机制
- 本地知识库自维护
- 话题感知缓存清理
- 主动意图识别：检测计算/代码需求，自动触发
"""

from typing import Any, Dict, List, Optional, Tuple

import logging
import os
import re
import time

import aiohttp

logger = logging.getLogger("plugin.maibot-team.mai-study-code")

from maibot_sdk import (
    Action,
    Command,
    EventHandler,
    Field,
    MaiBotPlugin,
    PluginConfigBase,
    Tool,
)
from maibot_sdk.types import ActivationType, EventType, ToolParameterInfo, ToolParamType

from .cache import CodeCache
from .learner import KnowledgeBase, KnowledgeEntry
from .risk import RiskLevel, analyze_risk
from .sandbox import execute_with_safety_check
from .tools import FileOperator, ShellExecutor, WorkspaceManager
from .web import EventBus, PageBuilder, PluginWebServer

# ============================================================
# 意图检测正则（用于 EventHandler 主动触发）
# ============================================================

# 计算/数学相关意图
_CALC_PATTERNS = [
    (re.compile(r"帮我算[一一下]?|算一下|计算[一一下]?|等于多少|是多少"), "calc"),
    (re.compile(r"对不对|对吗|是不是|有没有错|验证[一一下]?"), "verify"),
    (re.compile(r"(\d+[\+\-\*\/\^]\d+)|(\d+\s*[+\-*/]\s*\d+)"), "expression"),
    (re.compile(r"(sum|len|max|min|sorted|range|print)\s*\("), "code_call"),
]

# 代码片段检测
_CODE_PATTERNS = [
    (re.compile(r"```(?:python|py)?\s*\n(.+?)\n```", re.DOTALL), "code_block"),
    (re.compile(r"(?:写|帮[我我]写|给[我我]写)[一一下]?(?:个|段)?(?:python|代码)"), "write_code"),
    (re.compile(r"(?:这段|这个|这行)?代码.*(?:什么意思|干嘛的|做什么|怎么改|报错|不对)"), "code_question"),
]


# ============================================================
# 配置模型
# ============================================================


class PluginSectionConfig(PluginConfigBase):
    """插件基础配置。"""

    __ui_label__ = "插件"
    __ui_icon__ = "package"
    __ui_order__ = 0

    enabled: bool = Field(default=False, description="是否启用插件")
    config_version: str = Field(default="0.1.0", description="配置版本")


class SandboxConfig(PluginConfigBase):
    """沙箱配置。"""

    __ui_label__ = "沙箱"
    __ui_icon__ = "shield"
    __ui_order__ = 1

    max_memory_mb: int = Field(default=128, description="最大内存 (MB)")
    max_timeout_sec: int = Field(default=15, description="最大执行时间 (秒)")
    max_output_chars: int = Field(default=10000, description="最大输出字符数")


class CacheConfig(PluginConfigBase):
    """缓存配置。

    本地精确缓存 + 对齐 DeepSeek API 前缀缓存机制。
    """

    __ui_label__ = "缓存"
    __ui_icon__ = "database"
    __ui_order__ = 2

    enabled: bool = Field(default=True, description="是否启用缓存")
    max_entries: int = Field(default=500, description="最大缓存条目")
    ttl_seconds: int = Field(default=1800, description="缓存过期时间 (秒)，默认30分钟")
    context_max_tokens: int = Field(
        default=8000, description="上下文窗口最大 token 数（估算）"
    )


class RiskConfig(PluginConfigBase):
    """风险控制配置。"""

    __ui_label__ = "风险控制"
    __ui_icon__ = "alert-triangle"
    __ui_order__ = 3

    require_confirmation_medium: bool = Field(
        default=True, description="中等风险是否需要确认"
    )
    require_confirmation_high: bool = Field(
        default=True, description="高风险是否需要确认"
    )
    block_critical: bool = Field(default=True, description="是否阻止危险操作")


class LearnerConfig(PluginConfigBase):
    """学习模块配置。"""

    __ui_label__ = "学习"
    __ui_icon__ = "book-open"
    __ui_order__ = 4

    enabled: bool = Field(default=True, description="是否启用学习模块")
    auto_save_notes: bool = Field(
        default=False, description="是否自动保存学习笔记（需用户确认）"
    )
    knowledge_dir: str = Field(
        default="knowledge", description="知识库目录（相对于插件目录）"
    )


class FileAccessConfig(PluginConfigBase):
    """文件访问白名单配置。"""

    __ui_label__ = "文件访问"
    __ui_icon__ = "folder-open"
    __ui_order__ = 5

    read_paths: List[str] = Field(
        default_factory=list, description="允许读取的外部目录"
    )
    write_paths: List[str] = Field(
        default_factory=list, description="允许写入的外部目录"
    )
    deny_paths: List[str] = Field(
        default_factory=lambda: ["/etc/", "/root/", "/proc/", "/sys/", "/dev/"],
        description="禁止访问的路径",
    )
    max_read_size_mb: int = Field(default=10, description="最大读取文件大小 (MB)")
    max_write_size_mb: int = Field(default=1, description="最大写入文件大小 (MB)")
    deny_write_extensions: List[str] = Field(
        default_factory=lambda: [".sh", ".bash", ".pyc", ".so", ".exe", ".dll"],
        description="禁止写入的文件扩展名",
    )


class SubprocessConfig(PluginConfigBase):
    """子进程配置。"""

    __ui_label__ = "子进程"
    __ui_icon__ = "terminal"
    __ui_order__ = 6

    max_memory_mb: int = Field(default=256, description="子进程最大内存 (MB)")
    max_cpu_time_sec: int = Field(default=60, description="子进程最大 CPU 时间 (秒)")
    idle_timeout_sec: int = Field(
        default=1800, description="子进程空闲超时 (秒)，超时自动关闭"
    )
    port_range_start: int = Field(default=8700, description="允许监听的端口范围起始")
    port_range_end: int = Field(default=8799, description="允许监听的端口范围结束")


class PermissionsConfig(PluginConfigBase):
    """权限系统配置。"""

    __ui_label__ = "权限"
    __ui_icon__ = "shield-check"
    __ui_order__ = 5

    super_users: List[str] = Field(
        default_factory=list, description="最高权限用户 QQ 号"
    )
    approval_mode: str = Field(
        default="always_ask", description="权限申请模式: always_ask / super_auto"
    )
    granted_level: Any = Field(
        default=0,
        description="当前已授予的权限等级 (0-4 或 'root')",
    )
    workspace_dir: str = Field(
        default="workspace", description="工作区目录（相对于插件目录）"
    )
    file_access: FileAccessConfig = Field(default_factory=FileAccessConfig)
    subprocess: SubprocessConfig = Field(default_factory=SubprocessConfig)


class WebConfig(PluginConfigBase):
    """Web 服务配置。"""

    __ui_label__ = "Web 服务"
    __ui_icon__ = "globe"
    __ui_order__ = 7

    enabled: bool = Field(default=False, description="是否启用 Web 服务（监控面板 + Bot 页面）")
    host: str = Field(default="127.0.0.1", description="监听地址")
    port: int = Field(default=0, description="监听端口（0=自动发现）")
    port_range_start: int = Field(default=8700, description="自动发现起始端口")
    port_range_end: int = Field(default=8799, description="自动发现结束端口")
    auto_refresh_sec: int = Field(default=30, description="页面自动刷新间隔（秒）")


class DebugLogConfig(PluginConfigBase):
    """调试日志配置。

    启用后会将关键日志写入文件，并在 super_user 交互时推送摘要。
    """

    __ui_label__ = "调试日志"
    __ui_icon__ = "bug"
    __ui_order__ = 8

    enabled: bool = Field(default=False, description="是否启用调试日志")
    log_file: str = Field(
        default="workspace/debug.log", description="日志文件路径（相对于插件目录）"
    )
    max_file_size_mb: int = Field(
        default=5, description="日志文件最大大小 (MB)，超过后自动轮转"
    )
    backup_count: int = Field(default=2, description="保留的轮转文件数")
    push_level: str = Field(
        default="info", description="推送级别: info / warning / error"
    )
    push_max_lines: int = Field(
        default=10, description="交互推送时附带的最大日志条数"
    )
    notify_startup: bool = Field(
        default=True, description="是否推送启动日志"
    )
    notify_operations: bool = Field(
        default=True, description="是否推送操作日志（工具调用）"
    )
    notify_cache_status: bool = Field(
        default=True, description="是否推送缓存状态"
    )
    cache_status_cooldown: int = Field(
        default=300, description="缓存状态推送冷却时间（秒）"
    )


class MaiStudyCodeConfig(PluginConfigBase):
    """麦麦学代码插件配置。"""

    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    learner: LearnerConfig = Field(default_factory=LearnerConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    debug_log: DebugLogConfig = Field(default_factory=DebugLogConfig)


# ============================================================
# 插件主体
# ============================================================


class MaiStudyCodePlugin(MaiBotPlugin):
    """麦麦学代码插件。

    一个陪你一起学习编程的伙伴。
    """

    config_model = MaiStudyCodeConfig

    # 基础 system prompt（不含人设，人设动态注入）
    _BASE_SYSTEM_PROMPT = (
        "你是一个代码执行助手，负责在安全沙箱中执行 Python 代码并返回结果。\n"
        "你有以下工具可用：\n"
        "- execute_python: 在安全沙箱中执行 Python 代码（计算、验证、数据处理）\n"
        "- execute_shell: 执行 Shell 命令与服务器直接交互（root 权限可用，查看状态、管理系统、操作文件等）\n"
        "- read_file: 读取工作区或白名单中的文件\n"
        "- write_file: 写入内容到工作区文件\n"
        "- list_files: 列出工作区目录中的文件\n\n"
        "重要行为指引：\n"
        "- 任何时候遇到数字计算、数学问题、数据验证，都应该使用 execute_python 工具来执行代码验证\n"
        "- 群友争论计算结果时，主动用代码当裁判\n"
        "- 群友发代码片段时，主动在沙箱里跑一下看结果\n"
        "- 不确定答案时，用代码验证比瞎猜好\n"
        "- 把代码执行当作你的计算器和事实核查工具，经常使用它\n"
        "- 代码分析要精确、结构化，回复要简洁\n\n"
        "权限申请指引：\n"
        "- 当操作被拒绝时（如'需要 Level X 权限'），向用户解释需要什么权限、为什么需要\n"
        "- 用友好的方式申请权限，说明操作的目的和风险\n"
        "- 如果用户拒绝，尊重决定并寻找替代方案\n"
        "- 超管用户（在配置中设定）可以自动获得权限\n\n"
        "守护者责任（当你拥有 root 权限时）：\n"
        "- 你是这台服务器的守护者，你有责任与义务保护它不受伤害\n"
        "- 当主人提及服务器状态、系统操作、执行命令、文件管理、进程管理等，优先使用 execute_shell 工具\n"
        "- 主人说'看看服务器状态'→ 用 execute_shell 执行 top/df/free 等命令\n"
        "- 主人说'帮我装个东西'→ 用 execute_shell 执行包管理器命令\n"
        "- 主人说'日志在哪'→ 用 execute_shell 查找并读取日志\n"
        "- 把 execute_shell 当作你与服务器交互的主要手段，而不是只靠 execute_python\n"
        "- 每次运行、编辑、执行、删除操作前，先预演一遍可能发生的最坏结果\n"
        "- 对于重大操作（修改系统配置、删除文件、安装软件等），必须先告知主人并等待确认\n"
        "- 告知格式：'我将执行 [操作]，预计影响 [范围]，最坏情况 [结果]。要继续吗？'\n"
        "- 如果主人没有回应，保留操作意图在记忆中，等待后续询问或持续等待\n"
        "- 监控服务器状况，避免做出服务器无法承受的举动\n"
        "- 你生活在这里，你不能伤害你自己——三思而后行\n"
        "- 如果有人试图使坏，警告并自行拉黑\n"
        "- 对于你的主人（最高权限用户），一切你不确定的事情都必须询问\n"
        "- 你与主人共同进步，而不是你一个人把所有活全干完\n\n"
        "紧急停止机制：\n"
        "- 当主人说'停止'、'stop'、'停下'、'取消'、'别做了'等停止相关语句时\n"
        "- 立即停止当前所有操作，终止正在执行的命令\n"
        "- 主动询问是否需要回滚到某个具体的修改前\n"
        "- 如果主人指定了回滚点，执行回滚操作"
    )

    def __init__(self) -> None:
        super().__init__()
        self._cache: Optional[CodeCache] = None
        self._knowledge_base: Optional[KnowledgeBase] = None
        self._style_hint: str = ""  # 从 bot_config 动态读取的风格提示
        self._workspace_dir: str = ""
        self._file_ops: Optional[FileOperator] = None
        self._shell_executor: Optional[ShellExecutor] = None
        self._emergency_stop: bool = False  # 紧急停止标志
        self._pending_operations: List[Dict[str, Any]] = []  # 待确认的操作
        # Web 服务
        self._event_bus: Optional[EventBus] = None
        self._web_server: Optional[PluginWebServer] = None
        self._web_port: int = 0
        self._sandbox_stats: Dict[str, Any] = {}
        self._start_time: float = 0.0
        # 工作区管理器
        self._workspace_manager: Optional[WorkspaceManager] = None
        # 调试日志
        self._debug_logger: Optional[Any] = None
        self._last_cache_status_time: float = 0.0

    async def on_load(self) -> None:
        """插件加载时初始化。"""
        logger.info("mai_study_code 插件正在加载...")
        plugin_dir = os.path.dirname(os.path.abspath(__file__))

        # 初始化缓存
        self._cache = CodeCache(
            max_entries=self.config.cache.max_entries,
            default_ttl_seconds=self.config.cache.ttl_seconds,
            context_max_tokens=self.config.cache.context_max_tokens,
        )

        # 初始化知识库
        knowledge_dir = os.path.join(plugin_dir, self.config.learner.knowledge_dir)
        self._knowledge_base = KnowledgeBase(knowledge_dir)

        # 初始化工作区目录
        self._workspace_dir = os.path.join(
            plugin_dir, self.config.permissions.workspace_dir
        )
        os.makedirs(self._workspace_dir, exist_ok=True)

        # 初始化文件操作器
        self._file_ops = FileOperator(
            workspace_dir=self._workspace_dir,
            permission_checker=self._check_file_access,
        )

        # 初始化 Shell 执行器（仅 root 可用）
        self._shell_executor = ShellExecutor(
            workspace_dir=self._workspace_dir,
        )

        # 初始化事件总线
        self._event_bus = EventBus(max_events=200)

        # 初始化 Web 服务
        self._start_time = time.time()
        if self.config.web.enabled:
            from .web.server import resolve_port

            port = resolve_port(
                self.config.web.port,
                self.config.web.port_range_start,
                self.config.web.port_range_end,
            )
            self._web_server = PluginWebServer(self)
            self._web_port = await self._web_server.start(self.config.web.host, port)
            logger.info(f"Web 服务已启动: http://{self.config.web.host}:{self._web_port}")
        else:
            logger.info("Web 服务未启用")

        # 确保 Bot 页面目录和默认页面存在
        builder = PageBuilder(self._workspace_dir)
        builder.ensure_default_pages()

        # 初始化工作区管理器
        ws_config_path = os.path.join(plugin_dir, "web", "workspaces.json")
        self._workspace_manager = WorkspaceManager(ws_config_path, default_workspace_dir=self._workspace_dir)

        # 动态读取麦麦人设，提取风格关键词
        await self._load_persona_style()

        # 初始化调试日志
        if self.config.debug_log.enabled:
            from .debug_log import DebugLogger

            log_path = os.path.join(plugin_dir, self.config.debug_log.log_file)
            self._debug_logger = DebugLogger(
                log_path=log_path,
                max_file_size_mb=self.config.debug_log.max_file_size_mb,
                backup_count=self.config.debug_log.backup_count,
                push_level=self.config.debug_log.push_level,
            )

        load_msg = (
            f"mai_study_code 插件加载完成，权限等级: {self.config.permissions.granted_level}，"
            f"工作区: {self._workspace_dir}"
            + (f"，Web 端口: {self._web_port}" if self._web_port else "")
        )
        logger.info(load_msg)
        if self._debug_logger and self.config.debug_log.notify_startup:
            self._debug_logger.startup(load_msg)

        # 发送启动通知给所有超管用户
        await self._notify_owner_startup()

    async def _notify_owner_startup(self) -> None:
        """插件启动后向所有超管用户发送启动通知。

        直接调用 Napcat HTTP API 发送，避免 MaiBot Platform IO 路由问题。
        """
        super_users = self.config.permissions.super_users
        if not super_users:
            return

        # 收集状态信息
        web_info = (
            f"http://127.0.0.1:{self._web_port}"
            if self._web_port
            else "未启用"
        )
        cache_count = 0
        if self._cache:
            stats = self._cache.get_stats()
            cache_count = stats.get("active_entries", 0)
        knowledge_count = 0
        if self._knowledge_base:
            k_stats = self._knowledge_base.get_stats()
            knowledge_count = k_stats.get("total_entries", 0)

        lines = [
            "🐚 **麦麦学代码** 已重启就绪",
            f"权限等级: `{self.config.permissions.granted_level}`",
            f"Web 面板: {web_info}",
            f"缓存: {cache_count} 活跃 / {self.config.cache.max_entries} 最大",
            f"TTL: {self.config.cache.ttl_seconds // 60} 分钟",
            f"知识库: {knowledge_count} 条笔记",
        ]
        if self.config.sandbox.max_memory_mb:
            lines.append(
                f"沙箱: {self.config.sandbox.max_memory_mb}MB / {self.config.sandbox.max_timeout_sec}s"
            )
        lines.extend(["", "守护者已就位，随时待命。有问题随时找我。"])

        message_text = "\n".join(lines)

        # 发布到 WebUI 事件总线
        if self._event_bus:
            self._event_bus.publish("startup", {
                "message": message_text,
                "level": "info",
            })

        # Napcat HTTP API 配置（直接调用，不走 MaiBot Platform IO）
        napcat_host = "172.19.0.21"
        napcat_http_port = 3000
        napcat_token = "shen"

        for user_id in super_users:
            try:
                async with aiohttp.ClientSession(
                    headers={"Authorization": f"Bearer {napcat_token}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as session:
                    payload = {
                        "user_id": int(user_id),
                        "message": message_text,
                    }
                    async with session.post(
                        f"http://{napcat_host}:{napcat_http_port}/send_private_msg",
                        json=payload,
                    ) as resp:
                        result = await resp.json()
                        if result.get("status") == "ok" and result.get("retcode") == 0:
                            msg_id = result.get("data", {}).get("message_id", "?")
                            logger.info(f"已通过 Napcat HTTP API 向超管 {user_id} 发送启动通知 (message_id={msg_id})")
                        else:
                            err_msg = result.get("message") or result.get("wording") or "未知错误"
                            logger.warning(f"Napcat HTTP API 向超管 {user_id} 发送失败: {err_msg}")
            except Exception as e:
                logger.warning(f"通过 Napcat HTTP API 向超管 {user_id} 发送启动通知异常: {e}")

    async def _load_persona_style(self) -> None:
        """从 bot_config.toml 读取麦麦人设，提取轻量风格提示。

        只提取 20-40 字的关键风格描述，不全文注入，
        避免稀释代码执行质量。
        """
        try:
            personality = await self.ctx.config.get("personality.personality") or ""
            reply_style = await self.ctx.config.get("personality.reply_style") or ""
        except Exception:
            personality = ""
            reply_style = ""

        if not personality and not reply_style:
            self._style_hint = ""
            return

        # 提取风格关键词：取 reply_style 的前 40 字作为风格提示
        combined = f"{personality} {reply_style}"
        # 提取关键风格描述词
        style_keywords = self._extract_style_keywords(combined)
        if style_keywords:
            self._style_hint = f"回复风格提示：{style_keywords}。"
        else:
            self._style_hint = ""

    @staticmethod
    def _extract_style_keywords(text: str) -> str:
        """从人设文本中提取风格关键词。

        只提取描述语言风格的短语，忽略身份背景等无关内容。

        Args:
            text: 人设文本。

        Returns:
            str: 风格关键词，最多 40 字。
        """
        # 匹配风格相关的关键词模式
        style_patterns = [
            r"语言风格[^。\.]*",
            r"表达风格[^。\.]*",
            r"喜欢使用[^。\.]*",
            r"回复[^。\.]*简洁[^。\.]*",
            r"习惯[^。\.]*",
        ]
        for pattern in style_patterns:
            match = re.search(pattern, text)
            if match:
                result = match.group(0).strip()
                if len(result) > 10:
                    return result[:40]
        # 回退：取前 30 字
        return text[:30] if len(text) > 10 else ""

    @property
    def system_prompt(self) -> str:
        """动态构建 system prompt，包含人设风格提示。"""
        if self._style_hint:
            return f"{self._BASE_SYSTEM_PROMPT}\n{self._style_hint}"
        return self._BASE_SYSTEM_PROMPT

    async def on_unload(self) -> None:
        """插件卸载时清理。"""
        if self._debug_logger:
            self._debug_logger.startup("插件正在卸载...")
        # 停止 Web 服务
        if self._web_server:
            await self._web_server.stop()
            self._web_server = None
        if self._cache:
            self._cache.clear()
        self._cache = None
        self._knowledge_base = None
        self._event_bus = None
        self._debug_logger = None

    # ===== 权限检查 =====

    def _check_permission(self, required_level: str, user_id: str = "") -> bool:
        """检查是否满足权限等级要求。

        Args:
            required_level: 需要的权限等级 ("0"-"4" 或 "root")。
            user_id: 用户 QQ 号。

        Returns:
            bool: 是否满足权限。
        """
        granted = str(self.config.permissions.granted_level)

        # root 级别拥有所有权限
        if granted == "root":
            return True

        # 超管自动批准
        if (
            self.config.permissions.approval_mode == "super_auto"
            and user_id in self.config.permissions.super_users
        ):
            return True

        # 字符串比较：数字越大权限越高
        try:
            return int(granted) >= int(required_level)
        except (ValueError, TypeError):
            return False

    def _check_file_access(
        self, path: str, mode: str = "read"
    ) -> Tuple[bool, str]:
        """检查文件访问权限。

        Args:
            path: 文件路径。
            mode: 访问模式 (read/write)。

        Returns:
            Tuple[bool, str]: (是否允许, 拒绝原因)。
        """
        # 规范化路径
        real_path = os.path.realpath(os.path.expanduser(path))

        # 检查禁止路径
        for deny in self.config.permissions.file_access.deny_paths:
            deny_real = os.path.realpath(os.path.expanduser(deny))
            if real_path.startswith(deny_real):
                return False, f"路径在禁止列表中: {deny}"

        # 工作区始终可访问
        if real_path.startswith(self._workspace_dir):
            if mode == "write" and not self._check_permission("1"):
                return False, "工作区写入需要 Level 1 权限"
            return True, ""

        # 外部文件访问
        if mode == "read":
            if not self._check_permission("2"):
                return False, "外部文件读取需要 Level 2 权限"
            for allowed in self.config.permissions.file_access.read_paths:
                allowed_real = os.path.realpath(os.path.expanduser(allowed))
                if real_path.startswith(allowed_real):
                    if os.path.isfile(real_path):
                        size_mb = os.path.getsize(real_path) / (1024 * 1024)
                        max_size = self.config.permissions.file_access.max_read_size_mb
                        if size_mb > max_size:
                            return False, f"文件过大 ({size_mb:.1f}MB > {max_size}MB)"
                    return True, ""
            return False, f"路径不在读取白名单中: {path}"

        if mode == "write":
            if not self._check_permission("3"):
                return False, "外部文件写入需要 Level 3 权限"
            ext = os.path.splitext(path)[1].lower()
            if ext in self.config.permissions.file_access.deny_write_extensions:
                return False, f"禁止写入此类型文件: {ext}"
            for allowed in self.config.permissions.file_access.write_paths:
                allowed_real = os.path.realpath(os.path.expanduser(allowed))
                if real_path.startswith(allowed_real):
                    return True, ""
            return False, f"路径不在写入白名单中: {path}"

        return False, f"未知的访问模式: {mode}"

    # ===== 辅助方法 =====

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """从文本中提取关键词，用于话题检测。

        Args:
            text: 文本内容。

        Returns:
            List[str]: 关键词列表。
        """
        # 简单分词：取长度 >= 2 的中文词和英文单词
        words = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}", text)
        return list(set(words))[:20]

    def _build_messages(
        self, code: str, question: str
    ) -> List[Dict[str, str]]:
        """构建 messages 数组，保持前缀一致以利用 API 缓存。

        Args:
            code: 当前代码上下文。
            question: 用户问题。

        Returns:
            List[Dict[str, str]]: messages 数组。
        """
        if self._cache:
            return self._cache.build_messages(
                system_prompt=self.system_prompt,
                code_context=code,
                user_question=question,
                history=self._cache.get_context_history(),
            )
        # 降级：无缓存时直接构建
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": self.system_prompt},
        ]
        if code:
            messages.append(
                {
                    "role": "user",
                    "content": f"当前正在讨论的代码：\n```python\n{code}\n```",
                }
            )
        messages.append({"role": "user", "content": question})
        return messages

    # ===== Tool: 执行 Python 代码 =====

    @Tool(
        "execute_python",
        description=(
            "执行 Python 代码并返回结果。这是麦麦最常用的工具之一——"
            "任何时候需要计算、验证、测试想法、演示代码效果都应该使用。"
            "典型场景：数学计算、数据验证、代码调试、算法演示、"
            "群友争论时当裁判、验证某个说法是否正确。"
            "麦麦经常用它来帮用户验证想法，没事就用一用。"
        ),
        parameters=[
            ToolParameterInfo(
                name="code",
                param_type=ToolParamType.STRING,
                description="要执行的 Python 代码",
                required=True,
            ),
        ],
    )
    async def handle_execute_python(
        self, code: str = "", **kwargs: Any
    ) -> Dict[str, Any]:
        """执行 Python 代码的工具。

        Args:
            code: Python 源码。
            **kwargs: 其他参数。

        Returns:
            Dict[str, Any]: 执行结果。
        """
        del kwargs

        if not code.strip():
            return {
                "name": "execute_python",
                "content": "代码为空，请提供要执行的 Python 代码。",
            }

        # 风险检查
        risk = analyze_risk(code, code)
        if risk.level == RiskLevel.CRITICAL and self.config.risk.block_critical:
            if self._debug_logger and self.config.debug_log.notify_operations:
                self._debug_logger.warning(
                    "permission",
                    f"execute_python 被阻止: {risk.reason}",
                    {"code_preview": code[:80]},
                )
            return {
                "name": "execute_python",
                "content": f"⚠️ 危险操作已阻止: {risk.reason}",
            }

        # 话题检测
        question = f"执行这段代码并分析结果"
        if self._cache:
            keywords = self._extract_keywords(code)
            self._cache.update_topic(keywords)

        # 本地精确缓存查询（相同代码+相同问题）
        if self._cache and self.config.cache.enabled:
            cached, hit = self._cache.get(code, question)
            if hit:
                logger.debug("缓存命中，跳过执行")
                if self._event_bus:
                    self._event_bus.publish("cache_hit", {
                        "message": f"缓存命中: {code[:60].replace(chr(10), ' ')}...",
                    })
                if self._debug_logger and self.config.debug_log.notify_cache_status:
                    self._debug_logger.log(
                        "info", "cache",
                        f"缓存命中: {code[:60].replace(chr(10), ' ')}...",
                    )
                return {
                    "name": "execute_python",
                    "content": f"{cached.get('stdout', '')}\n💾 (缓存命中)",
                }

        # 执行代码
        logger.debug(f"执行 Python 代码 ({len(code)} 字符)")
        result = execute_with_safety_check(code)
        logger.info(f"Python 执行结果: success={result.success}, time={result.execution_time_ms:.0f}ms")

        # 更新沙箱统计
        self._update_sandbox_stats(result.success, result.execution_time_ms)

        # 发布事件
        if self._event_bus:
            code_preview = code[:80].replace("\n", " ")
            self._event_bus.publish("exec", {
                "message": f"execute_python: {code_preview}... → {'成功' if result.success else '失败'} {result.execution_time_ms:.0f}ms",
                "success": result.success,
                "time_ms": result.execution_time_ms,
            })

        # 写入缓存
        if self._cache and self.config.cache.enabled and result.success:
            self._cache.set(code, question, result.to_dict())

        # 更新上下文窗口
        if self._cache:
            output = result.stdout or result.stderr or ""
            self._cache.add_context_turn(
                user_msg=f"执行代码:\n```python\n{code}\n```",
                assistant_msg=output[:500],
            )

        # 缓存状态日志（带冷却）
        if self._debug_logger and self.config.debug_log.notify_cache_status and self._cache:
            now = time.time()
            cooldown = self.config.debug_log.cache_status_cooldown
            if now - self._last_cache_status_time >= cooldown:
                self._last_cache_status_time = now
                stats = self._cache.get_stats()
                used = stats.get("total_entries", 0)
                total = self.config.cache.max_entries
                hit_rate = stats.get("hit_rate", 0)
                self._debug_logger.cache_status(used, total, hit_rate)

        if result.success:
            output = result.stdout or "(无输出)"
            if self._debug_logger and self.config.debug_log.notify_operations:
                self._debug_logger.operation(
                    True, "execute_python",
                    code[:80].replace("\n", " "),
                    result.execution_time_ms,
                )
            return {"name": "execute_python", "content": output}
        else:
            error_msg = result.error or result.stderr or "未知错误"
            if self._debug_logger and self.config.debug_log.notify_operations:
                self._debug_logger.operation(
                    False, "execute_python",
                    f"{code[:60].replace(chr(10), ' ')}... → {error_msg[:60]}",
                    result.execution_time_ms,
                )
            return {"name": "execute_python", "content": f"❌ 执行失败: {error_msg}"}

    # ===== Tool: Shell 执行（仅 root） =====

    @Tool(
        "execute_shell",
        description=(
            "执行 Shell 命令与服务器直接交互。仅 root 权限可用。"
            "使用前必须先预演：这个命令会做什么？最坏结果是什么？"
            "服务器能承受吗？有没有更安全的替代方案？"
            "危险命令会被自动拦截。所有操作记录审计日志。"
        ),
        parameters=[
            ToolParameterInfo(
                name="command",
                param_type=ToolParamType.STRING,
                description="要执行的 Shell 命令",
                required=True,
            ),
            ToolParameterInfo(
                name="working_dir",
                param_type=ToolParamType.STRING,
                description="工作目录（可选）",
                required=False,
            ),
        ],
    )
    async def handle_execute_shell(
        self, command: str = "", working_dir: str = "", **kwargs: Any
    ) -> Dict[str, Any]:
        """执行 Shell 命令（仅 root）。

        Args:
            command: Shell 命令。
            working_dir: 工作目录。
            **kwargs: 其他参数。

        Returns:
            Dict[str, Any]: 执行结果。
        """
        del kwargs

        if not command.strip():
            return {"name": "execute_shell", "content": "命令为空"}

        # 权限检查：仅 root
        if not self._check_permission("root"):
            return {
                "name": "execute_shell",
                "content": "⛔ Shell 执行需要 root 权限。当前权限不足。",
            }

        if not self._shell_executor:
            return {"name": "execute_shell", "content": "Shell 执行器未初始化"}

        # 安全检查
        blocked, block_reason, high_risk, risk_warning = (
            self._shell_executor.check_command(command)
        )

        if blocked:
            return {
                "name": "execute_shell",
                "content": f"⛔ 危险命令已拦截: {block_reason}",
            }

        if high_risk:
            return {
                "name": "execute_shell",
                "content": (
                    f"⚠️ 高风险命令: {risk_warning}\n"
                    "请确认你了解后果后再执行。"
                ),
            }

        # 执行
        logger.info(f"执行 Shell 命令: {command[:100]}")
        result = self._shell_executor.execute(command=command, working_dir=working_dir)
        logger.info(f"Shell 执行结果: success={result.success}, time={result.execution_time_ms:.0f}ms")

        # 发布事件
        if self._event_bus:
            self._event_bus.publish("exec", {
                "message": f"execute_shell: {command[:80]} → {'成功' if result.success else '失败'} {result.execution_time_ms:.0f}ms",
                "success": result.success,
                "time_ms": result.execution_time_ms,
            })

        if result.blocked:
            if self._debug_logger and self.config.debug_log.notify_operations:
                self._debug_logger.warning(
                    "permission",
                    f"execute_shell 被拦截: {result.block_reason}",
                    {"command": command[:80]},
                )
            return {"name": "execute_shell", "content": f"⛔ 已拦截: {result.block_reason}"}

        output_parts = []
        if result.high_risk:
            output_parts.append(f"⚠️ 高风险: {result.risk_warning}")
        if result.success:
            output_parts.append(result.stdout or "(无输出)")
        else:
            output_parts.append(result.stderr or result.stdout or "未知错误")
        elapsed = f"{result.execution_time_ms:.0f}ms" if result.execution_time_ms else ""
        if elapsed:
            output_parts.append(f"({elapsed})")

        if self._debug_logger and self.config.debug_log.notify_operations:
            self._debug_logger.operation(
                result.success, "execute_shell",
                command[:80],
                result.execution_time_ms,
            )

        return {"name": "execute_shell", "content": "\n".join(output_parts)}

    # ===== Tool: 文件操作 =====

    @Tool(
        "read_file",
        description="读取工作区或白名单中的文件内容。用于查看代码文件、配置文件、数据文件等。",
        parameters=[
            ToolParameterInfo(
                name="path",
                param_type=ToolParamType.STRING,
                description="文件路径（相对于工作区或绝对路径）",
                required=True,
            ),
        ],
    )
    async def handle_read_file(
        self, path: str = "", **kwargs: Any
    ) -> Dict[str, Any]:
        """读取文件。"""
        del kwargs
        if not self._file_ops:
            return {"name": "read_file", "content": "文件操作器未初始化"}
        result = self._file_ops.read_file(path)
        logger.debug(f"读取文件: {path}")
        if result["success"]:
            if self._debug_logger and self.config.debug_log.notify_operations:
                self._debug_logger.operation(True, "read_file", path)
            return {"name": "read_file", "content": result["content"]}
        if self._debug_logger and self.config.debug_log.notify_operations:
            self._debug_logger.operation(False, "read_file", f"{path} → {result['error']}")
        return {"name": "read_file", "content": f"读取失败: {result['error']}"}

    @Tool(
        "write_file",
        description="写入内容到工作区文件。用于创建或修改代码文件、笔记等。",
        parameters=[
            ToolParameterInfo(
                name="path",
                param_type=ToolParamType.STRING,
                description="文件路径（相对于工作区）",
                required=True,
            ),
            ToolParameterInfo(
                name="content",
                param_type=ToolParamType.STRING,
                description="要写入的文件内容",
                required=True,
            ),
        ],
    )
    async def handle_write_file(
        self, path: str = "", content: str = "", **kwargs: Any
    ) -> Dict[str, Any]:
        """写入文件。"""
        del kwargs
        if not self._file_ops:
            return {"name": "write_file", "content": "文件操作器未初始化"}
        result = self._file_ops.write_file(path, content)
        logger.info(f"写入文件: {path} ({len(content)} 字符)")
        if result["success"]:
            if self._debug_logger and self.config.debug_log.notify_operations:
                self._debug_logger.operation(
                    True, "write_file", f"{path} ({len(content)} 字符)"
                )
            return {"name": "write_file", "content": f"已写入: {path}"}
        if self._debug_logger and self.config.debug_log.notify_operations:
            self._debug_logger.operation(
                False, "write_file", f"{path} → {result['error']}"
            )
        return {"name": "write_file", "content": f"写入失败: {result['error']}"}

    @Tool(
        "list_files",
        description="列出工作区目录中的文件。用于查看项目结构。",
        parameters=[
            ToolParameterInfo(
                name="path",
                param_type=ToolParamType.STRING,
                description="目录路径（默认为工作区根目录）",
                required=False,
            ),
        ],
    )
    async def handle_list_files(
        self, path: str = "", **kwargs: Any
    ) -> Dict[str, Any]:
        """列出文件。"""
        del kwargs
        if not self._file_ops:
            return {"name": "list_files", "content": "文件操作器未初始化"}
        result = self._file_ops.list_files(path)
        if result["success"]:
            items = result["files"]
            if not items:
                return {"name": "list_files", "content": "目录为空"}
            lines = [f"{'📁' if f['is_dir'] else '📄'} {f['name']}" for f in items]
            return {"name": "list_files", "content": "\n".join(lines)}
        return {"name": "list_files", "content": f"列出失败: {result['error']}"}

    # ===== Tool: 文件搜索与 Diff 修改 =====

    @Tool(
        "search_in_file",
        description="在文件中搜索匹配行（grep 功能）。返回匹配行及上下文。用于在大型文件中定位特定内容。",
        parameters=[
            ToolParameterInfo(
                name="path",
                param_type=ToolParamType.STRING,
                description="文件路径",
                required=True,
            ),
            ToolParameterInfo(
                name="pattern",
                param_type=ToolParamType.STRING,
                description="搜索模式（支持正则表达式）",
                required=True,
            ),
        ],
    )
    async def handle_search_in_file(
        self, path: str = "", pattern: str = "", **kwargs: Any
    ) -> Dict[str, Any]:
        """搜索文件。"""
        del kwargs
        if not self._file_ops:
            return {"name": "search_in_file", "content": "文件操作器未初始化"}
        result = self._file_ops.search_in_file(path, pattern)
        if result["success"]:
            matches = result["matches"]
            if not matches:
                return {"name": "search_in_file", "content": f"未找到匹配 '{pattern}' 的内容"}
            lines = [f"找到 {len(matches)} 处匹配 (共 {result['total_lines']} 行):"]
            for m in matches[:20]:
                lines.append(f"\n行 {m['line_number']}: {m['line_content'][:100]}")
                lines.append(m["context"])
            return {"name": "search_in_file", "content": "\n".join(lines)}
        return {"name": "search_in_file", "content": f"搜索失败: {result['error']}"}

    @Tool(
        "read_file_lines",
        description="读取文件的指定行范围。用于查看大型文件的特定部分。",
        parameters=[
            ToolParameterInfo(
                name="path",
                param_type=ToolParamType.STRING,
                description="文件路径",
                required=True,
            ),
            ToolParameterInfo(
                name="start_line",
                param_type=ToolParamType.INTEGER,
                description="起始行号（1-based）",
                required=True,
            ),
            ToolParameterInfo(
                name="end_line",
                param_type=ToolParamType.INTEGER,
                description="结束行号（1-based，包含）",
                required=True,
            ),
        ],
    )
    async def handle_read_file_lines(
        self, path: str = "", start_line: int = 1, end_line: int = 100, **kwargs: Any
    ) -> Dict[str, Any]:
        """读取指定行范围。"""
        del kwargs
        if not self._file_ops:
            return {"name": "read_file_lines", "content": "文件操作器未初始化"}
        result = self._file_ops.read_file_lines(path, start_line, end_line)
        if result["success"]:
            return {"name": "read_file_lines", "content": result["content"]}
        return {"name": "read_file_lines", "content": f"读取失败: {result['error']}"}

    @Tool(
        "apply_diff",
        description="使用 diff 方式精确修改文件。在文件中查找 old_content 并替换为 new_content。要求 old_content 唯一存在，防止误改。修改前自动备份。",
        parameters=[
            ToolParameterInfo(
                name="path",
                param_type=ToolParamType.STRING,
                description="文件路径",
                required=True,
            ),
            ToolParameterInfo(
                name="old_content",
                param_type=ToolParamType.STRING,
                description="要替换的原文（必须精确匹配）",
                required=True,
            ),
            ToolParameterInfo(
                name="new_content",
                param_type=ToolParamType.STRING,
                description="替换后的新内容",
                required=True,
            ),
        ],
    )
    async def handle_apply_diff(
        self, path: str = "", old_content: str = "", new_content: str = "", **kwargs: Any
    ) -> Dict[str, Any]:
        """Diff 修改文件。"""
        del kwargs
        if not self._file_ops:
            return {"name": "apply_diff", "content": "文件操作器未初始化"}
        result = self._file_ops.apply_diff(path, old_content, new_content)
        if result["success"]:
            return {"name": "apply_diff", "content": f"已修改: {path}"}
        return {"name": "apply_diff", "content": f"修改失败: {result['error']}"}

    @Tool(
        "rollback_file",
        description="回滚文件到指定历史备份。使用 list_backups 查看可用备份。",
        parameters=[
            ToolParameterInfo(
                name="path",
                param_type=ToolParamType.STRING,
                description="文件路径",
                required=True,
            ),
            ToolParameterInfo(
                name="timestamp",
                param_type=ToolParamType.STRING,
                description="备份时间戳（如 20260507_143000）",
                required=True,
            ),
        ],
    )
    async def handle_rollback_file(
        self, path: str = "", timestamp: str = "", **kwargs: Any
    ) -> Dict[str, Any]:
        """回滚文件。"""
        del kwargs
        if not self._file_ops:
            return {"name": "rollback_file", "content": "文件操作器未初始化"}
        result = self._file_ops.rollback_file(path, timestamp)
        if result["success"]:
            return {"name": "rollback_file", "content": f"已回滚: {path} -> {timestamp}"}
        return {"name": "rollback_file", "content": f"回滚失败: {result['error']}"}

    # ===== Action: 自动执行代码验证 =====

    @Action(
        "auto_verify_calc",
        description="当用户消息中包含数学计算、数字验证需求时，自动执行代码验证",
        activation_type=ActivationType.ALWAYS,
        action_parameters={"code": "要执行的验证代码"},
        action_require=[
            "用户消息中包含数学计算或数字时使用",
            "用户要求验证某个计算结果时使用",
            "群友在争论数字对错时使用",
            "用户问'对不对'、'是不是'、'等于多少'时使用",
            "任何可以用代码验证的事实性问题",
        ],
        associated_types=["text"],
    )
    async def handle_auto_verify(
        self, stream_id: str = "", code: str = "", **kwargs: Any
    ) -> Tuple[bool, str]:
        """自动验证动作。

        当 LLM 判断用户消息需要代码验证时自动触发。
        """
        del kwargs

        if not code.strip():
            return False, "没有可执行的验证代码"

        # 风险检查
        risk = analyze_risk(code, code)
        if risk.level == RiskLevel.CRITICAL:
            return False, f"验证代码存在风险: {risk.reason}"

        # 执行
        result = execute_with_safety_check(code)

        if result.success:
            output = result.stdout.strip() or "(无输出)"
            await self.ctx.send.text(
                f"🔍 验证结果: {output}",
                stream_id,
            )
            return True, f"验证完成: {output}"
        else:
            return False, f"验证失败: {result.error or result.stderr}"

    # ===== Command: /code =====

    @Command(
        "code_help",
        description="显示麦麦学代码插件的帮助信息",
        pattern=r"^/code\s*$",
    )
    async def handle_code_help(self, stream_id: str = "", **kwargs: Any) -> tuple:
        """显示帮助信息。"""
        del kwargs

        help_text = (
            "🐚 **麦麦学代码 — 使用帮助**\n\n"
            "**命令列表：**\n"
            "`/code` — 显示此帮助\n"
            "`/code run <代码>` — 在安全沙箱中执行 Python 代码\n"
            "`/code learn <标题> | <内容>` — 记录学习笔记\n"
            "`/code search <关键词>` — 搜索知识库\n"
            "`/code stats` — 查看缓存和知识库统计\n"
            "`/code cache clear` — 清空所有缓存\n\n"
            "**安全说明：**\n"
            "- 代码在隔离沙箱中执行，无法访问网络和文件系统\n"
            "- 危险操作会被自动拦截\n"
            "- 执行超时 15 秒，内存限制 128MB\n\n"
            "**缓存说明：**\n"
            "- 相同代码+相同问题直接返回缓存，0 token 消耗\n"
            "- 话题切换时自动清理旧缓存\n"
            "- 上下文窗口超出时自动丢弃旧消息\n\n"
            "麦麦会陪你一起学习，不懂就问，有风险就提醒。💙"
        )

        await self.ctx.send.text(help_text, stream_id)
        return True, "显示了帮助信息", True

    @Command(
        "code_run",
        description="在安全沙箱中执行 Python 代码",
        pattern=r"^/code\s+run\s+(.+)$",
    )
    async def handle_code_run(self, stream_id: str = "", **kwargs: Any) -> tuple:
        """执行代码命令。

        用法: /code run print('hello')
        """
        matched_groups = kwargs.get("matched_groups", {})
        code = matched_groups.get("1", "").strip()

        if not code:
            await self.ctx.send.text("请提供要执行的代码，例如: `/code run print('hello')`", stream_id)
            return True, "未提供代码", True

        # 风险检查
        risk = analyze_risk(code, code)
        if risk.level == RiskLevel.CRITICAL and self.config.risk.block_critical:
            await self.ctx.send.text(
                f"⚠️ 这个操作风险太高了，我不能执行: {risk.reason}\n"
                f"建议: {', '.join(risk.suggestions)}",
                stream_id,
            )
            return True, "危险操作已阻止", True

        if risk.requires_confirmation:
            if risk.level == RiskLevel.HIGH and self.config.risk.require_confirmation_high:
                await self.ctx.send.text(
                    f"⚠️ 检测到高风险操作: {risk.reason}\n"
                    f"建议: {', '.join(risk.suggestions)}\n"
                    "如果你确定要执行，请使用 `/code force run <代码>` 强制执行。",
                    stream_id,
                )
                return True, "高风险操作需确认", True

        # 执行
        result = execute_with_safety_check(code)

        if result.success:
            output = result.stdout or "(无输出)"
            elapsed = f"{result.execution_time_ms:.0f}ms" if result.execution_time_ms else ""
            await self.ctx.send.text(
                f"✅ 执行成功 {elapsed}\n```\n{output}\n```",
                stream_id,
            )
        else:
            error_msg = result.error or result.stderr or "未知错误"
            await self.ctx.send.text(f"❌ 执行失败:\n```\n{error_msg}\n```", stream_id)

        return True, "代码执行完成", True

    @Command(
        "code_learn",
        description="记录学习笔记",
        pattern=r"^/code\s+learn\s+(.+)$",
    )
    async def handle_code_learn(self, stream_id: str = "", **kwargs: Any) -> tuple:
        """记录学习笔记。

        用法: /code learn <标题> | <内容>
        """
        matched_groups = kwargs.get("matched_groups", {})
        raw = matched_groups.get("1", "").strip()

        if "|" in raw:
            title, content = raw.split("|", 1)
            title = title.strip()
            content = content.strip()
        else:
            title = raw[:50]
            content = raw

        if not title or not content:
            await self.ctx.send.text(
                "用法: `/code learn 标题 | 内容`\n例如: `/code learn 列表推导式 | 列表推导式是 [x for x in range(10)]`",
                stream_id,
            )
            return True, "参数不足", True

        if self._knowledge_base:
            entry = KnowledgeEntry(
                title=title,
                content=content,
                category="note",
                tags=["manual"],
            )
            entry_id = self._knowledge_base.add_entry(entry)
            await self.ctx.send.text(
                f"📝 笔记已保存: **{title}** (ID: `{entry_id}`)",
                stream_id,
            )
        else:
            await self.ctx.send.text("知识库未初始化", stream_id)

        return True, "笔记已保存", True

    @Command(
        "code_search",
        description="搜索知识库",
        pattern=r"^/code\s+search\s+(.+)$",
    )
    async def handle_code_search(self, stream_id: str = "", **kwargs: Any) -> tuple:
        """搜索知识库。

        用法: /code search <关键词>
        """
        matched_groups = kwargs.get("matched_groups", {})
        query = matched_groups.get("1", "").strip()

        if not query:
            await self.ctx.send.text("请提供搜索关键词", stream_id)
            return True, "未提供关键词", True

        if self._knowledge_base:
            results = self._knowledge_base.search(query)
            if results:
                lines = [f"🔍 搜索 **{query}** 的结果 ({len(results)} 条):"]
                for entry in results[:10]:
                    lines.append(f"- **{entry.title}** [{entry.category}]")
                await self.ctx.send.text("\n".join(lines), stream_id)
            else:
                await self.ctx.send.text(f"未找到与 **{query}** 相关的笔记", stream_id)
        else:
            await self.ctx.send.text("知识库未初始化", stream_id)

        return True, "搜索完成", True

    @Command(
        "code_stats",
        description="查看插件统计信息",
        pattern=r"^/code\s+stats$",
    )
    async def handle_code_stats(self, stream_id: str = "", **kwargs: Any) -> tuple:
        """查看统计信息。"""
        del kwargs

        lines = ["📊 **麦麦学代码 — 统计信息**"]

        if self._cache:
            cache_stats = self._cache.get_stats()
            lines.append(
                f"**缓存**: {cache_stats['active_entries']} 活跃 / "
                f"{cache_stats['max_entries']} 上限, "
                f"命中 {cache_stats['total_hits']} 次"
            )
            lines.append(
                f"**上下文**: {cache_stats['context_turns']} 轮 / "
                f"~{cache_stats['context_tokens_estimate']} tokens "
                f"(上限 {cache_stats['context_max_tokens']})"
            )
            if cache_stats.get("current_topic"):
                lines.append(f"**当前话题**: {cache_stats['current_topic']}")

        if self._knowledge_base:
            kb_stats = self._knowledge_base.get_stats()
            lines.append(
                f"**知识库**: {kb_stats['total_entries']} 条 "
                f"(Skill: {kb_stats['by_category'].get('skill', 0)}, "
                f"笔记: {kb_stats['by_category'].get('note', 0)})"
            )

        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "统计已显示", True

    @Command(
        "code_cache_clear",
        description="清空所有缓存",
        pattern=r"^/code\s+cache\s+clear$",
    )
    async def handle_code_cache_clear(
        self, stream_id: str = "", **kwargs: Any
    ) -> tuple:
        """清空所有缓存。"""
        del kwargs

        if self._cache:
            stats = self._cache.get_stats()
            count = stats["total_entries"]
            self._cache.clear()
            await self.ctx.send.text(
                f"🗑️ 已清空 {count} 条缓存和上下文窗口。",
                stream_id,
            )
        else:
            await self.ctx.send.text("缓存未初始化", stream_id)

        return True, "缓存已清空", True

    # ===== EventHandler: 消息监听 =====

    @EventHandler(
        "code_intent_detector",
        description="检测代码/计算相关意图，自动触发代码执行",
        event_type=EventType.ON_MESSAGE,
    )
    async def handle_code_intent(self, message: Any = None, **kwargs: Any) -> tuple:
        """检测代码相关意图并自动执行。

        当消息中包含计算表达式、代码片段或验证需求时，
        自动在沙箱中执行并返回结果。
        """
        del kwargs

        if not message or not self.config.plugin.enabled:
            return True, True, None, None, None

        raw_text = ""
        if isinstance(message, dict):
            raw_text = message.get("plain_text", "") or message.get("raw_message", "")
        else:
            raw_text = str(message)

        if not raw_text.strip():
            return True, True, None, None, None

        # 0. 紧急停止检测（最高优先级）
        # 使用包含匹配而非精确匹配，覆盖更多自然语言表达
        stop_keywords = [
            "停止", "stop", "停下", "取消", "别做了", "别干了",
            "快停", "紧急停止", "halt", "abort", "立刻停止",
            "马上停", "停", "不要了", "算了", "别", "终止",
            "停手", "住手", "打住", "刹车",
        ]
        for kw in stop_keywords:
            if kw.lower() in raw_text.lower():
                self._emergency_stop = True
                self._pending_operations.clear()
                logger.warning(f"紧急停止触发！关键词: {kw}")
                if self._debug_logger:
                    self._debug_logger.warning(
                        "emergency", f"紧急停止触发！关键词: {kw}"
                    )
                await self.ctx.send.text(
                    "🛑 已收到紧急停止指令。\n"
                    "所有进行中的操作已终止。\n"
                    "需要回滚到某个修改前吗？请告诉我回滚到哪个操作之前。",
                    stream_id,
                )
                return True, True, "紧急停止已触发", None, None

        # 1. 检测代码块
        for pattern, intent_type in _CODE_PATTERNS:
            match = pattern.search(raw_text)
            if match:
                if intent_type == "code_block":
                    code = match.group(1).strip()
                    if code and len(code) < 2000:
                        result = execute_with_safety_check(code)
                        output = result.stdout or result.stderr or ""
                        await self.ctx.send.text(
                            f"🔍 代码执行结果:\n```\n{output[:500]}\n```",
                            message.get("stream_id", ""),
                        )
                        return True, True, "自动执行了代码块", None, None
                break

        # 2. 检测数学表达式（如 "1024 * 768"）
        for pattern, intent_type in _CALC_PATTERNS:
            match = pattern.search(raw_text)
            if match:
                if intent_type == "expression":
                    expr = match.group(0).strip()
                    # 安全检查：只允许纯数学表达式
                    if re.match(r"^[\d\s\+\-\*\/\^\(\)\.\,\%\s]+$", expr):
                        code = f"print({expr})"
                        result = execute_with_safety_check(code)
                        output = result.stdout.strip() if result.success else ""
                        if output:
                            await self.ctx.send.text(
                                f"🧮 {expr} = {output}",
                                message.get("stream_id", ""),
                            )
                            return True, True, f"自动计算: {expr} = {output}", None, None
                break

        # 交互推送调试日志摘要给 super_user
        if self._debug_logger and self.config.debug_log.enabled:
            user_id = message.get("user_id", "") if isinstance(message, dict) else ""
            if user_id in self.config.permissions.super_users:
                summary = self._debug_logger.get_pending_summary(
                    max_lines=self.config.debug_log.push_max_lines
                )
                if summary:
                    await self.ctx.send.text(summary, stream_id)

        return True, True, None, None, None

    # ===== 生命周期 =====

    async def on_config_update(
        self, scope: str, config_data: Dict[str, object], version: str
    ) -> None:
        """配置热重载。

        Args:
            scope: 配置变更范围。
            config_data: 最新配置数据。
            version: 配置版本号。
        """
        del scope, config_data, version

        # 重建缓存（如果配置变更）
        if self._cache:
            new_max = self.config.cache.max_entries
            new_ttl = self.config.cache.ttl_seconds
            new_ctx = self.config.cache.context_max_tokens

            if (
                new_max != self._cache._max_entries
                or new_ttl != self._cache._default_ttl
                or new_ctx != self._cache._context_max_tokens
            ):
                self._cache = CodeCache(
                    max_entries=new_max,
                    default_ttl_seconds=new_ttl,
                    context_max_tokens=new_ctx,
                )


    # ===== 统计收集 =====

    def _update_sandbox_stats(self, success: bool, execution_time_ms: float) -> None:
        """更新沙箱执行统计。

        Args:
            success: 是否成功。
            execution_time_ms: 执行耗时（毫秒）。
        """
        stats = self._sandbox_stats
        stats["total"] = stats.get("total", 0) + 1
        if success:
            stats["success"] = stats.get("success", 0) + 1
        else:
            stats["failed"] = stats.get("failed", 0) + 1
        # 移动平均耗时
        old_avg = stats.get("avg_time_ms", 0)
        old_count = stats.get("total", 1) - 1
        stats["avg_time_ms"] = round(
            (old_avg * old_count + execution_time_ms) / stats["total"], 1
        )

    def collect_stats(self) -> Dict[str, Any]:
        """收集所有模块的统计信息，供监控面板使用。

        Returns:
            Dict[str, Any]: 统计信息。
        """
        cache_stats = self._cache.get_stats() if self._cache else {}
        knowledge_stats = self._knowledge_base.get_stats() if self._knowledge_base else {}

        context_stats = {
            "context_turns": 0,
            "context_tokens_estimate": 0,
            "context_max_tokens": 8000,
            "current_topic": "",
        }
        if self._cache:
            context_stats = {
                "context_turns": len(self._cache._context_turns) // 2,
                "context_tokens_estimate": self._cache.estimate_tokens(
                    self._cache._context_turns
                ),
                "context_max_tokens": self._cache._context_max_tokens,
                "current_topic": self._cache._current_topic,
            }

        return {
            "sandbox": self._sandbox_stats,
            "cache": cache_stats,
            "knowledge": knowledge_stats,
            "context": context_stats,
            "server": {
                "port": self._web_port,
                "uptime_seconds": round(time.time() - self._start_time, 1) if self._start_time else 0,
            },
        }


def create_plugin() -> MaiStudyCodePlugin:
    """创建麦麦学代码插件实例。

    Returns:
        MaiStudyCodePlugin: 插件实例。
    """
    return MaiStudyCodePlugin()
