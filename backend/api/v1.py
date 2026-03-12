from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ConfigDict

from backend.agent.decision_rules import build_forecast_summary, make_decision
from backend.data.uapis_weather import UapisError, fetch_weather

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


class QueryResponse(BaseModel):
    intent: Optional[str] = None
    entities: Entities
    forecastSummary: Optional[str] = None
    decision: Decision
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
    city = payload.city or (payload.location.name if payload.location else None)
    adcode = payload.adcode
    locale = (payload.locale or "zh-CN").lower()
    lang = payload.lang or ("en" if locale.startswith("en") else "zh")
    client_ip = request.client.host if request.client else None

    try:
        weather = await fetch_weather(
            city=city,
            adcode=adcode,
            lang=lang,
            extended=True,
            forecast=False,
            hourly=False,
            minutely=False,
            indices=False,
            client_ip=client_ip,
        )
    except UapisError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.payload)

    weather_city = weather.get("city")
    weather_province = weather.get("province")
    name_parts = [p for p in [weather_province, weather_city] if p]
    weather_name = "".join(name_parts) if name_parts else city

    if payload.location:
        loc = Location(
            name=payload.location.name or weather_name,
            lat=payload.location.lat,
            lon=payload.location.lon,
        )
    else:
        loc = Location(name=weather_name, lat=None, lon=None)

    advice, risk_level, reasons, actions = make_decision(weather)
    forecast_summary = build_forecast_summary(weather)

    return QueryResponse(
        intent=payload.scenario or "commute",
        entities=Entities(time=payload.time, mode=None, location=loc),
        forecastSummary=forecast_summary,
        decision=Decision(
            advice=advice,
            riskLevel=risk_level,
            reasons=reasons,
            actions=actions,
        ),
        followUps=[],
        sources=["uapis:misc/weather"],
        traceId=None,
    )


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
    client_ip = request.client.host if request.client else None
    try:
        return await fetch_weather(
            city=city,
            adcode=adcode,
            lang=lang,
            extended=extended,
            forecast=forecast,
            hourly=hourly,
            minutely=minutely,
            indices=indices,
            client_ip=client_ip,
        )
    except UapisError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.payload)


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
    now = datetime.now()
    return ForecastResponse(
        location={"lat": lat, "lon": lon, "tz": tz or "Asia/Shanghai"},
        current=ForecastCurrent(ts=now, temp=14.2, wind=3, aqi=55),
        hourly=[ForecastHourly(ts=now, temp=14.5, pop=0.4)],
        daily=[ForecastDaily(date=now.date(), tmin=11, tmax=16, uv=4)],
    )


# -----------------------------
# AQI
# -----------------------------
class AQIResponse(BaseModel):
    location: Dict[str, Any]
    ts: datetime
    aqi: int
    primary: Optional[str] = Field(default=None, description="Primary pollutant")


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
    now = datetime.now()
    return AQIResponse(location={"lat": lat, "lon": lon}, ts=now, aqi=55, primary="PM2.5")


# -----------------------------
# Tasks
# -----------------------------
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
    return TaskCreateResponse(task_id=1024, status="scheduled")
