# My team / league lookup tool, exposed as an LLM tool-calling function.
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import db
from context import LeagueCtx

TOOL_SCHEMA = {
    "name": "query_roster",
    "description": (
        "Look up fantasy league info synced from ESPN: your team's roster, the league's "
        "standings, or a given week's matchups. Data comes from the last time espn_sync.py "
        "was run, so it reflects that point in time, not necessarily live scores. Always "
        "scoped to whichever league is currently active in the app."
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


def _self_team_id(league: LeagueCtx) -> int | None:
    """Which team is the caller's, as an int. None for a league where it was never
    resolved (a public league with no ESPN_TEAM_ID and no cookies to match on)."""
    try:
        return int(league.team_id) if league.team_id else None
    except (TypeError, ValueError):
        return None


def _resolve_team(conn, league_id: str, team_query: str | None, self_id: int | None):
    """The named team, or the caller's own. `teams` has no is_self column — that was a
    per-viewer fact stored on rows shared by the whole league — so "mine" comes from the
    request context instead."""
    if team_query:
        row = conn.execute(
            "SELECT * FROM teams WHERE league_id = ? AND team_name LIKE ? ORDER BY team_id LIMIT 1",
            (league_id, f"%{team_query}%"),
        ).fetchone()
    elif self_id is not None:
        row = conn.execute(
            "SELECT * FROM teams WHERE league_id = ? AND team_id = ? LIMIT 1",
            (league_id, self_id),
        ).fetchone()
    else:
        row = None
    return dict(row) if row else None


def _get_teams(conn, league_id: str, include_logos: bool, self_id: int | None) -> dict:
    # logo_url is for the web UI only — it's noise in the LLM's tool results, so it's
    # opt-in rather than always selected. is_self is computed per request (0/1, since the
    # frontend renders it with a ternary) rather than read from a shared column.
    logo_col = ", logo_url" if include_logos else ""
    rows = conn.execute(
        f"""
        SELECT team_id, team_name, wins, losses, ties, points_for, points_against,
               CASE WHEN team_id = ? THEN 1 ELSE 0 END AS is_self{logo_col}
        FROM teams
        WHERE league_id = ?
        -- team_id breaks ties. Without it a preseason league (every team 0-0 with 0.0
        -- points) has no ordering at all, so standings positions shuffle between
        -- requests and "you are 4th" becomes "you are 10th" for no reason.
        ORDER BY wins DESC, points_for DESC, team_id
        """,
        (self_id, league_id),
    ).fetchall()
    return {"teams": [dict(row) for row in rows]}


def _get_roster(
    conn, league_id: str, team_query: str | None, include_logos: bool, self_id: int | None
) -> dict:
    team_row = _resolve_team(conn, league_id, team_query, self_id)
    if not team_row:
        msg = (
            f"No team found matching '{team_query}'."
            if team_query
            else "No self team found — has espn_sync.py been run?"
        )
        return {"error": msg}

    # Name/position/pro_team live on `players` now, stored once globally instead of
    # once per league. LEFT JOIN so a roster row is never dropped just because its
    # player hasn't been synced into the dimension yet.
    players = conn.execute(
        """
        SELECT p.full_name AS player_name, p.position, p.pro_team, p.gsis_id,
               r.lineup_slot, r.injury_status, r.total_points, r.projected_total_points
        FROM rosters r
        LEFT JOIN players p ON p.player_id = r.player_id
        WHERE r.league_id = ? AND r.team_id = ?
        ORDER BY CASE WHEN r.lineup_slot = 'BE' THEN 1 ELSE 0 END, p.position
        """,
        (league_id, team_row["team_id"]),
    ).fetchall()

    player_dicts = []
    for p in players:
        d = dict(p)
        if d["lineup_slot"] == "RB/WR/TE":
            d["lineup_slot"] = "FLEX"
        player_dicts.append(d)

    team = {
        "team_id": team_row["team_id"],
        "team_name": team_row["team_name"],
        "wins": team_row["wins"],
        "losses": team_row["losses"],
    }
    if include_logos:
        team["logo_url"] = team_row["logo_url"]

    return {"team": team, "players": player_dicts}


def _get_matchup(
    conn,
    league_id: str,
    team_query: str | None,
    week: int | None,
    include_logos: bool,
    self_id: int | None,
) -> dict:
    if week is None:
        row = conn.execute(
            "SELECT MAX(week) AS w FROM matchups WHERE league_id = ?", (league_id,)
        ).fetchone()
        week = row["w"] if row else None
    if week is None:
        return {"error": "No matchups have been synced yet — run espn_sync.py first."}

    team_row = _resolve_team(conn, league_id, team_query, self_id)

    if team_query and not team_row:
        return {"error": f"No team found matching '{team_query}'."}

    if team_row:
        matchup_rows = conn.execute(
            """
            SELECT * FROM matchups
            WHERE league_id = ? AND week = ? AND (home_team_id = ? OR away_team_id = ?)
            """,
            (league_id, week, team_row["team_id"], team_row["team_id"]),
        ).fetchall()
        if not matchup_rows:
            return {"error": f"No matchup found for '{team_row['team_name']}' in week {week}."}
    else:
        matchup_rows = conn.execute(
            "SELECT * FROM matchups WHERE league_id = ? AND week = ?", (league_id, week)
        ).fetchall()
        if not matchup_rows:
            return {"error": f"No matchups synced for week {week}."}

    teams = {
        row["team_id"]: row
        for row in conn.execute(
            "SELECT team_id, team_name, logo_url FROM teams WHERE league_id = ?", (league_id,)
        ).fetchall()
    }

    matchups = []
    for row in matchup_rows:
        m = dict(row)
        # Derived per request, not stored: "your matchup" depends on who is asking.
        m["is_self"] = int(self_id is not None and self_id in (m["home_team_id"], m["away_team_id"]))
        for side in ("home", "away"):
            team = teams.get(m[f"{side}_team_id"])
            m[f"{side}_team_name"] = team["team_name"] if team else "Unknown"
            if include_logos:
                m[f"{side}_logo_url"] = team["logo_url"] if team else None
        matchups.append(m)

    return {"week": week, "matchups": matchups}


def query_roster(
    league: LeagueCtx,
    view: str = "roster",
    team: str | None = None,
    week: int | None = None,
    include_logos: bool = False,
) -> dict:
    """Every teams/rosters/matchups query is scoped to `league` — team_id values are
    only unique within a league, not across leagues sharing this database."""
    view = (view or "roster").lower()
    league_id = league.key
    self_id = _self_team_id(league)

    conn = db.connect()
    try:
        if view == "teams":
            return _get_teams(conn, league_id, include_logos, self_id)
        if view == "roster":
            return _get_roster(conn, league_id, team, include_logos, self_id)
        if view == "matchup":
            return _get_matchup(conn, league_id, team, week, include_logos, self_id)
        return {"error": f"Unknown view '{view}'. Must be one of: roster, teams, matchup."}
    finally:
        conn.close()


def run_tool(tool_input: dict, league: LeagueCtx | None = None) -> dict:
    """LLM entrypoint. `league` is supplied by the caller, never by the model — it's
    not in TOOL_SCHEMA, so the agent can't ask for a league it shouldn't see."""
    if league is None:
        raise ValueError("query_roster needs a LeagueCtx")
    return query_roster(league, **tool_input)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query the local teams/rosters/matchups tables.")
    parser.add_argument("--view", choices=["roster", "teams", "matchup"], default="roster")
    parser.add_argument("--team")
    parser.add_argument("--week", type=int)
    args = parser.parse_args()

    result = query_roster(config.load_league_ctx(), view=args.view, team=args.team, week=args.week)
    print(json.dumps(result, indent=2))
