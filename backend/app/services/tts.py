"""Text-to-speech providers.

Mock mode synthesizes a real, playable WAV file locally so the whole pipeline
and frontend can be exercised before a Sarvam key exists. Real mode calls
Sarvam Bulbul v3 and normalizes the response to WAV bytes.
"""

from __future__ import annotations

import base64
import hashlib
import io
import math
import shutil
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_DEFAULT_MODEL = "bulbul:v3"
SARVAM_DEFAULT_SPEAKER = "anushka"
SARVAM_MAX_CHARS = 2400
SAMPLE_RATE = 22050
WORDS_PER_SECOND = 2.5


class TTSError(RuntimeError):
    """Speech synthesis failed."""


@dataclass
class TTSResult:
    audio_bytes: bytes
    duration_sec: int
    audio_format: str = "wav"

    @property
    def extension(self) -> str:
        return "wav" if self.audio_format == "wav" else self.audio_format


class TTSProvider(Protocol):
    def synthesize(self, text: str, language_code: str) -> TTSResult: ...


def estimate_duration(text: str) -> int:
    words = len(text.split())
    return max(3, round(words / WORDS_PER_SECOND))


def _tone_wav(duration_sec: int) -> bytes:
    """Build a quiet speech-like tone; deterministic and dependency-free."""
    frames = bytearray()
    total = SAMPLE_RATE * duration_sec
    for index in range(total):
        # Gentle wobble so the file is audible but not harsh.
        envelope = 0.12 * (1 + math.sin(2 * math.pi * index / (SAMPLE_RATE * 4)))
        sample = int(32767 * envelope * math.sin(2 * math.pi * 220 * index / SAMPLE_RATE))
        frames += struct.pack("<h", sample)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(bytes(frames))
    return buffer.getvalue()


def _wav_duration(data: bytes) -> int:
    try:
        with wave.open(io.BytesIO(data), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate() or SAMPLE_RATE
            return max(1, round(frames / rate))
    except (wave.Error, EOFError):
        return 0


def _merge_wav(chunks: list[bytes]) -> bytes:
    if len(chunks) == 1:
        return chunks[0]

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        for chunk in chunks:
            with wave.open(io.BytesIO(chunk), "rb") as source:
                if source.getframerate() != SAMPLE_RATE or source.getsampwidth() != 2:
                    raise TTSError("Sarvam returned audio with an unexpected sample format")
                output.writeframes(source.readframes(source.getnframes()))
    return buffer.getvalue()


def _split_text(text: str, limit: int = SARVAM_MAX_CHARS) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]

    sentences = [part.strip() for part in text.replace("\n", " ").split(". ") if part.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current}. {sentence}" if current else sentence
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = sentence[:limit]
    if current:
        chunks.append(current)
    return chunks


class MockTTSProvider:
    """Local WAV synthesis used whenever ``USE_MOCK_TTS`` is on."""

    def synthesize(self, text: str, language_code: str) -> TTSResult:
        if not text.strip():
            raise TTSError("Cannot synthesize empty text")
        duration = estimate_duration(text)
        return TTSResult(audio_bytes=_tone_wav(duration), duration_sec=duration)


class SarvamTTSProvider:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = SARVAM_DEFAULT_MODEL,
        speaker: str = SARVAM_DEFAULT_SPEAKER,
        timeout_sec: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.speaker = speaker
        self.timeout_sec = timeout_sec
        self._client = client

    def _post(self, text: str, language_code: str) -> bytes:
        payload = {
            "text": text,
            "target_language_code": language_code,
            "speaker": self.speaker,
            "model": self.model,
            "speech_sample_rate": SAMPLE_RATE,
            "enable_preprocessing": True,
        }
        headers = {"api-subscription-key": self.api_key}
        if self._client is not None:
            response = self._client.post(SARVAM_TTS_URL, json=payload, headers=headers)
        else:
            with httpx.Client(timeout=self.timeout_sec) as client:
                response = client.post(SARVAM_TTS_URL, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()
        audios = body.get("audios") or []
        if not audios:
            raise TTSError("Sarvam response contained no audio")
        return base64.b64decode(audios[0])

    def synthesize(self, text: str, language_code: str) -> TTSResult:
        if not text.strip():
            raise TTSError("Cannot synthesize empty text")
        chunks = [self._post(chunk, language_code) for chunk in _split_text(text)]
        audio = _merge_wav(chunks)
        duration = _wav_duration(audio) or estimate_duration(text)
        return TTSResult(audio_bytes=audio, duration_sec=duration)


def get_tts_provider(settings: Settings | None = None) -> TTSProvider:
    settings = settings or get_settings()
    if settings.use_mock_tts or not settings.sarvam_api_key:
        return MockTTSProvider()
    return SarvamTTSProvider(
        settings.sarvam_api_key,
        model=settings.sarvam_tts_model,
        speaker=settings.sarvam_speaker,
    )


def media_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    path = Path(settings.data_dir) / "media"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_audio(task_id: str, result: TTSResult, settings: Settings | None = None) -> str:
    """Persist synthesized audio and return its public URL path."""
    destination = media_dir(settings) / f"{task_id}.{result.extension}"
    destination.write_bytes(result.audio_bytes)
    return f"/media/{destination.name}"


def audio_cache_path(
    text: str,
    language_code: str,
    settings: Settings | None = None,
) -> Path:
    digest = hashlib.sha256(
        f"{settings.sarvam_tts_model}:{settings.sarvam_speaker}\0{language_code}\0{text}".encode()
    ).hexdigest()[:40]
    directory = media_dir(settings) / "cache"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{digest}.wav"


def synthesize_and_store(
    task_id: str,
    text: str,
    language_code: str,
    settings: Settings | None = None,
) -> tuple[str, int, bool]:
    """Return ``(url, duration_sec, from_cache)``, reusing audio when possible."""
    settings = settings or get_settings()
    directory = media_dir(settings)
    destination = directory / f"{task_id}.wav"
    cached = audio_cache_path(text, language_code, settings)

    if destination.exists():
        audio = destination.read_bytes()
        return f"/media/{destination.name}", _wav_duration(audio), True

    if cached.exists():
        shutil.copyfile(cached, destination)
        audio = destination.read_bytes()
        return f"/media/{destination.name}", _wav_duration(audio), True

    result = get_tts_provider(settings).synthesize(text, language_code)
    destination.write_bytes(result.audio_bytes)
    cached.write_bytes(result.audio_bytes)
    return f"/media/{destination.name}", result.duration_sec, False
