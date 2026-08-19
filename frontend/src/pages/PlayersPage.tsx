import { useEffect, useState } from "react"
import { api } from "../lib/api"
import type { PlayerStatLine } from "../lib/types"
import PositionBadge from "../components/PositionBadge"
import { LoadingState, ErrorState, EmptyState } from "../components/EmptyState"
import { round1 } from "../lib/format"

const POSITIONS = ["", "QB", "RB", "WR", "TE", "K", "DST"]
const SORT_OPTIONS = [
  { value: "fantasy_points_ppr", label: "Fantasy Pts (PPR)" },
  { value: "fantasy_points", label: "Fantasy Pts" },
  { value: "passing_yards", label: "Passing Yds" },
  { value: "rushing_yards", label: "Rushing Yds" },
  { value: "receiving_yards", label: "Receiving Yds" },
  { value: "receptions", label: "Receptions" },
]

export default function PlayersPage() {
  const [playerName, setPlayerName] = useState("")
  const [position, setPosition] = useState("")
  const [aggregate, setAggregate] = useState(true)
  const [sortBy, setSortBy] = useState("fantasy_points_ppr")
  const [rows, setRows] = useState<PlayerStatLine[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const handle = setTimeout(() => {
      setRows(null)
      api
        .stats({
          player_name: playerName || undefined,
          position: position || undefined,
          aggregate,
          sort_by: sortBy,
          limit: 50,
        })
        .then(setRows)
        .catch((e) => setError(String(e)))
    }, 250)
    return () => clearTimeout(handle)
  }, [playerName, position, aggregate, sortBy])

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-3xl font-bold text-text">Players</h1>

      <div className="flex flex-wrap items-center gap-3">
        <input
          value={playerName}
          onChange={(e) => setPlayerName(e.target.value)}
          placeholder="Search player…"
          className="w-56 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent/50 focus:outline-none"
        />
        <select
          value={position}
          onChange={(e) => setPosition(e.target.value)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:border-accent/50 focus:outline-none"
        >
          {POSITIONS.map((p) => (
            <option key={p} value={p}>
              {p || "All positions"}
            </option>
          ))}
        </select>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:border-accent/50 focus:outline-none"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              Sort: {o.label}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-text-muted">
          <input type="checkbox" checked={aggregate} onChange={(e) => setAggregate(e.target.checked)} className="accent-accent" />
          Season totals
        </label>
      </div>

      {error ? (
        <ErrorState message={error} />
      ) : !rows ? (
        <LoadingState />
      ) : rows.length === 0 ? (
        <EmptyState message="No players found." />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-faint">
                <th className="px-4 py-3 font-medium">Player</th>
                <th className="px-4 py-3 font-medium">Team</th>
                {!aggregate && <th className="px-4 py-3 font-medium">Wk</th>}
                <th className="px-4 py-3 text-right font-medium">Yds (P/R/Rec)</th>
                <th className="px-4 py-3 text-right font-medium">TD</th>
                <th className="px-4 py-3 text-right font-medium">Fantasy Pts</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.player_id}-${r.week ?? "agg"}-${i}`} className="border-b border-border last:border-b-0">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <PositionBadge position={r.position} />
                      <span className="text-text">{r.player_display_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-text-muted">{r.recent_team}</td>
                  {!aggregate && <td className="px-4 py-3 text-text-muted">{r.week}</td>}
                  <td className="px-4 py-3 text-right tabular-nums text-text-muted">
                    {r.passing_yards}/{r.rushing_yards}/{r.receiving_yards}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-text-muted">
                    {r.passing_tds + r.rushing_tds + r.receiving_tds}
                  </td>
                  <td className="px-4 py-3 text-right font-display font-bold tabular-nums text-accent">
                    {round1(r.fantasy_points_ppr)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
