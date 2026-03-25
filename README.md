# Patent Connector

기술 설명을 입력하면 AI가 특허 검색식을 자동 생성하고, 한국 특허를 검색한 뒤 관련성을 평가하는 시스템입니다.

## 주요 기능

- **검색식 자동 생성** — Gemini LLM이 기술 설명에서 개념 그룹(유의어 포함)을 추출하여 불리언 검색식 생성
- **KIPRIS 특허 검색** — 한국 특허 최대 500건 조회, AND(`*`)/OR(`+`) 연산자 활용
- **LLM 관련성 스코어링** — 500건 전체를 1~5점으로 평가 (100건씩 배치 병렬)
- **정량 기반 검색식 개선** — 관련성 점수 분포가 임계값 미달 시 자동으로 검색식 개선 반복
- **검색식 클립보드 복사** — IPC 코드 포함 최종 검색식을 한 번에 복사

## 파이프라인 흐름

```
기술 설명 입력
  → [Gemini] 검색식 생성 (개념 그룹 + IPC/CPC)
  → [KIPRIS] 한국 특허 500건 검색
  → [Gemini] 관련성 스코어링 (1~5점, 100건×5배치 병렬)
  → [정량 평가] 3점이상 비율 / 1점 비율 임계값 판정
  → PASS → 결과 반환 (점수순 정렬)
  → FAIL → 검색식 개선 → 재검색 (최대 2회)
```

## 스택

| 구분 | 기술 |
|------|------|
| Backend | FastAPI, Google Gemini, KIPRIS API |
| Frontend | React, Vite, TypeScript |
| Infra | Docker Compose, Nginx |

## 빠른 시작

### 1. 환경변수 설정

프로젝트 루트에 `.env` 파일 생성:

```bash
cp backend/.env.example .env
```

필수 항목:

| 변수 | 설명 | 발급처 |
|------|------|--------|
| `GEMINI_API_KEY` | Gemini API 키 | [Google AI Studio](https://aistudio.google.com/) |
| `KIPRIS_API_KEY` | KIPRIS API 키 | [KIPRIS Plus](https://plus.kipris.or.kr/) |

### 2. Docker로 실행

```bash
docker compose up -d --build
```

- Frontend: http://localhost:8094
- Backend API: http://localhost:8013

### 3. 로컬 개발

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev    # http://localhost:5182
```

## 환경변수

```env
# 필수
GEMINI_API_KEY=your-gemini-api-key
KIPRIS_API_KEY=your-kipris-api-key

# 모델 설정
GEMINI_MODEL=gemini-2.0-flash          # Gemini 모델 (기본: 2.0-flash)

# KIPRIS 설정
KIPRIS_DAILY_LIMIT=100                  # 일일 API 호출 한도
KIPRIS_MAX_ITERATIONS=2                 # 검색식 개선 최대 반복 횟수

# 관련성 평가 임계값
RELEVANCE_MIN_GOOD_RATIO=0.4           # 3점 이상 비율 >= 40%이면 통과
RELEVANCE_MAX_NOISE_RATIO=0.3          # 1점 비율 <= 30%이면 통과

# 포트
BACKEND_PORT=8013
FRONTEND_PORT=8094
```

## 관련성 점수 기준

| 점수 | 라벨 | 의미 |
|:----:|------|------|
| 5 | 핵심 | 핵심 기술 직접 일치 |
| 4 | 높음 | 동일 기술 문제/방법 |
| 3 | 보통 | 주요 기술 요소 공유 |
| 2 | 낮음 | 주변적 관련만 있음 |
| 1 | 무관 | 다른 기술 분야 |

## 버전 관리

```bash
cd frontend
npm version patch   # 0.2.0 → 0.2.1
npm version minor   # 0.2.0 → 0.3.0
npm version major   # 0.2.0 → 1.0.0
```

버전은 프론트엔드 하단 우측에 자동 표시됩니다.

## 프로젝트 구조

```
├── .env                          # 환경변수 (git 제외)
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI 앱
│   │   ├── api/routes.py         # API 엔드포인트
│   │   ├── core/
│   │   │   ├── config.py         # 설정
│   │   │   └── pipeline.py       # 검색 파이프라인
│   │   ├── models/schemas.py     # 데이터 모델
│   │   └── services/
│   │       ├── query_generator.py     # 검색식 생성 (Gemini)
│   │       ├── result_evaluator.py    # 관련성 스코어링 + 정량 평가
│   │       └── searchers/
│   │           ├── kipris.py          # KIPRIS API 어댑터
│   │           └── patentsview.py     # PatentsView API (일시 중지)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/SearchPage.tsx       # 메인 검색 페이지
│   │   └── components/PatentList.tsx  # 특허 목록 + 페이지네이션
│   └── package.json
└── data/                         # 런타임 데이터 (quota 등)
```
