from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from ipaddress import ip_address
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ConfigDict

from backend.agent.decision_rules import build_forecast_summary, make_intent_decision
from backend.agent.environment_fusion import build_environment_snapshot
from backend.agent.health_profile_store import get_health_profile_store
from backend.agent.health_rules import evaluate_health_alerts
from backend.agent.profile_analyzer import analyze_user_profile
from backend.agent.task_store import get_task_store
from backend.agent.llm_router import enrich_decision, llm_status
from backend.agent.memory_store import get_memory_store
from backend.data.uapis_weather import (
    UAPIS_BASE_URL,
    UapisError,
    fetch_weather,
    probe_weather_upstream,
    weather_status_probe_enabled,
)
from backend.data.market_realtime import MarketDataError, fetch_market_impact
from backend.data.geo import geocode_city, reverse_geocode
from backend.data.openmeteo import fetch_openmeteo_aqi, fetch_openmeteo_weather
from backend.nlp.intent import get_intent_classifier
from backend.nlp.slots import extract_slots
from backend.rag.retriever import build_query, get_retriever
from backend.tts_asr import SpeechServiceError, get_speech_service

router = APIRouter(prefix="/api/v1")

CN_TIMEZONE = timezone(timedelta(hours=8))
_VALID_RISK_LEVELS = {"low", "medium", "high"}
_DECISION_META_MARKERS = (
    "json",
    "markdown",
    "代码块",
    "输出",
    "格式",
    "base_decision",
    "需要确保",
    "生成最终",
    "确认所有信息",
)


def _normalize_timestamp(value: Any, *, fallback: Optional[str] = None) -> Optional[str]:
    if value in (None, ""):
        return fallback
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return fallback
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        text = text.replace(" ", "T")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return fallback
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CN_TIMEZONE)
    return parsed.isoformat()


def _extract_updated_at(payload: Dict[str, Any]) -> str:
    for key in ("updatedAt", "updated_at", "report_time", "reportTime", "ts", "time"):
        normalized = _normalize_timestamp(payload.get(key))
        if normalized:
            return normalized
    return datetime.now(timezone.utc).isoformat()


def _event_time_from_payload(
    value: Optional[datetime],
    weather: Optional[Dict[str, Any]] = None,
) -> Optional[datetime]:
    if value is not None:
        return value
    if weather:
        normalized = _extract_updated_at(weather)
        if normalized:
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                return None
    return None


def _looks_like_meta_response(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    lowered = text.lower()
    if len(text) > 240:
        return True
    return any(marker in lowered or marker in text for marker in _DECISION_META_MARKERS)


def _sanitize_decision_patch(
    value: Optional[Dict[str, Any]],
    *,
    fallback: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    advice = str(value.get("advice") or "").strip()
    risk_level = str(value.get("riskLevel") or "").strip().lower()
    if not advice or _looks_like_meta_response(advice):
        return None
    if risk_level not in _VALID_RISK_LEVELS:
        return None

    def _clean_items(raw: Any) -> List[str]:
        if not isinstance(raw, list):
            return []
        items: List[str] = []
        for item in raw:
            text = str(item or "").strip()
            if not text or text in {"[", "]", "{", "}"} or _looks_like_meta_response(text):
                continue
            items.append(text)
            if len(items) >= 6:
                break
        return items

    reasons = _clean_items(value.get("reasons"))
    actions = _clean_items(value.get("actions"))
    return {
        "advice": advice,
        "riskLevel": risk_level,
        "reasons": reasons if reasons else list(fallback.get("reasons", [])),
        "actions": actions if actions else list(fallback.get("actions", [])),
    }


def _pick_hourly_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("hourly", "hourly_forecast"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            return value
    return []


def _compose_location_name(
    payload: Dict[str, Any],
    *,
    fallback_city: Optional[str] = None,
    fallback_adcode: Optional[str] = None,
) -> Optional[str]:
    city_name = payload.get("city") or fallback_city
    province = payload.get("province")
    if city_name and province:
        if city_name in province:
            return province
        if province in city_name:
            return city_name
        return f"{province}{city_name}"
    return city_name or province or fallback_adcode


_PLACEHOLDER_LOCATION_NAMES = {
    "当前位置",
    "当前地点",
    "自动定位",
    "未定位",
    "未知位置",
    "current location",
    "current-location",
}


def _clean_location_name(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    if text.lower() in _PLACEHOLDER_LOCATION_NAMES:
        return None
    return text


def _extract_public_client_ip(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = ip_address(text)
    except ValueError:
        return None
    return str(parsed) if parsed.is_global else None


def _weather_requires_openmeteo_backfill(
    payload: Dict[str, Any],
    *,
    forecast: Optional[bool],
    hourly: Optional[bool],
    indices: Optional[bool],
    require_aqi: bool,
) -> bool:
    if require_aqi and payload.get("aqi") is None:
        return True
    if forecast and not isinstance(payload.get("forecast"), list):
        return True
    if hourly and not _pick_hourly_items(payload):
        return True
    if indices and not isinstance(payload.get("indices"), list):
        return True
    return False


def _merge_weather_payload(
    primary: Optional[Dict[str, Any]],
    fallback: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(fallback)
    if primary:
        for key, value in primary.items():
            if value is not None:
                merged[key] = value
    fallback_source = str(fallback.get("source") or "open-meteo")
    primary_source = str(primary.get("source") or "uapis") if primary else ""
    if primary and primary_source and primary_source != fallback_source:
        merged["source"] = f"{primary_source}+{fallback_source}"
    else:
        merged["source"] = fallback_source
    merged.setdefault("updatedAt", _extract_updated_at(merged))
    if "hourly" not in merged and isinstance(merged.get("hourly_forecast"), list):
        merged["hourly"] = merged["hourly_forecast"]
    if "forecast" not in merged and isinstance(merged.get("daily"), list):
        merged["forecast"] = merged["daily"]
    return merged


async def _fetch_openmeteo_weather_data(
    *,
    city: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
    lang: str,
    extended: Optional[bool],
    forecast: Optional[bool],
    hourly: Optional[bool],
    minutely: Optional[bool],
    indices: Optional[bool],
    require_aqi: bool,
) -> Dict[str, Any]:
    resolved_city = city
    resolved_province: Optional[str] = None
    resolved_lat = lat
    resolved_lon = lon

    if resolved_lat is None or resolved_lon is None:
        if not city:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "weather upstream unavailable and coordinates could not be resolved",
                },
            )
        geo = await geocode_city(city)
        if not geo:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "SERVICE_UNAVAILABLE",
                    "message": f"failed to geocode location: {city}",
                },
            )
        resolved_lat, resolved_lon, resolved_city, resolved_province = geo

    try:
        openmeteo_payload = await fetch_openmeteo_weather(
            resolved_lat,
            resolved_lon,
            city=resolved_city,
            province=resolved_province,
            lang=lang,
            extended=bool(extended),
            forecast=bool(forecast),
            hourly=bool(hourly),
            minutely=bool(minutely),
            indices=bool(indices),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": f"open-meteo weather fetch failed: {exc}",
            },
        ) from exc
    if require_aqi and openmeteo_payload.get("aqi") is None:
        try:
            aqi_payload = await fetch_openmeteo_aqi(resolved_lat, resolved_lon)
        except Exception:
            aqi_payload = {}
        if aqi_payload.get("aqi") is not None:
            openmeteo_payload["aqi"] = aqi_payload.get("aqi")
            openmeteo_payload["aqi_primary"] = aqi_payload.get("aqi_primary")
            openmeteo_payload.setdefault("ts", aqi_payload.get("ts"))
    openmeteo_payload.setdefault("lat", resolved_lat)
    openmeteo_payload.setdefault("lon", resolved_lon)
    openmeteo_payload.setdefault("updatedAt", _extract_updated_at(openmeteo_payload))
    return openmeteo_payload


async def _resolve_weather_data(
    *,
    request: Optional[Request],
    city: Optional[str],
    adcode: Optional[str],
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    lang: str,
    extended: Optional[bool] = None,
    forecast: Optional[bool] = None,
    hourly: Optional[bool] = None,
    minutely: Optional[bool] = None,
    indices: Optional[bool] = None,
    require_location: bool = False,
    require_aqi: bool = False,
) -> Dict[str, Any]:
    resolved_province: Optional[str] = None
    if not city and not adcode and lat is not None and lon is not None:
        try:
            resolved_city, resolved_province = await reverse_geocode(lat, lon)
        except Exception:
            resolved_city = None
        if resolved_city:
            city = resolved_city

    client_ip: Optional[str] = None
    use_ip_lookup = request is not None and not city and not adcode
    if use_ip_lookup:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = _extract_public_client_ip(forwarded.split(",")[0].strip())
        else:
            client = getattr(request, "client", None)
            host = getattr(client, "host", None)
            client_ip = _extract_public_client_ip(host)

    has_coordinates = lat is not None and lon is not None
    if require_location and not city and not adcode and not client_ip and not has_coordinates:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "LOCATION_REQUIRED",
                "message": "city/adcode or browser coordinates are required for real weather data",
            },
        )

    try:
        data = await fetch_weather(
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
        if isinstance(data, dict):
            data.setdefault("source", "uapis")
            data.setdefault("updatedAt", _extract_updated_at(data))
            if "hourly" not in data and isinstance(data.get("hourly_forecast"), list):
                data["hourly"] = data["hourly_forecast"]
            if "forecast" not in data and isinstance(data.get("daily"), list):
                data["forecast"] = data["daily"]
            if lat is not None:
                data.setdefault("lat", lat)
            if lon is not None:
                data.setdefault("lon", lon)
            if resolved_province:
                data.setdefault("province", resolved_province)
            if not _weather_requires_openmeteo_backfill(
                data,
                forecast=forecast,
                hourly=hourly,
                indices=indices,
                require_aqi=require_aqi,
            ):
                return data
        openmeteo_payload = await _fetch_openmeteo_weather_data(
            city=city or data.get("city"),
            lat=lat,
            lon=lon,
            lang=lang,
            extended=extended,
            forecast=forecast,
            hourly=hourly,
            minutely=minutely,
            indices=indices,
            require_aqi=require_aqi,
        )
        return _merge_weather_payload(data, openmeteo_payload)
    except UapisError as exc:
        try:
            return await _fetch_openmeteo_weather_data(
                city=city,
                lat=lat,
                lon=lon,
                lang=lang,
                extended=extended,
                forecast=forecast,
                hourly=hourly,
                minutely=minutely,
                indices=indices,
                require_aqi=require_aqi,
            )
        except HTTPException:
            detail = exc.payload if isinstance(exc.payload, dict) else None
            if not detail:
                detail = {"code": "UPSTREAM_ERROR", "message": f"weather upstream error {exc.status_code}"}
            raise HTTPException(status_code=exc.status_code, detail=detail)


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


class RecommendationItem(BaseModel):
    title: str
    summary: str
    rationale: List[str] = Field(default_factory=list)


class Recommendations(BaseModel):
    diet: RecommendationItem
    clothing: RecommendationItem
    travel: RecommendationItem
    work: RecommendationItem
    investment: RecommendationItem


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


class ProfileRequest(BaseModel):
    user_id: str
    display_name: Optional[str] = None
    persona: Optional[str] = None
    identity_summary: Optional[str] = None
    role: Optional[str] = None
    organization: Optional[str] = None
    home_base: Optional[str] = None
    family_structure: List[str] = Field(default_factory=list)
    asset_preferences: List[str] = Field(default_factory=list)
    schedule_windows: List[str] = Field(default_factory=list)
    decision_style: Optional[str] = None
    preferences: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    routines: List[str] = Field(default_factory=list)
    important_people: List[str] = Field(default_factory=list)
    important_locations: List[str] = Field(default_factory=list)
    work_context: Optional[str] = None
    long_term_memory: Optional[str] = None
    sensitivity_type: Optional[str] = None
    priority_tags: Optional[List[str]] = None
    conditions: List[str] = Field(default_factory=list)
    note: Optional[str] = None
    consent: bool = True
    sensitivity: Optional[Dict[str, Any]] = None
    profile_version: Optional[str] = "v2"


class ProfileResponse(BaseModel):
    user_id: str
    display_name: Optional[str] = None
    persona: Optional[str] = None
    identity_summary: Optional[str] = None
    role: Optional[str] = None
    organization: Optional[str] = None
    home_base: Optional[str] = None
    family_structure: List[str] = Field(default_factory=list)
    asset_preferences: List[str] = Field(default_factory=list)
    schedule_windows: List[str] = Field(default_factory=list)
    decision_style: Optional[str] = None
    preferences: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    routines: List[str] = Field(default_factory=list)
    important_people: List[str] = Field(default_factory=list)
    important_locations: List[str] = Field(default_factory=list)
    work_context: Optional[str] = None
    long_term_memory: Optional[str] = None
    sensitivity_type: Optional[str] = None
    priority_tags: Optional[List[str]] = None
    conditions: List[str]
    note: Optional[str] = None
    consent: bool = True
    sensitivity: Optional[Dict[str, Any]] = None
    profile_version: Optional[str] = "v2"
    created_at: Optional[str] = None
    updated_at: str
    source: str = "sqlite"


class HealthProfileRequest(ProfileRequest):
    pass


class HealthProfileResponse(ProfileResponse):
    pass


class HealthAlertsResponse(BaseModel):
    user_id: str
    alerts: List[Dict[str, Any]]
    riskLevel: str
    source: str = "sqlite"
    updatedAt: Optional[str] = None


class ProfileAnalysisResponse(BaseModel):
    user_id: str
    display_name: Optional[str] = None
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
    source: str = "location-unresolved"


class RagResponse(BaseModel):
    query: str
    items: List[EvidenceItem]


class ServiceCapability(BaseModel):
    available: bool
    reason: str = ""
    source: Optional[str] = None


class ServiceStatusResponse(BaseModel):
    api: ServiceCapability
    llm: ServiceCapability
    speech: ServiceCapability
    weather: ServiceCapability


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
    recommendations: Recommendations
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


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _weather_signal_parts(weather: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    if weather.get("weather"):
        parts.append(str(weather.get("weather")))
    temp = _safe_float(weather.get("temperature"))
    if temp is not None:
        parts.append(f"{round(temp)}℃")
    precipitation = _safe_float(weather.get("precipitation"))
    if precipitation is not None and precipitation > 0:
        parts.append(f"降水 {precipitation:.1f}mm")
    wind_power = weather.get("wind_power")
    if wind_power:
        parts.append(f"风力 {wind_power}")
    aqi = _safe_int(weather.get("aqi"))
    if aqi is not None:
        parts.append(f"AQI {aqi}")
    return parts


def _build_recommendations(
    *,
    weather: Dict[str, Any],
    profile: Optional[Dict[str, Any]] = None,
    market: Optional[Dict[str, Any]] = None,
    health_alerts: Optional[List[Dict[str, Any]]] = None,
    risk_level: str,
    forecast_summary: str,
) -> Recommendations:
    profile = profile or {}
    health_alerts = health_alerts or []
    temp = _safe_float(weather.get("temperature"))
    feels_like = _safe_float(weather.get("feels_like"))
    humidity = _safe_int(weather.get("humidity"))
    precipitation = _safe_float(weather.get("precipitation")) or 0.0
    wind_speed = _safe_float(weather.get("wind_speed"))
    uv = _safe_float(weather.get("uv"))
    pressure = _safe_float(weather.get("pressure"))
    aqi = _safe_int(weather.get("aqi"))
    aqi_primary = str(weather.get("aqi_primary") or "").strip()
    conditions = [str(item).strip() for item in (profile.get("conditions") or []) if str(item).strip()]
    family_structure = [str(item).strip() for item in (profile.get("family_structure") or []) if str(item).strip()]
    asset_preferences = [str(item).strip() for item in (profile.get("asset_preferences") or []) if str(item).strip()]
    schedule_windows = [str(item).strip() for item in (profile.get("schedule_windows") or []) if str(item).strip()]
    decision_style = str(profile.get("decision_style") or "").strip()
    work_context = str(profile.get("work_context") or "").strip()
    note = str(profile.get("note") or "").strip()

    diet_rationale: List[str] = []
    if temp is not None and temp <= 10:
        diet_title = "偏温热补水"
        diet_summary = "天气偏冷，饮食以热汤、温热主食和稳定补水为主，减少生冷摄入。"
        diet_rationale.append(f"当前温度 {temp:.1f}℃，偏冷时热量和热饮更有利于体感恢复。")
    elif temp is not None and temp >= 28:
        diet_title = "清爽补水优先"
        diet_summary = "气温偏高，优先补水、电解质和清淡饮食，减少高油高盐负担。"
        diet_rationale.append(f"当前温度 {temp:.1f}℃，高温下应优先补水和轻负担饮食。")
    else:
        diet_title = "均衡稳态"
        diet_summary = "当前温度适中，保持蛋白质、蔬果和规律补水即可。"
        if temp is not None:
            diet_rationale.append(f"当前温度 {temp:.1f}℃，无极端冷热压力。")
    if humidity is not None and humidity >= 80:
        diet_rationale.append(f"相对湿度 {humidity}% 偏高，建议减少过甜和过油，避免湿闷感加重。")
    if aqi is not None and aqi >= 100:
        diet_rationale.append(f"AQI {aqi}{f'，首要污染物 {aqi_primary}' if aqi_primary else ''}，可适当增加温水和富含维 C 食物。")
    if conditions:
        diet_rationale.append(f"档案条件 {', '.join(conditions[:3])} 已纳入饮食提醒。")

    clothing_rationale: List[str] = []
    clothing_layers = "短袖/薄层"
    if temp is not None and temp < 8:
        clothing_layers = "厚外套 + 保暖层"
    elif temp is not None and temp < 16:
        clothing_layers = "轻薄外套 + 长袖"
    elif temp is not None and temp > 28:
        clothing_layers = "速干薄衣"
    clothing_title = f"{clothing_layers}为主"
    clothing_summary = f"建议以 {clothing_layers} 为基础，按体感和风雨情况增减。"
    if feels_like is not None:
        clothing_rationale.append(f"体感温度 {feels_like:.1f}℃，比气温更适合作为穿衣基准。")
    elif temp is not None:
        clothing_rationale.append(f"当前温度 {temp:.1f}℃，建议按温度带选层次穿搭。")
    if precipitation > 0:
        clothing_rationale.append(f"当前降水 {precipitation:.1f}mm，外层需防水或至少防泼溅。")
    if wind_speed is not None and wind_speed >= 8:
        clothing_rationale.append(f"风速 {wind_speed:.1f}m/s 偏强，外层需要防风。")
    if uv is not None and uv >= 5:
        clothing_rationale.append(f"UV {uv:.1f} 偏强，建议墨镜/遮阳帽/防晒层。")

    travel_rationale: List[str] = []
    if precipitation > 0:
        travel_title = "降水出行模式"
        travel_summary = "建议优先查看实时路况，预留缓冲时间，并准备雨具或替代交通方式。"
        travel_rationale.append(f"当前降水 {precipitation:.1f}mm，路面湿滑和通行效率会下降。")
    else:
        travel_title = "常规出行模式"
        travel_summary = "当前可按常规计划出行，但仍建议结合风力和空气质量微调。"
        travel_rationale.append("当前无明显降水，出行链路主要受风力和空气质量影响。")
    if wind_speed is not None and wind_speed >= 10:
        travel_rationale.append(f"风速 {wind_speed:.1f}m/s，对骑行、步行和高架路段更不友好。")
    if aqi is not None:
        if aqi >= 150:
            travel_rationale.append(f"AQI {aqi} 已偏高，长时间户外通勤应减少暴露。")
        elif aqi >= 100:
            travel_rationale.append(f"AQI {aqi} 中度偏差，敏感人群建议降低户外暴露时长。")
    if forecast_summary:
        travel_rationale.append(f"预报摘要：{forecast_summary}")

    work_rationale: List[str] = []
    if risk_level == "high":
        work_title = "压缩外勤"
        work_summary = "建议把关键会议和高强度任务前置到室内或线上，减少临时外出。"
        work_rationale.append(f"当前综合风险 {risk_level}，工作节奏宜减少临时暴露。")
    elif precipitation > 0 or (aqi is not None and aqi >= 100):
        work_title = "稳态排程"
        work_summary = "建议优先处理确定性交付，把可变动外勤放在天气窗口更好的时段。"
        work_rationale.append("天气或空气质量存在扰动，排程上应提高缓冲。")
    else:
        work_title = "可推进关键任务"
        work_summary = "当前环境相对稳定，可优先推进需要连续专注和明确产出的工作。"
        work_rationale.append("当前环境链路未见明显高风险干扰。")
    if schedule_windows:
        work_rationale.append(f"档案时窗：{' / '.join(schedule_windows[:3])}。")
    if work_context:
        work_rationale.append(f"工作上下文：{work_context}。")
    if decision_style:
        work_rationale.append(f"决策风格：{decision_style}。")

    market_bias = str((market or {}).get("marketBias") or "cautious")
    market_conf = _safe_float((market or {}).get("confidence"))
    sectors = (market or {}).get("sectors") or []
    investment_rationale: List[str] = []
    if market_bias == "positive":
        investment_title = "偏修复观察"
        investment_summary = "市场链路偏正向，但更适合看板块轮动和确认信号，不宜仅凭天气单因子追高。"
    elif market_bias == "negative":
        investment_title = "偏防守观察"
        investment_summary = "天气扰动和资金面偏弱时，优先防守和仓位纪律，等待更强确认。"
    else:
        investment_title = "中性观察"
        investment_summary = "当前市场信号偏中性，建议更多看成交、主力流向和已持仓约束。"
    if market_conf is not None:
        investment_rationale.append(f"市场偏向 {market_bias}，置信度 {round(market_conf * 100)}%。")
    if sectors:
        top_sector = sectors[0]
        sector_name = str(top_sector.get('name') or '板块')
        sector_reason = str(top_sector.get('reason') or '').strip()
        investment_rationale.append(f"领先板块：{sector_name}{f'，{sector_reason}' if sector_reason else ''}")
    if asset_preferences:
        investment_rationale.append(f"档案资产偏好：{' / '.join(asset_preferences[:3])}。")
    if note:
        investment_rationale.append(f"档案备注：{note[:60]}{'...' if len(note) > 60 else ''}")
    investment_rationale.append("仅供参考，不构成投资建议。")

    if health_alerts:
        alert_titles = [str(item.get("condition") or item.get("title") or "提醒") for item in health_alerts[:3]]
        work_rationale.append(f"已触发提醒：{' / '.join(alert_titles)}。")
        travel_rationale.append(f"健康侧提醒：{' / '.join(alert_titles)}。")
    if family_structure:
        travel_rationale.append(f"家庭结构：{' / '.join(family_structure[:2])}，出行建议已偏向稳定和可预期。")

    return Recommendations(
        diet=RecommendationItem(title=diet_title, summary=diet_summary, rationale=diet_rationale),
        clothing=RecommendationItem(title=clothing_title, summary=clothing_summary, rationale=clothing_rationale),
        travel=RecommendationItem(title=travel_title, summary=travel_summary, rationale=travel_rationale),
        work=RecommendationItem(title=work_title, summary=work_summary, rationale=work_rationale),
        investment=RecommendationItem(title=investment_title, summary=investment_summary, rationale=investment_rationale),
    )


def _upsert_profile_from_payload(payload: ProfileRequest) -> Dict[str, Any]:
    store = get_health_profile_store()
    return store.upsert_profile(
        user_id=payload.user_id,
        display_name=payload.display_name,
        persona=payload.persona,
        identity_summary=payload.identity_summary,
        role=payload.role,
        organization=payload.organization,
        home_base=payload.home_base,
        family_structure=payload.family_structure,
        asset_preferences=payload.asset_preferences,
        schedule_windows=payload.schedule_windows,
        decision_style=payload.decision_style,
        preferences=payload.preferences,
        goals=payload.goals,
        constraints=payload.constraints,
        routines=payload.routines,
        important_people=payload.important_people,
        important_locations=payload.important_locations,
        work_context=payload.work_context,
        long_term_memory=payload.long_term_memory,
        sensitivity_type=payload.sensitivity_type,
        priority_tags=payload.priority_tags,
        conditions=payload.conditions,
        note=payload.note,
        consent=payload.consent,
        sensitivity=payload.sensitivity,
        profile_version=payload.profile_version or "v2",
    )


@router.get(
    "/status",
    tags=["System"],
    response_model=ServiceStatusResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="获取后端能力状态",
)
async def get_service_status() -> ServiceStatusResponse:
    llm_ok, llm_reason = llm_status()
    speech_ok, speech_reason = get_speech_service().status()
    weather_ok = False
    weather_reason = "weather upstream not configured"
    weather_source = "uapis+open-meteo"
    configured_weather_base = __import__("os").getenv("UAPIS_BASE_URL") or UAPIS_BASE_URL
    if configured_weather_base:
        if weather_status_probe_enabled():
            weather_ok, weather_reason = await probe_weather_upstream()
            if weather_ok and not weather_reason:
                weather_reason = "uapis reachable, open-meteo backup available"
            elif not weather_ok:
                weather_ok = True
                weather_reason = f"uapis probe failed, open-meteo backup available: {weather_reason or 'probe failed'}"
        else:
            weather_ok = True
            weather_reason = "uapis configured, open-meteo backup available"
    else:
        weather_ok = True
        weather_reason = "uapis not configured, open-meteo available"
    return ServiceStatusResponse(
        api=ServiceCapability(available=True, reason="running", source="fastapi"),
        llm=ServiceCapability(
            available=llm_ok,
            reason="" if llm_ok else llm_reason,
            source="configured" if llm_ok else "rules-only fallback",
        ),
        speech=ServiceCapability(
            available=speech_ok,
            reason="" if speech_ok else speech_reason,
            source="openai-compatible" if speech_ok else "browser/native fallback",
        ),
        weather=ServiceCapability(
            available=weather_ok,
            reason=weather_reason,
            source=weather_source,
        ),
    )


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
    trace_id = request.headers.get("x-request-id") or f"query-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    classifier = get_intent_classifier()
    intent = classifier.predict(payload.query)
    slots = extract_slots(payload.query)
    if payload.scenario:
        intent = payload.scenario

    location_name = _clean_location_name(payload.location.name if payload.location else None)
    city = payload.city or slots.get("city") or location_name
    adcode = payload.adcode
    locale = (payload.locale or "zh-CN").lower()
    lang = payload.lang or ("en" if locale.startswith("en") else "zh")
    weather = await _resolve_weather_data(
        request=request,
        city=city,
        adcode=adcode,
        lat=(payload.location.lat if payload.location else None),
        lon=(payload.location.lon if payload.location else None),
        lang=lang,
        extended=True,
        forecast=True,
        hourly=True,
        indices=(lang == "zh"),
        require_aqi=True,
    )

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
            name=location_name or weather_name,
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
    environment_time = _event_time_from_payload(payload.time, weather)
    environment = EnvironmentSnapshot(
        **build_environment_snapshot(weather, event_time=environment_time)
    )
    rag_query = build_query(
        query=payload.query,
        intent=intent,
        slots=slots,
        environment=environment.model_dump(),
    )
    rag_items = get_retriever().retrieve(rag_query)
    evidence = [EvidenceItem(**item) for item in rag_items]

    memory_store = None
    memory_history: Optional[List[Dict[str, Any]]] = None
    if payload.sessionId:
        memory_store = get_memory_store()
        memory_history = memory_store.list_messages(session_id=payload.sessionId, limit=6)

    llm_ok, llm_reason = llm_status()
    llm_decision: Optional[Dict[str, Any]] = None
    if llm_ok:
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
        llm_decision = _sanitize_decision_patch(llm_decision, fallback=base_decision)

    if llm_decision:
        advice = llm_decision["advice"]
        risk_level = llm_decision["riskLevel"]
        reasons = llm_decision.get("reasons", [])
        actions = llm_decision.get("actions", [])

    memory_preview: Optional[List[MemoryItem]] = None
    profile_summary: Optional[ProfileAnalysisResponse] = None
    profile_payload: Optional[Dict[str, Any]] = None
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
        profile_payload = get_health_profile_store().get_profile(payload.sessionId)
        if profile_payload:
            profile_summary = ProfileAnalysisResponse(
                **analyze_user_profile(
                    user_id=payload.sessionId,
                    health_profile=profile_payload,
                    memory=memory_store.list_messages(session_id=payload.sessionId, limit=12),
                )
            )

    health_alerts: Optional[List[Dict[str, Any]]] = None
    health_risk_level: Optional[str] = None
    if intent != "greeting":
        user_id = payload.sessionId or location_name or "guest"
        profile_store = get_health_profile_store()
        profile_payload = profile_store.get_profile(user_id)
        if profile_payload:
            conditions = profile_payload.get("conditions", [])
            sensitivity = profile_payload.get("sensitivity", {})
        else:
            conditions = []
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

    market_signal = " + ".join(_weather_signal_parts(weather))
    market_impact: Optional[Dict[str, Any]] = None
    try:
        market_impact = await fetch_market_impact(region="华东", signal=market_signal, horizon="24h")
    except MarketDataError:
        market_impact = None

    recommendations = _build_recommendations(
        weather=weather,
        profile=profile_payload,
        market=market_impact,
        health_alerts=health_alerts,
        risk_level=risk_level,
        forecast_summary=forecast_summary,
    )

    follow_ups: List[str] = []
    if not city and not adcode and not payload.location:
        follow_ups.append("可以补充城市或行政区，建议会更准确。")
    if not payload.time:
        follow_ups.append("如果有明确时间点，例如明早 7 点，可以补充后重新查询。")
    if not slots.get("activity") and intent in {"commute_decision", "sport_decision", "travel_decision"}:
        follow_ups.append("可以补充具体活动类型，例如骑行、跑步或开车。")

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
        recommendations=recommendations,
        nlu=NLUResult(intent=intent, slots=slots),
        environment=environment,
        evidence=evidence,
        memory=memory_preview,
        healthAlerts=health_alerts,
        healthRiskLevel=health_risk_level,
        profileSummary=profile_summary,
        followUps=follow_ups,
        sources=[
            f"{weather.get('source', 'unknown')}:weather",
            "rag:tfidf",
            "llm" if llm_decision else f"rules_only:{llm_reason or 'disabled'}",
        ],
        traceId=trace_id,
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
    "/profile",
    tags=["Profile"],
    response_model=ProfileResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="创建/更新用户档案",
)
def upsert_profile(payload: ProfileRequest) -> ProfileResponse:
    profile = _upsert_profile_from_payload(payload)
    return ProfileResponse(**profile)


@router.get(
    "/profile/{user_id}",
    tags=["Profile"],
    response_model=ProfileResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="获取用户档案",
)
def get_profile(user_id: str) -> ProfileResponse:
    store = get_health_profile_store()
    data = store.get_profile(user_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "profile not found"},
        )
    return ProfileResponse(**data)


@router.delete(
    "/profile/{user_id}",
    tags=["Profile"],
    responses=DEFAULT_ERROR_RESPONSES,
    summary="删除用户档案",
)
def delete_profile(user_id: str) -> Dict[str, str]:
    store = get_health_profile_store()
    existed = store.delete_profile(user_id)
    return {"status": "deleted" if existed else "missing", "user_id": user_id}


@router.post(
    "/health/profile",
    tags=["Health"],
    response_model=HealthProfileResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="创建/更新健康档案（兼容包装）",
)
def upsert_health_profile(payload: HealthProfileRequest) -> HealthProfileResponse:
    profile = _upsert_profile_from_payload(payload)
    return HealthProfileResponse(**profile)


@router.get(
    "/health/profile/{user_id}",
    tags=["Health"],
    response_model=HealthProfileResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="获取健康档案（兼容包装）",
)
def get_health_profile(user_id: str) -> HealthProfileResponse:
    store = get_health_profile_store()
    data = store.get_profile(user_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "profile not found"},
        )
    return HealthProfileResponse(**data)


@router.delete(
    "/health/profile/{user_id}",
    tags=["Health"],
    responses=DEFAULT_ERROR_RESPONSES,
    summary="删除健康档案（兼容包装）",
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
    summary="获取健康提醒",
)
async def get_health_alerts(
    user_id: str,
    request: Request,
    city: Optional[str] = Query(None),
    adcode: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    lang: str = Query("zh", pattern="^(zh|en)$"),
) -> HealthAlertsResponse:
    store = get_health_profile_store()
    profile = store.get_profile(user_id)
    if profile:
        conditions = profile.get("conditions", [])
        sensitivity = profile.get("sensitivity", {})
    else:
        conditions = []
        sensitivity = {}
    if city or adcode or (lat is not None and lon is not None):
        weather = await _resolve_weather_data(
            request=request,
            city=city,
            adcode=adcode,
            lat=lat,
            lon=lon,
            lang=lang,
            extended=True,
            require_location=True,
            require_aqi=True,
        )
    else:
        weather = {"source": "location-unresolved", "updatedAt": None}
    alerts = evaluate_health_alerts(conditions=conditions, weather=weather, sensitivity=sensitivity)
    risk_level = (
        "high"
        if any(alert.get("riskLevel") == "high" for alert in alerts)
        else "medium" if alerts else "low"
    )
    return HealthAlertsResponse(
        user_id=user_id,
        alerts=alerts,
        riskLevel=risk_level,
        source=weather.get("source", "location-unresolved"),
        updatedAt=weather.get("updatedAt"),
    )


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
    if not profile:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "profile not found"},
        )
    memory = memory_store.list_messages(session_id=user_id, limit=12)
    result = analyze_user_profile(user_id=user_id, health_profile=profile, memory=memory)
    return ProfileAnalysisResponse(**result)


# -----------------------------
# Stocks Impact
# -----------------------------
@router.get(
    "/stocks/impact",
    tags=["Market"],
    response_model=StocksImpactResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="股市影响分析",
)
async def get_stocks_impact(
    region: str = Query("华东"),
    signal: str = Query(""),
    horizon: str = Query("24h"),
) -> StocksImpactResponse:
    try:
        data = await fetch_market_impact(region=region, signal=signal, horizon=horizon)
    except MarketDataError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.payload)
    return StocksImpactResponse(**data)


# -----------------------------
# RAG Evidence
# -----------------------------
@router.get(
    "/rag/evidence",
    tags=["RAG"],
    response_model=RagResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="知识检索证据",
)
def get_rag_evidence(query: str = Query(...)) -> RagResponse:
    rag_items = get_retriever().retrieve(query)
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
    lat: Optional[float] = Query(None, description="Latitude, used to reverse-resolve city when city/adcode absent"),
    lon: Optional[float] = Query(None, description="Longitude, used to reverse-resolve city when city/adcode absent"),
    lang: str = Query("zh", pattern="^(zh|en)$"),
    extended: Optional[bool] = Query(None, description="Return extended fields"),
    forecast: Optional[bool] = Query(None, description="Return multi-day forecast (max 7 days)"),
    hourly: Optional[bool] = Query(None, description="Return hourly forecast (24 hours)"),
    minutely: Optional[bool] = Query(None, description="Return minutely precipitation (domestic only)"),
    indices: Optional[bool] = Query(None, description="Return life indices (zh only)"),
    _auth: Optional[str] = Depends(get_auth),
) -> Dict[str, Any]:
    return await _resolve_weather_data(
        request=request,
        city=city,
        adcode=adcode,
        lat=lat,
        lon=lon,
        lang=lang,
        extended=extended,
        forecast=forecast,
        hourly=hourly,
        minutely=minutely,
        indices=indices,
        require_location=True,
        require_aqi=True,
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
    source: str = "eastmoney"
    updatedAt: Optional[str] = None


@router.get(
    "/forecast",
    tags=["Forecast"],
    response_model=ForecastResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="天气预报：当前/逐小时/逐日",
)
async def get_forecast(
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    city: Optional[str] = Query(None, description="City name, preferred for upstream lookup"),
    adcode: Optional[str] = Query(None, description="Administrative code, preferred for upstream lookup"),
    hours: int = Query(24, ge=1, le=168),
    days: int = Query(7, ge=1, le=14),
    units: str = Query("metric"),
    lang: str = Query("zh-CN"),
    tz: Optional[str] = Query(None),
    _auth: Optional[str] = Depends(get_auth),
) -> ForecastResponse:
    language = "en" if lang.lower().startswith("en") else "zh"
    weather = await _resolve_weather_data(
        request=None,
        city=city,
        adcode=adcode,
        lat=lat,
        lon=lon,
        lang=language,
        extended=True,
        forecast=True,
        hourly=True,
        require_location=True,
        require_aqi=True,
    )
    current: Dict[str, Any] = {}
    hourly_items = _pick_hourly_items(weather)
    daily_items = weather.get("forecast") or []
    updated_at = weather.get("updatedAt")

    current["temp"] = weather.get("temperature")
    current["aqi"] = weather.get("aqi")
    wind_power = str(weather.get("wind_power") or "")
    wind_digits = "".join(ch for ch in wind_power if ch.isdigit() or ch == ".")
    current["wind"] = (
        float(wind_digits)
        if wind_digits
        else float(weather.get("wind_speed") or 0)
    )
    current["ts"] = _normalize_timestamp(weather.get("ts"), fallback=updated_at)

    normalized_hourly = []
    for item in hourly_items[:hours]:
        temp_value = item.get("temp", item.get("temperature", weather.get("temperature")))
        if temp_value is None:
            continue
        pop_value = item.get("pop", item.get("precip"))
        if pop_value is not None:
            pop_value = float(pop_value)
            if pop_value > 1:
                pop_value = round(pop_value / 100.0, 4)
        normalized_hourly.append(
            {
                "ts": _normalize_timestamp(item.get("ts") or item.get("time"), fallback=current.get("ts")),
                "temp": temp_value,
                "pop": pop_value,
            }
        )

    normalized_daily = []
    for item in daily_items[:days]:
        normalized_daily.append(
            {
                "date": item.get("date"),
                "tmin": item.get("tmin", item.get("temp_min")),
                "tmax": item.get("tmax", item.get("temp_max")),
                "uv": item.get("uv", item.get("uv_index", weather.get("uv"))),
            }
        )
    return ForecastResponse(
        location={
            "lat": lat,
            "lon": lon,
            "tz": tz or "Asia/Shanghai",
            "name": _compose_location_name(weather, fallback_city=city, fallback_adcode=adcode),
            "city": weather.get("city") or city,
            "adcode": weather.get("adcode") or adcode,
            "source": weather.get("source", "uapis"),
            "updatedAt": updated_at,
        },
        current=ForecastCurrent(**current) if current.get("ts") and current.get("temp") is not None else None,
        hourly=[ForecastHourly(**item) for item in normalized_hourly],
        daily=[ForecastDaily(**item) for item in normalized_daily],
        source=weather.get("source", "uapis"),
        updatedAt=updated_at,
    )


# -----------------------------
# AQI
# -----------------------------
class AQIResponse(BaseModel):
    location: Dict[str, Any]
    ts: datetime
    aqi: int
    primary: Optional[str] = Field(default=None, description="Primary pollutant")
    source: str = "uapis"
    updatedAt: Optional[str] = None


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
    source: str = "sqlite"
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class TaskItemResponse(BaseModel):
    task_id: int
    type: str
    scheduledTime: str
    priority: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: str
    createdAt: str
    updatedAt: str
    source: str = "sqlite"


@router.get(
    "/aqi",
    tags=["AQI"],
    response_model=AQIResponse,
    responses=DEFAULT_ERROR_RESPONSES,
    summary="空气质量（AQI）",
)
async def get_aqi(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    city: Optional[str] = Query(None),
    adcode: Optional[str] = Query(None),
    units: str = Query("metric"),
    _auth: Optional[str] = Depends(get_auth),
) -> AQIResponse:
    weather = await _resolve_weather_data(
        request=None,
        city=city,
        adcode=adcode,
        lat=lat,
        lon=lon,
        lang="zh",
        extended=True,
        require_location=True,
        require_aqi=True,
    )
    if weather.get("aqi") is None:
        raise HTTPException(
            status_code=502,
            detail={"code": "UPSTREAM_ERROR", "message": "weather upstream returned no AQI data"},
        )
    updated_at = weather.get("updatedAt")
    ts_value = _normalize_timestamp(weather.get("ts"), fallback=updated_at)
    if not ts_value:
        raise HTTPException(
            status_code=502,
            detail={"code": "UPSTREAM_ERROR", "message": "weather upstream returned invalid AQI timestamp"},
        )
    return AQIResponse(
        location={
            "lat": lat,
            "lon": lon,
            "name": _compose_location_name(weather, fallback_city=city, fallback_adcode=adcode),
            "city": weather.get("city") or city,
            "adcode": weather.get("adcode") or adcode,
        },
        ts=datetime.fromisoformat(ts_value),
        aqi=int(weather["aqi"]),
        primary=weather.get("aqi_primary"),
        source=weather.get("source", "uapis"),
        updatedAt=updated_at,
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
    data = get_task_store().create_task(
        task_type=payload.type,
        scheduled_time=payload.scheduled_time.isoformat(),
        priority=payload.priority or 5,
        metadata=payload.metadata,
    )
    return TaskCreateResponse(
        task_id=data["task_id"],
        status=data["status"],
        source=data["source"],
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


@router.get(
    "/tasks",
    tags=["Tasks"],
    response_model=List[TaskItemResponse],
    responses=DEFAULT_ERROR_RESPONSES,
    summary="获取任务/提醒列表",
)
async def list_tasks(
    limit: int = Query(20, ge=1, le=200),
    _auth: Optional[str] = Depends(get_auth),
) -> List[TaskItemResponse]:
    items = get_task_store().list_tasks(limit=limit)
    return [TaskItemResponse(**item) for item in items]
