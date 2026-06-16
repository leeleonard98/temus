import { useEffect, useState } from "react"

import { cn } from "@/lib/utils"
import { api } from "@/lib/api"

type HealthResponse = { status: string; db: string }

/**
 * Tiny corner indicator for backend liveness. Replaces the full HealthCard
 * panel now that the chat is the main view.
 */
export function HealthBadge() {
  const [state, setState] = useState<"loading" | "ok" | "down">("loading")

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const res = await api<HealthResponse>("/api/v1/health")
      if (cancelled) return
      setState(res.ok && res.data.status === "ok" ? "ok" : "down")
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const label =
    state === "loading" ? "Backend: checking…" : state === "ok" ? "Backend health: OK" : "Backend down"
  const dot =
    state === "loading"
      ? "bg-muted-foreground/40"
      : state === "ok"
        ? "bg-emerald-500"
        : "bg-destructive"

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border bg-background/80 px-2.5 py-1 text-xs text-muted-foreground shadow-sm backdrop-blur",
      )}
      title={label}
    >
      <span className={cn("inline-block h-2 w-2 rounded-full", dot)} aria-hidden />
      <span>{label}</span>
    </div>
  )
}
