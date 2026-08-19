import { useState } from "react"
import { api } from "../lib/api"
import type { NewsResult } from "../lib/types"
import PageHeader from "../components/PageHeader"
import { LoadingState, ErrorState, EmptyState } from "../components/EmptyState"

const SUGGESTIONS = ["injury report", "waiver wire pickups", "backfield committee", "snap counts"]

// RSS chunks usually open by repeating the headline — drop it so the snippet adds something.
function trimSnippet(snippet: string, title: string): string {
  const s = snippet.trim()
  const t = title?.trim()
  if (t && s.toLowerCase().startsWith(t.toLowerCase())) {
    return s.slice(t.length).replace(/^[\s:–—-]+/, "")
  }
  return s
}

export default function NewsPage() {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<NewsResult[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const search = (q: string = query) => {
    if (!q.trim()) return
    setQuery(q)
    setLoading(true)
    setError(null)
    api
      .news(q, { n_results: 10 })
      .then(setResults)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }

  return (
    <div>
      <PageHeader title="News" eyebrow="Semantic search across your synced RSS feeds" />

      <div className="mb-4 flex gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="Search injuries, roster moves, breakouts"
          className="flex-1 rounded-full border border-border bg-surface px-5 py-3.5 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
        />
        <button
          onClick={() => search()}
          className="pressable rounded-full bg-accent px-7 text-sm font-bold text-bg hover:bg-accent-strong"
        >
          Search
        </button>
      </div>

      <div className="mb-7 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => search(s)}
            className="rounded-full bg-surface px-4 py-2 text-xs font-medium text-text-muted transition-colors hover:bg-surface-raised hover:text-accent"
          >
            {s}
          </button>
        ))}
      </div>

      {error ? (
        <ErrorState message={error} />
      ) : loading ? (
        <LoadingState message="Searching" />
      ) : results === null ? (
        <EmptyState message="Search recent NFL news synced from your RSS feeds." />
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
              className="group rounded-2xl border border-border bg-surface p-5 shadow-soft transition-all hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-lift"
            >
              <div className="mb-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs">
                {r.source ? <span className="font-semibold text-accent">{r.source}</span> : null}
                {r.source && r.published ? <span className="text-text-faint">·</span> : null}
                {r.published ? <span className="text-text-faint">{r.published}</span> : null}
              </div>
              <h3 className="font-display soft text-lg font-semibold leading-snug text-text group-hover:text-accent">
                {r.title}
              </h3>
              <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-text-muted">
                {trimSnippet(r.snippet, r.title)}
              </p>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
