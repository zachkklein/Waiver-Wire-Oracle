-- The multi-tenant model. Phase 3 wires Supabase Auth to these; Phase 2 just lands
-- the shape. See docs/HOSTED_PLAN.md.

-- One row per account. `id` is intended to carry the same UUID as auth.users.id;
-- the foreign key to auth.users is deliberately deferred to Phase 3 so this table
-- stays insertable (and testable) before auth exists.
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per ESPN league, shared by everyone in it. This is what makes twelve
-- people in one league cost one copy of teams/rosters/matchups rather than twelve,
-- and what the sync worker locks on in Phase 5.
CREATE TABLE IF NOT EXISTS leagues (
    league_id TEXT PRIMARY KEY,
    season TEXT,
    name TEXT,
    last_synced_at TIMESTAMPTZ
);

-- The join: which accounts can see which league, and whose ESPN credentials to sync
-- it with. The *_enc columns hold ciphertext from Phase 4 -- nothing writes them yet.
-- espn_team_id is per-user by nature: two people in one league have different teams.
CREATE TABLE IF NOT EXISTS user_leagues (
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    league_id TEXT NOT NULL REFERENCES leagues (league_id) ON DELETE CASCADE,
    espn_team_id TEXT,
    espn_swid_enc TEXT,
    espn_s2_enc TEXT,
    label TEXT,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    credentials_valid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, league_id)
);

CREATE INDEX IF NOT EXISTS user_leagues_league_idx ON user_leagues (league_id);

-- Per-account Oracle settings: model choice, and (Phase 4) an encrypted
-- bring-your-own OpenRouter key. usage_* back the metered free tier in Phase 6.
CREATE TABLE IF NOT EXISTS user_settings (
    user_id UUID PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    openrouter_key_enc TEXT,
    openrouter_model TEXT,
    usage_period_start DATE,
    usage_questions INTEGER NOT NULL DEFAULT 0
);
