# App-level metadata: setup state, current week, self team, last-synced timestamps.
import os
import sqlite3

from fastapi import APIRouter

import config

router = APIRouter(prefix="/api", tags=["meta"])


def _empty(has_data: bool = False) -> dict:
    return {
        "self_team": None,
        "current_week": None,
        "synced_at": {"teams": None, "rosters": None, "matchups": None},
        "player_stats_rows": 0,
        "configured": config.is_configured(),
        "has_data": has_data,
    }


@router.get("/meta")
def get_meta():
    # A fresh install has no database until the first sync runs.
    if not os.path.exists(config.DB_PATH):
        return _empty()

    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        if "teams" not in tables:
            # Possible when only stats or news have been synced so far.
            return _empty()

        self_team = conn.execute(
            "SELECT team_id, team_name, wins, losses, ties FROM teams WHERE is_self = 1 LIMIT 1"
        ).fetchone()
        current_week = conn.execute("SELECT MAX(week) AS w FROM matchups").fetchone()["w"]
        teams_synced_at = conn.execute("SELECT MAX(updated_at) AS t FROM teams").fetchone()["t"]
        rosters_synced_at = conn.execute("SELECT MAX(updated_at) AS t FROM rosters").fetchone()["t"]
        matchups_synced_at = conn.execute("SELECT MAX(updated_at) AS t FROM matchups").fetchone()["t"]
        stats_row_count = (
            conn.execute("SELECT COUNT(*) AS c FROM player_stats").fetchone()["c"]
            if "player_stats" in tables
            else 0
        )

        return {
            "self_team": dict(self_team) if self_team else None,
            "current_week": current_week,
            "synced_at": {
                "teams": teams_synced_at,
                "rosters": rosters_synced_at,
                "matchups": matchups_synced_at,
            },
            "player_stats_rows": stats_row_count,
            "configured": config.is_configured(),
            "has_data": teams_synced_at is not None,
        }
    finally:
        conn.close()
