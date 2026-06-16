import { useEffect, useState } from "react"
import { MessageSquare, X } from "lucide-react"

import { ChatPanel } from "@/features/chat/ChatPanel"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/**
 * Floating chat drawer.
 *
 * Renders a fixed bottom-right launcher button; clicking it slides a side
 * panel in from the right with the standard `ChatPanel`. Because `useChat`
 * reads the shared `UiContextProvider`, any snapshot the host page has
 * published (e.g. portfolio totals on `/portfolio`) is automatically
 * shipped along with each chat send — that's the AC4 demo moment.
 *
 * Stateless beyond open/closed; the chat itself owns its own session +
 * messages, so opening/closing the drawer doesn't lose context.
 */
export function ChatDrawer() {
  const [open, setOpen] = useState(false)

  // Esc closes the drawer.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open])

  return (
    <>
      {/* Launcher — fixed, only visible when drawer closed. */}
      {!open && (
        <Button
          aria-label="Open chat"
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-40 h-12 w-12 rounded-full p-0 shadow-lg"
        >
          <MessageSquare className="h-5 w-5" />
        </Button>
      )}

      {/* Drawer + scrim. */}
      <div
        aria-hidden={!open}
        className={cn(
          "fixed inset-0 z-50 transition-opacity",
          open ? "pointer-events-auto" : "pointer-events-none opacity-0",
        )}
      >
        {/* Scrim — click to close. */}
        <div
          className={cn(
            "absolute inset-0 bg-black/40 transition-opacity",
            open ? "opacity-100" : "opacity-0",
          )}
          onClick={() => setOpen(false)}
        />

        {/* Panel. */}
        <aside
          role="dialog"
          aria-label="AuraWealth chat"
          className={cn(
            "absolute right-0 top-0 flex h-full w-full max-w-[460px] flex-col bg-background shadow-2xl transition-transform",
            open ? "translate-x-0" : "translate-x-full",
          )}
        >
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Ask about what you see
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setOpen(false)}
              aria-label="Close chat"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="min-h-0 flex-1 overflow-hidden">
            <ChatPanel />
          </div>
        </aside>
      </div>
    </>
  )
}
