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
