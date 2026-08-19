import { useEffect, useState } from "react"
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom"
import Sidebar from "./components/Sidebar"
import TopBar from "./components/TopBar"
import { api } from "./lib/api"
import type { Meta } from "./lib/types"

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const navigate = useNavigate()
  const { pathname } = useLocation()

  useEffect(() => {
    api
      .meta()
      .then((m) => {
        setMeta(m)
        // A fresh install has nothing to show — send them straight to setup.
        if (!m.configured && pathname !== "/setup") navigate("/setup", { replace: true })
      })
      .catch(() => setMeta(null))
  }, [pathname, navigate])

  const needsSync = meta?.configured && !meta.has_data && pathname !== "/setup"

  return (
    <div className="flex h-screen flex-col bg-bg md:flex-row">
      <Sidebar />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <TopBar meta={meta} />
        <main className="flex-1 overflow-y-auto px-4 py-5 md:px-8 md:py-7">
          {needsSync && (
            <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-accent/40 bg-accent/10 px-5 py-4">
              <span className="text-sm text-text">
                Your league is configured, but nothing has been synced yet.
              </span>
              <Link
                to="/setup"
                className="rounded-full bg-accent px-5 py-2 text-sm font-bold text-bg hover:bg-accent-strong"
              >
                Sync now
              </Link>
            </div>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  )
}
