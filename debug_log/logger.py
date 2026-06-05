"""调试日志记录器。

将关键日志写入文件持久化，并维护内存队列供交互推送和 Web 查看。
"""

from typing import Any, Dict, List, Optional

import logging
import os
import time
from collections import deque
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("plugin.maibot-team.mai-study-code.debug_log")

# 日志级别优先级
_LEVEL_ORDER = {"debug": 0, "info": 1, "warning": 2, "error": 3}

# 日志类别图标
_CATEGORY_ICONS = {
    "startup": "✅",
    "operation": "🔧",
    "cache": "💾",
    "error": "❌",
    "knowledge": "📝",
    "emergency": "🛑",
    "permission": "⚠️",
}


class DebugLogger:
    """调试日志记录器。

    功能：
    - 将关键日志写入文件（带轮转）
    - 维护内存队列供 Web API 查看
    - 维护待推送队列供交互时推送给 super_user
    """

    # 北京时间时区
    _CST = timezone(timedelta(hours=8))

    def __init__(
        self,
        log_path: str,
        max_file_size_mb: int = 5,
        backup_count: int = 2,
        push_level: str = "info",
        max_memory_entries: int = 500,
    ) -> None:
        """初始化调试日志记录器。

        Args:
            log_path: 日志文件绝对路径。
            max_file_size_mb: 日志文件最大大小 (MB)。
            backup_count: 保留的轮转文件数。
            push_level: 推送最低级别 (info/warning/error)。
            max_memory_entries: 内存中保留的最大条目数。
        """
        self._log_path = log_path
        self._max_file_size = max_file_size_mb * 1024 * 1024
        self._backup_count = backup_count
        self._push_level = push_level
        self._push_min_order = _LEVEL_ORDER.get(push_level, 1)

        # 内存队列（供 Web API 查看）
        self._entries: deque = deque(maxlen=max_memory_entries)
        # 待推送队列（交互时推送后清空）
        self._pending: deque = deque(maxlen=200)

        # 确保日志目录存在
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        logger.info(f"调试日志已启用: {log_path} (max={max_file_size_mb}MB, level={push_level})")

    # ================================================================
    # 公共 API
    # ================================================================

    def log(
        self,
        level: str,
        category: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录一条调试日志。

        Args:
            level: 日志级别 (info/warning/error)。
            category: 日志类别 (startup/operation/cache/error/knowledge/emergency/permission)。
            message: 简短描述。
            details: 可选的详细数据字典。
        """
        now = time.time()
        entry = {
            "timestamp": now,
            "time_str": self._format_time(now),
            "level": level,
            "category": category,
            "message": message,
            "details": details or {},
        }

        # 写入内存队列
        self._entries.append(entry)

        # 判断是否需要加入待推送队列
        level_order = _LEVEL_ORDER.get(level, 1)
        if level_order >= self._push_min_order:
            self._pending.append(entry)

        # 写入文件
        self._write_to_file(entry)

    def get_recent(self, count: int = 50) -> List[Dict[str, Any]]:
        """获取最近 N 条日志（供 Web API）。

        Args:
            count: 返回条数。

        Returns:
            List[Dict]: 日志条目列表。
        """
        entries = list(self._entries)
        return entries[-count:]

    def get_pending_summary(self, max_lines: int = 10) -> Optional[str]:
        """获取待推送摘要并清空待推送队列。

        Args:
            max_lines: 最大行数。

        Returns:
            Optional[str]: 格式化的摘要文本，无待推送内容时返回 None。
        """
        if not self._pending:
            return None

        # 取出所有待推送条目
        entries = []
        while self._pending:
            entries.append(self._pending.popleft())

        # 只取最近 max_lines 条
        if len(entries) > max_lines:
            entries = entries[-max_lines:]

        # 构建摘要
        lines = ["📋 [mai_study 调试日志]"]
        for e in entries:
            icon = _CATEGORY_ICONS.get(e["category"], "ℹ️")
            time_short = e["time_str"][-8:] if len(e["time_str"]) > 8 else e["time_str"]
            lines.append(f"{icon} [{time_short}] {e['message']}")

        return "\n".join(lines)

    # ================================================================
    # 便捷方法
    # ================================================================

    def startup(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """记录启动日志。"""
        self.log("info", "startup", message, details)

    def operation(
        self,
        success: bool,
        tool_name: str,
        detail: str,
        elapsed_ms: float = 0,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录操作日志。

        Args:
            success: 是否成功。
            tool_name: 工具名称 (execute_python/execute_shell/read_file/write_file)。
            detail: 操作详情。
            elapsed_ms: 耗时（毫秒）。
            details: 额外详情。
        """
        level = "info" if success else "error"
        elapsed_str = f" ({elapsed_ms:.0f}ms)" if elapsed_ms else ""
        status = "成功" if success else "失败"
        message = f"{tool_name}: {detail} → {status}{elapsed_str}"
        self.log(level, "operation", message, details)

    def cache_status(
        self, used: int, total: int, hit_rate: float, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录缓存状态。

        Args:
            used: 已用条目数。
            total: 最大条目数。
            hit_rate: 命中率 (0-1)。
            details: 额外详情。
        """
        pct = (used / total * 100) if total > 0 else 0
        message = f"缓存: {used}/{total} ({pct:.0f}%) | 命中率: {hit_rate:.0%}"
        self.log("info", "cache", message, details)

    def error(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """记录错误日志。"""
        self.log("error", "error", message, details)

    def warning(self, category: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """记录警告日志。"""
        self.log("warning", category, message, details)

    # ================================================================
    # 内部方法
    # ================================================================

    def _write_to_file(self, entry: Dict[str, Any]) -> None:
        """将日志条目写入文件。

        Args:
            entry: 日志条目字典。
        """
        try:
            # 检查是否需要轮转
            self._rotate_if_needed()

            line = (
                f"[{entry['time_str']}] [{entry['level'].upper()}] "
                f"[{entry['category']}] {entry['message']}\n"
            )
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            logger.error(f"写入调试日志文件失败: {e}")

    def _rotate_if_needed(self) -> None:
        """检查并执行日志轮转。"""
        if not os.path.isfile(self._log_path):
            return

        try:
            size = os.path.getsize(self._log_path)
        except OSError:
            return

        if size < self._max_file_size:
            return

        # 执行轮转：删除最旧的备份，依次重命名
        try:
            # 删除最旧的备份
            oldest = f"{self._log_path}.{self._backup_count}"
            if os.path.isfile(oldest):
                os.remove(oldest)

            # 依次重命名
            for i in range(self._backup_count - 1, 0, -1):
                old_name = f"{self._log_path}.{i}"
                new_name = f"{self._log_path}.{i + 1}"
                if os.path.isfile(old_name):
                    os.rename(old_name, new_name)

            # 重命名当前文件
            os.rename(self._log_path, f"{self._log_path}.1")
        except OSError as e:
            logger.warning(f"日志轮转失败: {e}")

    @staticmethod
    def _format_time(timestamp: float) -> str:
        """格式化时间戳为北京时间字符串。

        Args:
            timestamp: Unix 时间戳。

        Returns:
            str: 格式化的时间字符串。
        """
        dt = datetime.fromtimestamp(timestamp, tz=DebugLogger._CST)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
