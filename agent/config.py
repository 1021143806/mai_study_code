"""独立进程配置管理。

替代原来插件体系中的 plugin.config / bot_config.toml 等。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import json
import os
import tomllib


class LLMConfig:
    """LLM 调用配置。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_tokens: int = 4000,
        temperature: float = 0.1,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout


class SandboxConfig:
    """沙箱配置。"""

    def __init__(
        self,
        max_memory_mb: int = 128,
        max_timeout_sec: int = 15,
        max_output_chars: int = 10000,
    ) -> None:
        self.max_memory_mb = max_memory_mb
        self.max_timeout_sec = max_timeout_sec
        self.max_output_chars = max_output_chars


class CacheConfig:
    """缓存配置。"""

    def __init__(
        self,
        enabled: bool = True,
        max_entries: int = 500,
        ttl_seconds: int = 1800,
    ) -> None:
        self.enabled = enabled
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds


class RiskConfig:
    """风险控制配置。"""

    def __init__(
        self,
        require_confirmation_medium: bool = True,
        require_confirmation_high: bool = True,
        block_critical: bool = True,
    ) -> None:
        self.require_confirmation_medium = require_confirmation_medium
        self.require_confirmation_high = require_confirmation_high
        self.block_critical = block_critical


class LearnerConfig:
    """学习模块配置。"""

    def __init__(
        self,
        enabled: bool = True,
        auto_save_notes: bool = False,
        knowledge_dir: str = "knowledge",
    ) -> None:
        self.enabled = enabled
        self.auto_save_notes = auto_save_notes
        self.knowledge_dir = knowledge_dir


class WebConfig:
    """Web 服务配置。"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        auto_refresh_sec: int = 30,
        mai_study_code_plugin_url: str = "",
    ) -> None:
        self.host = host
        self.port = port  # 0 = 随机端口
        self.auto_refresh_sec = auto_refresh_sec
        # 麦麦插件侧的 HTTP 地址，mai_study_code 工具调用的回调
        self.mai_study_code_plugin_url = mai_study_code_plugin_url


class DebugLogConfig:
    """调试日志配置。"""

    def __init__(
        self,
        enabled: bool = False,
        log_file: str = "workspace/debug.log",
        max_file_size_mb: int = 5,
        backup_count: int = 2,
    ) -> None:
        self.enabled = enabled
        self.log_file = log_file
        self.max_file_size_mb = max_file_size_mb
        self.backup_count = backup_count


class AgentConfig:
    """智能体总配置。"""

    def __init__(self, data: Dict[str, Any]) -> None:
        self.debug: bool = data.get("debug", False)
        self.port: int = int(data.get("port", 0))
        self.host: str = str(data.get("host", "127.0.0.1"))

        # LLM
        llm_data = data.get("llm", {})
        self.llm = LLMConfig(
            api_key=str(llm_data.get("api_key", "")),
            base_url=str(llm_data.get("base_url", "https://api.deepseek.com/v1")),
            model=str(llm_data.get("model", "deepseek-chat")),
            max_tokens=int(llm_data.get("max_tokens", 4000)),
            temperature=float(llm_data.get("temperature", 0.1)),
            timeout=int(llm_data.get("timeout", 30)),
        )

        # 子模块
        sub_data = data.get("modules", {})
        self.sandbox = SandboxConfig(**sub_data.get("sandbox", {}))
        self.cache = CacheConfig(**sub_data.get("cache", {}))
        self.risk = RiskConfig(**sub_data.get("risk", {}))
        self.learner = LearnerConfig(**sub_data.get("learner", {}))
        self.web = WebConfig(**sub_data.get("web", {}))
        self.debug_log = DebugLogConfig(**sub_data.get("debug_log", {}))

        # 权限等级（默认 root，因为是独立进程自行管理）
        self.granted_level: str = str(data.get("granted_level", "root"))

        # 统计持久化路径
        self.stats_path: str = str(
            data.get("stats_path", os.path.join(os.path.dirname(__file__), "..", "data", "stats.json"))
        )

    @classmethod
    def load(cls, path: str) -> AgentConfig:
        """从 toml 文件加载配置。

        Args:
            path: 配置文件路径。

        Returns:
            AgentConfig: 配置实例。
        """
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(data)

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典（用于 API 展示）。"""
        return {
            "debug": self.debug,
            "host": self.host,
            "port": self.port,
            "llm": {
                "model": self.llm.model,
                "base_url": self.llm.base_url,
                "max_tokens": self.llm.max_tokens,
                "temperature": self.llm.temperature,
            },
            "granted_level": self.granted_level,
            "modules": {
                "sandbox": {
                    "max_memory_mb": self.sandbox.max_memory_mb,
                    "max_timeout_sec": self.sandbox.max_timeout_sec,
                    "max_output_chars": self.sandbox.max_output_chars,
                },
                "cache": {
                    "enabled": self.cache.enabled,
                    "max_entries": self.cache.max_entries,
                    "ttl_seconds": self.cache.ttl_seconds,
                },
            },
        }
