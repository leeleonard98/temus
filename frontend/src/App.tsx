import { useState, type JSX } from "react"

import { HealthCard } from "@/features/HealthCard"
import { cn } from "@/lib/utils"

type Feature = { id: string; label: string; render: () => JSX.Element }

const FEATURES: Feature[] = [
  { id: "health", label: "Health", render: () => <HealthCard /> },
  // Tomorrow: copy a FeatureCard, add to this list.
]

export default function App() {
  const [activeId, setActiveId] = useState<string>(FEATURES[0]?.id ?? "")
  const active = FEATURES.find((f) => f.id === activeId) ?? FEATURES[0]

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <h1 className="text-xl font-semibold tracking-tight">Temus</h1>
        </div>
      </header>
      <div className="mx-auto grid max-w-6xl grid-cols-[12rem_1fr] gap-6 px-6 py-6">
        <nav aria-label="features" className="space-y-1">
          {FEATURES.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setActiveId(f.id)}
              className={cn(
                "block w-full rounded-md px-3 py-2 text-left text-sm transition-colors",
                f.id === active?.id
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-accent",
              )}
            >
              {f.label}
            </button>
          ))}
        </nav>
        <main>{active?.render()}</main>
      </div>
    </div>
  )
}
