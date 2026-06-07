import { Activity, BarChart3, BrainCircuit, Database, DollarSign, Settings, ShieldCheck } from 'lucide-react'

import type { Persona } from '../../api/types'

const items = [
  ['live', Activity, 'Live feed'],
  ['plan', BrainCircuit, 'Plan output'],
  ['outcomes', DollarSign, 'Outcomes'],
  ['control', ShieldCheck, 'Control plane'],
  ['quality', BarChart3, 'Quality drift'],
  ['cost', DollarSign, 'Cost & tokens'],
  ['data', Database, 'Data model'],
  ['api', Activity, 'API surface'],
  ['settings', Settings, 'Settings'],
] as const

type Props = {
  active: string
  persona: Persona
  onNavigate: (view: string) => void
  onPersona: (persona: Persona) => void
}

export function Sidebar({ active, persona, onNavigate, onPersona }: Props) {
  return (
    <aside className="sidebar">
      <div className="brand">AgentOps</div>
      <div className="persona-toggle">
        <button className={persona === 'business' ? 'active' : ''} onClick={() => onPersona('business')}>Business</button>
        <button className={persona === 'technical' ? 'active' : ''} onClick={() => onPersona('technical')}>Technical</button>
      </div>
      <nav>
        {items.map(([id, Icon, label]) => (
          <button key={id} className={active === id ? 'active' : ''} onClick={() => onNavigate(id)}>
            <Icon size={17} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="model-pill">Ollama · llama3.2:3b</div>
    </aside>
  )
}

