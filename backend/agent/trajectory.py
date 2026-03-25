from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AgentToolCall(BaseModel):
    name: str
    args: Dict[str, Any] = Field(default_factory=dict)


class AgentThought(BaseModel):
    reasoning: str
    tool: Optional[AgentToolCall] = None
    final: bool = False
    answer: Optional[str] = None


class AgentStep(BaseModel):
    step: int
    type: Literal["thought", "action", "observation", "final"]
    title: str
    content: str
    tool: Optional[str] = None
    args: Optional[Dict[str, Any]] = None
    observation: Optional[Dict[str, Any]] = None
    answer: Optional[str] = None


class AgentResult(BaseModel):
    answer: str
    trajectory: List[AgentStep] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    toolsUsed: List[str] = Field(default_factory=list)
    sessionId: Optional[str] = None
    userId: Optional[str] = None
    traceId: Optional[str] = None
