import type { Meta } from "../lib/types"
import { timeAgo } from "../lib/format"

export default function TopBar({ meta }: { meta: Meta | null }) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-surface px-6">
      <div className="font-display text-lg font-bold text-text">
        {meta?.current_week ? `Week ${meta.current_week}` : "—"}
      </div>
      <div className="flex items-center gap-4 text-sm text-text-muted">
        {meta?.self_team && (
          <span>
            <span className="text-text">{meta.self_team.team_name}</span>{" "}
            <span className="text-text-faint">
              ({meta.self_team.wins}-{meta.self_team.losses}
              {meta.self_team.ties ? `-${meta.self_team.ties}` : ""})
            </span>
          </span>
        )}
        <span className="flex items-center gap-1.5 rounded-full border border-border bg-surface-raised px-3 py-1">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Synced {timeAgo(meta?.synced_at.teams)}
        </span>
      </div>
    </header>
  )
}
