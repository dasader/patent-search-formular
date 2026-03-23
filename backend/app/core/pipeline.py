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

    # Step 2: 국가별 독립 피드백 루프 (병렬, 타임아웃 적용)
    kr_task = _country_loop(
        description=description,
        initial_query=initial_query,
        country="KR",
        max_iterations=settings.kipris_max_iterations,
        emit=emit,
    )
    us_task = _country_loop(
        description=description,
        initial_query=initial_query,
        country="US",
        max_iterations=settings.patentsview_max_iterations,
        emit=emit,
    )

    try:
        (kr_query, kr_patents, kr_iters), (us_query, us_patents, us_iters) = await asyncio.wait_for(
            asyncio.gather(kr_task, us_task, return_exceptions=False),
            timeout=settings.pipeline_timeout,
        )
    except asyncio.TimeoutError:
        emit({"type": "error", "message": f"Pipeline timeout ({settings.pipeline_timeout}s)", "step": "pipeline", "recoverable": False})
        raise TimeoutError(f"Pipeline exceeded {settings.pipeline_timeout}s timeout")

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
        kipris_remaining=kipris_remaining,
        processing_time_ms=elapsed_ms,
    )


async def _country_loop(
    description: str,
    initial_query: SearchQuery,
    country: str,
    max_iterations: int,
    emit: Callable[[dict], None],
) -> tuple[SearchQuery, list[NormalizedPatent], int]:
    searcher = get_searcher(country)
    if searcher is None or not await searcher.is_available():
        emit({"type": "error", "message": f"{country} searcher unavailable", "step": "patent_search", "country": country, "recoverable": True})
        return initial_query, [], 0

    query = initial_query
    patents: list[NormalizedPatent] = []
    prev_query_json = ""

    for iteration in range(1, max_iterations + 1):
        # 검색
        emit({"type": "step", "step": "patent_search", "country": country, "iteration": iteration})
        try:
            patents = await _search_with_retry(searcher, query)
        except Exception as e:
            emit({"type": "error", "message": str(e), "step": "patent_search", "country": country, "recoverable": True})
            break

        # 평가
        emit({"type": "step", "step": "evaluation", "country": country, "iteration": iteration})
        evaluation = await result_evaluator.evaluate_results(description, query, patents, country)

        if evaluation.satisfied:
            emit({"type": "step", "step": "loop_done", "country": country, "iterations": iteration})
            return query, patents, iteration

        # 강제 종료: 검색식 동일
        current_query_json = query.model_dump_json()
        if current_query_json == prev_query_json:
            emit({"type": "step", "step": "loop_done", "country": country, "iterations": iteration})
            return query, patents, iteration
        prev_query_json = current_query_json

        # 마지막 반복이면 개선 없이 종료
        if iteration == max_iterations:
            emit({"type": "step", "step": "loop_done", "country": country, "iterations": iteration})
            return query, patents, iteration

        # 검색식 개선
        reason = "recall_low" if not evaluation.recall_ok else "precision_low"
        emit({"type": "step", "step": "query_refinement", "country": country, "iteration": iteration + 1, "reason": reason})

        results_summary = "\n".join(f"- {p.title}" for p in patents[:15])
        query = await query_generator.refine_query(
            description=description,
            current_query=query,
            results_summary=results_summary,
            feedback=evaluation.feedback,
        )

    emit({"type": "step", "step": "loop_done", "country": country, "iterations": max_iterations})
    return query, patents, max_iterations


async def _search_with_retry(searcher, query: SearchQuery, max_retries: int = 2) -> list[NormalizedPatent]:
    for attempt in range(max_retries + 1):
        try:
            return await searcher.search(query)
        except Exception:
            if attempt == max_retries:
                raise
            await asyncio.sleep(2 ** attempt)
