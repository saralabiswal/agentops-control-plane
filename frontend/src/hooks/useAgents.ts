import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { AgentDefinition, TaskSubmit } from '../api/types'

export function useAgents() {
  const [agents, setAgents] = useState<AgentDefinition[]>([])

  useEffect(() => {
    void api.agents.list().then(setAgents).catch(() => setAgents([]))
  }, [])

  const submit = useCallback((payload: TaskSubmit) => api.tasks.submit(payload), [])

  return { agents, submit }
}

