# App-level metadata: setup state, current week, self team, last-synced timestamps.

from fastapi import APIRouter

import config
import db
from api.deps import LeagueDep

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
def get_meta(league: LeagueDep):
    # A fresh install has no tables until the first sync runs.
    if not db.is_initialized():
        return _empty()

    league_id = league.key

    conn = db.connect()
    try:
        tables = db.table_names(conn)
        if "teams" not in tables:
            # Possible when only stats or news have been synced so far.
            return _empty()

        self_team = conn.execute(
            "SELECT team_id, team_name, wins, losses, ties, logo_url FROM teams "
            "WHERE league_id = ? AND is_self = 1 LIMIT 1",
            (league_id,),
        ).fetchone()

        # One round trip for the five aggregates rather than five. The frontend refetches
        # /api/meta on every navigation, and against a remote Postgres each round trip is
        # real latency — five sequential ones made this the slowest endpoint in the app.
        stats_expr = (
            "(SELECT COUNT(*) FROM player_stats)" if "player_stats" in tables else "0"
        )
        summary = conn.execute(
            f"""
            SELECT
                (SELECT MAX(week) FROM matchups WHERE league_id = ?) AS current_week,
                (SELECT MAX(updated_at) FROM teams WHERE league_id = ?) AS teams_at,
                (SELECT MAX(updated_at) FROM rosters WHERE league_id = ?) AS rosters_at,
                (SELECT MAX(updated_at) FROM matchups WHERE league_id = ?) AS matchups_at,
                {stats_expr} AS stats_rows
            """,
            (league_id, league_id, league_id, league_id),
        ).fetchone()

        teams_synced_at = summary["teams_at"]
        rosters_synced_at = summary["rosters_at"]
        matchups_synced_at = summary["matchups_at"]
        stats_row_count = summary["stats_rows"]

        return {
            "self_team": dict(self_team) if self_team else None,
            "current_week": summary["current_week"],
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
