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
