export interface SearchQuery {
  keywords_kr: string[]
  keywords_en: string[]
  keyword_groups_kr: string[][]
  keyword_groups_en: string[][]
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
  register_status: string | null
  relevance_score: number | null
  relevance_reason: string | null
}

export interface SearchResponse {
  query_kr: SearchQuery
  query_us: SearchQuery
  patents_kr: NormalizedPatent[]
  patents_us: NormalizedPatent[]
  iterations_kr: number
  iterations_us: number
  total_kr: number
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
  good_ratio?: number
  noise_ratio?: number
  satisfied?: boolean
}
