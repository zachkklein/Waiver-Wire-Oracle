import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api, teamLogoUrl } from "../lib/api"
import type { Team } from "../lib/types"
import PageHeader from "../components/PageHeader"
import TeamBadge from "../components/TeamBadge"
import { LoadingState, ErrorState } from "../components/EmptyState"
import { round1 } from "../lib/format"

type SortKey = "wins" | "points_for" | "points_against" | "diff"

const HEADERS: { key: SortKey; label: string }[] = [
  { key: "wins", label: "Record" },
  { key: "points_for", label: "For" },
  { key: "points_against", label: "Against" },
  { key: "diff", label: "Diff" },
]

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

  const diff = (t: Team) => t.points_for - t.points_against
  // Every branch ends in a team_id tiebreak so the table can't shuffle between
  // renders when teams are level — which they all are before week 1.
  const sorted = [...teams].sort((a, b) => {
    if (sortKey === "wins") return b.wins - a.wins || b.points_for - a.points_for || a.team_id - b.team_id
    if (sortKey === "diff") return diff(b) - diff(a) || a.team_id - b.team_id
    return b[sortKey] - a[sortKey] || a.team_id - b.team_id
  })

  return (
    <div>
      <PageHeader title="Standings" eyebrow="Top four make the playoffs" />

      <div className="overflow-x-auto rounded-2xl border border-border bg-surface shadow-soft">
        <table className="w-full min-w-[620px]">
          <thead>
            <tr>
              <th className="w-16 py-4 pl-6 text-left text-xs font-medium text-text-muted">#</th>
              <th className="py-4 text-left text-xs font-medium text-text-muted">Team</th>
              {HEADERS.map((h) => (
                <th key={h.key} className="w-28 py-4 pr-6 text-right">
                  <button
                    onClick={() => setSortKey(h.key)}
                    aria-sort={sortKey === h.key ? "descending" : "none"}
                    className={`text-xs font-medium transition-colors ${
                      sortKey === h.key ? "text-accent" : "text-text-muted hover:text-text"
                    }`}
                  >
                    {h.label}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((t, i) => {
              const d = diff(t)
              return (
                <tr
                  key={t.team_id}
                  className={`border-t border-border transition-colors hover:bg-surface-raised ${
                    t.is_self ? "bg-accent/[0.07]" : ""
                  }`}
                >
                  <td className="py-3.5 pl-6">
                    <span
                      className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold tabular-nums ${
                        i < 4 ? "bg-accent/15 text-accent" : "text-text-faint"
                      }`}
                    >
                      {i + 1}
                    </span>
                  </td>
                  <td className="py-3.5">
                    <Link
                      to={t.is_self ? "/roster" : `/roster?team=${encodeURIComponent(t.team_name)}`}
                      className="flex items-center gap-3 hover:underline"
                    >
                      <TeamBadge name={t.team_name} seed={t.team_id} logoUrl={teamLogoUrl(t.team_id, t.logo_url)} size="sm" />
                      <span
                        className={`text-sm ${
                          t.is_self ? "font-bold text-accent" : "font-medium text-text"
                        }`}
                      >
                        {t.team_name}
                      </span>
                    </Link>
                  </td>
                  <td className="py-3.5 pr-6 text-right text-sm font-bold tabular-nums text-text">
                    {t.wins}-{t.losses}
                    {t.ties ? `-${t.ties}` : ""}
                  </td>
                  <td className="py-3.5 pr-6 text-right text-sm tabular-nums text-text-muted">
                    {round1(t.points_for)}
                  </td>
                  <td className="py-3.5 pr-6 text-right text-sm tabular-nums text-text-muted">
                    {round1(t.points_against)}
                  </td>
                  <td
                    className={`py-3.5 pr-6 text-right text-sm font-semibold tabular-nums ${
                      d > 0 ? "text-status-good" : d < 0 ? "text-status-bad" : "text-text-faint"
                    }`}
                  >
                    {d > 0 ? "+" : ""}
                    {round1(d)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
