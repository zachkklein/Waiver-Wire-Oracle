const POSITION_STYLES: Record<string, string> = {
  QB: "bg-pos-qb/15 text-pos-qb",
  RB: "bg-pos-rb/15 text-pos-rb",
  WR: "bg-pos-wr/15 text-pos-wr",
  TE: "bg-pos-te/15 text-pos-te",
  K: "bg-pos-k/15 text-pos-k",
  "D/ST": "bg-pos-dst/20 text-pos-dst",
  DST: "bg-pos-dst/20 text-pos-dst",
  FLEX: "bg-pos-flex/15 text-pos-flex",
}

export default function PositionBadge({ position }: { position: string }) {
  const style = POSITION_STYLES[position] ?? "bg-text-faint/15 text-text-faint"
  return (
    <span
      className={`inline-flex h-6 min-w-[2.5rem] items-center justify-center rounded-full px-2 text-[11px] font-bold ${style}`}
    >
      {position}
    </span>
  )
}
