-- Supabase exposes every public-schema table through PostgREST, reachable with the
-- anon key that ships in the browser bundle. Without RLS that would make rosters --
-- and worse, user_leagues' ESPN credentials -- world-readable.
--
-- The app never uses PostgREST: FastAPI connects straight to Postgres as the table
-- owner, and owners bypass RLS. So enabling RLS and deliberately defining NO policies
-- denies the REST API entirely while leaving the backend untouched. Phase 3 adds real
-- per-user policies only if something ever needs to read through PostgREST.
--
-- The database linter reports these as INFO "rls_enabled_no_policy". That is the
-- intended state here, not an oversight.
ALTER TABLE teams          ENABLE ROW LEVEL SECURITY;
ALTER TABLE rosters        ENABLE ROW LEVEL SECURITY;
ALTER TABLE matchups       ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_stats   ENABLE ROW LEVEL SECURITY;
ALTER TABLE users          ENABLE ROW LEVEL SECURITY;
ALTER TABLE leagues        ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_leagues   ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings  ENABLE ROW LEVEL SECURITY;
