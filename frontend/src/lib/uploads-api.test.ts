import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { describeImages, uploadImage } from "./uploads-api"

describe("uploads-api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("uploadImage POSTs multipart and returns the parsed payload", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "abc123",
          path: "assets/uploads/abc123.png",
          mime: "image/png",
          bytes: 42,
        }),
        { status: 201 },
      ),
    )
    const file = new File([new Uint8Array([1, 2, 3])], "x.png", {
      type: "image/png",
    })
    const out = await uploadImage(file)

    expect(out.id).toBe("abc123")
    const [url, init] = vi.mocked(fetch).mock.calls[0]!
    expect(String(url)).toMatch(/\/uploads\/image$/)
    expect((init as RequestInit).method).toBe("POST")
    expect((init as RequestInit).body).toBeInstanceOf(FormData)
  })

  it("uploadImage throws a typed error including the workaround on 415", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: {
            error: "unsupported file type",
            workaround: "convert to PNG",
            supported: ["image/png"],
          },
        }),
        { status: 415 },
      ),
    )
    const file = new File([new Uint8Array([0])], "x.txt", { type: "text/plain" })
    await expect(uploadImage(file)).rejects.toMatchObject({
      status: 415,
      message: "unsupported file type",
      workaround: "convert to PNG",
    })
  })

  it("describeImages POSTs JSON and returns the description", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          description: "two charts and a table",
          image_ids: ["a", "b"],
        }),
        { status: 200 },
      ),
    )
    const out = await describeImages(["a", "b"], "what is this")
    expect(out.description).toContain("charts")
    const [url, init] = vi.mocked(fetch).mock.calls[0]!
    expect(String(url)).toMatch(/\/uploads\/describe$/)
    expect((init as RequestInit).method).toBe("POST")
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      image_ids: ["a", "b"],
      question: "what is this",
    })
  })
})
