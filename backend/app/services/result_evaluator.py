import asyncio
import json
import logging

from google import genai

from app.core.config import settings
from app.models.schemas import NormalizedPatent, SearchQuery

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.gemini_api_key)

class EvaluationResult:
    def __init__(self, satisfied: bool, feedback: str, good_ratio: float, noise_ratio: float):
        self.satisfied = satisfied
        self.feedback = feedback
        self.good_ratio = good_ratio
        self.noise_ratio = noise_ratio


def evaluate_scores(patents: list[NormalizedPatent]) -> EvaluationResult:
    """관련성 점수 기반 정량 평가. LLM 호출 없음."""
    if not patents:
        return EvaluationResult(satisfied=False, feedback="검색 결과 없음", good_ratio=0, noise_ratio=1.0)

    scored = [p for p in patents if p.relevance_score and p.relevance_score > 0]
    if not scored:
        return EvaluationResult(satisfied=False, feedback="스코어링 실패", good_ratio=0, noise_ratio=1.0)

    scored_total = len(scored)
    skipped = len(patents) - scored_total

    good_count = sum(1 for p in scored if p.relevance_score >= 3)
    noise_count = sum(1 for p in scored if p.relevance_score == 1)

    good_ratio = good_count / scored_total
    noise_ratio = noise_count / scored_total

    if skipped > 0:
        logger.warning(f"Relevance evaluation: {skipped}/{len(patents)} patents skipped (score=0)")

    min_good = settings.relevance_min_good_ratio
    max_noise = settings.relevance_max_noise_ratio

    precision_ok = noise_ratio <= max_noise
    recall_ok = good_ratio >= min_good
    satisfied = precision_ok and recall_ok

    parts = []
    if not recall_ok:
        parts.append(f"3점 이상 비율 {good_ratio:.0%} < 기준 {min_good:.0%} — 관련 키워드를 더 구체화하거나 유의어를 추가하세요")
    if not precision_ok:
        parts.append(f"1점 비율 {noise_ratio:.0%} > 기준 {max_noise:.0%} — 검색 범위가 넓어 키워드를 좁혀야 합니다")

    feedback = ". ".join(parts) if parts else "검색 품질 기준 충족"

    logger.info(
        f"Evaluation: good={good_ratio:.0%} noise={noise_ratio:.0%} "
        f"satisfied={satisfied} (thresholds: good>={min_good:.0%}, noise<={max_noise:.0%})"
    )

    return EvaluationResult(
        satisfied=satisfied,
        feedback=feedback,
        good_ratio=good_ratio,
        noise_ratio=noise_ratio,
    )


RELEVANCE_PROMPT = """\
You are a patent relevance scoring expert.

Target technology description:
{description}

Score EACH patent below on a 1-5 scale for relevance to the target technology:
  5: Directly related — core technology match
  4: Highly related — addresses same technical problem or method
  3: Moderately related — shares key technical components
  2: Weakly related — only peripheral overlap
  1: Not related — different technical domain

Patents to evaluate:
{patents}

Return a JSON array with EXACTLY {count} items, one per patent in the same order:
[
  {{"id": "application_number", "score": 1-5, "reason": "short reason in Korean"}},
  ...
]

Rules:
- Return ONLY valid JSON array, no markdown, no extra text
- "reason" must be under 30 characters in Korean
- Every patent must have an entry
"""


BATCH_SIZE = 100


async def score_relevance(
    description: str,
    patents: list[NormalizedPatent],
) -> list[NormalizedPatent]:
    """배치 병렬 호출로 전체 특허 관련성 스코어링 후 점수순 정렬."""
    if not patents:
        return patents

    # 100건씩 배치 분할
    batches = [patents[i:i + BATCH_SIZE] for i in range(0, len(patents), BATCH_SIZE)]
    logger.info(f"Scoring relevance for {len(patents)} patents in {len(batches)} batches")

    # 병렬 호출
    tasks = [_score_batch(description, batch) for batch in batches]
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

    # 결과 병합 — 출원번호 정규화 매칭 (하이픈/접두어 제거)
    score_map: dict[str, dict] = {}
    for result in batch_results:
        if isinstance(result, Exception):
            logger.error(f"Batch scoring failed: {result}")
            continue
        for s in result:
            raw_id = str(s.get("id", ""))
            normalized = raw_id.replace("-", "").replace(" ", "")
            # KR 접두어 제거
            if normalized.upper().startswith("KR"):
                normalized = normalized[2:]
            score_map[normalized] = s

    for p in patents:
        entry = score_map.get(p.application_number)
        if entry:
            p.relevance_score = entry.get("score")
            p.relevance_reason = entry.get("reason")
        else:
            p.relevance_score = 0
            p.relevance_reason = "평가 누락"

    # 누락 건 재시도 (1회)
    missed = [p for p in patents if p.relevance_score == 0]
    if missed and len(missed) <= len(patents) * 0.3:
        logger.info(f"Retrying {len(missed)} missed patents")
        try:
            retry_results = await _score_batch(description, missed)
            for s in retry_results:
                raw_id = str(s.get("id", ""))
                normalized = raw_id.replace("-", "").replace(" ", "")
                if normalized.upper().startswith("KR"):
                    normalized = normalized[2:]
                score_map[normalized] = s
            for p in missed:
                entry = score_map.get(p.application_number)
                if entry:
                    p.relevance_score = entry.get("score")
                    p.relevance_reason = entry.get("reason")
        except Exception as e:
            logger.error(f"Retry scoring failed: {e}")

    patents.sort(key=lambda p: p.relevance_score or 0, reverse=True)
    scored = sum(1 for p in patents if p.relevance_score and p.relevance_score > 0)
    logger.info(f"Relevance scoring done: {scored}/{len(patents)} scored")
    return patents


async def _score_batch(description: str, batch: list[NormalizedPatent]) -> list[dict]:
    patents_text = "\n".join(
        f"[{p.application_number}] {p.title}"
        + (f" | {p.abstract[:200]}" if p.abstract else "")
        for p in batch
    )

    prompt = RELEVANCE_PROMPT.format(
        description=description,
        patents=patents_text,
        count=len(batch),
    )

    response = await asyncio.to_thread(
        _client.models.generate_content,
        model=settings.gemini_model,
        contents=prompt,
    )

    return _parse_scores(response.text)


def _parse_scores(text: str) -> list[dict]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse relevance scores: {cleaned[:200]}")
    return []


