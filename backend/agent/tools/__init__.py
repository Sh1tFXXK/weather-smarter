from __future__ import annotations

from functools import lru_cache

from backend.agent.tools import aqi, forecast, memory, profile, rag, stocks, tasks, weather
from backend.agent.tools.base import ToolRegistry


@lru_cache(maxsize=1)
def get_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    weather.register(registry)
    forecast.register(registry)
    aqi.register(registry)
    rag.register(registry)
    memory.register(registry)
    profile.register(registry)
    tasks.register(registry)
    stocks.register(registry)
    return registry
