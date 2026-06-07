import type { BusinessOutcome } from '../../api/types'

export function OutcomeItem({ outcome }: { outcome: BusinessOutcome }) {
  return (
    <article className="outcome-item">
      <span>{outcome.domain}</span>
      <strong>${Math.round(outcome.financial_impact_usd).toLocaleString()}</strong>
      <p>{outcome.metric_name}</p>
    </article>
  )
}

