import { useEffect, useRef } from "react"

import { cn } from "@/lib/utils"
import type { Message, Role } from "@/lib/chat-api"
import type { AgentTrace, StageStatus } from "./useChat"

type DisplayMessage = Message & { pending?: boolean; trace?: AgentTrace }

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
              "flex flex-col",
              m.role === "user" ? "items-end" : "items-start",
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
            {m.role === "assistant" && m.trace ? (
              <ReasoningDisclosure trace={m.trace} />
            ) : null}
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

/**
 * Collapsible "Show reasoning" disclosure. Built on the native <details>
 * element so it works without bringing in another shadcn primitive.
 */
function ReasoningDisclosure({ trace }: { trace: AgentTrace }) {
  return (
    <details
      className="mt-1 max-w-[80%] rounded-md border border-border/60 bg-background/50 text-xs"
      data-testid="reasoning-disclosure"
    >
      <summary className="cursor-pointer select-none px-2 py-1 text-muted-foreground hover:text-foreground">
        Show reasoning
      </summary>
      <div className="space-y-3 border-t border-border/60 px-3 py-2">
        <Stepper trace={trace} />
        <ResearcherStage trace={trace.researcher} />
        <AnalystStage trace={trace.analyst} />
        <WriterStage trace={trace.writer} />
      </div>
    </details>
  )
}

function Stepper({ trace }: { trace: AgentTrace }) {
  const stages: { key: keyof AgentTrace; label: string; status: StageStatus }[] = [
    { key: "researcher", label: "Researcher", status: trace.researcher.status },
    { key: "analyst", label: "Analyst", status: trace.analyst.status },
    { key: "writer", label: "Writer", status: trace.writer.status },
  ]
  return (
    <ol
      className="flex items-center gap-2"
      aria-label="Agent pipeline progress"
      data-testid="agent-stepper"
    >
      {stages.map((s, i) => (
        <li key={s.key} className="flex items-center gap-2">
          <span
            className={cn(
              "inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-medium ring-1 ring-inset",
              s.status === "complete"
                ? "bg-emerald-100 text-emerald-800 ring-emerald-200"
                : s.status === "running"
                  ? "bg-amber-100 text-amber-800 ring-amber-200"
                  : "bg-muted text-muted-foreground ring-border",
            )}
            aria-label={`${s.label} ${s.status}`}
          >
            {s.status === "complete" ? "✓" : i + 1}
          </span>
          <span className="font-medium">{s.label}</span>
          {i < stages.length - 1 ? (
            <span className="text-muted-foreground/60">›</span>
          ) : null}
        </li>
      ))}
    </ol>
  )
}

function ResearcherStage({ trace }: { trace: AgentTrace["researcher"] }) {
  if (trace.status === "idle") return null
  return (
    <section data-testid="trace-researcher">
      <h4 className="mb-1 text-xs font-semibold">Researcher</h4>
      {trace.topics.length > 0 ? (
        <ul className="ml-4 list-disc text-muted-foreground">
          {trace.topics.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground">Identifying topics…</p>
      )}
      {trace.rationale ? (
        <p className="mt-1 italic text-muted-foreground">{trace.rationale}</p>
      ) : null}
    </section>
  )
}

function AnalystStage({ trace }: { trace: AgentTrace["analyst"] }) {
  if (trace.status === "idle") return null
  return (
    <section data-testid="trace-analyst">
      <h4 className="mb-1 text-xs font-semibold">Analyst</h4>
      {trace.findings.length > 0 ? (
        <ul className="space-y-1">
          {trace.findings.map((f, i) => (
            <li key={i} className="flex items-start gap-2">
              <span
                className={cn(
                  "shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ring-1 ring-inset",
                  f.confidence === "high"
                    ? "bg-emerald-100 text-emerald-800 ring-emerald-200"
                    : f.confidence === "low"
                      ? "bg-rose-100 text-rose-800 ring-rose-200"
                      : "bg-amber-100 text-amber-800 ring-amber-200",
                )}
              >
                {f.confidence}
              </span>
              <span className="text-muted-foreground">{f.claim}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground">Synthesizing findings…</p>
      )}
      {trace.summary ? (
        <p className="mt-1 italic text-muted-foreground">{trace.summary}</p>
      ) : null}
    </section>
  )
}

function WriterStage({ trace }: { trace: AgentTrace["writer"] }) {
  if (trace.status === "idle") return null
  return (
    <section data-testid="trace-writer">
      <h4 className="mb-1 text-xs font-semibold">Writer</h4>
      <p className="text-muted-foreground">
        {trace.status === "complete" ? "Wrote final answer." : "Writing final answer…"}
      </p>
    </section>
  )
}
