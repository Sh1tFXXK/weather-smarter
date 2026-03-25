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


def _normalize_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


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


def _build_tags(
    conditions: List[str],
    interest: str,
    risk: str,
    *,
    priority_tags: Optional[List[str]] = None,
    family_structure: Optional[List[str]] = None,
    asset_preferences: Optional[List[str]] = None,
    schedule_windows: Optional[List[str]] = None,
    decision_style: str = "",
    role: str = "",
    organization: str = "",
    home_base: str = "",
) -> List[str]:
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
    for item in (priority_tags or [])[:3]:
        tags.append(item)
    if family_structure:
        tags.append("家庭结构")
    if asset_preferences:
        tags.append("资产偏好")
    if schedule_windows:
        tags.append("作息窗口")
    if decision_style:
        tags.append(f"决策:{decision_style}")
    if role:
        tags.append("角色画像")
    if organization:
        tags.append("组织上下文")
    if home_base:
        tags.append("常驻地")
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
    family_structure: Optional[List[str]],
    asset_preferences: Optional[List[str]],
    schedule_windows: Optional[List[str]],
    decision_style: str,
    role: str,
    home_base: str,
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
    if family_structure:
        strategies.append(f"涉及家庭协同的信息需显式纳入：{' / '.join(family_structure[:2])}。")
    if asset_preferences:
        strategies.append(f"资产相关判断优先贴合这些偏好：{' / '.join(asset_preferences[:2])}。")
    if schedule_windows:
        strategies.append(f"提醒与执行建议需落在这些时间窗：{' / '.join(schedule_windows[:2])}。")
    if decision_style:
        strategies.append(f"输出语气与证据密度要匹配决策风格：{decision_style}。")
    if role or home_base:
        strategies.append(f"结合身份与常驻地输出结论：{' / '.join([item for item in [role, home_base] if item])}。")
    if not strategies and memory:
        strategies.append("继续积累查询与执行历史，以提高偏好判断稳定性。")
    return strategies[:4]


def _extract_execution_preference(
    memory: Optional[List[Dict[str, Any]]],
    *,
    schedule_windows: Optional[List[str]] = None,
    decision_style: str = "",
    family_structure: Optional[List[str]] = None,
) -> str:
    if schedule_windows:
        return "时间窗驱动型"
    if any(token in decision_style for token in ["果断", "执行", "直接", "拍板"]):
        return "行动执行型"
    if family_structure:
        return "协同执行型"
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


def _extract_adoption_tendency(
    memory: Optional[List[Dict[str, Any]]],
    *,
    asset_preferences: Optional[List[str]] = None,
    decision_style: str = "",
    priority_tags: Optional[List[str]] = None,
) -> str:
    if asset_preferences:
        return "偏好收益与风险对照"
    if any(token in decision_style for token in ["数据", "证据", "分析", "理性"]):
        return "偏好证据支撑"
    if priority_tags and any("家庭" in item or "孩子" in item for item in priority_tags):
        return "偏好场景化结论"
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
    profile = health_profile or {}
    display_name = str(profile.get("display_name") or "").strip()
    identity_summary = str(profile.get("identity_summary") or "").strip()
    role = str(profile.get("role") or "").strip()
    organization = str(profile.get("organization") or "").strip()
    home_base = str(profile.get("home_base") or "").strip()
    family_structure = _normalize_list(profile.get("family_structure"))
    asset_preferences = _normalize_list(profile.get("asset_preferences"))
    schedule_windows = _normalize_list(profile.get("schedule_windows"))
    decision_style = str(profile.get("decision_style") or "").strip()
    priority_tags = _normalize_list(profile.get("priority_tags"))
    work_context = str(profile.get("work_context") or "").strip()
    long_term_memory = str(profile.get("long_term_memory") or "").strip()
    preferences = _normalize_list(profile.get("preferences"))
    goals = _normalize_list(profile.get("goals"))
    constraints = _normalize_list(profile.get("constraints"))
    routines = _normalize_list(profile.get("routines"))
    important_people = _normalize_list(profile.get("important_people"))
    important_locations = _normalize_list(profile.get("important_locations"))
    conditions = _normalize_list(profile.get("conditions"))
    note = str(profile.get("note") or "").strip()
    text = _normalize_text(memory)
    explicit_text = "\n".join(
        [
            display_name,
            identity_summary,
            role,
            organization,
            home_base,
            decision_style,
            work_context,
            long_term_memory,
            note,
            "\n".join(priority_tags),
            "\n".join(family_structure),
            "\n".join(asset_preferences),
            "\n".join(schedule_windows),
            "\n".join(preferences),
            "\n".join(goals),
            "\n".join(constraints),
            "\n".join(routines),
            "\n".join(important_people),
            "\n".join(important_locations),
            "\n".join(conditions),
        ]
    ).strip()
    full_text = f"{explicit_text}\n{text}".strip()
    top_interest = _detect_top_interest(full_text)
    risk_preference = _detect_risk_preference(full_text)
    tags = _build_tags(
        conditions,
        top_interest,
        risk_preference,
        priority_tags=priority_tags,
        family_structure=family_structure,
        asset_preferences=asset_preferences,
        schedule_windows=schedule_windows,
        decision_style=decision_style,
        role=role,
        organization=organization,
        home_base=home_base,
    )
    for item in preferences[:3]:
        tags.append(item)
    for item in goals[:2]:
        tags.append(f"目标:{item}")
    for item in family_structure[:2]:
        tags.append(f"家庭:{item}")
    for item in asset_preferences[:2]:
        tags.append(f"资产:{item}")
    if work_context:
        tags.append("工作上下文")
    if important_locations:
        tags.append("地点记忆")
    if important_people:
        tags.append("人物记忆")
    seen = set()
    deduped_tags: List[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            deduped_tags.append(tag)
    tags = deduped_tags[:8]
    scenario_preferences = _extract_scenario_preferences(memory)
    strategy_recommendations = _extract_strategy_recommendations(
        conditions=conditions,
        top_interest=top_interest,
        risk_preference=risk_preference,
        family_structure=family_structure,
        asset_preferences=asset_preferences,
        schedule_windows=schedule_windows,
        decision_style=decision_style,
        role=role,
        home_base=home_base,
        memory=memory,
    )
    if goals:
        strategy_recommendations.insert(0, f"优先围绕用户目标输出可执行建议：{' / '.join(goals[:2])}。")
    if constraints:
        strategy_recommendations.insert(0, f"建议需显式避开这些约束：{' / '.join(constraints[:3])}。")
    if routines:
        strategy_recommendations.append(f"结合固定节律输出提醒：{' / '.join(routines[:2])}。")
    if schedule_windows:
        strategy_recommendations.append(f"执行时间窗优先级较高：{' / '.join(schedule_windows[:2])}。")
    if important_locations:
        strategy_recommendations.append(f"地点偏好优先级较高：{' / '.join(important_locations[:2])}。")
    if not strategy_recommendations:
        strategy_recommendations = ["继续积累用户背景、目标与行为记录，以稳定长期画像。"]
    strategy_recommendations = strategy_recommendations[:6]
    execution_preference = _extract_execution_preference(
        memory,
        schedule_windows=schedule_windows,
        decision_style=decision_style,
        family_structure=family_structure,
    )
    adoption_tendency = _extract_adoption_tendency(
        memory,
        asset_preferences=asset_preferences,
        decision_style=decision_style,
        priority_tags=priority_tags,
    )
    memory_count = len(memory or [])
    summary_parts: List[str] = []
    if display_name:
        summary_parts.append(f"用户标识为 {display_name}")
    if identity_summary:
        summary_parts.append(identity_summary)
    if role or organization:
        summary_parts.append(f"角色身份为 {' / '.join([item for item in [role, organization] if item])}")
    if home_base:
        summary_parts.append(f"常驻城市为 {home_base}")
    if family_structure:
        summary_parts.append(f"家庭结构包括 {' / '.join(family_structure[:3])}")
    if asset_preferences:
        summary_parts.append(f"资产偏好集中在 {' / '.join(asset_preferences[:3])}")
    if schedule_windows:
        summary_parts.append(f"作息时间窗为 {' / '.join(schedule_windows[:3])}")
    if decision_style:
        summary_parts.append(f"显式决策风格为 {decision_style}")
    if goals:
        summary_parts.append(f"当前目标包括 {' / '.join(goals[:3])}")
    if preferences:
        summary_parts.append(f"偏好集中在 {' / '.join(preferences[:3])}")
    if constraints:
        summary_parts.append(f"明确约束为 {' / '.join(constraints[:3])}")
    if routines:
        summary_parts.append(f"日常节律包含 {' / '.join(routines[:2])}")
    if important_locations:
        summary_parts.append(f"重要地点为 {' / '.join(important_locations[:3])}")
    if important_people:
        summary_parts.append(f"重要人物包括 {' / '.join(important_people[:3])}")
    if work_context:
        summary_parts.append(f"工作上下文：{work_context}")
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
        "display_name": display_name or user_id,
        "persona": profile.get("persona") or " / ".join(tags[:3]) if tags else "通用用户",
        "tags": tags,
        "top_interest": top_interest,
        "risk_preference": risk_preference,
        "condition_count": len(conditions),
        "memory_count": memory_count,
        "profile_completeness": (
            "high"
            if profile and (memory_count >= 2 or identity_summary or goals or preferences)
            else "medium"
            if profile or memory_count
            else "low"
        ),
        "summary": "；".join(summary_parts) or "当前仅有基础用户信息，建议补充长期档案与使用记录。",
        "scenario_preferences": scenario_preferences,
        "strategy_recommendations": strategy_recommendations,
        "execution_preference": execution_preference,
        "adoption_tendency": adoption_tendency,
        "evidence": {
            "profile": {
                "display_name": display_name,
                "identity_summary": identity_summary,
                "role": role,
                "organization": organization,
                "home_base": home_base,
                "family_structure": family_structure,
                "asset_preferences": asset_preferences,
                "schedule_windows": schedule_windows,
                "decision_style": decision_style,
                "priority_tags": priority_tags,
                "preferences": preferences,
                "goals": goals,
                "constraints": constraints,
                "routines": routines,
                "important_people": important_people,
                "important_locations": important_locations,
                "work_context": work_context,
                "long_term_memory": long_term_memory,
            },
            "conditions": conditions,
            "note": note,
            "recent_memory": (memory or [])[-3:],
        },
    }
