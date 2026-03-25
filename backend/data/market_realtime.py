from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx


EASTMONEY_BASE_URL = "https://push2.eastmoney.com/api/qt/clist/get"
DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_RETRIES = 2
DEFAULT_BACKOFF_SECONDS = 0.6

REGION_TO_FS = {
    "a股": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
    "沪深": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
    "华东": "m:90+t:2+f:!50",
    "华南": "m:90+t:4+f:!50",
    "华中": "m:90+t:3+f:!50",
    "华北": "m:90+t:1+f:!50",
    "西南": "m:90+t:7+f:!50",
    "西北": "m:90+t:8+f:!50",
    "东北": "m:90+t:6+f:!50",
}

DEFAULT_FIELDS = "f12,f14,f2,f3,f62,f184"


class MarketDataError(Exception):
    def __init__(self, status_code: int, payload: Dict[str, Any]):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"market data error {status_code}")


def _normalize_region_key(region: str) -> str:
    text = str(region or "").strip().lower()
    if not text:
        return "a股"
    aliases = {
        "china": "a股",
        "cn": "a股",
        "ashare": "a股",
        "a-share": "a股",
        "east china": "华东",
        "north china": "华北",
        "south china": "华南",
        "central china": "华中",
        "southwest": "西南",
        "northwest": "西北",
        "northeast": "东北",
    }
    return aliases.get(text, str(region or "").strip())


def _choose_region_filter(region: str) -> str:
    key = _normalize_region_key(region)
    return REGION_TO_FS.get(key, REGION_TO_FS["a股"])


def _classify_signal(signal: str) -> tuple[str, List[str]]:
    text = str(signal or "").strip()
    tokens = [item for item in text.replace("+", " ").replace("，", " ").replace(",", " ").split() if item]
    negative_markers = ("雨", "暴雨", "湿冷", "寒潮", "大风", "降温", "台风", "霾", "污染")
    positive_markers = ("晴", "回暖", "出游", "消费", "修复", "放晴", "升温")
    negative_hits = sum(marker in text for marker in negative_markers)
    positive_hits = sum(marker in text for marker in positive_markers)
    if negative_hits > positive_hits:
        return "negative", tokens
    if positive_hits > negative_hits:
        return "positive", tokens
    return "neutral", tokens


def _impact_direction(change_pct: float, net_main_flow: float, *, signal_bias: str) -> str:
    score = 0
    if change_pct > 0:
        score += 1
    elif change_pct < 0:
        score -= 1
    if net_main_flow > 0:
        score += 1
    elif net_main_flow < 0:
        score -= 1
    if signal_bias == "negative":
        score -= 1
    elif signal_bias == "positive":
        score += 1
    if score >= 1:
        return "positive"
    if score <= -1:
        return "negative"
    return "neutral"


def _sector_reason(name: str, change_pct: float, net_main_flow: float, *, signal_bias: str) -> str:
    trend = "上涨" if change_pct > 0 else "走弱" if change_pct < 0 else "持平"
    flow = "主力净流入" if net_main_flow > 0 else "主力净流出" if net_main_flow < 0 else "主力流向平稳"
    signal_note = {
        "negative": "天气扰动偏弱势",
        "positive": "天气扰动偏修复",
        "neutral": "天气影响中性",
    }[signal_bias]
    return f"{trend} {abs(change_pct):.2f}% ，{flow} {abs(net_main_flow):.2f} 亿，{signal_note}"


async def fetch_market_impact(region: str, signal: str, horizon: str) -> Dict[str, Any]:
    signal_bias, drivers = _classify_signal(signal)
    params = {
        "pn": "1",
        "pz": "8",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": _choose_region_filter(region),
        "fields": DEFAULT_FIELDS,
    }
    headers = {
        "Referer": "https://quote.eastmoney.com/",
        "User-Agent": "Mozilla/5.0",
    }

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS, headers=headers) as client:
        for attempt in range(DEFAULT_RETRIES + 1):
            try:
                response = await client.get(EASTMONEY_BASE_URL, params=params)
            except httpx.TimeoutException:
                if attempt < DEFAULT_RETRIES:
                    await asyncio.sleep(DEFAULT_BACKOFF_SECONDS * (2**attempt))
                    continue
                raise MarketDataError(
                    503,
                    {"code": "SERVICE_UNAVAILABLE", "message": "market upstream timeout"},
                )
            except httpx.RequestError:
                if attempt < DEFAULT_RETRIES:
                    await asyncio.sleep(DEFAULT_BACKOFF_SECONDS * (2**attempt))
                    continue
                raise MarketDataError(
                    503,
                    {"code": "SERVICE_UNAVAILABLE", "message": "market upstream unavailable"},
                )
            if response.status_code >= 400:
                raise MarketDataError(
                    response.status_code,
                    {"code": "UPSTREAM_ERROR", "message": response.text[:200]},
                )
            try:
                payload = response.json()
            except ValueError as exc:  # pragma: no cover - defensive
                raise MarketDataError(
                    502,
                    {"code": "UPSTREAM_ERROR", "message": "invalid market upstream response"},
                ) from exc
            break
        else:  # pragma: no cover - loop exits above
            raise MarketDataError(
                503,
                {"code": "SERVICE_UNAVAILABLE", "message": "market upstream unavailable"},
            )

    data = payload.get("data") or {}
    diff_items = data.get("diff") or []
    if not diff_items:
        raise MarketDataError(
            502,
            {"code": "UPSTREAM_ERROR", "message": "market upstream returned no sector data"},
        )

    sectors: List[Dict[str, Any]] = []
    positive_count = 0
    negative_count = 0
    confidence_components: List[float] = []
    for item in diff_items[:4]:
        change_pct = float(item.get("f3") or 0.0)
        net_main_flow_raw = float(item.get("f62") or 0.0)
        net_main_flow = net_main_flow_raw / 100000000.0
        impact = _impact_direction(change_pct, net_main_flow, signal_bias=signal_bias)
        if impact == "positive":
            positive_count += 1
        elif impact == "negative":
            negative_count += 1
        confidence_components.append(min(1.0, abs(change_pct) / 4 + abs(net_main_flow) / 10))
        sectors.append(
            {
                "name": item.get("f14") or item.get("f12") or "未知板块",
                "impact": impact,
                "reason": _sector_reason(
                    str(item.get("f14") or item.get("f12") or "未知板块"),
                    change_pct,
                    net_main_flow,
                    signal_bias=signal_bias,
                ),
                "code": item.get("f12"),
                "changePct": round(change_pct, 2),
                "mainFlowYi": round(net_main_flow, 2),
            }
        )

    if positive_count > negative_count:
        market_bias = "positive"
    elif negative_count > positive_count:
        market_bias = "negative"
    else:
        market_bias = "cautious"

    confidence = round(
        min(
            0.95,
            0.45 + (sum(confidence_components) / max(len(confidence_components), 1)) * 0.4,
        ),
        2,
    )
    updated_at = datetime.now(timezone.utc).isoformat()
    return {
        "region": region,
        "updatedAt": updated_at,
        "weatherSignal": signal,
        "marketBias": market_bias,
        "confidence": confidence,
        "sectors": sectors,
        "drivers": drivers or [signal] if signal else [],
        "disclaimer": "仅供参考，不构成投资建议。",
        "source": "eastmoney",
        "horizon": horizon,
    }
