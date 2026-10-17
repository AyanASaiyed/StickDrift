import type { Concern, Insights, Risk } from '../api'

const RISK_LABEL: Record<Risk, string> = {
  check: 'Check soon',
  watch: 'Keep an eye on',
  none: 'No concerns',
}

export function RiskBadge({ risk }: { risk: Risk }) {
  return <span className={`risk-badge risk-${risk}`}>{RISK_LABEL[risk]}</span>
}

/** Top-of-page alert shown to caregivers when a resident has a potential health concern. */
export function RiskAlert({ name, insights }: { name: string; insights: Insights }) {
  if (insights.status !== 'ok') {
    return (
      <div className="risk-alert risk-alert-none" role="status">
        <strong>Building a baseline</strong>
        <p>{insights.summary}</p>
      </div>
    )
  }
  if (insights.risk === 'none') {
    return (
      <div className="risk-alert risk-alert-none" role="status">
        <strong>No potential health concerns</strong>
        <p>{name}’s recent sessions are in line with their usual pattern.</p>
      </div>
    )
  }
  const first = insights.concerns[0]
  return (
    <div className={`risk-alert risk-alert-${insights.risk}`} role="alert">
      <div className="risk-alert-head">
        <svg viewBox="0 0 24 24" aria-hidden className="risk-icon">
          <path d="M12 3 2 21h20L12 3Z" />
          <path d="M12 10v5M12 18v.01" />
        </svg>
        <div>
          <strong>
            {insights.risk === 'check' ? 'Alert: ' : 'Watch: '}
            {name} may have a potential health concern
          </strong>
          <p>
            {insights.concerns.map((c) => c.title).join(' · ')}. {first.recommended_checks[0]}
          </p>
        </div>
      </div>
      <a className="risk-alert-link" href="#concerns">
        See evidence and recommended checks
      </a>
      {insights.synthetic && <p className="risk-alert-note">Based on simulated demo data.</p>}
    </div>
  )
}

export function ConcernCard({ concern }: { concern: Concern }) {
  return (
    <article className={`concern concern-${concern.level}`}>
      <header>
        <h3>{concern.title}</h3>
        <span className={`risk-badge risk-${concern.level}`}>{RISK_LABEL[concern.level]}</span>
      </header>
      <p>{concern.summary}</p>
      <div className="concern-cols">
        <section>
          <h4>Contributing measurements</h4>
          <ul>
            {concern.evidence.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </section>
        <section>
          <h4>Possible contributors</h4>
          <ul>
            {concern.possible_contributors.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </section>
      </div>
      <section className="concern-checks">
        <h4>Recommended caregiver checks</h4>
        <ol>
          {concern.recommended_checks.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ol>
      </section>
      <details className="concern-refs">
        <summary>Research basis</summary>
        <ul>
          {concern.references.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </details>
    </article>
  )
}
