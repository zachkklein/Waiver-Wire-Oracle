-- Phase 2.5. Three problems, all of which get worse with more users and leagues.
-- See docs/HOSTED_PLAN.md.

-- 1. Player identity had no home. rosters carried player_name/position/pro_team inline,
--    duplicated once per league that rosters the player, and -- worse -- rosters.player_id
--    is ESPN's id while player_stats.player_id is nflverse's GSIS id, so the two tables
--    could not be joined at all. The app fell back to matching on name strings, which
--    reached only 97 of 162 rostered players.
CREATE TABLE IF NOT EXISTS players (
    player_id       BIGINT PRIMARY KEY,        -- ESPN's id; what rosters reference
    gsis_id         TEXT UNIQUE,               -- nflverse's id; the missing join key
    full_name       TEXT NOT NULL,
    normalized_name TEXT NOT NULL,             -- suffixes/punctuation stripped, for linking
    position        TEXT,
    pro_team        TEXT,
    updated_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS players_normalized_name_idx ON players (normalized_name);

-- Seed it from what rosters already knows, so no data is lost on the column drop.
INSERT INTO players (player_id, full_name, normalized_name, position, pro_team, updated_at)
SELECT DISTINCT ON (player_id)
       player_id,
       player_name,
       regexp_replace(lower(regexp_replace(player_name, '\s+(Jr\.|Sr\.|II|III|IV|V)$', '')),
                      '[^a-z0-9]', '', 'g'),
       position,
       pro_team,
       now()
FROM rosters
ORDER BY player_id, updated_at DESC
ON CONFLICT (player_id) DO NOTHING;

-- Link to nflverse by normalized name, but only where the match is unambiguous in both
-- directions -- one ESPN player, one GSIS id. Anything ambiguous stays NULL rather than
-- silently attaching the wrong player's stats.
WITH stats_names AS (
    SELECT DISTINCT player_id AS gsis_id,
           regexp_replace(lower(regexp_replace(player_display_name, '\s+(Jr\.|Sr\.|II|III|IV|V)$', '')),
                          '[^a-z0-9]', '', 'g') AS norm
    FROM player_stats
), unique_stats AS (
    SELECT norm, min(gsis_id) AS gsis_id FROM stats_names GROUP BY norm HAVING count(*) = 1
), unique_players AS (
    SELECT normalized_name FROM players GROUP BY normalized_name HAVING count(*) = 1
)
UPDATE players p
SET gsis_id = u.gsis_id
FROM unique_stats u
WHERE p.normalized_name = u.norm
  AND p.gsis_id IS NULL
  AND p.normalized_name IN (SELECT normalized_name FROM unique_players);

-- 2. rosters loses the identity columns (now in players) and updated_at. The timestamp
--    is the subtle one: a per-row sync stamp means every row is rewritten on every sync
--    even when the roster is byte-identical, which defeats the guarded upsert entirely.
--    Sync freshness belongs to the league -- leagues.last_synced_at already exists.
ALTER TABLE rosters
    DROP COLUMN IF EXISTS player_name,
    DROP COLUMN IF EXISTS position,
    DROP COLUMN IF EXISTS pro_team,
    DROP COLUMN IF EXISTS updated_at;

-- 3. is_self was a per-user flag living on rows shared by everyone in the league. With
--    two members signed up, whoever synced last owned it and the other saw the wrong
--    team highlighted. It is now derived per request from the caller's team id.
ALTER TABLE teams    DROP COLUMN IF EXISTS is_self;
ALTER TABLE matchups DROP COLUMN IF EXISTS is_self;

-- 4. Real timestamps: 8 fixed bytes instead of a 29-byte ISO string, and staleness
--    checks (Phase 5) become comparisons rather than string compares.
ALTER TABLE teams        ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at::timestamptz;
ALTER TABLE matchups     ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at::timestamptz;
ALTER TABLE player_stats ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at::timestamptz;
