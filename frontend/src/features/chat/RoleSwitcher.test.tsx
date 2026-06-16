import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { RoleSwitcher } from "./RoleSwitcher"

describe("RoleSwitcher", () => {
  it("calls onChange with the clicked role", async () => {
    const onChange = vi.fn()
    render(<RoleSwitcher role="client" onChange={onChange} />)
    await userEvent.click(screen.getByRole("button", { name: /advisor/i }))
    expect(onChange).toHaveBeenCalledWith("advisor")
  })

  it("marks the current role as pressed", () => {
    render(<RoleSwitcher role="advisor" onChange={() => {}} />)
    expect(screen.getByRole("button", { name: /advisor/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    expect(screen.getByRole("button", { name: /client/i })).toHaveAttribute(
      "aria-pressed",
      "false",
    )
  })

  it("disables both buttons when disabled", () => {
    render(<RoleSwitcher role="client" onChange={() => {}} disabled />)
    expect(screen.getByRole("button", { name: /client/i })).toBeDisabled()
    expect(screen.getByRole("button", { name: /advisor/i })).toBeDisabled()
  })
})
