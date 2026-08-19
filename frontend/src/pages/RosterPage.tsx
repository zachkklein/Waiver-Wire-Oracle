import { useEffect, useState } from "react"
import { api } from "../lib/api"
import type { RosterResponse, Team } from "../lib/types"
import Card from "../components/Card"
import PageHeader from "../components/PageHeader"
import PlayerRow from "../components/PlayerRow"
import { Select } from "../components/Field"
import { LoadingState, ErrorState } from "../components/EmptyState"
import { round1 } from "../lib/format"

export default function RosterPage() {
  const [teams, setTeams] = useState<Team[]>([])
  const [selected, setSelected] = useState<string | undefined>(undefined)
  const [roster, setRoster] = useState<RosterResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .teams()
      .then((r) => setTeams(r.teams))
      .catch((e) => setError(String(e)))
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
  const projected = starters.reduce((sum, p) => sum + (p.projected_total_points || 0), 0)

  return (
    <div>
      <PageHeader
        title={roster?.team.team_name ?? "My Team"}
        eyebrow={
          roster
            ? `${roster.team.wins}-${roster.team.losses} · Starters projected ${round1(projected)} across the season`
            : undefined
        }
        action={
          <Select
            label="Viewing"
            value={selected ?? ""}
            onChange={(e) => setSelected(e.target.value || undefined)}
          >
            <option value="">My Team</option>
            {teams
              .filter((t) => !t.is_self)
              .map((t) => (
                <option key={t.team_id} value={t.team_name}>
                  {t.team_name}
                </option>
              ))}
          </Select>
        }
      />

      {!roster ? (
        <LoadingState />
      ) : roster.error ? (
        <ErrorState message={roster.error} />
      ) : (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <Card
            title={`Starters · ${starters.length}`}
            bodyClassName="px-2 pb-3 pt-2"
            action={<span className="text-xs text-text-faint">Points / projected</span>}
          >
            {starters.length === 0 ? (
              <p className="px-3 py-10 text-center text-sm text-text-faint">No starters found</p>
            ) : (
              starters.map((p) => <PlayerRow key={p.player_name} player={p} />)
            )}
          </Card>

          <Card title={`Bench · ${bench.length}`} bodyClassName="px-2 pb-3 pt-2">
            {bench.length === 0 ? (
              <p className="px-3 py-10 text-center text-sm text-text-faint">No bench players found</p>
            ) : (
              bench.map((p) => <PlayerRow key={p.player_name} player={p} />)
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
