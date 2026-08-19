import type { Matchup } from "../lib/types"
import TeamBadge from "./TeamBadge"
import { round1 } from "../lib/format"

function TeamRow({
  name,
  seed,
  score,
  projected,
  winning,
}: {
  name: string
  seed: number
  score: number
  projected: number
  winning: boolean
}) {
  return (
    <div className="flex items-center gap-3 py-2">
      <TeamBadge name={name} seed={seed} size="sm" />
      <div className="min-w-0 flex-1">
        <div className={`truncate text-sm font-medium ${winning ? "text-text" : "text-text-muted"}`}>{name}</div>
        <div className="text-xs text-text-faint">proj {round1(projected)}</div>
      </div>
      <div className={`font-display text-2xl font-bold tabular-nums ${winning ? "text-accent" : "text-text"}`}>
        {round1(score)}
      </div>
    </div>
  )
}

export default function MatchupCard({ matchup }: { matchup: Matchup }) {
  const homeWinning = matchup.home_score >= matchup.away_score
  return (
    <div
      className={`rounded-xl border bg-surface p-4 ${
        matchup.is_self ? "border-accent/50 shadow-[0_0_0_1px_rgba(47,224,138,0.15)]" : "border-border"
      }`}
    >
      {matchup.is_self ? (
        <div className="mb-1 inline-block rounded-full bg-accent-dim px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-accent">
          Your Matchup
        </div>
      ) : null}
      <TeamRow
        name={matchup.home_team_name}
        seed={matchup.home_team_id}
        score={matchup.home_score}
        projected={matchup.home_projected}
        winning={homeWinning}
      />
      <div className="border-t border-border" />
      <TeamRow
        name={matchup.away_team_name}
        seed={matchup.away_team_id}
        score={matchup.away_score}
        projected={matchup.away_projected}
        winning={!homeWinning}
      />
    </div>
  )
}
