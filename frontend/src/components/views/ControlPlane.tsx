import type { AgentDefinition, AgentRun } from '../../api/types'
import { QualityBars } from '../shared/QualityBars'
import { RoiBox } from '../shared/RoiBox'
import { SparkLine } from '../shared/SparkLine'

export function ControlPlane({
  agents,
  runs,
  impact,
}: {
  agents: AgentDefinition[]
  runs: AgentRun[]
  impact: number
}) {
  const cost = runs.reduce((sum, run) => sum + run.cost_usd, 0)
  return (
    <div className="view-grid">
      <section className="main-column">
        <div className="section-title"><h2>Agent pool</h2></div>
        <div className="agent-grid">
          {agents.map((agent) => (
            <article className="agent-tile" key={agent.id}>
              <strong>{agent.name}</strong>
              <span>{agent.domain}</span>
              <QualityBars score={runs.find((run) => run.agent_id === agent.id)?.quality_score ?? null} />
            </article>
          ))}
        </div>
      </section>
      <aside className="side-column">
        <RoiBox impact={impact} cost={cost} />
        <SparkLine values={[0.72, 0.76, 0.71, 0.82, 0.79, 0.86]} />
      </aside>
    </div>
  )
}

