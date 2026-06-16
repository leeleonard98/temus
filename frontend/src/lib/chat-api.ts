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
 * Stream a chat completion. Calls `onDelta` for each token, `onDone` once
 * the server signals completion (with the persisted assistant message id).
 *
 * Parses raw SSE frames: `data: <json>\n\n`. We do not depend on an SSE
 * library because POST + EventSource is a pain; raw fetch streaming is fine.
 */
export async function streamChat(
  sessionId: string,
  content: string,
  onDelta: (token: string) => void,
  onDone: (messageId: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ session_id: sessionId, content }),
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
      handleFrame(frame, onDelta, onDone)
      sepIdx = buffer.indexOf("\n\n")
    }
  }
  // Flush any trailing frame without terminator.
  const tail = buffer.trim()
  if (tail) handleFrame(tail, onDelta, onDone)
}

function handleFrame(
  frame: string,
  onDelta: (token: string) => void,
  onDone: (messageId: string) => void,
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
    if (typeof obj.delta === "string") {
      onDelta(obj.delta)
    }
    if (obj.done === true && typeof obj.message_id === "string") {
      onDone(obj.message_id)
    }
  }
}
