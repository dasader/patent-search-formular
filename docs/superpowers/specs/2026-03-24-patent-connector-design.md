# Patent Connector 설계 스펙

## 개요

기술 설명을 입력하면 LLM(Gemini)이 특허 검색식을 자동 생성하고, 한국(KIPRIS) + 미국(PatentsView) 특허를 검색한 뒤, 검색 결과를 자동 평가/개선하여 최적의 특허 목록을 제시하는 시스템.

## 스택

| 계층 | 기술 | 비고 |
|------|------|------|
| Backend | FastAPI + Uvicorn | hs-connector 동일 |
| LLM | Google Gemini API | 검색식 생성, 결과 평가 |
| Frontend | React + Vite + TypeScript | hs-connector 동일 |
| 프로덕션 서빙 | Nginx | hs-connector 동일 |
| 컨테이너 | Docker Compose | hs-connector 동일 |

## 포트

| 서비스 | 호스트 포트 | 컨테이너 포트 | 기술 |
|--------|------------|--------------|------|
| backend | **8013** | 8000 | FastAPI |
| frontend | **8094** | 80 | Nginx (정적 빌드) |
| frontend-dev | **5182** | 5173 | Vite dev 서버 |

---

## 아키텍처

### 디렉토리 구조

```
13_patent-connector/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI 앱 엔트리포인트
│   │   ├── api/
│   │   │   └── routes.py               # 검색 API 라우터
│   │   ├── core/
│   │   │   ├── config.py               # Pydantic 설정 (환경변수)
│   │   │   └── pipeline.py             # 검색식 생성-검색-평가 파이프라인
│   │   ├── services/
│   │   │   ├── query_generator.py      # Gemini로 검색식 생성
│   │   │   ├── patent_searcher.py      # 어댑터 패턴 기반 검색 디스패처
│   │   │   ├── searchers/
│   │   │   │   ├── base.py             # PatentSearcher 추상 인터페이스
│   │   │   │   ├── kipris.py           # KIPRIS 어댑터 (한국)
│   │   │   │   └── patentsview.py      # PatentsView 어댑터 (미국)
│   │   │   ├── result_evaluator.py     # 결과 평가 + 개선 판단 (Gemini)
│   │   │   └── rate_limiter.py         # Token bucket 레이트 제어
│   │   └── models/
│   │       └── schemas.py              # Pydantic 스키마 정의
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx                     # 레이아웃 + 라우팅
│   │   ├── main.tsx                    # React 진입점
│   │   ├── pages/
│   │   │   ├── SearchPage.tsx          # 단일 검색 페이지
│   │   │   └── SearchPage.css
│   │   ├── components/
│   │   │   ├── PatentList.tsx          # 특허 결과 카드 목록
│   │   │   └── PatentList.css
│   │   ├── api/
│   │   │   ├── client.ts              # Axios API 클라이언트
│   │   │   └── types.ts               # TypeScript 인터페이스
│   │   ├── index.css                   # 전역 스타일 (hs-connector에서 복사)
│   │   └── App.css                     # 레이아웃 (hs-connector에서 복사)
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── Dockerfile
│   └── nginx.conf
├── data/                               # 영속 데이터 (KIPRIS 카운터 등)
├── docker-compose.yml
├── CLAUDE.md
└── docs/
```

---

## 백엔드 파이프라인

### 전체 흐름

```
입력: 기술 설명 (description)
  ↓
[Step 1] 초기 검색식 생성 (QueryGenerator - Gemini)
  - 기술 설명에서 핵심 기술 요소 3~5개 추출
  - 각 요소에 대한 키워드 생성:
    - 한국어 키워드 → KIPRIS 검색용
    - 영어 키워드 → PatentsView 검색용 (USPTO 데이터는 영어 전용)
  - CPC/IPC 코드 추천
  ↓
[Step 2] 국가별 독립 피드백 루프 (병렬 실행 — asyncio.gather)

  ┌─ 한국 특허 루프 (KIPRIS) ──────────────────┐
  │                                            │
  │  [2-KR-a] KIPRIS 검색 (한국어 키워드 + IPC)  │
  │    ↓                                       │
  │  [2-KR-b] 결과 평가 (Gemini)                │
  │    - Precision + Recall 평가                │
  │    - 종료 조건 충족 → 루프 종료              │
  │    - 개선 필요 → 한국어 키워드/IPC 수정       │
  │    - 최대 KIPRIS_MAX_ITERATIONS회 (기본 2)   │
  │                                            │
  └────────────────────────────────────────────┘

  ┌─ 미국 특허 루프 (PatentsView) ─────────────┐
  │                                            │
  │  [2-US-a] PatentsView 검색 (영어 키워드+CPC) │
  │    ↓                                       │
  │  [2-US-b] 결과 평가 (Gemini)                │
  │    - Precision + Recall 평가                │
  │    - 종료 조건 충족 → 루프 종료              │
  │    - 개선 필요 → 영어 키워드/CPC 수정         │
  │    - 최대 PATENTSVIEW_MAX_ITERATIONS회 (기본 3) │
  │                                            │
  └────────────────────────────────────────────┘

  ↓ (양쪽 루프 완료 후)

[Step 3] 최종 결과 통합 반환
  - 한국 + 미국 특허 목록
  - 각 국가별 최종 검색식
  - 각 국가별 반복 횟수
```

### 조기 종료 조건 (각 루프 공통)

LLM이 각 루프에서 독립적으로 판단:

- **종료**: Precision 충족 AND Recall 충족 (핵심 기술 요소가 모두 커버되고, 노이즈 비율 낮음)
- **강제 종료**: 이전 반복과 검색식 동일 또는 결과 미개선
- **강제 종료**: 최대 반복 횟수 도달 (KIPRIS_MAX_ITERATIONS / PATENTSVIEW_MAX_ITERATIONS)
- **개선 시**:
  - Recall 부족 → 키워드/분류코드 추가 (확장)
  - Precision 부족 → 키워드 구체화, 제외어 추가 (축소)

### SSE 스트리밍 이벤트

각 단계별 진행 상황을 SSE로 프론트엔드에 실시간 전달:

```json
{ "type": "step", "step": "query_generation" }
{ "type": "step", "step": "patent_search", "country": "KR", "iteration": 1 }
{ "type": "step", "step": "patent_search", "country": "US", "iteration": 1 }
{ "type": "step", "step": "evaluation", "country": "KR", "iteration": 1 }
{ "type": "step", "step": "evaluation", "country": "US", "iteration": 1 }
{ "type": "step", "step": "query_refinement", "country": "US", "iteration": 2, "reason": "precision_low" }
{ "type": "step", "step": "loop_done", "country": "KR", "iterations": 1 }
{ "type": "step", "step": "loop_done", "country": "US", "iterations": 2 }
{ "type": "error", "message": "KIPRIS API 호출 실패", "step": "patent_search", "country": "KR", "recoverable": true }
{ "type": "result", "data": { ... } }
```

- 각 이벤트에 `country` 필드 포함 (국가별 독립 루프이므로)
- `loop_done`: 해당 국가 루프 완료 시 전송
- `error`: `recoverable: true`면 해당 국가 스킵 후 계속, `false`면 파이프라인 중단

---

## KIPRIS API 호출 절약 전략

일 100건 제한(개발단계 기준)을 고려한 설계:

1. 한국 특허 루프는 **최대 KIPRIS_MAX_ITERATIONS회** 반복 (기본 2회, `.env`에서 설정).
2. 결과적으로 **1건 검색당 KIPRIS 최대 2회 호출** (기본값 기준, 하루 최대 50건 검색 가능).
3. 백엔드에서 **일간 KIPRIS 호출 카운터** 관리:
   - 파일: `data/kipris_quota.json` (Docker 볼륨 마운트로 영속)
   - 형식: `{ "date": "2026-03-24", "used": 42 }`
   - 리셋: 요청 시 현재 날짜와 파일의 date 비교, 다르면 자동 리셋
   - 파일 없거나 손상 시: `used: 0`으로 초기화
   - 동시성: asyncio Lock으로 보호
4. 잔여 횟수를 API 응답에 포함하여 프론트엔드에 표시.
5. **한도 초과 시 한국 특허 검색 스킵**, 미국 특허만 반환 (경고 메시지 포함).

---

## 특허 검색 어댑터 패턴

다국가 확장을 위한 어댑터 인터페이스:

```python
class PatentSearcher(ABC):
    """특허 검색 어댑터 추상 인터페이스"""

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[NormalizedPatent]:
        """검색 수행, 정규화된 결과 반환"""
        ...

    @abstractmethod
    def get_country_code(self) -> str:
        """국가 코드 반환 (KR, US, EP 등)"""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """API 사용 가능 여부 (한도 초과 등 확인)"""
        ...
```

### 현재 구현 어댑터

| 어댑터 | 국가 | API | 응답 형식 | Rate Limit |
|--------|------|-----|----------|------------|
| KiprisSearcher | KR | KIPRIS Plus | XML → 파싱 | 1,000건/월 |
| PatentsViewSearcher | US | PatentsView | JSON | 45req/min |

### 향후 확장

새 국가 추가 시 `searchers/` 디렉토리에 어댑터 파일만 추가하고 `config.py`에서 활성화:

```python
# config.py
ENABLED_SEARCHERS: list[str] = ["kipris", "patentsview"]  # 향후: "epo", "cnipa" 등
```

---

## 데이터 모델

### SearchQuery (검색식)

```python
class SearchQuery(BaseModel):
    keywords_kr: list[str]           # 한국어 키워드
    keywords_en: list[str]           # 영어 키워드
    cpc_codes: list[str]             # CPC 분류 코드
    ipc_codes: list[str]             # IPC 분류 코드
    exclude_keywords: list[str]      # 제외 키워드
    core_elements: list[str]         # 핵심 기술 요소 (평가 기준)
```

### NormalizedPatent (정규화된 특허)

```python
class NormalizedPatent(BaseModel):
    country: str                     # 국가 코드 (KR, US)
    title: str                       # 발명의 명칭
    application_number: str          # 출원번호
    application_date: str | None     # 출원일
    abstract: str | None             # 초록 요약
    applicant: str | None            # 출원인
    ipc_codes: list[str]             # IPC 코드
    url: str | None                  # 원문 링크
```

### SearchResponse (최종 응답)

```python
class SearchResponse(BaseModel):
    query_kr: SearchQuery              # 한국 최종 검색식
    query_us: SearchQuery              # 미국 최종 검색식
    patents_kr: list[NormalizedPatent]  # 한국 특허
    patents_us: list[NormalizedPatent]  # 미국 특허
    iterations_kr: int                 # 한국 루프 반복 횟수
    iterations_us: int                 # 미국 루프 반복 횟수
    kipris_remaining: int              # KIPRIS 잔여 호출 횟수
    processing_time_ms: int            # 처리 시간
```

---

## API 엔드포인트

```
POST /api/v1/search/stream
  - 요청: { "description": "기술 설명 텍스트" }
  - 응답: SSE 스트림 (단계별 진행 + 최종 SearchResponse)

GET /api/v1/search/kipris-quota
  - 응답: { "used": 42, "limit": 1000, "remaining": 958, "resets_at": "2026-04-01" }

GET /health
  - 응답: { "status": "ok" }
```

---

## 프론트엔드

### 단일 페이지 구성 (SearchPage)

```
Accent Stripe (3px, var(--color-accent))
Navigation (Patent Connector)
  ↓
Hero Section
  "기술 설명으로 관련 특허를 찾아보세요"
  ↓
KIPRIS 잔여 호출 수 표시 (우측 상단 뱃지)
  ↓
입력 영역
  - 기술 설명 textarea
  - 검색 버튼
  ↓
진행률 영역 (검색 중)
  - 현재 단계: 검색식 생성 → 특허 검색 → 결과 평가
  - 반복 횟수: "개선 중 (2/3)"
  - 개선 사유: "검색 범위가 너무 넓어 키워드를 구체화합니다"
  ↓
결과 영역
  ├─ 최종 검색식 표시 (키워드 태그 + CPC 코드)
  ├─ 탭: 한국 특허 (N건) / 미국 특허 (N건)
  └─ PatentList 컴포넌트
      └─ 각 카드: 제목, 출원번호, 출원일, 초록 요약, 원문 링크
```

### 디자인 시스템

hs-connector의 `index.css`와 `App.css`를 그대로 복사하여 사용. 브랜드명과 네비게이션 링크만 변경. 전체 CSS 변수 세트(색상, 타이포그래피, 애니메이션)를 동일하게 유지하여 패밀리룩 보장.

### API 클라이언트

```typescript
searchStream(description: string, onStep: (event) => void): Promise<SearchResponse>
getKiprisQuota(): Promise<KiprisQuota>
```

---

## 환경 변수

```env
# Gemini API
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash

# KIPRIS API
KIPRIS_API_KEY=...
KIPRIS_DAILY_LIMIT=100
KIPRIS_MAX_ITERATIONS=2

# PatentsView API (선택 — API 키 없이도 동작, 키 있으면 rate limit 완화)
PATENTSVIEW_API_KEY=
PATENTSVIEW_MAX_ITERATIONS=3

# Server
BACKEND_PORT=8013
FRONTEND_PORT=8094
```

`backend/.env.example` 파일을 제공하여 필수/선택 환경 변수를 안내한다.

---

## Docker Compose

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8013:8000"
    env_file: ./backend/.env
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
    build: ./frontend
    ports:
      - "8094:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
```

---

## 비기능 요구사항

- **타임아웃**: 파이프라인 전체 180초 (최대 3회 반복 고려)
- **레이트 리미팅**: KIPRIS 월간 카운터 + PatentsView 45req/min 준수
- **에러 처리**:
  - 외부 API 실패 시 최대 2회 재시도 (지수 백오프: 1초, 2초)
  - 재시도 후에도 실패 시 해당 국가 스킵, SSE error 이벤트 전송 후 나머지 결과 반환
  - Gemini API 실패 시 파이프라인 중단 (recoverable: false)
- **CORS**: 개발 모드 전체 허용
- **로깅**: INFO/WARNING/ERROR 레벨
- **빈 결과 처리**: 한국/미국 모두 0건일 경우 프론트엔드에서 "검색 결과가 없습니다. 기술 설명을 더 구체적으로 입력해 보세요." 안내 메시지 표시. 한쪽만 0건이면 해당 탭에 빈 상태 메시지 표시.
