const POSITION_STYLES: Record<string, string> = {
  QB: "bg-pos-qb/15 text-pos-qb border-pos-qb/30",
  RB: "bg-pos-rb/15 text-pos-rb border-pos-rb/30",
  WR: "bg-pos-wr/15 text-pos-wr border-pos-wr/30",
  TE: "bg-pos-te/15 text-pos-te border-pos-te/30",
  K: "bg-pos-k/15 text-pos-k border-pos-k/30",
  "D/ST": "bg-pos-dst/15 text-pos-dst border-pos-dst/30",
  FLEX: "bg-pos-flex/15 text-pos-flex border-pos-flex/30",
}

export default function PositionBadge({ position }: { position: string }) {
  const style = POSITION_STYLES[position] ?? "bg-text-faint/15 text-text-faint border-text-faint/30"
  return (
    <span
      className={`inline-flex items-center justify-center rounded border px-1.5 py-0.5 font-display text-xs font-bold tracking-wide ${style}`}
    >
      {position}
    </span>
  )
}
