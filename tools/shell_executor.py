"""Shell 命令执行器。

仅 root 级别可用。提供与服务器直接交互的能力。
每次执行前强制预演最坏结果，危险命令自动拦截。
所有操作记录审计日志。
"""

from typing import Any, Dict, List, Optional, Tuple

import os
import re
import subprocess
import time


# ============================================================
# 危险命令模式（即使 root 也拦截）
# ============================================================
BLOCKED_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"rm\s+-rf\s+/"), "递归强制删除根目录"),
    (re.compile(r"mkfs\."), "格式化文件系统"),
    (re.compile(r"dd\s+if=.+\s+of=/dev/"), "直接写入磁盘设备"),
    (re.compile(r">\s*/dev/sd[a-z]"), "覆盖磁盘设备"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;:"), "Fork 炸弹"),
    (re.compile(r"chmod\s+777\s+/"), "将根目录权限设为777"),
    (re.compile(r"chown\s+-R\s+\S+\s+/"), "递归修改根目录所有者"),
]

# 高风险命令（需要额外确认，但不拦截）
HIGH_RISK_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"rm\s+-rf\s+[~/]"), "递归强制删除用户目录"),
    (re.compile(r"shutdown|reboot|halt|poweroff"), "系统关机/重启"),
    (re.compile(r"kill\s+-9"), "强制终止进程"),
    (re.compile(r"iptables|ufw|firewall-cmd"), "修改防火墙规则"),
    (re.compile(r"systemctl\s+(stop|disable|mask)"), "停止/禁用系统服务"),
    (re.compile(r"passwd|useradd|userdel|usermod"), "修改用户账户"),
]


class ShellResult:
    """Shell 命令执行结果。"""

    def __init__(
        self,
        success: bool,
        stdout: str = "",
        stderr: str = "",
        returncode: int = -1,
        blocked: bool = False,
        block_reason: str = "",
        high_risk: bool = False,
        risk_warning: str = "",
        execution_time_ms: float = 0,
    ) -> None:
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.blocked = blocked
        self.block_reason = block_reason
        self.high_risk = high_risk
        self.risk_warning = risk_warning
        self.execution_time_ms = execution_time_ms

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "high_risk": self.high_risk,
            "risk_warning": self.risk_warning,
            "execution_time_ms": self.execution_time_ms,
        }


class ShellExecutor:
    """Shell 命令执行器。

    仅 root 级别可用。提供危险命令拦截、高风险警告、
    审计日志等安全机制。
    """

    def __init__(
        self,
        workspace_dir: str,
        default_timeout: int = 60,
        max_output_chars: int = 10000,
    ) -> None:
        """初始化 Shell 执行器。

        Args:
            workspace_dir: 工作区目录（用于审计日志）。
            default_timeout: 默认超时时间（秒）。
            max_output_chars: 最大输出字符数。
        """
        self._workspace_dir = workspace_dir
        self._default_timeout = default_timeout
        self._max_output_chars = max_output_chars
        self._history_file = os.path.join(workspace_dir, ".shell_history.log")

    def check_command(self, command: str) -> Tuple[bool, str, bool, str]:
        """检查命令安全性。

        Args:
            command: 要执行的命令。

        Returns:
            Tuple[bool, str, bool, str]:
                (是否被拦截, 拦截原因, 是否高风险, 风险警告)
        """
        # 检查拦截模式
        for pattern, reason in BLOCKED_PATTERNS:
            if pattern.search(command):
                return True, reason, False, ""

        # 检查高风险模式
        for pattern, reason in HIGH_RISK_PATTERNS:
            if pattern.search(command):
                return False, "", True, reason

        return False, "", False, ""

    def execute(
        self,
        command: str,
        working_dir: str = "",
        timeout: Optional[int] = None,
        user_id: str = "",
    ) -> ShellResult:
        """执行 Shell 命令。

        Args:
            command: 要执行的命令。
            working_dir: 工作目录。
            timeout: 超时时间（秒）。
            user_id: 触发用户 ID（用于审计）。

        Returns:
            ShellResult: 执行结果。
        """
        if timeout is None:
            timeout = self._default_timeout

        # 安全检查
        blocked, block_reason, high_risk, risk_warning = self.check_command(command)

        if blocked:
            self._log(user_id, command, "BLOCKED", block_reason)
            return ShellResult(
                success=False,
                blocked=True,
                block_reason=block_reason,
            )

        # 执行
        start_time = time.monotonic()
        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=working_dir or None,
                text=True,
                executable="/bin/bash",
            )

            stdout, stderr = proc.communicate(timeout=timeout)
            elapsed_ms = (time.monotonic() - start_time) * 1000

            # 截断输出
            stdout = stdout[: self._max_output_chars] if stdout else ""
            stderr = stderr[: self._max_output_chars] if stderr else ""

            success = proc.returncode == 0

            self._log(user_id, command, "SUCCESS" if success else "FAILED", "")

            return ShellResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                returncode=proc.returncode,
                high_risk=high_risk,
                risk_warning=risk_warning,
                execution_time_ms=elapsed_ms,
            )

        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            elapsed_ms = (time.monotonic() - start_time) * 1000
            self._log(user_id, command, "TIMEOUT", f"超时 {timeout}s")
            return ShellResult(
                success=False,
                stderr=f"命令执行超时 ({timeout}秒)",
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            self._log(user_id, command, "ERROR", str(e))
            return ShellResult(
                success=False,
                stderr=f"执行异常: {e}",
                execution_time_ms=elapsed_ms,
            )

    def _log(self, user_id: str, command: str, status: str, detail: str) -> None:
        """写入审计日志。

        Args:
            user_id: 触发用户 ID。
            command: 执行的命令。
            status: 执行状态。
            detail: 详细信息。
        """
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_line = f"[{timestamp}] user={user_id} status={status} cmd={command}"
            if detail:
                log_line += f" detail={detail}"
            log_line += "\n"

            os.makedirs(os.path.dirname(self._history_file), exist_ok=True)
            with open(self._history_file, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception:
            pass  # 日志写入失败不影响主流程
