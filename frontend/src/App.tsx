import { useEffect, useState } from "react"
import { Outlet } from "react-router-dom"
import Sidebar from "./components/Sidebar"
import TopBar from "./components/TopBar"
import { api } from "./lib/api"
import type { Meta } from "./lib/types"

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)

  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null))
  }, [])

  return (
    <div className="flex h-screen bg-bg">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar meta={meta} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
