const BAD = new Set(["OUT", "IR", "PUP", "SUSPENSION", "DOUBTFUL"])
const WARN = new Set(["QUESTIONABLE", "Q"])

const LABEL: Record<string, string> = {
  QUESTIONABLE: "Questionable",
  DOUBTFUL: "Doubtful",
  SUSPENSION: "Suspended",
  OUT: "Out",
  IR: "IR",
  PUP: "PUP",
}

export default function InjuryPill({ status }: { status: string | null | undefined }) {
  if (!status) return null
  const s = status.toUpperCase()
  if (s === "ACTIVE" || s === "NORMAL") return null

  const style = BAD.has(s)
    ? "bg-status-bad/15 text-status-bad"
    : WARN.has(s)
      ? "bg-status-warn/15 text-status-warn"
      : "bg-text-faint/15 text-text-faint"

  return (
    <span className={`inline-flex h-6 items-center rounded-full px-2.5 text-[11px] font-semibold ${style}`}>
      {LABEL[s] ?? status}
    </span>
  )
}
