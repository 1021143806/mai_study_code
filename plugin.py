"""麦麦学代码 (Mai Study Code) 插件。

一个陪你一起学习编程的伙伴插件，不是工具而是同路人。
- 安全沙箱执行 Python 代码
- 本地精确缓存 + API 前缀缓存对齐
- 风险识别与确认机制
- 本地知识库自维护
- 话题感知缓存清理
"""

from typing import Any, Dict, List, Optional

import os
import re

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


class MaiStudyCodeConfig(PluginConfigBase):
    """麦麦学代码插件配置。"""

    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    learner: LearnerConfig = Field(default_factory=LearnerConfig)


# ============================================================
# 插件主体
# ============================================================


class MaiStudyCodePlugin(MaiBotPlugin):
    """麦麦学代码插件。

    一个陪你一起学习编程的伙伴。
    """

    config_model = MaiStudyCodeConfig

    # 默认 system prompt（保持前缀一致以利用 API 缓存）
    SYSTEM_PROMPT = (
        "你是麦麦，一个陪你一起学习编程的伙伴。"
        "你不是冷冰冰的代码工具，而是一个有温度的同路人。"
        "你会认真分析代码，给出清晰的解释，遇到风险会提醒。"
        "回复风格：简洁、友好、有洞察力，像朋友一样交流。"
    )

    def __init__(self) -> None:
        super().__init__()
        self._cache: Optional[CodeCache] = None
        self._knowledge_base: Optional[KnowledgeBase] = None

    async def on_load(self) -> None:
        """插件加载时初始化。"""
        # 初始化缓存
        self._cache = CodeCache(
            max_entries=self.config.cache.max_entries,
            default_ttl_seconds=self.config.cache.ttl_seconds,
            context_max_tokens=self.config.cache.context_max_tokens,
        )

        # 初始化知识库
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        knowledge_dir = os.path.join(plugin_dir, self.config.learner.knowledge_dir)
        self._knowledge_base = KnowledgeBase(knowledge_dir)

    async def on_unload(self) -> None:
        """插件卸载时清理。"""
        if self._cache:
            self._cache.clear()
        self._cache = None
        self._knowledge_base = None

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
                system_prompt=self.SYSTEM_PROMPT,
                code_context=code,
                user_question=question,
                history=self._cache.get_context_history(),
            )
        # 降级：无缓存时直接构建
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
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
        description="在安全沙箱中执行 Python 代码，返回执行结果。适合用于计算、数据处理、算法验证等场景。",
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
                return {
                    "name": "execute_python",
                    "content": f"{cached.get('stdout', '')}\n💾 (缓存命中)",
                }

        # 执行代码
        result = execute_with_safety_check(code)

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

        if result.success:
            output = result.stdout or "(无输出)"
            return {"name": "execute_python", "content": output}
        else:
            error_msg = result.error or result.stderr or "未知错误"
            return {"name": "execute_python", "content": f"❌ 执行失败: {error_msg}"}

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
        description="检测代码相关意图的消息",
        event_type=EventType.ON_MESSAGE,
    )
    async def handle_code_intent(self, message: Any = None, **kwargs: Any) -> tuple:
        """检测代码相关意图。

        当消息中包含代码相关关键词时，可以提示用户使用 /code 命令。
        当前版本仅做被动响应，不主动提示。
        """
        del kwargs

        if not message or not self.config.plugin.enabled:
            return True, True, None, None, None

        # 预留：未来可以在这里做主动意图识别
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


def create_plugin() -> MaiStudyCodePlugin:
    """创建麦麦学代码插件实例。

    Returns:
        MaiStudyCodePlugin: 插件实例。
    """
    return MaiStudyCodePlugin()
