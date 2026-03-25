from __future__ import annotations

from typing import Any, Dict

from backend.agent.memory_store import get_memory_store
from backend.agent.tools.base import ToolRegistry, ToolSpec


async def recall_memory_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    session_id = str(args.get("session_id") or "").strip()
    limit = int(args.get("limit", 6) or 6)
    items = get_memory_store().list_messages(session_id=session_id, limit=limit) if session_id else []
    query = str(args.get("query") or "").strip().lower()
    if query:
        items = [
            item for item in items
            if query in str(item.get("content") or "").lower()
            or query in str(item.get("metadata") or "").lower()
        ]
    return {
        "sessionId": session_id,
        "items": items,
        "count": len(items),
        "source": "memory:sqlite",
    }


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="recall_memory",
            description="检索用户的历史对话记忆",
            handler=recall_memory_tool,
        )
    )
