from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.decision.diet_decision import evaluate_diet
from backend.decision.health_decision import evaluate_health
from backend.decision.schedule_decision import evaluate_schedule
from backend.decision.travel_decision import evaluate_travel


def evaluate_intent_decision(
    intent: str, weather: Dict[str, Any], slots: Optional[Dict[str, Optional[str]]] = None
) -> Tuple[str, str, List[str], List[str]]:
    dispatcher = {
        "travel_decision": evaluate_travel,
        "commute_decision": evaluate_travel,
        "sport_decision": evaluate_travel,
        "health_decision": evaluate_health,
        "diet_decision": evaluate_diet,
        "schedule_decision": evaluate_schedule,
        "task_decision": evaluate_schedule,
    }

    handler = dispatcher.get(intent)
    if handler:
        if intent in ("travel_decision", "commute_decision", "sport_decision"):
            return handler(weather, slots)
        if intent in ("schedule_decision", "task_decision"):
            return handler(weather, slots)
        return handler(weather)

    # fallback to travel decision for any other intent
    return evaluate_travel(weather, slots)
