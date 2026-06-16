import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { Role } from "@/lib/chat-api"

type Props = {
  role: Role
  onChange: (role: Role) => void
  disabled?: boolean
}

const OPTIONS: ReadonlyArray<{ value: Role; label: string }> = [
  { value: "client", label: "Client" },
  { value: "advisor", label: "Advisor" },
]

/**
 * Segmented control for switching between client/advisor demo personas.
 * Uses shadcn Button primitives so it inherits focus/hover states.
 */
export function RoleSwitcher({ role, onChange, disabled }: Props) {
  return (
    <div
      role="group"
      aria-label="Switch role"
      className="inline-flex items-center rounded-md border bg-background p-0.5"
    >
      {OPTIONS.map((opt) => {
        const active = opt.value === role
        return (
          <Button
            key={opt.value}
            type="button"
            size="sm"
            variant={active ? "default" : "ghost"}
            disabled={disabled}
            aria-pressed={active}
            onClick={() => onChange(opt.value)}
            className={cn("h-8 px-3", active ? "" : "text-muted-foreground")}
          >
            {opt.label}
          </Button>
        )
      })}
    </div>
  )
}
