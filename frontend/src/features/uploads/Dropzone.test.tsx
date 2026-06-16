import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { Dropzone } from "./Dropzone"

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn())
  // jsdom doesn't implement createObjectURL.
  globalThis.URL.createObjectURL = vi.fn(() => "blob:fake")
  globalThis.URL.revokeObjectURL = vi.fn()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("Dropzone", () => {
  it("renders the upload affordance and the describe button", () => {
    render(<Dropzone />)
    expect(screen.getByText(/Drop images here/i)).toBeInTheDocument()
    expect(screen.getByTestId("describe-btn")).toBeDisabled()
  })

  it("uploads a selected file and shows a thumbnail", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "abc12345",
          path: "assets/uploads/abc12345.png",
          mime: "image/png",
          bytes: 11,
        }),
        { status: 201 },
      ),
    )

    render(<Dropzone />)
    const input = screen.getByTestId("file-input") as HTMLInputElement
    const file = new File([new Uint8Array([1, 2, 3])], "x.png", {
      type: "image/png",
    })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1)
    })
    await waitFor(() => {
      expect(screen.getByAltText("x.png")).toBeInTheDocument()
    })
    // describe button now enabled
    expect(screen.getByTestId("describe-btn")).not.toBeDisabled()
  })

  it("shows the friendly workaround when upload returns 415", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: {
            error: "unsupported file type",
            workaround: "convert to PNG",
          },
        }),
        { status: 415 },
      ),
    )

    render(<Dropzone />)
    const input = screen.getByTestId("file-input") as HTMLInputElement
    fireEvent.change(input, {
      target: { files: [new File(["x"], "x.txt", { type: "text/plain" })] },
    })

    const alert = await screen.findByRole("alert")
    expect(alert.textContent).toMatch(/convert to PNG/i)
  })
})
