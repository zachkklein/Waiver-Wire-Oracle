"""Database access, over either SQLite or Postgres.

Set ``DATABASE_URL`` and the app talks to Postgres (Supabase, for the hosted build);
leave it unset and it uses the local ``data/db.sqlite`` file, so ``git clone && main.py
serve`` still needs no external services. That's the whole reason this layer exists —
see ``docs/HOSTED_PLAN.md``.

Callers write SQL once, in SQLite's ``?`` placeholder style, and :func:`connect` returns
a connection that translates it for Postgres. Rows behave like mappings on both backends
(``row["team_name"]``), so read them by name — positional access is not portable.

The table definitions in ``ingest/*.py`` are deliberately written in the subset both
backends share (``CREATE TABLE IF NOT EXISTS``, ``TEXT``/``INTEGER``/``REAL``, composite
``PRIMARY KEY``, ``ON CONFLICT ... DO UPDATE SET x = excluded.x``), so one schema string
runs on both. Keep new DDL inside that subset. In particular keep booleans as ``INTEGER``
0/1 rather than Postgres ``BOOLEAN``: the frontend guards them with a ternary
(``{t.is_self ? ... : null}``) and expects a number.
"""

import os
import re
import sqlite3
from contextlib import contextmanager

import config


# psycopg wants a libpq connection string. Supabase's dashboard offers several URLs
# on different pages, and the API one (https://<ref>.supabase.co) is the easy mistake.
_POSTGRES_SCHEMES = ("postgresql://", "postgres://")


def database_url() -> str | None:
    """The Postgres URL, or None when running on the local SQLite file."""
    url = os.getenv("DATABASE_URL") or None
    if url and not url.startswith(_POSTGRES_SCHEMES):
        raise RuntimeError(
            "DATABASE_URL must be a Postgres connection string starting with "
            f"postgresql://, but got {url.split('://')[0]}://...\n"
            "In Supabase that's Project Settings -> Database -> Connection string -> "
            "URI (prefer the pooled one on port 6543) — not the Project URL under "
            "Project Settings -> API, which is an https:// address for PostgREST."
        )
    return url


def is_postgres() -> bool:
    return bool(database_url())


def _to_pg(sql: str) -> str:
    """Rewrite SQLite-style SQL for psycopg.

    Two substitutions: every literal ``%`` is doubled (psycopg scans the whole query
    for placeholders, so an unescaped one is a syntax error), then each ``?`` outside a
    string literal becomes ``%s``. Order matters — doubling first means the ``%s`` we
    introduce is never itself escaped.

    Our queries never contain a literal ``%``: ``LIKE`` wildcards are passed as
    parameters (``f"%{team}%"``), not baked into the SQL. The escape is here so that
    stays true by construction rather than by luck.
    """
    sql = sql.replace("%", "%%")

    out, in_string = [], False
    for ch in sql:
        if ch == "'":
            in_string = not in_string
        if ch == "?" and not in_string:
            out.append("%s")
        else:
            out.append(ch)
    return "".join(out)


# One pool per process, created on first use. Opening a fresh connection per request
# means a TLS handshake to the database's region every time: that measured ~0.7s of
# pure overhead, turning a 5ms SQLite endpoint into a 2.5s one. The pool amortises it.
#
# This is a module-level global, unlike anything in context.py, and that's fine — it's
# infrastructure shared by every request, not per-user state.
_pool = None
_pool_url = None


def _get_pool():
    global _pool, _pool_url
    url = database_url()
    if _pool is None or _pool_url != url:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        if _pool is not None:
            _pool.close()  # DATABASE_URL changed under us (tests, mostly)
        _pool = ConnectionPool(
            url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
            open=True,
        )
        _pool_url = url
    return _pool


def close_pool() -> None:
    """Drop the pool. For tests, and for a clean process shutdown."""
    global _pool, _pool_url
    if _pool is not None:
        _pool.close()
        _pool, _pool_url = None, None


class _PgConnection:
    """Wraps a pooled psycopg connection in the slice of the sqlite3 API we use."""

    def __init__(self, raw, pool=None):
        self._raw = raw
        self._pool = pool

    def execute(self, sql, params=()):
        cur = self._raw.cursor()
        cur.execute(_to_pg(sql), tuple(params))
        return cur

    def executemany(self, sql, seq_of_params):
        cur = self._raw.cursor()
        cur.executemany(_to_pg(sql), [tuple(p) for p in seq_of_params])
        return cur

    def executescript(self, sql):
        # psycopg runs a multi-statement string in one call, which is what
        # sqlite3.executescript does; the DDL is written to suit both.
        cur = self._raw.cursor()
        cur.execute(_to_pg(sql))
        return cur

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        """Return the connection to the pool rather than dropping it.

        Roll back first so the connection goes back IDLE. psycopg is not autocommit, so
        even a plain SELECT leaves it INTRANS; handing it back in that state makes
        psycopg_pool reset it and log "rolling back returned connection" on every single
        request. Uncommitted work is discarded either way — commit() is always explicit —
        this just keeps the logs readable.
        """
        if self._pool is None:
            self._raw.close()
            return
        try:
            self._raw.rollback()
        finally:
            self._pool.putconn(self._raw)


def connect():
    """Open a connection. Callers are responsible for commit()/close(), or use
    :func:`session` to get both handled."""
    if is_postgres():
        pool = _get_pool()
        return _PgConnection(pool.getconn(), pool)

    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row  # so rows are readable by column name on both backends
    return conn


@contextmanager
def session(commit: bool = False):
    """Connection as a context manager: commits on clean exit when asked, always closes."""
    conn = connect()
    try:
        yield conn
        if commit:
            conn.commit()
    finally:
        conn.close()


def is_initialized() -> bool:
    """True when there's a database with our tables in it.

    Replaces the old ``os.path.exists(DB_PATH)`` check, which only ever made sense for a
    file-backed database. A fresh install has neither a file nor any tables.
    """
    if is_postgres():
        try:
            with session() as conn:
                return "teams" in table_names(conn)
        except Exception:
            return False
    return os.path.exists(config.DB_PATH)


def table_names(conn) -> set:
    """Every table in the database, portably."""
    if is_postgres():
        rows = conn.execute(
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        ).fetchall()
    else:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def column_names(conn, table: str) -> list:
    """Column names for `table`, portably. Returns [] when the table doesn't exist.

    `table` is interpolated (PRAGMA takes no parameters), so it's validated against an
    identifier pattern first — every caller passes a hardcoded name, and this keeps it
    that way.
    """
    if not _IDENTIFIER.match(table):
        raise ValueError(f"Not a valid table name: {table!r}")

    if is_postgres():
        rows = conn.execute(
            "SELECT column_name AS name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = ? ORDER BY ordinal_position",
            (table,),
        ).fetchall()
        return [row["name"] for row in rows]

    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
