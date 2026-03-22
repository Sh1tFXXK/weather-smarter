from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional


INTEREST_KEYWORDS = {
    "commute": ["通勤", "上班", "骑行", "地铁", "公交", "开车"],
    "health": ["健康", "关节", "风湿", "哮喘", "过敏", "酸痛", "不适"],
    "sport": ["跑步", "运动", "锻炼", "户外", "骑行"],
    "travel": ["出行", "旅行", "航班", "高铁", "酒店"],
}

RISK_KEYWORDS = {
    "conservative": ["要带伞", "风险", "注意", "安全吗", "适合吗", "提醒"],
    "balanced": ["建议", "可以吗", "怎么安排", "是否需要"],
    "aggressive": ["照常", "坚持", "继续", "无所谓"],
}

CONDITION_TAGS = {
    "rheumatism": "湿冷敏感",
    "asthma": "呼吸敏感",
    "allergy": "过敏关注",
    "photosensitivity": "光照敏感",
    "cardio": "心血管关注",
}


def _normalize_text(memory: Optional[List[Dict[str, Any]]]) -> str:
    if not memory:
        return ""
    return "\n".join(str(item.get("content", "")) for item in memory if item.get("content"))


def _collect_metadata(memory: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not memory:
        return []
    return [item.get("metadata") or {} for item in memory]


def _detect_top_interest(text: str) -> str:
    scores: Counter[str] = Counter()
    for interest, keywords in INTEREST_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[interest] += 1
    return scores.most_common(1)[0][0] if scores else "general"


def _detect_risk_preference(text: str) -> str:
    scores: Counter[str] = Counter()
    for level, keywords in RISK_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[level] += 1
    return scores.most_common(1)[0][0] if scores else "balanced"


def _build_tags(conditions: List[str], interest: str, risk: str) -> List[str]:
    tags: List[str] = []
    for condition in conditions:
        label = CONDITION_TAGS.get(condition)
        if label:
            tags.append(label)
    if interest == "commute":
        tags.append("通勤优先")
    elif interest == "health":
        tags.append("健康管理")
    elif interest == "sport":
        tags.append("运动活跃")
    elif interest == "travel":
        tags.append("出行计划")
    if risk == "conservative":
        tags.append("谨慎决策")
    elif risk == "aggressive":
        tags.append("行动导向")
    else:
        tags.append("平衡决策")
    seen = set()
    deduped: List[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            deduped.append(tag)
    return deduped


def _extract_scenario_preferences(memory: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    metadata_items = _collect_metadata(memory)
    counter: Counter[str] = Counter()
    for item in metadata_items:
        intent = item.get("intent")
        if intent:
            counter[str(intent)] += 1
    labels = {
        "commute_decision": "通勤决策",
        "sport_decision": "运动安排",
        "umbrella_decision": "雨具准备",
        "clothing_decision": "穿衣建议",
        "travel_decision": "出行规划",
        "greeting": "闲聊问候",
    }
    return [
        {"scenario": labels.get(name, name), "count": count}
        for name, count in counter.most_common(3)
    ]


def _extract_strategy_recommendations(
    *,
    conditions: List[str],
    top_interest: str,
    risk_preference: str,
    memory: Optional[List[Dict[str, Any]]],
) -> List[str]:
    strategies: List[str] = []
    if "rheumatism" in conditions:
        strategies.append("遇到湿冷和降雨场景时，优先输出保暖与室内替代建议。")
    if "asthma" in conditions or "allergy" in conditions:
        strategies.append("空气质量或花粉波动时，优先输出佩戴口罩和降低户外暴露时长。")
    if top_interest == "commute":
        strategies.append("通勤场景优先推送降水、风力和体感温度的提前提醒。")
    elif top_interest == "sport":
        strategies.append("运动场景优先结合 AQI、降雨和温度给出强度调整建议。")
    elif top_interest == "travel":
        strategies.append("出行场景优先聚合天气趋势、交通风险和装备清单。")
    if risk_preference == "conservative":
        strategies.append("默认采用更保守阈值，提前提示风险而不是临界时才提醒。")
    elif risk_preference == "aggressive":
        strategies.append("建议输出里保留可继续执行的备选方案，而不是只给出停止建议。")
    if not strategies and memory:
        strategies.append("继续积累查询与执行历史，以提高偏好判断稳定性。")
    return strategies[:4]


def _extract_execution_preference(memory: Optional[List[Dict[str, Any]]]) -> str:
    metadata_items = _collect_metadata(memory)
    action_count = 0
    stop_signals = 0
    for item in metadata_items:
        decision = item.get("decision") or {}
        actions = decision.get("actions") or []
        if actions:
            action_count += len(actions)
        advice = str(decision.get("advice") or "")
        if any(token in advice for token in ["避免", "取消", "暂停", "不建议"]):
            stop_signals += 1
    if action_count >= 4 and stop_signals == 0:
        return "行动执行型"
    if stop_signals >= 2:
        return "风险规避型"
    return "平衡执行型"


def _extract_adoption_tendency(memory: Optional[List[Dict[str, Any]]]) -> str:
    metadata_items = _collect_metadata(memory)
    evidence_hits = 0
    action_hits = 0
    for item in metadata_items:
        if (item.get("evidence") or []):
            evidence_hits += 1
        decision = item.get("decision") or {}
        if decision.get("actions"):
            action_hits += 1
    if action_hits >= 2 and evidence_hits >= 1:
        return "偏好可执行建议"
    if evidence_hits >= 2:
        return "偏好证据支撑"
    return "偏好简洁结论"


def analyze_user_profile(
    *,
    user_id: str,
    health_profile: Optional[Dict[str, Any]],
    memory: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    conditions = list((health_profile or {}).get("conditions") or [])
    note = (health_profile or {}).get("note") or ""
    text = _normalize_text(memory)
    full_text = f"{text}\n{note}".strip()
    top_interest = _detect_top_interest(full_text)
    risk_preference = _detect_risk_preference(full_text)
    tags = _build_tags(conditions, top_interest, risk_preference)
    scenario_preferences = _extract_scenario_preferences(memory)
    strategy_recommendations = _extract_strategy_recommendations(
        conditions=conditions,
        top_interest=top_interest,
        risk_preference=risk_preference,
        memory=memory,
    )
    execution_preference = _extract_execution_preference(memory)
    adoption_tendency = _extract_adoption_tendency(memory)
    memory_count = len(memory or [])
    summary_parts: List[str] = []
    if conditions:
        summary_parts.append(f"健康特征集中在 {', '.join(conditions)}")
    if top_interest != "general":
        summary_parts.append(f"近期关注重心偏向 {top_interest}")
    if risk_preference == "conservative":
        summary_parts.append("决策风格偏谨慎")
    elif risk_preference == "aggressive":
        summary_parts.append("决策风格偏行动导向")
    else:
        summary_parts.append("决策风格相对平衡")
    if note:
        summary_parts.append(f"备注显示 {note}")
    return {
        "user_id": user_id,
        "persona": " / ".join(tags[:3]) if tags else "通用用户",
        "tags": tags,
        "top_interest": top_interest,
        "risk_preference": risk_preference,
        "condition_count": len(conditions),
        "memory_count": memory_count,
        "profile_completeness": "high" if health_profile and memory_count >= 2 else "medium" if health_profile or memory_count else "low",
        "summary": "；".join(summary_parts) or "当前仅有基础用户信息，建议补充健康档案和使用记录。",
        "scenario_preferences": scenario_preferences,
        "strategy_recommendations": strategy_recommendations,
        "execution_preference": execution_preference,
        "adoption_tendency": adoption_tendency,
        "evidence": {
            "conditions": conditions,
            "note": note,
            "recent_memory": (memory or [])[-3:],
        },
    }
