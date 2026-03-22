from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.decision.utils import to_float, wind_level


def evaluate_travel(weather: Dict[str, Any], slots: Optional[Dict[str, Any]] = None) -> Tuple[str, str, List[str], List[str]]:
    reasons: List[str] = []
    actions: List[str] = []
    score = 0

    temp = to_float(weather.get("feels_like")) or to_float(weather.get("temperature"))
    precip = to_float(weather.get("precipitation"))
    wind = wind_level(weather.get("wind_power"))
    status = str(weather.get("weather") or "").lower()

    if precip and precip > 0:
        score += 2
        reasons.append("可能有降水")
        actions.append("携带雨具")

    if "雨" in status or "storm" in status:
        score += 1
        reasons.append("天气有雨")
        actions.append("避开露天骑行")

    if wind and wind > 8:
        score += 2
        reasons.append("风力偏大")
        actions.append("减少骑行/骑车")
    elif wind and wind >= 6:
        score += 1
        reasons.append("风力稍大")
        actions.append("打稳雨伞")

    if temp is not None:
        if temp < 0:
            score += 2
            reasons.append("体感偏冷")
            actions.append("加强保暖")
        elif temp > 35:
            score += 2
            reasons.append("体感偏热")
            actions.append("避开正午外出")

    if score >= 4:
        risk = "high"
        advice = "当前出行情境风险较高，优先考虑室内或延期。"
    elif score >= 2:
        risk = "medium"
        advice = "天气有一定程度的限制，建议带上雨具/防风装备，降低外出强度。"
    else:
        risk = "low"
        advice = "天气条件较好，适合出行。"

    if not reasons:
        if temp is not None:
            reasons.append("温度舒适")
        elif status:
            reasons.append("天气状态良好")

    if not actions:
        actions.append("按计划出行")

    actions = list(dict.fromkeys(actions))
    reasons = list(dict.fromkeys(reasons))
    return advice, risk, reasons, actions
