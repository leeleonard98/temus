import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { Session } from "@/lib/chat-api"

type Props = {
  sessions: Session[]
  currentSessionId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  disabled?: boolean
}

/**
 * Left-rail session picker. Lists recent sessions for the active user
 * (newest first) and exposes a prominent "New chat" button.
 */
export function SessionPicker({
  sessions,
  currentSessionId,
  onSelect,
  onNew,
  disabled,
}: Props) {
  return (
    <aside
      aria-label="Chat sessions"
      className="flex w-60 shrink-0 flex-col border-r bg-muted/20"
    >
      <div className="border-b p-3">
        <Button
          type="button"
          size="sm"
          className="w-full"
          onClick={onNew}
          disabled={disabled}
        >
          New chat
        </Button>
      </div>
      <nav className="flex-1 overflow-y-auto p-2" aria-label="Recent sessions">
        {sessions.length === 0 ? (
          <p className="px-2 py-3 text-xs text-muted-foreground">
            No sessions yet.
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {sessions.map((s) => {
              const active = s.id === currentSessionId
              return (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(s.id)}
                    aria-current={active ? "true" : undefined}
                    className={cn(
                      "flex w-full flex-col items-start gap-0.5 rounded-md px-2.5 py-2 text-left text-sm transition-colors",
                      "hover:bg-accent hover:text-accent-foreground",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      active && "bg-accent text-accent-foreground",
                    )}
                  >
                    <span className="line-clamp-1 font-medium">
                      {s.title?.trim() ? s.title : "Untitled"}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatRelative(s.updated_at ?? s.created_at)}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </nav>
    </aside>
  )
}

/**
 * Tiny relative-time helper. We avoid dragging in date-fns for one usage.
 * Returns strings like "just now", "5m ago", "2h ago", "3d ago",
 * or a YYYY-MM-DD fallback for older entries / unparseable inputs.
 */
function formatRelative(iso: string): string {
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return iso
  const deltaSec = Math.max(0, Math.floor((Date.now() - t) / 1000))
  if (deltaSec < 45) return "just now"
  const min = Math.floor(deltaSec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  if (day < 7) return `${day}d ago`
  return new Date(t).toISOString().slice(0, 10)
}
