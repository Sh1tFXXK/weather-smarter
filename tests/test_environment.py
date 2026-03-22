from datetime import datetime

from backend.agent.environment_fusion import build_environment_snapshot


def test_environment_snapshot_risk_flags() -> None:
    weather = {
        "weather": "小雨",
        "temperature": 12,
        "feels_like": 10,
        "humidity": 85,
        "wind_power": "3级",
        "precipitation": 1.2,
        "uv": 1.0,
        "aqi": 60,
    }
    snapshot = build_environment_snapshot(weather, event_time=datetime(2026, 3, 14, 8, 0, 0))
    assert "rain" in snapshot["riskFlags"]
