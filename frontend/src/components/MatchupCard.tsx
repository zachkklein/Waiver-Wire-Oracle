import type { Matchup } from "../lib/types"
import TeamBadge from "./TeamBadge"
import { teamLogoUrl } from "../lib/api"
import { round1 } from "../lib/format"

/**
 * Head-to-head card. The bar under the scores splits proportionally to each
 * side's projection, so "who's favored, and by how much" reads at a glance.
 */
export default function MatchupCard({
  matchup,
  featured = false,
  className = "",
}: {
  matchup: Matchup
  featured?: boolean
  className?: string
}) {
  const homeProj = matchup.home_projected || 0
  const awayProj = matchup.away_projected || 0
  const total = homeProj + awayProj
  const homeShare = total > 0 ? (homeProj / total) * 100 : 50

  const homeLeads = matchup.home_score > matchup.away_score
  const awayLeads = matchup.away_score > matchup.home_score
  const homeFavored = homeProj >= awayProj

  const nameSize = featured ? "text-lg md:text-xl" : "text-sm"
  const scoreSize = featured ? "text-4xl md:text-5xl" : "text-2xl"
  const avatar = featured ? "md" : "sm"

  return (
    <article
      className={`flex flex-col rounded-2xl border bg-surface shadow-soft ${
        matchup.is_self ? "border-accent/40" : "border-border"
      } ${featured ? "p-6 md:p-7" : "p-5"} ${className}`}
    >
      <div className="mb-5 flex items-center justify-between gap-3">
        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold ${
            matchup.is_self ? "bg-accent/15 text-accent" : "bg-surface-raised text-text-muted"
          }`}
        >
          {matchup.is_self ? "Your matchup" : `Week ${matchup.week}`}
        </span>
        {matchup.is_playoff ? (
          <span className="rounded-full bg-accent/15 px-3 py-1 text-xs font-semibold text-accent">
            Playoff
          </span>
        ) : null}
      </div>

      {/* When the card is stretched to fill a row (the dashboard's featured slot), the
          teams take the slack and stay centred rather than leaving a gap underneath. */}
      <div
        className={`flex justify-between gap-4 ${
          featured ? "flex-1 items-center" : "items-start"
        }`}
      >
        <div className="min-w-0 flex-1">
          <TeamBadge
            name={matchup.home_team_name}
            seed={matchup.home_team_id}
            logoUrl={teamLogoUrl(matchup.home_team_id, matchup.home_logo_url)}
            size={avatar}
          />
          <h3
            className={`mt-3 font-display soft ${nameSize} font-semibold leading-snug ${
              awayLeads ? "text-text-muted" : "text-text"
            }`}
          >
            {matchup.home_team_name}
          </h3>
          <div
            className={`mt-1 ${scoreSize} font-extrabold leading-none tabular-nums ${
              homeLeads ? "text-accent" : "text-text"
            }`}
          >
            {round1(matchup.home_score)}
          </div>
        </div>

        <div className="min-w-0 flex-1 text-right">
          <div className="flex justify-end">
            <TeamBadge
              name={matchup.away_team_name}
              seed={matchup.away_team_id}
              logoUrl={teamLogoUrl(matchup.away_team_id, matchup.away_logo_url)}
              size={avatar}
            />
          </div>
          <h3
            className={`mt-3 font-display soft ${nameSize} font-semibold leading-snug ${
              homeLeads ? "text-text-muted" : "text-text"
            }`}
          >
            {matchup.away_team_name}
          </h3>
          <div
            className={`mt-1 ${scoreSize} font-extrabold leading-none tabular-nums ${
              awayLeads ? "text-accent" : "text-text"
            }`}
          >
            {round1(matchup.away_score)}
          </div>
        </div>
      </div>

      <div className={featured ? "mt-8" : "mt-6"}>
        <div className="relative h-2.5 overflow-hidden rounded-full bg-surface-raised">
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-accent/70"
            style={{ width: `${homeShare}%` }}
          />
        </div>
        <div className="mt-2.5 flex items-center justify-between text-xs">
          <span className={homeFavored ? "font-semibold text-accent" : "text-text-faint"}>
            Projected {round1(homeProj)}
          </span>
          <span className={!homeFavored ? "font-semibold text-accent" : "text-text-faint"}>
            Projected {round1(awayProj)}
          </span>
        </div>
      </div>
    </article>
  )
}
