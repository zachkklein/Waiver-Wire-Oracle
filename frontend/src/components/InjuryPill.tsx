const BAD = new Set(["OUT", "IR", "PUP", "SUSPENSION", "DOUBTFUL"])
const WARN = new Set(["QUESTIONABLE", "Q"])

export default function InjuryPill({ status }: { status: string | null | undefined }) {
  if (!status) return null
  const s = status.toUpperCase()
  if (s === "ACTIVE" || s === "NORMAL" || s === "") return null

  const style = BAD.has(s)
    ? "bg-status-bad/15 text-status-bad border-status-bad/30"
    : WARN.has(s)
      ? "bg-status-warn/15 text-status-warn border-status-warn/30"
      : "bg-text-faint/15 text-text-faint border-text-faint/30"

  return (
    <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${style}`}>
      {s}
    </span>
  )
}
