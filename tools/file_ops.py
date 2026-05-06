"""文件操作工具。

提供安全的文件读写能力，受权限系统控制。
- 工作区文件：Level 1+ 可读写
- 外部文件读取：Level 2+，需在白名单中
- 外部文件写入：Level 3+，需在白名单中
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

import os


class FileOperator:
    """文件操作器。

    封装文件读写操作，通过回调进行权限检查。
    """

    def __init__(
        self,
        workspace_dir: str,
        permission_checker: Callable[[str, str], Tuple[bool, str]],
    ) -> None:
        """初始化文件操作器。

        Args:
            workspace_dir: 工作区根目录。
            permission_checker: 权限检查回调 (path, mode) -> (allowed, reason)。
        """
        self._workspace_dir = os.path.realpath(workspace_dir)
        self._check = permission_checker

    def read_file(self, path: str) -> Dict[str, Any]:
        """读取文件内容。

        Args:
            path: 文件路径（相对于工作区或绝对路径）。

        Returns:
            Dict[str, Any]: {"success": bool, "content": str, "error": str}
        """
        real_path = self._resolve_path(path)

        allowed, reason = self._check(real_path, "read")
        if not allowed:
            return {"success": False, "content": "", "error": reason}

        try:
            with open(real_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"success": True, "content": content, "error": ""}
        except UnicodeDecodeError:
            try:
                with open(real_path, "r", encoding="latin-1") as f:
                    content = f.read()
                return {
                    "success": True,
                    "content": content,
                    "error": "警告: 文件非 UTF-8 编码，已用 latin-1 读取",
                }
            except Exception as e:
                return {"success": False, "content": "", "error": f"读取失败: {e}"}
        except Exception as e:
            return {"success": False, "content": "", "error": f"读取失败: {e}"}

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """写入文件内容。

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

        try:
            os.makedirs(os.path.dirname(real_path), exist_ok=True)
            with open(real_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "error": ""}
        except Exception as e:
            return {"success": False, "error": f"写入失败: {e}"}

    def list_files(self, path: str = "") -> Dict[str, Any]:
        """列出目录内容。

        Args:
            path: 目录路径（默认为工作区根目录）。

        Returns:
            Dict[str, Any]: {"success": bool, "files": list, "error": str}
        """
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
                items.append(
                    {
                        "name": entry,
                        "is_dir": is_dir,
                        "size": size,
                    }
                )
            return {"success": True, "files": items, "error": ""}
        except Exception as e:
            return {"success": False, "files": [], "error": f"列出失败: {e}"}

    def delete_file(self, path: str) -> Dict[str, Any]:
        """删除文件。

        Args:
            path: 文件路径。

        Returns:
            Dict[str, Any]: {"success": bool, "error": str}
        """
        real_path = self._resolve_path(path)

        allowed, reason = self._check(real_path, "write")
        if not allowed:
            return {"success": False, "error": reason}

        try:
            if os.path.isdir(real_path):
                return {"success": False, "error": "不能删除目录，请逐个删除文件"}
            os.remove(real_path)
            return {"success": True, "error": ""}
        except FileNotFoundError:
            return {"success": False, "error": "文件不存在"}
        except Exception as e:
            return {"success": False, "error": f"删除失败: {e}"}

    def file_exists(self, path: str) -> Dict[str, Any]:
        """检查文件是否存在。

        Args:
            path: 文件路径。

        Returns:
            Dict[str, Any]: {"success": bool, "exists": bool}
        """
        real_path = self._resolve_path(path)
        exists = os.path.exists(real_path)
        return {"success": True, "exists": exists}

    def _resolve_path(self, path: str) -> str:
        """解析路径。

        相对路径相对于工作区根目录。

        Args:
            path: 原始路径。

        Returns:
            str: 解析后的绝对路径。
        """
        expanded = os.path.expanduser(path)
        if os.path.isabs(expanded):
            return os.path.realpath(expanded)
        return os.path.realpath(os.path.join(self._workspace_dir, expanded))
