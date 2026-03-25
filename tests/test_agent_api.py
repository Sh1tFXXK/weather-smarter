from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_agent_run_returns_trajectory_and_tools(monkeypatch) -> None:
    async def fake_weather(args):
        return {
            "city": "北京",
            "weather": "小雨",
            "temperature": 12,
            "aqi": 68,
            "source": "uapis",
            "updatedAt": "2026-03-24T08:00:00+08:00",
        }

    async def fake_forecast(args):
        return {
            "hourly": [{"ts": "2026-03-25T08:00:00+08:00", "temp": 11, "pop": 0.73}],
            "daily": [{"date": "2026-03-25", "tmin": 10, "tmax": 15, "uv": 2}],
            "source": "uapis",
            "updatedAt": "2026-03-24T08:00:00+08:00",
        }

    async def fake_profile(args):
        return {
            "user_id": "u1",
            "profile": {"conditions": ["asthma"], "sensitivity": {"humidity": 70}},
            "found": True,
            "source": "profile:sqlite",
        }

    async def fake_memory(args):
        return {
            "sessionId": "s1",
            "items": [{"role": "user", "content": "明早通勤要带伞吗"}],
            "count": 1,
            "source": "memory:sqlite",
        }

    async def fake_health(args):
        assert args["weather"]["weather"] == "小雨"
        assert args["profile"]["conditions"] == ["asthma"]
        return {
            "riskLevel": "medium",
            "alerts": [{"title": "哮喘注意湿冷"}],
            "source": "uapis",
        }

    monkeypatch.setattr("backend.agent.tools.weather.get_weather_tool", fake_weather)
    monkeypatch.setattr("backend.agent.tools.forecast.get_forecast_tool", fake_forecast)
    monkeypatch.setattr("backend.agent.tools.profile.get_user_profile_tool", fake_profile)
    monkeypatch.setattr("backend.agent.tools.memory.recall_memory_tool", fake_memory)
    monkeypatch.setattr("backend.agent.tools.profile.assess_health_risk_tool", fake_health)

    from backend.agent.tools import get_tool_registry

    get_tool_registry.cache_clear()

    response = client.post(
        "/api/v1/agent/run",
        json={
            "goal": "明天早上 8 点通勤，要带伞吗？我有哮喘。",
            "city": "北京",
            "session_id": "s1",
            "user_id": "u1",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"]
    assert "get_weather" in payload["toolsUsed"]
    assert "get_forecast" in payload["toolsUsed"]
    assert "get_user_profile" in payload["toolsUsed"]
    assert "assess_health_risk" in payload["toolsUsed"]
    assert payload["trajectory"][-1]["type"] == "final"


def test_agent_stream_emits_sse_events(monkeypatch) -> None:
    async def fake_search(args):
        return {"query": args["query"], "items": [{"title": "证据", "content": "内容"}], "count": 1, "source": "rag:tfidf"}

    monkeypatch.setattr("backend.agent.tools.rag.search_knowledge_tool", fake_search)

    from backend.agent.tools import get_tool_registry

    get_tool_registry.cache_clear()

    with client.stream(
        "POST",
        "/api/v1/agent/stream",
        json={"goal": "给我一条知识依据", "session_id": "stream-s1"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "data:" in body
    assert "\"type\":\"final\"" in body
