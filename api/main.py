# FastAPI app for the Waiver Wire Oracle web UI. Serves the JSON API under /api,
# and in production also serves the built frontend (frontend/dist) as static files.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from api.routers import chat, league, leagues, meta, news, settings, stats

app = FastAPI(title="Waiver Wire Oracle")


@app.on_event("startup")
def _migrate_db() -> None:
    # One-time upgrade for databases created before multi-league support: teams/rosters/
    # matchups need a league_id column. Backfilling it needs a league id, and pre-upgrade
    # installs only ever had one — the currently configured (active) one.
    if not config.ESPN_LEAGUE_ID:
        return
    import sqlite3

    from ingest import espn_sync

    conn = sqlite3.connect(config.DB_PATH)
    try:
        espn_sync.init_db(conn, str(config.ESPN_LEAGUE_ID))
        conn.commit()
    finally:
        conn.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    league.router,
    leagues.router,
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
