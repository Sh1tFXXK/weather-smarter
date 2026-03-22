from __future__ import annotations

from typing import List, Optional, Tuple

from backend.nlp.intent_data import INTENT_SAMPLES

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.svm import LinearSVC

    _SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - fallback if sklearn is not installed
    _SKLEARN_AVAILABLE = False


KEYWORD_INTENTS = [
    ("greeting", ["你好", "您好", "hi", "hello", "早上好", "晚上好"]),
    ("umbrella_decision", ["带伞", "雨伞", "下雨", "降雨", "雨衣"]),
    ("sport_decision", ["跑步", "运动", "健身", "骑行", "徒步"]),
    ("commute_decision", ["通勤", "上班", "下班", "早高峰", "晚高峰"]),
    ("clothing_decision", ["穿衣", "穿什么", "外套", "短袖", "长袖"]),
    ("car_wash_decision", ["洗车"]),
    ("travel_decision", ["出游", "旅行", "出门", "出行"]),
]


def _rule_intent(text: str) -> Optional[str]:
    for intent, keywords in KEYWORD_INTENTS:
        if any(keyword in text for keyword in keywords):
            return intent
    return None


def _build_training_set() -> Tuple[List[str], List[str]]:
    texts: List[str] = []
    labels: List[str] = []
    for intent, samples in INTENT_SAMPLES.items():
        for sample in samples:
            texts.append(sample)
            labels.append(intent)
    return texts, labels


class IntentClassifier:
    def __init__(self) -> None:
        self._use_sklearn = _SKLEARN_AVAILABLE
        self._trained = False
        if self._use_sklearn:
            self._vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
            self._model = LinearSVC()

    def _train(self) -> None:
        if not self._use_sklearn or self._trained:
            return
        texts, labels = _build_training_set()
        if not texts:
            self._trained = True
            return
        features = self._vectorizer.fit_transform(texts)
        self._model.fit(features, labels)
        self._trained = True

    def predict(self, text: str) -> str:
        rule_intent = _rule_intent(text)
        if rule_intent:
            return rule_intent

        if self._use_sklearn:
            if not self._trained:
                self._train()
            return self._model.predict(self._vectorizer.transform([text]))[0]

        return "weather_query"


_CLASSIFIER: Optional[IntentClassifier] = None


def get_intent_classifier() -> IntentClassifier:
    global _CLASSIFIER
    if _CLASSIFIER is None:
        _CLASSIFIER = IntentClassifier()
    return _CLASSIFIER
