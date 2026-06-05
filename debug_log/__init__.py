"""调试日志模块。

提供 DebugLogger，将关键日志写入文件并在 super_user 交互时推送摘要。
"""

from .logger import DebugLogger

__all__ = ["DebugLogger"]
