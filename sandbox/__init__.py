"""安全沙箱模块。

提供 Python 代码的安全执行环境，包括：
- AST 静态代码分析
- 子进程隔离执行
- 资源限制与超时控制
"""

from .ast_checker import ASTChecker, CodeSafetyError, check_code_safety
from .executor import ExecutionError, ExecutionResult, execute, execute_with_safety_check
from .limits import (
    ALLOWED_MODULES,
    FORBIDDEN_BUILTINS,
    FORBIDDEN_MODULES,
    RESOURCE_LIMITS,
    SAFE_BUILTINS,
    SANDBOX_WORK_DIR,
)

__all__ = [
    "ASTChecker",
    "CodeSafetyError",
    "check_code_safety",
    "ExecutionError",
    "ExecutionResult",
    "execute",
    "execute_with_safety_check",
    "ALLOWED_MODULES",
    "FORBIDDEN_BUILTINS",
    "FORBIDDEN_MODULES",
    "RESOURCE_LIMITS",
    "SAFE_BUILTINS",
    "SANDBOX_WORK_DIR",
]
