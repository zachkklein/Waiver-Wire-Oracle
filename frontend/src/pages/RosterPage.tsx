import { useEffect, useState } from "react"
import { api } from "../lib/api"
import type { RosterResponse, Team } from "../lib/types"
import Card from "../components/Card"
import PlayerRow from "../components/PlayerRow"
import { LoadingState, ErrorState } from "../components/EmptyState"

export default function RosterPage() {
  const [teams, setTeams] = useState<Team[]>([])
  const [selected, setSelected] = useState<string | undefined>(undefined)
  const [roster, setRoster] = useState<RosterResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.teams().then((r) => setTeams(r.teams)).catch((e) => setError(String(e)))
  }, [])

  useEffect(() => {
    setRoster(null)
    api
      .roster(selected)
      .then(setRoster)
      .catch((e) => setError(String(e)))
  }, [selected])

  if (error) return <ErrorState message={error} />

  const starters = roster?.players.filter((p) => p.lineup_slot !== "BE" && p.lineup_slot !== "IR") ?? []
  const bench = roster?.players.filter((p) => p.lineup_slot === "BE" || p.lineup_slot === "IR") ?? []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl font-bold text-text">
          {roster?.team.team_name ?? "My Team"}
        </h1>
        <select
          value={selected ?? ""}
          onChange={(e) => setSelected(e.target.value || undefined)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:border-accent/50 focus:outline-none"
        >
          <option value="">My Team</option>
          {teams
            .filter((t) => !t.is_self)
            .map((t) => (
              <option key={t.team_id} value={t.team_name}>
                {t.team_name}
              </option>
            ))}
        </select>
      </div>

      {!roster ? (
        <LoadingState />
      ) : roster.error ? (
        <ErrorState message={roster.error} />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card title="Starters">
            {starters.length === 0 ? (
              <p className="text-sm text-text-faint">No starters found.</p>
            ) : (
              starters.map((p) => <PlayerRow key={p.player_name} player={p} />)
            )}
          </Card>
          <Card title="Bench">
            {bench.length === 0 ? (
              <p className="text-sm text-text-faint">No bench players found.</p>
            ) : (
              bench.map((p) => <PlayerRow key={p.player_name} player={p} />)
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
