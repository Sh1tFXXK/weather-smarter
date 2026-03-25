from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from backend.agent import llm_router
from backend.agent.tools.base import ToolRegistry


def _build_prompt(goal: str, context: Dict[str, Any], tools: ToolRegistry) -> tuple[str, str]:
    tool_lines = [
        {"name": item.name, "description": item.description}
        for item in tools.list()
    ]
    system_prompt = (
        "你是一个 Agent Planner。"
        "你的任务是根据用户目标选择合适的工具调用顺序。"
        "严格输出 JSON，格式为 {\"steps\":[{\"tool\":\"tool_name\",\"args\":{...}}]}。"
        "不要输出解释，不要 markdown，不要虚构不存在的工具。"
        "最多 6 步，尽量只选择必要工具。"
    )
    user_prompt = json.dumps(
        {"goal": goal, "context": context, "tools": tool_lines},
        ensure_ascii=False,
    )
    return system_prompt, user_prompt


def _parse_plan(raw_text: str, tools: ToolRegistry) -> Optional[List[Dict[str, Any]]]:
    if not raw_text:
        return None
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(raw_text[start : end + 1])
        except json.JSONDecodeError:
            return None
    steps = data.get("steps") if isinstance(data, dict) else None
    if not isinstance(steps, list):
        return None
    parsed: List[Dict[str, Any]] = []
    for item in steps[:6]:
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("tool") or "").strip()
        if not tool_name or not tools.has(tool_name):
            continue
        args = item.get("args")
        parsed.append({"tool": tool_name, "args": args if isinstance(args, dict) else {}})
    return parsed or None


async def _plan_with_openai(goal: str, context: Dict[str, Any], tools: ToolRegistry) -> Optional[List[Dict[str, Any]]]:
    if not getattr(llm_router, "_OPENAI_AVAILABLE", False):
        return None
    system_prompt, user_prompt = _build_prompt(goal, context, tools)
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    base_url = os.getenv("OPENAI_BASE_URL")
    compat_mode = (os.getenv("OPENAI_COMPAT_MODE") or "").lower()
    api_key = os.getenv("OPENAI_API_KEY") or ("lm-studio" if base_url else None)
    client = llm_router.OpenAI(api_key=api_key, base_url=base_url)

    def _call() -> Any:
        if compat_mode == "chat" or base_url:
            return client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=500,
            )
        return client.responses.create(
            model=model,
            input=[
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_output_tokens=500,
            text={"format": {"type": "json_object"}},
        )

    try:
        response = await asyncio.to_thread(_call)
    except Exception:
        return None

    raw_text = None
    if compat_mode == "chat" or base_url:
        if hasattr(response, "choices"):
            choice = response.choices[0] if response.choices else None
            if choice and choice.message:
                raw_text = choice.message.content
    return _parse_plan(raw_text or llm_router._extract_text(response), tools)


async def _plan_with_ollama(goal: str, context: Dict[str, Any], tools: ToolRegistry) -> Optional[List[Dict[str, Any]]]:
    if not getattr(llm_router, "_HTTPX_AVAILABLE", False):
        return None
    system_prompt, user_prompt = _build_prompt(goal, context, tools)
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("LLM_MODEL", "llama3.2:1b")
    timeout = float(os.getenv("OLLAMA_TIMEOUT", "30"))
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 500},
    }
    try:
        async with llm_router.httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{base_url}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    message = data.get("message", {}) if isinstance(data, dict) else {}
    return _parse_plan(message.get("content") if isinstance(message, dict) else "", tools)


async def _plan_with_llama_cpp(goal: str, context: Dict[str, Any], tools: ToolRegistry) -> Optional[List[Dict[str, Any]]]:
    llama = llm_router._get_llama()
    if llama is None:
        return None
    system_prompt, user_prompt = _build_prompt(goal, context, tools)

    def _call() -> Any:
        return llama.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=500,
        )

    try:
        response = await asyncio.to_thread(_call)
    except Exception:
        return None
    raw_text = None
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            raw_text = (choices[0].get("message") or {}).get("content")
    return _parse_plan(raw_text or "", tools)


async def plan_with_llm(goal: str, context: Dict[str, Any], tools: ToolRegistry) -> Optional[List[Dict[str, Any]]]:
    if not llm_router.llm_enabled():
        return None
    provider = llm_router._provider()
    if provider == "openai":
        return await _plan_with_openai(goal, context, tools)
    if provider == "ollama":
        return await _plan_with_ollama(goal, context, tools)
    if provider == "llama_cpp":
        return await _plan_with_llama_cpp(goal, context, tools)
    return None
