"""沙箱安全限制配置。

定义白名单 builtins、允许的模块、禁止的模块/函数，
以及资源限制参数。
"""

from typing import AbstractSet, Dict

# ============================================================
# 安全 builtins 白名单
# ============================================================
SAFE_BUILTINS: AbstractSet[str] = frozenset(
    {
        # 基本类型与转换
        "abs",
        "all",
        "any",
        "ascii",
        "bin",
        "bool",
        "bytes",
        "bytearray",
        "chr",
        "complex",
        "dict",
        "divmod",
        "enumerate",
        "filter",
        "float",
        "format",
        "frozenset",
        "hash",
        "hex",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "map",
        "max",
        "min",
        "next",
        "oct",
        "ord",
        "pow",
        "print",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "tuple",
        "type",
        "zip",
        # 对象操作
        "hasattr",
        "getattr",
        "id",
        "object",
        "property",
        "staticmethod",
        "classmethod",
        "super",
        # 异常
        "Exception",
        "ValueError",
        "TypeError",
        "KeyError",
        "IndexError",
        "StopIteration",
        "RuntimeError",
        "AssertionError",
        "AttributeError",
        "ImportError",
        "NotImplementedError",
        "ZeroDivisionError",
        # 其他安全函数
        "callable",
        "dir",
        "help",
        "memoryview",
    }
)

# ============================================================
# 禁止的 import 模块（即使尝试 import 也会被拦截）
# ============================================================
FORBIDDEN_MODULES: AbstractSet[str] = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "shutil",
        "socket",
        "requests",
        "urllib",
        "urllib2",
        "urllib.request",
        "urllib.error",
        "urllib.parse",
        "http",
        "http.client",
        "http.server",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        "telnetlib",
        "ctypes",
        "multiprocessing",
        "threading",
        "concurrent.futures",
        "asyncio",
        "signal",
        "atexit",
        "code",
        "codeop",
        "codecs",
        "importlib",
        "pkgutil",
        "pickle",
        "marshal",
        "shelve",
        "pathlib",
        "glob",
        "fnmatch",
        "io",
        "tempfile",
        "webbrowser",
        "antigravity",
        "turtle",
        "tkinter",
        "curses",
        "pty",
        "pdb",
        "traceback",
        "inspect",
        "gc",
        "sysconfig",
        "platform",
        "getpass",
        "logging",
        "warnings",
    }
)

# ============================================================
# 允许的 import 模块白名单（纯计算，无副作用）
# ============================================================
ALLOWED_MODULES: AbstractSet[str] = frozenset(
    {
        # 数学
        "math",
        "cmath",
        "decimal",
        "fractions",
        "statistics",
        "random",
        # 数据结构
        "itertools",
        "functools",
        "collections",
        "heapq",
        "bisect",
        "array",
        # 时间（只读）
        "datetime",
        "calendar",
        "time",
        # 数据格式
        "json",
        "csv",
        # 字符串
        "re",
        "string",
        "textwrap",
        "difflib",
        # 类型
        "typing",
        "dataclasses",
        "enum",
        "numbers",
        # 工具
        "copy",
        "pprint",
        "operator",
        "contextlib",
        # 编码
        "hashlib",
        "base64",
        "binascii",
        "html",
        "xml.etree.ElementTree",
        # 测试
        "unittest",
        "doctest",
        # 函数式
        "functools",
    }
)

# ============================================================
# 禁止的内置函数/关键字（AST 扫描用）
# ============================================================
FORBIDDEN_BUILTINS: AbstractSet[str] = frozenset(
    {
        "__import__",
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
    }
)

# ============================================================
# 资源限制参数
# ============================================================
RESOURCE_LIMITS: Dict[str, int] = {
    "max_memory_mb": 128,  # 最大内存 (MB)
    "max_cpu_time_sec": 10,  # 最大 CPU 时间 (秒)
    "max_wall_time_sec": 15,  # 最大墙上时间 (秒)
    "max_output_chars": 10000,  # 最大输出字符数
    "max_file_size_mb": 10,  # 最大文件写入大小 (MB)
}

# ============================================================
# 沙箱工作目录
# ============================================================
SANDBOX_WORK_DIR: str = "/tmp/mai_code_sandbox"
