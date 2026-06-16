import { useEffect, useState } from "react"
import { TrendingDown, TrendingUp } from "lucide-react"

import { streamPrices, type PriceTick } from "@/lib/portfolio-api"
import { cn } from "@/lib/utils"

type Props = {
  symbols?: string[]
  intervalMs?: number
  /** Optional callback so parents (e.g. dashboard) can derive day-change. */
  onTick?: (tick: PriceTick) => void
}

const DEFAULT_SYMBOLS = ["AAPL", "MSFT", "NVDA", "VOO", "BND"]

type TickerState = Record<
  string,
  { price: number; prevPrice: number | null; ts: string }
>

/**
 * Live price ticker. Connects to /api/v1/prices/stream and renders a
 * horizontal strip of symbols + last prices, with a tiny up/down arrow
 * derived from the previous tick.
 */
export function PriceTicker({ symbols = DEFAULT_SYMBOLS, intervalMs = 500, onTick }: Props) {
  const [state, setState] = useState<TickerState>({})

  useEffect(() => {
    const stop = streamPrices(
      symbols,
      (tick) => {
        setState((prev) => {
          const last = prev[tick.symbol]?.price ?? null
          return {
            ...prev,
            [tick.symbol]: { price: tick.price, prevPrice: last, ts: tick.ts },
          }
        })
        onTick?.(tick)
      },
      { intervalMs },
    )
    return stop
    // Re-subscribe if the symbol set changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbols.join(",")])

  return (
    <div
      data-testid="price-ticker"
      className="flex items-center gap-6 overflow-x-auto rounded-md border bg-muted/40 px-4 py-2 text-sm"
    >
      {symbols.map((sym) => {
        const t = state[sym]
        const dir =
          t && t.prevPrice != null
            ? t.price > t.prevPrice
              ? "up"
              : t.price < t.prevPrice
                ? "down"
                : "flat"
            : "flat"
        return (
          <div key={sym} className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs font-semibold uppercase text-muted-foreground">{sym}</span>
            <span className="font-mono tabular-nums">
              {t ? t.price.toFixed(2) : "—"}
            </span>
            {dir === "up" && <TrendingUp className="h-3.5 w-3.5 text-emerald-600" />}
            {dir === "down" && <TrendingDown className="h-3.5 w-3.5 text-red-600" />}
            <span
              className={cn(
                "inline-block h-1.5 w-1.5 rounded-full",
                dir === "up"
                  ? "bg-emerald-500"
                  : dir === "down"
                    ? "bg-red-500"
                    : "bg-slate-400",
              )}
            />
          </div>
        )
      })}
    </div>
  )
}
