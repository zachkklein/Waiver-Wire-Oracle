import { authEnabled, authHeaders, cachedAccessToken } from "./auth"
import type {
  ChatMsg,
  ChatStreamEvent,
  League,
  LeaguePreview,
  Meta,
  MatchupsResponse,
  NewLeaguePayload,
  NewsResult,
  PlayerStatLine,
  RosterResponse,
  Settings,
  SettingsPayload,
  SyncStatus,
  SyncTarget,
  Team,
} from "./types"

async function getJSON<T>(path: string, params: Record<string, unknown> = {}): Promise<T> {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") qs.set(key, String(value))
  }
  const query = qs.toString()
  const res = await fetch(`/api${path}${query ? `?${query}` : ""}`, {
    headers: await authHeaders(),
  })
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`)
  return res.json()
}

async function sendJSON<T>(method: "POST" | "PUT", path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    // FastAPI puts human-readable validation/HTTPException messages in `detail`.
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail ?? `${path} failed: ${res.status}`)
  }
  return res.json()
}

async function sendEmpty<T>(method: "PUT" | "DELETE", path: string): Promise<T> {
  const res = await fetch(`/api${path}`, { method, headers: await authHeaders() })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail ?? `${path} failed: ${res.status}`)
  }
  return res.json()
}

export const api = {
  teams: () => getJSON<{ teams: Team[] }>("/teams"),
  roster: (team?: string) => getJSON<RosterResponse>("/roster", { team }),
  matchups: (week?: number, team?: string) => getJSON<MatchupsResponse>("/matchups", { week, team }),
  stats: (params: {
    player_name?: string
    position?: string
    team?: string
    season?: number
    week_min?: number
    week_max?: number
    season_type?: string
    aggregate?: boolean
    sort_by?: string
    limit?: number
  }) => getJSON<PlayerStatLine[]>("/stats", params),
  news: (query: string, params: { n_results?: number; source?: string; since_days?: number } = {}) =>
    getJSON<NewsResult[]>("/news", { query, ...params }),
  meta: () => getJSON<Meta>("/meta"),

  settings: () => getJSON<Settings>("/settings"),
  saveSettings: (payload: SettingsPayload) => sendJSON<Settings>("PUT", "/settings", payload),
  leaguePreview: (payload: {
    ESPN_LEAGUE_ID: string
    ESPN_SEASON: string
    ESPN_SWID?: string
    ESPN_S2?: string
  }) => sendJSON<LeaguePreview>("POST", "/settings/league-preview", payload),

  startSync: (targets?: SyncTarget[]) =>
    sendJSON<{ running: boolean; targets: string[] }>("POST", "/sync", { targets }),
  syncStatus: () => getJSON<SyncStatus>("/sync"),

  leagues: () => getJSON<League[]>("/leagues"),
  addLeague: (payload: NewLeaguePayload) => sendJSON<League[]>("POST", "/leagues", payload),
  activateLeague: (leagueId: string) =>
    sendEmpty<League[]>("PUT", `/leagues/${encodeURIComponent(leagueId)}/activate`),
  removeLeague: (leagueId: string) =>
    sendEmpty<League[]>("DELETE", `/leagues/${encodeURIComponent(leagueId)}`),
}

/** Team logos are served through the app rather than linked straight to ESPN: members'
 * own uploads live behind ESPN's auth cookies, which the browser doesn't have. A team
 * with no synced logo gets null so `TeamBadge` falls back to initials.
 *
 * This is the one endpoint whose token rides in the query string: the browser reaches it
 * through `<img src>`, which can't carry an Authorization header. If the cached token has
 * gone stale the image 401s and `TeamBadge` falls back to initials until the next render. */
export function teamLogoUrl(teamId: number, logoUrl: string | null | undefined): string | null {
  if (!logoUrl) return null
  const token = authEnabled() ? cachedAccessToken() : null
  return token
    ? `/api/team-logo/${teamId}?access_token=${encodeURIComponent(token)}`
    : `/api/team-logo/${teamId}`
}

export async function* streamChat(messages: ChatMsg[]): AsyncGenerator<ChatStreamEvent> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ messages }),
  })
  if (!res.ok || !res.body) throw new Error(`chat failed: ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split("\n")
    buffer = lines.pop() ?? ""
    for (const line of lines) {
      if (!line.trim()) continue
      yield JSON.parse(line) as ChatStreamEvent
    }
  }
  if (buffer.trim()) yield JSON.parse(buffer) as ChatStreamEvent
}
