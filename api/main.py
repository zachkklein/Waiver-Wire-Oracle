# FastAPI app for the Waiver Wire Oracle web UI. Serves the JSON API under /api,
# and in production also serves the built frontend (frontend/dist) as static files.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import auth
import config
import db
from api.routers import auth as auth_router
from api.routers import chat, league, leagues, logos, meta, news, settings, stats

app = FastAPI(title="Waiver Wire Oracle")


@app.on_event("startup")
def _check_config() -> None:
    # Reject a legacy Supabase key here rather than letting it quietly work.
    auth.check_config()

    # Accounts live in Postgres tables created by supabase/migrations. Sitting on the
    # local SQLite file with auth switched on would fail later, per request, with a
    # missing-table error — say so once, at startup, instead.
    if auth.is_enabled() and not db.is_postgres():
        raise RuntimeError(
            "SUPABASE_URL is set, so this deployment has accounts — but DATABASE_URL "
            "isn't, so it would be storing them in the local data/db.sqlite file. Point "
            "DATABASE_URL at Postgres, or unset SUPABASE_URL to run single-user."
        )


@app.on_event("startup")
def _migrate_db() -> None:
    # One-time upgrade for databases created before multi-league support: teams/rosters/
    # matchups need a league_id column. Backfilling it needs a league id, and pre-upgrade
    # installs only ever had one — the currently configured one. That only ever applies
    # to a self-hosted SQLite file; a hosted database has no ambient league to name, and
    # was created from the current schema anyway.
    if auth.is_enabled():
        return

    league = config.load_league_ctx()
    if not league.league_id:
        return
    from ingest import espn_sync

    with db.session(commit=True) as conn:
        espn_sync.init_db(conn, league.key)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth_router.router,
    league.router,
    leagues.router,
    logos.router,
    stats.router,
    news.router,
    meta.router,
    chat.router,
    settings.router,
):
    app.include_router(router)

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
