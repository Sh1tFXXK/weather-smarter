from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ConfigDict

from backend.agent.decision_rules import build_forecast_summary, make_intent_decision
from backend.agent.environment_fusion import build_environment_snapshot
from backend.agent.health_profile_store import get_health_profile_store
from backend.agent.health_rules import evaluate_health_alerts
from backend.agent.profile_analyzer import analyze_user_profile
from backend.agent.llm_router import enrich_decision, llm_status
from backend.agent.memory_store import get_memory_store
from backend.data.mock_data import (
    mock_aqi,
    mock_forecast,
    infer_health_conditions,
    mock_health_conditions,
    mock_health_profile,
    mock_rag,
    mock_stocks,
    mock_task,
    mock_weather,
)
from backend.nlp.intent import get_intent_classifier
from backend.nlp.slots import extract_slots
from backend.rag.retriever import build_query, get_retriever
from backend.tts_asr import SpeechServiceError, get_speech_service

router = APIRouter(prefix="/api/v1")


# -----------------------------
# Security (API Key or Bearer)
# -----------------------------
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def get_auth(
    api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Optional[str]:
    # Accept either header if present. Enforce in production via config if required.
    if api_key:
        return api_key
    if bearer and bearer.credentials:
        return bearer.credentials
    return None


# -----------------------------
# Common Models
# -----------------------------
class ErrorDetail(BaseModel):
    code: str = Field(..., description="Error code enum")
    message: str = Field(..., description="Human readable error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional structured error details"
    )


class ErrorResponse(BaseModel):
    error: ErrorDetail
    traceId: Optional[str] = Field(
        default=None, description="Request trace identifier for debugging"
    )


DEFAULT_ERROR_RESPONSES = {
    400: {
        "model": ErrorResponse,
        "description": "VALIDATION_ERROR: invalid or missing parameters",
    },
    401: {
        "model": ErrorResponse,
        "description": "UNAUTHORIZED: missing or invalid credentials",
    },
    404: {"model": ErrorResponse, "description": "NOT_FOUND: resource not found"},
    429: {
        "model": ErrorResponse,
        "description": "RATE_LIMITED: too many requests",
    },
    502: {"model": ErrorResponse, "description": "UPSTREAM_ERROR: upstream error"},
    500: {"model": ErrorResponse, "description": "SERVER_ERROR: unexpected error"},
    503: {
        "model": ErrorResponse,
        "description": "SERVICE_UNAVAILABLE: upstream unavailable",
    },
}


# -----------------------------
# Decision (query)
# -----------------------------
class Location(BaseModel):
    name: Optional[str] = Field(default=None, description="Display name of location")
    lat: Optional[float] = Field(default=None, description="Latitude in decimal degrees")
    lon: Optional[float] = Field(default=None, description="Longitude in decimal degrees")


class Entities(BaseModel):
    time: Optional[datetime] = Field(default=None, description="ISO time of interest")
    mode: Optional[str] = Field(default=None, description="Commute or activity mode")
    location: Optional[Location] = Field(default=None, description="Resolved location")


class Decision(BaseModel):
    advice: str
    riskLevel: str = Field(description="low|medium|high")
    reasons: List[str] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    query: str = Field(..., description="User natural language question")
    locale: Optional[str] = Field(default="zh-CN")
    lang: Optional[str] = Field(default=None, description="zh|en override for weather data")
    sessionId: Optional[str] = None
    location: Optional[Location] = None
    city: Optional[str] = Field(default=None, description="City name (zh/en)")
    adcode: Optional[str] = Field(default=None, description="Administrative code")
    time: Optional[datetime] = None
    scenario: Optional[str] = Field(default=None, description="Optional hint scenario")
    units: Optional[str] = Field(default="metric", description="metric|imperial")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "明早7点从浦东骑行通勤，需要带雨衣吗？",
                    "locale": "zh-CN",
                    "sessionId": "abc-123",
                    "city": "上海",
                    "location": {"lat": 31.23, "lon": 121.53, "name": "浦东"},
                    "time": "2026-03-13T07:00:00+08:00",
                    "scenario": "commute",
                    "units": "metric",
                }
            ]
        }
    )


class NLUResult(BaseModel):
    intent: str
    slots: Dict[str, Optional[str]]


class MemoryItem(BaseModel):
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str


class EnvironmentSnapshot(BaseModel):
    time: str
    timeBucket: str
    weather: Dict[str, Any]
    comfortIndex: Optional[int] = None
    riskFlags: List[str]
    sources: List[str]


class EvidenceItem(BaseModel):
    id: str
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    domain: Optional[str] = None
    score: Optional[float] = None


class HealthProfileRequest(BaseModel):
    user_id: str
    conditions: List[str] = Field(default_factory=list)
    note: Optional[str] = None
    consent: bool = True
    sensitivity: Optional[Dict[str, Any]] = None


class HealthProfileResponse(BaseModel):
    user_id: str
    conditions: List[str]
    note: Optional[str] = None
    consent: bool = True
    sensitivity: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: str
    source: str = "mock"


class HealthAlertsResponse(BaseModel):
    user_id: str
    alerts: List[Dict[str, Any]]
    riskLevel: str


class ProfileAnalysisResponse(BaseModel):
    user_id: str
    persona: str
    tags: List[str]
    top_interest: str
    risk_preference: str
    execution_preference: str
    adoption_tendency: str
    condition_count: int
    memory_count: int
    profile_completeness: str
    summary: str
    scenario_preferences: List[Dict[str, Any]]
    strategy_recommendations: List[str]
    evidence: Dict[str, Any]


class StocksImpactResponse(BaseModel):
    region: str
    updatedAt: str
    weatherSignal: str
    marketBias: str
    confidence: float
    sectors: List[Dict[str, Any]]
    drivers: List[str]
    disclaimer: str
    source: str = "mock"


class RagResponse(BaseModel):
    query: str
    items: List[EvidenceItem]


class ASRRequest(BaseModel):
    audioBase64: str = Field(..., description="Base64 encoded audio bytes")
    filename: str = Field(default="speech.webm")
    contentType: str = Field(default="audio/webm")
    language: Optional[str] = Field(default="zh", description="Language hint, e.g. zh/en")
    prompt: Optional[str] = Field(default=None, description="Optional transcription hint")


class ASRResponse(BaseModel):
    text: str
    language: Optional[str] = None
    durationMs: Optional[int] = None
    provider: str
    model: str


class TTSRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize")
    voice: str = Field(default="alloy")
    format: str = Field(default="mp3", description="mp3|wav|opus|aac|flac")
    instructions: Optional[str] = Field(default=None, description="Voice style hint")


class TTSResponse(BaseModel):
    audioBase64: str
    mimeType: str
    provider: str
    model: str
    voice: str


class QueryResponse(BaseModel):
    intent: Optional[str] = None
    entities: Entities
    forecastSummary: Optional[str] = None
    decision: Decision
    nlu: Optional[NLUResult] = None
    environment: Optional[EnvironmentSnapshot] = None
    evidence: Optional[List[EvidenceItem]] = None
    memory: Optional[List[MemoryItem]] = None
    healthAlerts: Optional[List[Dict[str, Any]]] = None
    healthRiskLevel: Optional[str] = None
    profileSummary: Optional[ProfileAnalysisResponse] = None
    followUps: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    traceId: Optional[str] = None


@router.post(
    "/query",
    tags=["Decision"],
    response_model=QueryResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="自然语言决策：解析意图并生成建议",
    description="将自然语言问题解析为意图与实体，结合天气/规则/记忆输出可解释建议",
)
async def post_query(
    payload: QueryRequest,
    request: Request,
    _auth: Optional[str] = Depends(get_auth),
) -> QueryResponse:
    # Always use mock data for this implementation.
    classifier = get_intent_classifier()
    intent = classifier.predict(payload.query)
    slots = extract_slots(payload.query)
    if payload.scenario:
        intent = payload.scenario

    city = payload.city or slots.get("city") or (payload.location.name if payload.location else None)
    adcode = payload.adcode
    locale = (payload.locale or "zh-CN").lower()
    lang = payload.lang or ("en" if locale.startswith("en") else "zh")
    weather = mock_weather(city=city, adcode=adcode, lang=lang, extended=True)

    weather_city = weather.get("city")
    weather_province = weather.get("province")
    if weather_city and weather_province:
        if weather_city in weather_province:
            weather_name = weather_province
        elif weather_province in weather_city:
            weather_name = weather_city
        else:
            weather_name = f"{weather_province}{weather_city}"
    else:
        weather_name = weather_city or weather_province or city

    if payload.location:
        loc = Location(
            name=payload.location.name or weather_name,
            lat=payload.location.lat,
            lon=payload.location.lon,
        )
    else:
        loc = Location(name=weather_name, lat=None, lon=None)

    if intent == "greeting":
        advice = "你好！可以问我天气、出行、穿衣、运动建议。"
        risk_level = "low"
        reasons = []
        actions = []
    else:
        advice, risk_level, reasons, actions = make_intent_decision(intent, weather, slots)
    base_decision = {
        "advice": advice,
        "riskLevel": risk_level,
        "reasons": reasons,
        "actions": actions,
    }
    forecast_summary = build_forecast_summary(weather)
    environment = EnvironmentSnapshot(
        **build_environment_snapshot(weather, event_time=payload.time)
    )
    rag_query = build_query(
        query=payload.query,
        intent=intent,
        slots=slots,
        environment=environment.model_dump(),
    )
    rag_items = get_retriever().retrieve(rag_query)
    if not rag_items:
        rag_items = mock_rag(rag_query)
    evidence = [EvidenceItem(**item) for item in rag_items]

    memory_store = None
    memory_history: Optional[List[Dict[str, Any]]] = None
    if payload.sessionId:
        memory_store = get_memory_store()
        memory_history = memory_store.list_messages(session_id=payload.sessionId, limit=6)

    llm_ok, llm_reason = llm_status()
    if not llm_ok:
        raise HTTPException(
            status_code=503,
            detail={"code": "LLM_NOT_CONFIGURED", "message": llm_reason},
        )
    llm_decision = await enrich_decision(
        intent=intent,
        query=payload.query,
        locale=payload.locale,
        weather=weather,
        environment=environment.model_dump(),
        base_decision=base_decision,
        memory=memory_history,
        rag=rag_items,
    )
    if not llm_decision:
        raise HTTPException(
            status_code=502,
            detail={"code": "LLM_FAILED", "message": "LLM did not return valid decision"},
        )
    advice = llm_decision["advice"]
    risk_level = llm_decision["riskLevel"]
    reasons = llm_decision.get("reasons", [])
    actions = llm_decision.get("actions", [])

    memory_preview: Optional[List[MemoryItem]] = None
    profile_summary: Optional[ProfileAnalysisResponse] = None
    if payload.sessionId:
        if memory_store is None:
            memory_store = get_memory_store()
        memory_store.add_message(
            session_id=payload.sessionId,
            role="user",
            content=payload.query,
            metadata={"intent": intent, "slots": slots},
        )
        assistant_text = advice if intent == "greeting" else f"{forecast_summary} {advice}".strip()
        memory_store.add_message(
            session_id=payload.sessionId,
            role="assistant",
            content=assistant_text,
            metadata={
                "decision": {
                    "advice": advice,
                    "riskLevel": risk_level,
                    "reasons": reasons,
                    "actions": actions,
                },
                "intent": intent,
                "scenario": payload.scenario or intent,
                "user_preference_signals": {
                    "actionCount": len(actions),
                    "riskLevel": risk_level,
                    "hasEvidence": bool(evidence),
                    "hasFollowUpRecommendation": bool(actions),
                },
                "environment": environment.model_dump(),
                "evidence": [item.model_dump() for item in evidence],
            },
        )
        memory_preview = [
            MemoryItem(**item)
            for item in memory_store.list_messages(session_id=payload.sessionId, limit=6)
        ]
        profile = get_health_profile_store().get_profile(payload.sessionId)
        profile_summary = ProfileAnalysisResponse(
            **analyze_user_profile(
                user_id=payload.sessionId,
                health_profile=profile,
                memory=memory_store.list_messages(session_id=payload.sessionId, limit=12),
            )
        )

    health_alerts: Optional[List[Dict[str, Any]]] = None
    health_risk_level: Optional[str] = None
    if intent != "greeting":
        user_id = payload.sessionId or (payload.location.name if payload.location else None) or "guest"
        profile_store = get_health_profile_store()
        profile = profile_store.get_profile(user_id)
        if profile:
            conditions = profile.get("conditions", [])
            sensitivity = profile.get("sensitivity", {})
        else:
            inferred = infer_health_conditions(payload.query)
            conditions = inferred or mock_health_conditions(user_id)
            sensitivity = {}
        health_alerts = evaluate_health_alerts(
            conditions=conditions,
            weather=weather,
            sensitivity=sensitivity,
        )
        health_risk_level = (
            "high"
            if any(alert.get("riskLevel") == "high" for alert in health_alerts)
            else "medium" if health_alerts else "low"
        )

    return QueryResponse(
        intent=intent,
        entities=Entities(time=payload.time, mode=slots.get("activity"), location=loc),
        forecastSummary=forecast_summary,
        decision=Decision(
            advice=advice,
            riskLevel=risk_level,
            reasons=reasons,
            actions=actions,
        ),
        nlu=NLUResult(intent=intent, slots=slots),
        environment=environment,
        evidence=evidence,
        memory=memory_preview,
        healthAlerts=health_alerts,
        healthRiskLevel=health_risk_level,
        profileSummary=profile_summary,
        followUps=[],
        sources=["mock:weather", "mock:rag"],
        traceId=None,
    )


@router.get(
    "/memory/{session_id}",
    tags=["Memory"],
    response_model=List[MemoryItem],
    responses=DEFAULT_ERROR_RESPONSES,
    summary="获取会话记忆",
)
def get_memory(session_id: str, limit: int = Query(20, ge=1, le=200)) -> List[MemoryItem]:
    memory_store = get_memory_store()
    return [
        MemoryItem(**item)
        for item in memory_store.list_messages(session_id=session_id, limit=limit)
    ]


@router.delete(
    "/memory/{session_id}",
    tags=["Memory"],
    responses=DEFAULT_ERROR_RESPONSES,
    summary="清理会话记忆",
)
def clear_memory(session_id: str) -> Dict[str, str]:
    memory_store = get_memory_store()
    memory_store.clear_session(session_id)
    return {"status": "cleared", "sessionId": session_id}


# -----------------------------
# Health Profile (Mock)
# -----------------------------
@router.post(
    "/health/profile",
    tags=["Health"],
    response_model=HealthProfileResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="创建/更新健康档案（模拟）",
)
def upsert_health_profile(payload: HealthProfileRequest) -> HealthProfileResponse:
    store = get_health_profile_store()
    profile = store.upsert_profile(
        user_id=payload.user_id,
        conditions=payload.conditions,
        note=payload.note,
        consent=payload.consent,
        sensitivity=payload.sensitivity,
    )
    return HealthProfileResponse(**profile)


@router.get(
    "/health/profile/{user_id}",
    tags=["Health"],
    response_model=HealthProfileResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="获取健康档案（模拟）",
)
def get_health_profile(user_id: str) -> HealthProfileResponse:
    store = get_health_profile_store()
    data = store.get_profile(user_id)
    if not data:
        data = mock_health_profile(user_id, mock_health_conditions(user_id), None, True)
    return HealthProfileResponse(**data)


@router.delete(
    "/health/profile/{user_id}",
    tags=["Health"],
    responses=DEFAULT_ERROR_RESPONSES,
    summary="删除健康档案（模拟）",
)
def delete_health_profile(user_id: str) -> Dict[str, str]:
    store = get_health_profile_store()
    existed = store.delete_profile(user_id)
    return {"status": "deleted" if existed else "missing", "user_id": user_id}


@router.get(
    "/health/alerts/{user_id}",
    tags=["Health"],
    response_model=HealthAlertsResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="获取健康提醒（模拟）",
)
def get_health_alerts(user_id: str) -> HealthAlertsResponse:
    store = get_health_profile_store()
    profile = store.get_profile(user_id)
    if profile:
        conditions = profile.get("conditions", [])
        sensitivity = profile.get("sensitivity", {})
    else:
        conditions = mock_health_conditions(user_id)
        sensitivity = {}
    alerts = evaluate_health_alerts(
        conditions=conditions,
        weather=mock_weather(city="上海", extended=True),
        sensitivity=sensitivity,
    )
    risk_level = (
        "high"
        if any(alert.get("riskLevel") == "high" for alert in alerts)
        else "medium" if alerts else "low"
    )
    return HealthAlertsResponse(user_id=user_id, alerts=alerts, riskLevel=risk_level)


@router.get(
    "/profile/analyze/{user_id}",
    tags=["Profile"],
    response_model=ProfileAnalysisResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="用户画像分析",
)
def analyze_profile(user_id: str) -> ProfileAnalysisResponse:
    profile_store = get_health_profile_store()
    memory_store = get_memory_store()
    profile = profile_store.get_profile(user_id)
    memory = memory_store.list_messages(session_id=user_id, limit=12)
    result = analyze_user_profile(user_id=user_id, health_profile=profile, memory=memory)
    return ProfileAnalysisResponse(**result)


# -----------------------------
# Stocks Impact (Mock)
# -----------------------------
@router.get(
    "/stocks/impact",
    tags=["Market"],
    response_model=StocksImpactResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="股市影响分析（模拟）",
)
def get_stocks_impact(
    region: str = Query("华东"),
    signal: str = Query("雨天+湿冷"),
    horizon: str = Query("24h"),
) -> StocksImpactResponse:
    data = mock_stocks(region, signal)
    return StocksImpactResponse(**data)


# -----------------------------
# RAG Evidence (Mock)
# -----------------------------
@router.get(
    "/rag/evidence",
    tags=["RAG"],
    response_model=RagResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="知识检索证据（模拟）",
)
def get_rag_evidence(query: str = Query(...)) -> RagResponse:
    rag_items = get_retriever().retrieve(query)
    if not rag_items:
        rag_items = mock_rag(query)
    items = [EvidenceItem(**item) for item in rag_items]
    return RagResponse(query=query, items=items)


@router.post(
    "/asr",
    tags=["Speech"],
    response_model=ASRResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="语音识别（ASR）",
)
async def transcribe_audio(
    payload: ASRRequest,
    _auth: Optional[str] = Depends(get_auth),
) -> ASRResponse:
    service = get_speech_service()
    try:
        result = await service.transcribe(
            audio_b64=payload.audioBase64,
            filename=payload.filename,
            content_type=payload.contentType,
            language=payload.language,
            prompt=payload.prompt,
        )
    except SpeechServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        )
    return ASRResponse(
        text=result["text"],
        language=result.get("language"),
        durationMs=result.get("durationMs"),
        provider=result["provider"],
        model=result["model"],
    )


@router.post(
    "/tts",
    tags=["Speech"],
    response_model=TTSResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="语音合成（TTS）",
)
async def synthesize_audio(
    payload: TTSRequest,
    _auth: Optional[str] = Depends(get_auth),
) -> TTSResponse:
    service = get_speech_service()
    try:
        result = await service.synthesize(
            text=payload.text,
            voice=payload.voice,
            format_=payload.format,
            instructions=payload.instructions,
        )
    except SpeechServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        )
    return TTSResponse(**result)


# -----------------------------
# Weather (UAPIS Proxy)
# -----------------------------
@router.get(
    "/misc/weather",
    tags=["Weather"],
    responses=DEFAULT_ERROR_RESPONSES,
    summary="天气查询（UAPIS 代理）",
    description="支持 adcode/city 或按 IP 定位查询，并透传扩展气象字段与生活指数参数。",
)
async def get_misc_weather(
    request: Request,
    city: Optional[str] = Query(None, description="City name, supports zh/en"),
    adcode: Optional[str] = Query(None, description="Administrative code, higher priority than city"),
    lang: str = Query("zh", pattern="^(zh|en)$"),
    extended: Optional[bool] = Query(None, description="Return extended fields"),
    forecast: Optional[bool] = Query(None, description="Return multi-day forecast (max 7 days)"),
    hourly: Optional[bool] = Query(None, description="Return hourly forecast (24 hours)"),
    minutely: Optional[bool] = Query(None, description="Return minutely precipitation (domestic only)"),
    indices: Optional[bool] = Query(None, description="Return life indices (zh only)"),
    _auth: Optional[str] = Depends(get_auth),
) -> Dict[str, Any]:
    return mock_weather(
        city=city,
        adcode=adcode,
        lang=lang,
        extended=extended,
        forecast=forecast,
        hourly=hourly,
        minutely=minutely,
        indices=indices,
    )


# -----------------------------
# Forecast
# -----------------------------
class ForecastCurrent(BaseModel):
    ts: datetime
    temp: float
    wind: Optional[float] = None
    aqi: Optional[int] = None


class ForecastHourly(BaseModel):
    ts: datetime
    temp: float
    pop: Optional[float] = Field(default=None, description="probability of precipitation")


class ForecastDaily(BaseModel):
    date: date
    tmin: Optional[float] = None
    tmax: Optional[float] = None
    uv: Optional[float] = None


class ForecastResponse(BaseModel):
    location: Dict[str, Any]
    current: Optional[ForecastCurrent] = None
    hourly: List[ForecastHourly] = Field(default_factory=list)
    daily: List[ForecastDaily] = Field(default_factory=list)


@router.get(
    "/forecast",
    tags=["Forecast"],
    response_model=ForecastResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="天气预报：当前/逐小时/逐日",
)
async def get_forecast(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    hours: int = Query(24, ge=1, le=168),
    days: int = Query(7, ge=1, le=14),
    units: str = Query("metric"),
    lang: str = Query("zh-CN"),
    tz: Optional[str] = Query(None),
    _auth: Optional[str] = Depends(get_auth),
) -> ForecastResponse:
    data = mock_forecast(lat, lon, hours, days, tz or "Asia/Shanghai")
    current = data.get("current")
    hourly = data.get("hourly", [])
    daily = data.get("daily", [])
    return ForecastResponse(
        location=data.get("location", {"lat": lat, "lon": lon, "tz": tz or "Asia/Shanghai"}),
        current=ForecastCurrent(**current) if current else None,
        hourly=[ForecastHourly(**item) for item in hourly],
        daily=[ForecastDaily(**item) for item in daily],
    )


# -----------------------------
# AQI
# -----------------------------
class AQIResponse(BaseModel):
    location: Dict[str, Any]
    ts: datetime
    aqi: int
    primary: Optional[str] = Field(default=None, description="Primary pollutant")


class TaskCreate(BaseModel):
    type: str
    scheduled_time: datetime
    priority: Optional[int] = Field(default=5, ge=1, le=10)
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "sport",
                    "scheduled_time": "2026-03-13T06:30:00+08:00",
                    "priority": 5,
                    "metadata": {"location": {"lat": 31.23, "lon": 121.53}},
                }
            ]
        }
    )


class TaskCreateResponse(BaseModel):
    task_id: int
    status: str = Field(description="scheduled|queued|failed")


@router.get(
    "/aqi",
    tags=["AQI"],
    response_model=AQIResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="空气质量（AQI）",
)
async def get_aqi(
    lat: float = Query(...),
    lon: float = Query(...),
    units: str = Query("metric"),
    _auth: Optional[str] = Depends(get_auth),
) -> AQIResponse:
    data = mock_aqi(lat, lon)
    return AQIResponse(
        location=data.get("location", {"lat": lat, "lon": lon}),
        ts=datetime.fromisoformat(data["ts"]),
        aqi=data["aqi"],
        primary=data.get("primary"),
    )


@router.post(
    "/tasks",
    tags=["Tasks"],
    response_model=TaskCreateResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="创建任务/提醒",
)
async def create_task(
    payload: TaskCreate,
    _idempotency_key: Optional[str] = Query(
        default=None, alias="Idempotency-Key", description="Optional idempotency key"
    ),
    _auth: Optional[str] = Depends(get_auth),
) -> TaskCreateResponse:
    data = mock_task(payload.type, payload.scheduled_time.isoformat(), payload.priority or 5)
    return TaskCreateResponse(task_id=data["task_id"], status=data["status"])
