
from __future__ import annotations

import base64
import logging
from typing import Optional, Protocol, runtime_checkable

from app.core.settings import get_settings

logger = logging.getLogger(__name__)


# ── Custom errors ─────────────────────────────────────────────────────────────


class VoiceServiceError(Exception):
    """Raised when STT or TTS fails."""


# ── STT protocol + providers ──────────────────────────────────────────────────


@runtime_checkable
class STTProvider(Protocol):
    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> str: ...


class StubSTTProvider:
    """Stub provider for development / testing (returns a placeholder)."""

    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        logger.warning("StubSTTProvider: returning placeholder transcription.")
        return "[STT provider not configured — set STT_PROVIDER and STT_API_KEY]"


class GoogleSTTProvider:
    """Google Cloud Speech-to-Text provider."""

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        import httpx

        encoding_map = {
            "audio/wav": "LINEAR16",
            "audio/webm": "WEBM_OPUS",
            "audio/ogg": "OGG_OPUS",
            "audio/flac": "FLAC",
            "audio/mp3": "MP3",
        }
        encoding = encoding_map.get(mime_type, "LINEAR16")
        audio_b64 = base64.b64encode(audio_bytes).decode()

        payload = {
            "config": {"encoding": encoding, "languageCode": "en-IN", "enableAutomaticPunctuation": True},
            "audio": {"content": audio_b64},
        }
        url = f"https://speech.googleapis.com/v1/speech:recognize?key={self._key}"

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as exc:
                raise VoiceServiceError(f"Google STT failed: {exc}") from exc

        results = data.get("results", [])
        if not results:
            return ""
        return results[0]["alternatives"][0].get("transcript", "")


class AudexumSTTProvider:
    """Audexum Speech-to-Text provider."""

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        import httpx
        import asyncio

        url = "https://audexum.com/api/transcribe"
        headers = {"Authorization": f"Bearer {self._key}"}
        ext = mime_type.split("/")[-1] if "/" in mime_type else "wav"
        files = {"audio": (f"recording.{ext}", audio_bytes, mime_type)}

        for attempt in range(5):
            async with httpx.AsyncClient(timeout=30) as client:
                try:
                    resp = await client.post(url, headers=headers, files=files, data={"timestamps": "false"})
                    if resp.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    return data.get("text", "")
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (401, 402, 403):
                        raise VoiceServiceError(f"Audexum STT Auth/Billing Error: {exc.response.status_code}") from exc
                    raise VoiceServiceError(f"Audexum STT failed: {exc}") from exc
                except httpx.HTTPError as exc:
                    raise VoiceServiceError(f"Audexum STT failed: {exc}") from exc
        raise VoiceServiceError("Audexum STT failed: max retries for 429 exceeded.")


# ── TTS protocol + providers ──────────────────────────────────────────────────


@runtime_checkable
class TTSProvider(Protocol):
    async def synthesize(self, text: str) -> bytes: ...


class StubTTSProvider:
    """Stub provider for development / testing."""

    async def synthesize(self, text: str) -> bytes:
        logger.warning("StubTTSProvider: no audio generated.")
        return b""


class GoogleTTSProvider:
    """Google Cloud Text-to-Speech provider."""

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def synthesize(self, text: str) -> bytes:
        import httpx

        payload = {
            "input": {"text": text},
            "voice": {"languageCode": "en-IN", "name": "en-IN-Standard-A"},
            "audioConfig": {"audioEncoding": "MP3"},
        }
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self._key}"

        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as exc:
                raise VoiceServiceError(f"Google TTS failed: {exc}") from exc

        audio_b64 = data.get("audioContent", "")
        return base64.b64decode(audio_b64)


class AudexumTTSProvider:
    """Audexum Text-to-Speech provider."""

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def synthesize(self, text: str) -> bytes:
        import httpx
        import asyncio

        url = "https://audexum.com/api/synthesize"
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json"
        }
        payload = {"text": text, "format": "mp3"}

        for attempt in range(5):
            async with httpx.AsyncClient(timeout=20) as client:
                try:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    resp.raise_for_status()
                    return resp.content
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (401, 402, 403):
                        raise VoiceServiceError(f"Audexum TTS Auth/Billing Error: {exc.response.status_code}") from exc
                    raise VoiceServiceError(f"Audexum TTS failed: {exc}") from exc
                except httpx.HTTPError as exc:
                    raise VoiceServiceError(f"Audexum TTS failed: {exc}") from exc
        raise VoiceServiceError("Audexum TTS failed: max retries for 429 exceeded.")


# ── VoiceService facade ───────────────────────────────────────────────────────


class VoiceService:
    """
    Coordinates STT and TTS.
    Selects providers from configuration; falls back to stubs gracefully.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._stt = self._build_stt(settings.stt_provider, settings)
        self._tts = self._build_tts(settings.tts_provider, settings)

    @staticmethod
    def _build_stt(provider: str, settings) -> STTProvider:
        if provider == "google" and settings.stt_api_key:
            logger.info("VoiceService: STT → GoogleSTTProvider")
            return GoogleSTTProvider(settings.stt_api_key)
        elif provider == "audexum" and settings.audexum_api_key:
            logger.info("VoiceService: STT → AudexumSTTProvider")
            return AudexumSTTProvider(settings.audexum_api_key)
        logger.warning("VoiceService: STT → StubSTTProvider (set STT_PROVIDER + STT_API_KEY)")
        return StubSTTProvider()

    @staticmethod
    def _build_tts(provider: str, settings) -> TTSProvider:
        if provider == "google" and settings.tts_api_key:
            logger.info("VoiceService: TTS → GoogleTTSProvider")
            return GoogleTTSProvider(settings.tts_api_key)
        elif provider == "audexum" and settings.audexum_api_key:
            logger.info("VoiceService: TTS → AudexumTTSProvider")
            return AudexumTTSProvider(settings.audexum_api_key)
        logger.warning("VoiceService: TTS → StubTTSProvider (set TTS_PROVIDER + TTS_API_KEY)")
        return StubTTSProvider()

    async def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
        """Convert audio bytes to text."""
        try:
            return await self._stt.transcribe(audio_bytes, mime_type)
        except VoiceServiceError:
            raise
        except Exception as exc:
            raise VoiceServiceError(f"Unexpected STT error: {exc}") from exc

    async def synthesize(self, text: str) -> bytes:
        """Convert text to audio bytes (MP3)."""
        try:
            return await self._tts.synthesize(text)
        except VoiceServiceError:
            raise
        except Exception as exc:
            raise VoiceServiceError(f"Unexpected TTS error: {exc}") from exc
