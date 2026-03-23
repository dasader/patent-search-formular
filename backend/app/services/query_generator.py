import asyncio
import json
import logging

from google import genai

from app.core.config import settings
from app.models.schemas import SearchQuery

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.gemini_api_key)

GENERATE_PROMPT = """\
You are a patent search expert. Given a technology description, generate patent search queries.

Technology description:
{description}

Return a JSON object with these fields:
- keywords_kr: list of Korean keywords for KIPRIS search (3-8 keywords)
- keywords_en: list of English keywords for PatentsView search (3-8 keywords)
- cpc_codes: list of relevant CPC classification codes (1-5 codes, e.g. "H04L", "G06F")
- ipc_codes: list of relevant IPC classification codes (1-5 codes)
- exclude_keywords: list of keywords to exclude from results (0-3)
- core_elements: list of core technology elements (3-5) that must be covered in search results

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

Generate an improved search query. Return a JSON object with these fields:
- keywords_kr: list of Korean keywords (3-8)
- keywords_en: list of English keywords (3-8)
- cpc_codes: list of CPC codes (1-5)
- ipc_codes: list of IPC codes (1-5)
- exclude_keywords: list of exclusion keywords (0-5)
- core_elements: list of core technology elements (3-5)

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

    return SearchQuery(**data)
