from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mock_weather(
    *,
    city: Optional[str] = None,
    adcode: Optional[str] = None,
    lang: str = "zh",
    extended: Optional[bool] = None,
    forecast: Optional[bool] = None,
    hourly: Optional[bool] = None,
    minutely: Optional[bool] = None,
    indices: Optional[bool] = None,
) -> Dict[str, Any]:
    name = city or "上海"
    base = {
        "city": name,
        "province": None,
        "weather": "小雨",
        "temperature": 12.2,
        "feels_like": 10.8,
        "humidity": 82,
        "wind_direction": "东风",
        "wind_power": "4级",
        "precipitation": 1.2,
        "uv": 1.5,
        "aqi": 68,
        "status": "ok",
        "source": "mock",
        "updatedAt": _now_iso(),
    }
    if extended:
        base.update(
            {
                "pressure": 1012,
                "visibility": 6,
                "dew_point": 8.2,
                "cloud": 78,
            }
        )
    if forecast:
        base["forecast"] = [
            {"date": "2026-03-17", "tmin": 9, "tmax": 16, "text": "阴"},
            {"date": "2026-03-18", "tmin": 10, "tmax": 18, "text": "多云"},
        ]
    if hourly:
        base["hourly"] = [
            {"ts": "2026-03-17T07:00:00+08:00", "temp": 12.1, "pop": 0.6},
            {"ts": "2026-03-17T08:00:00+08:00", "temp": 12.4, "pop": 0.4},
        ]
    if minutely:
        base["minutely"] = {
            "summary": "未来1小时有小雨",
            "precipitation": [0.1, 0.2, 0.3, 0.2, 0.1],
        }
    if indices:
        base["indices"] = [
            {"type": "sport", "level": "适宜", "desc": "气温适中，适合运动"},
            {"type": "umbrella", "level": "建议", "desc": "短时降水，建议带伞"},
        ]
    if lang == "en":
        base["weather"] = "Light rain"
    return base


def mock_forecast(lat: float, lon: float, hours: int, days: int, tz: str) -> Dict[str, Any]:
    now = datetime.now()
    hourly = [
        {
            "ts": (now + timedelta(hours=i)).isoformat(),
            "temp": round(12 + i * 0.2, 1),
            "pop": round(max(0, 0.6 - i * 0.03), 2),
        }
        for i in range(min(hours, 24))
    ]
    daily = [
        {
            "date": (now + timedelta(days=i)).date().isoformat(),
            "tmin": round(8 + i * 0.4, 1),
            "tmax": round(16 + i * 0.5, 1),
            "uv": round(2 + i * 0.3, 1),
        }
        for i in range(min(days, 7))
    ]
    return {
        "location": {"lat": lat, "lon": lon, "tz": tz},
        "current": {"ts": now.isoformat(), "temp": 12.2, "wind": 4.0, "aqi": 68},
        "hourly": hourly,
        "daily": daily,
        "source": "mock",
        "updatedAt": _now_iso(),
    }


def mock_aqi(lat: float, lon: float) -> Dict[str, Any]:
    value = random.choice([55, 68, 72, 88])
    return {
        "location": {"lat": lat, "lon": lon},
        "ts": _now_iso(),
        "aqi": value,
        "primary": "PM2.5",
        "source": "mock",
    }


def mock_task(task_type: str, scheduled_time: str, priority: int) -> Dict[str, Any]:
    return {
        "task_id": random.randint(1000, 2000),
        "status": "scheduled",
        "nextRun": scheduled_time,
        "priority": priority,
        "type": task_type,
        "source": "mock",
    }


def mock_health_profile(
    user_id: str,
    conditions: List[str],
    note: Optional[str],
    consent: bool = True,
    sensitivity: Optional[Dict[str, Any]] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    now = _now_iso()
    return {
        "user_id": user_id,
        "conditions": conditions,
        "note": note,
        "consent": consent,
        "sensitivity": sensitivity or {},
        "created_at": created_at or now,
        "updated_at": now,
        "source": "mock",
    }


def mock_health_conditions(user_id: str) -> List[str]:
    if not user_id:
        return []
    seed = sum(ord(ch) for ch in user_id)
    condition_sets = [
        ["rheumatism"],
        ["asthma"],
        ["photosensitivity"],
        ["rheumatism", "asthma"],
        [],
    ]
    return condition_sets[seed % len(condition_sets)]


def infer_health_conditions(text: str) -> List[str]:
    if not text:
        return []
    mapping = {
        "风湿": "rheumatism",
        "关节": "rheumatism",
        "哮喘": "asthma",
        "气喘": "asthma",
        "过敏": "asthma",
        "光敏": "photosensitivity",
        "日晒": "photosensitivity",
        "皮肤": "photosensitivity",
    }
    result = {value for key, value in mapping.items() if key in text}
    return sorted(result)


def mock_health_alerts(
    conditions: List[str], weather: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    return []


def mock_stocks(region: str, signal: str) -> Dict[str, Any]:
    return {
        "region": region,
        "updatedAt": _now_iso(),
        "weatherSignal": signal,
        "marketBias": "cautious",
        "confidence": 0.62,
        "sectors": [
            {"name": "交通与物流", "impact": "negative", "reason": "降雨影响运输效率"},
            {"name": "户外零售", "impact": "negative", "reason": "客流下降"},
            {"name": "医药健康", "impact": "positive", "reason": "健康需求提升"},
            {"name": "线上服务", "impact": "positive", "reason": "线上娱乐与配送需求提升"},
        ],
        "drivers": ["降水", "低温", "风力偏大"],
        "disclaimer": "仅供参考，不构成投资建议。",
        "source": "mock",
    }


def mock_rag(query: str) -> List[Dict[str, Any]]:
    return [
        {
            "id": "health_rheumatism",
            "title": "湿冷与关节不适",
            "content": "湿冷天气可能加重关节不适，注意保暖。",
            "tags": ["health"],
            "domain": "health",
            "score": 0.82,
        },
        {
            "id": "commute_rain",
            "title": "雨天通勤安全提示",
            "content": "雨天路滑，建议提前出门并减速。",
            "tags": ["commute"],
            "domain": "travel",
            "score": 0.71,
        },
    ]
