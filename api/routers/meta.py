# App-level metadata: setup state, current week, self team, last-synced timestamps.

from fastapi import APIRouter

import db
from api.deps import LeagueDep

router = APIRouter(prefix="/api", tags=["meta"])


def _empty(configured: bool, has_data: bool = False) -> dict:
    return {
        "self_team": None,
        "current_week": None,
        "synced_at": None,
        "player_stats_rows": 0,
        "configured": configured,
        "has_data": has_data,
    }


@router.get("/meta")
def get_meta(league: LeagueDep):
    # A fresh install has no tables until the first sync runs; a brand-new account has
    # no league yet, and `league.key` would be the string "None" — don't query with it.
    if not league.is_configured or not db.is_initialized():
        return _empty(league.is_configured)

    league_id = league.key

    conn = db.connect()
    try:
        tables = db.table_names(conn)
        if "teams" not in tables:
            # Possible when only stats or news have been synced so far.
            return _empty(league.is_configured)

        # Which team is "yours" comes from the request's league context, not from a
        # column: teams rows are shared by everyone in the league.
        try:
            self_id = int(league.team_id) if league.team_id else None
        except (TypeError, ValueError):
            self_id = None

        self_team = (
            conn.execute(
                "SELECT team_id, team_name, wins, losses, ties, logo_url FROM teams "
                "WHERE league_id = ? AND team_id = ? LIMIT 1",
                (league_id, self_id),
            ).fetchone()
            if self_id is not None
            else None
        )

        # One round trip for all of it rather than several. The frontend refetches
        # /api/meta on every navigation, and against a remote Postgres each round trip is
        # real latency — sequential ones made this the slowest endpoint in the app.
        #
        # Sync freshness comes from leagues.last_synced_at: teams/rosters/matchups no
        # longer carry a per-row updated_at, because one would rewrite every row on every
        # sync. has_data asks whether teams rows exist rather than trusting a timestamp,
        # so a database synced before that change still reports correctly.
        stats_expr = (
            "(SELECT COUNT(*) FROM player_stats)" if "player_stats" in tables else "0"
        )
        leagues_expr = (
            "(SELECT last_synced_at FROM leagues WHERE league_id = ?)"
            if "leagues" in tables
            else "NULL"
        )
        params = [league_id]
        if "leagues" in tables:
            params.append(league_id)
        params.append(league_id)

        summary = conn.execute(
            f"""
            SELECT
                (SELECT MAX(week) FROM matchups WHERE league_id = ?) AS current_week,
                {leagues_expr} AS synced_at,
                (SELECT COUNT(*) FROM teams WHERE league_id = ?) AS team_count,
                {stats_expr} AS stats_rows
            """,
            tuple(params),
        ).fetchone()

        synced_at = summary["synced_at"]
        stats_row_count = summary["stats_rows"]

        return {
            "self_team": dict(self_team) if self_team else None,
            "current_week": summary["current_week"],
            "synced_at": synced_at,
            "player_stats_rows": stats_row_count,
            "configured": league.is_configured,
            "has_data": summary["team_count"] > 0,
        }
    finally:
        conn.close()
