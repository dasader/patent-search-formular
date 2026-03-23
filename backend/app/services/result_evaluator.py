import asyncio
import json
import logging

from google import genai

from app.core.config import settings
from app.models.schemas import NormalizedPatent, SearchQuery

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.gemini_api_key)

EVALUATE_PROMPT = """\
You are a patent search quality evaluator.

Original technology description:
{description}

Core technology elements that should be covered:
{core_elements}

Current search query:
{query}

Search results ({country} patents):
{results}

Evaluate the search results on two axes:

1. PRECISION: What fraction of results are relevant to the technology description?
   - Are there many irrelevant/noisy results?
   - Is the search too broad?

2. RECALL: Are all core technology elements covered by at least one result?
   - Which elements are missing?
   - Is the search too narrow?

Return a JSON object:
{{
  "satisfied": true/false,
  "precision_ok": true/false,
  "recall_ok": true/false,
  "feedback": "specific feedback for query improvement",
  "missing_elements": ["element1", ...],
  "noise_description": "description of irrelevant results if any"
}}

Return ONLY valid JSON, no markdown.
"""


class EvaluationResult:
    def __init__(self, satisfied: bool, feedback: str, precision_ok: bool, recall_ok: bool):
        self.satisfied = satisfied
        self.feedback = feedback
        self.precision_ok = precision_ok
        self.recall_ok = recall_ok


async def evaluate_results(
    description: str,
    query: SearchQuery,
    results: list[NormalizedPatent],
    country: str,
) -> EvaluationResult:
    results_text = "\n".join(
        f"- [{r.application_number}] {r.title}"
        + (f"\n  Abstract: {r.abstract[:200]}..." if r.abstract else "")
        for r in results[:20]
    )

    if not results_text:
        results_text = "(no results found)"

    prompt = EVALUATE_PROMPT.format(
        description=description,
        core_elements="\n".join(f"- {e}" for e in query.core_elements),
        query=query.model_dump_json(indent=2),
        results=results_text,
        country=country,
    )

    response = await asyncio.to_thread(
        _client.models.generate_content,
        model=settings.gemini_model,
        contents=prompt,
    )

    return _parse_evaluation(response.text)


def _parse_evaluation(text: str) -> EvaluationResult:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse evaluation response, forcing re-evaluation: {cleaned[:200]}")
        return EvaluationResult(satisfied=False, feedback="Evaluation parse failed — retry with refined query", precision_ok=False, recall_ok=False)

    return EvaluationResult(
        satisfied=data.get("satisfied", True),
        feedback=data.get("feedback", ""),
        precision_ok=data.get("precision_ok", True),
        recall_ok=data.get("recall_ok", True),
    )
