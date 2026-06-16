import { Composer } from "./Composer"
import { MessageList } from "./MessageList"
import { RoleSwitcher } from "./RoleSwitcher"
import { SessionPicker } from "./SessionPicker"
import { useChat } from "./useChat"
import { cn } from "@/lib/utils"
import type { Role } from "@/lib/chat-api"

const ROLE_THEME: Record<Role, { strip: string; badge: string; title: string; subtitle: string }> = {
  client: {
    strip: "bg-gradient-to-r from-emerald-600 to-teal-500",
    badge: "bg-emerald-100 text-emerald-900 ring-emerald-200",
    title: "Financial GPS",
    subtitle: "Your personal AI financial copilot",
  },
  advisor: {
    strip: "bg-gradient-to-r from-indigo-700 to-slate-700",
    badge: "bg-indigo-100 text-indigo-900 ring-indigo-200",
    title: "Command Center",
    subtitle: "Advisor workbench powered by AuraWealth",
  },
}

export function ChatPanel() {
  const chat = useChat()
  const theme = ROLE_THEME[chat.role]

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden rounded-lg border bg-card shadow-sm">
      <SessionPicker
        sessions={chat.sessions}
        currentSessionId={chat.currentSessionId}
        onSelect={(id) => {
          void chat.selectSession(id)
        }}
        onNew={() => {
          void chat.newChat()
        }}
        disabled={chat.isStreaming || !chat.user}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className={cn("h-1.5 w-full", theme.strip)} aria-hidden />
        <header className="flex items-center justify-between gap-4 border-b px-4 py-3">
          <div className="flex items-center gap-3">
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
                theme.badge,
              )}
            >
              {chat.role === "client" ? "Client" : "Advisor"}
            </span>
            <div>
              <h2 className="text-sm font-semibold leading-tight">{theme.title}</h2>
              <p className="text-xs text-muted-foreground">{theme.subtitle}</p>
            </div>
          </div>
          <RoleSwitcher
            role={chat.role}
            onChange={chat.setRole}
            disabled={chat.isStreaming}
          />
        </header>

        {chat.error ? (
          <div
            role="alert"
            className="border-b border-destructive/30 bg-destructive/5 px-4 py-2 text-sm text-destructive"
          >
            {chat.error}
          </div>
        ) : null}

        <MessageList
          messages={chat.messages}
          role={chat.role}
          isStreaming={chat.isStreaming}
        />

        <Composer
          onSend={chat.send}
          disabled={chat.isStreaming || !chat.session}
          placeholder={
            chat.role === "client"
              ? "Ask about your finances…"
              : "Ask about clients, portfolios, or markets…"
          }
        />
      </div>
    </div>
  )
}
