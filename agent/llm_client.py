"""LLM API 客户端（直调 DeepSeek API，不经过 MaiBot 插件体系）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import aiohttp
import asyncio
import json
import logging

from .config import LLMConfig

logger = logging.getLogger("mai-study-code.llm")


class LLMClient:
    """LLM API 客户端。

    直接调用 OpenAI 兼容 API，替代原来的 plugin.ctx.llm.generate_with_tools()。
    """

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._base_url = config.base_url
        self._api_key = config.api_key
        self._model = config.model

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """调用 LLM 生成响应。

        Args:
            messages: 消息列表。
            tools: 工具定义列表（可选）。
            **kwargs: 其他参数。

        Returns:
            Dict[str, Any]: 统一响应字典，格式与 maibot_sdk 兼容：
                {
                    "response": "...",
                    "content": "...",
                    "tool_calls": [...],
                    "model": "...",
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cache_hit_tokens": 0,
                }
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
            "temperature": kwargs.get("temperature", self._config.temperature),
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        logger.debug(
            f"LLM 请求: model={self._model}, messages={len(messages)}条, "
            f"tools={len(tools) if tools else 0}个, "
            f"input_tokens≈{sum(len(m.get('content','') or '') for m in messages) // 2}"
        )

        timeout = aiohttp.ClientTimeout(total=self._config.timeout)
        try:
            async with aiohttp.ClientSession(
                headers=headers,
                timeout=timeout,
            ) as session:
                async with session.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"LLM API 错误 ({resp.status}): {error_text[:200]}")
                        return {
                            "response": f"（LLM API 返回 {resp.status}）",
                            "content": "",
                            "tool_calls": [],
                            "model": self._model,
                            "error": error_text[:200],
                        }

                    data = await resp.json()
                    return self._parse_response(data)
        except asyncio.TimeoutError:
            logger.warning(f"LLM 请求超时 ({self._config.timeout}s)")
            return {
                "response": "（生成超时）",
                "tool_calls": [],
                "error": "timeout",
            }
        except Exception as e:
            logger.error(f"LLM 请求异常: {e}")
            return {
                "response": f"（生成异常: {e}）",
                "tool_calls": [],
                "error": str(e),
            }

    def _parse_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析 OpenAI 兼容 API 的响应。

        Args:
            data: API 原始响应。

        Returns:
            Dict[str, Any]: 统一响应字典。
        """
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        tool_calls_raw = message.get("tool_calls", [])

        # 解析工具调用
        tool_calls = []
        for tc in tool_calls_raw:
            tool_calls.append({
                "id": tc.get("id", ""),
                "type": tc.get("type", "function"),
                "function": {
                    "name": tc.get("function", {}).get("name", ""),
                    "arguments": tc.get("function", {}).get("arguments", "{}"),
                },
            })

        # Token 统计
        usage = data.get("usage", {})
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        cache_hit_tokens = int(usage.get("prompt_cache_hit_tokens", 0) or 0)

        return {
            "response": content,
            "content": content,
            "tool_calls": tool_calls,
            "model": data.get("model", self._model),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cache_hit_tokens": cache_hit_tokens,
        }
