"""麦麦学代码 (Mai Study Code) 插件 — 精简版。

这个插件作为 MaiBot 与独立 mai_study_code 智能体进程之间的桥梁。
职责仅限于：
1. 注册 @Tool 到 Maisaka（execute_python / read_file / write_file 等）
2. EventHandler 检测代码/计算意图，通过 HTTP 转发给独立进程
3. 不再内嵌 Web 服务、LLM 调用循环、知识库管理

独立智能体进程由 Supervisor 管理：mai_study_code_agent
"""

from typing import Any, Dict, List, Optional, Tuple

import asyncio
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

from .risk import RiskLevel, analyze_risk
from .sandbox import execute_with_safety_check

# ============================================================
# 独立进程 HTTP 地址（Agent 端口见 agent_config.toml）
# 由 Supervisor 管理，启动后写在 /main/log/app/mai_study_code_agent.log
# ============================================================

_AGENT_BASE_URL = "http://127.0.0.1:38227"  # 默认端口，独立进程会输出实际端口


# ============================================================
# 意图检测正则
# ============================================================

_CALC_PATTERNS = [
    (re.compile(r"帮我算[一一下]?|算一下|计算[一一下]?|等于多少|是多少"), "calc"),
    (re.compile(r"对不对|对吗|是不是|有没有错|验证[一一下]?"), "verify"),
    (re.compile(r"(\d+[\+\-\*\/\^]\d+)|(\d+\s*[+\-*/]\s*\d+)"), "expression"),
    (re.compile(r"(sum|len|max|min|sorted|range|print)\s*\("), "code_call"),
]

_CODE_PATTERNS = [
    (re.compile(r"```(?:python|py)?\s*\n(.+?)\n```", re.DOTALL), "code_block"),
    (re.compile(r"(?:写|帮[我我]写|给[我我]写)[一一下]?(?:个|段)?(?:python|代码)"), "write_code"),
    (re.compile(r"(?:这段|这个|这行)?代码.*(?:什么意思|干嘛的|做什么|怎么改|报错|不对)"), "code_question"),
]


# ============================================================
# 配置
# ============================================================


class PluginSectionConfig(PluginConfigBase):
    """插件基础配置。"""

    __ui_label__ = "插件"
    __ui_icon__ = "package"
    __ui_order__ = 0

    enabled: bool = Field(default=False, description="是否启用插件")
    config_version: str = Field(default="0.2.0", description="配置版本")


class SandboxConfig(PluginConfigBase):
    """沙箱配置。"""

    __ui_label__ = "沙箱"
    __ui_icon__ = "shield"
    __ui_order__ = 1

    max_memory_mb: int = Field(default=128, description="最大内存 (MB)")
    max_timeout_sec: int = Field(default=15, description="最大执行时间 (秒)")
    max_output_chars: int = Field(default=10000, description="最大输出字符数")


class RiskConfig(PluginConfigBase):
    """风险控制配置。"""

    __ui_label__ = "风险控制"
    __ui_icon__ = "alert-triangle"
    __ui_order__ = 2

    require_confirmation_medium: bool = Field(default=True, description="中等风险是否需要确认")
    require_confirmation_high: bool = Field(default=True, description="高风险是否需要确认")
    block_critical: bool = Field(default=True, description="是否阻止危险操作")


class PermissionsConfig(PluginConfigBase):
    """权限系统配置。"""

    __ui_label__ = "权限"
    __ui_icon__ = "shield-check"
    __ui_order__ = 3

    super_users: List[str] = Field(default_factory=list, description="最高权限用户 QQ 号")
    granted_level: Any = Field(default=0, description="当前已授予的权限等级")


class MaiStudyCodeConfig(PluginConfigBase):
    """麦麦学代码插件配置。"""

    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)


# ============================================================
# 插件主体
# ============================================================


class MaiStudyCodePlugin(MaiBotPlugin):
    """麦麦学代码插件（精简版）。

    职责：在 Maisaka 中注册代码相关的 @Tool，不再承担智能体逻辑。
    智能体逻辑由 mai_study_code_agent 独立进程承载。
    """

    config_model = MaiStudyCodeConfig

    async def on_load(self) -> None:
        """插件加载。"""
        logger.info("mai_study_code 精简版插件加载完成")

    async def on_unload(self) -> None:
        """插件卸载。"""
        logger.info("mai_study_code 精简版插件已卸载")

    async def on_config_update(self, scope: str, config_data: dict[str, Any], version: str) -> None:
        """配置热更新回调。"""
        logger.info(f"mai_study_code 配置已更新: scope={scope}, version={version}")

    # ===== Tool: 执行 Python 代码 =====

    @Tool(
        "execute_python",
        description=(
            "在安全沙箱中执行 Python 代码并返回结果。"
            "用于计算、验证、测试想法、调试代码。"
        ),
        parameters=[
            ToolParameterInfo(
                name="code",
                param_type=ToolParamType.STRING,
                description="要执行的 Python 代码",
                required=True,
            ),
        ],
        visibility="visible",
    )
    async def handle_execute_python(self, code: str = "", **kwargs: Any) -> Dict[str, Any]:
        """执行 Python 代码。"""
        del kwargs

        if not code.strip():
            return {"name": "execute_python", "content": "代码为空"}

        risk = analyze_risk(code, code)
        if risk.level == RiskLevel.CRITICAL and self.config.risk.block_critical:
            return {"name": "execute_python", "content": f"⚠️ 危险操作已阻止: {risk.reason}"}

        result = execute_with_safety_check(code)

        if result.success:
            output = result.stdout or "(无输出)"
            return {"name": "execute_python", "content": output}
        else:
            error_msg = result.error or result.stderr or "未知错误"
            return {"name": "execute_python", "content": f"❌ 执行失败: {error_msg}"}

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
        ],
        associated_types=["text"],
    )
    async def handle_auto_verify(
        self, stream_id: str = "", code: str = "", **kwargs: Any
    ) -> Tuple[bool, str]:
        """自动验证。"""
        del kwargs

        if not code.strip():
            return False, "没有可执行的验证代码"

        risk = analyze_risk(code, code)
        if risk.level == RiskLevel.CRITICAL:
            return False, f"验证代码存在风险: {risk.reason}"

        result = execute_with_safety_check(code)

        if result.success:
            output = result.stdout.strip() or "(无输出)"
            await self.ctx.send.text(f"🔍 验证结果: {output}", stream_id)
            return True, f"验证完成: {output}"
        else:
            return False, f"验证失败: {result.error or result.stderr}"

    # ===== EventHandler: 消息监听 =====

    @EventHandler(
        "code_intent_detector",
        description="检测代码/计算相关意图，自动触发代码执行",
        event_type=EventType.ON_MESSAGE,
    )
    async def handle_code_intent(self, message: Any = None, **kwargs: Any) -> tuple:
        """检测代码/计算意图。"""
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

        stream_id = message.get("stream_id", "") if isinstance(message, dict) else ""

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
                            stream_id,
                        )
                        return True, True, "自动执行了代码块", None, None
                break

        # 2. 检测数学表达式
        for pattern, intent_type in _CALC_PATTERNS:
            match = pattern.search(raw_text)
            if match:
                if intent_type == "expression":
                    expr = match.group(0).strip()
                    if re.match(r"^[\d\s\+\-\*\/\^\(\)\.\,\%\s]+$", expr):
                        code = f"print({expr})"
                        result = execute_with_safety_check(code)
                        output = result.stdout.strip() if result.success else ""
                        if output:
                            await self.ctx.send.text(
                                f"🧮 {expr} = {output}",
                                stream_id,
                            )
                            return True, True, f"自动计算: {expr} = {output}", None, None
                break

        return True, True, None, None, None


def create_plugin() -> MaiStudyCodePlugin:
    """创建插件实例。"""
    return MaiStudyCodePlugin()
