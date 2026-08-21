import type { Meta } from "../lib/types"
import { teamLogoUrl } from "../lib/api"
import { timeAgo } from "../lib/format"
import { useAuth } from "../auth/AuthProvider"
import LeagueSwitcher from "./LeagueSwitcher"
import TeamBadge from "./TeamBadge"

export default function TopBar({ meta }: { meta: Meta | null }) {
  const { accountsEnabled, email, signOut } = useAuth()

  return (
    <header className="flex h-[72px] shrink-0 items-center justify-between gap-4 border-b border-border bg-surface px-4 md:px-8">
      <LeagueSwitcher />

      <div className="flex items-center gap-3">
        <span className="hidden items-center gap-2 rounded-full bg-surface-raised px-3.5 py-2 text-xs font-medium text-text-muted sm:flex">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Synced {timeAgo(meta?.synced_at)}
        </span>

        {meta?.self_team && (
          <div className="flex items-center gap-2.5 rounded-full bg-surface-raised py-1.5 pl-1.5 pr-4">
            <TeamBadge
              name={meta.self_team.team_name}
              seed={meta.self_team.team_id}
              logoUrl={teamLogoUrl(meta.self_team.team_id, meta.self_team.logo_url)}
              size="sm"
            />
            <div className="leading-tight">
              <div className="max-w-[10rem] truncate text-sm font-semibold text-text">
                {meta.self_team.team_name}
              </div>
              <div className="text-xs text-text-faint">
                {meta.self_team.wins}-{meta.self_team.losses}
                {meta.self_team.ties ? `-${meta.self_team.ties}` : ""}
              </div>
            </div>
          </div>
        )}

        {/* Only a deployment with accounts has anything to sign out of. */}
        {accountsEnabled && (
          <button
            onClick={signOut}
            title={email ?? undefined}
            className="rounded-full bg-surface-raised px-4 py-2 text-xs font-semibold text-text-muted transition-colors hover:bg-border/60 hover:text-text"
          >
            Sign out
          </button>
        )}
      </div>
    </header>
  )
}
