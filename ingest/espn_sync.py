# Pulls roster/matchups/scores from ESPN via espn-api and stores them in SQLite.
import os
import sys
from datetime import datetime, timezone

from espn_api.football import League

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import db
from context import LeagueCtx
from names import normalize_player_name

# `teams`/`rosters`/`matchups` are scoped to one league; `players` is global (an NFL
# player is the same player in every league), as are player_stats and the news store.
#
# league_id is ESPN's own league id (as a string) — it's already globally unique, so it
# doubles as the key that scopes teams/rosters/matchups to one of possibly several
# configured leagues sharing this database. player_stats/news stay unscoped: they're
# nflverse/RSS data, not tied to any one ESPN league.
SCHEMA = """
-- Player identity, stored once globally rather than once per league that rosters the
-- player. gsis_id is nflverse's id, which is what makes rosters joinable to
-- player_stats at all -- see names.py and stats_sync.link_players().
CREATE TABLE IF NOT EXISTS players (
    player_id BIGINT PRIMARY KEY,
    gsis_id TEXT UNIQUE,
    full_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    position TEXT,
    pro_team TEXT,
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS players_normalized_name_idx ON players (normalized_name);

-- One row per ESPN league, shared by everyone in it. Carries the sync timestamp now
-- that rosters has no per-row one. Postgres gets a richer definition (FKs from
-- user_leagues) in supabase/migrations; IF NOT EXISTS leaves that alone.
CREATE TABLE IF NOT EXISTS leagues (
    league_id TEXT PRIMARY KEY,
    season TEXT,
    name TEXT,
    last_synced_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS teams (
    league_id TEXT,
    team_id INTEGER,
    team_name TEXT,
    wins INTEGER,
    losses INTEGER,
    ties INTEGER,
    points_for REAL,
    points_against REAL,
    logo_url TEXT,
    PRIMARY KEY (league_id, team_id)
);

-- teams/rosters/matchups deliberately have no updated_at: a per-row sync stamp rewrites
-- every row on every sync even when nothing changed, defeating the IS DISTINCT FROM
-- guards on the upserts below. Sync freshness lives on leagues.last_synced_at.
CREATE TABLE IF NOT EXISTS rosters (
    league_id TEXT,
    team_id INTEGER,
    player_id BIGINT,
    lineup_slot TEXT,
    injury_status TEXT,
    total_points REAL,
    projected_total_points REAL,
    PRIMARY KEY (league_id, team_id, player_id)
);

CREATE TABLE IF NOT EXISTS matchups (
    league_id TEXT,
    week INTEGER,
    home_team_id INTEGER,
    away_team_id INTEGER,
    home_score REAL,
    away_score REAL,
    home_projected REAL,
    away_projected REAL,
    is_playoff INTEGER,
    PRIMARY KEY (league_id, week, home_team_id, away_team_id)
);
"""


def get_league(ctx: LeagueCtx) -> League:
    if not ctx.is_configured:
        raise RuntimeError(
            "League ID and season are required — set them in the app's Setup page, or "
            "ESPN_LEAGUE_ID/ESPN_SEASON in .env"
        )

    # espn_s2/swid are only needed for private leagues; public ones load fine as None.
    return League(
        league_id=int(ctx.league_id),
        year=int(ctx.season),
        espn_s2=ctx.s2,
        swid=ctx.swid,
    )


def _migrate_legacy_tables(conn, league_id: str) -> None:
    """One-time upgrade for databases created before multi-league support: tables
    without a league_id column get renamed aside, recreated with the new schema, and
    their existing rows backfilled with `league_id` (the only league that data could
    have belonged to).

    Only ever finds work to do on a long-lived SQLite file — a Postgres database is
    created from the current schema, so there's nothing pre-multi-league to fix."""
    existing = db.table_names(conn)
    to_migrate = []
    for table in ("teams", "rosters", "matchups"):
        if table not in existing:
            continue
        cols = db.column_names(conn, table)
        if "league_id" in cols:
            continue
        conn.execute(f"ALTER TABLE {table} RENAME TO {table}_legacy")
        to_migrate.append((table, cols))

    conn.executescript(SCHEMA)

    for table, cols in to_migrate:
        collist = ", ".join(cols)
        conn.execute(
            f"INSERT INTO {table} (league_id, {collist}) "
            f"SELECT ?, {collist} FROM {table}_legacy",
            (league_id,),
        )
        conn.execute(f"DROP TABLE {table}_legacy")


# Columns added to an existing table after its first release. Unlike the league_id
# migration these need no backfill — the next sync fills them in.
ADDED_COLUMNS = {"teams": [("logo_url", "TEXT")]}


def _migrate_added_columns(conn) -> None:
    for table, columns in ADDED_COLUMNS.items():
        existing = set(db.column_names(conn, table))
        for name, decl in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def init_db(conn, league_id: str) -> None:
    _migrate_legacy_tables(conn, league_id)
    conn.executescript(SCHEMA)
    _migrate_added_columns(conn)


def find_self_team_id(league: League, ctx: LeagueCtx) -> int | None:
    """Identify the user's own team. An explicitly configured team wins — public
    leagues have no cookies to match against, so ESPN_TEAM_ID is the only signal."""
    explicit = ctx.team_id
    if explicit:
        try:
            team_id = int(explicit)
        except ValueError:
            team_id = None
        if team_id is not None and any(t.team_id == team_id for t in league.teams):
            return team_id

    swid = (ctx.swid or "").strip().strip("{}").lower()
    if not swid:
        return None

    for team in league.teams:
        for owner in team.owners:
            owner_id = (owner.get("id") or "").strip("{}").lower()
            if owner_id == swid:
                return team.team_id
    return None


def sync_teams(conn, league: League, league_id: str) -> None:
    """Standings for every team. No is_self column: which team is "yours" is a property
    of the viewer, not of the league, and these rows are shared by everyone in it."""
    rows = [
        (
            league_id,
            team.team_id,
            team.team_name,
            team.wins,
            team.losses,
            team.ties,
            team.points_for,
            team.points_against,
            # espn-api leaves logo_url as "" for teams that never set one.
            getattr(team, "logo_url", None) or None,
        )
        for team in league.teams
    ]
    conn.executemany(
        """
        INSERT INTO teams (league_id, team_id, team_name, wins, losses, ties,
                           points_for, points_against, logo_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(league_id, team_id) DO UPDATE SET
            team_name=excluded.team_name,
            wins=excluded.wins,
            losses=excluded.losses,
            ties=excluded.ties,
            points_for=excluded.points_for,
            points_against=excluded.points_against,
            logo_url=excluded.logo_url
        WHERE teams.team_name      IS DISTINCT FROM excluded.team_name
           OR teams.wins           IS DISTINCT FROM excluded.wins
           OR teams.losses         IS DISTINCT FROM excluded.losses
           OR teams.ties           IS DISTINCT FROM excluded.ties
           OR teams.points_for     IS DISTINCT FROM excluded.points_for
           OR teams.points_against IS DISTINCT FROM excluded.points_against
           OR teams.logo_url       IS DISTINCT FROM excluded.logo_url
        """,
        rows,
    )


def sync_players(conn, league: League) -> None:
    """Upsert global player identity from every team's roster.

    gsis_id is deliberately not touched here — ESPN doesn't know it. It's filled in by
    stats_sync.link_players() from the nflverse side.
    """
    now = datetime.now(timezone.utc).isoformat()
    seen: dict[int, tuple] = {}
    for team in league.teams:
        for player in team.roster:
            seen[player.playerId] = (
                player.playerId,
                player.name,
                normalize_player_name(player.name),
                player.position,
                player.proTeam,
                now,
            )

    conn.executemany(
        """
        INSERT INTO players (player_id, full_name, normalized_name, position, pro_team, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET
            full_name=excluded.full_name,
            normalized_name=excluded.normalized_name,
            position=excluded.position,
            pro_team=excluded.pro_team,
            updated_at=excluded.updated_at
        WHERE players.full_name IS DISTINCT FROM excluded.full_name
           OR players.position  IS DISTINCT FROM excluded.position
           OR players.pro_team  IS DISTINCT FROM excluded.pro_team
        """,
        list(seen.values()),
    )


def sync_roster(conn, team, league_id: str) -> None:
    """Upsert this team's roster, then remove only the players who actually left.

    Not delete-then-insert. That rewrote every row on every sync — 200% tuple churn on
    a table whose contents barely change — which at a few thousand leagues means tens of
    millions of dead tuples a day and autovacuum falling behind. The WHERE on DO UPDATE
    is what makes an unchanged roster cost zero writes; it only works because the table
    has no per-row updated_at to invalidate it.
    """
    rows = [
        (
            league_id,
            team.team_id,
            player.playerId,
            player.lineupSlot,
            player.injuryStatus,
            player.total_points,
            player.projected_total_points,
        )
        for player in team.roster
    ]

    conn.executemany(
        """
        INSERT INTO rosters (
            league_id, team_id, player_id, lineup_slot, injury_status,
            total_points, projected_total_points
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(league_id, team_id, player_id) DO UPDATE SET
            lineup_slot=excluded.lineup_slot,
            injury_status=excluded.injury_status,
            total_points=excluded.total_points,
            projected_total_points=excluded.projected_total_points
        WHERE rosters.lineup_slot            IS DISTINCT FROM excluded.lineup_slot
           OR rosters.injury_status          IS DISTINCT FROM excluded.injury_status
           OR rosters.total_points           IS DISTINCT FROM excluded.total_points
           OR rosters.projected_total_points IS DISTINCT FROM excluded.projected_total_points
        """,
        rows,
    )

    # Drop anyone no longer on the roster. Empty roster -> delete them all.
    player_ids = [player.playerId for player in team.roster]
    if player_ids:
        placeholders = ", ".join("?" for _ in player_ids)
        conn.execute(
            f"DELETE FROM rosters WHERE league_id = ? AND team_id = ? "
            f"AND player_id NOT IN ({placeholders})",
            (league_id, team.team_id, *player_ids),
        )
    else:
        conn.execute(
            "DELETE FROM rosters WHERE league_id = ? AND team_id = ?",
            (league_id, team.team_id),
        )


def sync_matchups(conn, league: League, league_id: str, week: int) -> None:
    """Every matchup in the week. Like teams, no is_self — "your matchup" is derived
    per request from the caller's team id."""
    box_scores = league.box_scores(week=week)

    rows = []
    for box in box_scores:
        if box.home_team is None or box.away_team is None:
            continue  # bye week
        rows.append(
            (
                league_id,
                week,
                box.home_team.team_id,
                box.away_team.team_id,
                box.home_score,
                box.away_score,
                box.home_projected,
                box.away_projected,
                int(box.is_playoff),
            )
        )

    conn.executemany(
        """
        INSERT INTO matchups (
            league_id, week, home_team_id, away_team_id, home_score, away_score,
            home_projected, away_projected, is_playoff
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(league_id, week, home_team_id, away_team_id) DO UPDATE SET
            home_score=excluded.home_score,
            away_score=excluded.away_score,
            home_projected=excluded.home_projected,
            away_projected=excluded.away_projected,
            is_playoff=excluded.is_playoff
        WHERE matchups.home_score     IS DISTINCT FROM excluded.home_score
           OR matchups.away_score     IS DISTINCT FROM excluded.away_score
           OR matchups.home_projected IS DISTINCT FROM excluded.home_projected
           OR matchups.away_projected IS DISTINCT FROM excluded.away_projected
           OR matchups.is_playoff     IS DISTINCT FROM excluded.is_playoff
        """,
        rows,
    )


def record_league_sync(conn, league_id: str, ctx: LeagueCtx) -> None:
    """Stamp the league's freshness in one place.

    This is where sync time lives now that rosters has no per-row updated_at, and it's
    what Phase 5's "refresh only if stale" check will read.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO leagues (league_id, season, name, last_synced_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(league_id) DO UPDATE SET
            season = COALESCE(excluded.season, leagues.season),
            name = COALESCE(excluded.name, leagues.name),
            last_synced_at = excluded.last_synced_at
        """,
        (league_id, ctx.season, ctx.label, now),
    )


def run(ctx: LeagueCtx | None = None) -> None:
    ctx = ctx or config.load_league_ctx()
    league = get_league(ctx)
    league_id = ctx.key
    self_team_id = find_self_team_id(league, ctx)

    config.sync_league_name(league_id, getattr(league.settings, "name", None))
    # Persist whichever team we resolved as the user's, so queries can derive is_self
    # without re-running SWID matching. In the hosted build this is user_leagues.espn_team_id.
    config.sync_self_team_id(league_id, self_team_id)

    conn = db.connect()
    try:
        init_db(conn, league_id)
        sync_teams(conn, league, league_id)
        sync_players(conn, league)

        for team in league.teams:
            sync_roster(conn, team, league_id)

        for week in range(1, league.current_week + 1):
            sync_matchups(conn, league, league_id, week)

        record_league_sync(conn, league_id, ctx)
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
