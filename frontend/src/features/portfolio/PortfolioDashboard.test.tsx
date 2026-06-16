import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { PortfolioDashboard } from "./PortfolioDashboard"

function fakeFetch(handlers: Record<string, () => Response | Promise<Response>>) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), "http://test").pathname +
      new URL(String(input), "http://test").search
    for (const k of Object.keys(handlers)) {
      if (path.startsWith(k)) return handlers[k]()
    }
    // Default: empty SSE stream so PriceTicker mounts cleanly.
    return new Response(new ReadableStream({ start: (c) => c.close() }), { status: 200 })
  })
}

const portfolioFixture = {
  user_id: "u1",
  accounts: [
    {
      id: "a1",
      name: "Joint Brokerage",
      kind: "brokerage",
      positions: [
        {
          symbol: "AAPL",
          quantity: "10",
          avg_cost: "100",
          last_price: "200",
          market_value: "2000.00",
          asset_class: "equity",
        },
      ],
    },
  ],
  totals: {
    market_value: "2000.00",
    cost_basis: "1000.00",
    unrealized_pl: "1000.00",
    unrealized_pl_pct: 100,
  },
  allocation: [{ asset_class: "equity", weight: 1.0 }],
}

describe("PortfolioDashboard", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      fakeFetch({
        "/api/v1/users": async () =>
          new Response(
            JSON.stringify({ id: "u1", email: "x@y", display_name: "X", role: "client" }),
            { status: 200 },
          ),
        "/api/v1/portfolio": async () =>
          new Response(JSON.stringify(portfolioFixture), { status: 200 }),
        "/api/v1/goals": async () =>
          new Response(
            JSON.stringify([
              {
                id: "g1",
                user_id: "u1",
                name: "Retirement",
                target_amount: "1000000",
                target_date: "2055-01-01",
                current_amount: "100000",
                created_at: "2026-01-01T00:00:00Z",
              },
            ]),
            { status: 200 },
          ),
        "/api/v1/risk": async () =>
          new Response(
            JSON.stringify({
              user_id: "u1",
              score: 70,
              label: "aggressive",
              drivers: ["AAPL (equity) — 70.0 pts"],
            }),
            { status: 200 },
          ),
      }),
    )
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("renders KPIs and account table after data loads", async () => {
    render(<PortfolioDashboard />)
    await waitFor(() =>
      expect(screen.getByTestId("portfolio-dashboard")).toBeInTheDocument(),
    )
    // KPI shows formatted total market value.
    expect(screen.getByTestId("kpi-market-value")).toHaveTextContent(/\$2,000\.00/)
    // AAPL appears in the price ticker AND the positions table.
    expect(screen.getAllByText(/AAPL/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/Retirement/)).toBeInTheDocument()
    expect(screen.getByText(/aggressive/i)).toBeInTheDocument()
  })

  it("invokes onUiContextChange with the loaded portfolio snapshot", async () => {
    const onUi = vi.fn()
    render(<PortfolioDashboard onUiContextChange={onUi} />)
    await waitFor(() => expect(onUi).toHaveBeenCalled())
    const ctx = onUi.mock.calls.at(-1)![0] as Record<string, unknown>
    expect(ctx.market_value).toBe(2000)
    expect((ctx.top_positions as Array<{ symbol: string }>)[0].symbol).toBe("AAPL")
  })
})
