from backend.agent.decision_rules import make_intent_decision


def test_sport_decision_reasons() -> None:
    advice, risk_level, reasons, actions = make_intent_decision(
        "sport_decision",
        {
            "weather": "晴",
            "temperature": 20,
            "feels_like": 20,
            "precipitation": 0,
            "wind_power": "3级",
            "aqi": 50,
        },
        {"activity": "running", "date": "tomorrow"},
    )
    assert risk_level == "low"
    assert "适合" in advice
    assert reasons
    assert actions
