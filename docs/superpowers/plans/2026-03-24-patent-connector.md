# Patent Connector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기술 설명을 입력하면 LLM이 특허 검색식을 자동 생성/개선하여 한국+미국 특허를 검색하는 시스템 구축

**Architecture:** FastAPI 백엔드가 Gemini LLM으로 검색식을 생성하고, KIPRIS(한국)/PatentsView(미국) API로 특허를 검색한다. 한국/미국 피드백 루프를 병렬로 실행하여 검색식을 자동 개선한다. React 프론트엔드가 SSE 스트리밍으로 진행 상황을 실시간 표시한다.

**Tech Stack:** FastAPI, Google Gemini API, React 19, Vite 8, TypeScript, Axios, Docker Compose

**Spec:** `docs/superpowers/specs/2026-03-24-patent-connector-design.md`

**Reference project (패밀리룩):** `C:\Users\ilhwa\Downloads\_cursors\11_hscode-connector\`

---

## File Structure

### Backend

| File | Responsibility |
|------|---------------|
| `backend/app/main.py` | FastAPI 앱 생성, CORS, 라우터 등록, 헬스체크 |
| `backend/app/core/config.py` | Pydantic BaseSettings 환경변수 설정 |
| `backend/app/core/pipeline.py` | 검색식 생성→검색→평가 파이프라인 오케스트레이터 |
| `backend/app/models/schemas.py` | Pydantic 요청/응답 스키마 |
| `backend/app/api/routes.py` | SSE 스트리밍 검색 API, KIPRIS quota API |
| `backend/app/services/query_generator.py` | Gemini로 검색식 생성/개선 |
| `backend/app/services/result_evaluator.py` | Gemini로 검색 결과 평가 (Precision+Recall) |
| `backend/app/services/patent_searcher.py` | 어댑터 디스패처 (활성화된 searcher 관리) |
| `backend/app/services/searchers/base.py` | PatentSearcher 추상 인터페이스 |
| `backend/app/services/searchers/kipris.py` | KIPRIS API 어댑터 (XML 파싱, 월간 카운터) |
| `backend/app/services/searchers/patentsview.py` | PatentsView API 어댑터 (JSON) |
| `backend/app/services/rate_limiter.py` | Token bucket 레이트 리미터 (hs-connector에서 복사) |
| `backend/requirements.txt` | Python 의존성 |
| `backend/Dockerfile` | 백엔드 Docker 이미지 |
| `backend/.env.example` | 환경변수 템플릿 |

### Frontend

| File | Responsibility |
|------|---------------|
| `frontend/src/main.tsx` | React 진입점 |
| `frontend/src/App.tsx` | 레이아웃 (accent stripe, nav, footer) |
| `frontend/src/App.css` | 레이아웃 스타일 (hs-connector에서 복사 후 수정) |
| `frontend/src/index.css` | 전역 CSS 변수 (hs-connector에서 복사) |
| `frontend/src/pages/SearchPage.tsx` | 검색 페이지 (입력, 진행률, 결과) |
| `frontend/src/pages/SearchPage.css` | 검색 페이지 스타일 |
| `frontend/src/components/PatentList.tsx` | 특허 결과 카드 목록 |
| `frontend/src/components/PatentList.css` | 특허 카드 스타일 |
| `frontend/src/api/client.ts` | Axios API 클라이언트 + SSE |
| `frontend/src/api/types.ts` | TypeScript 인터페이스 |
| `frontend/package.json` | Node 의존성 |
| `frontend/vite.config.ts` | Vite 설정 (프록시 포함) |
| `frontend/tsconfig.json` | TypeScript 설정 |
| `frontend/tsconfig.app.json` | 앱 TypeScript 설정 |
| `frontend/tsconfig.node.json` | 노드 TypeScript 설정 |
| `frontend/Dockerfile` | 멀티스테이지 빌드 |
| `frontend/nginx.conf` | Nginx SPA + API 프록시 |

### Root

| File | Responsibility |
|------|---------------|
| `docker-compose.yml` | 백엔드 + 프론트엔드 서비스 정의 |
| `CLAUDE.md` | 프로젝트 가이드 |
| `data/` | 영속 데이터 디렉토리 (KIPRIS 카운터) |

---

## Task 1: 프로젝트 스캐폴딩 + 설정

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/searchers/__init__.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/requirements.txt`
- Create: `backend/Dockerfile`
- Create: `backend/.env.example`
- Create: `backend/app/core/config.py`
- Create: `backend/app/models/schemas.py`

- [ ] **Step 1: 백엔드 디렉토리 구조 생성**

```bash
cd C:\Users\ilhwa\Downloads\_cursors\13_patent-connector
mkdir -p backend/app/api backend/app/core backend/app/services/searchers backend/app/models data
touch backend/app/__init__.py backend/app/api/__init__.py backend/app/core/__init__.py
touch backend/app/services/__init__.py backend/app/services/searchers/__init__.py backend/app/models/__init__.py
```

- [ ] **Step 2: requirements.txt 작성**

```
# backend/requirements.txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
google-genai
pydantic>=2.9.0
pydantic-settings>=2.7.0
httpx==0.28.1
sse-starlette==2.2.1
pytest==8.3.4
pytest-asyncio==0.25.0
```

- [ ] **Step 3: .env.example 작성**

```env
# backend/.env.example

# Gemini API (필수)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash

# KIPRIS API (필수)
KIPRIS_API_KEY=your-kipris-api-key
KIPRIS_MONTHLY_LIMIT=1000
KIPRIS_MAX_ITERATIONS=2

# PatentsView API (선택 — 키 없이도 동작)
PATENTSVIEW_API_KEY=
PATENTSVIEW_MAX_ITERATIONS=3

# Server
BACKEND_PORT=8013
FRONTEND_PORT=8094
```

- [ ] **Step 4: config.py 작성**

hs-connector의 `config.py` 패턴을 따름 (Pydantic BaseSettings + .env).

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"

    # KIPRIS
    kipris_api_key: str
    kipris_monthly_limit: int = 1000
    kipris_max_iterations: int = 2

    # PatentsView
    patentsview_api_key: str = ""
    patentsview_max_iterations: int = 3

    # Pipeline
    pipeline_timeout: int = 180
    max_input_length: int = 5000

    # Paths
    data_dir: str = "./data"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

- [ ] **Step 5: schemas.py 작성**

```python
# backend/app/models/schemas.py
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    description: str = Field(..., min_length=10, max_length=5000)


class SearchQuery(BaseModel):
    keywords_kr: list[str] = []
    keywords_en: list[str] = []
    cpc_codes: list[str] = []
    ipc_codes: list[str] = []
    exclude_keywords: list[str] = []
    core_elements: list[str] = []


class NormalizedPatent(BaseModel):
    country: str
    title: str
    application_number: str
    application_date: str | None = None
    abstract: str | None = None
    applicant: str | None = None
    ipc_codes: list[str] = []
    url: str | None = None


class SearchResponse(BaseModel):
    query_kr: SearchQuery
    query_us: SearchQuery
    patents_kr: list[NormalizedPatent] = []
    patents_us: list[NormalizedPatent] = []
    iterations_kr: int = 0
    iterations_us: int = 0
    kipris_remaining: int = 0
    processing_time_ms: int = 0


class KiprisQuota(BaseModel):
    used: int
    limit: int
    remaining: int
    resets_at: str


class ErrorResponse(BaseModel):
    detail: str
```

- [ ] **Step 6: Dockerfile 작성**

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: git init + 커밋**

```bash
cd C:\Users\ilhwa\Downloads\_cursors\13_patent-connector
mkdir -p data && touch data/.gitkeep
git init
git add backend/ data/.gitkeep
git commit -m "feat: backend scaffolding — config, schemas, Dockerfile"
```

---

## Task 2: 레이트 리미터 + 검색 어댑터 인터페이스

**Files:**
- Create: `backend/app/services/rate_limiter.py` (hs-connector에서 복사)
- Create: `backend/app/services/searchers/base.py`

- [ ] **Step 1: rate_limiter.py 복사**

hs-connector의 `backend/app/services/rate_limiter.py`를 그대로 복사.

```bash
cp C:\Users\ilhwa\Downloads\_cursors\11_hscode-connector\backend\app\services\rate_limiter.py \
   C:\Users\ilhwa\Downloads\_cursors\13_patent-connector\backend\app\services\rate_limiter.py
```

- [ ] **Step 2: 검색 어댑터 추상 인터페이스 작성**

```python
# backend/app/services/searchers/base.py
from abc import ABC, abstractmethod

from app.models.schemas import NormalizedPatent, SearchQuery


class PatentSearcher(ABC):
    """특허 검색 어댑터 추상 인터페이스"""

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[NormalizedPatent]:
        ...

    @abstractmethod
    def get_country_code(self) -> str:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...
```

- [ ] **Step 3: 커밋**

```bash
git add backend/app/services/rate_limiter.py backend/app/services/searchers/base.py
git commit -m "feat: rate limiter + patent searcher interface"
```

---

## Task 3: KIPRIS 어댑터 (한국 특허)

**Files:**
- Create: `backend/app/services/searchers/kipris.py`

- [ ] **Step 1: KIPRIS 어댑터 구현**

KIPRIS Plus API는 XML 응답. 월간 카운터를 `data/kipris_quota.json`에 파일 기반 관리.

```python
# backend/app/services/searchers/kipris.py
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

import httpx

from app.core.config import settings
from app.models.schemas import NormalizedPatent, SearchQuery
from app.services.searchers.base import PatentSearcher

logger = logging.getLogger(__name__)

KIPRIS_BASE_URL = "http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getWordSearch"
QUOTA_FILE = Path(settings.data_dir) / "kipris_quota.json"


class KiprisSearcher(PatentSearcher):
    def __init__(self):
        self._lock = asyncio.Lock()

    def get_country_code(self) -> str:
        return "KR"

    async def is_available(self) -> bool:
        quota = await self._read_quota()
        return quota["used"] < settings.kipris_monthly_limit

    async def search(self, query: SearchQuery) -> list[NormalizedPatent]:
        if not await self.is_available():
            logger.warning("KIPRIS monthly quota exceeded")
            return []

        keywords = " ".join(query.keywords_kr)
        if not keywords.strip():
            return []

        params = {
            "word": keywords,
            "patent": "true",
            "utility": "true",
            "numOfRows": 30,
            "pageNo": 1,
            "ServiceKey": settings.kipris_api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(KIPRIS_BASE_URL, params=params)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"KIPRIS API error: {e}")
            raise

        await self._increment_quota()
        return self._parse_xml(resp.text)

    def _parse_xml(self, xml_text: str) -> list[NormalizedPatent]:
        results: list[NormalizedPatent] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            logger.error("Failed to parse KIPRIS XML response")
            return results

        for item in root.iter("item"):
            title = self._get_text(item, "inventionTitle", "")
            if not title:
                continue
            results.append(NormalizedPatent(
                country="KR",
                title=title,
                application_number=self._get_text(item, "applicationNumber", ""),
                application_date=self._format_date(self._get_text(item, "applicationDate")),
                abstract=self._get_text(item, "astrtCont"),
                applicant=self._get_text(item, "applicantName"),
                ipc_codes=self._parse_ipc(self._get_text(item, "ipcNumber")),
                url=self._build_url(self._get_text(item, "applicationNumber")),
            ))
        return results

    def _get_text(self, el: ElementTree.Element, tag: str, default: str | None = None) -> str | None:
        child = el.find(tag)
        return child.text.strip() if child is not None and child.text else default

    def _format_date(self, date_str: str | None) -> str | None:
        if not date_str or len(date_str) < 8:
            return date_str
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    def _parse_ipc(self, ipc_str: str | None) -> list[str]:
        if not ipc_str:
            return []
        return [c.strip() for c in ipc_str.split(",") if c.strip()]

    def _build_url(self, app_num: str | None) -> str | None:
        if not app_num:
            return None
        return f"https://kpat.kipris.or.kr/kpat/biblioa.do?method=biblioFrame&applno={app_num}"

    async def _read_quota(self) -> dict:
        async with self._lock:
            current_month = datetime.now().strftime("%Y-%m")
            try:
                data = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
                if data.get("month") != current_month:
                    data = {"month": current_month, "used": 0}
                    QUOTA_FILE.write_text(json.dumps(data), encoding="utf-8")
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                data = {"month": current_month, "used": 0}
                QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
                QUOTA_FILE.write_text(json.dumps(data), encoding="utf-8")
            return data

    async def _increment_quota(self):
        async with self._lock:
            data = await self._read_quota_unlocked()
            data["used"] = data.get("used", 0) + 1
            QUOTA_FILE.write_text(json.dumps(data), encoding="utf-8")

    async def _read_quota_unlocked(self) -> dict:
        current_month = datetime.now().strftime("%Y-%m")
        try:
            data = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
            if data.get("month") != current_month:
                data = {"month": current_month, "used": 0}
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            data = {"month": current_month, "used": 0}
        return data

    async def get_quota(self) -> dict:
        data = await self._read_quota()
        remaining = max(0, settings.kipris_monthly_limit - data["used"])
        now = datetime.now()
        if now.month == 12:
            resets_at = f"{now.year + 1}-01-01"
        else:
            resets_at = f"{now.year}-{now.month + 1:02d}-01"
        return {
            "used": data["used"],
            "limit": settings.kipris_monthly_limit,
            "remaining": remaining,
            "resets_at": resets_at,
        }
```

주의: `_read_quota`는 lock 내부에서 호출되므로, `_increment_quota`에서는 별도의 `_read_quota_unlocked` 사용 (이중 lock 방지).

- [ ] **Step 2: 커밋**

```bash
git add backend/app/services/searchers/kipris.py
git commit -m "feat: KIPRIS searcher adapter with monthly quota tracking"
```

---

## Task 4: PatentsView 어댑터 (미국 특허)

**Files:**
- Create: `backend/app/services/searchers/patentsview.py`

- [ ] **Step 1: PatentsView 어댑터 구현**

```python
# backend/app/services/searchers/patentsview.py
import logging

import httpx

from app.models.schemas import NormalizedPatent, SearchQuery
from app.services.searchers.base import PatentSearcher

logger = logging.getLogger(__name__)

PATENTSVIEW_BASE_URL = "https://search.patentsview.org/api/v1/patent"


class PatentsViewSearcher(PatentSearcher):
    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    def get_country_code(self) -> str:
        return "US"

    async def is_available(self) -> bool:
        return True

    async def search(self, query: SearchQuery) -> list[NormalizedPatent]:
        keywords = " ".join(query.keywords_en)
        if not keywords.strip():
            return []

        q_filter = self._build_query(query)
        params = {
            "q": q_filter,
            "f": '["patent_id","patent_title","patent_date","patent_abstract","assignees_at_grant.assignee_organization","cpcs.cpc_group_id"]',
            "per_page": 30,
        }

        headers = {}
        if self._api_key:
            headers["X-Api-Key"] = self._api_key

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(PATENTSVIEW_BASE_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"PatentsView API error: {e}")
            raise

        return self._parse_response(data)

    def _build_query(self, query: SearchQuery) -> str:
        import json as _json
        conditions = []

        # 키워드 텍스트 검색
        keywords = query.keywords_en
        if keywords:
            text_query = " ".join(keywords)
            conditions.append({"_text_any": {"patent_abstract": text_query}})

        # CPC 코드 필터
        for cpc in query.cpc_codes:
            conditions.append({"_begins": {"cpcs.cpc_group_id": cpc}})

        if not conditions:
            return "{}"

        if len(conditions) == 1:
            return _json.dumps(conditions[0])

        return _json.dumps({"_and": conditions})

    def _parse_response(self, data: dict) -> list[NormalizedPatent]:
        results: list[NormalizedPatent] = []
        patents = data.get("patents", [])

        for p in patents:
            title = p.get("patent_title", "")
            if not title:
                continue

            # 출원인 추출
            assignees = p.get("assignees_at_grant", [])
            applicant = assignees[0].get("assignee_organization", "") if assignees else None

            # CPC 코드 추출
            cpcs = p.get("cpcs", [])
            cpc_codes = list({c.get("cpc_group_id", "") for c in cpcs if c.get("cpc_group_id")})

            results.append(NormalizedPatent(
                country="US",
                title=title,
                application_number=p.get("patent_id", ""),
                application_date=p.get("patent_date"),
                abstract=p.get("patent_abstract"),
                applicant=applicant,
                ipc_codes=cpc_codes,
                url=f"https://patents.google.com/patent/US{p.get('patent_id', '')}",
            ))

        return results
```

- [ ] **Step 2: 커밋**

```bash
git add backend/app/services/searchers/patentsview.py
git commit -m "feat: PatentsView searcher adapter"
```

---

## Task 5: 검색 디스패처

**Files:**
- Create: `backend/app/services/patent_searcher.py`

- [ ] **Step 1: 어댑터 디스패처 구현**

활성화된 어댑터를 관리하고 국가 코드로 조회하는 디스패처.

```python
# backend/app/services/patent_searcher.py
from app.core.config import settings
from app.services.searchers.base import PatentSearcher
from app.services.searchers.kipris import KiprisSearcher
from app.services.searchers.patentsview import PatentsViewSearcher

_REGISTRY: dict[str, PatentSearcher] = {}


def init_searchers():
    global _REGISTRY
    _REGISTRY = {
        "KR": KiprisSearcher(),
        "US": PatentsViewSearcher(api_key=settings.patentsview_api_key),
    }


def get_searcher(country_code: str) -> PatentSearcher | None:
    return _REGISTRY.get(country_code)


def get_all_searchers() -> dict[str, PatentSearcher]:
    return dict(_REGISTRY)
```

- [ ] **Step 2: 커밋**

```bash
git add backend/app/services/patent_searcher.py
git commit -m "feat: patent searcher dispatcher"
```

---

## Task 6: 검색식 생성기 (Gemini)

**Files:**
- Create: `backend/app/services/query_generator.py`

- [ ] **Step 1: QueryGenerator 구현**

Gemini에 기술 설명을 보내 검색식(키워드, CPC/IPC, 핵심 요소)을 생성.

```python
# backend/app/services/query_generator.py
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
```

- [ ] **Step 2: 커밋**

```bash
git add backend/app/services/query_generator.py
git commit -m "feat: Gemini-based query generator with refinement"
```

---

## Task 7: 결과 평가기 (Gemini)

**Files:**
- Create: `backend/app/services/result_evaluator.py`

- [ ] **Step 1: ResultEvaluator 구현**

Gemini가 검색 결과의 Precision(노이즈 비율)과 Recall(핵심 요소 커버리지)을 평가.

```python
# backend/app/services/result_evaluator.py
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
        logger.error(f"Failed to parse evaluation: {cleaned[:200]}")
        return EvaluationResult(satisfied=True, feedback="", precision_ok=True, recall_ok=True)

    return EvaluationResult(
        satisfied=data.get("satisfied", True),
        feedback=data.get("feedback", ""),
        precision_ok=data.get("precision_ok", True),
        recall_ok=data.get("recall_ok", True),
    )
```

- [ ] **Step 2: 커밋**

```bash
git add backend/app/services/result_evaluator.py
git commit -m "feat: Gemini-based result evaluator (precision + recall)"
```

---

## Task 8: 파이프라인 오케스트레이터

**Files:**
- Create: `backend/app/core/pipeline.py`

- [ ] **Step 1: Pipeline 구현**

한국/미국 피드백 루프를 `asyncio.gather`로 병렬 실행하는 파이프라인.

```python
# backend/app/core/pipeline.py
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
```

- [ ] **Step 2: 커밋**

```bash
git add backend/app/core/pipeline.py
git commit -m "feat: pipeline orchestrator with parallel country loops"
```

---

## Task 9: FastAPI 앱 + API 라우트

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/api/routes.py`

- [ ] **Step 1: API 라우트 구현**

SSE 스트리밍 검색 + KIPRIS quota 엔드포인트.

```python
# backend/app/api/routes.py
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
```

- [ ] **Step 2: main.py 구현**

```python
# backend/app/main.py
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.services.patent_searcher import init_searchers

logging.basicConfig(level=logging.INFO)
for name in ["httpx", "httpcore", "chromadb"]:
    logging.getLogger(name).setLevel(logging.WARNING)


def create_app() -> FastAPI:
    app = FastAPI(title="Patent Connector API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.on_event("startup")
    async def startup():
        init_searchers()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 3: 커밋**

```bash
git add backend/app/main.py backend/app/api/routes.py
git commit -m "feat: FastAPI app with SSE streaming search endpoint"
```

---

## Task 10: 프론트엔드 스캐폴딩

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css` (hs-connector에서 복사)
- Create: `frontend/src/App.css` (hs-connector에서 복사 후 수정)
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/vite-env.d.ts`

- [ ] **Step 1: Vite 프로젝트 초기화**

```bash
cd C:\Users\ilhwa\Downloads\_cursors\13_patent-connector
mkdir -p frontend/src/pages frontend/src/components frontend/src/api frontend/src/assets
```

- [ ] **Step 2: package.json 작성**

```json
{
  "name": "patent-connector-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview"
  },
  "dependencies": {
    "axios": "^1.13.6",
    "react": "^19.2.4",
    "react-dom": "^19.2.4"
  },
  "devDependencies": {
    "@types/react": "^19.1.8",
    "@types/react-dom": "^19.1.6",
    "@vitejs/plugin-react": "^6.0.0",
    "typescript": "~5.9.3",
    "vite": "^8.0.0"
  }
}
```

참고: 단일 페이지이므로 react-router-dom 불필요.

- [ ] **Step 3: vite.config.ts 작성**

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 4: TypeScript 설정 파일 작성**

```json
// frontend/tsconfig.json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

```json
// frontend/tsconfig.app.json
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsBuildInfo",
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true,
    "resolveJsonModule": true
  },
  "include": ["src"]
}
```

```json
// frontend/tsconfig.node.json
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsBuildInfo",
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 5: index.html 작성**

```html
<!-- frontend/index.html -->
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Patent Connector</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: vite-env.d.ts 작성**

```typescript
// frontend/src/vite-env.d.ts
/// <reference types="vite/client" />
```

- [ ] **Step 7: index.css 복사 + App.css 복사 수정**

```bash
cp C:\Users\ilhwa\Downloads\_cursors\11_hscode-connector\frontend\src\index.css \
   C:\Users\ilhwa\Downloads\_cursors\13_patent-connector\frontend\src\index.css
cp C:\Users\ilhwa\Downloads\_cursors\11_hscode-connector\frontend\src\App.css \
   C:\Users\ilhwa\Downloads\_cursors\13_patent-connector\frontend\src\App.css
```

App.css는 그대로 사용 (브랜드명은 App.tsx에서 변경).

- [ ] **Step 8: main.tsx 작성**

```typescript
// frontend/src/main.tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 9: App.tsx 작성**

hs-connector 패턴을 따르되, 단일 페이지이므로 react-router 없이 구현.

```typescript
// frontend/src/App.tsx
import SearchPage from './pages/SearchPage'
import { version } from '../package.json'
import './App.css'

function App() {
  return (
    <>
      <div className="accent-stripe" />
      <nav className="nav">
        <div className="nav-inner">
          <a href="/" className="nav-brand">
            <span className="nav-brand-icon">⚡</span>
            Patent Connector
          </a>
        </div>
      </nav>
      <main className="main">
        <SearchPage />
      </main>
      <footer className="footer">
        <div className="footer-inner">
          <span className="footer-brand">blinktask.work</span>
          <span className="footer-version">v{version}</span>
        </div>
      </footer>
    </>
  )
}

export default App
```

- [ ] **Step 10: npm install 실행**

```bash
cd C:\Users\ilhwa\Downloads\_cursors\13_patent-connector\frontend
npm install
```

- [ ] **Step 11: 커밋**

```bash
cd C:\Users\ilhwa\Downloads\_cursors\13_patent-connector
git add frontend/
git commit -m "feat: frontend scaffolding — Vite + React + TypeScript + family look CSS"
```

---

## Task 11: 프론트엔드 API 계층

**Files:**
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`

- [ ] **Step 1: TypeScript 타입 정의**

```typescript
// frontend/src/api/types.ts

export interface SearchQuery {
  keywords_kr: string[]
  keywords_en: string[]
  cpc_codes: string[]
  ipc_codes: string[]
  exclude_keywords: string[]
  core_elements: string[]
}

export interface NormalizedPatent {
  country: string
  title: string
  application_number: string
  application_date: string | null
  abstract: string | null
  applicant: string | null
  ipc_codes: string[]
  url: string | null
}

export interface SearchResponse {
  query_kr: SearchQuery
  query_us: SearchQuery
  patents_kr: NormalizedPatent[]
  patents_us: NormalizedPatent[]
  iterations_kr: number
  iterations_us: number
  kipris_remaining: number
  processing_time_ms: number
}

export interface KiprisQuota {
  used: number
  limit: number
  remaining: number
  resets_at: string
}

export interface SSEEvent {
  type: 'step' | 'error' | 'result'
  step?: string
  country?: string
  iteration?: number
  reason?: string
  message?: string
  recoverable?: boolean
  data?: SearchResponse
  iterations?: number
}
```

- [ ] **Step 2: API 클라이언트 구현**

hs-connector의 `classifyStream` 패턴을 따라 Fetch 기반 SSE 처리.

```typescript
// frontend/src/api/client.ts
import axios from 'axios'
import type { KiprisQuota, SearchResponse, SSEEvent } from './types'

const api = axios.create({ baseURL: '/api/v1' })

export async function searchStream(
  description: string,
  onEvent: (event: SSEEvent) => void,
): Promise<SearchResponse> {
  const response = await fetch('/api/v1/search/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description }),
  })

  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult: SearchResponse | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data: ')) continue

      const jsonStr = trimmed.slice(6)
      if (!jsonStr) continue

      try {
        const event: SSEEvent = JSON.parse(jsonStr)
        onEvent(event)
        if (event.type === 'result' && event.data) {
          finalResult = event.data
        }
      } catch {
        // skip malformed events
      }
    }
  }

  if (!finalResult) throw new Error('No result received')
  return finalResult
}

export async function getKiprisQuota(): Promise<KiprisQuota> {
  const { data } = await api.get<KiprisQuota>('/search/kipris-quota')
  return data
}
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/api/
git commit -m "feat: frontend API client with SSE streaming"
```

---

## Task 12: SearchPage 컴포넌트

**Files:**
- Create: `frontend/src/pages/SearchPage.tsx`
- Create: `frontend/src/pages/SearchPage.css`

- [ ] **Step 1: SearchPage.css 작성**

hs-connector의 ClassifyPage.css 패턴을 따르되 patent-connector에 맞게 수정.

```css
/* frontend/src/pages/SearchPage.css */

/* Hero */
.search-hero {
  padding: 48px 0 32px;
  text-align: center;
}

.search-hero h1 {
  font-family: var(--font-display);
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-ink);
  margin: 0 0 8px;
}

.search-hero p {
  font-family: var(--font-body);
  font-size: 1rem;
  color: var(--color-muted);
  margin: 0;
}

/* Quota badge */
.quota-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  background: var(--color-accent-light);
  color: var(--color-accent);
  border: 1px solid var(--color-accent-border);
  margin-top: 16px;
}

.quota-badge.warning {
  background: var(--color-warning-light);
  color: var(--color-warning);
  border-color: rgba(146, 64, 14, 0.18);
}

/* Input area */
.search-input-area {
  max-width: 720px;
  margin: 0 auto 32px;
}

.search-textarea {
  width: 100%;
  min-height: 120px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  font-family: var(--font-body);
  font-size: 0.95rem;
  color: var(--color-ink);
  background: var(--color-surface);
  resize: vertical;
  transition: border-color var(--transition);
  box-sizing: border-box;
}

.search-textarea:focus {
  outline: none;
  border-color: var(--color-accent);
}

.search-textarea::placeholder {
  color: var(--color-faint);
}

.search-button {
  display: block;
  width: 100%;
  margin-top: 12px;
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  background: var(--color-accent);
  color: #fff;
  font-family: var(--font-body);
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity var(--transition);
}

.search-button:hover:not(:disabled) {
  opacity: 0.9;
}

.search-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Progress area */
.search-progress {
  max-width: 720px;
  margin: 0 auto 32px;
  padding: 20px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
}

.progress-title {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 12px;
}

.progress-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-family: var(--font-body);
  font-size: 0.875rem;
  color: var(--color-muted);
}

.progress-step.active {
  color: var(--color-accent);
  font-weight: 600;
}

.progress-step .spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.progress-reason {
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--color-accent-light);
  font-family: var(--font-body);
  font-size: 0.8rem;
  color: var(--color-accent);
}

/* Query display */
.query-display {
  max-width: 720px;
  margin: 0 auto 24px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
}

.query-display h3 {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 8px;
}

.keyword-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.keyword-tag {
  padding: 3px 10px;
  border-radius: 12px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  background: var(--color-accent-light);
  color: var(--color-accent);
  border: 1px solid var(--color-accent-border);
}

.keyword-tag.cpc {
  background: var(--color-warning-light);
  color: var(--color-warning);
  border-color: rgba(146, 64, 14, 0.18);
}

/* Country tabs */
.country-tabs {
  display: flex;
  gap: 2px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}

.country-tab {
  padding: 8px 20px;
  border: none;
  background: none;
  font-family: var(--font-body);
  font-size: 0.9rem;
  color: var(--color-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color var(--transition), border-color var(--transition);
}

.country-tab.active {
  color: var(--color-accent);
  border-bottom-color: var(--color-accent);
  font-weight: 600;
}

/* Empty state */
.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--color-muted);
  font-family: var(--font-body);
}

/* Error */
.search-error {
  max-width: 720px;
  margin: 0 auto 16px;
  padding: 12px 16px;
  border-radius: 8px;
  background: var(--color-negative-light);
  color: var(--color-negative);
  font-family: var(--font-body);
  font-size: 0.875rem;
}

/* Meta */
.search-meta {
  max-width: 720px;
  margin: 0 auto 16px;
  display: flex;
  gap: 16px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--color-muted);
}
```

- [ ] **Step 2: SearchPage.tsx 작성**

```typescript
// frontend/src/pages/SearchPage.tsx
import { useState, useEffect } from 'react'
import { searchStream, getKiprisQuota } from '../api/client'
import type { SearchResponse, KiprisQuota, SSEEvent } from '../api/types'
import PatentList from '../components/PatentList'
import './SearchPage.css'

function SearchPage() {
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [quota, setQuota] = useState<KiprisQuota | null>(null)
  const [activeTab, setActiveTab] = useState<'KR' | 'US'>('KR')
  const [steps, setSteps] = useState<SSEEvent[]>([])
  const [currentStep, setCurrentStep] = useState<SSEEvent | null>(null)

  useEffect(() => {
    getKiprisQuota().then(setQuota).catch(() => {})
  }, [])

  const handleSearch = async () => {
    if (!description.trim() || loading) return
    setLoading(true)
    setError(null)
    setResponse(null)
    setSteps([])
    setCurrentStep(null)

    try {
      const result = await searchStream(description, (event) => {
        if (event.type === 'step') {
          setCurrentStep(event)
          setSteps(prev => [...prev, event])
        } else if (event.type === 'error' && !event.recoverable) {
          setError(event.message || 'Unknown error')
        }
      })
      setResponse(result)
      setQuota(prev => prev ? { ...prev, remaining: result.kipris_remaining, used: prev.limit - result.kipris_remaining } : prev)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed')
    } finally {
      setLoading(false)
      setCurrentStep(null)
    }
  }

  const getStepLabel = (event: SSEEvent): string => {
    const country = event.country ? ` [${event.country}]` : ''
    const iter = event.iteration ? ` (${event.iteration}회차)` : ''
    switch (event.step) {
      case 'query_generation': return '검색식 생성 중...'
      case 'patent_search': return `${country} 특허 검색 중...${iter}`
      case 'evaluation': return `${country} 결과 평가 중...${iter}`
      case 'query_refinement': return `${country} 검색식 개선 중...${iter}`
      case 'loop_done': return `${country} 검색 완료 (${event.iterations}회 반복)`
      default: return event.step || ''
    }
  }

  const activeQuery = activeTab === 'KR' ? response?.query_kr : response?.query_us
  const activePatents = activeTab === 'KR' ? response?.patents_kr : response?.patents_us
  const krCount = response?.patents_kr.length || 0
  const usCount = response?.patents_us.length || 0

  return (
    <div>
      <div className="search-hero">
        <h1>Patent Connector</h1>
        <p>기술 설명으로 관련 특허를 찾아보세요</p>
        {quota && (
          <div className={`quota-badge ${quota.remaining < 100 ? 'warning' : ''}`}>
            KIPRIS {quota.remaining}/{quota.limit}건 남음
          </div>
        )}
      </div>

      <div className="search-input-area">
        <textarea
          className="search-textarea"
          placeholder="기술 설명을 입력하세요 (최소 10자)..."
          value={description}
          onChange={e => setDescription(e.target.value)}
          disabled={loading}
        />
        <button
          className="search-button"
          onClick={handleSearch}
          disabled={loading || description.trim().length < 10}
        >
          {loading ? '검색 중...' : '특허 검색'}
        </button>
      </div>

      {error && <div className="search-error">{error}</div>}

      {loading && currentStep && (
        <div className="search-progress">
          <div className="progress-title">검색 진행 중</div>
          {steps.map((s, i) => (
            <div key={i} className={`progress-step ${s === currentStep ? 'active' : ''}`}>
              {s === currentStep && <span className="spinner" />}
              {getStepLabel(s)}
            </div>
          ))}
          {currentStep.reason && (
            <div className="progress-reason">
              {currentStep.reason === 'precision_low'
                ? '검색 범위가 너무 넓어 키워드를 구체화합니다'
                : '누락된 기술 요소가 있어 키워드를 확장합니다'}
            </div>
          )}
        </div>
      )}

      {response && (
        <>
          {response.processing_time_ms > 0 && (
            <div className="search-meta">
              <span>처리 시간: {(response.processing_time_ms / 1000).toFixed(1)}초</span>
              <span>KR {response.iterations_kr}회 반복</span>
              <span>US {response.iterations_us}회 반복</span>
            </div>
          )}

          {activeQuery && (
            <div className="query-display">
              <h3>최종 검색식</h3>
              <div className="keyword-tags">
                {(activeTab === 'KR' ? activeQuery.keywords_kr : activeQuery.keywords_en).map((kw, i) => (
                  <span key={i} className="keyword-tag">{kw}</span>
                ))}
                {(activeTab === 'KR' ? activeQuery.ipc_codes : activeQuery.cpc_codes).map((code, i) => (
                  <span key={`cpc-${i}`} className="keyword-tag cpc">{code}</span>
                ))}
              </div>
            </div>
          )}

          <div className="country-tabs">
            <button
              className={`country-tab ${activeTab === 'KR' ? 'active' : ''}`}
              onClick={() => setActiveTab('KR')}
            >
              한국 특허 ({krCount}건)
            </button>
            <button
              className={`country-tab ${activeTab === 'US' ? 'active' : ''}`}
              onClick={() => setActiveTab('US')}
            >
              미국 특허 ({usCount}건)
            </button>
          </div>

          {activePatents && activePatents.length > 0 ? (
            <PatentList patents={activePatents} />
          ) : (
            <div className="empty-state">
              {krCount === 0 && usCount === 0
                ? '검색 결과가 없습니다. 기술 설명을 더 구체적으로 입력해 보세요.'
                : `${activeTab === 'KR' ? '한국' : '미국'} 특허 검색 결과가 없습니다.`}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default SearchPage
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/pages/
git commit -m "feat: SearchPage with SSE progress and country tabs"
```

---

## Task 13: PatentList 컴포넌트

**Files:**
- Create: `frontend/src/components/PatentList.tsx`
- Create: `frontend/src/components/PatentList.css`

- [ ] **Step 1: PatentList.css 작성**

hs-connector의 ResultTable.css 패턴을 따름.

```css
/* frontend/src/components/PatentList.css */

.patent-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 720px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.patent-card {
  padding: 16px 20px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  transition: border-color var(--transition);
  animation: fadeUp 0.2s ease-out both;
}

.patent-card:hover {
  border-color: var(--color-accent-border);
}

.patent-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

.patent-title {
  font-family: var(--font-body);
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
  line-height: 1.4;
}

.patent-number {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--color-accent);
  white-space: nowrap;
  flex-shrink: 0;
}

.patent-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
  font-family: var(--font-body);
  font-size: 0.8rem;
  color: var(--color-muted);
}

.patent-abstract {
  font-family: var(--font-body);
  font-size: 0.85rem;
  color: var(--color-ink-light);
  line-height: 1.6;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.patent-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.patent-ipc-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.patent-ipc-tag {
  padding: 2px 8px;
  border-radius: 10px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  background: var(--color-border-light);
  color: var(--color-muted);
}

.patent-link {
  font-family: var(--font-body);
  font-size: 0.8rem;
  color: var(--color-accent);
  text-decoration: none;
}

.patent-link:hover {
  text-decoration: underline;
}
```

- [ ] **Step 2: PatentList.tsx 작성**

```typescript
// frontend/src/components/PatentList.tsx
import type { NormalizedPatent } from '../api/types'
import './PatentList.css'

interface Props {
  patents: NormalizedPatent[]
}

function PatentList({ patents }: Props) {
  return (
    <div className="patent-list">
      {patents.map((patent, index) => (
        <div
          key={`${patent.country}-${patent.application_number}`}
          className="patent-card"
          style={{ animationDelay: `${index * 0.06}s` }}
        >
          <div className="patent-card-header">
            <h4 className="patent-title">{patent.title}</h4>
            <span className="patent-number">{patent.application_number}</span>
          </div>

          <div className="patent-meta">
            {patent.application_date && <span>출원일: {patent.application_date}</span>}
            {patent.applicant && <span>출원인: {patent.applicant}</span>}
          </div>

          {patent.abstract && (
            <p className="patent-abstract">{patent.abstract}</p>
          )}

          <div className="patent-footer">
            <div className="patent-ipc-tags">
              {patent.ipc_codes.slice(0, 5).map((code, i) => (
                <span key={i} className="patent-ipc-tag">{code}</span>
              ))}
            </div>
            {patent.url && (
              <a
                className="patent-link"
                href={patent.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                원문 보기 →
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export default PatentList
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/components/
git commit -m "feat: PatentList component with card layout"
```

---

## Task 14: 프론트엔드 배포 설정

**Files:**
- Create: `frontend/nginx.conf`
- Create: `frontend/Dockerfile`

- [ ] **Step 1: nginx.conf 작성**

hs-connector 패턴을 따르되, SSE 프록시 설정 포함.

```nginx
# frontend/nginx.conf
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # 검색 API (SSE 스트리밍)
    location /api/v1/search/ {
        proxy_pass http://backend:8000/api/v1/search/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # 일반 API
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SPA 라우팅
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 2: Dockerfile 작성**

```dockerfile
# frontend/Dockerfile
FROM node:20-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/nginx.conf frontend/Dockerfile
git commit -m "feat: frontend Nginx + Dockerfile for production"
```

---

## Task 15: Docker Compose + CLAUDE.md + PORT_REGISTRY 업데이트

**Files:**
- Create: `docker-compose.yml`
- Create: `CLAUDE.md`
- Modify: `C:\Users\ilhwa\Downloads\_cursors\PORT_REGISTRY.md`

- [ ] **Step 1: docker-compose.yml 작성**

```yaml
# docker-compose.yml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "${BACKEND_PORT:-8013}:8000"
    env_file:
      - ./backend/.env
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "${FRONTEND_PORT:-8094}:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
```

- [ ] **Step 2: CLAUDE.md 작성**

```markdown
# 13_patent-connector

기술 설명 → 특허 검색식 자동 생성 + 한국/미국 특허 검색 시스템

## 스택
- Backend: FastAPI + Google Gemini + KIPRIS API + PatentsView API
- Frontend: React + Vite + TypeScript

## 포트
- Backend: 8013 (호스트) → 8000 (컨테이너)
- Frontend: 8094 (Nginx prod) / 5182 (Vite dev)

## 실행
- Backend: `cd backend && uvicorn app.main:app --reload --port 8000`
- Frontend: `cd frontend && npm run dev`

## 환경변수
- `backend/.env.example` 참고
- KIPRIS API 키: https://plus.kipris.or.kr/ 에서 발급
- Gemini API 키: Google AI Studio에서 발급
```

- [ ] **Step 3: PORT_REGISTRY.md 업데이트**

`PORT_REGISTRY.md`의 "12_trade-statistics" 섹션 뒤에 13_patent-connector 항목 추가.

현재 사용 중인 포트 현황 섹션에 추가:
```markdown
### 13_patent-connector (기술 설명 → 특허 검색)

| 서비스 | 호스트 포트 | 컨테이너 포트 | 기술 |
|--------|------------|--------------|------|
| backend | **8013**  | 8000         | FastAPI |
| frontend | **8094** | 80           | Nginx (정적 빌드) |
| frontend-dev | **5182** | 5173     | Vite dev 서버 (로컬 개발 전용) |
```

전체 사용 포트 요약 섹션에 추가:
```
8013        13_patent-connector backend
8094        13_patent-connector frontend (Nginx)
5182        13_patent-connector frontend-dev (Vite dev)
```

- [ ] **Step 4: data/.gitkeep 생성**

```bash
touch C:\Users\ilhwa\Downloads\_cursors\13_patent-connector\data\.gitkeep
```

- [ ] **Step 5: .gitignore 작성**

```
# Root .gitignore
backend/.env
data/kipris_quota.json
frontend/node_modules/
frontend/dist/
__pycache__/
*.pyc
```

- [ ] **Step 6: 커밋**

```bash
git add docker-compose.yml CLAUDE.md .gitignore data/.gitkeep
git commit -m "feat: Docker Compose, CLAUDE.md, project config"
```

PORT_REGISTRY 업데이트는 별도 커밋:
```bash
cd C:\Users\ilhwa\Downloads\_cursors
git add PORT_REGISTRY.md
git commit -m "docs: add 13_patent-connector to PORT_REGISTRY"
```

---

## Task 16: 통합 테스트 + 로컬 실행 확인

- [ ] **Step 1: backend .env 파일 생성**

```bash
cp backend/.env.example backend/.env
# 실제 API 키 입력
```

- [ ] **Step 2: 백엔드 단독 실행 확인**

```bash
cd C:\Users\ilhwa\Downloads\_cursors\13_patent-connector\backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Expected: 서버 시작, `http://localhost:8000/health` 에서 `{"status":"ok"}` 응답.

- [ ] **Step 3: 프론트엔드 단독 실행 확인**

```bash
cd C:\Users\ilhwa\Downloads\_cursors\13_patent-connector\frontend
npm run dev
```

Expected: `http://localhost:5173` 에서 SearchPage UI 표시, 패밀리룩 CSS 적용 확인.

- [ ] **Step 4: 통합 테스트 — 실제 검색 수행**

브라우저에서 기술 설명 입력 후 검색 버튼 클릭:
- SSE 진행률이 실시간 표시되는지 확인
- 한국/미국 탭 전환이 정상 동작하는지 확인
- 특허 카드가 올바르게 렌더링되는지 확인

- [ ] **Step 5: Docker Compose 빌드 및 실행**

```bash
cd C:\Users\ilhwa\Downloads\_cursors\13_patent-connector
docker compose up --build
```

Expected: `http://localhost:8094` 에서 전체 시스템 동작 확인.

- [ ] **Step 6: 최종 커밋**

모든 수정 사항 반영 후 최종 커밋.

```bash
git add -A
git commit -m "feat: patent-connector v0.1.0 — complete initial implementation"
```
