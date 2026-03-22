from backend.decision.decision_engine import evaluate_intent_decision


def test_travel_decision_rain() -> None:
    advice, risk, reasons, actions = evaluate_intent_decision(
        "travel_decision",
        {"weather": "小雨", "precipitation": 3, "wind_power": "2级", "temperature": 18},
        {"activity": "commute"},
    )
    assert "雨具" in "".join(actions)
    assert risk in ("medium", "high")


def test_health_decision_pm25() -> None:
    advice, risk, reasons, actions = evaluate_intent_decision(
        "health_decision",
        {"weather": "霾", "aqi": 160, "temperature": 22, "uv": 3},
    )
    assert "室外" not in advice or "减少" in advice
    assert any("空气" in reason for reason in reasons)
    assert risk in ("medium", "high")


def test_diet_decision_hot() -> None:
    advice, risk, reasons, actions = evaluate_intent_decision(
        "diet_decision",
        {"weather": "晴", "temperature": 32, "humidity": 60},
    )
    assert "多饮水" in "".join(actions)
    assert risk == "low"


def test_schedule_decision_precip() -> None:
    advice, risk, reasons, actions = evaluate_intent_decision(
        "schedule_decision",
        {"weather": "雨", "precipitation": 2},
        {"activity": "running"},
    )
    assert "室内" in "".join(actions)
