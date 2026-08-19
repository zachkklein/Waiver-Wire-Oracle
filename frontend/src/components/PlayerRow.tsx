import type { RosterPlayer } from "../lib/types"
import PositionBadge from "./PositionBadge"
import InjuryPill from "./InjuryPill"
import { round1 } from "../lib/format"

export default function PlayerRow({ player }: { player: RosterPlayer }) {
  return (
    <div className="flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-surface-raised">
      <span className="w-12 shrink-0 text-xs font-semibold text-text-faint">
        {player.lineup_slot}
      </span>
      <PositionBadge position={player.position} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-text">{player.player_name}</div>
        <div className="text-xs text-text-faint">{player.pro_team}</div>
      </div>
      <InjuryPill status={player.injury_status} />
      <div className="w-16 shrink-0 text-right">
        <div className="text-sm font-bold tabular-nums text-text">{round1(player.total_points)}</div>
        <div className="text-xs tabular-nums text-text-faint">
          {round1(player.projected_total_points)}
        </div>
      </div>
    </div>
  )
}
