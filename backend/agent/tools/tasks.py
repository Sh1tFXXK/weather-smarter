from __future__ import annotations

from typing import Any, Dict

from backend.agent.task_store import get_task_store
from backend.agent.tools.base import ToolRegistry, ToolSpec


async def create_task_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    metadata = dict(args.get("metadata") or {})
    note = str(args.get("note") or "").strip()
    if note and "note" not in metadata:
        metadata["note"] = note
    return get_task_store().create_task(
        task_type=str(args.get("type") or "general"),
        scheduled_time=str(args.get("time") or args.get("scheduled_time") or ""),
        priority=int(args.get("priority", 5) or 5),
        metadata=metadata,
    )


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="create_task",
            description="创建一个定时提醒或待办任务",
            handler=create_task_tool,
        )
    )
