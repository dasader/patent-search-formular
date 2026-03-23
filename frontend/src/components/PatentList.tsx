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
