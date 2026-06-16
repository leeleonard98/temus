import { describe, expect, it, vi, beforeEach, afterEach } from "vitest"

import { streamChat, upsertUser, createSession, listSessions, listMessages } from "./chat-api"

/** Build a ReadableStream that emits the given chunks (as strings). */
function streamFrom(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c))
      controller.close()
    },
  })
}

describe("chat-api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  describe("upsertUser", () => {
    it("POSTs to /users and returns the user", async () => {
      const fetchMock = vi.mocked(fetch)
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "u1", email: "a@b.c", display_name: "A", role: "client" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      )

      const user = await upsertUser({ email: "a@b.c", display_name: "A", role: "client" })

      expect(user).toEqual({ id: "u1", email: "a@b.c", display_name: "A", role: "client" })
      expect(fetchMock).toHaveBeenCalledOnce()
      const [, init] = fetchMock.mock.calls[0]!
      expect(init?.method).toBe("POST")
    })

    it("throws on non-2xx", async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "boom" }), { status: 500 }),
      )
      await expect(upsertUser({ email: "x", display_name: "x", role: "client" })).rejects.toThrow(/boom/)
    })
  })

  describe("createSession / listSessions / listMessages", () => {
    it("createSession POSTs and returns session", async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "s1", user_id: "u1", title: "t", created_at: "now" }), {
          status: 200,
        }),
      )
      const s = await createSession({ user_id: "u1", title: "t" })
      expect(s.id).toBe("s1")
    })

    it("listSessions GETs with user_id query param", async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      await listSessions("u1")
      const [url] = vi.mocked(fetch).mock.calls[0]!
      expect(String(url)).toContain("user_id=u1")
    })

    it("listMessages GETs the session-scoped path", async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      await listMessages("s1")
      const [url] = vi.mocked(fetch).mock.calls[0]!
      expect(String(url)).toContain("/sessions/s1/messages")
    })
  })

  describe("streamChat", () => {
    it("parses SSE deltas and signals done with message_id", async () => {
      const body = streamFrom([
        'data: {"delta": "Hel"}\n\n',
        'data: {"delta": "lo"}\n\n',
        'data: {"done": true, "message_id": "m1"}\n\n',
      ])
      vi.mocked(fetch).mockResolvedValueOnce(new Response(body, { status: 200 }))

      const deltas: string[] = []
      const onDelta = vi.fn((t: string) => deltas.push(t))
      const onDone = vi.fn()

      await streamChat("s1", "hi", onDelta, onDone)

      expect(deltas.join("")).toBe("Hello")
      expect(onDone).toHaveBeenCalledWith("m1")
    })

    it("handles split frames across chunks", async () => {
      const body = streamFrom([
        'data: {"del',
        'ta": "ab"}\n',
        '\ndata: {"delta": "cd"}\n\n',
        'data: {"done": true, "message_id": "m2"}\n\n',
      ])
      vi.mocked(fetch).mockResolvedValueOnce(new Response(body, { status: 200 }))

      const deltas: string[] = []
      await streamChat("s", "x", (t) => deltas.push(t), () => {})
      expect(deltas.join("")).toBe("abcd")
    })

    it("rejects when response is not ok", async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "nope" }), { status: 400 }),
      )
      await expect(streamChat("s", "x", () => {}, () => {})).rejects.toThrow(/nope/)
    })
  })
})
