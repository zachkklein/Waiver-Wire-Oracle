import { useEffect, useState } from "react"
import { api } from "../lib/api"
import type { MatchupsResponse, Meta } from "../lib/types"
import MatchupCard from "../components/MatchupCard"
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
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl font-bold text-text">Matchups</h1>
        <select
          value={week ?? ""}
          onChange={(e) => setWeek(Number(e.target.value))}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:border-accent/50 focus:outline-none"
        >
          {weeks.map((w) => (
            <option key={w} value={w}>
              Week {w}
            </option>
          ))}
        </select>
      </div>

      {!data ? (
        <LoadingState />
      ) : data.error ? (
        <ErrorState message={data.error} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.matchups.map((m) => (
            <MatchupCard key={`${m.home_team_id}-${m.away_team_id}`} matchup={m} />
          ))}
        </div>
      )}
    </div>
  )
}
