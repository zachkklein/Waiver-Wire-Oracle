-- New tables do not inherit RLS, so the players table added in 20260821001000 was
-- reachable through PostgREST with the public anon key until now. Same deny-by-default
-- as every other table: RLS on, no policies, backend connects as owner and bypasses it.
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
