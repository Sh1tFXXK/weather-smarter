from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_model_path() -> Path:
    return project_root() / "models" / "gguf" / "Qwen3-0.6B.Q4_K_M.gguf"


def build_backend_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("UAPIS_BASE_URL", "https://uapis.cn/api/v1")
    env.setdefault("UAPIS_TIMEOUT", "5.0")
    env.setdefault("UAPIS_RETRIES", "2")
    env.setdefault("UAPIS_BACKOFF", "0.6")
    env.setdefault("WEATHER_STATUS_PROBE", "1")

    env.setdefault("LLM_PROVIDER", "llama_cpp")
    env.setdefault("LLM_MODEL_PATH", str(default_model_path()))
    env.setdefault("LLM_CTX", "2048")
    env.setdefault("LLM_GPU_LAYERS", "0")
    env.setdefault("LLM_THREADS", str(max(2, min(6, os.cpu_count() or 4))))
    env.setdefault("LLM_BATCH", "128")
    env.setdefault("LLM_TEMPERATURE", "0.2")
    env.setdefault("LLM_MAX_TOKENS", "300")
    env.setdefault("LLM_RESPONSE_FORMAT", "json_object")

    env.setdefault("EXPECT_LLM", "1")
    env.setdefault("EXPECT_REAL_WEATHER", "1")
    return env
