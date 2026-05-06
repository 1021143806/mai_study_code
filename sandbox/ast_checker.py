"""AST 静态代码分析器。

在代码执行前对 Python 源码进行 AST 扫描，
检测危险的 import、函数调用和语法结构。
"""

from typing import List, Optional, Tuple

import ast

from .limits import ALLOWED_MODULES, FORBIDDEN_BUILTINS, FORBIDDEN_MODULES


class CodeSafetyError(Exception):
    """代码安全检查失败异常。"""

    def __init__(self, message: str, line: int = 0, col: int = 0) -> None:
        super().__init__(message)
        self.line = line
        self.col = col


class ASTChecker(ast.NodeVisitor):
    """AST 安全检查器。

    遍历 AST 节点，检测：
    - 禁止的 import 语句
    - 禁止的内置函数调用
    - 危险的文件操作
    - 过大的代码结构
    """

    def __init__(self, max_nodes: int = 500) -> None:
        """初始化检查器。

        Args:
            max_nodes: 最大 AST 节点数，防止代码膨胀攻击。
        """
        self.errors: List[CodeSafetyError] = []
        self.warnings: List[CodeSafetyError] = []
        self._node_count: int = 0
        self._max_nodes: int = max_nodes

    def check(self, code: str) -> Tuple[bool, List[CodeSafetyError], List[CodeSafetyError]]:
        """对代码执行安全检查。

        Args:
            code: 待检查的 Python 源码。

        Returns:
            Tuple[bool, List[CodeSafetyError], List[CodeSafetyError]]:
                (是否通过, 错误列表, 警告列表)
        """
        self.errors.clear()
        self.warnings.clear()
        self._node_count = 0

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self.errors.append(
                CodeSafetyError(f"语法错误: {e.msg}", e.lineno or 0, e.offset or 0)
            )
            return False, self.errors, self.warnings

        self.visit(tree)

        if self._node_count > self._max_nodes:
            self.errors.append(
                CodeSafetyError(
                    f"代码节点数 ({self._node_count}) 超过限制 ({self._max_nodes})"
                )
            )

        return len(self.errors) == 0, self.errors, self.warnings

    def _check_node_count(self) -> None:
        """检查节点计数。"""
        self._node_count += 1

    # ---- Import 检查 ----

    def visit_Import(self, node: ast.Import) -> None:
        """检查 import xxx 语句。"""
        self._check_node_count()
        for alias in node.names:
            self._check_import_name(alias.name, node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """检查 from xxx import yyy 语句。"""
        self._check_node_count()
        if node.module is None:
            return

        # 检查相对导入
        if node.level is not None and node.level > 0:
            self.errors.append(
                CodeSafetyError(
                    f"禁止相对导入 (level={node.level})",
                    node.lineno,
                    node.col_offset,
                )
            )
            return

        self._check_import_name(node.module, node.lineno, node.col_offset)

        for alias in node.names:
            full_name = f"{node.module}.{alias.name}"
            self._check_import_name(full_name, node.lineno, node.col_offset)

        self.generic_visit(node)

    def _check_import_name(self, name: str, lineno: int, col: int) -> None:
        """检查单个 import 名称是否安全。

        Args:
            name: 模块全名。
            lineno: 行号。
            col: 列偏移。
        """
        # 检查是否在禁止列表中
        for forbidden in FORBIDDEN_MODULES:
            if name == forbidden or name.startswith(forbidden + "."):
                self.errors.append(
                    CodeSafetyError(
                        f"禁止导入模块: {name}",
                        lineno,
                        col,
                    )
                )
                return

        # 检查是否在白名单中
        if name not in ALLOWED_MODULES:
            # 检查是否是白名单模块的子模块
            is_allowed = False
            for allowed in ALLOWED_MODULES:
                if name == allowed or name.startswith(allowed + "."):
                    is_allowed = True
                    break

            if not is_allowed:
                self.errors.append(
                    CodeSafetyError(
                        f"不允许导入模块: {name}（不在白名单中）",
                        lineno,
                        col,
                    )
                )

    # ---- 函数调用检查 ----

    def visit_Call(self, node: ast.Call) -> None:
        """检查函数调用。"""
        self._check_node_count()

        func_name = self._get_call_name(node)
        if func_name:
            # 检查禁止的内置函数
            if func_name in FORBIDDEN_BUILTINS:
                self.errors.append(
                    CodeSafetyError(
                        f"禁止调用: {func_name}()",
                        node.lineno,
                        node.col_offset,
                    )
                )

            # 检查 open() 调用
            if func_name == "open":
                self._check_open_call(node)

        self.generic_visit(node)

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """获取函数调用的名称。

        Args:
            node: Call AST 节点。

        Returns:
            Optional[str]: 函数名，无法确定时返回 None。
        """
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    def _check_open_call(self, node: ast.Call) -> None:
        """检查 open() 调用的模式参数。

        Args:
            node: open() 调用的 AST 节点。
        """
        # open() 的第二个参数是模式
        if len(node.args) >= 2:
            mode_arg = node.args[1]
            if isinstance(mode_arg, ast.Constant) and isinstance(mode_arg.value, str):
                mode = mode_arg.value.lower()
                if "w" in mode or "a" in mode or "+" in mode:
                    self.errors.append(
                        CodeSafetyError(
                            f"禁止文件写入模式: open(..., '{mode}')",
                            node.lineno,
                            node.col_offset,
                        )
                    )
            else:
                # 模式是变量，无法静态确定，保守拒绝
                self.errors.append(
                    CodeSafetyError(
                        "open() 模式参数必须是字符串常量",
                        node.lineno,
                        node.col_offset,
                    )
                )

        # 检查关键字参数 mode
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                mode = str(kw.value.value).lower()
                if "w" in mode or "a" in mode or "+" in mode:
                    self.errors.append(
                        CodeSafetyError(
                            f"禁止文件写入模式: open(mode='{mode}')",
                            node.lineno,
                            node.col_offset,
                        )
                    )

    # ---- 其他危险结构 ----

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """检查属性访问（防止双下划线访问）。"""
        self._check_node_count()
        if node.attr.startswith("__") and node.attr.endswith("__"):
            # 允许常见的魔术方法访问
            allowed_dunders = {"__class__", "__name__", "__doc__", "__dict__"}
            if node.attr not in allowed_dunders:
                self.warnings.append(
                    CodeSafetyError(
                        f"访问特殊属性: .{node.attr}",
                        node.lineno,
                        node.col_offset,
                    )
                )
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        """检查 with 语句（防止 with open(...) as f 绕过检查）。"""
        self._check_node_count()
        for item in node.items:
            if isinstance(item.context_expr, ast.Call):
                func_name = self._get_call_name(item.context_expr)
                if func_name == "open":
                    self._check_open_call(item.context_expr)
        self.generic_visit(node)


def check_code_safety(code: str) -> Tuple[bool, List[CodeSafetyError], List[CodeSafetyError]]:
    """对代码执行安全检查的便捷函数。

    Args:
        code: 待检查的 Python 源码。

    Returns:
        Tuple[bool, List[CodeSafetyError], List[CodeSafetyError]]:
            (是否通过, 错误列表, 警告列表)
    """
    checker = ASTChecker()
    return checker.check(code)
