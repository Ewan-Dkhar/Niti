"""Plain-language localization node."""

from app.agent.state import AgentState
from app.schemas import PolicyExtraction, VoicePayload
from app.services.vernacular import get_simplification_provider


def simplify_vernacular_node(state: AgentState) -> dict:
    extracted_data = state.get("extracted_data") or {}
    if not extracted_data:
        return {"simplified_script": "", "voice_payload": {}}

    policy = PolicyExtraction.model_validate(extracted_data)
    language_code = state.get("target_language", "hi-IN")
    script = get_simplification_provider().simplify(policy, language_code)
    duration = max(10, round(len(script.split()) / 2.5))

    payload = VoicePayload(
        language_code=language_code,
        plain_text_script=script,
        duration_estimate_sec=duration,
    )

    return {
        "simplified_script": script,
        "voice_payload": payload.model_dump(),
    }
