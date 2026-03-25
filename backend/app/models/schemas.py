from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    description: str = Field(..., min_length=10, max_length=5000)


class SearchQuery(BaseModel):
    keywords_kr: list[str] = []
    keywords_en: list[str] = []
    keyword_groups_kr: list[list[str]] = []   # 개념 그룹 (한국어)
    keyword_groups_en: list[list[str]] = []   # 개념 그룹 (영어, 유의어 포함)
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
    relevance_score: int | None = None      # 1~5 기술 관련성 점수
    relevance_reason: str | None = None     # 관련성 판단 사유


class SearchResponse(BaseModel):
    query_kr: SearchQuery
    query_us: SearchQuery
    patents_kr: list[NormalizedPatent] = []
    patents_us: list[NormalizedPatent] = []
    iterations_kr: int = 0
    iterations_us: int = 0
    total_kr: int = 0
    kipris_remaining: int = 0
    processing_time_ms: int = 0


class KiprisQuota(BaseModel):
    used: int
    limit: int
    remaining: int
    resets_at: str


class ErrorResponse(BaseModel):
    detail: str
