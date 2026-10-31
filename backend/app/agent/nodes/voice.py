"""Voice synthesis node: script -> audio file served under /media."""

import logging

from app.agent.state import AgentState
from app.services.tts import TTSError, get_tts_provider, write_audio

logger = logging.getLogger(__name__)


def synthesize_voice_node(state: AgentState) -> dict:
    script = (state.get("simplified_script") or "").strip()
    if not script:
        return {"audio_output_url": ""}

    language_code = state.get("target_language", "hi-IN")
    task_id = state.get("task_id", "document")

    try:
        result = get_tts_provider().synthesize(script, language_code)
    except TTSError:
        logger.exception("Voice synthesis failed for task %s", task_id)
        return {"audio_output_url": ""}

    url = write_audio(task_id, result)
    payload = dict(state.get("voice_payload") or {})
    payload["audio_base64"] = None
    payload["duration_estimate_sec"] = result.duration_sec

    logger.info(
        "Synthesized %.1fs of %s audio for task %s", result.duration_sec, language_code, task_id
    )
    return {"audio_output_url": url, "voice_payload": payload}
