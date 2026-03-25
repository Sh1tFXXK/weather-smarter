"""Open-Meteo weather, AQI and geocoding — free, no API key required."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
TIMEOUT = 10.0
RETRIES = 2
BACKOFF = 0.6

# WMO weather interpretation codes → Chinese
WMO_ZH: Dict[int, str] = {
    0: "晴", 1: "基本晴朗", 2: "部分多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "细雨", 53: "小雨", 55: "毛毛雨",
    56: "冻细雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻小雨", 67: "冻大雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "冰粒",
    80: "阵雨", 81: "中阵雨", 82: "强阵雨",
    85: "阵雪", 86: "大阵雪",
    95: "雷阵雨", 96: "雷阵雨夹冰雹", 99: "强雷阵雨夹冰雹",
}

WMO_EN: Dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Drizzle (light)", 53: "Drizzle", 55: "Drizzle (dense)",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Rain showers", 81: "Rain showers", 82: "Heavy rain showers",
    85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Heavy thunderstorm with hail",
}


def _wmo(code: int, lang: str = "zh") -> str:
    code = int(code or 0)
    if lang == "en":
        return WMO_EN.get(code, f"Weather code {code}")
    return WMO_ZH.get(code, f"天气代码{code}")


def _deg_to_dir(deg: float, lang: str = "zh") -> str:
    dirs_zh = ["北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风"]
    dirs_en = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    dirs = dirs_en if lang == "en" else dirs_zh
    return dirs[round(float(deg or 0) / 45) % 8]


def _kmh_to_beaufort_zh(kmh: float) -> str:
    ms = float(kmh or 0) / 3.6
    thresholds = [0.2, 1.5, 3.3, 5.4, 7.9, 10.7, 13.8, 17.1, 20.7, 24.4, 28.4, 32.6]
    for level, t in enumerate(thresholds):
        if ms < t:
            return f"{level}级"
    return "12级以上"


def _build_indices(
    temp: float,
    precip: float,
    uv: float,
    aqi: int,
    humidity: float,
) -> List[Dict[str, Any]]:
    """Generate lifestyle indices from weather parameters."""
    t, p, u, a, h = float(temp or 0), float(precip or 0), float(uv or 0), int(aqi or 0), float(humidity or 0)
    indices = []

    # Sport
    sport_ok = 5 <= t <= 30 and p < 0.5 and a < 100
    indices.append({
        "type": "sport",
        "level": "适宜" if sport_ok else "不宜",
        "desc": "气温舒适，空气良好，适合户外运动" if sport_ok else "当前条件不宜剧烈户外运动",
    })
    # Umbrella
    rain = p > 0.2
    indices.append({
        "type": "umbrella",
        "level": "建议" if rain else "不必",
        "desc": "有降水，请携带雨伞" if rain else "暂无降水，无需带伞",
    })
    # UV protection
    uv_level = "强" if u >= 6 else "中等" if u >= 3 else "弱"
    indices.append({
        "type": "uv",
        "level": uv_level,
        "desc": "紫外线强，建议涂抹防晒霜并佩戴遮阳帽" if u >= 6
              else "紫外线中等，外出可做基础防晒" if u >= 3
              else "紫外线较弱，无需特别防护",
    })
    # Dressing
    if t < 5:
        dress, desc = "厚衣", "气温较低，建议穿羽绒服或厚外套"
    elif t < 15:
        dress, desc = "外套", "气温偏凉，建议穿外套或风衣"
    elif t < 25:
        dress, desc = "适中", "气温舒适，正常着装即可"
    else:
        dress, desc = "轻薄", "气温较高，建议穿轻薄透气衣物"
    indices.append({"type": "dress", "level": dress, "desc": desc})

    # Air quality for outdoor activity
    if a <= 50:
        aq_level, aq_desc = "优", "空气优良，非常适合户外活动"
    elif a <= 100:
        aq_level, aq_desc = "良", "空气良好，适合户外活动"
    elif a <= 150:
        aq_level, aq_desc = "轻度污染", "空气轻度污染，敏感人群减少户外"
    else:
        aq_level, aq_desc = "污染", "空气污染较重，建议减少户外活动"
    indices.append({"type": "air", "level": aq_level, "desc": aq_desc})

    return indices


async def _get(
    client: httpx.AsyncClient,
    url: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    last_err: Exception = RuntimeError("no attempts")
    for attempt in range(RETRIES + 1):
        try:
            resp = await client.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
            last_err = exc
            if attempt < RETRIES:
                await asyncio.sleep(BACKOFF * (2 ** attempt))
    raise last_err


async def geocode_city(
    city: str,
) -> Optional[Tuple[float, float, str, str]]:
    """Convert city name → (lat, lon, display_name, province). Returns None on failure."""
    if not city:
        return None
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            data = await _get(client, GEOCODING_URL, {
                "name": city,
                "count": 1,
                "language": "zh",
                "format": "json",
            })
        except Exception:
            return None
    results = data.get("results") or []
    if not results:
        return None
    r = results[0]
    return (
        float(r["latitude"]),
        float(r["longitude"]),
        r.get("name") or city,
        r.get("admin1") or "",
    )


async def fetch_openmeteo_weather(
    lat: float,
    lon: float,
    *,
    city: Optional[str] = None,
    province: Optional[str] = None,
    lang: str = "zh",
    extended: bool = True,
    forecast: bool = True,
    hourly: bool = True,
    minutely: bool = False,
    indices: bool = True,
) -> Dict[str, Any]:
    """Fetch comprehensive weather from Open-Meteo (free, no key)."""
    now_iso = datetime.now(timezone.utc).isoformat()

    wx_params: Dict[str, Any] = {
        "latitude": round(float(lat), 4),
        "longitude": round(float(lon), 4),
        "current": ",".join([
            "temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "precipitation", "rain", "weather_code",
            "wind_speed_10m", "wind_direction_10m",
            "cloud_cover", "surface_pressure", "visibility",
        ]),
        "hourly": ",".join([
            "temperature_2m", "relative_humidity_2m",
            "precipitation_probability", "precipitation",
            "weather_code", "wind_speed_10m",
        ]),
        "daily": ",".join([
            "temperature_2m_max", "temperature_2m_min",
            "precipitation_sum", "uv_index_max", "weather_code",
        ]),
        "forecast_days": 7,
        "timezone": "Asia/Shanghai",
        "wind_speed_unit": "kmh",
    }
    aqi_params: Dict[str, Any] = {
        "latitude": round(float(lat), 4),
        "longitude": round(float(lon), 4),
        "current": "pm2_5,pm10,european_aqi,us_aqi",
        "timezone": "Asia/Shanghai",
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        wx_task = _get(client, FORECAST_URL, wx_params)
        aqi_task = _get(client, AIR_QUALITY_URL, aqi_params)
        wx_data, aqi_data = await asyncio.gather(wx_task, aqi_task, return_exceptions=True)

    if isinstance(wx_data, Exception):
        raise wx_data

    cur = wx_data.get("current") or {}
    hourly_raw = wx_data.get("hourly") or {}
    daily_raw = wx_data.get("daily") or {}

    temp: Optional[float] = cur.get("temperature_2m")
    feels: Optional[float] = cur.get("apparent_temperature")
    humidity: Optional[float] = cur.get("relative_humidity_2m")
    precip: float = float(cur.get("precipitation") or 0)
    wmo_code: int = int(cur.get("weather_code") or 0)
    wind_kmh: float = float(cur.get("wind_speed_10m") or 0)
    wind_deg: float = float(cur.get("wind_direction_10m") or 0)
    cloud: Optional[float] = cur.get("cloud_cover")
    pressure: Optional[float] = cur.get("surface_pressure")
    vis_m: Optional[float] = cur.get("visibility")
    current_time: str = str(cur.get("time") or now_iso)

    # AQI
    aqi_val: Optional[int] = None
    aqi_primary: Optional[str] = None
    if not isinstance(aqi_data, Exception):
        aqi_cur = aqi_data.get("current") or {}
        eu_aqi = aqi_cur.get("european_aqi")
        us_aqi = aqi_cur.get("us_aqi")
        aqi_val = int(eu_aqi) if eu_aqi is not None else (int(us_aqi) if us_aqi is not None else None)
        pm25 = aqi_cur.get("pm2_5")
        pm10 = aqi_cur.get("pm10")
        if pm25 is not None and (pm10 is None or float(pm25) >= float(pm10)):
            aqi_primary = "PM2.5"
        elif pm10 is not None:
            aqi_primary = "PM10"

    # UV from daily
    daily_uv_list: List[float] = daily_raw.get("uv_index_max") or []
    uv_val: Optional[float] = daily_uv_list[0] if daily_uv_list else None

    result: Dict[str, Any] = {
        "city": city or f"({lat:.2f},{lon:.2f})",
        "province": province,
        "weather": _wmo(wmo_code, lang),
        "temperature": temp,
        "feels_like": feels,
        "humidity": humidity,
        "wind_direction": _deg_to_dir(wind_deg, lang),
        "wind_power": _kmh_to_beaufort_zh(wind_kmh),
        "wind_speed": round(wind_kmh / 3.6, 1),
        "precipitation": round(precip, 2),
        "uv": round(uv_val, 1) if uv_val is not None else None,
        "aqi": aqi_val,
        "aqi_primary": aqi_primary,
        "lat": round(float(lat), 4),
        "lon": round(float(lon), 4),
        "status": "ok",
        "source": "open-meteo",
        "updatedAt": (current_time + ":00+08:00" if len(current_time) == 13 else current_time),
    }

    if extended:
        result["pressure"] = round(float(pressure), 1) if pressure is not None else None
        result["visibility"] = round(float(vis_m) / 1000, 1) if vis_m is not None else None
        result["cloud"] = int(cloud) if cloud is not None else None

    if forecast:
        dates: List[str] = daily_raw.get("time") or []
        tmins: List[float] = daily_raw.get("temperature_2m_min") or []
        tmaxs: List[float] = daily_raw.get("temperature_2m_max") or []
        wmos: List[int] = daily_raw.get("weather_code") or []
        result["forecast"] = [
            {
                "date": dates[i],
                "tmin": round(tmins[i], 1) if i < len(tmins) else None,
                "tmax": round(tmaxs[i], 1) if i < len(tmaxs) else None,
                "text": _wmo(wmos[i] if i < len(wmos) else 0, lang),
            }
            for i in range(len(dates[:7]))
        ]

    if hourly:
        h_times: List[str] = hourly_raw.get("time") or []
        h_temps: List[float] = hourly_raw.get("temperature_2m") or []
        h_pops: List[Optional[float]] = hourly_raw.get("precipitation_probability") or []
        hourly_list = []
        for i, t_str in enumerate(h_times[:24]):
            pop = h_pops[i] if i < len(h_pops) else None
            hourly_list.append({
                "ts": (t_str + ":00+08:00" if len(t_str) == 13 else t_str),
                "temp": round(h_temps[i], 1) if i < len(h_temps) else None,
                "pop": round(float(pop) / 100.0, 3) if pop is not None else None,
            })
        result["hourly"] = hourly_list

    if indices:
        result["indices"] = _build_indices(
            temp or 0,
            precip,
            uv_val or 0,
            aqi_val or 0,
            humidity or 0,
        )

    return result


async def fetch_openmeteo_aqi(lat: float, lon: float) -> Dict[str, Any]:
    """Standalone AQI fetch from Open-Meteo air quality API."""
    params: Dict[str, Any] = {
        "latitude": round(float(lat), 4),
        "longitude": round(float(lon), 4),
        "current": "pm2_5,pm10,european_aqi,us_aqi",
        "timezone": "Asia/Shanghai",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        data = await _get(client, AIR_QUALITY_URL, params)
    cur = data.get("current") or {}
    eu_aqi = cur.get("european_aqi")
    us_aqi = cur.get("us_aqi")
    aqi_val = int(eu_aqi) if eu_aqi is not None else (int(us_aqi) if us_aqi is not None else 0)
    pm25 = cur.get("pm2_5")
    pm10 = cur.get("pm10")
    primary = "PM2.5" if (pm25 is not None and (pm10 is None or float(pm25) >= float(pm10))) else "PM10"
    return {
        "aqi": aqi_val,
        "aqi_primary": primary,
        "pm2_5": pm25,
        "pm10": pm10,
        "source": "open-meteo",
        "ts": str(cur.get("time") or datetime.now(timezone.utc).isoformat()),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
