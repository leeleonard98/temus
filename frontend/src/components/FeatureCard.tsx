import { type ReactNode } from "react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ErrorBoundary } from "@/components/ErrorBoundary"

export type FeatureState = "idle" | "loading" | "success" | "error"

type Props = {
  title: string
  description?: string
  state: FeatureState
  errorMessage?: string
  form?: ReactNode
  result?: ReactNode
}

/**
 * One layout, one pattern for every feature in the demo.
 *
 * Renders a card with optional form on top and a result region below
 * that switches on `state`. Wrapped in an ErrorBoundary so a thrown
 * render-time error in one feature does not blank the whole app.
 */
export function FeatureCard({
  title,
  description,
  state,
  errorMessage,
  form,
  result,
}: Props) {
  return (
    <ErrorBoundary>
      <Card className="w-full">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          {description ? <CardDescription>{description}</CardDescription> : null}
        </CardHeader>
        <CardContent className="space-y-4">
          {form}
          <div aria-live="polite">
            {state === "idle" && (
              <p className="text-sm text-muted-foreground">No data yet.</p>
            )}
            {state === "loading" && (
              <div className="space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
              </div>
            )}
            {state === "success" && result}
            {state === "error" && (
              <div className="rounded-md border border-destructive/50 bg-destructive/5 p-3 text-sm text-destructive">
                {errorMessage ?? "Request failed."}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </ErrorBoundary>
  )
}
