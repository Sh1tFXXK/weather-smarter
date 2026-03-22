from backend.nlp.intent import get_intent_classifier
from backend.nlp.slots import extract_slots


def test_intent_rule() -> None:
    classifier = get_intent_classifier()
    assert classifier.predict("要带伞吗") == "umbrella_decision"


def test_greeting_intent() -> None:
    classifier = get_intent_classifier()
    assert classifier.predict("你好") == "greeting"


def test_slot_extraction() -> None:
    slots = extract_slots("明天北京适合跑步吗")
    assert slots["city"] == "北京"
    assert slots["date"] == "tomorrow"
    assert slots["activity"] == "running"
