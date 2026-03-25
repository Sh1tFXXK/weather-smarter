from __future__ import annotations

from typing import Any, Dict

from backend.api.v1 import (
    _compose_location_name,
    _normalize_timestamp,
    _pick_hourly_items,
    _resolve_weather_data,
)
from backend.agent.tools.base import ToolRegistry, ToolSpec


async def get_forecast_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    hours = int(args.get("hours", 24) or 24)
    days = int(args.get("days", 7) or 7)
    weather = await _resolve_weather_data(
        request=None,
        city=args.get("city"),
        adcode=args.get("adcode"),
        lat=args.get("lat"),
        lon=args.get("lon"),
        lang=args.get("lang", "zh"),
        extended=True,
        forecast=True,
        hourly=True,
        require_location=True,
        require_aqi=True,
    )
    updated_at = weather.get("updatedAt")
    hourly_items = []
    for item in _pick_hourly_items(weather)[:hours]:
        pop_value = item.get("pop", item.get("precip"))
        if pop_value is not None:
            pop_value = float(pop_value)
            if pop_value > 1:
                pop_value = round(pop_value / 100.0, 4)
        hourly_items.append(
            {
                "ts": _normalize_timestamp(item.get("ts") or item.get("time"), fallback=updated_at),
                "temp": item.get("temp", item.get("temperature", weather.get("temperature"))),
                "pop": pop_value,
            }
        )
    daily_items = []
    for item in (weather.get("forecast") or [])[:days]:
        daily_items.append(
            {
                "date": item.get("date"),
                "tmin": item.get("tmin", item.get("temp_min")),
                "tmax": item.get("tmax", item.get("temp_max")),
                "uv": item.get("uv", item.get("uv_index", weather.get("uv"))),
                "text": item.get("text"),
            }
        )
    return {
        "location": {
            "name": _compose_location_name(
                weather,
                fallback_city=args.get("city"),
                fallback_adcode=args.get("adcode"),
            ),
            "city": weather.get("city") or args.get("city"),
            "adcode": weather.get("adcode") or args.get("adcode"),
            "lat": args.get("lat"),
            "lon": args.get("lon"),
        },
        "current": {
            "ts": _normalize_timestamp(weather.get("ts"), fallback=updated_at),
            "temp": weather.get("temperature"),
            "aqi": weather.get("aqi"),
            "wind": weather.get("wind_speed"),
        },
        "hourly": hourly_items,
        "daily": daily_items,
        "source": weather.get("source"),
        "updatedAt": updated_at,
    }


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="get_forecast",
            description="获取未来逐小时与逐日天气预报，包含降水概率",
            handler=get_forecast_tool,
        )
    )
