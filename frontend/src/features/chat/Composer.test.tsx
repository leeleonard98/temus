import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { Composer } from "./Composer"

describe("Composer", () => {
  it("Enter sends and clears the input", async () => {
    const onSend = vi.fn()
    render(<Composer onSend={onSend} />)
    const input = screen.getByLabelText(/message/i)
    await userEvent.type(input, "hello{enter}")
    expect(onSend).toHaveBeenCalledWith("hello")
    expect(input).toHaveValue("")
  })

  it("Shift+Enter inserts a newline and does not send", async () => {
    const onSend = vi.fn()
    render(<Composer onSend={onSend} />)
    const input = screen.getByLabelText(/message/i)
    await userEvent.type(input, "line1{Shift>}{Enter}{/Shift}line2")
    expect(onSend).not.toHaveBeenCalled()
    expect(input).toHaveValue("line1\nline2")
  })

  it("Send button is disabled while streaming", () => {
    render(<Composer onSend={() => {}} disabled />)
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled()
    expect(screen.getByLabelText(/message/i)).toBeDisabled()
  })

  it("Send button is disabled when input is empty", () => {
    render(<Composer onSend={() => {}} />)
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled()
  })

  it("clicking Send submits the trimmed value", async () => {
    const onSend = vi.fn()
    render(<Composer onSend={onSend} />)
    await userEvent.type(screen.getByLabelText(/message/i), "  hi  ")
    await userEvent.click(screen.getByRole("button", { name: /send/i }))
    expect(onSend).toHaveBeenCalledWith("hi")
  })
})
