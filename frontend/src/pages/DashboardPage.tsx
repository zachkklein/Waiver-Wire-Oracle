import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api } from "../lib/api"
import type { Meta, MatchupsResponse, Team } from "../lib/types"
import Card from "../components/Card"
import MatchupCard from "../components/MatchupCard"
import TeamBadge from "../components/TeamBadge"
import { LoadingState, ErrorState } from "../components/EmptyState"
import { round1 } from "../lib/format"

export default function DashboardPage() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [matchups, setMatchups] = useState<MatchupsResponse | null>(null)
  const [teams, setTeams] = useState<Team[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.meta(), api.matchups(), api.teams()])
      .then(([m, mu, t]) => {
        setMeta(m)
        setMatchups(mu)
        setTeams(t.teams)
      })
      .catch((e) => setError(String(e)))
  }, [])

  if (error) return <ErrorState message={error} />
  if (!meta) return <LoadingState />

  const selfMatchup = matchups?.matchups.find((m) => m.is_self)
  const rankedTeams = [...(teams ?? [])].sort(
    (a, b) => b.wins - a.wins || b.points_for - a.points_for,
  )
  const selfRank = rankedTeams.findIndex((t) => t.is_self) + 1

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-3xl font-bold text-text">
          {meta.self_team?.team_name ?? "Dashboard"}
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          {meta.self_team
            ? `${meta.self_team.wins}-${meta.self_team.losses}${meta.self_team.ties ? `-${meta.self_team.ties}` : ""} · Rank #${selfRank || "—"} of ${rankedTeams.length}`
            : "Run espn_sync.py to load your team"}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card title="Your Matchup" className="lg:col-span-2">
          {selfMatchup ? (
            <MatchupCard matchup={selfMatchup} />
          ) : (
            <p className="text-sm text-text-faint">No matchup synced for this week yet.</p>
          )}
        </Card>

        <Card title="Standings" action={<Link to="/standings" className="text-xs text-accent hover:underline">View all</Link>}>
          <div className="flex flex-col gap-2">
            {rankedTeams.slice(0, 5).map((t, i) => (
              <div key={t.team_id} className="flex items-center gap-3">
                <span className="w-4 text-xs text-text-faint">{i + 1}</span>
                <TeamBadge name={t.team_name} seed={t.team_id} size="sm" />
                <span className={`flex-1 truncate text-sm ${t.is_self ? "font-semibold text-accent" : "text-text"}`}>
                  {t.team_name}
                </span>
                <span className="text-xs text-text-muted">
                  {t.wins}-{t.losses}
                </span>
                <span className="w-12 text-right text-xs tabular-nums text-text-faint">{round1(t.points_for)}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Link to="/roster" className="rounded-xl border border-border bg-surface p-4 transition-colors hover:border-accent/40">
          <div className="font-display text-lg font-bold text-text">My Team</div>
          <div className="text-sm text-text-muted">Starters, bench, injuries</div>
        </Link>
        <Link to="/players" className="rounded-xl border border-border bg-surface p-4 transition-colors hover:border-accent/40">
          <div className="font-display text-lg font-bold text-text">Players</div>
          <div className="text-sm text-text-muted">{meta.player_stats_rows.toLocaleString()} stat lines synced</div>
        </Link>
        <Link to="/chat" className="rounded-xl border border-border bg-surface p-4 transition-colors hover:border-accent/40">
          <div className="font-display text-lg font-bold text-text">Ask the Oracle</div>
          <div className="text-sm text-text-muted">Start/sit and waiver advice</div>
        </Link>
      </div>
    </div>
  )
}
