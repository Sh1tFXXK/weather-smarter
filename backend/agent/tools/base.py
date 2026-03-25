from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict


ToolHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._items: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        self._items[spec.name] = spec
        return spec

    def get(self, name: str) -> ToolSpec:
        return self._items[name]

    def has(self, name: str) -> bool:
        return name in self._items

    def list(self) -> list[ToolSpec]:
        return list(self._items.values())

    async def invoke(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return await self.get(name).handler(args)
