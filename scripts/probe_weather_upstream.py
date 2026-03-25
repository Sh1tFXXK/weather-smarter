from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.v1 import _resolve_weather_data
from scripts.backend_env import build_backend_env


async def main() -> None:
    os.environ.update(build_backend_env())
    data = await _resolve_weather_data(
        request=None,
        city="上海",
        adcode="310000",
        lang="zh",
        extended=True,
        forecast=True,
        hourly=True,
        minutely=False,
        indices=True,
    )
    summary = {
        "city": data.get("city"),
        "source": data.get("source"),
        "weather": data.get("weather"),
        "temperature": data.get("temperature"),
        "aqi": data.get("aqi"),
        "updatedAt": data.get("updatedAt"),
        "hasForecast": bool(data.get("forecast")),
        "hasHourly": bool(data.get("hourly")),
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"ERROR {exc}")
        sys.exit(1)
