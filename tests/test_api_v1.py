from fastapi.testclient import TestClient

from backend.agent.memory_store import get_memory_store
from backend.agent.health_profile_store import get_health_profile_store
from backend.main import app


client = TestClient(app)


def test_rag_evidence_endpoint_returns_items() -> None:
    response = client.get("/api/v1/rag/evidence", params={"query": "跑步建议"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "跑步建议"
    assert payload["items"]


def test_rag_evidence_endpoint_returns_empty_list_without_mock_fallback(monkeypatch) -> None:
    class EmptyRetriever:
        def retrieve(self, query: str):
            assert query == "不存在的证据"
            return []

    monkeypatch.setattr("backend.api.v1.get_retriever", lambda: EmptyRetriever())
    response = client.get("/api/v1/rag/evidence", params={"query": "不存在的证据"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "不存在的证据"
    assert payload["items"] == []


def test_status_endpoint_returns_capabilities() -> None:
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api"]["available"] is True
    assert "llm" in payload
    assert "speech" in payload
    assert "weather" in payload


def test_status_endpoint_reports_weather_probe(monkeypatch) -> None:
    monkeypatch.setenv("UAPIS_BASE_URL", "https://uapis.cn/api/v1")
    monkeypatch.setenv("WEATHER_STATUS_PROBE", "1")

    async def fake_probe() -> tuple[bool, str]:
        return True, ""

    monkeypatch.setattr("backend.api.v1.probe_weather_upstream", fake_probe)
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["weather"]["source"] == "uapis+open-meteo"
    assert payload["weather"]["reason"] == "uapis reachable, open-meteo backup available"


def test_status_endpoint_keeps_weather_available_when_uapis_probe_fails(monkeypatch) -> None:
    monkeypatch.setenv("UAPIS_BASE_URL", "https://uapis.cn/api/v1")
    monkeypatch.setenv("WEATHER_STATUS_PROBE", "1")

    async def fake_probe() -> tuple[bool, str]:
        return False, "timeout"

    monkeypatch.setattr("backend.api.v1.probe_weather_upstream", fake_probe)
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["weather"]["available"] is True
    assert payload["weather"]["source"] == "uapis+open-meteo"
    assert "open-meteo backup available" in payload["weather"]["reason"]


def test_status_endpoint_allows_local_dev_cors_origin() -> None:
    response = client.options(
        "/api/v1/status",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_health_profile_roundtrip_endpoint() -> None:
    user_id = "api-test-user"
    create_response = client.post(
        "/api/v1/profile",
        json={
            "user_id": user_id,
            "display_name": "API 用户",
            "identity_summary": "关注通勤与天气变化",
            "preferences": ["提前提醒", "真实数据"],
            "goals": ["准时通勤"],
            "conditions": ["rheumatism"],
            "note": "api test",
            "consent": True,
            "sensitivity": {"humidity": 70},
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["user_id"] == user_id
    assert created["display_name"] == "API 用户"
    assert created["preferences"] == ["提前提醒", "真实数据"]
    assert created["conditions"] == ["rheumatism"]

    fetch_response = client.get(f"/api/v1/profile/{user_id}")
    assert fetch_response.status_code == 200
    fetched = fetch_response.json()
    assert fetched["user_id"] == user_id
    assert fetched["identity_summary"] == "关注通勤与天气变化"
    assert fetched["sensitivity"]["humidity"] == 70

    delete_response = client.delete(f"/api/v1/profile/{user_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"


def test_health_profile_returns_404_when_missing() -> None:
    response = client.get("/api/v1/profile/missing-profile-user")
    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"]["code"] == "NOT_FOUND"


def test_create_task_persists_to_backend() -> None:
    response = client.post(
        "/api/v1/tasks",
        json={
            "type": "commute",
            "scheduled_time": "2026-03-23T08:00:00+08:00",
            "priority": 6,
            "metadata": {"source": "test"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "scheduled"
    assert payload["task_id"] > 0
    assert payload["source"] == "sqlite"
    assert payload["createdAt"]

    list_response = client.get("/api/v1/tasks")
    assert list_response.status_code == 200
    items = list_response.json()
    assert any(item["task_id"] == payload["task_id"] for item in items)


def test_profile_analysis_endpoint_returns_persona() -> None:
    user_id = "profile-analysis-user"
    create_response = client.post(
        "/api/v1/profile",
        json={
            "user_id": user_id,
            "display_name": "分析用户",
            "identity_summary": "每天关注通勤和运动安排",
            "preferences": ["可执行建议", "提前提示"],
            "goals": ["降低淋雨概率", "保持晨跑"],
            "constraints": ["早高峰时间紧"],
            "important_locations": ["徐汇", "公司"],
            "work_context": "工作日固定通勤",
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
    assert payload["display_name"] == "分析用户"
    assert payload["persona"]
    assert isinstance(payload["tags"], list)
    assert "summary" in payload
    assert isinstance(payload["scenario_preferences"], list)
    assert isinstance(payload["strategy_recommendations"], list)
    assert payload["memory_count"] >= 2


def test_profile_analysis_returns_404_when_health_profile_missing() -> None:
    user_id = "missing-profile-analysis-user"
    get_memory_store().clear_session(user_id)
    response = client.get(f"/api/v1/profile/analyze/{user_id}")
    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"]["code"] == "NOT_FOUND"


def test_query_endpoint_degrades_without_llm(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    async def fake_resolve_weather_data(**kwargs):
        return {
            "city": "上海",
            "weather": "多云",
            "temperature": 16,
            "feels_like": 17,
            "humidity": 70,
            "wind_direction": "北风",
            "wind_power": "1级",
            "precipitation": 0,
            "uv": 0,
            "aqi": 57,
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)

    response = client.post(
        "/api/v1/query",
        json={
            "query": "明早上海骑行通勤要带雨衣吗",
            "city": "上海",
            "sessionId": "query-no-llm-user",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["advice"]
    assert payload["decision"]["riskLevel"] in {"low", "medium", "high"}
    assert any("rules_only:" in item for item in payload["sources"])
    assert payload["traceId"]
    assert isinstance(payload["followUps"], list)


def test_query_profile_summary_is_empty_without_health_profile(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    async def fake_resolve_weather_data(**kwargs):
        return {
            "city": "北京",
            "weather": "晴",
            "temperature": 18,
            "feels_like": 18,
            "humidity": 40,
            "wind_direction": "西北风",
            "wind_power": "2级",
            "precipitation": 0,
            "uv": 3,
            "aqi": 42,
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)

    user_id = "query-without-health-profile-user"
    get_memory_store().clear_session(user_id)
    get_health_profile_store().delete_profile(user_id)

    response = client.post(
        "/api/v1/query",
        json={
            "query": "今天通勤要不要带雨具？",
            "city": "北京",
            "sessionId": user_id,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["profileSummary"] is None


def test_health_profile_compat_wrapper_roundtrip() -> None:
    user_id = "compat-health-profile-user"
    create_response = client.post(
        "/api/v1/health/profile",
        json={
            "user_id": user_id,
            "display_name": "兼容用户",
            "conditions": ["allergy"],
            "note": "春季敏感",
            "consent": True,
        },
    )
    assert create_response.status_code == 200
    fetch_response = client.get(f"/api/v1/health/profile/{user_id}")
    assert fetch_response.status_code == 200
    payload = fetch_response.json()
    assert payload["display_name"] == "兼容用户"
    assert payload["conditions"] == ["allergy"]
    delete_response = client.delete(f"/api/v1/health/profile/{user_id}")
    assert delete_response.status_code == 200


def test_forecast_prefers_city_and_adcode_for_upstream(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    async def fake_resolve_weather_data(**kwargs):
        captured["city"] = kwargs.get("city")
        captured["adcode"] = kwargs.get("adcode")
        return {
            "city": "上海",
            "weather": "小雨",
            "temperature": 13,
            "aqi": 62,
            "wind_power": "4级",
            "forecast": [{"date": "2026-03-22", "tmin": 10, "tmax": 16, "uv": 2.0}],
            "hourly": [{"ts": "2026-03-22T08:00:00+08:00", "temp": 13, "pop": 0.4}],
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.get(
        "/api/v1/forecast",
        params={"lat": 31.23, "lon": 121.53, "city": "上海", "adcode": "310000"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert captured == {"city": "上海", "adcode": "310000"}
    assert payload["source"] == "uapis"


def test_forecast_passes_coordinates_to_upstream(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_resolve_weather_data(**kwargs):
        captured.update(kwargs)
        return {
            "city": "北京",
            "temperature": 14,
            "aqi": 66,
            "wind_power": "2级",
            "forecast": [{"date": "2026-03-22", "temp_min": 8, "temp_max": 18, "uv_index": 3}],
            "hourly_forecast": [{"time": "2026-03-22 08:00:00", "temperature": 14, "precip": 30}],
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.get("/api/v1/forecast", params={"lat": 39.9042, "lon": 116.4074})
    assert response.status_code == 200
    payload = response.json()
    assert captured["lat"] == 39.9042
    assert captured["lon"] == 116.4074
    assert payload["location"]["city"] == "北京"
    assert payload["daily"][0]["tmin"] == 8
    assert payload["daily"][0]["tmax"] == 18
    assert payload["hourly"][0]["temp"] == 14


def test_forecast_allows_city_without_coordinates(monkeypatch) -> None:
    async def fake_resolve_weather_data(**kwargs):
        return {
            "city": "杭州",
            "source": "uapis",
            "forecast": [{"date": "2026-03-22", "tmin": 12, "tmax": 18, "uv": 3.0}],
            "hourly": [{"ts": "2026-03-22T08:00:00+08:00", "temp": 16, "pop": 0.2}],
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.get("/api/v1/forecast", params={"city": "杭州"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "uapis"
    assert payload["location"]["lat"] is None
    assert payload["location"]["lon"] is None


def test_forecast_normalizes_openmeteo_payload(monkeypatch) -> None:
    async def fake_resolve_weather_data(**kwargs):
        return {
            "city": "北京",
            "province": "北京市",
            "temperature": 14.2,
            "aqi": 61,
            "wind_speed": 3.1,
            "forecast": [{"date": "2026-03-23", "tmin": 8.0, "tmax": 18.0, "uv": 4.5}],
            "hourly": [{"ts": "2026-03-23T10:00:00+08:00", "temp": 14.5, "pop": 0.12}],
            "source": "open-meteo",
            "updatedAt": "2026-03-23T09:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.get("/api/v1/forecast", params={"lat": 39.9042, "lon": 116.4074})
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "open-meteo"
    assert payload["location"]["name"] == "北京市"
    assert payload["current"]["aqi"] == 61
    assert payload["daily"][0]["uv"] == 4.5
    assert payload["hourly"][0]["pop"] == 0.12


def test_aqi_prefers_city_and_adcode_for_upstream(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    async def fake_resolve_weather_data(**kwargs):
        captured["city"] = kwargs.get("city")
        captured["adcode"] = kwargs.get("adcode")
        return {
            "aqi": 59,
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.get(
        "/api/v1/aqi",
        params={"lat": 31.23, "lon": 121.53, "city": "上海", "adcode": "310000"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert captured == {"city": "上海", "adcode": "310000"}
    assert payload["source"] == "uapis"


def test_aqi_passes_coordinates_and_maps_primary_pollutant(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_resolve_weather_data(**kwargs):
        captured.update(kwargs)
        return {
            "city": "北京",
            "aqi": 88,
            "aqi_primary": "PM10",
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.get("/api/v1/aqi", params={"lat": 39.9042, "lon": 116.4074})
    assert response.status_code == 200
    payload = response.json()
    assert captured["lat"] == 39.9042
    assert captured["lon"] == 116.4074
    assert payload["aqi"] == 88
    assert payload["primary"] == "PM10"
    assert payload["location"]["city"] == "北京"


def test_aqi_allows_city_without_coordinates(monkeypatch) -> None:
    async def fake_resolve_weather_data(**kwargs):
        return {
            "aqi": 42,
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.get("/api/v1/aqi", params={"city": "杭州"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["aqi"] == 42
    assert payload["source"] == "uapis"


def test_aqi_normalizes_openmeteo_payload(monkeypatch) -> None:
    async def fake_resolve_weather_data(**kwargs):
        return {
            "city": "杭州",
            "province": "浙江省",
            "aqi": 35,
            "aqi_primary": "PM2.5",
            "source": "open-meteo",
            "updatedAt": "2026-03-23T09:20:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.get("/api/v1/aqi", params={"city": "杭州"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "open-meteo"
    assert payload["primary"] == "PM2.5"
    assert payload["location"]["name"] == "浙江省杭州"


def test_stocks_impact_uses_realtime_market_source(monkeypatch) -> None:
    async def fake_fetch_market_impact(region: str, signal: str, horizon: str):
        assert region == "华东"
        assert signal == "降水 + AQI 92"
        assert horizon == "24h"
        return {
            "region": region,
            "updatedAt": "2026-03-22T08:00:00+08:00",
            "weatherSignal": signal,
            "marketBias": "negative",
            "confidence": 0.72,
            "sectors": [
                {"name": "物流", "impact": "negative", "reason": "主力净流出与天气扰动共振"},
            ],
            "drivers": ["降水", "AQI 92"],
            "disclaimer": "仅供参考，不构成投资建议。",
            "source": "eastmoney",
        }

    monkeypatch.setattr("backend.api.v1.fetch_market_impact", fake_fetch_market_impact)
    response = client.get(
        "/api/v1/stocks/impact",
        params={"region": "华东", "signal": "降水 + AQI 92", "horizon": "24h"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "eastmoney"
    assert payload["marketBias"] == "negative"
    assert payload["sectors"][0]["name"] == "物流"


def test_aqi_returns_502_when_upstream_has_no_aqi(monkeypatch) -> None:
    async def fake_resolve_weather_data(**kwargs):
        return {
            "city": "杭州",
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.get("/api/v1/aqi", params={"city": "杭州"})
    assert response.status_code == 502
    payload = response.json()
    assert payload["detail"]["code"] == "UPSTREAM_ERROR"


def test_health_alerts_uses_real_weather_when_location_provided(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_resolve_weather_data(**kwargs):
        captured.update(kwargs)
        return {
            "humidity": 85,
            "feels_like": 8,
            "precipitation": 0.6,
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.get(
        "/api/v1/health/alerts/demo-user",
        params={"lat": 39.9042, "lon": 116.4074, "city": "北京"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert captured["lat"] == 39.9042
    assert captured["lon"] == 116.4074
    assert payload["source"] == "uapis"


def test_query_ignores_placeholder_location_name_and_uses_coordinates(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_resolve_weather_data(**kwargs):
        captured.update(kwargs)
        return {
            "city": "北京",
            "weather": "晴",
            "temperature": 20,
            "feels_like": 20,
            "humidity": 30,
            "wind_direction": "西风",
            "wind_power": "2级",
            "precipitation": 0,
            "uv": 4,
            "aqi": 36,
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.post(
        "/api/v1/query",
        json={
            "query": "现在适合出门吗",
            "location": {"lat": 39.9042, "lon": 116.4074, "name": "当前位置"},
            "sessionId": "placeholder-location-user",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert captured["city"] is None
    assert captured["lat"] == 39.9042
    assert captured["lon"] == 116.4074
    assert payload["entities"]["location"]["name"] == "北京"


def test_query_does_not_inject_mock_health_conditions_when_profile_missing(monkeypatch) -> None:
    user_id = "query-no-profile-health-alerts"
    get_memory_store().clear_session(user_id)
    get_health_profile_store().delete_profile(user_id)

    async def fake_resolve_weather_data(**kwargs):
        return {
            "city": "北京",
            "weather": "晴",
            "temperature": 20,
            "feels_like": 20,
            "humidity": 30,
            "wind_direction": "西风",
            "wind_power": "2级",
            "precipitation": 0,
            "uv": 4,
            "aqi": 36,
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.post(
        "/api/v1/query",
        json={
            "query": "今天空气怎么样",
            "city": "北京",
            "sessionId": user_id,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["healthAlerts"] == []
    assert payload["healthRiskLevel"] == "low"


def test_query_discards_malformed_llm_decision_and_keeps_rule_fields(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")

    async def fake_resolve_weather_data(**kwargs):
        return {
            "city": "上海",
            "weather": "多云",
            "temperature": 15,
            "feels_like": 16,
            "humidity": 76,
            "wind_direction": "东北风",
            "wind_power": "1级",
            "precipitation": 0,
            "uv": 0,
            "aqi": 69,
            "source": "uapis",
            "updatedAt": "2026-03-22T21:26:56+08:00",
        }

    async def fake_enrich_decision(**kwargs):
        return {
            "advice": "需要确保输出的JSON格式正确，包含 advice riskLevel reasons actions。",
            "riskLevel": "首先，检查环境数据中的天气情况。",
            "reasons": ["需要确保输出 JSON 格式正确", "["],
            "actions": ["生成最终的 JSON 响应"],
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    monkeypatch.setattr("backend.api.v1.enrich_decision", fake_enrich_decision)

    response = client.post(
        "/api/v1/query",
        json={
            "query": "明早上海骑行通勤要带雨衣吗",
            "city": "上海",
            "sessionId": "query-malformed-llm-user",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["riskLevel"] in {"low", "medium", "high"}
    assert "json" not in payload["decision"]["advice"].lower()
    assert all("json" not in item.lower() for item in payload["decision"]["reasons"])


def test_query_environment_time_prefers_weather_updated_at_when_request_time_missing(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    async def fake_resolve_weather_data(**kwargs):
        return {
            "city": "北京",
            "weather": "晴",
            "temperature": 20,
            "feels_like": 20,
            "humidity": 30,
            "wind_direction": "西风",
            "wind_power": "2级",
            "precipitation": 0,
            "uv": 4,
            "aqi": 36,
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)

    response = client.post(
        "/api/v1/query",
        json={
            "query": "现在适合出门吗",
            "city": "北京",
            "sessionId": "query-environment-time-user",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"]["time"] == "2026-03-22T08:00:00+08:00"


def test_health_alerts_without_profile_do_not_use_mock_conditions(monkeypatch) -> None:
    user_id = "health-alerts-no-profile"
    get_health_profile_store().delete_profile(user_id)

    async def fake_resolve_weather_data(**kwargs):
        return {
            "humidity": 85,
            "feels_like": 8,
            "precipitation": 0.6,
            "source": "uapis",
            "updatedAt": "2026-03-22T08:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1._resolve_weather_data", fake_resolve_weather_data)
    response = client.get(
        f"/api/v1/health/alerts/{user_id}",
        params={"lat": 39.9042, "lon": 116.4074},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["alerts"] == []
    assert payload["riskLevel"] == "low"


def test_misc_weather_skips_loopback_ip_when_city_is_provided(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    async def fake_fetch_weather(**kwargs):
        captured["city"] = kwargs.get("city")
        captured["adcode"] = kwargs.get("adcode")
        captured["client_ip"] = kwargs.get("client_ip")
        return {"city": "上海", "source": "uapis", "weather": "晴", "aqi": 41}

    monkeypatch.setattr("backend.api.v1.fetch_weather", fake_fetch_weather)
    response = client.get(
        "/api/v1/misc/weather",
        params={"city": "上海", "adcode": "310000", "lang": "zh"},
    )
    assert response.status_code == 200
    assert response.json()["source"] == "uapis"
    assert captured == {"city": "上海", "adcode": "310000", "client_ip": None}


def test_misc_weather_reverse_geocodes_when_only_lat_lon_provided(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    async def fake_reverse_geocode(lat: float, lon: float):
        assert lat == 39.9042
        assert lon == 116.4074
        return "北京", None

    async def fake_fetch_weather(**kwargs):
        captured["city"] = kwargs.get("city")
        captured["adcode"] = kwargs.get("adcode")
        captured["client_ip"] = kwargs.get("client_ip")
        return {"city": "北京", "source": "uapis", "weather": "晴", "aqi": 36}

    monkeypatch.setattr("backend.api.v1.reverse_geocode", fake_reverse_geocode)
    monkeypatch.setattr("backend.api.v1.fetch_weather", fake_fetch_weather)

    response = client.get(
        "/api/v1/misc/weather",
        params={"lat": 39.9042, "lon": 116.4074, "lang": "zh"},
    )
    assert response.status_code == 200
    assert response.json()["city"] == "北京"
    assert captured == {"city": "北京", "adcode": None, "client_ip": None}


def test_misc_weather_falls_back_to_openmeteo_when_uapis_fails(monkeypatch) -> None:
    async def fake_fetch_weather(**kwargs):
        raise __import__("backend.data.uapis_weather", fromlist=["UapisError"]).UapisError(
            503,
            {"code": "SERVICE_UNAVAILABLE", "message": "uapis offline"},
        )

    async def fake_openmeteo_weather(lat, lon, **kwargs):
        assert lat == 39.9042
        assert lon == 116.4074
        return {
            "city": "北京",
            "province": "北京市",
            "weather": "晴",
            "temperature": 18.5,
            "humidity": 35,
            "wind_power": "2级",
            "wind_speed": 2.4,
            "aqi": 46,
            "aqi_primary": "PM2.5",
            "forecast": [{"date": "2026-03-23", "tmin": 10, "tmax": 21, "text": "晴"}],
            "hourly": [{"ts": "2026-03-23T09:00:00+08:00", "temp": 18.5, "pop": 0.0}],
            "indices": [{"type": "sport", "level": "适宜", "desc": "适合户外运动"}],
            "source": "open-meteo",
            "updatedAt": "2026-03-23T09:00:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1.fetch_weather", fake_fetch_weather)
    monkeypatch.setattr("backend.api.v1.fetch_openmeteo_weather", fake_openmeteo_weather)

    response = client.get(
        "/api/v1/misc/weather",
        params={
            "lat": 39.9042,
            "lon": 116.4074,
            "lang": "zh",
            "extended": "true",
            "forecast": "true",
            "hourly": "true",
            "indices": "true",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "open-meteo"
    assert payload["city"] == "北京"
    assert payload["aqi"] == 46
    assert payload["forecast"]
    assert payload["hourly"]


def test_misc_weather_backfills_openmeteo_when_uapis_missing_aqi_and_forecast(monkeypatch) -> None:
    async def fake_fetch_weather(**kwargs):
        return {
            "city": "上海",
            "province": "上海市",
            "weather": "多云",
            "temperature": 17,
            "source": "uapis",
            "updatedAt": "2026-03-23T09:10:00+08:00",
        }

    async def fake_openmeteo_weather(lat, lon, **kwargs):
        assert lat == 31.23
        assert lon == 121.53
        return {
            "city": "上海",
            "province": "上海市",
            "aqi": 52,
            "aqi_primary": "PM10",
            "forecast": [{"date": "2026-03-23", "tmin": 12, "tmax": 19, "text": "多云"}],
            "hourly": [{"ts": "2026-03-23T10:00:00+08:00", "temp": 18, "pop": 0.2}],
            "indices": [{"type": "air", "level": "良", "desc": "空气良好"}],
            "source": "open-meteo",
            "updatedAt": "2026-03-23T09:15:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1.fetch_weather", fake_fetch_weather)
    monkeypatch.setattr("backend.api.v1.fetch_openmeteo_weather", fake_openmeteo_weather)

    response = client.get(
        "/api/v1/misc/weather",
        params={
            "lat": 31.23,
            "lon": 121.53,
            "lang": "zh",
            "forecast": "true",
            "hourly": "true",
            "indices": "true",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "uapis+open-meteo"
    assert payload["weather"] == "多云"
    assert payload["aqi"] == 52
    assert payload["forecast"][0]["tmax"] == 19
    assert payload["hourly"][0]["temp"] == 18


def test_misc_weather_uses_openmeteo_geocode_when_city_has_no_coordinates(monkeypatch) -> None:
    async def fake_fetch_weather(**kwargs):
        raise __import__("backend.data.uapis_weather", fromlist=["UapisError"]).UapisError(
            503,
            {"code": "SERVICE_UNAVAILABLE", "message": "uapis offline"},
        )

    async def fake_geocode_city(city: str):
        assert city == "杭州"
        return 30.2741, 120.1551, "杭州", "浙江省"

    async def fake_openmeteo_weather(lat, lon, **kwargs):
        assert lat == 30.2741
        assert lon == 120.1551
        assert kwargs["city"] == "杭州"
        assert kwargs["province"] == "浙江省"
        return {
            "city": "杭州",
            "province": "浙江省",
            "weather": "小雨",
            "temperature": 15,
            "aqi": 38,
            "source": "open-meteo",
            "updatedAt": "2026-03-23T08:30:00+08:00",
        }

    monkeypatch.setattr("backend.api.v1.fetch_weather", fake_fetch_weather)
    monkeypatch.setattr("backend.api.v1.geocode_city", fake_geocode_city)
    monkeypatch.setattr("backend.api.v1.fetch_openmeteo_weather", fake_openmeteo_weather)

    response = client.get("/api/v1/misc/weather", params={"city": "杭州", "lang": "zh"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "open-meteo"
    assert payload["city"] == "杭州"
    assert payload["province"] == "浙江省"


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
