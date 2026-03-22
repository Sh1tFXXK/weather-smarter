from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _default_kb_path() -> Path:
    return Path(__file__).resolve().parent / "knowledge_base.jsonl"


def _load_kb(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


class RAGRetriever:
    def __init__(self, items: List[Dict[str, Any]]) -> None:
        self.items = items
        self._vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
        texts = [self._build_text(item) for item in items]
        self._matrix = self._vectorizer.fit_transform(texts) if texts else None

    @staticmethod
    def _build_text(item: Dict[str, Any]) -> str:
        parts = [
            item.get("title", ""),
            item.get("content", ""),
            " ".join(item.get("tags", []) or []),
            item.get("domain", ""),
        ]
        return " ".join([p for p in parts if p])

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if not query or not self.items or self._matrix is None:
            return []
        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._matrix).flatten()
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results: List[Dict[str, Any]] = []
        for idx, score in ranked[:top_k]:
            item = dict(self.items[idx])
            item["score"] = round(float(score), 4)
            results.append(item)
        return results


def build_query(
    *,
    query: str,
    intent: Optional[str],
    slots: Optional[Dict[str, Any]],
    environment: Optional[Dict[str, Any]],
) -> str:
    parts = [query]
    if intent:
        parts.append(intent)
    if slots:
        parts.extend([str(v) for v in slots.values() if v])
    if environment:
        weather = environment.get("weather") or {}
        parts.extend(
            [
                str(weather.get("status") or ""),
                str(weather.get("temperature") or ""),
                str(weather.get("aqi") or ""),
            ]
        )
        risk_flags = environment.get("riskFlags") or []
        parts.extend([str(flag) for flag in risk_flags])
    return " ".join([p for p in parts if p])


@lru_cache(maxsize=1)
def get_retriever() -> RAGRetriever:
    kb_path = Path(os.getenv("RAG_KB_PATH", str(_default_kb_path())))
    items = _load_kb(kb_path)
    return RAGRetriever(items)
