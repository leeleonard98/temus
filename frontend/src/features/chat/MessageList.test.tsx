import { describe, it, expect, beforeAll } from "vitest"
import { render, screen } from "@testing-library/react"

import { MessageList } from "./MessageList"

beforeAll(() => {
  // jsdom doesn't implement scrollIntoView
  Element.prototype.scrollIntoView = () => {}
})

describe("MessageList", () => {
  it("shows empty-state copy for the client role", () => {
    render(<MessageList messages={[]} role="client" isStreaming={false} />)
    expect(screen.getByText(/financial gps/i)).toBeInTheDocument()
  })

  it("shows empty-state copy for the advisor role", () => {
    render(<MessageList messages={[]} role="advisor" isStreaming={false} />)
    expect(screen.getByText(/command center/i)).toBeInTheDocument()
  })

  it("renders user and assistant messages", () => {
    render(
      <MessageList
        role="client"
        isStreaming={false}
        messages={[
          { id: "1", session_id: "s", role: "user", content: "hi", created_at: "t" },
          { id: "2", session_id: "s", role: "assistant", content: "hello", created_at: "t" },
        ]}
      />,
    )
    expect(screen.getByText("hi")).toBeInTheDocument()
    expect(screen.getByText("hello")).toBeInTheDocument()
  })

  it("renders typing dots for empty pending assistant message", () => {
    render(
      <MessageList
        role="client"
        isStreaming
        messages={[
          {
            id: "p",
            session_id: "s",
            role: "assistant",
            content: "",
            created_at: "t",
            pending: true,
          },
        ]}
      />,
    )
    expect(screen.getByLabelText(/assistant is typing/i)).toBeInTheDocument()
  })
})
