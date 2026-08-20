import { useEffect, useState } from "react"

// Muted, turf-compatible tones — distinct enough to tell teams apart
// without competing with brass for attention.
const PALETTE = ["#d9a93f", "#5b9dd9", "#e2574c", "#57c08a", "#a98bd1", "#e08a3c", "#4fb0a8", "#c2708f"]

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return "?"
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}

export default function TeamBadge({
  name,
  seed,
  logoUrl,
  size = "md",
}: {
  name: string
  seed: number
  logoUrl?: string | null
  size?: "sm" | "md" | "lg"
}) {
  // ESPN hosts these on its own CDN; a dead or blocked URL falls back to initials.
  const [broken, setBroken] = useState(false)
  useEffect(() => setBroken(false), [logoUrl])

  const dims =
    size === "sm" ? "h-9 w-9 text-xs" : size === "lg" ? "h-14 w-14 text-lg" : "h-11 w-11 text-sm"

  if (logoUrl && !broken) {
    return (
      <img
        aria-hidden
        src={logoUrl}
        alt=""
        loading="lazy"
        onError={() => setBroken(true)}
        className={`shrink-0 rounded-full bg-surface-raised object-cover ${dims}`}
      />
    )
  }

  return (
    <div
      aria-hidden
      className={`flex shrink-0 items-center justify-center rounded-full font-bold text-bg ${dims}`}
      style={{ backgroundColor: PALETTE[seed % PALETTE.length] }}
    >
      {initials(name)}
    </div>
  )
}
