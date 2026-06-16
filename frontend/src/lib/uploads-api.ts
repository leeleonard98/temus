/**
 * Uploads API client — image upload + vision describe (V1, V2, V4).
 *
 * Mirrors the style of `portfolio-api.ts`. Throws on non-2xx so callers can
 * surface the error in the UI.
 */
const API_BASE: string =
  (import.meta.env?.VITE_API_BASE_URL as string | undefined) ?? "/api/v1"

export type UploadedImage = {
  id: string
  path: string
  mime: string
  bytes: number
}

export type DescribeResponse = {
  description: string
  image_ids: string[]
}

export type UploadError = {
  status: number
  message: string
  workaround?: string
}

export async function uploadImage(file: File): Promise<UploadedImage> {
  const fd = new FormData()
  fd.append("file", file)
  const res = await fetch(`${API_BASE}/uploads/image`, {
    method: "POST",
    body: fd,
  })
  if (!res.ok) {
    let detail: unknown
    try {
      detail = (await res.json()).detail
    } catch {
      detail = undefined
    }
    const err: UploadError = {
      status: res.status,
      message:
        (detail as { error?: string } | undefined)?.error ??
        `upload failed (${res.status})`,
      workaround: (detail as { workaround?: string } | undefined)?.workaround,
    }
    throw err
  }
  return (await res.json()) as UploadedImage
}

export async function describeImages(
  imageIds: string[],
  question: string,
): Promise<DescribeResponse> {
  const res = await fetch(`${API_BASE}/uploads/describe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_ids: imageIds, question }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(text || `describe failed (${res.status})`)
  }
  return (await res.json()) as DescribeResponse
}
