import { useEffect } from 'react'
import { useProjectStore } from '@/store/useProjectStore'

/**
 * Subscribes to the backend SSE stream at /api/watch/events.
 * On each badge_update event, updates the matching project's changedCount
 * in the Zustand store.
 *
 * EventSource auto-reconnects on error — no manual reconnect logic needed
 * for same-host connections (browser handles it).
 *
 * Call this hook once at the App.tsx top level so badge updates are received
 * regardless of which project is active.
 */
export function useWatchEvents() {
  const setChangedCount = useProjectStore((s) => s.setChangedCount)

  useEffect(() => {
    const es = new EventSource('/api/watch/events')

    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data)
        if (payload.type === 'badge_update') {
          setChangedCount(payload.project_id, payload.changed_count)
        }
      } catch {
        // Ignore malformed events — do not crash the hook
      }
    }

    es.onerror = () => {
      // EventSource reconnects automatically after error on same-host SSE.
      // Log in dev mode only.
      if (import.meta.env.DEV) {
        console.warn('[useWatchEvents] SSE connection error — browser will reconnect')
      }
    }

    return () => {
      es.close()
    }
  }, [setChangedCount])
}
