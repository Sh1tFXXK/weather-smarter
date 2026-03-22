from backend.agent.health_rules import evaluate_health_alerts


def test_health_alerts_rheumatism() -> None:
    alerts = evaluate_health_alerts(
        conditions=["rheumatism"],
        weather={"humidity": 85, "feels_like": 8, "precipitation": 1.2},
    )
    assert alerts
    assert alerts[0]["condition"] == "rheumatism"


def test_health_alerts_asthma() -> None:
    alerts = evaluate_health_alerts(
        conditions=["asthma"],
        weather={"aqi": 160, "wind_power": "6级"},
    )
    assert alerts
    assert alerts[0]["condition"] == "asthma"


def test_health_alerts_photosensitivity() -> None:
    alerts = evaluate_health_alerts(
        conditions=["photosensitivity"],
        weather={"uv": 8},
    )
    assert alerts
    assert alerts[0]["condition"] == "photosensitivity"
