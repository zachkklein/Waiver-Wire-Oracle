import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api, teamLogoUrl } from "../lib/api"
import type { Meta, MatchupsResponse, Team } from "../lib/types"
import Card from "../components/Card"
import MatchupCard from "../components/MatchupCard"
import TeamBadge from "../components/TeamBadge"
import { LoadingState, ErrorState } from "../components/EmptyState"
import { round1 } from "../lib/format"

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-surface px-5 py-3.5">
      <div className="text-xs text-text-muted">{label}</div>
      <div className="mt-1 text-2xl font-extrabold tabular-nums text-text">{value}</div>
    </div>
  )
}

const STANDINGS_WINDOW = 5

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
  const ranked = [...(teams ?? [])].sort((a, b) => b.wins - a.wins || b.points_for - a.points_for)
  const selfIndex = ranked.findIndex((t) => t.is_self)
  const selfRank = selfIndex + 1
  const selfTeam = ranked[selfIndex]

  // Show a five-team window centred on your own rank, clamped at either end of the
  // table — so you always see two rivals above and two below, or the nearest five
  // when you're near the top or bottom. The full table lives on /standings.
  const windowStart = Math.min(
    Math.max((selfIndex < 0 ? 0 : selfIndex) - 2, 0),
    Math.max(ranked.length - STANDINGS_WINDOW, 0),
  )
  const nearbyTeams = ranked.slice(windowStart, windowStart + STANDINGS_WINDOW)

  return (
    // Fixed to the viewport on desktop so the dashboard never scrolls: the header,
    // stat row and shortcut row hold their natural heights and the matchup/standings
    // row absorbs whatever is left. Mobile stacks and scrolls as usual.
    <div className="flex flex-col gap-4 lg:h-full lg:min-h-0">
      <header className="shrink-0">
        <h1 className="font-display soft text-[30px] font-semibold leading-tight text-text md:text-[40px]">
          {meta.self_team?.team_name ?? "Dashboard"}
        </h1>
        <p className="mt-1.5 text-sm text-text-muted">
          {meta.current_week ? `Week ${meta.current_week} · ` : ""}
          {selfRank ? `Sitting ${selfRank} of ${ranked.length}` : "Season not started"}
        </p>
      </header>

      {selfTeam && (
        <div className="grid shrink-0 grid-cols-2 gap-3 md:grid-cols-4">
          <Stat
            label="Record"
            value={`${selfTeam.wins}-${selfTeam.losses}${selfTeam.ties ? `-${selfTeam.ties}` : ""}`}
          />
          <Stat label="League rank" value={selfRank ? `${selfRank}` : "—"} />
          <Stat label="Points for" value={round1(selfTeam.points_for)} />
          <Stat label="Points against" value={round1(selfTeam.points_against)} />
        </div>
      )}

      {/* No min-h-0 here on purpose: the row never shrinks below the five standings
          rows, it only absorbs spare height. On a window too short for even that, the
          page falls back to scrolling rather than clipping the table. */}
      <div className="grid grid-cols-1 gap-4 lg:flex-1 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {selfMatchup ? (
            <MatchupCard matchup={selfMatchup} featured className="lg:h-full" />
          ) : (
            <Card title="Your matchup">
              <p className="text-sm text-text-muted">
                No matchup synced for this week yet. Run{" "}
                <code className="rounded-md bg-surface-raised px-1.5 py-0.5 text-[13px] text-accent">
                  main.py sync espn
                </code>{" "}
                to pull it in.
              </p>
            </Card>
          )}
        </div>

        <Card
          title="Standings"
          className="lg:h-full"
          bodyClassName="px-3 pb-3 pt-2"
          action={
            <Link to="/standings" className="text-xs font-semibold text-accent hover:underline">
              View all
            </Link>
          }
        >
          {nearbyTeams.map((t, i) => (
            <Link
              key={t.team_id}
              to={t.is_self ? "/roster" : `/roster?team=${encodeURIComponent(t.team_name)}`}
              className={`flex items-center gap-3 rounded-xl px-2 py-1 transition-colors hover:bg-surface-raised ${
                t.is_self ? "bg-accent/10" : ""
              }`}
            >
              <span className="w-4 text-xs font-semibold tabular-nums text-text-faint">
                {windowStart + i + 1}
              </span>
              <TeamBadge name={t.team_name} seed={t.team_id} logoUrl={teamLogoUrl(t.team_id, t.logo_url)} size="sm" />
              <span
                className={`flex-1 truncate text-sm hover:underline ${
                  t.is_self ? "font-semibold text-accent" : "text-text-muted"
                }`}
              >
                {t.team_name}
              </span>
              <span className="text-sm font-semibold tabular-nums text-text">
                {t.wins}-{t.losses}
              </span>
            </Link>
          ))}
        </Card>
      </div>

      <div className="grid shrink-0 grid-cols-1 gap-4 sm:grid-cols-3">
        {[
          { to: "/roster", title: "My Team", copy: "Starters, bench, injury report" },
          {
            to: "/players",
            title: "Players",
            copy: `${meta.player_stats_rows.toLocaleString()} stat lines synced`,
          },
          { to: "/chat", title: "Ask the Oracle", copy: "Start/sit and waiver calls" },
        ].map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className="group rounded-2xl border border-border bg-surface p-4 shadow-soft transition-all hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-lift"
          >
            <div className="font-display soft text-base font-semibold text-text group-hover:text-accent">
              {link.title}
            </div>
            <div className="mt-1 text-sm text-text-muted">{link.copy}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}
