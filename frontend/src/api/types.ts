export type Persona = 'business' | 'technical'

export type AgentDefinition = {
  id: string
  name: string
  domain: string
  agent_type: string
  description: string
  model_default: string
  execution_mode: string
}

export type ModelPricing = {
  id: string
  provider: string
  model_name: string
  input_cost_per_1k: number
  output_cost_per_1k: number
  api_call_cost_per_1k: number
  compute_vcpu_cost_per_second: number
  compute_memory_gib_cost_per_second: number
  effective_from: string
  effective_to: string | null
}

export type RuntimeProvider = {
  provider: 'ollama' | 'groq' | 'gemini'
  label: string
  configured: boolean
  active_model: string
  models: string[]
  next_action: string
}

export type RuntimeSettings = {
  active_provider: 'ollama' | 'groq' | 'gemini'
  active_model: string
  providers: RuntimeProvider[]
}

export type RuntimeSettingsUpdate = {
  active_provider: 'ollama' | 'groq' | 'gemini'
  model_name: string
}

export type Session = {
  id: string
  name: string
  status: string
  total_cost_usd: number
  total_tasks: number
  success_rate: number
  avg_quality_score: number
}

export type AgentRun = {
  id: string
  task_id: string
  agent_id: string
  run_type: string
  parent_run_id: string | null
  model_used: string
  status: string
  error_message: string | null
  latency_ms: number
  cost_usd: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  output_payload: Record<string, unknown>
  quality_score: number | null
  quality_dimensions: Record<string, unknown> | null
}

export type BusinessOutcome = {
  id: string
  task_id: string
  agent_run_id: string
  domain: string
  outcome_type: string
  metric_name: string
  metric_value: number
  metric_unit: string
  financial_impact_usd: number
  confidence_score: number
  computed_at: string
}

export type TaskSubmit = {
  agent_id: string
  session_id: string
  input_payload: Record<string, unknown>
  priority?: 'LOW' | 'NORMAL' | 'HIGH'
}

export type Task = TaskSubmit & {
  id: string
  domain: string
  task_type: string
  status: string
}
