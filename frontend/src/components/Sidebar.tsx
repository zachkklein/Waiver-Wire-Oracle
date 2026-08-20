import { NavLink } from "react-router-dom"

const LINKS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/roster", label: "My Team" },
  { to: "/matchups", label: "Matchups" },
  { to: "/standings", label: "Standings" },
  { to: "/players", label: "Players" },
  { to: "/news", label: "News" },
  { to: "/chat", label: "Oracle" },
  { to: "/setup", label: "Setup" },
]

export default function Sidebar() {
  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-border bg-surface md:w-64 md:border-b-0 md:border-r">
      <div className="flex items-center gap-3 px-5 py-5 md:px-6 md:py-7">
        <img
          src="/waiverLogo.png"
          alt=""
          aria-hidden
          className="h-11 w-11 shrink-0 object-contain"
        />
        <span className="font-display soft text-[17px] font-semibold leading-[1.15] text-text">
          Waiver Wire
          <br />
          <span className="text-accent">Oracle</span>
        </span>
      </div>

      <nav className="flex flex-row gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:overflow-x-visible md:px-4 md:pb-4">
        {LINKS.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.end}
            className={({ isActive }) =>
              `shrink-0 whitespace-nowrap rounded-full px-4 py-2.5 text-sm font-semibold transition-colors ${
                isActive
                  ? "bg-accent/15 text-accent"
                  : "text-text-muted hover:bg-surface-raised hover:text-text"
              }`
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>

      <div className="hidden px-6 py-5 text-xs text-text-faint md:block">Runs locally</div>
    </aside>
  )
}
