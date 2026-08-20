# SQL lookup tool for player stats, exposed as an LLM tool-calling function.
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db
from context import LeagueCtx  # noqa: F401  (used in a type hint)

NUMERIC_COLUMNS = [
    "completions",
    "attempts",
    "passing_yards",
    "passing_tds",
    "interceptions",
    "carries",
    "rushing_yards",
    "rushing_tds",
    "receptions",
    "targets",
    "receiving_yards",
    "receiving_tds",
    "fumbles_lost",
    "fantasy_points",
    "fantasy_points_ppr",
]
SORTABLE_COLUMNS = set(NUMERIC_COLUMNS) | {"week", "season"}

TOOL_SCHEMA = {
    "name": "query_stats",
    "description": (
        "Look up NFL player weekly stats (yards, TDs, targets, fantasy points, etc.) from the "
        "local stats database. Can return individual weekly stat lines, or aggregate totals "
        "across a range of weeks (e.g. 'top RBs by PPR points over the last 3 weeks')."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "player_name": {
                "type": "string",
                "description": "Full or partial player name to search for, e.g. 'Josh Allen' or 'Allen'.",
            },
            "position": {
                "type": "string",
                "description": "Filter by position: QB, RB, WR, TE, K, or DST.",
            },
            "team": {
                "type": "string",
                "description": "Filter by NFL team abbreviation, e.g. 'BUF'.",
            },
            "season": {
                "type": "integer",
                "description": "Filter by season year, e.g. 2024.",
            },
            "week_min": {
                "type": "integer",
                "description": "Minimum week (inclusive) to include.",
            },
            "week_max": {
                "type": "integer",
                "description": "Maximum week (inclusive) to include.",
            },
            "season_type": {
                "type": "string",
                "description": "REG or POST. Omit to include all.",
            },
            "aggregate": {
                "type": "boolean",
                "description": (
                    "If true, sum stats per player across all matched weeks instead of "
                    "returning individual weekly rows. Useful for leaderboard-style questions."
                ),
            },
            "sort_by": {
                "type": "string",
                "description": (
                    "Stat column to sort results by, descending. Default 'fantasy_points_ppr'. "
                    f"One of: {', '.join(sorted(SORTABLE_COLUMNS))}."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Max rows to return. Default 25, capped at 200.",
            },
        },
        "required": [],
    },
}


def query_stats(
    player_name: str | None = None,
    position: str | None = None,
    team: str | None = None,
    season: int | None = None,
    week_min: int | None = None,
    week_max: int | None = None,
    season_type: str | None = None,
    aggregate: bool = False,
    sort_by: str = "fantasy_points_ppr",
    limit: int = 25,
) -> list[dict]:
    if sort_by not in SORTABLE_COLUMNS:
        sort_by = "fantasy_points_ppr"
    limit = max(1, min(int(limit or 25), 200))

    where, params = [], []
    if player_name:
        where.append("(player_display_name LIKE ? OR player_name LIKE ?)")
        like = f"%{player_name}%"
        params += [like, like]
    if position:
        where.append("position = ?")
        params.append(position.upper())
    if team:
        where.append("recent_team = ?")
        params.append(team.upper())
    if season is not None:
        where.append("season = ?")
        params.append(int(season))
    if week_min is not None:
        where.append("week >= ?")
        params.append(int(week_min))
    if week_max is not None:
        where.append("week <= ?")
        params.append(int(week_max))
    if season_type:
        where.append("season_type = ?")
        params.append(season_type.upper())

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    conn = db.connect()
    try:
        if aggregate:
            agg_cols = ", ".join(f"SUM({c}) AS {c}" for c in NUMERIC_COLUMNS)
            order_expr = f"SUM({sort_by})" if sort_by in NUMERIC_COLUMNS else sort_by
            sql = f"""
                SELECT player_id, player_display_name, player_name, position, recent_team,
                       COUNT(DISTINCT week) AS games_played, {agg_cols}
                FROM player_stats
                {where_clause}
                GROUP BY player_id, player_display_name, player_name, position, recent_team
                ORDER BY {order_expr} DESC
                LIMIT ?
            """
        else:
            sql = f"""
                SELECT player_id, player_display_name, player_name, position, recent_team,
                       season, week, season_type, opponent_team, {", ".join(NUMERIC_COLUMNS)}
                FROM player_stats
                {where_clause}
                ORDER BY {sort_by} DESC
                LIMIT ?
            """
        rows = conn.execute(sql, params + [limit]).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def run_tool(tool_input: dict, league: "LeagueCtx | None" = None) -> list[dict]:
    # `league` is accepted for a uniform tool interface and ignored: this data is
    # nflverse/RSS, not tied to any one ESPN league.
    return query_stats(**tool_input)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query the local player_stats table.")
    parser.add_argument("--player", dest="player_name")
    parser.add_argument("--position")
    parser.add_argument("--team")
    parser.add_argument("--season", type=int)
    parser.add_argument("--week-min", type=int)
    parser.add_argument("--week-max", type=int)
    parser.add_argument("--season-type")
    parser.add_argument("--aggregate", action="store_true")
    parser.add_argument("--sort-by", default="fantasy_points_ppr")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    results = query_stats(
        player_name=args.player_name,
        position=args.position,
        team=args.team,
        season=args.season,
        week_min=args.week_min,
        week_max=args.week_max,
        season_type=args.season_type,
        aggregate=args.aggregate,
        sort_by=args.sort_by,
        limit=args.limit,
    )
    print(json.dumps(results, indent=2))
