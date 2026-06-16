import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { SessionPicker } from "./SessionPicker"
import type { Session } from "@/lib/chat-api"

function makeSession(overrides: Partial<Session> = {}): Session {
  return {
    id: "s-1",
    user_id: "u-1",
    title: "Hello",
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

describe("SessionPicker", () => {
  it("renders one entry per session, newest titles visible", () => {
    const sessions: Session[] = [
      makeSession({ id: "s-1", title: "Latest" }),
      makeSession({ id: "s-2", title: "Earlier" }),
    ]
    render(
      <SessionPicker
        sessions={sessions}
        currentSessionId="s-1"
        onSelect={() => {}}
        onNew={() => {}}
      />,
    )
    expect(screen.getByText("Latest")).toBeInTheDocument()
    expect(screen.getByText("Earlier")).toBeInTheDocument()
  })

  it("clicking a session entry calls onSelect with its id", async () => {
    const onSelect = vi.fn()
    const sessions: Session[] = [
      makeSession({ id: "s-1", title: "First" }),
      makeSession({ id: "s-2", title: "Second" }),
    ]
    render(
      <SessionPicker
        sessions={sessions}
        currentSessionId="s-1"
        onSelect={onSelect}
        onNew={() => {}}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: /Second/i }))
    expect(onSelect).toHaveBeenCalledWith("s-2")
  })

  it('"New chat" button calls onNew', async () => {
    const onNew = vi.fn()
    render(
      <SessionPicker
        sessions={[]}
        currentSessionId={null}
        onSelect={() => {}}
        onNew={onNew}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: /new chat/i }))
    expect(onNew).toHaveBeenCalledTimes(1)
  })

  it("renders 'Untitled' when session.title is null/empty", () => {
    const sessions: Session[] = [
      makeSession({ id: "s-1", title: null }),
      makeSession({ id: "s-2", title: "  " }),
    ]
    render(
      <SessionPicker
        sessions={sessions}
        currentSessionId="s-1"
        onSelect={() => {}}
        onNew={() => {}}
      />,
    )
    expect(screen.getAllByText("Untitled")).toHaveLength(2)
  })

  it("disables 'New chat' when disabled prop is set", () => {
    render(
      <SessionPicker
        sessions={[]}
        currentSessionId={null}
        onSelect={() => {}}
        onNew={() => {}}
        disabled
      />,
    )
    expect(screen.getByRole("button", { name: /new chat/i })).toBeDisabled()
  })
})
