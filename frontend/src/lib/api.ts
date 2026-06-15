/**
 * Single source of truth for talking to the backend.
 *
 * Returns a tagged result so callers never have to handle thrown rejections.
 */
export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string }

export async function api<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<ApiResult<T>> {
  try {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      ...init,
    })
    const text = await res.text()
    const body = text ? safeJson<T>(text) : (undefined as unknown as T)
    if (!res.ok) {
      const message =
        body && typeof body === "object" && "detail" in (body as Record<string, unknown>)
          ? String((body as Record<string, unknown>).detail)
          : `HTTP ${res.status}`
      return { ok: false, error: message }
    }
    return { ok: true, data: body as T }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "network error" }
  }
}

function safeJson<T>(text: string): T | string {
  try {
    return JSON.parse(text) as T
  } catch {
    return text
  }
}
