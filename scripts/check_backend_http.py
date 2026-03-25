from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8000"


def request_json(
    path: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    timeout_s: float = 5,
) -> tuple[int, str]:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as response:
        return response.status, response.read().decode("utf-8")


def wait_until_ready(path: str = "/api/v1/status", timeout_s: int = 30) -> str:
    last_error = ""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            _, text = request_json(path, timeout_s=15)
            return text
        except Exception as exc:
            last_error = str(exc)
            time.sleep(1)
    raise RuntimeError(last_error or "backend not ready")


def main() -> None:
    startup_session_id = f"startup-check-{int(time.time())}"
    print("CHECK status")
    status_text = wait_until_ready()
    status_payload = json.loads(status_text)
    llm_status = status_payload.get("llm") or {}
    if os.getenv("EXPECT_LLM", "1") in {"1", "true", "TRUE"}:
        if not bool(llm_status.get("available")):
            raise RuntimeError(
                "llm unavailable in /api/v1/status: "
                f"{llm_status.get('reason') or 'unknown reason'}"
            )
    print("CHECK docs")
    docs_status, _ = request_json("/docs", timeout_s=10)
    print("CHECK tasks")
    tasks_status, tasks_text = request_json("/api/v1/tasks", timeout_s=10)
    query_body = json.dumps(
        {
            "query": "明早上海骑行通勤要带雨衣吗",
            "city": "上海",
            "adcode": "310000",
            "sessionId": startup_session_id,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    print("CHECK query")
    query_status, query_text = request_json(
        "/api/v1/query",
        method="POST",
        body=query_body,
        timeout_s=120,
    )
    query_payload = json.loads(query_text)

    print("CHECK weather")
    weather_status, weather_text = request_json(
        "/api/v1/misc/weather?city=%E4%B8%8A%E6%B5%B7&adcode=310000&lang=zh&extended=true&forecast=true&hourly=true&indices=true",
        timeout_s=20,
    )
    weather_payload = json.loads(weather_text)
    print("CHECK forecast")
    forecast_status, forecast_text = request_json(
        "/api/v1/forecast?lat=31.23&lon=121.53&city=%E4%B8%8A%E6%B5%B7&adcode=310000&hours=24&days=7",
        timeout_s=20,
    )
    forecast_payload = json.loads(forecast_text)
    print("CHECK aqi")
    aqi_status, aqi_text = request_json(
        "/api/v1/aqi?lat=31.23&lon=121.53&city=%E4%B8%8A%E6%B5%B7&adcode=310000",
        timeout_s=20,
    )
    aqi_payload = json.loads(aqi_text)
    print("CHECK stocks")
    stocks_status, stocks_text = request_json(
        "/api/v1/stocks/impact?region=%E5%8D%8E%E4%B8%9C&signal=%E9%99%8D%E6%B0%B4%20%2B%20AQI%2080&horizon=24h",
        timeout_s=20,
    )
    stocks_payload = json.loads(stocks_text)

    if os.getenv("EXPECT_LLM", "1") in {"1", "true", "TRUE"} and "llm" not in query_payload.get("sources", []):
        raise RuntimeError(f"query did not use llm: {query_payload.get('sources')}")
    if os.getenv("EXPECT_REAL_WEATHER", "1") in {"1", "true", "TRUE"}:
        for name, payload in (
            ("status", status_payload.get("weather", {})),
            ("misc/weather", weather_payload),
            ("forecast", forecast_payload),
            ("aqi", aqi_payload),
        ):
            source = payload.get("source")
            if source == "mock" or source == "mock-fallback":
                raise RuntimeError(f"{name} still using mock source: {source}")
        if stocks_payload.get("source") in {"mock", "rules"}:
            raise RuntimeError(f"stocks/impact still using non-realtime source: {stocks_payload.get('source')}")

    print("STATUS", status_text)
    print("DOCS", docs_status)
    print("TASKS", tasks_status, tasks_text)
    print("QUERY", query_status, query_text)
    print("WEATHER", weather_status, weather_text)
    print("FORECAST", forecast_status, forecast_text)
    print("AQI", aqi_status, aqi_text)
    print("STOCKS", stocks_status, stocks_text)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"HTTP_ERROR {exc.code} {exc.read().decode('utf-8', errors='replace')}")
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR {exc}")
        sys.exit(1)
