from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.decision.decision_engine import evaluate_intent_decision
from backend.decision.utils import to_float, to_int, wind_level


def build_forecast_summary(data: Dict[str, Any]) -> str:
    weather_label = data.get("weather")
    temperature = to_float(data.get("temperature"))
    feels_like = to_float(data.get("feels_like"))
    humidity = to_float(data.get("humidity"))
    wind_direction = data.get("wind_direction")
    wind_power_value = data.get("wind_power")
    aqi = to_int(data.get("aqi"))

    parts: List[str] = []
    if weather_label:
        parts.append(str(weather_label))
    if temperature is not None:
        temp_part = f"{temperature:.1f}℃"
        if feels_like is not None:
            temp_part += f"(体感{feels_like:.1f}℃)"
        parts.append(temp_part)
    if wind_direction or wind_power_value:
        wind_desc = f"{wind_direction or ''}{wind_power_value or ''}".strip()
        if wind_desc:
            parts.append(wind_desc)
    if humidity is not None:
        parts.append(f"湿度{humidity:.0f}%")
    if aqi is not None:
        parts.append(f"AQI {aqi}")

    return "，".join(parts) if parts else "天气信息获取成功"


def make_decision(data: Dict[str, Any]) -> Tuple[str, str, List[str], List[str]]:
    weather_text = str(data.get("weather") or "")
    weather_lower = weather_text.lower()
    temperature = to_float(data.get("feels_like")) or to_float(data.get("temperature"))
    precipitation = to_float(data.get("precipitation"))
    uv = to_float(data.get("uv"))
    aqi = to_int(data.get("aqi"))
    wind_level_value = wind_level(data.get("wind_power"))

    reasons: List[str] = []
    actions: List[str] = []
    score = 0

    rain_keywords = ["雨", "阵雨", "雷", "暴雨", "冰雹", "台风"]
    snow_keywords = ["雪", "雨夹雪", "冰"]

    if any(keyword in weather_text for keyword in rain_keywords) or (
        precipitation is not None and precipitation > 0
    ):
        score += 2
        reasons.append("可能有降水")
        actions.extend(["携带雨具", "注意路面湿滑"])

    if any(keyword in weather_text for keyword in snow_keywords):
        score += 2
        reasons.append("可能有雨雪或结冰")
        actions.extend(["注意防滑", "必要时减少户外行走"])

    if "雷" in weather_text or "storm" in weather_lower:
        score += 2
        reasons.append("雷暴天气风险")
        actions.append("避开空旷区域")

    if temperature is not None:
        if temperature <= -5 or temperature >= 38:
            score += 3
            reasons.append("体感温度极端")
            if temperature <= -5:
                actions.append("加强保暖")
            else:
                actions.append("避开正午强光")
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
            actions.extend(["涂抹防晒霜", "佩戴太阳镜/帽子"])
        elif uv >= 5:
            score += 1
            reasons.append("紫外线偏强")
            actions.append("适度防晒")

    if wind_level_value is not None:
        if wind_level_value >= 8:
            score += 2
            reasons.append("风力较大")
            actions.append("注意加固物品")
        elif wind_level_value >= 6:
            score += 1
            reasons.append("风力偏大")
            actions.append("避开高空/骑行")

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


def _clothing_suggestion(temperature: Optional[float]) -> Optional[str]:
    if temperature is None:
        return None
    if temperature < 5:
        return "厚外套"
    if temperature < 15:
        return "外套或薄羽绒"
    if temperature < 25:
        return "长袖或薄外套"
    return "短袖"


def _sport_suitable(
    temperature: Optional[float],
    wind_amount: Optional[int],
    precipitation: Optional[float],
    aqi: Optional[int],
) -> bool:
    if temperature is not None and not (10 <= temperature <= 25):
        return False
    if wind_amount is not None and wind_amount >= 6:
        return False
    if precipitation is not None and precipitation > 0:
        return False
    if aqi is not None and aqi >= 100:
        return False
    return True


def make_intent_decision(
    intent: str, data: Dict[str, Any], slots: Optional[Dict[str, Optional[str]]] = None
) -> Tuple[str, str, List[str], List[str]]:
    specialized = intent in (
        "travel_decision",
        "commute_decision",
        "sport_decision",
        "health_decision",
        "diet_decision",
        "schedule_decision",
    )
    if specialized:
        advice, risk_level, reasons, actions = evaluate_intent_decision(intent, data, slots)
    else:
        advice, risk_level, reasons, actions = make_decision(data)

    if specialized:
        return advice, risk_level, reasons, actions

    temperature = to_float(data.get("feels_like")) or to_float(data.get("temperature"))
    precipitation = to_float(data.get("precipitation"))
    aqi = to_int(data.get("aqi"))
    wind_amount = wind_level(data.get("wind_power"))

    if intent == "umbrella_decision":
        rain_signals = [
            "雨" in str(data.get("weather") or ""),
            precipitation is not None and precipitation > 0,
        ]
        if any(rain_signals):
            advice = "建议带伞。"
            reasons.append("可能有降水")
            actions.append("携带雨具")
        else:
            advice = "一般不需要带伞。"

    if intent == "clothing_decision":
        clothing = _clothing_suggestion(temperature)
        if clothing:
            advice = f"建议穿{clothing}。"
            reasons.append("根据体感温度给出穿衣建议")
            actions.append(f"穿着建议：{clothing}")

    if intent == "sport_decision":
        suitable = _sport_suitable(temperature, wind_amount, precipitation, aqi)
        if suitable:
            advice = "天气条件较好，适合户外运动。"
            actions.append("注意适度热身")
            if temperature is not None:
                reasons.append("温度适宜(10-25℃)")
            if precipitation is not None and precipitation <= 0:
                reasons.append("无明显降水")
            if wind_amount is not None and wind_amount < 6:
                reasons.append("风力较小")
            if aqi is not None and aqi < 100:
                reasons.append("空气质量良好")
        else:
            advice = "不建议高强度户外运动，注意安全。"
            actions.append("选择室内或低强度活动")
            if temperature is not None and not (10 <= temperature <= 25):
                reasons.append("温度不在10-25℃")
            if precipitation is not None and precipitation > 0:
                reasons.append("可能有降水")
            if wind_amount is not None and wind_amount >= 6:
                reasons.append("风力偏大")
            if aqi is not None and aqi >= 100:
                reasons.append("空气质量一般或偏差")

    actions = list(dict.fromkeys(actions))
    reasons = list(dict.fromkeys(reasons))
    return advice, risk_level, reasons, actions
