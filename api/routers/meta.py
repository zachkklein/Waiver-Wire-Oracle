# App-level metadata: current week, self team, last-synced timestamps.
import sqlite3

from fastapi import APIRouter

import config

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/meta")
def get_meta():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        self_team = conn.execute(
            "SELECT team_id, team_name, wins, losses, ties FROM teams WHERE is_self = 1 LIMIT 1"
        ).fetchone()
        current_week = conn.execute("SELECT MAX(week) AS w FROM matchups").fetchone()["w"]
        teams_synced_at = conn.execute("SELECT MAX(updated_at) AS t FROM teams").fetchone()["t"]
        rosters_synced_at = conn.execute("SELECT MAX(updated_at) AS t FROM rosters").fetchone()["t"]
        matchups_synced_at = conn.execute("SELECT MAX(updated_at) AS t FROM matchups").fetchone()["t"]
        stats_row_count = conn.execute("SELECT COUNT(*) AS c FROM player_stats").fetchone()["c"]

        return {
            "self_team": dict(self_team) if self_team else None,
            "current_week": current_week,
            "synced_at": {
                "teams": teams_synced_at,
                "rosters": rosters_synced_at,
                "matchups": matchups_synced_at,
            },
            "player_stats_rows": stats_row_count,
        }
    finally:
        conn.close()
