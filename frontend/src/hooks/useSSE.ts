import { useEffect, useRef } from 'react'

export type SSEEvent = {
  event: 'run_started' | 'run_completed' | 'quality_scored'
  run_id: string
  [key: string]: unknown
}

export function useSSE(onEvent: (event: SSEEvent) => void) {
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource('/api/v1/stream/runs')
    esRef.current = es
    es.onmessage = (e) => {
      try {
        onEvent(JSON.parse(e.data) as SSEEvent)
      } catch {
        /* Heartbeats and malformed messages are ignored. */
      }
    }
    es.onerror = () => {
      setTimeout(() => es.close(), 3000)
    }
    return () => es.close()
  }, [onEvent])
}

