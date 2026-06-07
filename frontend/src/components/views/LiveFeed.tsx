import type { AgentRun, BusinessOutcome } from '../../api/types'
import { OutcomeItem } from '../shared/OutcomeItem'
import { RunCard } from '../shared/RunCard'
import { WorkflowCard } from '../shared/WorkflowCard'

type Props = {
  runs: AgentRun[]
  outcomes: BusinessOutcome[]
}

export function LiveFeed({ runs, outcomes }: Props) {
  return (
    <div className="view-grid">
      <section className="main-column">
        <WorkflowCard runs={runs} />
        <div className="section-title"><h2>Live run feed</h2></div>
        <div className="run-list">
          {runs.map((run) => <RunCard key={run.id} run={run} />)}
          {runs.length === 0 && <div className="empty-state">Waiting for agent activity</div>}
        </div>
      </section>
      <aside className="side-column">
        <div className="section-title"><h2>Financial outcomes</h2></div>
        {outcomes.slice(0, 5).map((outcome) => <OutcomeItem key={outcome.id} outcome={outcome} />)}
      </aside>
    </div>
  )
}

