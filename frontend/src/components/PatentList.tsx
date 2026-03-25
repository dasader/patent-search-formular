import { useState } from 'react'
import type { NormalizedPatent } from '../api/types'
import './PatentList.css'

interface Props {
  patents: NormalizedPatent[]
}

const PAGE_SIZE = 20

const scoreLabel = (score: number | null) => {
  if (score == null) return null
  const labels: Record<number, string> = { 5: '핵심', 4: '높음', 3: '보통', 2: '낮음', 1: '무관' }
  return labels[score] || ''
}

const statusBadge = (status: string | null) => {
  if (!status) return null
  const isRegistered = status.includes('등록')
  return (
    <span className={`status-badge ${isRegistered ? 'status-registered' : 'status-published'}`}>
      {isRegistered ? '✓ 등록' : '○ 출원'}
    </span>
  )
}

function PatentList({ patents }: Props) {
  const [page, setPage] = useState(0)
  const totalPages = Math.ceil(patents.length / PAGE_SIZE)
  const start = page * PAGE_SIZE
  const visible = patents.slice(start, start + PAGE_SIZE)

  return (
    <div className="patent-list">
      <div className="pagination-info">
        {patents.length}건 중 {start + 1}~{Math.min(start + PAGE_SIZE, patents.length)}건 표시
      </div>
      {visible.map((patent, index) => (
        <div
          key={`${patent.country}-${patent.application_number}`}
          className={`patent-card ${patent.relevance_score ? `relevance-${patent.relevance_score}` : ''}`}
          style={{ animationDelay: `${index * 0.06}s` }}
        >
          <div className="patent-card-header">
            <div className="patent-title-area">
              {patent.relevance_score != null && (
                <span className={`relevance-badge score-${patent.relevance_score}`}>
                  {patent.relevance_score} {scoreLabel(patent.relevance_score)}
                </span>
              )}
              {patent.country === 'KR' && statusBadge(patent.register_status)}
              <h4 className="patent-title">{patent.title}</h4>
            </div>
            <span className="patent-number">{patent.application_number}</span>
          </div>

          {patent.relevance_reason && (
            <div className="relevance-reason">{patent.relevance_reason}</div>
          )}

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
      {totalPages > 1 && (
        <div className="pagination">
          <button
            className="pagination-btn"
            disabled={page === 0}
            onClick={() => setPage(0)}
          >
            {'<<'}
          </button>
          <button
            className="pagination-btn"
            disabled={page === 0}
            onClick={() => setPage(p => p - 1)}
          >
            {'<'}
          </button>
          {Array.from({ length: totalPages }, (_, i) => i)
            .filter(i => Math.abs(i - page) <= 2 || i === 0 || i === totalPages - 1)
            .reduce<number[]>((acc, i) => {
              if (acc.length > 0 && i - acc[acc.length - 1] > 1) acc.push(-1)
              acc.push(i)
              return acc
            }, [])
            .map((i, idx) =>
              i === -1 ? (
                <span key={`dot-${idx}`} className="pagination-dots">...</span>
              ) : (
                <button
                  key={i}
                  className={`pagination-btn ${i === page ? 'active' : ''}`}
                  onClick={() => setPage(i)}
                >
                  {i + 1}
                </button>
              )
            )}
          <button
            className="pagination-btn"
            disabled={page === totalPages - 1}
            onClick={() => setPage(p => p + 1)}
          >
            {'>'}
          </button>
          <button
            className="pagination-btn"
            disabled={page === totalPages - 1}
            onClick={() => setPage(totalPages - 1)}
          >
            {'>>'}
          </button>
        </div>
      )}
    </div>
  )
}

export default PatentList
