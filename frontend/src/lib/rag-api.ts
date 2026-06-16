/**
 * RAG API client — semantic / keyword / hybrid retrieval (R1, R6, R8).
 *
 * Used by the (future) chat agent integration; kept tiny because the demo
 * page exercises hybrid only.
 */
const API_BASE: string =
  (import.meta.env?.VITE_API_BASE_URL as string | undefined) ?? "/api/v1"

export type RagHit = {
  chunk_id: string
  doc_id: string
  title: string
  lang: string
  content: string
  score: number
}

export type RagResponse = {
  query: string
  k: number
  results: RagHit[]
}

type Mode = "semantic" | "keyword" | "hybrid"

async function search(mode: Mode, query: string, k = 8): Promise<RagResponse> {
  const res = await fetch(`${API_BASE}/rag/${mode}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, k }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(text || `rag/${mode} failed (${res.status})`)
  }
  return (await res.json()) as RagResponse
}

export const ragSemantic = (q: string, k?: number) => search("semantic", q, k)
export const ragKeyword = (q: string, k?: number) => search("keyword", q, k)
export const ragHybrid = (q: string, k?: number) => search("hybrid", q, k)
