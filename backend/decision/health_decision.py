from __future__ import annotations

from typing import Any, Dict, List, Tuple

from backend.decision.utils import to_float, to_int


def evaluate_health(weather: Dict[str, Any]) -> Tuple[str, str, List[str], List[str]]:
    reasons: List[str] = []
    actions: List[str] = []
    score = 0

    pm25 = to_int(weather.get("pm25") or weather.get("air_pollutants", {}).get("pm25"))
    aqi = to_int(weather.get("aqi"))
    temp = to_float(weather.get("feels_like")) or to_float(weather.get("temperature"))
    uv = to_float(weather.get("uv"))
    humidity = to_float(weather.get("humidity"))

    air_quality_value = pm25 or aqi
    if air_quality_value and air_quality_value >= 200:
        score += 3
        reasons.append("空气质量较差")
        actions.append("减少户外高强度活动")
    elif air_quality_value and air_quality_value >= 150:
        score += 2
        reasons.append("空气质量偏差")
        actions.append("减少户外运动强度")
    elif air_quality_value and air_quality_value >= 100:
        score += 1
        reasons.append("空气质量一般")
        actions.append("关注敏感人群防护")

    if temp is not None:
        if temp >= 35:
            score += 2
            reasons.append("高温风险")
            actions.extend(["减少户外暴晒", "注意补水"])
        elif temp <= 0:
            score += 2
            reasons.append("低温风险")
            actions.append("防寒保暖")
        elif temp <= 5:
            score += 1
            reasons.append("体感偏冷")
            actions.append("适量增衣")

    if uv and uv > 7:
        score += 1
        reasons.append("紫外线强")
        actions.append("涂抹防晒霜")

    if humidity and humidity > 85:
        score += 1
        reasons.append("湿度高")
        actions.append("注意防潮")

    if score >= 4:
        risk = "high"
        advice = "健康风险较高，减少外出或选室内活动。"
    elif score >= 2:
        risk = "medium"
        advice = "存在环境压力，建议适度调整活动强度。"
    else:
        risk = "low"
        advice = "环境条件适宜，按个人状态安排即可。"

    actions = list(dict.fromkeys(actions))
    reasons = list(dict.fromkeys(reasons))
    return advice, risk, reasons, actions
