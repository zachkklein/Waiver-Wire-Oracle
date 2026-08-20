"""Copy a local SQLite database into Postgres.

    DATABASE_URL=postgresql://... python3 scripts/migrate_to_postgres.py [--dry-run]

One-way and idempotent: every table upserts on its primary key, so re-running is safe
and picks up anything that changed. Reads SQLite directly (not through db.py, which
would follow DATABASE_URL to the destination) and writes through db.py.

The destination schema must already exist — apply the migrations in supabase/migrations
first. This script moves rows, it does not create tables.

`leagues` is populated from the ESPN leagues found in the SQLite data, so the hosted
build has the shared-league rows the plan calls for. `users`/`user_leagues` stay empty:
there are no accounts until Phase 3, and this database has no way to know whose league
this was.
"""

import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import db

# Ordered so that anything with a foreign key lands after what it references.
TABLES = ("teams", "rosters", "matchups", "player_stats")

PRIMARY_KEYS = {
    "teams": ("league_id", "team_id"),
    "rosters": ("league_id", "team_id", "player_id"),
    "matchups": ("league_id", "week", "home_team_id", "away_team_id"),
    "player_stats": ("player_id", "season", "week", "season_type"),
}

BATCH = 500


def _sqlite_conn() -> sqlite3.Connection:
    if not os.path.exists(config.DB_PATH):
        raise SystemExit(f"No SQLite database at {config.DB_PATH} — nothing to migrate.")
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _upsert_sql(table: str, columns: list[str]) -> str:
    keys = PRIMARY_KEYS[table]
    updatable = [c for c in columns if c not in keys]
    collist = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    setlist = ", ".join(f"{c} = excluded.{c}" for c in updatable)
    return (
        f"INSERT INTO {table} ({collist}) VALUES ({placeholders}) "
        f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {setlist}"
    )


def copy_table(src: sqlite3.Connection, dest, table: str, dry_run: bool) -> int:
    src_columns = [r["name"] for r in src.execute(f"PRAGMA table_info({table})")]
    if not src_columns:
        print(f"  {table}: not present in SQLite, skipping")
        return 0

    # Only copy columns the destination actually has, so a schema that has moved on
    # doesn't break the migration.
    dest_columns = set(db.column_names(dest, table))
    missing = [c for c in src_columns if c not in dest_columns]
    columns = [c for c in src_columns if c in dest_columns]
    if missing:
        print(f"  {table}: skipping columns absent from Postgres: {', '.join(missing)}")
    if not columns:
        raise SystemExit(f"{table}: no columns in common between SQLite and Postgres.")

    rows = src.execute(f"SELECT {', '.join(columns)} FROM {table}").fetchall()
    if dry_run:
        print(f"  {table}: would copy {len(rows)} rows")
        return len(rows)

    sql = _upsert_sql(table, columns)
    for start in range(0, len(rows), BATCH):
        dest.executemany(sql, [tuple(r) for r in rows[start : start + BATCH]])
    print(f"  {table}: copied {len(rows)} rows")
    return len(rows)


def seed_leagues(src: sqlite3.Connection, dest, dry_run: bool) -> int:
    """Create a `leagues` row for each league present in the synced data."""
    league_ids = [r["league_id"] for r in src.execute("SELECT DISTINCT league_id FROM teams")]
    if dry_run:
        print(f"  leagues: would seed {len(league_ids)} rows")
        return len(league_ids)

    active = config.load_league_ctx()
    for league_id in league_ids:
        # Only the active league's season/label are knowable from local settings.
        season = active.season if league_id == active.key else None
        label = active.label if league_id == active.key else None
        dest.execute(
            "INSERT INTO leagues (league_id, season, name) VALUES (?, ?, ?) "
            "ON CONFLICT (league_id) DO UPDATE SET "
            "season = COALESCE(excluded.season, leagues.season), "
            "name = COALESCE(excluded.name, leagues.name)",
            (league_id, season, label),
        )
    print(f"  leagues: seeded {len(league_ids)} rows")
    return len(league_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report counts, write nothing")
    args = parser.parse_args()

    if not db.is_postgres():
        raise SystemExit("DATABASE_URL is not set — nothing to migrate into.")

    src = _sqlite_conn()
    dest = db.connect()
    print(f"SQLite {config.DB_PATH} -> Postgres")
    try:
        total = sum(copy_table(src, dest, t, args.dry_run) for t in TABLES)
        seed_leagues(src, dest, args.dry_run)
        if not args.dry_run:
            dest.commit()
    finally:
        dest.close()
        src.close()

    print(f"{'Would copy' if args.dry_run else 'Copied'} {total} rows.")


if __name__ == "__main__":
    main()
