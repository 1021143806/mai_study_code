"""风险分析模块。

对代码操作进行风险评估，分为四个等级：
- CRITICAL: 系统级破坏（rm -rf, 修改系统配置等）
- HIGH: 数据风险（修改数据库、删除用户文件等）
- MEDIUM: 配置风险（修改项目配置、环境变量等）
- LOW: 普通操作（打印、计算等）
"""

from typing import Any, Dict, List, Optional, Tuple

import re


class RiskLevel:
    """风险等级常量。"""

    CRITICAL = "critical"  # 系统级破坏
    HIGH = "high"  # 数据风险
    MEDIUM = "medium"  # 配置风险
    LOW = "low"  # 普通操作
    NONE = "none"  # 无风险


class RiskResult:
    """风险评估结果。"""

    def __init__(
        self,
        level: str,
        reason: str = "",
        suggestions: Optional[List[str]] = None,
        requires_confirmation: bool = False,
    ) -> None:
        self.level = level
        self.reason = reason
        self.suggestions = suggestions or []
        self.requires_confirmation = requires_confirmation

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "level": self.level,
            "reason": self.reason,
            "suggestions": self.suggestions,
            "requires_confirmation": self.requires_confirmation,
        }


# ============================================================
# 风险模式定义
# ============================================================

# 危险命令模式（正则）
CRITICAL_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"rm\s+-rf\s+/"), "递归强制删除根目录"),
    (re.compile(r"mkfs\."), "格式化文件系统"),
    (re.compile(r"dd\s+if="), "磁盘直接写入"),
    (re.compile(r">\s*/dev/sd[a-z]"), "覆盖磁盘设备"),
    (re.compile(r"chmod\s+777\s+/"), "将根目录权限设为777"),
    (re.compile(r"chown\s+-R\s+\S+\s+/"), "递归修改根目录所有者"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;:"), "Fork 炸弹"),
    (re.compile(r"wget\s+\S+\s*-O\s+/etc/"), "下载文件覆盖系统配置"),
    (re.compile(r"curl\s+\S+\s*-o\s+/etc/"), "下载文件覆盖系统配置"),
]

HIGH_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"rm\s+-rf\s+[~/]"), "递归强制删除用户目录"),
    (re.compile(r"DROP\s+(TABLE|DATABASE)", re.IGNORECASE), "删除数据库表/库"),
    (re.compile(r"DELETE\s+FROM", re.IGNORECASE), "删除数据库记录"),
    (re.compile(r"shutdown|reboot|halt|poweroff"), "系统关机/重启"),
    (re.compile(r"kill\s+-9"), "强制终止进程"),
    (re.compile(r"iptables|ufw|firewall-cmd"), "修改防火墙规则"),
]

MEDIUM_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"pip\s+install|pip3\s+install"), "安装 Python 包"),
    (re.compile(r"npm\s+install|yarn\s+add"), "安装 Node.js 包"),
    (re.compile(r"git\s+push\s+--force"), "强制推送代码"),
    (re.compile(r"export\s+\w+="), "修改环境变量"),
    (re.compile(r"source\s+\S+\.sh"), "执行 shell 脚本"),
    (re.compile(r"\.\s+\S+\.sh"), "source shell 脚本"),
]


class RiskAnalyzer:
    """代码操作风险分析器。

    分析用户请求和代码内容，评估风险等级。
    """

    def __init__(self) -> None:
        """初始化风险分析器。"""
        self._critical_patterns = CRITICAL_PATTERNS
        self._high_patterns = HIGH_PATTERNS
        self._medium_patterns = MEDIUM_PATTERNS

    def analyze_request(self, user_message: str) -> RiskResult:
        """分析用户请求的风险等级。

        Args:
            user_message: 用户消息文本。

        Returns:
            RiskResult: 风险评估结果。
        """
        # 检查危险模式
        for pattern, reason in self._critical_patterns:
            if pattern.search(user_message):
                return RiskResult(
                    level=RiskLevel.CRITICAL,
                    reason=f"检测到危险操作: {reason}",
                    suggestions=[
                        "这个操作可能对系统造成不可逆的破坏",
                        "建议使用更安全的替代方案",
                        "如果确实需要执行，请手动操作并确认",
                    ],
                    requires_confirmation=True,
                )

        for pattern, reason in self._high_patterns:
            if pattern.search(user_message):
                return RiskResult(
                    level=RiskLevel.HIGH,
                    reason=f"检测到高风险操作: {reason}",
                    suggestions=[
                        "请确认你了解这个操作的后果",
                        "建议先备份相关数据",
                    ],
                    requires_confirmation=True,
                )

        for pattern, reason in self._medium_patterns:
            if pattern.search(user_message):
                return RiskResult(
                    level=RiskLevel.MEDIUM,
                    reason=f"检测到中等风险操作: {reason}",
                    suggestions=["请确认这是你想要的操作"],
                    requires_confirmation=True,
                )

        return RiskResult(
            level=RiskLevel.LOW,
            reason="未检测到明显风险",
            requires_confirmation=False,
        )

    def analyze_code(self, code: str) -> RiskResult:
        """分析代码内容的风险等级。

        Args:
            code: Python 代码文本。

        Returns:
            RiskResult: 风险评估结果。
        """
        risks: List[Tuple[str, str]] = []

        # 检查文件写入操作
        if re.search(r"open\([^)]*['\"][wa]", code):
            risks.append((RiskLevel.MEDIUM, "代码包含文件写入操作"))

        # 检查网络操作
        if re.search(r"(import\s+socket|import\s+requests|urllib)", code):
            risks.append((RiskLevel.HIGH, "代码包含网络操作"))

        # 检查子进程
        if re.search(r"(subprocess|os\.system|os\.popen)", code):
            risks.append((RiskLevel.CRITICAL, "代码尝试执行系统命令"))

        # 检查文件系统遍历
        if re.search(r"os\.walk|os\.listdir|glob\.glob", code):
            risks.append((RiskLevel.MEDIUM, "代码包含文件系统遍历"))

        if not risks:
            return RiskResult(
                level=RiskLevel.LOW,
                reason="代码未检测到明显风险",
                requires_confirmation=False,
            )

        # 取最高风险等级
        level_order = {
            RiskLevel.CRITICAL: 4,
            RiskLevel.HIGH: 3,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 1,
        }
        highest = max(risks, key=lambda r: level_order.get(r[0], 0))

        return RiskResult(
            level=highest[0],
            reason="; ".join(r[1] for r in risks),
            suggestions=["代码包含潜在风险操作，请确认后再执行"],
            requires_confirmation=highest[0] in (RiskLevel.CRITICAL, RiskLevel.HIGH),
        )

    def analyze(self, user_message: str, code: str = "") -> RiskResult:
        """综合分析用户请求和代码的风险。

        Args:
            user_message: 用户消息。
            code: 代码内容（可选）。

        Returns:
            RiskResult: 综合风险评估结果。
        """
        request_risk = self.analyze_request(user_message)

        if code:
            code_risk = self.analyze_code(code)
            # 取两者中风险更高的
            level_order = {
                RiskLevel.CRITICAL: 4,
                RiskLevel.HIGH: 3,
                RiskLevel.MEDIUM: 2,
                RiskLevel.LOW: 1,
                RiskLevel.NONE: 0,
            }
            if level_order.get(code_risk.level, 0) > level_order.get(
                request_risk.level, 0
            ):
                return code_risk

        return request_risk


# 全局实例
_analyzer = RiskAnalyzer()


def analyze_risk(user_message: str, code: str = "") -> RiskResult:
    """分析风险的便捷函数。

    Args:
        user_message: 用户消息。
        code: 代码内容（可选）。

    Returns:
        RiskResult: 风险评估结果。
    """
    return _analyzer.analyze(user_message, code)
