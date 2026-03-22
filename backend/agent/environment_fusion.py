from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _wind_level(wind_power: Optional[str]) -> Optional[int]:
    if not wind_power:
        return None
    digits = [int(ch) for ch in wind_power if ch.isdigit()]
    if digits:
        return int(sum(digits) / len(digits))
    if "微" in wind_power:
        return 2
    if "小" in wind_power:
        return 3
    if "中" in wind_power:
        return 5
    if "大" in wind_power:
        return 7
    if "强" in wind_power:
        return 9
    if "烈" in wind_power:
        return 10
    return None


def _time_bucket(dt: datetime) -> str:
    hour = dt.hour
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 13:
        return "noon"
    if 13 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


def _comfort_index(temp: Optional[float], humidity: Optional[float], wind_level: Optional[int]) -> Optional[int]:
    if temp is None:
        return None
    base = 100 - abs(temp - 22) * 3
    if humidity is not None:
        base -= abs(humidity - 50) * 0.5
    if wind_level is not None:
        base -= wind_level * 2
    return max(0, min(100, int(base)))


def build_environment_snapshot(
    weather: Dict[str, Any],
    *,
    event_time: Optional[datetime],
) -> Dict[str, Any]:
    now = event_time or datetime.now()
    temperature = _to_float(weather.get("temperature"))
    feels_like = _to_float(weather.get("feels_like"))
    humidity = _to_float(weather.get("humidity"))
    precipitation = _to_float(weather.get("precipitation"))
    uv = _to_float(weather.get("uv"))
    aqi = _to_int(weather.get("aqi"))
    wind_level = _wind_level(weather.get("wind_power"))

    risk_flags: List[str] = []
    weather_text = str(weather.get("weather") or "")
    if "雨" in weather_text or (precipitation is not None and precipitation > 0):
        risk_flags.append("rain")
    if "雪" in weather_text:
        risk_flags.append("snow")
    if "雷" in weather_text:
        risk_flags.append("storm")
    if aqi is not None and aqi >= 150:
        risk_flags.append("air_quality")
    if uv is not None and uv >= 7:
        risk_flags.append("uv")
    if temperature is not None and (temperature <= 0 or temperature >= 35):
        risk_flags.append("temperature_extreme")
    if wind_level is not None and wind_level >= 6:
        risk_flags.append("wind")

    return {
        "time": now.isoformat(),
        "timeBucket": _time_bucket(now),
        "weather": {
            "status": weather.get("weather"),
            "temperature": temperature,
            "feelsLike": feels_like,
            "humidity": humidity,
            "windDirection": weather.get("wind_direction"),
            "windPower": weather.get("wind_power"),
            "precipitation": precipitation,
            "uv": uv,
            "aqi": aqi,
        },
        "comfortIndex": _comfort_index(temperature or feels_like, humidity, wind_level),
        "riskFlags": risk_flags,
        "sources": ["weather", "time"],
    }
