from __future__ import annotations

from typing import Any, Dict, List, Optional


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _wind_level(wind_power: Optional[str]) -> Optional[int]:
    if not wind_power:
        return None
    digits = [int(ch) for ch in str(wind_power) if ch.isdigit()]
    if digits:
        return int(sum(digits) / len(digits))
    return None


def _apply_sensitivity(thresholds: Dict[str, Any], sensitivity: Dict[str, Any]) -> Dict[str, Any]:
    if not sensitivity:
        return thresholds
    updated = dict(thresholds)
    for key, value in sensitivity.items():
        if value is None:
            continue
        updated[key] = value
    return updated


def evaluate_health_alerts(
    *,
    conditions: List[str],
    weather: Dict[str, Any],
    sensitivity: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    sensitivity = sensitivity or {}
    humidity = _to_float(weather.get("humidity"))
    feels_like = _to_float(weather.get("feels_like")) or _to_float(weather.get("temperature"))
    precipitation = _to_float(weather.get("precipitation"))
    aqi = _to_int(weather.get("aqi"))
    uv = _to_float(weather.get("uv"))
    wind_level = _wind_level(weather.get("wind_power"))

    alerts: List[Dict[str, Any]] = []

    if "rheumatism" in conditions:
        thresholds = _apply_sensitivity(
            {"humidity": 75, "feels_like": 12, "precipitation": 0.1}, sensitivity
        )
        reasons: List[str] = []
        if humidity is not None and humidity >= thresholds["humidity"]:
            reasons.append("湿度较高")
        if precipitation is not None and precipitation >= thresholds["precipitation"]:
            reasons.append("有降水")
        if feels_like is not None and feels_like <= thresholds["feels_like"]:
            reasons.append("体感温度偏低")
        if reasons:
            risk_level = (
                "high"
                if (humidity is not None and humidity >= thresholds["humidity"] + 10)
                and precipitation
                else "medium"
            )
            alerts.append(
                {
                    "condition": "rheumatism",
                    "riskLevel": risk_level,
                    "reasons": reasons,
                    "actions": ["注意关节保暖", "减少湿冷环境停留"],
                }
            )

    if "asthma" in conditions:
        thresholds = _apply_sensitivity({"aqi": 100, "wind": 6}, sensitivity)
        reasons = []
        if aqi is not None and aqi >= thresholds["aqi"]:
            reasons.append("空气质量一般或偏差")
        if wind_level is not None and wind_level >= thresholds["wind"]:
            reasons.append("风力偏大")
        if reasons:
            risk_level = "high" if (aqi is not None and aqi >= thresholds["aqi"] + 50) else "medium"
            alerts.append(
                {
                    "condition": "asthma",
                    "riskLevel": risk_level,
                    "reasons": reasons,
                    "actions": ["减少户外高强度运动", "必要时佩戴口罩"],
                }
            )

    if "photosensitivity" in conditions:
        thresholds = _apply_sensitivity({"uv": 6}, sensitivity)
        reasons = []
        if uv is not None and uv >= thresholds["uv"]:
            reasons.append("紫外线偏强")
        if reasons:
            risk_level = "high" if (uv is not None and uv >= thresholds["uv"] + 3) else "medium"
            alerts.append(
                {
                    "condition": "photosensitivity",
                    "riskLevel": risk_level,
                    "reasons": reasons,
                    "actions": ["加强防晒", "避免正午暴晒"],
                }
            )

    return alerts
