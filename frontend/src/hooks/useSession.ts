import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { Session } from '../api/types'

export function useSession() {
  const [session, setSession] = useState<Session | null>(null)

  const create = useCallback(async () => {
    const next = await api.sessions.create(`Demo Session ${new Date().toLocaleTimeString()}`)
    setSession(next)
    return next
  }, [])

  useEffect(() => {
    void create()
  }, [create])

  return { session, create }
}

