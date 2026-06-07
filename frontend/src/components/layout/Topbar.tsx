import { Play, Plus } from 'lucide-react'

import type { Session } from '../../api/types'
import { KpiCard } from '../shared/KpiCard'

type Props = {
  session: Session | null
  onNewPlan: () => void
  onRunSession: () => void
}

export function Topbar({ session, onNewPlan, onRunSession }: Props) {
  return (
    <header className="topbar">
      <KpiCard label="Session" value={session?.status ?? 'Starting'} />
      <KpiCard label="Tasks" value={`${session?.total_tasks ?? 0}`} />
      <KpiCard label="Cost" value={`$${(session?.total_cost_usd ?? 0).toFixed(2)}`} />
      <KpiCard label="Quality" value={`${Math.round((session?.avg_quality_score ?? 0) * 100)}%`} />
      <button className="icon-button" onClick={onNewPlan} title="New plan"><Plus size={18} />New plan</button>
      <button className="icon-button primary" onClick={onRunSession} title="Run session"><Play size={18} />Run</button>
    </header>
  )
}

