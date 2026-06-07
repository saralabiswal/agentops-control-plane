import type { BusinessOutcome, Persona } from '../../api/types'
import { OutcomeItem } from '../shared/OutcomeItem'

export function Outcomes({ outcomes, persona }: { outcomes: BusinessOutcome[]; persona: Persona }) {
  const total = outcomes.reduce((sum, outcome) => sum + outcome.financial_impact_usd, 0)
  if (persona === 'technical') {
    return (
      <section className="page-section">
        <div className="section-title"><h2>Outcome rows</h2></div>
        <table>
          <tbody>
            {outcomes.map((outcome) => (
              <tr key={outcome.id}>
                <td>{outcome.domain}</td>
                <td>{outcome.metric_name}</td>
                <td>${Math.round(outcome.financial_impact_usd).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    )
  }
  return (
    <section className="page-section">
      <div className="hero-metric">
        <span>Total protected</span>
        <strong>${Math.round(total).toLocaleString()}</strong>
      </div>
      <div className="outcome-grid">
        {outcomes.map((outcome) => <OutcomeItem key={outcome.id} outcome={outcome} />)}
      </div>
    </section>
  )
}

