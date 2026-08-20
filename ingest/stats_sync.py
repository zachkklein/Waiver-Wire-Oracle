# Pulls nflverse weekly player stats via nfl-data-py and stores them in SQLite.
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import nfl_data_py as nfl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS player_stats (
    player_id TEXT,
    player_name TEXT,
    player_display_name TEXT,
    position TEXT,
    recent_team TEXT,
    season INTEGER,
    week INTEGER,
    season_type TEXT,
    opponent_team TEXT,
    completions REAL,
    attempts REAL,
    passing_yards REAL,
    passing_tds REAL,
    interceptions REAL,
    carries REAL,
    rushing_yards REAL,
    rushing_tds REAL,
    receptions REAL,
    targets REAL,
    receiving_yards REAL,
    receiving_tds REAL,
    fumbles_lost REAL,
    fantasy_points REAL,
    fantasy_points_ppr REAL,
    updated_at TEXT,
    PRIMARY KEY (player_id, season, week, season_type)
);
"""

COLUMNS = [
    "player_id",
    "player_name",
    "player_display_name",
    "position",
    "recent_team",
    "season",
    "week",
    "season_type",
    "opponent_team",
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


def init_db(conn) -> None:
    conn.executescript(SCHEMA)


def _to_native(value):
    if pd.isna(value):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def fetch_weekly_stats(years: list[int]) -> pd.DataFrame:
    try:
        df = nfl.import_weekly_data(years, downcast=False)
    except Exception as exc:
        raise RuntimeError(
            f"Could not fetch nflverse weekly stats for {years} "
            "(the season may not have started yet, or the year has no data released)."
        ) from exc

    df["fumbles_lost"] = (
        df["sack_fumbles_lost"] + df["rushing_fumbles_lost"] + df["receiving_fumbles_lost"]
    )
    return df[COLUMNS]


def sync_player_stats(conn, years: list[int]) -> int:
    df = fetch_weekly_stats(years)
    now = datetime.now(timezone.utc).isoformat()

    rows = [
        tuple(_to_native(v) for v in row) + (now,)
        for row in df.itertuples(index=False, name=None)
    ]

    conn.executemany(
        f"""
        INSERT INTO player_stats ({", ".join(COLUMNS)}, updated_at)
        VALUES ({", ".join("?" for _ in COLUMNS)}, ?)
        ON CONFLICT(player_id, season, week, season_type) DO UPDATE SET
            {", ".join(f"{col}=excluded.{col}" for col in COLUMNS if col not in ("player_id", "season", "week", "season_type"))},
            updated_at=excluded.updated_at
        """,
        rows,
    )
    return len(rows)


def run(years: list[int] | None = None, default_season: str | int | None = None) -> int:
    """Player stats are nflverse data, shared by every league — the only league-shaped
    input is which season to default to when no years are given."""
    if not years:
        default_season = default_season or config.load_league_ctx().season
        if not default_season:
            raise RuntimeError("ESPN_SEASON must be set in .env, or pass years explicitly")
        years = [int(default_season)]

    conn = db.connect()
    try:
        init_db(conn)
        row_count = sync_player_stats(conn, years)
        conn.commit()
    finally:
        conn.close()

    return row_count


if __name__ == "__main__":
    cli_years = [int(y) for y in sys.argv[1:]] or None
    count = run(cli_years)
    print(f"Synced {count} player-week stat lines.")
