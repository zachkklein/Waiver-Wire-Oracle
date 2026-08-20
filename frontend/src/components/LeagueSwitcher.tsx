import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "../lib/api"
import type { League } from "../lib/types"

export default function LeagueSwitcher() {
  const [leagues, setLeagues] = useState<League[] | null>(null)
  const [open, setOpen] = useState(false)
  const [switching, setSwitching] = useState(false)
  const ref = useRef<HTMLDivElement | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    api
      .leagues()
      .then(setLeagues)
      .catch(() => setLeagues([]))
  }, [])

  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", onClick)
    return () => document.removeEventListener("mousedown", onClick)
  }, [open])

  if (!leagues || leagues.length === 0) return null

  const active = leagues.find((l) => l.active) ?? leagues[0]

  const switchTo = async (leagueId: string) => {
    setOpen(false)
    if (leagueId === active.league_id) return
    setSwitching(true)
    try {
      await api.activateLeague(leagueId)
      // Every page's data is scoped server-side to the active league and fetched on
      // mount — a full reload is the simplest way to refresh everything at once.
      window.location.reload()
    } catch {
      setSwitching(false)
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={switching}
        className="flex items-center gap-2 rounded-full bg-surface-raised px-4 py-2 text-sm font-semibold text-text transition-colors hover:bg-border/60 disabled:opacity-60"
      >
        <span className="max-w-[10rem] truncate">{switching ? "Switching…" : active.label}</span>
        <svg width="12" height="12" viewBox="0 0 12 12" className="shrink-0 text-text-faint">
          <path
            d="M2.5 4.5L6 8l3.5-3.5"
            stroke="currentColor"
            strokeWidth="1.5"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 top-[calc(100%+8px)] z-20 w-64 rounded-2xl border border-border bg-surface p-1.5 shadow-lift">
          {leagues.map((l) => (
            <button
              key={l.league_id}
              onClick={() => switchTo(l.league_id)}
              className={`flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2.5 text-left text-sm transition-colors ${
                l.active ? "bg-accent/15 text-accent" : "text-text hover:bg-surface-raised"
              }`}
            >
              <span className="truncate font-medium">{l.label}</span>
              {l.season && <span className="shrink-0 text-xs text-text-faint">{l.season}</span>}
            </button>
          ))}
          <button
            onClick={() => {
              setOpen(false)
              navigate("/setup?new=1")
            }}
            className="mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm font-semibold text-accent hover:bg-surface-raised"
          >
            + Add another league
          </button>
        </div>
      )}
    </div>
  )
}
