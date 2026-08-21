export interface Team {
  team_id: number
  team_name: string
  wins: number
  losses: number
  ties: number
  points_for: number
  points_against: number
  is_self: number
  logo_url: string | null
}

export interface RosterPlayer {
  player_name: string
  position: string
  pro_team: string
  lineup_slot: string
  injury_status: string
  total_points: number
  projected_total_points: number
}

export interface RosterResponse {
  team: {
    team_id: number
    team_name: string
    wins: number
    losses: number
    logo_url: string | null
  }
  players: RosterPlayer[]
  error?: string
}

export interface Matchup {
  week: number
  home_team_id: number
  away_team_id: number
  home_team_name: string
  away_team_name: string
  home_score: number
  away_score: number
  home_projected: number
  away_projected: number
  is_playoff: number
  is_self: number
  home_logo_url: string | null
  away_logo_url: string | null
}

export interface MatchupsResponse {
  week: number
  matchups: Matchup[]
  error?: string
}

export interface PlayerStatLine {
  player_id: string
  player_display_name: string
  player_name: string
  position: string
  recent_team: string
  season?: number
  week?: number
  season_type?: string
  opponent_team?: string
  games_played?: number
  completions: number
  attempts: number
  passing_yards: number
  passing_tds: number
  interceptions: number
  carries: number
  rushing_yards: number
  rushing_tds: number
  receptions: number
  targets: number
  receiving_yards: number
  receiving_tds: number
  fumbles_lost: number
  fantasy_points: number
  fantasy_points_ppr: number
}

export interface NewsResult {
  title: string
  source: string
  link: string
  published: string
  snippet: string
  distance: number
}

export interface Meta {
  self_team: {
    team_id: number
    team_name: string
    wins: number
    losses: number
    ties: number
    logo_url: string | null
  } | null
  current_week: number | null
  synced_at: string | null
  player_stats_rows: number
  configured: boolean
  has_data: boolean
}

export interface Settings {
  ESPN_LEAGUE_ID: string
  ESPN_SEASON: string
  ESPN_TEAM_ID: string
  OPENROUTER_MODEL: string
  RSS_FEED_URLS: string[]
  configured: boolean
  has_espn_swid: boolean
  has_espn_s2: boolean
  has_openrouter_api_key: boolean
}

export interface SettingsPayload {
  ESPN_LEAGUE_ID?: string
  ESPN_SEASON?: string
  ESPN_SWID?: string
  ESPN_S2?: string
  ESPN_TEAM_ID?: string
  label?: string
  OPENROUTER_API_KEY?: string
  OPENROUTER_MODEL?: string
  RSS_FEED_URLS?: string[]
}

export interface LeaguePreview {
  league_name: string | null
  current_week: number
  teams: { team_id: number; team_name: string }[]
}

export interface League {
  league_id: string
  label: string
  season: string
  active: boolean
  has_espn_swid: boolean
  has_espn_s2: boolean
}

export interface NewLeaguePayload {
  ESPN_LEAGUE_ID: string
  ESPN_SEASON: string
  label?: string
  ESPN_SWID?: string
  ESPN_S2?: string
  ESPN_TEAM_ID?: string
}

/** Served unauthenticated by GET /api/auth/config. `enabled: false` is the
 * self-hosted install: no sign-in screen, no tokens on requests. `publishable_key` is
 * Supabase's publishable key (`sb_publishable_...`), which is meant to ship in the
 * browser — it is never a secret or service-role key. */
export interface AuthConfig {
  enabled: boolean
  url: string | null
  publishable_key: string | null
}

export type SyncTarget = "espn" | "stats" | "news"

export interface SyncStatus {
  running: boolean
  results: Record<string, { ok: boolean; detail: string; self_team_found?: boolean }>
  started_at: string | null
  finished_at: string | null
}

export interface ChatMsg {
  role: "user" | "assistant"
  content: string
}

export type ChatStreamEvent =
  | { type: "token"; content: string }
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; name: string }
  | { type: "done" }
  | { type: "error"; message: string }
