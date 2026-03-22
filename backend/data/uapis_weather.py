from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

import httpx


UAPIS_BASE_URL = os.getenv("UAPIS_BASE_URL", "https://uapis.cn/api/v1")
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("UAPIS_TIMEOUT", "5.0"))
DEFAULT_RETRIES = int(os.getenv("UAPIS_RETRIES", "2"))
DEFAULT_BACKOFF_SECONDS = float(os.getenv("UAPIS_BACKOFF", "0.6"))


class UapisError(Exception):
    def __init__(self, status_code: int, payload: Dict[str, Any]):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"UAPIS error {status_code}")


def _bool_param(value: Optional[bool]) -> Optional[str]:
    if value is None:
        return None
    return "true" if value else "false"


async def fetch_weather(
    *,
    city: Optional[str],
    adcode: Optional[str],
    lang: Optional[str],
    extended: Optional[bool],
    forecast: Optional[bool],
    hourly: Optional[bool],
    minutely: Optional[bool],
    indices: Optional[bool],
    client_ip: Optional[str],
) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if adcode:
        params["adcode"] = adcode
    if city:
        params["city"] = city
    if lang:
        params["lang"] = lang

    for key, value in (
        ("extended", _bool_param(extended)),
        ("forecast", _bool_param(forecast)),
        ("hourly", _bool_param(hourly)),
        ("minutely", _bool_param(minutely)),
        ("indices", _bool_param(indices)),
    ):
        if value is not None:
            params[key] = value

    headers: Dict[str, str] = {}
    if client_ip:
        headers["X-Forwarded-For"] = client_ip

    url = f"{UAPIS_BASE_URL}/misc/weather"

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        for attempt in range(DEFAULT_RETRIES + 1):
            try:
                response = await client.get(url, params=params, headers=headers)
            except httpx.TimeoutException:
                if attempt < DEFAULT_RETRIES:
                    await asyncio.sleep(DEFAULT_BACKOFF_SECONDS * (2**attempt))
                    continue
                raise UapisError(
                    status_code=503,
                    payload={
                        "code": "SERVICE_UNAVAILABLE",
                        "message": "weather service timeout",
                    },
                )
            except httpx.RequestError:
                if attempt < DEFAULT_RETRIES:
                    await asyncio.sleep(DEFAULT_BACKOFF_SECONDS * (2**attempt))
                    continue
                raise UapisError(
                    status_code=503,
                    payload={
                        "code": "SERVICE_UNAVAILABLE",
                        "message": "weather service unavailable",
                    },
                )

            if response.status_code >= 400:
                try:
                    payload = response.json()
                except ValueError:
                    payload = {"code": "UPSTREAM_ERROR", "message": response.text}
                raise UapisError(status_code=response.status_code, payload=payload)

            try:
                return response.json()
            except ValueError:
                raise UapisError(
                    status_code=502,
                    payload={"code": "UPSTREAM_ERROR", "message": "invalid upstream response"},
                )

    raise UapisError(
        status_code=503,
        payload={"code": "SERVICE_UNAVAILABLE", "message": "weather service unavailable"},
    )
