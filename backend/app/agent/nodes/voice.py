"""Voice synthesis node: script -> audio file served under /media."""

import logging

from app.agent.state import AgentState
from app.services.tts import TTSError, synthesize_and_store

logger = logging.getLogger(__name__)


def synthesize_voice_node(state: AgentState) -> dict:
    script = (state.get("simplified_script") or "").strip()
    if not script:
        return {"audio_output_url": ""}

    language_code = state.get("target_language", "hi-IN")
    task_id = state.get("task_id", "document")

    try:
        url, duration, from_cache = synthesize_and_store(task_id, script, language_code)
    except (TTSError, OSError):
        logger.exception("Voice synthesis failed for task %s", task_id)
        return {"audio_output_url": ""}

    payload = dict(state.get("voice_payload") or {})
    payload["audio_base64"] = None
    payload["duration_estimate_sec"] = duration

    logger.info(
        "Voice ready for task %s (%.0fs, %s)",
        task_id,
        duration,
        "cached" if from_cache else "synthesized",
    )
    return {"audio_output_url": url, "voice_payload": payload}
