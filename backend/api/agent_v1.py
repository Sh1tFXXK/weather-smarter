from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agent.runner import AgentRunner
from backend.agent.tools import get_tool_registry
from backend.agent.trajectory import AgentResult


router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


class AgentRequest(BaseModel):
    goal: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    city: Optional[str] = None
    adcode: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    locale: Optional[str] = "zh-CN"
    lang: Optional[str] = "zh"
    hours: Optional[int] = 24
    days: Optional[int] = 7
    scheduled_time: Optional[str] = None
    task_type: Optional[str] = None
    region: Optional[str] = None
    horizon: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


def _build_context(payload: AgentRequest) -> Dict[str, Any]:
    context = dict(payload.context)
    context.setdefault("session_id", payload.session_id)
    context.setdefault("user_id", payload.user_id)
    context.setdefault("city", payload.city)
    context.setdefault("adcode", payload.adcode)
    context.setdefault("lat", payload.lat)
    context.setdefault("lon", payload.lon)
    context.setdefault("locale", payload.locale)
    context.setdefault("lang", payload.lang)
    context.setdefault("hours", payload.hours)
    context.setdefault("days", payload.days)
    context.setdefault("scheduled_time", payload.scheduled_time)
    context.setdefault("task_type", payload.task_type)
    context.setdefault("region", payload.region)
    context.setdefault("horizon", payload.horizon)
    context.setdefault("trace_id", f"agent-{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
    return context


@router.post("/run", response_model=AgentResult)
async def run_agent(payload: AgentRequest) -> AgentResult:
    runner = AgentRunner(tools=get_tool_registry())
    return await runner.run(payload.goal, _build_context(payload))


@router.post("/stream")
async def stream_agent(payload: AgentRequest) -> StreamingResponse:
    runner = AgentRunner(tools=get_tool_registry())
    context = _build_context(payload)

    async def event_gen() -> AsyncIterator[str]:
        async for step in runner.stream(payload.goal, context):
            yield f"data: {step.model_dump_json()}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
