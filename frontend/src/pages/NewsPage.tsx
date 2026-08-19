import { useState } from "react"
import { api } from "../lib/api"
import type { NewsResult } from "../lib/types"
import { LoadingState, ErrorState, EmptyState } from "../components/EmptyState"

export default function NewsPage() {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<NewsResult[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const search = () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    api
      .news(query, { n_results: 10 })
      .then(setResults)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-3xl font-bold text-text">News</h1>

      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="Search injuries, roster moves, breakouts…"
          className="flex-1 rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-text placeholder:text-text-faint focus:border-accent/50 focus:outline-none"
        />
        <button
          onClick={search}
          className="rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-bg transition-opacity hover:opacity-90"
        >
          Search
        </button>
      </div>

      {error ? (
        <ErrorState message={error} />
      ) : loading ? (
        <LoadingState />
      ) : results === null ? (
        <EmptyState message="Search recent NFL news synced from RSS feeds." />
      ) : results.length === 0 ? (
        <EmptyState message="No results." />
      ) : (
        <div className="flex flex-col gap-3">
          {results.map((r, i) => (
            <a
              key={i}
              href={r.link}
              target="_blank"
              rel="noreferrer"
              className="rounded-xl border border-border bg-surface p-4 transition-colors hover:border-accent/40"
            >
              <div className="flex items-start justify-between gap-4">
                <h3 className="font-medium text-text">{r.title}</h3>
                <span className="shrink-0 text-xs text-text-faint">{r.published}</span>
              </div>
              <p className="mt-1.5 text-sm text-text-muted">{r.snippet}</p>
              <div className="mt-2 text-xs text-accent">{r.source}</div>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
