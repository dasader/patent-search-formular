import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.core.pipeline import run_pipeline
from app.models.schemas import KiprisQuota, SearchRequest
from app.services.patent_searcher import get_searcher
from app.services.searchers.kipris import KiprisSearcher

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


@router.post("/search/stream")
async def search_stream(request: SearchRequest):
    event_queue: asyncio.Queue = asyncio.Queue()

    def on_event(event: dict):
        event_queue.put_nowait(event)

    async def generate():
        task = asyncio.create_task(
            run_pipeline(description=request.description, on_event=on_event)
        )

        while not task.done():
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                yield {"data": json.dumps(event, ensure_ascii=False)}
            except asyncio.TimeoutError:
                continue

        # Drain remaining events
        while not event_queue.empty():
            event = event_queue.get_nowait()
            yield {"data": json.dumps(event, ensure_ascii=False)}

        # Final result
        try:
            result = task.result()
            yield {"data": json.dumps({"type": "result", "data": result.model_dump()}, ensure_ascii=False)}
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            yield {"data": json.dumps({"type": "error", "message": str(e), "step": "pipeline", "recoverable": False}, ensure_ascii=False)}

    return EventSourceResponse(generate())


@router.get("/search/kipris-quota", response_model=KiprisQuota)
async def kipris_quota():
    searcher = get_searcher("KR")
    if not isinstance(searcher, KiprisSearcher):
        raise HTTPException(status_code=503, detail="KIPRIS searcher not available")
    quota = await searcher.get_quota()
    return KiprisQuota(**quota)
