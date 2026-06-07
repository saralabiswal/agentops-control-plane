import { GitBranch } from 'lucide-react'

import type { AgentRun } from '../../api/types'

export function WorkflowCard({ runs }: { runs: AgentRun[] }) {
  const nodes = runs.filter((run) => run.run_type === 'WORKFLOW_NODE')
  return (
    <section className="workflow-band">
      <div className="section-title">
        <GitBranch size={18} />
        <h2>ProjectPlanning workflow</h2>
      </div>
      <div className="node-strip">
        {['decompose', 'capacity', 'risk', 'assign', 'synthesize'].map((node, index) => (
          <span key={node} className={nodes[index] ? 'node node-done' : 'node'}>
            {node}
          </span>
        ))}
      </div>
    </section>
  )
}

