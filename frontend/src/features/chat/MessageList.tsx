import { useEffect, useRef } from "react"

import { cn } from "@/lib/utils"
import type { Message, Role } from "@/lib/chat-api"

type DisplayMessage = Message & { pending?: boolean }

type Props = {
  messages: DisplayMessage[]
  role: Role
  isStreaming: boolean
}

const ACCENT_BY_ROLE: Record<Role, { user: string }> = {
  client: { user: "bg-emerald-600 text-white" },
  advisor: { user: "bg-indigo-600 text-white" },
}

export function MessageList({ messages, role, isStreaming }: Props) {
  const endRef = useRef<HTMLDivElement | null>(null)

  // Auto-scroll on new tokens / new messages.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" })
  }, [messages, isStreaming])

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        <p className="text-sm text-muted-foreground">
          {role === "client"
            ? "Ask your Financial GPS anything — savings, investments, retirement."
            : "Welcome, Advisor. Ask the Command Center about clients, portfolios, or markets."}
        </p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4" data-testid="message-list">
      <ul className="mx-auto flex max-w-3xl flex-col gap-3">
        {messages.map((m) => (
          <li
            key={m.id}
            className={cn(
              "flex",
              m.role === "user" ? "justify-end" : "justify-start",
            )}
          >
            <div
              className={cn(
                "max-w-[80%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm shadow-sm",
                m.role === "user"
                  ? ACCENT_BY_ROLE[role].user
                  : "bg-muted text-foreground",
              )}
            >
              {m.content || (m.pending ? <TypingDots /> : null)}
            </div>
          </li>
        ))}
      </ul>
      <div ref={endRef} />
    </div>
  )
}

function TypingDots() {
  return (
    <span aria-label="Assistant is typing" className="inline-flex gap-1">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-foreground/50 [animation-delay:-0.3s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-foreground/50 [animation-delay:-0.15s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-foreground/50" />
    </span>
  )
}
