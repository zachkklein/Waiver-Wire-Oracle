-- Phase 3: wire Supabase Auth to the accounts model (docs/HOSTED_PLAN.md).

-- public.users.id was always *intended* to carry auth.users.id; the Phase 2 migration
-- left that a convention so the table stayed insertable before auth existed. Make it a
-- constraint now that it doesn't: deleting an account in Supabase Auth must also remove
-- its league links, and with them the stored ESPN cookies -- espn_s2 is a session cookie
-- for the user's whole ESPN account, so an orphaned row is the one leak worth designing
-- against. The default goes for the same reason: an id comes from Auth or not at all.
ALTER TABLE users ALTER COLUMN id DROP DEFAULT;

ALTER TABLE users
    ADD CONSTRAINT users_id_fkey
    FOREIGN KEY (id) REFERENCES auth.users (id) ON DELETE CASCADE;

-- Which league an account is currently looking at. is_default already existed; this
-- makes "at most one per user" the database's job, so store._make_default() can
-- clear-then-set in one transaction without two rows ever both claiming it.
CREATE UNIQUE INDEX IF NOT EXISTS user_leagues_one_default_idx
    ON user_leagues (user_id) WHERE is_default;
