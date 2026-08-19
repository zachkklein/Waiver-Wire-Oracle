# Pulls roster/matchups/scores from ESPN via espn-api and stores them in SQLite.
import os
import sqlite3
import sys
from datetime import datetime, timezone

from espn_api.football import League

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    team_name TEXT,
    wins INTEGER,
    losses INTEGER,
    ties INTEGER,
    points_for REAL,
    points_against REAL,
    is_self INTEGER,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS rosters (
    team_id INTEGER,
    player_id INTEGER,
    player_name TEXT,
    position TEXT,
    pro_team TEXT,
    lineup_slot TEXT,
    injury_status TEXT,
    total_points REAL,
    projected_total_points REAL,
    updated_at TEXT,
    PRIMARY KEY (team_id, player_id)
);

CREATE TABLE IF NOT EXISTS matchups (
    week INTEGER,
    home_team_id INTEGER,
    away_team_id INTEGER,
    home_score REAL,
    away_score REAL,
    home_projected REAL,
    away_projected REAL,
    is_playoff INTEGER,
    is_self INTEGER,
    updated_at TEXT,
    PRIMARY KEY (week, home_team_id, away_team_id)
);
"""


def get_league() -> League:
    if not config.ESPN_LEAGUE_ID or not config.ESPN_SEASON:
        raise RuntimeError(
            "League ID and season are required — set them in the app's Setup page, or "
            "ESPN_LEAGUE_ID/ESPN_SEASON in .env"
        )

    # espn_s2/swid are only needed for private leagues; public ones load fine as None.
    return League(
        league_id=int(config.ESPN_LEAGUE_ID),
        year=int(config.ESPN_SEASON),
        espn_s2=config.ESPN_S2,
        swid=config.ESPN_SWID,
    )


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def find_self_team_id(league: League) -> int | None:
    """Identify the user's own team. An explicitly configured team wins — public
    leagues have no cookies to match against, so ESPN_TEAM_ID is the only signal."""
    explicit = config.ESPN_TEAM_ID
    if explicit:
        try:
            team_id = int(explicit)
        except ValueError:
            team_id = None
        if team_id is not None and any(t.team_id == team_id for t in league.teams):
            return team_id

    swid = (config.ESPN_SWID or "").strip().strip("{}").lower()
    if not swid:
        return None

    for team in league.teams:
        for owner in team.owners:
            owner_id = (owner.get("id") or "").strip("{}").lower()
            if owner_id == swid:
                return team.team_id
    return None


def sync_teams(conn: sqlite3.Connection, league: League, self_team_id: int | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            team.team_id,
            team.team_name,
            team.wins,
            team.losses,
            team.ties,
            team.points_for,
            team.points_against,
            int(team.team_id == self_team_id),
            now,
        )
        for team in league.teams
    ]
    conn.executemany(
        """
        INSERT INTO teams (team_id, team_name, wins, losses, ties, points_for, points_against, is_self, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(team_id) DO UPDATE SET
            team_name=excluded.team_name,
            wins=excluded.wins,
            losses=excluded.losses,
            ties=excluded.ties,
            points_for=excluded.points_for,
            points_against=excluded.points_against,
            is_self=excluded.is_self,
            updated_at=excluded.updated_at
        """,
        rows,
    )


def sync_roster(conn: sqlite3.Connection, team) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("DELETE FROM rosters WHERE team_id = ?", (team.team_id,))
    rows = [
        (
            team.team_id,
            player.playerId,
            player.name,
            player.position,
            player.proTeam,
            player.lineupSlot,
            player.injuryStatus,
            player.total_points,
            player.projected_total_points,
            now,
        )
        for player in team.roster
    ]
    conn.executemany(
        """
        INSERT INTO rosters (
            team_id, player_id, player_name, position, pro_team,
            lineup_slot, injury_status, total_points, projected_total_points, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def sync_matchups(conn: sqlite3.Connection, league: League, week: int, self_team_id: int | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    box_scores = league.box_scores(week=week)

    rows = []
    for box in box_scores:
        if box.home_team is None or box.away_team is None:
            continue  # bye week
        is_self = self_team_id in (box.home_team.team_id, box.away_team.team_id)
        rows.append(
            (
                week,
                box.home_team.team_id,
                box.away_team.team_id,
                box.home_score,
                box.away_score,
                box.home_projected,
                box.away_projected,
                int(box.is_playoff),
                int(is_self),
                now,
            )
        )

    conn.executemany(
        """
        INSERT INTO matchups (
            week, home_team_id, away_team_id, home_score, away_score,
            home_projected, away_projected, is_playoff, is_self, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(week, home_team_id, away_team_id) DO UPDATE SET
            home_score=excluded.home_score,
            away_score=excluded.away_score,
            home_projected=excluded.home_projected,
            away_projected=excluded.away_projected,
            is_playoff=excluded.is_playoff,
            is_self=excluded.is_self,
            updated_at=excluded.updated_at
        """,
        rows,
    )


def run() -> None:
    league = get_league()
    self_team_id = find_self_team_id(league)

    conn = sqlite3.connect(config.DB_PATH)
    try:
        init_db(conn)
        sync_teams(conn, league, self_team_id)

        for team in league.teams:
            sync_roster(conn, team)

        for week in range(1, league.current_week + 1):
            sync_matchups(conn, league, week, self_team_id)
        conn.commit()
    finally:
        conn.close()

    return league, self_team_id


if __name__ == "__main__":
    league, self_team_id = run()

    total_players = sum(len(t.roster) for t in league.teams)
    print(f"Synced {len(league.teams)} teams.")
    print(f"Synced rosters for all {len(league.teams)} teams ({total_players} players total).")
    print(f"Synced matchups for weeks 1-{league.current_week}.")

    if self_team_id is None:
        print("Could not match ESPN_SWID to a team in this league; self-team flag not set.")
    else:
        self_team = next(t for t in league.teams if t.team_id == self_team_id)
        print(f"Your team: '{self_team.team_name}'.")
