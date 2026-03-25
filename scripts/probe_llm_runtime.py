from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.llm_router import enrich_decision, llm_status
from scripts.backend_env import build_backend_env


async def main() -> None:
    os.environ.update(build_backend_env())
    ok, reason = llm_status()
    if not ok:
        raise RuntimeError(reason)

    decision = await enrich_decision(
        intent="commute_decision",
        query="明早七点在上海骑行通勤，需要带雨衣吗？",
        locale="zh-CN",
        weather={
            "weather": "小雨",
            "temperature": 12,
            "feels_like": 10,
            "humidity": 82,
            "wind_direction": "东北风",
            "wind_power": "4级",
            "precipitation": 1.2,
            "uv": 1.5,
            "aqi": 68,
        },
        environment={
            "time": "2026-03-22T07:00:00+08:00",
            "timeBucket": "morning_peak",
            "weather": {"status": "小雨", "temperature": 12, "aqi": 68},
            "comfortIndex": 58,
            "riskFlags": ["rain", "wind"],
            "sources": ["probe"],
        },
        base_decision={
            "advice": "建议携带轻便雨衣，注意路滑。",
            "riskLevel": "medium",
            "reasons": ["有降雨", "骑行路面湿滑"],
            "actions": ["带雨衣", "提前出发"],
        },
        memory=[],
        rag=[
            {
                "id": "commute_rain",
                "title": "雨天骑行",
                "content": "雨天骑行应降低速度并做好防水准备。",
                "tags": ["commute"],
                "domain": "travel",
                "score": 0.8,
            }
        ],
    )
    if not decision:
        raise RuntimeError("LLM returned no decision")
    print(json.dumps(decision, ensure_ascii=False))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"ERROR {exc}")
        sys.exit(1)
