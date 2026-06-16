/**
 * Chat API client.
 *
 * Talks to the AuraWealth backend. Throws on non-2xx so callers can surface
 * errors via try/catch — keeps the streaming path tidy.
 */

export type Role = "client" | "advisor"
export type MessageRole = "user" | "assistant" | "system"

export type User = {
  id: string
  email: string
  display_name: string
  role: Role
}

export type Session = {
  id: string
  user_id: string
  title: string | null
  created_at: string
  updated_at?: string
}

export type Message = {
  id: string
  session_id: string
  role: MessageRole
  content: string
  created_at: string
}

/** Agent stage names emitted by the sequential pipeline. */
export type AgentName = "researcher" | "analyst" | "writer"

/** Trace events emitted alongside the final-answer deltas. */
export type AgentEvent =
  | { type: "agent_start"; agent: AgentName }
  | { type: "agent_delta"; agent: AgentName; content: string }
  | { type: "agent_complete"; agent: AgentName; output: Record<string, unknown> }

const API_BASE: string =
  (import.meta.env?.VITE_API_BASE_URL as string | undefined) ?? "/api/v1"

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  })
  const text = await res.text()
  const parsed = text ? safeJson(text) : undefined
  if (!res.ok) {
    const detail =
      parsed && typeof parsed === "object" && parsed !== null && "detail" in parsed
        ? String((parsed as Record<string, unknown>).detail)
        : `HTTP ${res.status}`
    throw new Error(detail)
  }
  return parsed as T
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export function upsertUser(input: { email: string; display_name: string; role: Role }): Promise<User> {
  return jsonRequest<User>("/users", {
    method: "POST",
    body: JSON.stringify(input),
  })
}

export function createSession(input: { user_id: string; title?: string }): Promise<Session> {
  return jsonRequest<Session>("/sessions", {
    method: "POST",
    body: JSON.stringify(input),
  })
}

export function listSessions(userId: string): Promise<Session[]> {
  return jsonRequest<Session[]>(`/sessions?user_id=${encodeURIComponent(userId)}`)
}

export function listMessages(sessionId: string): Promise<Message[]> {
  return jsonRequest<Message[]>(`/sessions/${encodeURIComponent(sessionId)}/messages`)
}

/**
 * Stream a chat completion.
 *
 * The backend runs a sequential 3-agent pipeline (Researcher -> Analyst ->
 * Writer). The Writer's tokens are the user-facing answer and arrive as
 * `{type:"delta", content:"..."}` frames. Researcher / Analyst emit
 * `agent_start` / `agent_delta` / `agent_complete` frames the UI renders as
 * a "Show reasoning" disclosure (consumed via `onAgentEvent`).
 *
 * For backwards compatibility we also accept the legacy `{delta:"..."}`
 * shape (no `type` field) and route those to `onDelta`.
 *
 * Parses raw SSE frames: `data: <json>\n\n`. We don't depend on an SSE
 * library because POST + EventSource is a pain; raw fetch streaming is fine.
 */
export async function streamChat(
  sessionId: string,
  content: string,
  onDelta: (token: string) => void,
  onDone: (messageId: string) => void,
  signal?: AbortSignal,
  uiContext?: object,
  onAgentEvent?: (event: AgentEvent) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      session_id: sessionId,
      content,
      ...(uiContext ? { ui_context: uiContext } : {}),
    }),
    signal,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => "")
    const parsed = text ? safeJson(text) : undefined
    const detail =
      parsed && typeof parsed === "object" && parsed !== null && "detail" in parsed
        ? String((parsed as Record<string, unknown>).detail)
        : `HTTP ${res.status}`
    throw new Error(detail)
  }
  if (!res.body) throw new Error("response has no body")

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  // SSE frames are separated by a blank line ("\n\n").
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let sepIdx = buffer.indexOf("\n\n")
    while (sepIdx !== -1) {
      const frame = buffer.slice(0, sepIdx)
      buffer = buffer.slice(sepIdx + 2)
      handleFrame(frame, onDelta, onDone, onAgentEvent)
      sepIdx = buffer.indexOf("\n\n")
    }
  }
  // Flush any trailing frame without terminator.
  const tail = buffer.trim()
  if (tail) handleFrame(tail, onDelta, onDone, onAgentEvent)
}

function isAgent(value: unknown): value is AgentName {
  return value === "researcher" || value === "analyst" || value === "writer"
}

function handleFrame(
  frame: string,
  onDelta: (token: string) => void,
  onDone: (messageId: string) => void,
  onAgentEvent?: (event: AgentEvent) => void,
): void {
  // A frame may have multiple lines; we only care about `data:` lines.
  const lines = frame.split("\n")
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed.startsWith("data:")) continue
    const payload = trimmed.slice(5).trim()
    if (!payload) continue
    let parsed: unknown
    try {
      parsed = JSON.parse(payload)
    } catch {
      continue
    }
    if (typeof parsed !== "object" || parsed === null) continue
    const obj = parsed as Record<string, unknown>

    const type = typeof obj.type === "string" ? obj.type : undefined

    // New typed schema:
    //   {"type":"delta","content":"..."}            <- user-facing token
    //   {"type":"done","message_id":"..."}          <- final marker
    //   {"type":"error","error":"..."}              <- streaming error
    //   {"type":"agent_start","agent":"..."}        <- trace start
    //   {"type":"agent_delta","agent":"...","content":"..."} <- internal token
    //   {"type":"agent_complete","agent":"...","output":{...}} <- trace done
    if (type === "delta" && typeof obj.content === "string") {
      onDelta(obj.content)
      continue
    }
    if (type === "done" && typeof obj.message_id === "string") {
      onDone(obj.message_id)
      continue
    }
    if (type === "error" && typeof obj.error === "string") {
      throw new Error(obj.error)
    }
    if (type === "agent_start" && isAgent(obj.agent)) {
      onAgentEvent?.({ type: "agent_start", agent: obj.agent })
      continue
    }
    if (
      type === "agent_delta" &&
      isAgent(obj.agent) &&
      typeof obj.content === "string"
    ) {
      onAgentEvent?.({ type: "agent_delta", agent: obj.agent, content: obj.content })
      continue
    }
    if (type === "agent_complete" && isAgent(obj.agent)) {
      const output =
        typeof obj.output === "object" && obj.output !== null
          ? (obj.output as Record<string, unknown>)
          : {}
      onAgentEvent?.({ type: "agent_complete", agent: obj.agent, output })
      continue
    }

    // Backwards-compat: legacy shape with no `type` field — treat as delta/done.
    if (type === undefined) {
      if (typeof obj.delta === "string") {
        onDelta(obj.delta)
      }
      if (obj.done === true && typeof obj.message_id === "string") {
        onDone(obj.message_id)
      }
    }
  }
}
