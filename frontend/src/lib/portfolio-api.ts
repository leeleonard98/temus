/**
 * Portfolio API client — typed wrappers for /portfolio, /goals, /risk, /clients,
 * and a tiny SSE consumer for /prices/stream.
 *
 * Mirrors the style of `chat-api.ts`. Throws on non-2xx so callers can use
 * try/catch.
 */

const API_BASE: string =
  (import.meta.env?.VITE_API_BASE_URL as string | undefined) ?? "/api/v1"

export type AssetClass = "equity" | "bond" | "cash" | "crypto" | "alt"
export type AccountKind = "cash" | "brokerage" | "retirement" | "crypto"
export type RiskLabel = "conservative" | "moderate" | "aggressive"

export type Position = {
  symbol: string
  quantity: string
  avg_cost: string
  last_price: string
  market_value: string
  asset_class: AssetClass
}

export type Account = {
  id: string
  name: string
  kind: AccountKind
  positions: Position[]
}

export type PortfolioTotals = {
  market_value: string
  cost_basis: string
  unrealized_pl: string
  unrealized_pl_pct: number
}

export type AllocationSlice = {
  asset_class: AssetClass
  weight: number
}

export type Portfolio = {
  user_id: string
  accounts: Account[]
  totals: PortfolioTotals
  allocation: AllocationSlice[]
}

export type Goal = {
  id: string
  user_id: string
  name: string
  target_amount: string
  target_date: string
  current_amount: string
  created_at: string
}

export type RiskAssessment = {
  user_id: string
  score: number
  label: RiskLabel
  drivers: string[]
}

export type ClientSummary = {
  id: string
  email: string
  display_name: string
  market_value: string
  account_count: number
}

export type PriceTick = {
  symbol: string
  price: number
  ts: string
}

async function jget<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const getPortfolio = (userId: string): Promise<Portfolio> =>
  jget<Portfolio>(`/portfolio?user_id=${encodeURIComponent(userId)}`)

export const listGoals = (userId: string): Promise<Goal[]> =>
  jget<Goal[]>(`/goals?user_id=${encodeURIComponent(userId)}`)

export const getRisk = (userId: string): Promise<RiskAssessment> =>
  jget<RiskAssessment>(`/risk?user_id=${encodeURIComponent(userId)}`)

export const listClients = (): Promise<ClientSummary[]> =>
  jget<ClientSummary[]>("/clients")

/**
 * Open an SSE connection to /prices/stream and call `onTick` for each frame.
 * Returns an abort function. The `signal` arg is also accepted for parity
 * with `streamChat`.
 */
export function streamPrices(
  symbols: string[],
  onTick: (tick: PriceTick) => void,
  opts: { intervalMs?: number; signal?: AbortSignal } = {},
): () => void {
  const controller = new AbortController()
  if (opts.signal) {
    opts.signal.addEventListener("abort", () => controller.abort())
  }
  const params = new URLSearchParams({
    symbols: symbols.join(","),
    interval_ms: String(opts.intervalMs ?? 500),
  })
  const url = `${API_BASE}/prices/stream?${params.toString()}`

  // Fire-and-forget: caller cancels via the returned function.
  void (async () => {
    try {
      const res = await fetch(url, { signal: controller.signal })
      if (!res.ok || !res.body) return
      const reader = res.body.getReader()
      const dec = new TextDecoder()
      let buf = ""
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        let idx = buf.indexOf("\n\n")
        while (idx !== -1) {
          const frame = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          for (const line of frame.split("\n")) {
            const t = line.trim()
            if (!t.startsWith("data:")) continue
            try {
              onTick(JSON.parse(t.slice(5).trim()) as PriceTick)
            } catch {
              /* ignore malformed frames */
            }
          }
          idx = buf.indexOf("\n\n")
        }
      }
    } catch {
      /* aborted or network error — caller surfaces as needed */
    }
  })()

  return () => controller.abort()
}
