from __future__ import annotations

from typing import Any, Dict

from backend.agent.health_profile_store import get_health_profile_store
from backend.agent.health_rules import evaluate_health_alerts
from backend.agent.tools.base import ToolRegistry, ToolSpec


async def get_user_profile_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(args.get("user_id") or "").strip()
    profile = get_health_profile_store().get_profile(user_id) if user_id else None
    return {
        "user_id": user_id,
        "profile": profile,
        "found": bool(profile),
        "source": "profile:sqlite",
    }


async def assess_health_risk_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    weather = args.get("weather") or {}
    profile = args.get("profile") or {}
    alerts = evaluate_health_alerts(
        conditions=profile.get("conditions", []),
        weather=weather,
        sensitivity=profile.get("sensitivity", {}),
    )
    risk_level = (
        "high"
        if any(item.get("riskLevel") == "high" for item in alerts)
        else "medium" if alerts else "low"
    )
    return {
        "riskLevel": risk_level,
        "alerts": alerts,
        "conditionCount": len(profile.get("conditions", [])),
        "source": weather.get("source", "profile+weather"),
    }


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="get_user_profile",
            description="获取用户的长期档案、偏好和约束",
            handler=get_user_profile_tool,
        )
    )
    registry.register(
        ToolSpec(
            name="assess_health_risk",
            description="基于当前环境参数和用户健康状况评估风险",
            handler=assess_health_risk_tool,
        )
    )
