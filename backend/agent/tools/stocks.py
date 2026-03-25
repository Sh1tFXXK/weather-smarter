from __future__ import annotations

from typing import Any, Dict

from backend.agent.tools.base import ToolRegistry, ToolSpec
from backend.data.market_realtime import fetch_market_impact


async def query_stock_impact_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    return await fetch_market_impact(
        region=str(args.get("region") or "华东"),
        signal=str(args.get("weather_signal") or args.get("signal") or ""),
        horizon=str(args.get("horizon") or "24h"),
    )


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="query_stock_impact",
            description="分析当前天气对各行业板块的潜在影响",
            handler=query_stock_impact_tool,
        )
    )
