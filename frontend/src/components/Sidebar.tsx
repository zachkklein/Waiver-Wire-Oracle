import { NavLink } from "react-router-dom"

const LINKS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/roster", label: "My Team" },
  { to: "/matchups", label: "Matchups" },
  { to: "/standings", label: "Standings" },
  { to: "/players", label: "Players" },
  { to: "/news", label: "News" },
  { to: "/chat", label: "Oracle" },
]

export default function Sidebar() {
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex h-16 items-center gap-2 border-b border-border px-5">
        <span className="text-xl">🏈</span>
        <span className="font-display text-lg font-bold tracking-wide text-text">
          Waiver Wire <span className="text-accent">Oracle</span>
        </span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {LINKS.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.end}
            className={({ isActive }) =>
              `rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-accent-dim text-accent"
                  : "text-text-muted hover:bg-surface-raised hover:text-text"
              }`
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
