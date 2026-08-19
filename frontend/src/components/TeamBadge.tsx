const PALETTE = ["#2fe08a", "#3b82f6", "#ef4444", "#f97316", "#a855f7", "#eab308", "#14b8a6", "#f472b6"]

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return "?"
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}

function colorFor(seed: number): string {
  return PALETTE[seed % PALETTE.length]
}

export default function TeamBadge({
  name,
  seed,
  size = "md",
}: {
  name: string
  seed: number
  size?: "sm" | "md" | "lg"
}) {
  const dims = size === "sm" ? "h-7 w-7 text-xs" : size === "lg" ? "h-12 w-12 text-lg" : "h-9 w-9 text-sm"
  const color = colorFor(seed)
  return (
    <div
      className={`flex shrink-0 items-center justify-center rounded-full font-display font-bold text-bg ${dims}`}
      style={{ backgroundColor: color }}
    >
      {initials(name)}
    </div>
  )
}
