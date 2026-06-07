import type { AgentRun } from '../../api/types'
import { QualityBars } from '../shared/QualityBars'

export function QualityDrift({ runs }: { runs: AgentRun[] }) {
  return (
    <section className="page-section">
      <div className="section-title"><h2>Quality drift</h2></div>
      <div className="run-list">
        {runs.map((run) => (
          <article className="run-card" key={run.id}>
            <strong>{run.agent_id}</strong>
            <QualityBars score={run.quality_score} />
            <p>{String(run.quality_dimensions?.reasoning_trace ?? 'Pending judge reasoning')}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

