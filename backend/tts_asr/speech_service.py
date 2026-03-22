from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


class SpeechServiceError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _speech_provider() -> str:
    provider = (os.getenv("SPEECH_PROVIDER") or os.getenv("LLM_PROVIDER") or "").lower()
    if provider == "llama_cpp":
        return ""
    return provider


def _openai_base_url() -> str:
    return (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")


def _openai_api_key() -> Optional[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key
    if os.getenv("OPENAI_BASE_URL"):
        return "lm-studio"
    return None


@dataclass
class SpeechService:
    timeout: float = 60.0

    def status(self) -> tuple[bool, str]:
        provider = _speech_provider()
        if provider != "openai":
            return False, "SPEECH_PROVIDER not configured for supported backend"
        if not _openai_api_key():
            return False, "OPENAI_API_KEY missing"
        return True, ""

    async def transcribe(
        self,
        *,
        audio_b64: str,
        filename: str,
        content_type: str,
        language: Optional[str],
        prompt: Optional[str],
    ) -> Dict[str, Any]:
        ok, reason = self.status()
        if not ok:
            raise SpeechServiceError("ASR_NOT_CONFIGURED", reason, status_code=503)

        try:
            audio_bytes = base64.b64decode(audio_b64)
        except Exception as exc:  # pragma: no cover - invalid base64 guard
            raise SpeechServiceError("INVALID_AUDIO", f"Invalid base64 audio: {exc}", status_code=400)

        files = {
            "file": (filename or "speech.webm", audio_bytes, content_type or "audio/webm"),
        }
        data = {
            "model": os.getenv("ASR_MODEL", "gpt-4o-mini-transcribe"),
        }
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{_openai_base_url()}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {_openai_api_key()}"},
                    data=data,
                    files=files,
                )
            except httpx.HTTPError as exc:
                raise SpeechServiceError("ASR_UPSTREAM_UNAVAILABLE", str(exc), status_code=503)

        if response.status_code >= 400:
            raise SpeechServiceError(
                "ASR_UPSTREAM_ERROR",
                response.text[:300],
                status_code=502 if response.status_code < 500 else 503,
            )

        payload = response.json()
        text = payload.get("text") or payload.get("transcript") or ""
        return {
            "text": text,
            "language": language or payload.get("language"),
            "durationMs": payload.get("duration_ms"),
            "provider": "openai",
            "model": data["model"],
            "raw": payload,
        }

    async def synthesize(
        self,
        *,
        text: str,
        voice: str,
        format_: str,
        instructions: Optional[str],
    ) -> Dict[str, Any]:
        ok, reason = self.status()
        if not ok:
            raise SpeechServiceError("TTS_NOT_CONFIGURED", reason, status_code=503)
        if not text.strip():
            raise SpeechServiceError("INVALID_TEXT", "Text is required", status_code=400)

        payload: Dict[str, Any] = {
            "model": os.getenv("TTS_MODEL", "gpt-4o-mini-tts"),
            "voice": voice or os.getenv("TTS_VOICE", "alloy"),
            "input": text,
            "format": format_ or os.getenv("TTS_FORMAT", "mp3"),
        }
        if instructions:
            payload["instructions"] = instructions

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{_openai_base_url()}/audio/speech",
                    headers={"Authorization": f"Bearer {_openai_api_key()}"},
                    json=payload,
                )
            except httpx.HTTPError as exc:
                raise SpeechServiceError("TTS_UPSTREAM_UNAVAILABLE", str(exc), status_code=503)

        if response.status_code >= 400:
            raise SpeechServiceError(
                "TTS_UPSTREAM_ERROR",
                response.text[:300],
                status_code=502 if response.status_code < 500 else 503,
            )

        audio_bytes = response.content
        return {
            "audioBase64": base64.b64encode(audio_bytes).decode("ascii"),
            "mimeType": f"audio/{payload['format']}",
            "provider": "openai",
            "model": payload["model"],
            "voice": payload["voice"],
        }


_SERVICE: Optional[SpeechService] = None


def get_speech_service() -> SpeechService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = SpeechService(timeout=float(os.getenv("SPEECH_TIMEOUT", "60")))
    return _SERVICE
