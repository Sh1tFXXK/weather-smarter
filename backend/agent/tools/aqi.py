from __future__ import annotations

from typing import Any, Dict

from backend.api.v1 import _compose_location_name, _normalize_timestamp, _resolve_weather_data
from backend.agent.tools.base import ToolRegistry, ToolSpec


async def get_aqi_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    weather = await _resolve_weather_data(
        request=None,
        city=args.get("city"),
        adcode=args.get("adcode"),
        lat=args.get("lat"),
        lon=args.get("lon"),
        lang=args.get("lang", "zh"),
        extended=True,
        require_location=True,
        require_aqi=True,
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
        "aqi": weather.get("aqi"),
        "primary": weather.get("aqi_primary"),
        "ts": _normalize_timestamp(weather.get("ts"), fallback=weather.get("updatedAt")),
        "source": weather.get("source"),
        "updatedAt": weather.get("updatedAt"),
    }


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="get_aqi",
            description="获取指定城市或坐标的 AQI 与首要污染物",
            handler=get_aqi_tool,
        )
    )
