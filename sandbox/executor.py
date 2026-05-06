"""安全代码执行器。

在受限子进程中执行 Python 代码，提供多层安全防护：
- 子进程隔离
- 资源限制（内存、CPU、时间）
- 输出截断
- 工作目录限定
"""

from typing import Any, Dict, Optional

import os
import resource
import subprocess
import tempfile
import time

from .ast_checker import check_code_safety
from .limits import RESOURCE_LIMITS, SANDBOX_WORK_DIR


class ExecutionError(Exception):
    """代码执行异常。"""

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        super().__init__(message)
        self.detail = detail


class ExecutionResult:
    """代码执行结果。"""

    def __init__(
        self,
        success: bool,
        stdout: str = "",
        stderr: str = "",
        returncode: int = -1,
        error: str = "",
        execution_time_ms: float = 0,
    ) -> None:
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.error = error
        self.execution_time_ms = execution_time_ms

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }


def _ensure_sandbox_dir() -> None:
    """确保沙箱工作目录存在。"""
    os.makedirs(SANDBOX_WORK_DIR, exist_ok=True)


def _set_process_limits() -> None:
    """设置子进程资源限制（在子进程中调用）。"""
    max_memory = RESOURCE_LIMITS["max_memory_mb"] * 1024 * 1024
    max_cpu = RESOURCE_LIMITS["max_cpu_time_sec"]
    max_fsize = RESOURCE_LIMITS["max_file_size_mb"] * 1024 * 1024

    try:
        # 内存限制（软限制 / 硬限制）
        resource.setrlimit(resource.RLIMIT_AS, (max_memory, max_memory * 2))
    except (ValueError, resource.error):
        pass

    try:
        # CPU 时间限制
        resource.setrlimit(resource.RLIMIT_CPU, (max_cpu, max_cpu + 5))
    except (ValueError, resource.error):
        pass

    try:
        # 禁止创建子进程
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    except (ValueError, resource.error):
        pass

    try:
        # 文件大小限制
        resource.setrlimit(resource.RLIMIT_FSIZE, (max_fsize, max_fsize))
    except (ValueError, resource.error):
        pass


def execute(
    code: str,
    timeout: Optional[int] = None,
    max_output_chars: Optional[int] = None,
) -> ExecutionResult:
    """在安全沙箱中执行 Python 代码。

    执行流程：
    1. AST 静态安全检查
    2. 写入临时文件
    3. 子进程隔离执行
    4. 收集并截断输出
    5. 清理临时文件

    Args:
        code: 待执行的 Python 源码。
        timeout: 超时时间（秒），默认使用配置值。
        max_output_chars: 最大输出字符数，默认使用配置值。

    Returns:
        ExecutionResult: 执行结果。
    """
    if timeout is None:
        timeout = RESOURCE_LIMITS["max_wall_time_sec"]
    if max_output_chars is None:
        max_output_chars = RESOURCE_LIMITS["max_output_chars"]

    # 第1层：AST 静态检查
    passed, errors, warnings = check_code_safety(code)
    if not passed:
        error_msgs = "; ".join(str(e) for e in errors)
        return ExecutionResult(
            success=False,
            error=f"代码安全检查未通过: {error_msgs}",
        )

    _ensure_sandbox_dir()

    # 写入临时文件
    script_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            dir=SANDBOX_WORK_DIR,
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            script_path = f.name

        # 子进程执行
        start_time = time.monotonic()

        try:
            proc = subprocess.Popen(
                ["python3", "-I", "-S", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=SANDBOX_WORK_DIR,
                preexec_fn=_set_process_limits,
                text=True,
                env={
                    "PATH": "/usr/bin:/bin",
                    "HOME": SANDBOX_WORK_DIR,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": "",
                },
            )

            stdout, stderr = proc.communicate(timeout=timeout)
            elapsed_ms = (time.monotonic() - start_time) * 1000

            # 截断输出
            stdout = stdout[:max_output_chars] if stdout else ""
            stderr = stderr[:max_output_chars] if stderr else ""

            return ExecutionResult(
                success=proc.returncode == 0,
                stdout=stdout,
                stderr=stderr,
                returncode=proc.returncode,
                execution_time_ms=elapsed_ms,
            )

        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            elapsed_ms = (time.monotonic() - start_time) * 1000
            return ExecutionResult(
                success=False,
                error=f"代码执行超时 ({timeout}秒)",
                execution_time_ms=elapsed_ms,
            )

    except Exception as e:
        return ExecutionResult(
            success=False,
            error=f"执行器异常: {e}",
        )

    finally:
        # 清理临时文件
        if script_path and os.path.exists(script_path):
            try:
                os.unlink(script_path)
            except OSError:
                pass


def execute_with_safety_check(code: str) -> ExecutionResult:
    """先做安全检查再执行，返回详细结果。

    与 execute() 相同，但会在错误信息中包含 AST 检查的警告。

    Args:
        code: 待执行的 Python 源码。

    Returns:
        ExecutionResult: 执行结果。
    """
    passed, errors, warnings = check_code_safety(code)

    if not passed:
        error_msgs = "; ".join(str(e) for e in errors)
        return ExecutionResult(
            success=False,
            error=f"代码安全检查未通过: {error_msgs}",
        )

    result = execute(code)

    # 附加警告信息
    if warnings and result.success:
        warning_msgs = "; ".join(str(w) for w in warnings)
        if result.stdout:
            result.stdout = f"[警告] {warning_msgs}\n{result.stdout}"
        else:
            result.stdout = f"[警告] {warning_msgs}"

    return result
