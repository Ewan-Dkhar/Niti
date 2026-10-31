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
   context, using the citation labels provided (e.g. "Section 4, clause 2 (page 3)").
4. If the document does not state a field, return an empty list (or null for the
   optional gazette number/date) instead of guessing.
5. Keep monetary amounts, percentages, and dates exactly as they appear.
6. Do not merge separate eligibility conditions into one item.
"""


def build_user_prompt(document_text: str, target_language: str) -> str:
    return f"""Target language for downstream explainers: {target_language}

Extract the policy into the PolicyExtraction schema from the document context
below. The context contains citation labels in square brackets before each
chunk. Use those labels in `citation_source_map`.

<document>
{document_text}
</document>

Return only the structured PolicyExtraction object."""
