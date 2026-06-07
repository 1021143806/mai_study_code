"""多工作区管理器。

支持的工作区类型：
- local-sandbox: 本地沙箱（当前用户 a1）
- local-root: 本地 root（通过 su/sudo）
- ssh: 远程 SSH（通过 sshpass + ssh）

每个工作区提供统一的文件操作和执行接口。
"""

from typing import Any, Dict, List, Optional, Tuple

import json
import os
import re
import subprocess
import time


# ============================================================
# 工具函数（必须在类定义之前）
# ============================================================
# 工具函数（必须在类定义之前）
# ============================================================

def shlex_quote(s: str) -> str:
    """安全的 shell 引用。"""
    if not s:
        return "''"
    if re.match(r'^[a-zA-Z0-9_./@:,=+\-]+$', s):
        return s
    return "'" + s.replace("'", "'\\''") + "'"


# ============================================================
# 工作区基类
# ============================================================
# 工作区配置
# ============================================================

WORKSPACE_CONFIG_FILE = None  # 由插件 on_load 时设置

def set_config_path(path: str) -> None:
    """设置工作区配置文件路径。"""
    global WORKSPACE_CONFIG_FILE
    WORKSPACE_CONFIG_FILE = path


# ============================================================
# 工作区基类
# ============================================================

class Workspace:
    """工作区基类。"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.name: str = config.get("name", "未命名")
        self.ws_type: str = config.get("type", "local-sandbox")
        self.config = config

    def list_files(self, path: str = "") -> Dict[str, Any]:
        """列出目录内容。"""
        raise NotImplementedError

    def read_file(self, path: str) -> Dict[str, Any]:
        """读取文件内容。"""
        raise NotImplementedError

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """写入文件。"""
        raise NotImplementedError

    def execute(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """执行命令。"""
        raise NotImplementedError

    def test_connection(self) -> Tuple[bool, str]:
        """测试连接是否可用。"""
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:
        """导出配置（不含密码）。"""
        d = dict(self.config)
        d.pop("password", None)
        return d


# ============================================================
# 本地沙箱工作区（a1 用户）
# ============================================================

class LocalSandboxWorkspace(Workspace):
    """本地沙箱工作区。
    
    以当前用户（a1）身份操作，限制在配置的根目录内。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        self.root: str = config.get("path", os.path.expanduser("~"))
        os.makedirs(self.root, exist_ok=True)

    def _resolve(self, path: str) -> str:
        if not path or path == "." or path == "/":
            return self.root
        joined = os.path.join(self.root, path)
        real = os.path.realpath(joined)
        if not real.startswith(os.path.realpath(self.root)):
            return self.root  # 安全限制，防止路径逃逸
        return real

    def list_files(self, path: str = "") -> Dict[str, Any]:
        target = self._resolve(path)
        try:
            entries = sorted(os.listdir(target))
            tree = []
            ignored = {".git", "__pycache__", ".pytest_cache", "node_modules", ".npm_cache"}
            for name in entries:
                if name.startswith(".") and name not in (".gitignore", ".env"):
                    continue
                if name in ignored:
                    continue
                full = os.path.join(target, name)
                try:
                    rel = os.path.relpath(full, self.root)
                except ValueError:
                    rel = name
                node = {"name": name, "path": rel, "is_dir": os.path.isdir(full)}
                if node["is_dir"]:
                    node["children"] = self._build_subtree(full)
                tree.append(node)
            return {"success": True, "tree": tree, "root": path or "."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _build_subtree(self, dir_path: str, depth: int = 0) -> List[Dict]:
        if depth > 3:
            return []
        entries = []
        try:
            for name in sorted(os.listdir(dir_path)):
                if name.startswith("."):
                    continue
                full = os.path.join(dir_path, name)
                node = {"name": name, "is_dir": os.path.isdir(full)}
                if node["is_dir"]:
                    node["children"] = self._build_subtree(full, depth + 1)
                entries.append(node)
        except PermissionError:
            pass
        return entries

    def read_file(self, path: str) -> Dict[str, Any]:
        target = self._resolve(path)
        if not os.path.isfile(target):
            return {"success": False, "error": "文件不存在"}
        try:
            with open(target, "r", encoding="utf-8") as f:
                content = f.read()
            return {"success": True, "content": content, "path": path}
        except UnicodeDecodeError:
            try:
                with open(target, "r", encoding="latin-1") as f:
                    content = f.read()
                return {"success": True, "content": content, "path": path}
            except Exception as e:
                return {"success": False, "error": f"读取失败: {e}"}
        except Exception as e:
            return {"success": False, "error": f"读取失败: {e}"}

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        target = self._resolve(path)
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": f"写入失败: {e}"}

    def execute(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        start = time.monotonic()
        try:
            proc = subprocess.Popen(
                command, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                cwd=self.root, executable="/bin/bash",
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            elapsed = (time.monotonic() - start) * 1000
            return {
                "success": proc.returncode == 0,
                "stdout": (stdout or "")[:10000],
                "stderr": (stderr or "")[:10000],
                "returncode": proc.returncode,
                "execution_time_ms": round(elapsed, 1),
            }
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return {"success": False, "error": f"执行超时 ({timeout}s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def test_connection(self) -> Tuple[bool, str]:
        try:
            os.listdir(self.root)
            return True, "可用"
        except Exception as e:
            return False, str(e)


# ============================================================
# 本地 Root 工作区
# ============================================================

class LocalRootWorkspace(LocalSandboxWorkspace):
    """本地 root 工作区。
    
    通过 su 以 root 身份执行操作，root 目录为 /。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        self.root = "/"
        self._su_password: str = config.get("password", "")

    def _su_cmd(self, cmd: str) -> str:
        """包装为 su 命令。"""
        if self._su_password:
            # 通过管道传密码
            return f'echo "{self._su_password}" | su -c {shlex_quote(cmd)}'
        return f"su -c {shlex_quote(cmd)}"

    def _resolve(self, path: str) -> str:
        if not path or path == ".":
            return "/"
        if path.startswith("/"):
            return os.path.realpath(path)
        return os.path.realpath("/" + path)

    def execute(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        start = time.monotonic()
        su_cmd = self._su_cmd(command)
        try:
            proc = subprocess.Popen(
                su_cmd, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                executable="/bin/bash",
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            elapsed = (time.monotonic() - start) * 1000
            return {
                "success": proc.returncode == 0,
                "stdout": (stdout or "")[:10000],
                "stderr": (stderr or "")[:10000],
                "returncode": proc.returncode,
                "execution_time_ms": round(elapsed, 1),
            }
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return {"success": False, "error": f"执行超时 ({timeout}s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def test_connection(self) -> Tuple[bool, str]:
        result = self.execute("whoami", timeout=5)
        if result.get("success"):
            return True, f"以 {result.get('stdout','').strip()} 身份连接"
        return False, result.get("error", "连接失败")


# ============================================================
# SSH 远程工作区
# ============================================================

class SSHWorkspace(Workspace):
    """SSH 远程工作区。
    
    通过 sshpass + ssh 连接远程服务器，支持密码认证。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        self.host: str = config.get("host", "")
        self.port: int = config.get("port", 22)
        self.username: str = config.get("username", "root")
        self.password: str = config.get("password", "")
        self.root: str = config.get("path", "/root")

    def _ssh_opts(self) -> str:
        return (
            f"-o StrictHostKeyChecking=no "
            f"-o UserKnownHostsFile=/dev/null "
            f"-o ConnectTimeout=10 "
            f"-p {self.port}"
        )

    def _ssh_exec(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """通过 SSH 执行远程命令。"""
        ssh_cmd = (
            f'sshpass -e ssh {self._ssh_opts()} '
            f'{shlex_quote(self.username)}@{shlex_quote(self.host)} '
            f'{shlex_quote(command)}'
        )
        env = os.environ.copy()
        env["SSHPASS"] = self.password

        start = time.monotonic()
        try:
            proc = subprocess.Popen(
                ssh_cmd, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, env=env,
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            elapsed = (time.monotonic() - start) * 1000
            return {
                "success": proc.returncode == 0,
                "stdout": (stdout or "")[:10000],
                "stderr": (stderr or "")[:10000],
                "returncode": proc.returncode,
                "execution_time_ms": round(elapsed, 1),
            }
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return {"success": False, "error": f"执行超时 ({timeout}s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_files(self, path: str = "") -> Dict[str, Any]:
        target = path if path else self.root
        # 用 find -printf 一次性获取名称和类型
        result = self._ssh_exec(
            f'find {shlex_quote(target)} -maxdepth 1 ! -name ".*" '
            f'-printf "%f|%y\\n" 2>/dev/null | sort',
            timeout=10
        )
        if result.get("success") and result.get("stdout"):
            tree = []
            for line in result["stdout"].strip().split("\n"):
                line = line.strip()
                if not line or "|" not in line:
                    continue
                name, ftype = line.rsplit("|", 1)
                if not name or name == target.strip("/"):
                    continue
                tree.append({"name": name, "is_dir": ftype == "d"})
            return {"success": True, "tree": tree, "root": target}
        return {"success": True, "tree": [], "root": target}
        if result.get("success") and result.get("stdout"):
            try:
                tree = json.loads(result["stdout"].strip())
                return {"success": True, "tree": tree, "root": target}
            except json.JSONDecodeError:
                pass
        # 降级
        return {"success": True, "tree": [], "root": target}

    def read_file(self, path: str) -> Dict[str, Any]:
        # 使用 cat 通过 SSH 读取
        result = self._ssh_exec(f'cat {shlex_quote(path)}', timeout=10)
        if result.get("success"):
            return {"success": True, "content": result.get("stdout", ""), "path": path}
        return {"success": False, "error": result.get("stderr") or result.get("error", "读取失败")}

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        # 使用 echo + base64 通过 SSH 写入（避免转义问题）
        import base64
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        cmd = f'echo {encoded} | base64 -d > {shlex_quote(path)}'
        result = self._ssh_exec(cmd, timeout=10)
        return {"success": result.get("success", False), "path": path}

    def execute(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        return self._ssh_exec(command, timeout)

    def test_connection(self) -> Tuple[bool, str]:
        result = self._ssh_exec("whoami", timeout=10)
        if result.get("success"):
            return True, f"{result.get('stdout','').strip()}@{self.host}"
        err = result.get("stderr") or result.get("error", "连接失败")
        return False, err

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.config)
        d.pop("password", None)
        return d


# ============================================================
# 工作区工厂
# ============================================================

def create_workspace(config: Dict[str, Any]) -> Workspace:
    """根据配置创建工作区实例。"""
    ws_type = config.get("type", "local-sandbox")
    if ws_type == "local-root":
        return LocalRootWorkspace(config)
    elif ws_type == "ssh":
        return SSHWorkspace(config)
    else:  # local-sandbox 默认
        return LocalSandboxWorkspace(config)


# ============================================================
# WorkspaceManager
# ============================================================

class WorkspaceManager:
    """工作区管理器，管理多个工作区的配置和生命周期。"""

    def __init__(self, config_path: str, default_workspace_dir: str = "") -> None:
        self._config_path = config_path
        self._default_workspace_dir = default_workspace_dir or os.path.expanduser("~a1")
        self._workspaces: Dict[str, Workspace] = {}
        self._active: str = ""
        self._load_config()

    def _load_config(self) -> None:
        """从 JSON 文件加载工作区配置。"""
        if not os.path.isfile(self._config_path):
            # 默认配置：沙箱工作台 + root
            defaults = [
                {
                    "name": "沙箱工作台",
                    "type": "local-sandbox",
                    "path": self._default_workspace_dir,
                },
                {
                    "name": "本地 Root",
                    "type": "local-root",
                    "password": "",
                },
            ]
            self._workspaces = {}
            for cfg in defaults:
                ws = create_workspace(cfg)
                self._workspaces[ws.name] = ws
            self._active = defaults[0]["name"]
            self._save_config()
            return

        with open(self._config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._workspaces = {}
        for cfg in data.get("workspaces", []):
            ws = create_workspace(cfg)
            self._workspaces[ws.name] = ws
        self._active = data.get("active", "")

    def _save_config(self) -> None:
        """保存工作区配置到 JSON 文件。"""
        data = {
            "active": self._active,
            "workspaces": [ws.to_dict() for ws in self._workspaces.values()],
        }
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --- 查询 ---

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """列出所有工作区配置（不含密码）。"""
        return [ws.to_dict() for ws in self._workspaces.values()]

    def get_active(self) -> str:
        """获取当前工作区名称。"""
        if self._active and self._active in self._workspaces:
            return self._active
        if self._workspaces:
            return next(iter(self._workspaces.keys()))
        return ""

    def get_workspace(self, name: str) -> Optional[Workspace]:
        """获取指定名称的工作区实例。"""
        return self._workspaces.get(name)

    def get_active_workspace(self) -> Optional[Workspace]:
        """获取当前工作区实例。"""
        name = self.get_active()
        return self._workspaces.get(name) if name else None

    # --- 管理 ---

    def add_or_update(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """添加或更新工作区。"""
        name = config.get("name", "").strip()
        if not name:
            return False, "名称不能为空"
        ws = create_workspace(config)
        self._workspaces[name] = ws
        self._save_config()
        return True, "已保存"

    def remove(self, name: str) -> Tuple[bool, str]:
        """删除工作区。"""
        if name not in self._workspaces:
            return False, "工作区不存在"
        del self._workspaces[name]
        if self._active == name:
            self._active = ""
        self._save_config()
        return True, "已删除"

    def set_active(self, name: str) -> Tuple[bool, str]:
        """切换当前工作区。"""
        if name not in self._workspaces:
            return False, "工作区不存在"
        self._active = name
        self._save_config()
        return True, f"已切换到 {name}"

    def test_connection(self, name: str) -> Dict[str, Any]:
        """测试工作区连接。"""
        ws = self._workspaces.get(name)
        if not ws:
            return {"success": False, "error": "工作区不存在"}
        ok, msg = ws.test_connection()
        return {"success": ok, "message": msg}

    # --- 文件操作代理 ---

    def list_files(self, path: str = "", workspace: str = "") -> Dict[str, Any]:
        ws = self._workspaces.get(workspace or self.get_active())
        if not ws:
            return {"success": False, "error": "工作区不存在"}
        return ws.list_files(path)

    def read_file(self, path: str, workspace: str = "") -> Dict[str, Any]:
        ws = self._workspaces.get(workspace or self.get_active())
        if not ws:
            return {"success": False, "error": "工作区不存在"}
        return ws.read_file(path)

    def write_file(self, path: str, content: str, workspace: str = "") -> Dict[str, Any]:
        ws = self._workspaces.get(workspace or self.get_active())
        if not ws:
            return {"success": False, "error": "工作区不存在"}
        return ws.write_file(path, content)

    def execute(self, command: str, workspace: str = "", timeout: int = 30) -> Dict[str, Any]:
        ws = self._workspaces.get(workspace or self.get_active())
        if not ws:
            return {"success": False, "error": "工作区不存在"}
        return ws.execute(command, timeout)
