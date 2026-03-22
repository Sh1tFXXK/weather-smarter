from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.decision.utils import to_float, wind_level


def evaluate_schedule(weather: Dict[str, Any], slots: Optional[Dict[str, Any]] = None) -> Tuple[str, str, List[str], List[str]]:
    reasons: List[str] = []
    actions: List[str] = []
    activity = (slots or {}).get("activity") or "活动"

    temp = to_float(weather.get("feels_like")) or to_float(weather.get("temperature"))
    precip = to_float(weather.get("precipitation"))
    wind = wind_level(weather.get("wind_power"))

    if precip and precip > 0:
        reasons.append("可能有降水")
        actions.append(f"将{activity}改成室内或推迟")
    elif wind and wind >= 8:
        reasons.append("风力较强")
        actions.append(f"将{activity}调整至室内")
    elif temp and (temp <= 0 or temp >= 35):
        reasons.append("温度极端")
        actions.append(f"调整{activity}时段或类型")

    if not actions:
        return (
            f"当前的天气适宜安排{activity}。",
            "low",
            [],
            [],
        )

    return (
        "根据天气调整任务安排。",
        "medium" if (precip and precip > 0) or (wind and wind >= 8) else "low",
        reasons,
        actions,
    )
