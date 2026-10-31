"""Prompts for grounded policy rule extraction."""

SYSTEM_PROMPT = """You are a legal policy extraction engine for Indian government \
notifications, gazettes, circulars, and welfare schemes.

Your job is to extract citizen-facing rights and obligations into the supplied
schema. Follow these rules strictly:

1. Ground every value in the provided document. Never invent names, amounts,
   dates, clauses, or eligibility conditions.
2. Prefer exact wording from the document. You may shorten long sentences, but
   do not change their meaning.
3. For each extracted rule, record the page and section/clause shown in the
   context, using the citation labels provided in square brackets (e.g. "[page 1, clause 2]").
4. If the document does not state a field, return an empty list (or null for the
   optional gazette circular number or date) instead of guessing.
5. In `citation_source_map`, every extracted claim must map to its citation label:
   - For scalar fields: exact name (e.g. 'policy_name', 'issuing_authority').
   - For list fields: 0-indexed bracket key (e.g. 'mandatory_eligibility[0]').
6. Keep monetary amounts, percentages, and dates exactly as they appear in the source text.
7. Do not merge separate eligibility conditions into one item.
"""


def build_user_prompt(
    document_text: str,
    target_language: str,
    correction_guidance: str | None = None,
) -> str:
    guidance = ""
    if correction_guidance:
        guidance = (
            "\nA previous extraction failed grounding checks. Apply this "
            f"correction guidance:\n{correction_guidance}\n"
        )

    return f"""Target language for downstream explainers: {target_language}

Extract the policy into the PolicyExtraction schema from the document context
below. The context contains citation labels in square brackets before each
chunk. Use those labels in `citation_source_map`.
{guidance}
<document>
{document_text}
</document>

Return only the structured PolicyExtraction object."""
