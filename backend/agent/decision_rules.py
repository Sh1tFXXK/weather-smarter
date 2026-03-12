from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


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
    numbers = re.findall(r"\d+", wind_power)
    if numbers:
        if len(numbers) >= 2:
            return round((int(numbers[0]) + int(numbers[1])) / 2)
        return int(numbers[0])

    mapping = [
        ("微", 2),
        ("小", 3),
        ("中", 5),
        ("大", 7),
        ("强", 9),
        ("烈", 10),
    ]
    for key, level in mapping:
        if key in wind_power:
            return level
    return None


def build_forecast_summary(data: Dict[str, Any]) -> str:
    weather = data.get("weather")
    temperature = _to_float(data.get("temperature"))
    feels_like = _to_float(data.get("feels_like"))
    humidity = _to_float(data.get("humidity"))
    wind_direction = data.get("wind_direction")
    wind_power = data.get("wind_power")
    aqi = _to_int(data.get("aqi"))

    parts: List[str] = []
    if weather:
        parts.append(str(weather))
    if temperature is not None:
        temp_part = f"{temperature:.1f}℃"
        if feels_like is not None:
            temp_part += f"(体感{feels_like:.1f}℃)"
        parts.append(temp_part)
    if wind_direction or wind_power:
        wind_part = f"{wind_direction or ''}{wind_power or ''}".strip()
        if wind_part:
            parts.append(wind_part)
    if humidity is not None:
        parts.append(f"湿度{humidity:.0f}%")
    if aqi is not None:
        parts.append(f"AQI {aqi}")

    return "，".join(parts) if parts else "天气信息获取成功"


def make_decision(data: Dict[str, Any]) -> Tuple[str, str, List[str], List[str]]:
    weather_text = str(data.get("weather") or "")
    weather_text_lower = weather_text.lower()

    temperature = _to_float(data.get("feels_like")) or _to_float(data.get("temperature"))
    precipitation = _to_float(data.get("precipitation"))
    uv = _to_float(data.get("uv"))
    aqi = _to_int(data.get("aqi"))
    wind_level = _wind_level(data.get("wind_power"))

    reasons: List[str] = []
    actions: List[str] = []
    score = 0

    rain_keywords = ["雨", "阵雨", "雷", "暴雨", "冰雹", "台风"]
    snow_keywords = ["雪", "雨夹雪", "冰"]

    if any(k in weather_text for k in rain_keywords) or (precipitation is not None and precipitation > 0):
        score += 2
        reasons.append("可能有降水")
        actions.extend(["携带雨具", "注意路面湿滑"])

    if any(k in weather_text for k in snow_keywords):
        score += 2
        reasons.append("可能有雨雪或结冰")
        actions.extend(["注意防滑", "视情况减少骑行/步行"])

    if "雷" in weather_text or "storm" in weather_text_lower:
        score += 2
        reasons.append("雷暴天气风险")
        actions.append("避免空旷区域停留")

    if temperature is not None:
        if temperature <= -5 or temperature >= 38:
            score += 3
            reasons.append("体感温度极端")
            if temperature <= -5:
                actions.append("加强保暖")
            else:
                actions.append("尽量避免正午户外活动")
        elif temperature <= 0 or temperature >= 35:
            score += 2
            reasons.append("体感温度偏极端")
            if temperature <= 0:
                actions.append("增添保暖衣物")
            else:
                actions.append("注意补水降温")
        elif temperature <= 5 or temperature >= 30:
            score += 1
            reasons.append("体感温度偏冷/偏热")
            if temperature <= 5:
                actions.append("适当加衣")
            else:
                actions.append("适当防晒")

    if aqi is not None:
        if aqi >= 200:
            score += 3
            reasons.append("空气质量较差")
            actions.extend(["减少户外活动", "必要时佩戴口罩"])
        elif aqi >= 150:
            score += 2
            reasons.append("空气质量偏差")
            actions.append("减少剧烈户外运动")
        elif aqi >= 100:
            score += 1
            reasons.append("空气质量一般")
            actions.append("关注敏感人群防护")

    if uv is not None:
        if uv >= 7:
            score += 2
            reasons.append("紫外线较强")
            actions.extend(["涂抹防晒霜", "佩戴帽子/太阳镜"])
        elif uv >= 5:
            score += 1
            reasons.append("紫外线偏强")
            actions.append("适度防晒")

    if wind_level is not None:
        if wind_level >= 8:
            score += 2
            reasons.append("风力较大")
            actions.append("注意防风加固物品")
        elif wind_level >= 6:
            score += 1
            reasons.append("风力偏大")
            actions.append("注意防风")

    if score >= 5:
        risk_level = "high"
    elif score >= 3:
        risk_level = "medium"
    else:
        risk_level = "low"

    actions = list(dict.fromkeys(actions))
    reasons = list(dict.fromkeys(reasons))

    if not actions:
        advice = "天气条件较稳定，按需安排出行。"
    elif risk_level == "high":
        advice = "建议谨慎出行，" + "，".join(actions) + "。"
    else:
        advice = "建议" + "，".join(actions) + "。"

    return advice, risk_level, reasons, actions
