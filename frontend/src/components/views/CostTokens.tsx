import type { AgentRun } from '../../api/types'

export function CostTokens({ runs }: { runs: AgentRun[] }) {
  return (
    <section className="page-section">
      <div className="section-title"><h2>Cost & tokens</h2></div>
      <table>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id}>
              <td>{run.model_used}</td>
              <td>{run.total_tokens} tokens</td>
              <td>${run.cost_usd.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

