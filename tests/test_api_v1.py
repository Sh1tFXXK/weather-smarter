from fastapi.testclient import TestClient

from backend.agent.memory_store import get_memory_store
from backend.main import app


client = TestClient(app)


def test_rag_evidence_endpoint_returns_items() -> None:
    response = client.get("/api/v1/rag/evidence", params={"query": "跑步建议"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "跑步建议"
    assert payload["items"]


def test_health_profile_roundtrip_endpoint() -> None:
    user_id = "api-test-user"
    create_response = client.post(
        "/api/v1/health/profile",
        json={
            "user_id": user_id,
            "conditions": ["rheumatism"],
            "note": "api test",
            "consent": True,
            "sensitivity": {"humidity": 70},
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["user_id"] == user_id
    assert created["conditions"] == ["rheumatism"]

    fetch_response = client.get(f"/api/v1/health/profile/{user_id}")
    assert fetch_response.status_code == 200
    fetched = fetch_response.json()
    assert fetched["user_id"] == user_id
    assert fetched["sensitivity"]["humidity"] == 70

    delete_response = client.delete(f"/api/v1/health/profile/{user_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"


def test_profile_analysis_endpoint_returns_persona() -> None:
    user_id = "profile-analysis-user"
    create_response = client.post(
        "/api/v1/health/profile",
        json={
            "user_id": user_id,
            "conditions": ["rheumatism", "allergy"],
            "note": "湿冷天容易关节不适，平时也关注通勤天气",
            "consent": True,
            "sensitivity": {"humidity": 75},
        },
    )
    assert create_response.status_code == 200

    memory_store = get_memory_store()
    memory_store.clear_session(user_id)
    memory_store.add_message(
        session_id=user_id,
        role="user",
        content="明早骑行通勤要带雨衣吗？我关节容易不舒服",
        metadata={"intent": "commute_decision"},
    )
    memory_store.add_message(
        session_id=user_id,
        role="user",
        content="今天空气一般，还适合跑步吗？",
        metadata={"intent": "sport_decision"},
    )

    analysis_response = client.get(f"/api/v1/profile/analyze/{user_id}")
    assert analysis_response.status_code == 200
    payload = analysis_response.json()
    assert payload["user_id"] == user_id
    assert payload["persona"]
    assert isinstance(payload["tags"], list)
    assert "summary" in payload
    assert isinstance(payload["scenario_preferences"], list)
    assert isinstance(payload["strategy_recommendations"], list)
    assert payload["memory_count"] >= 2


def test_profile_analysis_uses_structured_assistant_metadata() -> None:
    user_id = "query-profile-user"
    memory_store = get_memory_store()
    memory_store.clear_session(user_id)
    memory_store.add_message(
        session_id=user_id,
        role="assistant",
        content="明早建议携带轻便雨衣，避免长时间暴露在湿冷环境。",
        metadata={
            "scenario": "commute_decision",
            "evidence": [{"title": "降雨概率升高"}],
            "decision": {
                "advice": "建议携带轻便雨衣，避免长时间暴露在湿冷环境。",
                "riskLevel": "medium",
                "actions": ["带雨衣", "注意保暖"],
            },
            "user_preference_signals": {
                "actionCount": 2,
                "riskLevel": "medium",
                "hasEvidence": True,
                "hasFollowUpRecommendation": True,
            },
        },
    )
    memory = memory_store.list_messages(session_id=user_id, limit=6)
    assistant_items = [item for item in memory if item["role"] == "assistant"]
    assert assistant_items
    metadata = assistant_items[-1]["metadata"]
    assert "user_preference_signals" in metadata
    assert "scenario" in metadata

    analysis_response = client.get(f"/api/v1/profile/analyze/{user_id}")
    assert analysis_response.status_code == 200
    payload = analysis_response.json()
    assert "execution_preference" in payload
    assert "adoption_tendency" in payload
