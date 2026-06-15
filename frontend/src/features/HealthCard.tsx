import { useEffect, useState } from "react"

import { FeatureCard, type FeatureState } from "@/components/FeatureCard"
import { api } from "@/lib/api"

type HealthResponse = { status: string; db: string }

export function HealthCard() {
  const [state, setState] = useState<FeatureState>("idle")
  const [data, setData] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | undefined>()

  useEffect(() => {
    let cancelled = false
    async function run() {
      setState("loading")
      const res = await api<HealthResponse>("/api/v1/health")
      if (cancelled) return
      if (res.ok) {
        setData(res.data)
        setState("success")
      } else {
        setError(res.error)
        setState("error")
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <FeatureCard
      title="Health"
      description="Backend liveness + DB connectivity probe."
      state={state}
      errorMessage={error}
      result={
        data ? (
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-muted-foreground">status</dt>
            <dd className="font-medium">{data.status}</dd>
            <dt className="text-muted-foreground">db</dt>
            <dd className="font-medium">{data.db}</dd>
          </dl>
        ) : null
      }
    />
  )
}
