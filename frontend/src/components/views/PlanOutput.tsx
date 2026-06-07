import type { AgentRun } from '../../api/types'

export function PlanOutput({ runs }: { runs: AgentRun[] }) {
  const parent = runs.find((run) => run.run_type === 'WORKFLOW_PARENT')
  const plan = parent?.output_payload ?? {}
  return (
    <section className="page-section">
      <div className="section-title"><h2>Plan output</h2></div>
      <div className="plan-layout">
        <article className="plan-summary">
          <span>{String(plan.project_title ?? 'No plan generated')}</span>
          <p>{String(plan.executive_summary ?? 'Run ProjectPlanningAgent to populate this view.')}</p>
          <strong>{String(plan.delivery_confidence ?? '0')} confidence</strong>
        </article>
        <pre>{JSON.stringify(plan, null, 2)}</pre>
      </div>
    </section>
  )
}

