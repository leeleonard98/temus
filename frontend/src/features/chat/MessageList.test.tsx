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

  it("renders a 'Show reasoning' disclosure when an assistant trace is attached", () => {
    render(
      <MessageList
        role="client"
        isStreaming={false}
        messages={[
          {
            id: "u",
            session_id: "s",
            role: "user",
            content: "explain diversification",
            created_at: "t",
          },
          {
            id: "a",
            session_id: "s",
            role: "assistant",
            content: "Diversification spreads risk.",
            created_at: "t",
            trace: {
              researcher: {
                status: "complete",
                topics: ["diversification", "risk"],
                rationale: "Identified relevant topics.",
              },
              analyst: {
                status: "complete",
                findings: [{ claim: "spread across asset classes", confidence: "high" }],
                summary: "Synthesized.",
              },
              writer: { status: "complete" },
            },
          },
        ]}
      />,
    )
    expect(screen.getByText(/show reasoning/i)).toBeInTheDocument()
    expect(screen.getByTestId("agent-stepper")).toBeInTheDocument()
    expect(screen.getByText("diversification")).toBeInTheDocument()
    expect(screen.getByText(/spread across asset classes/i)).toBeInTheDocument()
    expect(screen.getByText(/wrote final answer/i)).toBeInTheDocument()
  })
})
