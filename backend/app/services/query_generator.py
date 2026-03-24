import asyncio
import json
import logging

from google import genai

from app.core.config import settings
from app.models.schemas import SearchQuery

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.gemini_api_key)

GENERATE_PROMPT = """\
You are a patent search expert. Given a technology description, generate structured patent search queries.

Technology description:
{description}

## Instructions

1. Identify 2-5 core technology CONCEPTS from the description.
2. For each concept, list 2-4 synonyms or alternative terms (including abbreviations).
3. Each concept becomes a "keyword group". Within a group, terms are OR-joined; across groups, they are AND-joined.
   Example: [["CRISPR", "Cas9", "Cas12"], ["gene editing", "genome editing"], ["off-target", "specificity"]]
   → (CRISPR OR Cas9 OR Cas12) AND (gene editing OR genome editing) AND (off-target OR specificity)

Return a JSON object:
- keyword_groups_kr: list of groups for Korean patent search (2-5 groups, each with 2-4 Korean synonyms)
- keyword_groups_en: list of groups for US patent search (2-5 groups, each with 2-4 English synonyms)
- cpc_codes: relevant CPC codes (1-5, e.g. "C12N 15/10")
- ipc_codes: relevant IPC codes (1-5)
- exclude_keywords: keywords to exclude (0-3)
- core_elements: core technology elements for result evaluation (3-5)

Example output:
{"keyword_groups_kr": [["유전자 편집", "게놈 편집"], ["CRISPR", "크리스퍼"]], "keyword_groups_en": [["gene editing", "genome editing"], ["CRISPR", "Cas9"]], "cpc_codes": ["C12N 15/10"], "ipc_codes": ["C12N 15/00"], "exclude_keywords": [], "core_elements": ["CRISPR system", "guide RNA"]}

Return ONLY valid JSON, no markdown.
"""

REFINE_PROMPT = """\
You are a patent search expert. The current search query needs improvement.

Original technology description:
{description}

Current search query:
{current_query}

Search results summary (titles):
{results_summary}

Evaluation feedback:
{feedback}

Improve the search query. You may:
- Add/remove synonym terms within existing concept groups
- Add/remove entire concept groups
- Adjust CPC/IPC codes
- Add exclusion keywords to reduce noise

Return a JSON object:
- keyword_groups_kr: list of groups (2-5 groups, each with 2-4 Korean synonyms)
- keyword_groups_en: list of groups (2-5 groups, each with 2-4 English synonyms)
- cpc_codes: CPC codes (1-5)
- ipc_codes: IPC codes (1-5)
- exclude_keywords: exclusion keywords (0-5)
- core_elements: core technology elements (3-5)

Return ONLY valid JSON, no markdown.
"""


async def generate_query(description: str) -> SearchQuery:
    prompt = GENERATE_PROMPT.format(description=description)
    response = await asyncio.to_thread(
        _client.models.generate_content,
        model=settings.gemini_model,
        contents=prompt,
    )
    return _parse_query_response(response.text)


async def refine_query(
    description: str,
    current_query: SearchQuery,
    results_summary: str,
    feedback: str,
) -> SearchQuery:
    prompt = REFINE_PROMPT.format(
        description=description,
        current_query=current_query.model_dump_json(indent=2),
        results_summary=results_summary,
        feedback=feedback,
    )
    response = await asyncio.to_thread(
        _client.models.generate_content,
        model=settings.gemini_model,
        contents=prompt,
    )
    return _parse_query_response(response.text)


def _parse_query_response(text: str) -> SearchQuery:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse Gemini response: {cleaned[:200]}")
        raise ValueError("Failed to parse search query from LLM response")

    # keyword_groups → flat keywords 자동 생성 (하위 호환)
    if "keyword_groups_kr" in data and not data.get("keywords_kr"):
        data["keywords_kr"] = [g[0] for g in data["keyword_groups_kr"] if g]
    if "keyword_groups_en" in data and not data.get("keywords_en"):
        data["keywords_en"] = [g[0] for g in data["keyword_groups_en"] if g]

    return SearchQuery(**data)
