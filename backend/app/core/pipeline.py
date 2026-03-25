import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from app.core.config import settings
from app.models.schemas import NormalizedPatent, SearchQuery, SearchResponse
from app.services import query_generator, result_evaluator
from app.services.patent_searcher import get_searcher
from app.services.searchers.kipris import KiprisSearcher

logger = logging.getLogger(__name__)


async def run_pipeline(
    description: str,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> SearchResponse:
    start = time.time()

    def emit(event: dict):
        if on_event:
            on_event(event)

    # Step 1: 초기 검색식 생성
    emit({"type": "step", "step": "query_generation"})
    initial_query = await query_generator.generate_query(description)

    # Step 2: KR 검색 실행 (US는 API 변경 이슈로 일시 중지)
    kr_task = _country_loop(
        description=description,
        initial_query=initial_query,
        country="KR",
        max_iterations=settings.kipris_max_iterations,
        emit=emit,
    )

    try:
        kr_result = await asyncio.wait_for(kr_task, timeout=settings.pipeline_timeout)
    except asyncio.TimeoutError:
        emit({"type": "error", "message": f"Pipeline timeout ({settings.pipeline_timeout}s)", "step": "pipeline", "recoverable": False})
        raise TimeoutError(f"Pipeline exceeded {settings.pipeline_timeout}s timeout")

    if isinstance(kr_result, Exception):
        logger.error(f"KR search failed: {kr_result}")
        emit({"type": "error", "message": str(kr_result), "step": "patent_search", "country": "KR", "recoverable": True})
        kr_query, kr_patents, kr_iters, kr_total = initial_query, [], 0, 0
    else:
        kr_query, kr_patents, kr_iters, kr_total = kr_result

    # US 검색 비활성화 (PatentsView API 사이트 변경 이슈)
    us_query, us_patents, us_iters = initial_query, [], 0

    # KIPRIS 잔여 횟수 조회
    kipris_remaining = 0
    kipris = get_searcher("KR")
    if isinstance(kipris, KiprisSearcher):
        quota = await kipris.get_quota()
        kipris_remaining = quota["remaining"]

    elapsed_ms = int((time.time() - start) * 1000)

    return SearchResponse(
        query_kr=kr_query,
        query_us=us_query,
        patents_kr=kr_patents,
        patents_us=us_patents,
        iterations_kr=kr_iters,
        iterations_us=us_iters,
        total_kr=kr_total,
        kipris_remaining=kipris_remaining,
        processing_time_ms=elapsed_ms,
    )


async def _country_loop(
    description: str,
    initial_query: SearchQuery,
    country: str,
    max_iterations: int,
    emit: Callable[[dict], None],
) -> tuple[SearchQuery, list[NormalizedPatent], int, int]:
    """검색 → 스코어링 → 정량평가 → 개선 루프. Returns (query, patents, iterations, total_count)."""
    searcher = get_searcher(country)
    if searcher is None or not await searcher.is_available():
        emit({"type": "error", "message": f"{country} searcher unavailable", "step": "patent_search", "country": country, "recoverable": True})
        return initial_query, [], 0, 0

    query = initial_query
    patents: list[NormalizedPatent] = []
    total_count = 0
    prev_query_json = ""

    for iteration in range(1, max_iterations + 1):
        # 1. 검색
        emit({"type": "step", "step": "patent_search", "country": country, "iteration": iteration})
        try:
            patents, total_count = await _search_with_retry(searcher, query)
        except Exception as e:
            emit({"type": "error", "message": str(e), "step": "patent_search", "country": country, "recoverable": True})
            break

        if not patents:
            break

        # 2. 관련성 스코어링 (LLM 배치)
        emit({"type": "step", "step": "relevance_scoring", "country": country, "iteration": iteration})
        try:
            patents = await result_evaluator.score_relevance(description, patents)
        except Exception as e:
            logger.error(f"Relevance scoring failed: {e}")
            emit({"type": "error", "message": f"관련성 평가 실패: {e}", "step": "relevance_scoring", "country": country, "recoverable": True})
            break

        # 3. 정량 평가
        emit({"type": "step", "step": "evaluation", "country": country, "iteration": iteration})
        evaluation = result_evaluator.evaluate_scores(patents)

        emit({"type": "step", "step": "evaluation_result", "country": country, "iteration": iteration,
              "good_ratio": round(evaluation.good_ratio, 2), "noise_ratio": round(evaluation.noise_ratio, 2),
              "satisfied": evaluation.satisfied})

        if evaluation.satisfied:
            emit({"type": "step", "step": "loop_done", "country": country, "iterations": iteration})
            return query, patents, iteration, total_count

        # 강제 종료: 검색식 동일
        current_query_json = query.model_dump_json()
        if current_query_json == prev_query_json:
            emit({"type": "step", "step": "loop_done", "country": country, "iterations": iteration})
            return query, patents, iteration, total_count
        prev_query_json = current_query_json

        # 마지막 반복이면 개선 없이 종료
        if iteration == max_iterations:
            emit({"type": "step", "step": "loop_done", "country": country, "iterations": iteration})
            return query, patents, iteration, total_count

        # 4. 검색식 개선 (점수 분포 피드백 포함)
        reason = "recall_low" if evaluation.good_ratio < settings.relevance_min_good_ratio else "precision_low"
        emit({"type": "step", "step": "query_refinement", "country": country, "iteration": iteration + 1, "reason": reason})

        # 저점 특허 제목으로 노이즈 패턴 전달
        noise_titles = "\n".join(f"- {p.title}" for p in patents if p.relevance_score and p.relevance_score <= 2)[:500]
        good_titles = "\n".join(f"- {p.title}" for p in patents if p.relevance_score and p.relevance_score >= 4)[:500]

        feedback = (
            f"{evaluation.feedback}\n\n"
            f"관련성 높은 특허 예시:\n{good_titles}\n\n"
            f"관련성 낮은 특허 예시 (노이즈):\n{noise_titles}"
        )

        results_summary = "\n".join(f"- [{p.relevance_score}점] {p.title}" for p in patents[:30])
        query = await query_generator.refine_query(
            description=description,
            current_query=query,
            results_summary=results_summary,
            feedback=feedback,
        )

    emit({"type": "step", "step": "loop_done", "country": country, "iterations": max_iterations})
    return query, patents, max_iterations, total_count


async def _search_with_retry(searcher, query: SearchQuery, max_retries: int = 2) -> tuple[list[NormalizedPatent], int]:
    for attempt in range(max_retries + 1):
        try:
            return await searcher.search(query)
        except Exception:
            if attempt == max_retries:
                raise
            await asyncio.sleep(2 ** attempt)
    return [], 0
