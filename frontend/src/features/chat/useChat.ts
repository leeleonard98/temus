import { useCallback, useEffect, useRef, useState } from "react"

import {
  createSession,
  listMessages,
  listSessions,
  streamChat,
  upsertUser,
  type AgentEvent,
  type Message,
  type Role,
  type Session,
  type User,
} from "@/lib/chat-api"

const STORAGE_KEY = "aurawealth.chat.v1"

type Persisted = {
  role: Role
  /** Cache of role -> userId so role flips don't reissue upserts when avoidable. */
  userIds: Partial<Record<Role, string>>
  /** Last-selected session per role, so a refresh restores context. */
  sessionIds: Partial<Record<Role, string>>
}

const SEED_IDENTITIES: Record<Role, { email: string; display_name: string }> = {
  client: { email: "client-demo@aura.test", display_name: "Demo Client" },
  advisor: { email: "advisor-demo@aura.test", display_name: "Demo Advisor" },
}

function loadPersisted(): Persisted {
  if (typeof localStorage === "undefined") {
    return { role: "client", userIds: {}, sessionIds: {} }
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { role: "client", userIds: {}, sessionIds: {} }
    const parsed = JSON.parse(raw) as Partial<Persisted>
    const role: Role = parsed.role === "advisor" ? "advisor" : "client"
    return {
      role,
      userIds: parsed.userIds ?? {},
      sessionIds: parsed.sessionIds ?? {},
    }
  } catch {
    return { role: "client", userIds: {}, sessionIds: {} }
  }
}

function savePersisted(p: Persisted) {
  if (typeof localStorage === "undefined") return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(p))
  } catch {
    /* quota / private mode */
  }
}

/** Per-stage status of the agent pipeline as the trace events arrive. */
export type StageStatus = "idle" | "running" | "complete"

export type AgentTrace = {
  researcher: { status: StageStatus; topics: string[]; rationale: string }
  analyst: {
    status: StageStatus
    findings: { claim: string; confidence: string }[]
    summary: string
  }
  writer: { status: StageStatus }
}

export function emptyTrace(): AgentTrace {
  return {
    researcher: { status: "idle", topics: [], rationale: "" },
    analyst: { status: "idle", findings: [], summary: "" },
    writer: { status: "idle" },
  }
}

function applyAgentEvent(prev: AgentTrace, ev: AgentEvent): AgentTrace {
  if (ev.type === "agent_start") {
    return { ...prev, [ev.agent]: { ...prev[ev.agent], status: "running" } }
  }
  if (ev.type === "agent_complete") {
    if (ev.agent === "researcher") {
      const topics = Array.isArray(ev.output.topics)
        ? (ev.output.topics as unknown[]).map((t) => String(t))
        : []
      const rationale = typeof ev.output.rationale === "string" ? ev.output.rationale : ""
      return { ...prev, researcher: { status: "complete", topics, rationale } }
    }
    if (ev.agent === "analyst") {
      const rawFindings = Array.isArray(ev.output.findings) ? ev.output.findings : []
      const findings = rawFindings
        .map((f) => {
          if (!f || typeof f !== "object") return null
          const obj = f as Record<string, unknown>
          const claim = typeof obj.claim === "string" ? obj.claim : ""
          const confidence = typeof obj.confidence === "string" ? obj.confidence : "medium"
          return claim ? { claim, confidence } : null
        })
        .filter((x): x is { claim: string; confidence: string } => x !== null)
      const summary = typeof ev.output.summary === "string" ? ev.output.summary : ""
      return { ...prev, analyst: { status: "complete", findings, summary } }
    }
    if (ev.agent === "writer") {
      return { ...prev, writer: { status: "complete" } }
    }
  }
  // agent_delta is currently ignored — the structured `complete` payload is enough.
  return prev
}

/** Local-only chat draft messages (assistant placeholder gets a temp id). */
type DraftMessage = Message & { pending?: boolean; trace?: AgentTrace }

export type UseChat = {
  user: User | null
  role: Role
  setRole: (role: Role) => void
  session: Session | null
  sessions: Session[]
  currentSessionId: string | null
  messages: DraftMessage[]
  send: (content: string) => Promise<void>
  newChat: () => Promise<void>
  selectSession: (id: string) => Promise<void>
  isStreaming: boolean
  error: string | undefined
}

export function useChat(): UseChat {
  const [persisted, setPersisted] = useState<Persisted>(() => loadPersisted())
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [sessions, setSessions] = useState<Session[]>([])
  const [messages, setMessages] = useState<DraftMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | undefined>(undefined)

  // Track the active bootstrap so role-switching mid-flight doesn't race.
  const bootstrapTokenRef = useRef(0)
  // Mirror persisted state in a ref so the bootstrap effect can read the
  // pinned sessionId for the active role without re-triggering on every
  // selectSession() call (which mutates persisted.sessionIds).
  const persistedRef = useRef(persisted)
  useEffect(() => {
    persistedRef.current = persisted
  }, [persisted])

  // Bootstrap on mount and whenever the role changes.
  useEffect(() => {
    const token = ++bootstrapTokenRef.current
    let cancelled = false

    async function bootstrap() {
      setError(undefined)
      setMessages([])
      setSession(null)
      setSessions([])
      try {
        const role = persistedRef.current.role
        const seed = SEED_IDENTITIES[role]
        const u = await upsertUser({ ...seed, role })
        if (cancelled || token !== bootstrapTokenRef.current) return
        setUser(u)
        setPersisted((prev) => {
          const next: Persisted = {
            ...prev,
            userIds: { ...prev.userIds, [role]: u.id },
          }
          savePersisted(next)
          return next
        })

        const existing = await listSessions(u.id)
        if (cancelled || token !== bootstrapTokenRef.current) return

        const persistedSessionId = persistedRef.current.sessionIds[role]
        const restored = persistedSessionId
          ? existing.find((s) => s.id === persistedSessionId)
          : undefined
        const s =
          restored ?? existing[0] ?? (await createSession({ user_id: u.id, title: "New chat" }))
        if (cancelled || token !== bootstrapTokenRef.current) return

        // Make sure the chosen session is reflected in the list.
        const list = existing.some((e) => e.id === s.id) ? existing : [s, ...existing]
        setSessions(list)
        setSession(s)
        setPersisted((prev) => {
          const next: Persisted = {
            ...prev,
            sessionIds: { ...prev.sessionIds, [role]: s.id },
          }
          savePersisted(next)
          return next
        })

        const history = await listMessages(s.id)
        if (cancelled || token !== bootstrapTokenRef.current) return
        setMessages(history)
      } catch (e) {
        if (cancelled || token !== bootstrapTokenRef.current) return
        setError(e instanceof Error ? e.message : "failed to load chat")
      }
    }

    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [persisted.role])

  const setRole = useCallback((nextRole: Role) => {
    setPersisted((prev) => {
      if (prev.role === nextRole) return prev
      const next = { ...prev, role: nextRole }
      savePersisted(next)
      return next
    })
  }, [])

  const persistSessionForCurrentRole = useCallback((sessionId: string) => {
    setPersisted((prev) => {
      const next: Persisted = {
        ...prev,
        sessionIds: { ...prev.sessionIds, [prev.role]: sessionId },
      }
      savePersisted(next)
      return next
    })
  }, [])

  const newChat = useCallback(async () => {
    if (!user || isStreaming) return
    setError(undefined)
    try {
      const s = await createSession({ user_id: user.id, title: "New chat" })
      setSessions((prev) => [s, ...prev.filter((x) => x.id !== s.id)])
      setSession(s)
      setMessages([])
      persistSessionForCurrentRole(s.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to create chat")
    }
  }, [user, isStreaming, persistSessionForCurrentRole])

  const selectSession = useCallback(
    async (id: string) => {
      if (isStreaming) return
      // Tolerate selecting a session not yet in our list (rare race).
      const target = sessions.find((s) => s.id === id)
      if (!target) {
        setError("session not found")
        return
      }
      setError(undefined)
      setSession(target)
      setMessages([])
      persistSessionForCurrentRole(target.id)
      try {
        const history = await listMessages(target.id)
        setMessages(history)
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to load messages")
      }
    },
    [sessions, isStreaming, persistSessionForCurrentRole],
  )

  const send = useCallback(
    async (content: string) => {
      const trimmed = content.trim()
      if (!trimmed || !session || isStreaming) return
      setError(undefined)

      const now = new Date().toISOString()
      const userMsg: DraftMessage = {
        id: `local-user-${Date.now()}`,
        session_id: session.id,
        role: "user",
        content: trimmed,
        created_at: now,
      }
      const placeholderId = `local-asst-${Date.now()}`
      const placeholder: DraftMessage = {
        id: placeholderId,
        session_id: session.id,
        role: "assistant",
        content: "",
        created_at: now,
        pending: true,
      }

      setMessages((prev) => [...prev, userMsg, placeholder])
      setIsStreaming(true)

      // Trace state lives in a ref so the SSE callbacks can mutate it without
      // re-rendering on every token; we flush it onto the assistant message
      // (a) on each agent_complete and (b) on `done`.
      let trace: AgentTrace = emptyTrace()

      try {
        await streamChat(
          session.id,
          trimmed,
          (token) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === placeholderId ? { ...m, content: m.content + token } : m,
              ),
            )
          },
          (messageId) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === placeholderId
                  ? { ...m, id: messageId, pending: false, trace }
                  : m,
              ),
            )
          },
          undefined,
          undefined,
          (event) => {
            trace = applyAgentEvent(trace, event)
            // Mirror running/complete state into the placeholder live so the
            // stepper updates while the Writer is still streaming.
            const snapshot = trace
            setMessages((prev) =>
              prev.map((m) =>
                m.id === placeholderId ? { ...m, trace: snapshot } : m,
              ),
            )
          },
        )
      } catch (e) {
        const msg = e instanceof Error ? e.message : "chat request failed"
        setError(msg)
        // Drop the empty assistant placeholder so the UI doesn't show an empty bubble.
        setMessages((prev) =>
          prev.filter((m) => !(m.id === placeholderId && m.content === "")),
        )
      } finally {
        setIsStreaming(false)
      }
    },
    [session, isStreaming],
  )

  return {
    user,
    role: persisted.role,
    setRole,
    session,
    sessions,
    currentSessionId: session?.id ?? null,
    messages,
    send,
    newChat,
    selectSession,
    isStreaming,
    error,
  }
}
