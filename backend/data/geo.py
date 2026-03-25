from __future__ import annotations

from typing import Optional, Tuple

import httpx

from backend.data.openmeteo import geocode_city as openmeteo_geocode_city


USER_AGENT = "weather-smarter/1.0"


async def reverse_geocode(lat: float, lon: float) -> Tuple[Optional[str], Optional[str]]:
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "jsonv2",
        "zoom": 10,
        "addressdetails": 1,
        "accept-language": "zh-CN,zh,en",
    }
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    address = payload.get("address") or {}
    city = (
        address.get("city")
        or address.get("town")
        or address.get("county")
        or address.get("state_district")
        or address.get("state")
    )
    province = (
        address.get("state")
        or address.get("province")
        or address.get("region")
    )
    return city, province


async def geocode_city(city: str) -> Optional[Tuple[float, float, str, str]]:
    """Resolve a city name to coordinates using Open-Meteo geocoding."""
    return await openmeteo_geocode_city(city)
