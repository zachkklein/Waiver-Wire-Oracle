import type {
  ChatMsg,
  ChatStreamEvent,
  Meta,
  MatchupsResponse,
  NewsResult,
  PlayerStatLine,
  RosterResponse,
  Team,
} from "./types"

async function getJSON<T>(path: string, params: Record<string, unknown> = {}): Promise<T> {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") qs.set(key, String(value))
  }
  const query = qs.toString()
  const res = await fetch(`/api${path}${query ? `?${query}` : ""}`)
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`)
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
}

export async function* streamChat(messages: ChatMsg[]): AsyncGenerator<ChatStreamEvent> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
