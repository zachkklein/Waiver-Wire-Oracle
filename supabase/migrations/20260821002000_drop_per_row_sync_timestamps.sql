-- Finish what the rosters change started. A per-row updated_at means every row is
-- rewritten on every sync even when nothing upstream changed, which defeats the
-- IS DISTINCT FROM guards on the upserts. rosters dropped it already; teams and
-- matchups are the remaining churn.
--
-- matchups matters most at scale: sync re-upserts every week 1..current_week on every
-- run, so by late season that is ~90 rows per league rewritten each time, for no reason
-- -- a week 3 final score does not change again.
--
-- Sync freshness now lives solely on leagues.last_synced_at, which is also the single
-- source of truth Phase 5's staleness check needs. player_stats keeps its updated_at:
-- it is global data that does not grow with users, so its churn is constant.
ALTER TABLE teams    DROP COLUMN IF EXISTS updated_at;
ALTER TABLE matchups DROP COLUMN IF EXISTS updated_at;
