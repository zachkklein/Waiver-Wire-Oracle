import { useEffect, useState } from "react"
import { api } from "../lib/api"
import type { Team } from "../lib/types"
import TeamBadge from "../components/TeamBadge"
import { LoadingState, ErrorState } from "../components/EmptyState"
import { round1 } from "../lib/format"

type SortKey = "wins" | "points_for" | "points_against"

export default function StandingsPage() {
  const [teams, setTeams] = useState<Team[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>("wins")

  useEffect(() => {
    api
      .teams()
      .then((r) => setTeams(r.teams))
      .catch((e) => setError(String(e)))
  }, [])

  if (error) return <ErrorState message={error} />
  if (!teams) return <LoadingState />

  const sorted = [...teams].sort((a, b) => {
    if (sortKey === "wins") return b.wins - a.wins || b.points_for - a.points_for
    return b[sortKey] - a[sortKey]
  })

  const headers: { key: SortKey; label: string }[] = [
    { key: "wins", label: "Record" },
    { key: "points_for", label: "PF" },
    { key: "points_against", label: "PA" },
  ]

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-3xl font-bold text-text">Standings</h1>

      <div className="overflow-hidden rounded-xl border border-border bg-surface">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-faint">
              <th className="px-4 py-3 font-medium">#</th>
              <th className="px-4 py-3 font-medium">Team</th>
              {headers.map((h) => (
                <th
                  key={h.key}
                  onClick={() => setSortKey(h.key)}
                  className={`cursor-pointer px-4 py-3 text-right font-medium hover:text-text ${
                    sortKey === h.key ? "text-accent" : ""
                  }`}
                >
                  {h.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((t, i) => (
              <tr key={t.team_id} className={`border-b border-border last:border-b-0 ${t.is_self ? "bg-accent-dim/30" : ""}`}>
                <td className="px-4 py-3 text-text-faint">{i + 1}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <TeamBadge name={t.team_name} seed={t.team_id} size="sm" />
                    <span className={t.is_self ? "font-semibold text-accent" : "text-text"}>{t.team_name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-text">
                  {t.wins}-{t.losses}
                  {t.ties ? `-${t.ties}` : ""}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-text-muted">{round1(t.points_for)}</td>
                <td className="px-4 py-3 text-right tabular-nums text-text-muted">{round1(t.points_against)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
