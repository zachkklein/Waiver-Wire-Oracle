import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import AuthProvider from './auth/AuthProvider.tsx'
import AuthGate from './auth/AuthGate.tsx'
import DashboardPage from './pages/DashboardPage.tsx'
import RosterPage from './pages/RosterPage.tsx'
import MatchupsPage from './pages/MatchupsPage.tsx'
import StandingsPage from './pages/StandingsPage.tsx'
import PlayersPage from './pages/PlayersPage.tsx'
import NewsPage from './pages/NewsPage.tsx'
import ChatPage from './pages/ChatPage.tsx'
import SetupPage from './pages/SetupPage.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      {/* AuthProvider sits inside the router because the sign-in screen and the pages
          behind the gate both use router hooks. On a self-hosted install the gate
          resolves to "no accounts here" and renders straight through. */}
      <AuthProvider>
        <AuthGate>
          <Routes>
            <Route element={<App />}>
              <Route index element={<DashboardPage />} />
              <Route path="roster" element={<RosterPage />} />
              <Route path="matchups" element={<MatchupsPage />} />
              <Route path="standings" element={<StandingsPage />} />
              <Route path="players" element={<PlayersPage />} />
              <Route path="news" element={<NewsPage />} />
              <Route path="chat" element={<ChatPage />} />
              <Route path="setup" element={<SetupPage />} />
            </Route>
          </Routes>
        </AuthGate>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
