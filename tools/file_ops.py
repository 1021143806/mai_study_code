"""文件操作工具。

提供安全的文件读写能力，受权限系统控制。
- 工作区文件：Level 1+ 可读写
- 外部文件读取：Level 2+，需在白名单中
- 外部文件写入：Level 3+，需在白名单中
- 行数限制：按权限等级阶梯式限制
- Diff 修改：精确替换，自动备份
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

import os
import re
import shutil
import time


class FileOperator:
    """文件操作器。

    封装文件读写操作，通过回调进行权限检查。
    支持行数限制、文件搜索、diff 修改、备份回滚。
    """

    # 默认行数限制（按权限等级）
    DEFAULT_MAX_LINES: Dict[str, int] = {
        "0": 200,
        "1": 200,
        "2": 500,
        "3": 500,
        "4": 1000,
        "root": 1000,
    }

    def __init__(
        self,
        workspace_dir: str,
        permission_checker: Callable[[str, str], Tuple[bool, str]],
        max_lines_map: Optional[Dict[str, int]] = None,
        max_history_backups: int = 20,
    ) -> None:
        """初始化文件操作器。

        Args:
            workspace_dir: 工作区根目录。
            permission_checker: 权限检查回调 (path, mode) -> (allowed, reason)。
            max_lines_map: 按权限等级的行数限制映射。
            max_history_backups: 最大历史备份数量。
        """
        self._workspace_dir = os.path.realpath(workspace_dir)
        self._check = permission_checker
        self._max_lines_map = max_lines_map or self.DEFAULT_MAX_LINES
        self._max_history_backups = max_history_backups
        self._history_dir = os.path.join(workspace_dir, ".history")
        os.makedirs(self._history_dir, exist_ok=True)

    # ================================================================
    # 文件读取（带行数限制）
    # ================================================================

    def read_file(self, path: str, max_lines: Optional[int] = None) -> Dict[str, Any]:
        """读取文件内容（带行数限制）。

        Args:
            path: 文件路径。
            max_lines: 最大行数限制，默认根据权限等级自动确定。

        Returns:
            Dict[str, Any]: {"success", "content", "total_lines", "truncated", "error"}
        """
        real_path = self._resolve_path(path)

        allowed, reason = self._check(real_path, "read")
        if not allowed:
            return {"success": False, "content": "", "total_lines": 0, "truncated": False, "error": reason}

        try:
            with open(real_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            try:
                with open(real_path, "r", encoding="latin-1") as f:
                    lines = f.readlines()
            except Exception as e:
                return {"success": False, "content": "", "total_lines": 0, "truncated": False, "error": f"读取失败: {e}"}
        except Exception as e:
            return {"success": False, "content": "", "total_lines": 0, "truncated": False, "error": f"读取失败: {e}"}

        total_lines = len(lines)
        limit = max_lines if max_lines is not None else self._get_max_lines()

        if total_lines <= limit:
            return {
                "success": True,
                "content": "".join(lines),
                "total_lines": total_lines,
                "truncated": False,
                "error": "",
            }

        # 超出限制：返回前 N 行 + 提示
        truncated_content = "".join(lines[:limit])
        hint = (
            f"\n\n--- 文件共 {total_lines} 行，已显示前 {limit} 行 ---\n"
            f"使用 search_in_file 搜索特定内容，或使用 read_file_lines 指定行范围读取。"
        )
        return {
            "success": True,
            "content": truncated_content + hint,
            "total_lines": total_lines,
            "truncated": True,
            "error": "",
        }

    def read_file_lines(
        self, path: str, start_line: int, end_line: int
    ) -> Dict[str, Any]:
        """读取文件的指定行范围。

        Args:
            path: 文件路径。
            start_line: 起始行号（1-based）。
            end_line: 结束行号（1-based，包含）。

        Returns:
            Dict[str, Any]: {"success", "content", "total_lines", "error"}
        """
        real_path = self._resolve_path(path)

        allowed, reason = self._check(real_path, "read")
        if not allowed:
            return {"success": False, "content": "", "total_lines": 0, "error": reason}

        try:
            with open(real_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            try:
                with open(real_path, "r", encoding="latin-1") as f:
                    lines = f.readlines()
            except Exception as e:
                return {"success": False, "content": "", "total_lines": 0, "error": f"读取失败: {e}"}
        except Exception as e:
            return {"success": False, "content": "", "total_lines": 0, "error": f"读取失败: {e}"}

        total_lines = len(lines)
        start = max(0, start_line - 1)
        end = min(total_lines, end_line)

        if start >= total_lines:
            return {"success": False, "content": "", "total_lines": total_lines, "error": f"起始行 {start_line} 超出文件总行数 {total_lines}"}

        selected = lines[start:end]
        # 添加行号
        numbered = []
        for i, line in enumerate(selected, start=start + 1):
            numbered.append(f"{i:6d}| {line}")

        return {
            "success": True,
            "content": "".join(numbered),
            "total_lines": total_lines,
            "error": "",
        }

    def search_in_file(
        self, path: str, pattern: str, context_lines: int = 2
    ) -> Dict[str, Any]:
        """在文件中搜索匹配行（grep 功能）。

        Args:
            path: 文件路径。
            pattern: 搜索模式（支持正则表达式）。
            context_lines: 匹配行前后的上下文行数。

        Returns:
            Dict[str, Any]: {"success", "matches", "total_lines", "error"}
        """
        real_path = self._resolve_path(path)

        allowed, reason = self._check(real_path, "read")
        if not allowed:
            return {"success": False, "matches": [], "total_lines": 0, "error": reason}

        try:
            with open(real_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            try:
                with open(real_path, "r", encoding="latin-1") as f:
                    lines = f.readlines()
            except Exception as e:
                return {"success": False, "matches": [], "total_lines": 0, "error": f"搜索失败: {e}"}
        except Exception as e:
            return {"success": False, "matches": [], "total_lines": 0, "error": f"搜索失败: {e}"}

        total_lines = len(lines)
        matches = []

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return {"success": False, "matches": [], "total_lines": total_lines, "error": f"无效的正则表达式: {e}"}

        for i, line in enumerate(lines):
            if regex.search(line):
                ctx_start = max(0, i - context_lines)
                ctx_end = min(total_lines, i + context_lines + 1)
                context = []
                for j in range(ctx_start, ctx_end):
                    prefix = ">>>" if j == i else "   "
                    context.append(f"{prefix} {j+1:6d}| {lines[j].rstrip()}")
                matches.append(
                    {
                        "line_number": i + 1,
                        "line_content": line.rstrip(),
                        "context": "\n".join(context),
                    }
                )

        return {
            "success": True,
            "matches": matches,
            "total_lines": total_lines,
            "error": "",
        }

    # ================================================================
    # 文件写入
    # ================================================================

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """写入文件内容（创建新文件或完全覆盖）。

        Args:
            path: 文件路径。
            content: 要写入的内容。

        Returns:
            Dict[str, Any]: {"success": bool, "error": str}
        """
        real_path = self._resolve_path(path)

        allowed, reason = self._check(real_path, "write")
        if not allowed:
            return {"success": False, "error": reason}

        # 如果文件已存在，先备份
        if os.path.exists(real_path):
            self._backup_file(real_path)

        try:
            os.makedirs(os.path.dirname(real_path), exist_ok=True)
            with open(real_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "error": ""}
        except Exception as e:
            return {"success": False, "error": f"写入失败: {e}"}

    # ================================================================
    # Diff 修改
    # ================================================================

    def apply_diff(self, path: str, old_content: str, new_content: str) -> Dict[str, Any]:
        """使用 diff 方式精确修改文件。

        在文件中查找 old_content 并替换为 new_content。
        要求 old_content 在文件中唯一存在，防止误改多处。

        Args:
            path: 文件路径。
            old_content: 要替换的原文（必须精确匹配）。
            new_content: 替换后的新内容。

        Returns:
            Dict[str, Any]: {"success", "error", "occurrences"}
        """
        real_path = self._resolve_path(path)

        allowed, reason = self._check(real_path, "write")
        if not allowed:
            return {"success": False, "error": reason, "occurrences": 0}

        if not os.path.exists(real_path):
            return {"success": False, "error": "文件不存在", "occurrences": 0}

        try:
            with open(real_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return {"success": False, "error": f"读取文件失败: {e}", "occurrences": 0}

        # 统计 old_content 出现次数
        occurrences = content.count(old_content)

        if occurrences == 0:
            return {
                "success": False,
                "error": "未找到匹配内容，文件可能已被修改。请重新读取文件后再试。",
                "occurrences": 0,
            }

        if occurrences > 1:
            return {
                "success": False,
                "error": f"匹配到 {occurrences} 处相同内容，请提供更多上下文使匹配唯一。",
                "occurrences": occurrences,
            }

        # 唯一匹配：执行替换
        self._backup_file(real_path)

        new_file_content = content.replace(old_content, new_content, 1)

        try:
            with open(real_path, "w", encoding="utf-8") as f:
                f.write(new_file_content)
            return {"success": True, "error": "", "occurrences": 1}
        except Exception as e:
            return {"success": False, "error": f"写入失败: {e}", "occurrences": 1}

    # ================================================================
    # 备份与回滚
    # ================================================================

    def _backup_file(self, real_path: str) -> str:
        """备份文件到历史目录。

        Args:
            real_path: 文件绝对路径。

        Returns:
            str: 备份文件路径。
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        basename = os.path.basename(real_path)
        backup_name = f"{basename}.{timestamp}.bak"
        backup_path = os.path.join(self._history_dir, backup_name)

        try:
            shutil.copy2(real_path, backup_path)
        except Exception:
            pass

        # 清理旧备份
        self._cleanup_old_backups(basename)

        return backup_path

    def _cleanup_old_backups(self, basename: str) -> None:
        """清理超出数量限制的旧备份。

        Args:
            basename: 原始文件名。
        """
        try:
            backups = sorted(
                [f for f in os.listdir(self._history_dir) if f.startswith(basename)],
                reverse=True,
            )
            for old in backups[self._max_history_backups:]:
                os.remove(os.path.join(self._history_dir, old))
        except Exception:
            pass

    def list_backups(self, path: str) -> Dict[str, Any]:
        """列出文件的历史备份。

        Args:
            path: 原始文件路径。

        Returns:
            Dict[str, Any]: {"success", "backups", "error"}
        """
        basename = os.path.basename(path)
        try:
            backups = sorted(
                [
                    {
                        "filename": f,
                        "timestamp": f.replace(f"{basename}.", "").replace(".bak", ""),
                    }
                    for f in os.listdir(self._history_dir)
                    if f.startswith(basename) and f.endswith(".bak")
                ],
                key=lambda x: x["timestamp"],
                reverse=True,
            )
            return {"success": True, "backups": backups, "error": ""}
        except Exception as e:
            return {"success": False, "backups": [], "error": str(e)}

    def rollback_file(self, path: str, timestamp: str) -> Dict[str, Any]:
        """回滚文件到指定备份。

        Args:
            path: 原始文件路径。
            timestamp: 备份时间戳（如 "20260507_143000"）。

        Returns:
            Dict[str, Any]: {"success", "error"}
        """
        real_path = self._resolve_path(path)

        allowed, reason = self._check(real_path, "write")
        if not allowed:
            return {"success": False, "error": reason}

        basename = os.path.basename(real_path)
        backup_name = f"{basename}.{timestamp}.bak"
        backup_path = os.path.join(self._history_dir, backup_name)

        if not os.path.exists(backup_path):
            return {"success": False, "error": f"备份不存在: {timestamp}"}

        try:
            # 回滚前也备份当前版本
            if os.path.exists(real_path):
                self._backup_file(real_path)
            shutil.copy2(backup_path, real_path)
            return {"success": True, "error": ""}
        except Exception as e:
            return {"success": False, "error": f"回滚失败: {e}"}

    # ================================================================
    # 其他操作
    # ================================================================

    def list_files(self, path: str = "") -> Dict[str, Any]:
        """列出目录内容。"""
        real_path = self._resolve_path(path) if path else self._workspace_dir

        allowed, reason = self._check(real_path, "read")
        if not allowed:
            return {"success": False, "files": [], "error": reason}

        try:
            items = []
            for entry in sorted(os.listdir(real_path)):
                entry_path = os.path.join(real_path, entry)
                is_dir = os.path.isdir(entry_path)
                size = 0 if is_dir else os.path.getsize(entry_path)
                items.append({"name": entry, "is_dir": is_dir, "size": size})
            return {"success": True, "files": items, "error": ""}
        except Exception as e:
            return {"success": False, "files": [], "error": f"列出失败: {e}"}

    def delete_file(self, path: str) -> Dict[str, Any]:
        """删除文件。"""
        real_path = self._resolve_path(path)

        allowed, reason = self._check(real_path, "write")
        if not allowed:
            return {"success": False, "error": reason}

        try:
            if os.path.isdir(real_path):
                return {"success": False, "error": "不能删除目录"}
            if os.path.exists(real_path):
                self._backup_file(real_path)
            os.remove(real_path)
            return {"success": True, "error": ""}
        except FileNotFoundError:
            return {"success": False, "error": "文件不存在"}
        except Exception as e:
            return {"success": False, "error": f"删除失败: {e}"}

    def file_exists(self, path: str) -> Dict[str, Any]:
        """检查文件是否存在。"""
        real_path = self._resolve_path(path)
        return {"success": True, "exists": os.path.exists(real_path)}

    # ================================================================
    # 内部方法
    # ================================================================

    def _get_max_lines(self) -> int:
        """获取当前权限等级的最大行数限制。"""
        # 尝试从权限检查器获取当前等级（通过回调间接获取）
        # 默认返回最宽松的限制
        return max(self._max_lines_map.values()) if self._max_lines_map else 1000

    def _resolve_path(self, path: str) -> str:
        """解析路径。"""
        expanded = os.path.expanduser(path)
        if os.path.isabs(expanded):
            return os.path.realpath(expanded)
        return os.path.realpath(os.path.join(self._workspace_dir, expanded))
