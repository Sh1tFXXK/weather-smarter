from __future__ import annotations

from typing import Any, Dict, List, Tuple

from backend.decision.utils import to_float


def evaluate_diet(weather: Dict[str, Any]) -> Tuple[str, str, List[str], List[str]]:
    reasons: List[str] = []
    actions: List[str] = []

    temp = to_float(weather.get("feels_like")) or to_float(weather.get("temperature"))
    humidity = to_float(weather.get("humidity"))

    if temp is not None and temp > 30:
        reasons.append("当前高温")
        actions.append("多饮水、多吃水果")
    elif temp is not None and temp < 5:
        reasons.append("当前寒冷")
        actions.append("适合温热食物／汤类")

    if humidity and humidity > 80:
        reasons.append("湿度较高")
        actions.append("饮食清淡，避免油腻")

    if not actions:
        return (
            "当前没有明显环境异常，保持平衡饮食即可。",
            "low",
            [],
            [],
        )

    return (
        "根据环境调整饮食即可。",
        "low",
        reasons,
        actions,
    )
