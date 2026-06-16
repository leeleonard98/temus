import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { act, renderHook, waitFor } from "@testing-library/react"

import { useChat } from "./useChat"

/** Build a Response whose body is a SSE-style stream of pre-encoded chunks. */
function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c))
      controller.close()
    },
  })
  return new Response(stream, { status: 200 })
}

/** Convenience JSON Response. */
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

describe("useChat", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  /** Set up fetch mocks for: upsertUser, listSessions (empty), createSession, listMessages (empty). */
  function primeBootstrap(role: "client" | "advisor" = "client") {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          id: `u-${role}`,
          email: `${role}-demo@aura.test`,
          display_name: role === "client" ? "Demo Client" : "Demo Advisor",
          role,
        }),
      ) // upsertUser
      .mockResolvedValueOnce(jsonResponse([])) // listSessions -> empty
      .mockResolvedValueOnce(
        jsonResponse({
          id: `s-${role}`,
          user_id: `u-${role}`,
          title: "New chat",
          created_at: "now",
        }),
      ) // createSession
      .mockResolvedValueOnce(jsonResponse([])) // listMessages
    return fetchMock
  }

  it("bootstraps user + session on mount and starts with empty messages", async () => {
    primeBootstrap("client")
    const { result } = renderHook(() => useChat())

    await waitFor(() => expect(result.current.user?.id).toBe("u-client"))
    expect(result.current.role).toBe("client")
    expect(result.current.session?.id).toBe("s-client")
    expect(result.current.messages).toEqual([])
    expect(result.current.isStreaming).toBe(false)
  })

  it("send() optimistically appends user message and streams assistant tokens", async () => {
    const fetchMock = primeBootstrap("client")
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'data: {"delta": "Hel"}\n\n',
        'data: {"delta": "lo"}\n\n',
        'data: {"done": true, "message_id": "m1"}\n\n',
      ]),
    )

    const { result } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.session?.id).toBe("s-client"))

    await act(async () => {
      await result.current.send("hi")
    })

    const msgs = result.current.messages
    expect(msgs).toHaveLength(2)
    expect(msgs[0]).toMatchObject({ role: "user", content: "hi" })
    expect(msgs[1]).toMatchObject({ role: "assistant", content: "Hello", id: "m1" })
    expect(result.current.isStreaming).toBe(false)
    expect(result.current.error).toBeUndefined()
  })

  it("setRole switches identity and reloads session", async () => {
    primeBootstrap("client")
    const { result } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.user?.id).toBe("u-client"))

    // Re-prime for advisor bootstrap
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          id: "u-advisor",
          email: "advisor-demo@aura.test",
          display_name: "Demo Advisor",
          role: "advisor",
        }),
      )
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(
        jsonResponse({ id: "s-advisor", user_id: "u-advisor", title: "New chat", created_at: "now" }),
      )
      .mockResolvedValueOnce(jsonResponse([]))

    act(() => result.current.setRole("advisor"))

    await waitFor(() => expect(result.current.user?.id).toBe("u-advisor"))
    expect(result.current.role).toBe("advisor")
    expect(result.current.session?.id).toBe("s-advisor")
  })

  it("surfaces an error when streamChat fails (and does not lose the user message)", async () => {
    const fetchMock = primeBootstrap("client")
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "boom" }, 500))

    const { result } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.session?.id).toBe("s-client"))

    await act(async () => {
      await result.current.send("hi")
    })

    expect(result.current.error).toMatch(/boom/)
    expect(result.current.isStreaming).toBe(false)
    // user message stays so the user can retry
    const userMsgs = result.current.messages.filter((m) => m.role === "user")
    expect(userMsgs).toHaveLength(1)
  })

  it("uses an existing session if listSessions returns one", async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          id: "u-client",
          email: "client-demo@aura.test",
          display_name: "Demo Client",
          role: "client",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse([
          { id: "s-existing", user_id: "u-client", title: "Old", created_at: "t0" },
        ]),
      )
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: "msg-1",
            session_id: "s-existing",
            role: "assistant",
            content: "welcome back",
            created_at: "t1",
          },
        ]),
      )

    const { result } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.session?.id).toBe("s-existing"))
    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0]?.content).toBe("welcome back")
    // Note: createSession should NOT have been called — only 3 fetches.
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it("exposes the list of sessions and the current session id after bootstrap", async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          id: "u-client",
          email: "client-demo@aura.test",
          display_name: "Demo Client",
          role: "client",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse([
          { id: "s-1", user_id: "u-client", title: "Old", created_at: "t0" },
          { id: "s-2", user_id: "u-client", title: "Older", created_at: "t-1" },
        ]),
      )
      .mockResolvedValueOnce(jsonResponse([])) // listMessages

    const { result } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.session?.id).toBe("s-1"))

    expect(result.current.sessions.map((s) => s.id)).toEqual(["s-1", "s-2"])
    expect(result.current.currentSessionId).toBe("s-1")
  })

  it("newChat() creates a fresh session, switches to it, and clears messages", async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          id: "u-client",
          email: "client-demo@aura.test",
          display_name: "Demo Client",
          role: "client",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse([
          { id: "s-1", user_id: "u-client", title: "Old", created_at: "t0" },
        ]),
      )
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: "m-old",
            session_id: "s-1",
            role: "assistant",
            content: "history",
            created_at: "t1",
          },
        ]),
      )

    const { result } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.session?.id).toBe("s-1"))
    expect(result.current.messages).toHaveLength(1)

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        id: "s-new",
        user_id: "u-client",
        title: "New chat",
        created_at: "t2",
      }),
    )

    await act(async () => {
      await result.current.newChat()
    })

    expect(result.current.currentSessionId).toBe("s-new")
    expect(result.current.session?.id).toBe("s-new")
    expect(result.current.messages).toEqual([])
    expect(result.current.sessions[0]?.id).toBe("s-new")
    expect(result.current.sessions.map((s) => s.id)).toContain("s-1")
  })

  it("selectSession() switches to an existing session and reloads its messages", async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          id: "u-client",
          email: "client-demo@aura.test",
          display_name: "Demo Client",
          role: "client",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse([
          { id: "s-1", user_id: "u-client", title: "Now", created_at: "t1" },
          { id: "s-2", user_id: "u-client", title: "Earlier", created_at: "t0" },
        ]),
      )
      .mockResolvedValueOnce(jsonResponse([])) // initial listMessages for s-1

    const { result } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.currentSessionId).toBe("s-1"))

    fetchMock.mockResolvedValueOnce(
      jsonResponse([
        {
          id: "m-2",
          session_id: "s-2",
          role: "assistant",
          content: "old greeting",
          created_at: "t0",
        },
      ]),
    )

    await act(async () => {
      await result.current.selectSession("s-2")
    })

    expect(result.current.currentSessionId).toBe("s-2")
    expect(result.current.session?.id).toBe("s-2")
    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0]?.content).toBe("old greeting")
  })

  it("restores the persisted sessionId for the current role on remount", async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          id: "u-client",
          email: "client-demo@aura.test",
          display_name: "Demo Client",
          role: "client",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse([
          { id: "s-newest", user_id: "u-client", title: "Now", created_at: "t2" },
          { id: "s-pinned", user_id: "u-client", title: "Earlier", created_at: "t1" },
        ]),
      )
      .mockResolvedValueOnce(jsonResponse([]))

    const { result, unmount } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.currentSessionId).toBe("s-newest"))

    fetchMock.mockResolvedValueOnce(
      jsonResponse([
        {
          id: "m-pinned",
          session_id: "s-pinned",
          role: "assistant",
          content: "pinned chat",
          created_at: "t1",
        },
      ]),
    )

    await act(async () => {
      await result.current.selectSession("s-pinned")
    })
    expect(result.current.currentSessionId).toBe("s-pinned")

    unmount()

    // Remount: localStorage should drive us back to s-pinned, not s-newest.
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          id: "u-client",
          email: "client-demo@aura.test",
          display_name: "Demo Client",
          role: "client",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse([
          { id: "s-newest", user_id: "u-client", title: "Now", created_at: "t2" },
          { id: "s-pinned", user_id: "u-client", title: "Earlier", created_at: "t1" },
        ]),
      )
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: "m-pinned",
            session_id: "s-pinned",
            role: "assistant",
            content: "pinned chat",
            created_at: "t1",
          },
        ]),
      )

    const { result: result2 } = renderHook(() => useChat())
    await waitFor(() => expect(result2.current.currentSessionId).toBe("s-pinned"))
    expect(result2.current.session?.id).toBe("s-pinned")
    expect(result2.current.messages[0]?.content).toBe("pinned chat")
  })

  it("isStreaming flips true during send and false after", async () => {
    const fetchMock = primeBootstrap("client")

    // Build a manually-controlled stream so we can observe the in-flight state.
    let push: ((s: string) => void) | undefined
    let close: (() => void) | undefined
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        push = (s) => controller.enqueue(encoder.encode(s))
        close = () => controller.close()
      },
    })
    fetchMock.mockResolvedValueOnce(new Response(stream, { status: 200 }))

    const { result } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.session?.id).toBe("s-client"))

    let sendPromise: Promise<void> | undefined
    act(() => {
      sendPromise = result.current.send("hi")
    })

    await waitFor(() => expect(result.current.isStreaming).toBe(true))

    await act(async () => {
      push!('data: {"delta": "ok"}\n\ndata: {"done": true, "message_id": "m"}\n\n')
      close!()
      await sendPromise
    })

    expect(result.current.isStreaming).toBe(false)
  })
})
