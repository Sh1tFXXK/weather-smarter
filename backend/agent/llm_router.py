from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI

    _OPENAI_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    _OPENAI_AVAILABLE = False

try:
    import httpx

    _HTTPX_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    _HTTPX_AVAILABLE = False

try:
    from llama_cpp import Llama

    _LLAMACPP_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    _LLAMACPP_AVAILABLE = False


def _provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "").lower()


def llm_status() -> tuple[bool, str]:
    provider = _provider()
    if not provider:
        return False, "LLM_PROVIDER not set"
    if provider == "openai":
        if not _OPENAI_AVAILABLE:
            return False, "OpenAI SDK not installed"
        if not os.getenv("OPENAI_API_KEY"):
            if os.getenv("OPENAI_BASE_URL"):
                return True, ""
            return False, "OPENAI_API_KEY missing"
        return True, ""
    if provider == "ollama":
        if not _HTTPX_AVAILABLE:
            return False, "httpx not installed"
        return True, ""
    if provider == "llama_cpp":
        if not _LLAMACPP_AVAILABLE:
            return False, "llama-cpp-python not installed"
        if not os.getenv("LLM_MODEL_PATH"):
            return False, "LLM_MODEL_PATH missing"
        return True, ""
    return False, f"Unsupported LLM_PROVIDER: {provider}"


def llm_enabled() -> bool:
    ok, _ = llm_status()
    return ok


_LLAMA_INSTANCE: Optional[Llama] = None
_LLAMA_LOCK = threading.Lock()


def _get_llama() -> Optional[Llama]:
    if not _LLAMACPP_AVAILABLE:
        return None
    global _LLAMA_INSTANCE
    if _LLAMA_INSTANCE is not None:
        return _LLAMA_INSTANCE
    with _LLAMA_LOCK:
        if _LLAMA_INSTANCE is not None:
            return _LLAMA_INSTANCE
        model_path = os.getenv("LLM_MODEL_PATH")
        if not model_path:
            return None
        n_ctx = int(os.getenv("LLM_CTX", "2048"))
        n_gpu_layers = int(os.getenv("LLM_GPU_LAYERS", "0"))
        n_threads = int(os.getenv("LLM_THREADS", "8"))
        n_batch = int(os.getenv("LLM_BATCH", "512"))
        lora_path = os.getenv("LLM_LORA_PATH")
        kwargs: Dict[str, Any] = {
            "model_path": model_path,
            "n_ctx": n_ctx,
            "n_gpu_layers": n_gpu_layers,
            "n_threads": n_threads,
            "n_batch": n_batch,
        }
        if lora_path:
            kwargs["lora_path"] = lora_path
        _LLAMA_INSTANCE = Llama(**kwargs)
        return _LLAMA_INSTANCE


def _extract_text(response: Any) -> str:
    if hasattr(response, "output_text"):
        return response.output_text or ""
    output = getattr(response, "output", None)
    if not output:
        return ""
    texts: List[str] = []
    for item in output:
        content = getattr(item, "content", None) or []
        for part in content:
            text = getattr(part, "text", None)
            if text:
                texts.append(text)
            elif isinstance(part, dict) and part.get("text"):
                texts.append(part["text"])
    return "\n".join(texts).strip()


def _normalize_memory(memory: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    if not memory:
        return []
    result: List[Dict[str, str]] = []
    for item in memory:
        role = item.get("role", "user")
        content = item.get("content", "")
        if content:
            result.append({"role": role, "content": content})
    return result[-6:]


def _build_context(
    *,
    intent: str,
    query: str,
    locale: Optional[str],
    weather: Dict[str, Any],
    environment: Optional[Dict[str, Any]],
    base_decision: Dict[str, Any],
    memory: Optional[List[Dict[str, Any]]],
    rag: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    weather_core = {
        "status": weather.get("weather"),
        "temperature": weather.get("temperature"),
        "feels_like": weather.get("feels_like"),
        "humidity": weather.get("humidity"),
        "wind_direction": weather.get("wind_direction"),
        "wind_power": weather.get("wind_power"),
        "precipitation": weather.get("precipitation"),
        "uv": weather.get("uv"),
        "aqi": weather.get("aqi"),
    }
    return {
        "query": query,
        "intent": intent,
        "locale": locale,
        "weather": weather_core,
        "environment": environment,
        "base_decision": base_decision,
        "memory": _normalize_memory(memory),
        "rag": rag or [],
    }


def _parse_json_response(raw_text: str) -> Optional[Dict[str, Any]]:
    if not raw_text:
        return None
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(raw_text[start : end + 1])
        except json.JSONDecodeError:
            return None


def _normalize_decision(
    data: Dict[str, Any], base_decision: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    if not isinstance(data, dict):
        return None
    if "advice" not in data or "riskLevel" not in data:
        return None
    if not isinstance(data.get("reasons", []), list):
        data["reasons"] = []
    if not isinstance(data.get("actions", []), list):
        data["actions"] = []
    return {
        "advice": data.get("advice", base_decision.get("advice")),
        "riskLevel": data.get("riskLevel", base_decision.get("riskLevel")),
        "reasons": data.get("reasons", base_decision.get("reasons", [])),
        "actions": data.get("actions", base_decision.get("actions", [])),
    }


async def _enrich_with_openai(
    *,
    intent: str,
    query: str,
    locale: Optional[str],
    weather: Dict[str, Any],
    environment: Optional[Dict[str, Any]],
    base_decision: Dict[str, Any],
    memory: Optional[List[Dict[str, Any]]],
    rag: Optional[List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    if not _OPENAI_AVAILABLE:
        return None

    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "300"))
    response_format = (os.getenv("LLM_RESPONSE_FORMAT") or "json_object").lower()
    base_url = os.getenv("OPENAI_BASE_URL")
    compat_mode = (os.getenv("OPENAI_COMPAT_MODE") or "").lower()
    api_key = os.getenv("OPENAI_API_KEY") or ("lm-studio" if base_url else None)

    system_prompt = (
        "你是环境驱动决策系统的智能推理层。"
        "基于输入的环境数据与规则决策，生成更自然、可解释的建议。"
        "严格输出 JSON："
        '{"advice": "...", "riskLevel": "low|medium|high", '
        '"reasons": ["..."], "actions": ["..."]}'
        "。若无法改进，保持 base_decision。"
        "advice 必须直接回答用户问题，并尽量包含问题中的城市/时间/活动。"
        "当 intent 为 greeting 时，仅输出简短问候，不要提及天气或建议。"
        "不要输出解释，不要使用代码块。"
    )

    context = _build_context(
        intent=intent,
        query=query,
        locale=locale,
        weather=weather,
        environment=environment,
        base_decision=base_decision,
        memory=memory,
        rag=rag,
    )

    client = OpenAI(api_key=api_key, base_url=base_url)

    def _call() -> Any:
        if compat_mode == "chat" or base_url:
            payload: Dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(context, ensure_ascii=False),
                    },
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format == "json_schema":
                payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "decision", "schema": {
                    "type": "object",
                    "properties": {
                        "advice": {"type": "string"},
                        "riskLevel": {"type": "string"},
                        "reasons": {"type": "array", "items": {"type": "string"}},
                        "actions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["advice", "riskLevel", "reasons", "actions"],
                    "additionalProperties": False,
                }}}
            return client.chat.completions.create(**payload)
        payload = {
            "model": model,
            "input": [
                {"role": "developer", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False),
                },
            ],
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if response_format in ("json_object", "json_schema"):
            if response_format == "json_schema":
                payload["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": "decision",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "advice": {"type": "string"},
                                "riskLevel": {"type": "string"},
                                "reasons": {"type": "array", "items": {"type": "string"}},
                                "actions": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["advice", "riskLevel", "reasons", "actions"],
                            "additionalProperties": False,
                        },
                        "strict": True,
                    }
                }
            else:
                payload["text"] = {"format": {"type": "json_object"}}
        return client.responses.create(**payload)

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
    data = _parse_json_response(raw_text or _extract_text(response))
    if not data and raw_text:
        repair_prompt = (
            "你是 JSON 修复助手。请将下面内容转换为严格的 JSON 对象，"
            "只输出 JSON，不要任何解释或代码块。"
            '字段必须包含: "advice","riskLevel","reasons","actions"。'
            "如果信息不足，请基于 base_decision 补全。"
            "advice 需直接回答问题并包含城市/时间/活动（若有）。"
            "当 intent 为 greeting 时，仅输出简短问候，不要提及天气或建议。"
        )
        repair_context = {
            "raw": raw_text,
            "base_decision": base_decision,
        }

        def _repair() -> Any:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": repair_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(repair_context, ensure_ascii=False),
                    },
                ],
                "temperature": 0,
                "max_tokens": max_tokens,
            }
            if response_format == "json_schema":
                payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "decision", "schema": {
                    "type": "object",
                    "properties": {
                        "advice": {"type": "string"},
                        "riskLevel": {"type": "string"},
                        "reasons": {"type": "array", "items": {"type": "string"}},
                        "actions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["advice", "riskLevel", "reasons", "actions"],
                    "additionalProperties": False,
                }}}
            return client.chat.completions.create(**payload)

        try:
            repair_resp = await asyncio.to_thread(_repair)
            repair_text = None
            if hasattr(repair_resp, "choices"):
                choice = repair_resp.choices[0] if repair_resp.choices else None
                if choice and choice.message:
                    repair_text = choice.message.content
            data = _parse_json_response(repair_text or "")
        except Exception:
            data = None
    if not data:
        return None
    return _normalize_decision(data, base_decision)


async def _enrich_with_ollama(
    *,
    intent: str,
    query: str,
    locale: Optional[str],
    weather: Dict[str, Any],
    environment: Optional[Dict[str, Any]],
    base_decision: Dict[str, Any],
    memory: Optional[List[Dict[str, Any]]],
    rag: Optional[List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    if not _HTTPX_AVAILABLE:
        return None

    model = os.getenv("LLM_MODEL", "llama3.2:1b")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "300"))
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    timeout = float(os.getenv("OLLAMA_TIMEOUT", "30"))
    response_format = (os.getenv("LLM_RESPONSE_FORMAT") or "json_object").lower()

    system_prompt = (
        "你是环境驱动决策系统的智能推理层。"
        "基于输入的环境数据与规则决策，生成更自然、可解释的建议。"
        "严格输出 JSON："
        '{"advice": "...", "riskLevel": "low|medium|high", '
        '"reasons": ["..."], "actions": ["..."]}'
        "。若无法改进，保持 base_decision。"
        "advice 必须直接回答用户问题，并尽量包含问题中的城市/时间/活动。"
        "当 intent 为 greeting 时，仅输出简短问候，不要提及天气或建议。"
        "不要输出解释，不要使用代码块。"
    )

    context = _build_context(
        intent=intent,
        query=query,
        locale=locale,
        weather=weather,
        environment=environment,
        base_decision=base_decision,
        memory=memory,
        rag=rag,
    )

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }

    if response_format in ("json_object", "json_schema", "json"):
        payload["format"] = "json"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{base_url}/api/chat", json=payload)
        resp.raise_for_status()
    except Exception:
        return None

    try:
        data = resp.json()
    except ValueError:
        return None

    message = data.get("message", {}) if isinstance(data, dict) else {}
    raw_text = message.get("content") if isinstance(message, dict) else None
    parsed = _parse_json_response(raw_text or "")
    if not parsed:
        return None
    return _normalize_decision(parsed, base_decision)


async def _enrich_with_llama_cpp(
    *,
    intent: str,
    query: str,
    locale: Optional[str],
    weather: Dict[str, Any],
    environment: Optional[Dict[str, Any]],
    base_decision: Dict[str, Any],
    memory: Optional[List[Dict[str, Any]]],
    rag: Optional[List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    llama = _get_llama()
    if llama is None:
        return None

    temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "300"))

    system_prompt = (
        "你是环境驱动决策系统的智能推理层。"
        "基于输入的环境数据与规则决策，生成更自然、可解释的建议。"
        "严格输出 JSON："
        '{"advice": "...", "riskLevel": "low|medium|high", '
        '"reasons": ["..."], "actions": ["..."]}'
        "。若无法改进，保持 base_decision。"
        "advice 必须直接回答用户问题，并尽量包含问题中的城市/时间/活动。"
        "当 intent 为 greeting 时，仅输出简短问候，不要提及天气或建议。"
        "不要输出解释，不要使用代码块。"
    )

    context = _build_context(
        intent=intent,
        query=query,
        locale=locale,
        weather=weather,
        environment=environment,
        base_decision=base_decision,
        memory=memory,
        rag=rag,
    )

    def _call() -> Any:
        return llama.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    try:
        response = await asyncio.to_thread(_call)
    except Exception:
        return None

    raw_text = None
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            raw_text = message.get("content")
    parsed = _parse_json_response(raw_text or "")
    if not parsed:
        return None
    return _normalize_decision(parsed, base_decision)


async def enrich_decision(
    *,
    intent: str,
    query: str,
    locale: Optional[str],
    weather: Dict[str, Any],
    environment: Optional[Dict[str, Any]],
    base_decision: Dict[str, Any],
    memory: Optional[List[Dict[str, Any]]],
    rag: Optional[List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    if not llm_enabled():
        return None
    provider = _provider()
    if provider == "openai":
        return await _enrich_with_openai(
            intent=intent,
            query=query,
            locale=locale,
            weather=weather,
            environment=environment,
            base_decision=base_decision,
            memory=memory,
            rag=rag,
        )
    if provider == "ollama":
        return await _enrich_with_ollama(
            intent=intent,
            query=query,
            locale=locale,
            weather=weather,
            environment=environment,
            base_decision=base_decision,
            memory=memory,
            rag=rag,
        )
    if provider == "llama_cpp":
        return await _enrich_with_llama_cpp(
            intent=intent,
            query=query,
            locale=locale,
            weather=weather,
            environment=environment,
            base_decision=base_decision,
            memory=memory,
            rag=rag,
        )
    return None
