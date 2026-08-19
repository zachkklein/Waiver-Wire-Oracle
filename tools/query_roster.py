# My team / league lookup tool, exposed as an Anthropic tool-use function.
import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

TOOL_SCHEMA = {
    "name": "query_roster",
    "description": (
        "Look up fantasy league info synced from ESPN: your team's roster, the league's "
        "standings, or a given week's matchups. Data comes from the last time espn_sync.py "
        "was run, so it reflects that point in time, not necessarily live scores."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "view": {
                "type": "string",
                "enum": ["roster", "teams", "matchup"],
                "description": (
                    "'roster' returns a team's players (defaults to your own team). "
                    "'teams' returns league standings for every team. "
                    "'matchup' returns matchup(s) for a given week (defaults to the latest "
                    "synced week; defaults to your own matchup, or all matchups if no team "
                    "is given)."
                ),
            },
            "team": {
                "type": "string",
                "description": (
                    "Team name (partial match ok) to look up instead of your own team. "
                    "Applies to the 'roster' and 'matchup' views."
                ),
            },
            "week": {
                "type": "integer",
                "description": "Week number for the 'matchup' view. Defaults to the latest synced week.",
            },
        },
        "required": [],
    },
}


def _resolve_team(conn: sqlite3.Connection, team_query: str | None):
    if team_query:
        row = conn.execute(
            "SELECT * FROM teams WHERE team_name LIKE ? ORDER BY team_id LIMIT 1",
            (f"%{team_query}%",),
        ).fetchone()
    else:
        row = conn.execute("SELECT * FROM teams WHERE is_self = 1 LIMIT 1").fetchone()
    return dict(row) if row else None


def _get_teams(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT team_id, team_name, wins, losses, ties, points_for, points_against, is_self
        FROM teams
        ORDER BY wins DESC, points_for DESC
        """
    ).fetchall()
    return {"teams": [dict(row) for row in rows]}


def _get_roster(conn: sqlite3.Connection, team_query: str | None) -> dict:
    team_row = _resolve_team(conn, team_query)
    if not team_row:
        msg = (
            f"No team found matching '{team_query}'."
            if team_query
            else "No self team found — has espn_sync.py been run?"
        )
        return {"error": msg}

    players = conn.execute(
        """
        SELECT player_name, position, pro_team, lineup_slot, injury_status,
               total_points, projected_total_points
        FROM rosters
        WHERE team_id = ?
        ORDER BY CASE WHEN lineup_slot = 'BE' THEN 1 ELSE 0 END, position
        """,
        (team_row["team_id"],),
    ).fetchall()

    return {
        "team": {
            "team_id": team_row["team_id"],
            "team_name": team_row["team_name"],
            "wins": team_row["wins"],
            "losses": team_row["losses"],
        },
        "players": [dict(p) for p in players],
    }


def _get_matchup(conn: sqlite3.Connection, team_query: str | None, week: int | None) -> dict:
    if week is None:
        row = conn.execute("SELECT MAX(week) AS w FROM matchups").fetchone()
        week = row["w"] if row else None
    if week is None:
        return {"error": "No matchups have been synced yet — run espn_sync.py first."}

    team_row = _resolve_team(conn, team_query)

    if team_query and not team_row:
        return {"error": f"No team found matching '{team_query}'."}

    if team_row:
        matchup_rows = conn.execute(
            "SELECT * FROM matchups WHERE week = ? AND (home_team_id = ? OR away_team_id = ?)",
            (week, team_row["team_id"], team_row["team_id"]),
        ).fetchall()
        if not matchup_rows:
            return {"error": f"No matchup found for '{team_row['team_name']}' in week {week}."}
    else:
        matchup_rows = conn.execute("SELECT * FROM matchups WHERE week = ?", (week,)).fetchall()
        if not matchup_rows:
            return {"error": f"No matchups synced for week {week}."}

    team_names = {
        row["team_id"]: row["team_name"]
        for row in conn.execute("SELECT team_id, team_name FROM teams").fetchall()
    }

    matchups = []
    for row in matchup_rows:
        m = dict(row)
        m["home_team_name"] = team_names.get(m["home_team_id"], "Unknown")
        m["away_team_name"] = team_names.get(m["away_team_id"], "Unknown")
        matchups.append(m)

    return {"week": week, "matchups": matchups}


def query_roster(
    view: str = "roster",
    team: str | None = None,
    week: int | None = None,
) -> dict:
    view = (view or "roster").lower()

    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if view == "teams":
            return _get_teams(conn)
        if view == "roster":
            return _get_roster(conn, team)
        if view == "matchup":
            return _get_matchup(conn, team, week)
        return {"error": f"Unknown view '{view}'. Must be one of: roster, teams, matchup."}
    finally:
        conn.close()


def run_tool(tool_input: dict) -> dict:
    return query_roster(**tool_input)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query the local teams/rosters/matchups tables.")
    parser.add_argument("--view", choices=["roster", "teams", "matchup"], default="roster")
    parser.add_argument("--team")
    parser.add_argument("--week", type=int)
    args = parser.parse_args()

    result = query_roster(view=args.view, team=args.team, week=args.week)
    print(json.dumps(result, indent=2))
