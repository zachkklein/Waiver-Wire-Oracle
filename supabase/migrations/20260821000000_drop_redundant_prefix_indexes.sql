-- Both of these duplicate a leftmost prefix of their table's primary key, so the PK
-- index already serves every query they were meant to help (verified with EXPLAIN:
-- "Index Scan using rosters_pkey ... Index Cond: (league_id = ... AND team_id = ...)").
--
-- A redundant index is not free: it is written on every insert and update, and at
-- multi-league scale it is also hundreds of MB of dead weight. Added in
-- 20260820232506_league_and_stats_tables.sql by mistake.
DROP INDEX IF EXISTS rosters_league_team_idx;   -- PK: (league_id, team_id, player_id)
DROP INDEX IF EXISTS matchups_league_week_idx;  -- PK: (league_id, week, home_team_id, away_team_id)
