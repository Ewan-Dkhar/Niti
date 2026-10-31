"""Tests for WAV synthesis, Sarvam calls, and the voice node."""

import base64
import io
import wave
from pathlib import Path

import httpx
import pytest

from app.agent.nodes.voice import synthesize_voice_node
from app.core.config import Settings
from app.services.tts import (
    MockTTSProvider,
    SarvamTTSProvider,
    TTSError,
    estimate_duration,
    get_tts_provider,
    write_audio,
)


def test_mock_provider_returns_playable_wav() -> None:
    result = MockTTSProvider().synthesize("यह एक छोटा परीक्षण वाक्य है।", "hi-IN")

    assert result.audio_bytes.startswith(b"RIFF")
    with wave.open(io.BytesIO(result.audio_bytes), "rb") as handle:
        assert handle.getnframes() > 0
        assert handle.getframerate() == 22050
    assert result.duration_sec == estimate_duration("यह एक छोटा परीक्षण वाक्य है।")
    assert result.extension == "wav"


def test_mock_provider_rejects_empty_text() -> None:
    with pytest.raises(TTSError):
        MockTTSProvider().synthesize("   ", "hi-IN")


def test_factory_defaults_to_mock_without_key() -> None:
    assert isinstance(get_tts_provider(Settings(use_mock_tts=True)), MockTTSProvider)
    assert isinstance(
        get_tts_provider(Settings(use_mock_tts=False, sarvam_api_key=None)),
        MockTTSProvider,
    )


def test_factory_uses_sarvam_with_key() -> None:
    provider = get_tts_provider(Settings(use_mock_tts=False, sarvam_api_key="key"))

    assert isinstance(provider, SarvamTTSProvider)


def test_write_audio_persists_under_media_dir(tmp_path: Path) -> None:
    result = MockTTSProvider().synthesize("short script", "en-IN")
    settings = Settings(data_dir=str(tmp_path))

    url = write_audio("task-123", result, settings)

    assert url == "/media/task-123.wav"
    assert (tmp_path / "media" / "task-123.wav").read_bytes() == result.audio_bytes


def test_voice_node_writes_audio_and_updates_payload() -> None:
    result = synthesize_voice_node(
        {
            "task_id": "node-task",
            "target_language": "ta-IN",
            "simplified_script": "இது ஒரு சோதனை ஸ்கிரிப்ட்.",
            "voice_payload": {
                "language_code": "ta-IN",
                "plain_text_script": "இது ஒரு சோதனை ஸ்கிரிப்ட்.",
                "duration_estimate_sec": 10,
            },
        }
    )

    assert result["audio_output_url"].startswith("/media/node-task")
    assert result["voice_payload"]["duration_estimate_sec"] >= 3


def test_voice_node_noops_without_script() -> None:
    assert synthesize_voice_node({"task_id": "x", "simplified_script": ""}) == {
        "audio_output_url": ""
    }


def test_sarvam_provider_posts_text_and_decodes_audio() -> None:
    wav = MockTTSProvider().synthesize("नमस्ते", "hi-IN").audio_bytes
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["payload"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"audios": [base64.b64encode(wav).decode()]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = SarvamTTSProvider("test-key", client=client, speaker="anushka")

    result = provider.synthesize("नमस्ते", "hi-IN")

    assert result.audio_bytes == wav
    assert result.duration_sec >= 1
    assert captured["url"] == "https://api.sarvam.ai/text-to-speech"
    assert captured["headers"]["api-subscription-key"] == "test-key"
    assert captured["payload"]["model"] == "bulbul:v3"
    assert captured["payload"]["target_language_code"] == "hi-IN"


def test_sarvam_provider_raises_without_audio() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"audios": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = SarvamTTSProvider("key", client=client)

    with pytest.raises(TTSError):
        provider.synthesize("hello", "en-IN")
