/**
 * UI-context bridge for AC4.
 *
 * Pages that render data the user can ask questions about (the portfolio
 * dashboard today, the uploads page tomorrow) call `setUiContext({...})` to
 * publish a JSON snapshot. The chat hook reads `useUiContext()` and ships
 * the latest snapshot along with each `streamChat` call so the model can
 * ground numerical claims in what's on screen.
 *
 * Snapshot shape is intentionally untyped (`object | null`) — pages
 * decide what's relevant; the model is told to treat the JSON as the only
 * source of truth for those numbers.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"

type Snapshot = object | null

type UiContextValue = {
  /** The most recently published snapshot, or null if no page is publishing. */
  snapshot: Snapshot
  /** Publish a snapshot. Pass null on unmount to clear. */
  setUiContext: (value: Snapshot) => void
  /** Stable getter for consumers that read at send-time only. */
  getSnapshot: () => Snapshot
}

const UiContext = createContext<UiContextValue | undefined>(undefined)

export function UiContextProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshotState] = useState<Snapshot>(null)
  // Mirror in a ref so consumers (e.g. useChat.send) read the freshest value
  // at call time without re-subscribing on every snapshot change.
  const ref = useRef<Snapshot>(null)

  const setUiContext = useCallback((value: Snapshot) => {
    ref.current = value
    setSnapshotState(value)
  }, [])

  const getSnapshot = useCallback(() => ref.current, [])

  const value = useMemo<UiContextValue>(
    () => ({ snapshot, setUiContext, getSnapshot }),
    [snapshot, setUiContext, getSnapshot],
  )

  return <UiContext.Provider value={value}>{children}</UiContext.Provider>
}

export function useUiContext(): UiContextValue {
  const ctx = useContext(UiContext)
  if (!ctx) {
    // Tolerant fallback for tests / pages mounted outside the provider.
    // Returns an inert no-op so consumers don't blow up.
    return INERT
  }
  return ctx
}

const INERT: UiContextValue = {
  snapshot: null,
  setUiContext: () => {},
  getSnapshot: () => null,
}

/**
 * Helper for pages: publish on mount/update, clear on unmount.
 *
 *   usePublishUiContext(snapshot)
 *
 * Re-publishes whenever `snapshot` changes (referential equality). Pages
 * should memoise their snapshot if they want to avoid spurious updates.
 */
export function usePublishUiContext(snapshot: Snapshot): void {
  const { setUiContext } = useUiContext()
  useEffect(() => {
    setUiContext(snapshot)
    return () => setUiContext(null)
  }, [snapshot, setUiContext])
}
