"""代码智能体核心：LLM 对话循环 + 工具定义 + 工具执行。

这个模块负责 WebUI 代码面板中的所有智能体逻辑：
1. 工具定义（基于权限等级筛选）
2. LLM 对话循环（最多 3 轮工具调用）
3. 工具执行（文件操作、代码执行、目录切换）
4. Token 统计
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import asyncio
import json
import logging
import os

from .config import AgentConfig
from .llm_client import LLMClient

logger = logging.getLogger("mai-study-code.agent")


# 工具定义（OpenAI Function Calling 格式）
_ALL_TOOLS: Dict[str, Dict[str, Any]] = {
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容。如果路径是目录会自动列出目录内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件或目录路径（相对于当前目录）",
                    }
                },
                "required": ["path"],
            },
        },
    },
    "list_dir": {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出指定目录下的文件和子目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目录路径（相对于当前目录，省略则列出当前目录）",
                    }
                },
                "required": [],
            },
        },
    },
    "write_file": {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "创建或覆盖工作区文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "文件内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    "execute_code": {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "在沙箱中执行 Python 代码并返回结果",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python 代码"},
                },
                "required": ["code"],
            },
        },
    },
    "create_dir": {
        "type": "function",
        "function": {
            "name": "create_dir",
            "description": "创建工作区内的目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目录路径（相对于当前目录）",
                    }
                },
                "required": ["path"],
            },
        },
    },
    "change_dir": {
        "type": "function",
        "function": {
            "name": "change_dir",
            "description": "切换当前工作目录到指定的子目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目标目录路径（相对于当前目录，使用 .. 返回上级）",
                    }
                },
                "required": ["path"],
            },
        },
    },
}

_TOKEN_PRICING = {
    "input_price_per_1k": 0.001,
    "output_price_per_1k": 0.002,
    "cache_hit_price_per_1k": 0.0001,
}


def _resolve_path(p: str, cwd: str) -> str:
    """解析相对路径。"""
    if not p or p.startswith("/") or "../" in p.replace("\\", "/"):
        return p
    return f"{cwd}/{p}" if cwd else p


class SandboxStats:
    """沙箱执行统计（独立管理，替代 plugin._sandbox_stats）。"""

    def __init__(self, stats_path: str = "") -> None:
        self._stats_path = stats_path
        self._data: Dict[str, Any] = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "avg_time_ms": 0.0,
        }
        self._load()

    def _load(self) -> None:
        if not self._stats_path:
            return
        try:
            with open(self._stats_path) as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    self._data.update(loaded)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save(self) -> None:
        if not self._stats_path:
            return
        try:
            os.makedirs(os.path.dirname(self._stats_path), exist_ok=True)
            with open(self._stats_path, "w") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def record(self, success: bool, execution_time_ms: float) -> None:
        d = self._data
        d["total"] = d.get("total", 0) + 1
        if success:
            d["success"] = d.get("success", 0) + 1
        else:
            d["failed"] = d.get("failed", 0) + 1
        old_avg = d.get("avg_time_ms", 0.0)
        old_count = d["total"] - 1
        d["avg_time_ms"] = round(
            (old_avg * old_count + execution_time_ms) / d["total"], 1
        )
        self._save()

    def get(self) -> Dict[str, Any]:
        return dict(self._data)


class AgentLoop:
    """代码智能体对话循环。

    不再依赖 plugin 实例，所有依赖通过构造器注入。

    职责：
    - 根据权限等级筛选可用工具
    - 执行 LLM 对话循环（最多 3 轮）
    - 执行工具调用
    - 统计 token 消耗
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_client: LLMClient,
    ) -> None:
        self._config = config
        self._llm_client = llm_client
        self._sandbox_stats = SandboxStats(config.stats_path)

        # Token 统计
        self._token_stats: Dict[str, Any] = {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost": 0.0,
            "bars": [],
        }

    def get_token_stats(self) -> Dict[str, Any]:
        return dict(self._token_stats)

    def get_sandbox_stats(self) -> Dict[str, Any]:
        """获取沙箱执行统计。"""
        return self._sandbox_stats.get()

    async def run(
        self,
        messages: List[Dict[str, Any]],
        cwd: str,
    ) -> Dict[str, Any]:
        """执行一轮完整的智能体对话。

        Args:
            messages: 前端传来的消息列表（完整 chatHistory）。
            cwd: 当前工作目录（相对路径）。

        Returns:
            Dict[str, Any]: 包含 response/model/tool_results/cwd 的字典。
        """
        granted_level = self._config.granted_level
        tools = self._get_tools_for_level(granted_level)

        enhanced_messages = list(messages)

        # 注入工作区上下文
        ws_context = self._build_ws_context(cwd)
        if ws_context:
            enhanced_messages.insert(
                0, {"role": "system", "content": ws_context},
            )

        all_tool_results: List[Dict[str, Any]] = []
        final_response = ""
        model = ""

        for _round in range(3):
            result = await self._llm_client.generate(
                enhanced_messages, tools=tools,
            )

            # Token 统计
            self._record_token_usage(result)

            response_text = result.get("response", "") or result.get("content", "")
            model = result.get("model", model)
            tool_calls = result.get("tool_calls", []) or []

            if response_text and not tool_calls:
                final_response = response_text
                break

            if response_text:
                final_response = response_text

            if not tool_calls:
                break

            # 执行工具
            round_results = await self._execute_tools(tool_calls, cwd)
            all_tool_results.extend(round_results)

            # 回填消息历史
            self._backfill_messages(enhanced_messages, tool_calls, round_results)
        else:
            if not final_response:
                final_response = response_text or "(达到最大轮次)"

        return {
            "response": final_response,
            "model": model,
            "tool_results": all_tool_results,
            "cwd": cwd,
        }

    # ── 内部方法 ──

    @staticmethod
    def _get_tools_for_level(level: str) -> List[Dict[str, Any]]:
        allowed_names = {
            "0": [],
            "1": ["read_file"],
            "2": ["read_file", "write_file", "execute_code", "create_dir", "change_dir", "list_dir"],
            "3": ["read_file", "write_file", "execute_code", "create_dir", "change_dir", "list_dir"],
            "4": ["read_file", "write_file", "execute_code", "create_dir", "change_dir", "list_dir"],
            "root": ["read_file", "write_file", "execute_code", "create_dir", "change_dir", "list_dir"],
        }.get(level, ["read_file"])
        return [_ALL_TOOLS[name] for name in allowed_names]

    @staticmethod
    def _build_ws_context(cwd: str) -> str:
        if not cwd:
            return ""
        return (
            f"当前工作目录: {cwd}\n"
            "读写文件时路径相对于当前目录。使用 change_dir 切换目录，使用 .. 返回上级。"
        )

    def _record_token_usage(self, result: Dict[str, Any]) -> None:
        prompt_tokens = int(result.get("prompt_tokens", 0) or 0)
        completion_tokens = int(result.get("completion_tokens", 0) or 0)
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens <= 0:
            return

        cache_hit = int(result.get("cache_hit_tokens", 0) or 0)
        cost = round(
            (prompt_tokens / 1000) * _TOKEN_PRICING["input_price_per_1k"]
            + (completion_tokens / 1000) * _TOKEN_PRICING["output_price_per_1k"],
            6,
        )

        s = self._token_stats
        s["total_prompt_tokens"] = s.get("total_prompt_tokens", 0) + prompt_tokens
        s["total_completion_tokens"] = s.get("total_completion_tokens", 0) + completion_tokens
        s["total_cost"] = round(s.get("total_cost", 0) + cost, 6)
        bars = s.get("bars", [])
        bars.append({
            "total_tokens": total_tokens,
            "cost": cost,
            "label": "对话",
            "timestamp": __import__("time").time(),
        })
        if len(bars) > 50:
            bars[:] = bars[-50:]
        s["bars"] = bars

        logger.info(
            f"Token 消耗: prompt={prompt_tokens}, completion={completion_tokens}, "
            f"cache_hit={cache_hit}, cost=${cost}"
        )

    async def _execute_tools(
        self,
        tool_calls: List[Dict[str, Any]],
        cwd: str,
    ) -> List[Dict[str, Any]]:
        """执行工具调用。"""
        round_results: List[Dict[str, Any]] = []

        for tc in tool_calls:
            func_name = (
                tc.get("function", {}).get("name", "")
                if isinstance(tc, dict) else ""
            )
            args_raw = (
                tc.get("function", {}).get("arguments", "{}")
                if isinstance(tc, dict) else "{}"
            )
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except Exception:
                args = {}

            entry: Dict[str, Any] = {
                "tool": func_name, "input": "", "output": "", "success": False,
            }

            try:
                if func_name in ("read_file", "list_dir"):
                    path = (
                        _resolve_path(args.get("path", ""), cwd)
                        if func_name == "read_file"
                        else (args.get("path", "") or cwd or ".")
                    )
                    entry["input"] = path
                    entry["output"] = f"[模拟] 读取 {path}"
                    entry["success"] = True

                elif func_name == "write_file":
                    path = _resolve_path(args.get("path", ""), cwd)
                    content = args.get("content", "")
                    entry["input"] = f"{path} ({len(content)} chars)"
                    entry["output"] = f"[模拟] 写入 {path}"
                    entry["success"] = True

                elif func_name == "change_dir":
                    target = args.get("path", "")
                    entry["input"] = target
                    if target == "..":
                        if cwd:
                            cwd = "/".join(cwd.rstrip("/").split("/")[:-1])
                    elif target.startswith("/"):
                        cwd = target.lstrip("/")
                    else:
                        cwd = f"{cwd}/{target}".lstrip("/") if cwd else target
                    entry["output"] = f"已切换到 {cwd or '(根目录)'}"
                    entry["success"] = True

                elif func_name == "create_dir":
                    path = _resolve_path(args.get("path", ""), cwd)
                    entry["input"] = path
                    entry["output"] = f"[模拟] 创建目录 {path}"
                    entry["success"] = True

                elif func_name == "execute_code":
                    code = args.get("code", "")
                    entry["input"] = code[:100]
                    from ..sandbox import execute_with_safety_check
                    try:
                        future = asyncio.get_running_loop().run_in_executor(
                            None, lambda: execute_with_safety_check(code),
                        )
                        er = await asyncio.wait_for(future, timeout=15)
                        entry["output"] = (
                            er.stdout if er.success else (er.stderr or er.error or "")
                        )
                        entry["success"] = er.success
                        self._sandbox_stats.record(
                            er.success, er.execution_time_ms,
                        )
                    except asyncio.TimeoutError:
                        entry["output"] = "执行超时"
                    except Exception as e:
                        entry["output"] = f"执行异常: {e}"

                else:
                    entry["output"] = f"未知工具: {func_name}"

            except Exception as e:
                entry["output"] = str(e)

            round_results.append(entry)

        return round_results

    @staticmethod
    def _backfill_messages(
        messages: List[Dict[str, Any]],
        tool_calls: List[Dict[str, Any]],
        round_results: List[Dict[str, Any]],
    ) -> None:
        """工具调用结果回填。"""
        assistant_msg: Dict[str, Any] = {
            "role": "assistant", "content": "", "tool_calls": [],
        }
        for tc in tool_calls:
            if isinstance(tc, dict):
                assistant_msg["tool_calls"].append({
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", "{}"),
                    },
                })
        messages.append(assistant_msg)

        for i, tr in enumerate(round_results):
            tc_id = tool_calls[i].get("id", "") if i < len(tool_calls) else ""
            messages.append({
                "role": "tool",
                "content": f"[{tr['tool']}] {tr['output'][:2000]}",
                "tool_call_id": tc_id,
            })
