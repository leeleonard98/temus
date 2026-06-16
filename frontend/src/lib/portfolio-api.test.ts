import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  getPortfolio,
  getRisk,
  listClients,
  listGoals,
  streamPrices,
} from "./portfolio-api"

function streamFrom(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder()
  return new ReadableStream({
    start(c) {
      for (const ch of chunks) c.enqueue(enc.encode(ch))
      c.close()
    },
  })
}

describe("portfolio-api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("getPortfolio fetches /portfolio with user_id", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          user_id: "u1",
          accounts: [],
          totals: {
            market_value: "0",
            cost_basis: "0",
            unrealized_pl: "0",
            unrealized_pl_pct: 0,
          },
          allocation: [],
        }),
        { status: 200 },
      ),
    )
    const p = await getPortfolio("u1")
    expect(p.user_id).toBe("u1")
    const [url] = vi.mocked(fetch).mock.calls[0]!
    expect(String(url)).toContain("user_id=u1")
  })

  it("listGoals returns the JSON list", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify([{ id: "g1", name: "House" }]), { status: 200 }),
    )
    const goals = await listGoals("u1")
    expect(goals).toHaveLength(1)
  })

  it("getRisk returns the risk assessment", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          user_id: "u1",
          score: 55,
          label: "moderate",
          drivers: ["VOO (equity) — 21.0 pts"],
        }),
        { status: 200 },
      ),
    )
    const r = await getRisk("u1")
    expect(r.label).toBe("moderate")
    expect(r.score).toBe(55)
  })

  it("listClients hits /clients", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
    await listClients()
    const [url] = vi.mocked(fetch).mock.calls[0]!
    expect(String(url)).toMatch(/\/clients$/)
  })

  it("streamPrices parses SSE frames and invokes onTick", async () => {
    const body = streamFrom([
      'data: {"symbol":"AAPL","price":192.5,"ts":"2026-06-16T00:00:00Z"}\n\n',
      'data: {"symbol":"AAPL","price":193.0,"ts":"2026-06-16T00:00:01Z"}\n\n',
    ])
    vi.mocked(fetch).mockResolvedValueOnce(new Response(body, { status: 200 }))

    const ticks: number[] = []
    const stop = streamPrices(["AAPL"], (t) => ticks.push(t.price))
    // Wait for the stream to drain — micro-task tick.
    await new Promise((r) => setTimeout(r, 50))
    stop()
    expect(ticks).toEqual([192.5, 193.0])
  })
})
