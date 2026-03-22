import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.decision.decision_engine import evaluate_intent_decision

if __name__ == "__main__":
    print(evaluate_intent_decision("health_decision", {"weather": "霾", "aqi": 160, "temperature": 22, "uv": 3}))
