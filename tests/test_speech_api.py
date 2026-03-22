from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_asr_returns_503_when_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("SPEECH_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    response = client.post(
        "/api/v1/asr",
        json={
            "audioBase64": "aGVsbG8=",
            "filename": "sample.webm",
            "contentType": "audio/webm",
            "language": "zh",
        },
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["code"] == "ASR_NOT_CONFIGURED"


def test_tts_returns_503_when_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("SPEECH_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    response = client.post(
        "/api/v1/tts",
        json={"text": "你好，今天天气怎么样？", "voice": "alloy", "format": "mp3"},
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["code"] == "TTS_NOT_CONFIGURED"
