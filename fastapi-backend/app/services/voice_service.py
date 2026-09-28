
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
    async def transcribe(self, audio_bytes: bytes, mime_type: str, language: str = "en") -> str: ...


class StubSTTProvider:
    """Stub provider for development / testing (returns a placeholder)."""

    async def transcribe(self, audio_bytes: bytes, mime_type: str, language: str = "en") -> str:
        logger.warning("StubSTTProvider: returning placeholder transcription.")
        return "[STT provider not configured — set STT_PROVIDER and STT_API_KEY]"


class GoogleSTTProvider:
    """Google Cloud Speech-to-Text provider."""

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def transcribe(self, audio_bytes: bytes, mime_type: str, language: str = "en") -> str:
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
        
        lang_map = {"hi": "hi-IN", "mr": "mr-IN", "gu": "gu-IN", "ta": "ta-IN", "te": "te-IN", "kn": "kn-IN", "ml": "ml-IN", "bn": "bn-IN"}
        stt_lang = lang_map.get(language, "en-IN")

        payload = {
            "config": {"encoding": encoding, "languageCode": stt_lang, "enableAutomaticPunctuation": True},
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

    async def transcribe(self, audio_bytes: bytes, mime_type: str, language: str = "en") -> str:
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
                    err_text = exc.response.text
                    if exc.response.status_code in (401, 402, 403):
                        raise VoiceServiceError(f"Audexum STT Auth/Billing Error: {exc.response.status_code} - {err_text}") from exc
                    raise VoiceServiceError(f"Audexum STT failed: {exc} - Response: {err_text}") from exc
                except httpx.HTTPError as exc:
                    raise VoiceServiceError(f"Audexum STT failed: {exc}") from exc
        raise VoiceServiceError("Audexum STT failed: max retries for 429 exceeded.")

class GroqSTTProvider:
    """Groq Speech-to-Text provider (Uses Whisper, Free, Fast)."""

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def transcribe(self, audio_bytes: bytes, mime_type: str, language: str = "en") -> str:
        import httpx
        
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self._key}"}
        
        ext = mime_type.split("/")[-1] if "/" in mime_type else "webm"
        # Groq expects a filename with a proper extension for whisper
        files = {"file": (f"recording.{ext}", audio_bytes, mime_type)}
        data = {"model": "whisper-large-v3"}
        if language != "en":
            data["language"] = language
        
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(url, headers=headers, files=files, data=data)
                resp.raise_for_status()
                result = resp.json()
                return result.get("text", "")
            except Exception as exc:
                raise VoiceServiceError(f"Groq STT failed: {exc}") from exc

class GSTTProvider:
    """Free Google STT using SpeechRecognition and PyAV (no API key required)."""

    def __init__(self) -> None:
        pass

    async def transcribe(self, audio_bytes: bytes, mime_type: str, language: str = "en") -> str:
        import speech_recognition as sr
        import av
        import io
        import wave
        import asyncio

        def _transcribe():
            # Convert WebM to WAV using PyAV
            input_io = io.BytesIO(audio_bytes)
            try:
                container = av.open(input_io)
            except Exception:
                input_io.seek(0)
                container = av.open(input_io, format='webm')
                
            audio_stream = container.streams.audio[0]
            
            output_io = io.BytesIO()
            with wave.open(output_io, 'wb') as wave_write:
                wave_write.setnchannels(1)
                wave_write.setsampwidth(2)
                wave_write.setframerate(16000)
                
                resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
                
                for frame in container.decode(audio_stream):
                    for resampled_frame in resampler.resample(frame):
                        wave_write.writeframes(bytes(resampled_frame.planes[0]))
            
            output_io.seek(0)
            
            recognizer = sr.Recognizer()
            with sr.AudioFile(output_io) as source:
                audio_data = recognizer.record(source)
            
            lang_map = {"hi": "hi-IN", "mr": "mr-IN", "gu": "gu-IN", "ta": "ta-IN", "te": "te-IN", "kn": "kn-IN", "ml": "ml-IN", "bn": "bn-IN"}
            stt_lang = lang_map.get(language, "en-IN")
            return recognizer.recognize_google(audio_data, language=stt_lang)

        try:
            return await asyncio.to_thread(_transcribe)
        except sr.UnknownValueError:
            return ""
        except Exception as exc:
            import traceback
            err = traceback.format_exc()
            with open("gstt_error.log", "w") as f:
                f.write(err)
            raise VoiceServiceError(f"GSTT failed: {exc}") from exc


# ── TTS protocol + providers ──────────────────────────────────────────────────


@runtime_checkable
class TTSProvider(Protocol):
    async def synthesize(self, text: str, language: str = "en") -> bytes: ...


class StubTTSProvider:
    """Stub provider for development / testing."""

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        logger.warning("StubTTSProvider: no audio generated.")
        return b""


class GoogleTTSProvider:
    """Google Cloud Text-to-Speech provider."""

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        import httpx

        lang_map = {"hi": "hi-IN", "mr": "mr-IN", "gu": "gu-IN", "ta": "ta-IN", "te": "te-IN", "kn": "kn-IN", "ml": "ml-IN", "bn": "bn-IN"}
        tts_lang = lang_map.get(language, "en-IN")

        payload = {
            "input": {"text": text},
            "voice": {"languageCode": tts_lang},
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

    async def synthesize(self, text: str, language: str = "en") -> bytes:
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

class EdgeTTSProvider:
    """Microsoft Edge Text-to-Speech provider (Free, Neural, Multi-lingual)."""

    def __init__(self) -> None:
        pass

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        import edge_tts
        
        voice_map = {
            "hi": "hi-IN-SwaraNeural",
            "mr": "mr-IN-AarohiNeural",
            "gu": "gu-IN-DhwaniNeural",
            "ta": "ta-IN-PallaviNeural",
            "te": "te-IN-ShrutiNeural",
            "kn": "kn-IN-SapnaNeural",
            "ml": "ml-IN-SobhanaNeural",
            "bn": "bn-IN-TanishaaNeural"
        }
        voice = voice_map.get(language, "en-IN-NeerjaNeural")
        
        try:
            communicate = edge_tts.Communicate(text, voice)
            audio_bytes = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes.extend(chunk["data"])
            return bytes(audio_bytes)
        except Exception as exc:
            raise VoiceServiceError(f"EdgeTTS failed: {exc}") from exc

class GTTSProvider:
    """gTTS (Google Translate Text-to-Speech) provider. Free, no API key required."""

    def __init__(self) -> None:
        pass

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        from gtts import gTTS
        import io
        import asyncio

        def _synthesize():
            # lang="en", tld="co.in" produces Indian English
            tts = gTTS(text=text, lang=language)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            return fp.getvalue()

        try:
            audio_bytes = await asyncio.to_thread(_synthesize)
            return audio_bytes
        except Exception as exc:
            raise VoiceServiceError(f"gTTS failed: {exc}") from exc


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
        elif provider == "groq" and getattr(settings, "groq_api_key", None):
            logger.info("VoiceService: STT → GroqSTTProvider")
            return GroqSTTProvider(settings.groq_api_key)
        elif provider == "gstt":
            logger.info("VoiceService: STT → GSTTProvider")
            return GSTTProvider()
        logger.warning("VoiceService: STT → StubSTTProvider (set STT_PROVIDER)")
        return StubSTTProvider()

    @staticmethod
    def _build_tts(provider: str, settings) -> TTSProvider:
        if provider == "google" and settings.tts_api_key:
            logger.info("VoiceService: TTS → GoogleTTSProvider")
            return GoogleTTSProvider(settings.tts_api_key)
        elif provider == "audexum" and settings.audexum_api_key:
            logger.info("VoiceService: TTS → AudexumTTSProvider")
            return AudexumTTSProvider(settings.audexum_api_key)
        elif provider == "edge":
            logger.info("VoiceService: TTS → EdgeTTSProvider")
            return EdgeTTSProvider()
        elif provider == "gtts":
            logger.info("VoiceService: TTS → GTTSProvider")
            return GTTSProvider()
        logger.warning("VoiceService: TTS → StubTTSProvider (set TTS_PROVIDER)")
        return StubTTSProvider()

    async def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav", language: str = "en") -> str:
        """Convert audio bytes to text."""
        try:
            return await self._stt.transcribe(audio_bytes, mime_type, language)
        except VoiceServiceError:
            raise
        except Exception as exc:
            raise VoiceServiceError(f"Unexpected STT error: {exc}") from exc

    async def translate_text(self, text: str, target_lang: str) -> str:
        if target_lang == "en" or not text.strip():
            return text
            
        import urllib.request
        import urllib.parse
        import json
        import asyncio
        
        def _do_translate():
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                        translated = "".join(item[0] for item in data[0] if item and item[0])
                        if translated:
                            return translated
            except Exception as e:
                logger.error(f"Failed to translate text to {target_lang}: {e}")
            return text
            
        return await asyncio.to_thread(_do_translate)

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        """Convert text to audio bytes (MP3)."""
        try:
            # Always translate the text first before feeding it to the native neural voice
            translated_text = await self.translate_text(text, language)
            return await self._tts.synthesize(translated_text, language)
        except VoiceServiceError:
            raise
        except Exception as exc:
            raise VoiceServiceError(f"Unexpected TTS error: {exc}") from exc
