from __future__ import annotations

from typing import Any, Dict

from backend.agent.tools.base import ToolRegistry, ToolSpec
from backend.rag.retriever import get_retriever


async def search_knowledge_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    query = str(args.get("query") or "").strip()
    top_k = int(args.get("top_k", 5) or 5)
    items = get_retriever().retrieve(query, top_k=top_k)
    return {"query": query, "items": items, "count": len(items), "source": "rag:tfidf"}


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="search_knowledge",
            description="从本地知识库检索相关内容，用于回答专业问题",
            handler=search_knowledge_tool,
        )
    )
