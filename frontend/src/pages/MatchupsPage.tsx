import { useEffect, useState } from "react"
import { api } from "../lib/api"
import type { MatchupsResponse, Meta } from "../lib/types"
import MatchupCard from "../components/MatchupCard"
import PageHeader from "../components/PageHeader"
import { LoadingState, ErrorState } from "../components/EmptyState"

export default function MatchupsPage() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [week, setWeek] = useState<number | null>(null)
  const [data, setData] = useState<MatchupsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.meta().then((m) => {
      setMeta(m)
      setWeek(m.current_week ?? 1)
    })
  }, [])

  useEffect(() => {
    if (week === null) return
    setData(null)
    api
      .matchups(week)
      .then(setData)
      .catch((e) => setError(String(e)))
  }, [week])

  if (error) return <ErrorState message={error} />

  const maxWeek = meta?.current_week ?? 1
  const weeks = Array.from({ length: maxWeek }, (_, i) => i + 1)

  return (
    <div>
      <PageHeader
        title="Matchups"
        eyebrow="Every head-to-head in the league, week by week"
        action={
          <div className="flex flex-wrap gap-2">
            {weeks.map((w) => (
              <button
                key={w}
                onClick={() => setWeek(w)}
                aria-current={w === week ? "true" : undefined}
                className={`h-10 min-w-10 rounded-full px-3.5 text-sm font-semibold tabular-nums transition-colors ${
                  w === week
                    ? "bg-accent text-bg"
                    : "bg-surface text-text-muted hover:bg-surface-raised hover:text-text"
                }`}
              >
                {w}
              </button>
            ))}
          </div>
        }
      />

      {!data ? (
        <LoadingState />
      ) : data.error ? (
        <ErrorState message={data.error} />
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 2xl:grid-cols-3">
          {data.matchups.map((m) => (
            <MatchupCard key={`${m.home_team_id}-${m.away_team_id}`} matchup={m} />
          ))}
        </div>
      )}
    </div>
  )
}
