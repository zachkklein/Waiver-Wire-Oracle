export interface Team {
  team_id: number
  team_name: string
  wins: number
  losses: number
  ties: number
  points_for: number
  points_against: number
  is_self: number
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
  self_team: { team_id: number; team_name: string; wins: number; losses: number; ties: number } | null
  current_week: number | null
  synced_at: { teams: string | null; rosters: string | null; matchups: string | null }
  player_stats_rows: number
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
