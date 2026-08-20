-- League-scoped data, synced from ESPN. Identical to the definitions in
-- ingest/espn_sync.py so the app's init_db() is a no-op against this database.
-- Booleans stay INTEGER 0/1 rather than BOOLEAN: the frontend guards them with a
-- ternary and expects a number.
CREATE TABLE IF NOT EXISTS teams (
    league_id TEXT,
    team_id INTEGER,
    team_name TEXT,
    wins INTEGER,
    losses INTEGER,
    ties INTEGER,
    points_for REAL,
    points_against REAL,
    is_self INTEGER,
    logo_url TEXT,
    updated_at TEXT,
    PRIMARY KEY (league_id, team_id)
);

CREATE TABLE IF NOT EXISTS rosters (
    league_id TEXT,
    team_id INTEGER,
    player_id INTEGER,
    player_name TEXT,
    position TEXT,
    pro_team TEXT,
    lineup_slot TEXT,
    injury_status TEXT,
    total_points REAL,
    projected_total_points REAL,
    updated_at TEXT,
    PRIMARY KEY (league_id, team_id, player_id)
);

CREATE TABLE IF NOT EXISTS matchups (
    league_id TEXT,
    week INTEGER,
    home_team_id INTEGER,
    away_team_id INTEGER,
    home_score REAL,
    away_score REAL,
    home_projected REAL,
    away_projected REAL,
    is_playoff INTEGER,
    is_self INTEGER,
    updated_at TEXT,
    PRIMARY KEY (league_id, week, home_team_id, away_team_id)
);

-- nflverse weekly stats: global, shared by every league and every user.
CREATE TABLE IF NOT EXISTS player_stats (
    player_id TEXT,
    player_name TEXT,
    player_display_name TEXT,
    position TEXT,
    recent_team TEXT,
    season INTEGER,
    week INTEGER,
    season_type TEXT,
    opponent_team TEXT,
    completions REAL,
    attempts REAL,
    passing_yards REAL,
    passing_tds REAL,
    interceptions REAL,
    carries REAL,
    rushing_yards REAL,
    rushing_tds REAL,
    receptions REAL,
    targets REAL,
    receiving_yards REAL,
    receiving_tds REAL,
    fumbles_lost REAL,
    fantasy_points REAL,
    fantasy_points_ppr REAL,
    updated_at TEXT,
    PRIMARY KEY (player_id, season, week, season_type)
);

-- Indexes the app's access patterns actually use. SQLite got by on table scans at
-- this size; Postgres may as well have them.
CREATE INDEX IF NOT EXISTS rosters_league_team_idx ON rosters (league_id, team_id);
CREATE INDEX IF NOT EXISTS matchups_league_week_idx ON matchups (league_id, week);
CREATE INDEX IF NOT EXISTS player_stats_display_name_idx ON player_stats (player_display_name);
CREATE INDEX IF NOT EXISTS player_stats_season_week_idx ON player_stats (season, week);
