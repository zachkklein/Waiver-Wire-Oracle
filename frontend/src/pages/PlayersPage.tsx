import { useEffect, useState } from "react"
import { api } from "../lib/api"
import type { PlayerStatLine } from "../lib/types"
import PageHeader from "../components/PageHeader"
import PositionBadge from "../components/PositionBadge"
import { Select, TextInput } from "../components/Field"
import { LoadingState, ErrorState, EmptyState } from "../components/EmptyState"
import { round1 } from "../lib/format"

const POSITIONS = ["", "QB", "RB", "WR", "TE", "K", "DST"]
const SORT_OPTIONS = [
  { value: "fantasy_points_ppr", label: "Fantasy points (PPR)" },
  { value: "fantasy_points", label: "Fantasy points" },
  { value: "passing_yards", label: "Passing yards" },
  { value: "rushing_yards", label: "Rushing yards" },
  { value: "receiving_yards", label: "Receiving yards" },
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
    <div>
      <PageHeader title="Players" eyebrow="League-wide leaders from synced nflverse stats" />

      <div className="mb-5 flex flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-5 shadow-soft">
        <TextInput
          label="Search"
          value={playerName}
          onChange={(e) => setPlayerName(e.target.value)}
          placeholder="Player name"
          className="w-56"
        />
        <Select label="Position" value={position} onChange={(e) => setPosition(e.target.value)}>
          {POSITIONS.map((p) => (
            <option key={p} value={p}>
              {p || "All positions"}
            </option>
          ))}
        </Select>
        <Select label="Sort by" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
        <label className="flex cursor-pointer items-center gap-2.5 py-2.5 text-sm text-text-muted">
          <input
            type="checkbox"
            checked={aggregate}
            onChange={(e) => setAggregate(e.target.checked)}
            className="h-4 w-4 rounded accent-accent"
          />
          Season totals
        </label>
      </div>

      {error ? (
        <ErrorState message={error} />
      ) : !rows ? (
        <LoadingState />
      ) : rows.length === 0 ? (
        <EmptyState message="No players match those filters." />
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-border bg-surface shadow-soft">
          <table className="w-full min-w-[740px]">
            <thead>
              <tr>
                {["#", "Player", "Team", aggregate ? "Games" : "Week", "Pass", "Rush", "Rec", "TD", "Points"].map(
                  (h, i) => (
                    <th
                      key={h}
                      className={`py-4 text-xs font-medium text-text-muted ${
                        i === 0 ? "pl-6 text-left" : i === 1 ? "text-left" : "pr-6 text-right"
                      }`}
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={`${r.player_id}-${r.week ?? "agg"}-${i}`}
                  className="border-t border-border transition-colors hover:bg-surface-raised"
                >
                  <td className="py-3 pl-6 text-sm tabular-nums text-text-faint">{i + 1}</td>
                  <td className="py-3">
                    <div className="flex items-center gap-3">
                      <PositionBadge position={r.position} />
                      <span className="text-sm font-semibold text-text">
                        {r.player_display_name}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 pr-6 text-right text-sm text-text-muted">{r.recent_team}</td>
                  <td className="py-3 pr-6 text-right text-sm tabular-nums text-text-muted">
                    {aggregate ? r.games_played : r.week}
                  </td>
                  <td className="py-3 pr-6 text-right text-sm tabular-nums text-text-muted">
                    {r.passing_yards || "—"}
                  </td>
                  <td className="py-3 pr-6 text-right text-sm tabular-nums text-text-muted">
                    {r.rushing_yards || "—"}
                  </td>
                  <td className="py-3 pr-6 text-right text-sm tabular-nums text-text-muted">
                    {r.receiving_yards || "—"}
                  </td>
                  <td className="py-3 pr-6 text-right text-sm tabular-nums text-text">
                    {r.passing_tds + r.rushing_tds + r.receiving_tds}
                  </td>
                  <td className="py-3 pr-6 text-right text-sm font-bold tabular-nums text-accent">
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
