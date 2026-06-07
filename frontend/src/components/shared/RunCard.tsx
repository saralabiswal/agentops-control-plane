import { CheckCircle2, Clock3, XCircle } from 'lucide-react'

import type { AgentRun } from '../../api/types'

export function RunCard({ run }: { run: AgentRun }) {
  const Icon = run.status === 'COMPLETE' ? CheckCircle2 : run.status === 'FAILED' ? XCircle : Clock3
  return (
    <article className={`run-card ${run.status === 'FAILED' ? 'run-card-failed' : ''}`}>
      <div className="run-card-row">
        <div className="run-status">
          <Icon size={18} />
          <span>{run.status}</span>
        </div>
        <div>
          <h3>{run.agent_id}</h3>
          <p>{run.run_type} · {run.model_used}</p>
        </div>
        <dl>
          <div><dt>Latency</dt><dd>{run.latency_ms} ms</dd></div>
          <div><dt>Tokens</dt><dd>{run.total_tokens}</dd></div>
          <div><dt>Quality</dt><dd>{run.quality_score ?? 'pending'}</dd></div>
        </dl>
      </div>
      {run.status === 'FAILED' && run.error_message && (
        <p className="run-error">{run.error_message}</p>
      )}
    </article>
  )
}
