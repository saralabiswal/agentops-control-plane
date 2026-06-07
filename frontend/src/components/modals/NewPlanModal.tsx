import { X } from 'lucide-react'
import { useState } from 'react'

import type { Session, TaskSubmit } from '../../api/types'

type Props = {
  session: Session | null
  onClose: () => void
  onSubmit: (payload: TaskSubmit) => Promise<void>
}

const team = [
  { name: 'Tom W.', role: 'Tech Lead', skills: ['infra', 'payments', 'k8s'], load_pct: 55 },
  { name: 'James K.', role: 'Senior Eng', skills: ['backend', 'payments'], load_pct: 60 },
  { name: 'Mei L.', role: 'Senior Eng', skills: ['frontend', 'testing'], load_pct: 30 },
]

export function NewPlanModal({ session, onClose, onSubmit }: Props) {
  const [instruction, setInstruction] = useState('Launch a customer-facing billing migration in Q3.')
  const [timelineWeeks, setTimelineWeeks] = useState(8)
  const [revenue, setRevenue] = useState(240000)

  async function submit() {
    if (!session) return
    await onSubmit({
      agent_id: 'agent-project-planning',
      session_id: session.id,
      input_payload: {
        instruction,
        team_members: team,
        timeline_weeks: timelineWeeks,
        committed_revenue_usd: revenue,
      },
      priority: 'HIGH',
    })
    onClose()
  }

  return (
    <div className="modal-backdrop">
      <section className="modal">
        <button className="close-button" onClick={onClose} title="Close"><X size={18} /></button>
        <h2>New plan</h2>
        <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} />
        <label>Timeline weeks<input type="number" value={timelineWeeks} onChange={(event) => setTimelineWeeks(Number(event.target.value))} /></label>
        <label>Committed revenue<input type="number" value={revenue} onChange={(event) => setRevenue(Number(event.target.value))} /></label>
        <button className="icon-button primary" onClick={() => void submit()}>Run workflow</button>
      </section>
    </div>
  )
}

