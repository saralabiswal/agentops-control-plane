import type {
  AgentDefinition,
  AgentRun,
  BusinessOutcome,
  ModelPricing,
  RuntimeSettings,
  RuntimeSettingsUpdate,
  Session,
  Task,
  TaskSubmit,
} from './types'

const BASE = '/api/v1'
const REQUEST_TIMEOUT_MS = 15000

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
      signal: init?.signal ?? controller.signal,
    })
    if (!res.ok) {
      let detail = ''
      try {
        const body = await res.json() as { detail?: string }
        detail = body.detail ? `: ${body.detail}` : ''
      } catch {
        detail = ''
      }
      throw new Error(`${res.status} ${res.statusText}${detail}`)
    }
    return res.json() as Promise<T>
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('API request timed out. Confirm the backend is running on port 8000.')
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}

export const api = {
  sessions: {
    create: (name: string) =>
      req<Session>('/sessions', { method: 'POST', body: JSON.stringify({ name }) }),
    list: () => req<Session[]>('/sessions'),
    get: (id: string) => req<Session>(`/sessions/${id}`),
    close: (id: string) => req<Session>(`/sessions/${id}/close`, { method: 'POST' }),
  },
  tasks: {
    submit: (payload: TaskSubmit) =>
      req<Task>('/tasks', { method: 'POST', body: JSON.stringify(payload) }),
    batch: (payload: { tasks: TaskSubmit[] }) =>
      req<Task[]>('/tasks/batch', { method: 'POST', body: JSON.stringify(payload) }),
    status: (id: string) => req<{ id: string; status: string }>(`/tasks/${id}/status`),
    retry: (id: string) => req<Task>(`/tasks/${id}/retry`, { method: 'POST' }),
  },
  runs: {
    list: (params?: Record<string, string>) =>
      req<AgentRun[]>(`/runs?${new URLSearchParams(params)}`),
    get: (id: string) => req<AgentRun>(`/runs/${id}`),
    quality: (id: string) => req<Record<string, unknown>>(`/runs/${id}/quality`),
  },
  outcomes: {
    session: (id: string) =>
      req<{ session_id: string; total_financial_impact_usd: number; outcomes: BusinessOutcome[] }>(
        `/outcomes/session/${id}`,
      ),
    summary: () => req<{ total_financial_impact_usd: number; total_cost_usd: number; roi_multiple: number }>('/outcomes/summary'),
  },
  agents: {
    list: () => req<AgentDefinition[]>('/agents'),
  },
  pricing: {
    list: () => req<ModelPricing[]>('/pricing'),
  },
  settings: {
    runtime: () => req<RuntimeSettings>('/settings/runtime'),
    updateRuntime: (payload: RuntimeSettingsUpdate) =>
      req<RuntimeSettings>('/settings/runtime', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      }),
  },
}
