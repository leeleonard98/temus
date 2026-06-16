import { useEffect, useState } from "react"
import { ArrowDownRight, ArrowUpRight, ShieldCheck, Target, Wallet } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import {
  getPortfolio,
  getRisk,
  listGoals,
  type Goal,
  type Portfolio,
  type PriceTick,
  type RiskAssessment,
} from "@/lib/portfolio-api"
import { upsertUser, type Role } from "@/lib/chat-api"

import { AllocationChart } from "./AllocationChart"
import { PriceTicker } from "./PriceTicker"

const SEED_BY_ROLE: Record<Role, { email: string; display_name: string }> = {
  client: { email: "client-demo@aura.test", display_name: "Demo Client" },
  advisor: { email: "advisor-demo@aura.test", display_name: "Demo Advisor" },
}

function formatMoney(value: string | number, opts: { compact?: boolean } = {}): string {
  const n = typeof value === "string" ? Number(value) : value
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: opts.compact ? "compact" : "standard",
    maximumFractionDigits: 2,
  }).format(n)
}

type Props = {
  /** Defaults to client; advisors can pass "advisor". */
  role?: Role
  /** Expose a UI-state snapshot to a parent (drives AC4 chat grounding). */
  onUiContextChange?: (ctx: object) => void
}

/**
 * Portfolio dashboard — KPIs, allocation, accounts, goals, risk.
 *
 * Bootstraps the seeded demo user (matching `seed_demo.py`) on first render
 * and pulls the four supporting endpoints in parallel.
 */
export function PortfolioDashboard({ role = "client", onUiContextChange }: Props) {
  const [userId, setUserId] = useState<string | null>(null)
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [goals, setGoals] = useState<Goal[]>([])
  const [risk, setRisk] = useState<RiskAssessment | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [livePrice, setLivePrice] = useState<Record<string, number>>({})

  // 1. Resolve user id (idempotent upsert of the seeded demo identity).
  useEffect(() => {
    let cancelled = false
    async function bootstrap() {
      try {
        const u = await upsertUser({ ...SEED_BY_ROLE[role], role })
        if (!cancelled) setUserId(u.id)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "failed to load user")
      }
    }
    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [role])

  // 2. Fetch portfolio / goals / risk in parallel once we have the user id.
  useEffect(() => {
    if (!userId) return
    let cancelled = false
    async function load() {
      try {
        const [p, g, r] = await Promise.all([
          getPortfolio(userId!),
          listGoals(userId!),
          getRisk(userId!),
        ])
        if (cancelled) return
        setPortfolio(p)
        setGoals(g)
        setRisk(r)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "failed to load portfolio")
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [userId])

  // 3. Whenever the portfolio refreshes, hand a UI-state snapshot up to the
  //    parent so the chat drawer can ground questions like "what's my AAPL %?"
  useEffect(() => {
    if (!portfolio || !onUiContextChange) return
    onUiContextChange({
      market_value: Number(portfolio.totals.market_value),
      unrealized_pl: Number(portfolio.totals.unrealized_pl),
      unrealized_pl_pct: portfolio.totals.unrealized_pl_pct,
      allocation: portfolio.allocation,
      top_positions: portfolio.accounts
        .flatMap((a) => a.positions.map((p) => ({
          symbol: p.symbol,
          market_value: Number(p.market_value),
          asset_class: p.asset_class,
        })))
        .sort((a, b) => b.market_value - a.market_value)
        .slice(0, 5),
    })
  }, [portfolio, onUiContextChange])

  if (error) {
    return (
      <div className="rounded-md bg-destructive/10 p-4 text-sm text-destructive">
        {error}
      </div>
    )
  }

  if (!portfolio || !risk) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-12 w-full" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  // Day-change is approximated from the live ticker: compare live price to the
  // first observed live price (since component mount). Phase 3 will replace
  // this with an open-of-day price.
  const liveSymbols = ["AAPL", "MSFT", "NVDA", "VOO", "BND"]
  const liveDeltaUsd = portfolio.accounts
    .flatMap((a) => a.positions)
    .reduce((acc, p) => {
      const live = livePrice[p.symbol]
      if (live == null) return acc
      const last = Number(p.last_price)
      return acc + (live - last) * Number(p.quantity)
    }, 0)

  const pl = Number(portfolio.totals.unrealized_pl)
  const plPositive = pl >= 0

  return (
    <div className="space-y-6" data-testid="portfolio-dashboard">
      <PriceTicker
        symbols={liveSymbols}
        onTick={(t: PriceTick) =>
          setLivePrice((prev) => ({ ...prev, [t.symbol]: t.price }))
        }
      />

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1.5">
              <Wallet className="h-3.5 w-3.5" /> Total market value
            </CardDescription>
            <CardTitle data-testid="kpi-market-value">
              {formatMoney(portfolio.totals.market_value)}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Cost basis {formatMoney(portfolio.totals.cost_basis)}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1.5">
              {plPositive ? (
                <ArrowUpRight className="h-3.5 w-3.5 text-emerald-600" />
              ) : (
                <ArrowDownRight className="h-3.5 w-3.5 text-red-600" />
              )}
              Unrealized P/L
            </CardDescription>
            <CardTitle
              className={cn(plPositive ? "text-emerald-700" : "text-red-700")}
            >
              {formatMoney(pl)} ({portfolio.totals.unrealized_pl_pct.toFixed(2)}%)
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Live since open: {liveDeltaUsd >= 0 ? "+" : ""}
            {formatMoney(liveDeltaUsd)}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5" /> Risk score
            </CardDescription>
            <CardTitle>
              {risk.score}{" "}
              <span className="text-base font-medium capitalize text-muted-foreground">
                {risk.label}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-xs text-muted-foreground">
              {risk.drivers.map((d, i) => (
                <li key={i}>• {d}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      {/* Allocation + goals */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Asset allocation</CardTitle>
          </CardHeader>
          <CardContent>
            <AllocationChart allocation={portfolio.allocation} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-1.5">
              <Target className="h-4 w-4" /> Goals
            </CardTitle>
          </CardHeader>
          <CardContent>
            {goals.length === 0 ? (
              <p className="text-sm text-muted-foreground">No goals set yet.</p>
            ) : (
              <ul className="space-y-3">
                {goals.map((g) => {
                  const pct = Math.min(
                    100,
                    Math.round(
                      (Number(g.current_amount) / Number(g.target_amount)) * 100,
                    ),
                  )
                  return (
                    <li key={g.id}>
                      <div className="mb-1 flex items-center justify-between text-sm">
                        <span className="font-medium">{g.name}</span>
                        <span className="text-muted-foreground">
                          {formatMoney(g.current_amount, { compact: true })} /{" "}
                          {formatMoney(g.target_amount, { compact: true })}
                        </span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-emerald-500"
                          style={{ width: `${pct}%` }}
                          data-testid={`goal-bar-${g.id}`}
                        />
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        Target {g.target_date} · {pct}%
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Accounts */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Accounts</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {portfolio.accounts.map((acct) => (
            <div key={acct.id}>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold">{acct.name}</h3>
                <span className="text-xs uppercase text-muted-foreground">
                  {acct.kind}
                </span>
              </div>
              <table className="w-full text-sm">
                <thead className="text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="pb-1 text-left">Symbol</th>
                    <th className="pb-1 text-right">Qty</th>
                    <th className="pb-1 text-right">Avg cost</th>
                    <th className="pb-1 text-right">Last</th>
                    <th className="pb-1 text-right">Mkt value</th>
                    <th className="pb-1 text-right">Class</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {acct.positions.map((p) => (
                    <tr key={`${acct.id}-${p.symbol}`} className="font-mono tabular-nums">
                      <td className="py-1.5 font-sans font-medium">{p.symbol}</td>
                      <td className="py-1.5 text-right">{Number(p.quantity).toLocaleString()}</td>
                      <td className="py-1.5 text-right">{formatMoney(p.avg_cost)}</td>
                      <td className="py-1.5 text-right">{formatMoney(p.last_price)}</td>
                      <td className="py-1.5 text-right">{formatMoney(p.market_value)}</td>
                      <td className="py-1.5 text-right font-sans capitalize text-muted-foreground">
                        {p.asset_class}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
