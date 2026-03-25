from __future__ import annotations

from typing import Any, Dict

from backend.api.v1 import _resolve_weather_data
from backend.agent.tools.base import ToolRegistry, ToolSpec


async def get_weather_tool(args: Dict[str, Any]) -> Dict[str, Any]:
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
        "city": weather.get("city"),
        "province": weather.get("province"),
        "weather": weather.get("weather"),
        "temperature": weather.get("temperature"),
        "feels_like": weather.get("feels_like"),
        "humidity": weather.get("humidity"),
        "wind_direction": weather.get("wind_direction"),
        "wind_power": weather.get("wind_power"),
        "wind_speed": weather.get("wind_speed"),
        "precipitation": weather.get("precipitation"),
        "uv": weather.get("uv"),
        "aqi": weather.get("aqi"),
        "aqi_primary": weather.get("aqi_primary"),
        "source": weather.get("source"),
        "updatedAt": weather.get("updatedAt"),
        "lat": weather.get("lat", args.get("lat")),
        "lon": weather.get("lon", args.get("lon")),
    }


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="get_weather",
            description="获取指定城市或坐标的实时天气与环境快照",
            handler=get_weather_tool,
        )
    )
