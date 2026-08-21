"""Where a user's leagues and settings live.

Two backends behind one interface, picked per request by whether the caller is a
signed-in account (``auth.Principal.is_account``):

* **No account** — ``data/settings.json``, via ``config.py``. This is the self-hosted
  install, and its behaviour is exactly what it was before accounts existed.
* **An account** — the ``users`` / ``leagues`` / ``user_leagues`` / ``user_settings``
  tables. Twelve people in one league share one copy of ``teams``/``rosters``/``matchups``
  (keyed by ESPN's league id, unchanged since Phase 2) and differ only in their
  ``user_leagues`` row: which team is theirs, which league they're looking at, and the
  ESPN cookies used to sync it.

Every function takes a ``Principal`` first, for the same reason every tool takes a
``LeagueCtx``: "the active league" is a property of the requester, never of the process.
This module is the *only* place allowed to branch on which of the two it is — routers,
tools, and ingests just receive a context.

Secrets (``espn_swid_enc``, ``espn_s2_enc``, ``openrouter_key_enc``) are written in the
clear for now; the columns are named for the ciphertext that Phase 4 puts in them. Read
and write them only through :func:`_secret` / the writers here, so that change is
confined to this file.
"""

import config
import db
from auth import Principal
from context import LeagueCtx, UserCtx


class StoreError(Exception):
    """A request that the store can't satisfy — reported to the user, not a bug."""


# --------------------------------------------------------------------------------------
# Account-backed implementation
# --------------------------------------------------------------------------------------


def _secret(value):
    """Unwrap a stored credential. Phase 4 decrypts here."""
    return value or None


def _seal(value):
    """Wrap a credential for storage. Phase 4 encrypts here."""
    return value or None


def ensure_account(principal: Principal) -> None:
    """Make sure a signed-in account has a ``users`` row.

    Provisioned just in time rather than by a trigger on ``auth.users``: it works however
    the account was created, and keeps the schema runnable on plain Postgres. Called from
    every write path and from ``GET /api/auth/me``; reads don't need it, since an account
    with no rows simply has no leagues.
    """
    if not principal.is_account:
        return
    with db.session(commit=True) as conn:
        conn.execute(
            """
            INSERT INTO users (id, email) VALUES (?, ?)
            ON CONFLICT (id) DO UPDATE SET email = excluded.email
            WHERE users.email IS DISTINCT FROM excluded.email
            """,
            (principal.user_id, principal.email or ""),
        )


_LEAGUE_COLUMNS = """
    ul.league_id, ul.espn_team_id, ul.espn_swid_enc, ul.espn_s2_enc,
    ul.label AS user_label, ul.is_default, l.season, l.name AS league_name
"""


def _rows(conn, user_id: str) -> list:
    """Every league this account is linked to, active one first, then oldest first.

    The `created_at` tiebreak matters for the same reason the standings sort has one:
    without it, a user with two leagues and no default has no defined "first" league.
    """
    return conn.execute(
        f"""
        SELECT {_LEAGUE_COLUMNS}
        FROM user_leagues ul
        JOIN leagues l ON l.league_id = ul.league_id
        WHERE ul.user_id = ?
        ORDER BY ul.is_default DESC, ul.created_at, ul.league_id
        """,
        (user_id,),
    ).fetchall()


def _active_row(conn, user_id: str):
    rows = _rows(conn, user_id)
    return rows[0] if rows else None


def _ctx_from_row(row) -> LeagueCtx:
    return LeagueCtx(
        league_id=row["league_id"],
        season=row["season"],
        swid=_secret(row["espn_swid_enc"]),
        s2=_secret(row["espn_s2_enc"]),
        team_id=row["espn_team_id"],
        # ESPN's own name first: this is display text shared by everyone in the league,
        # whereas user_label is one person's rename of it.
        label=row["league_name"] or row["user_label"] or row["league_id"],
    )


def _db_load_league_ctx(principal: Principal) -> LeagueCtx:
    with db.session() as conn:
        row = _active_row(conn, principal.user_id)
    return _ctx_from_row(row) if row else LeagueCtx()


def _db_load_user_ctx(principal: Principal) -> UserCtx:
    """The account's Oracle credentials, falling back to the deployment's own key.

    That fallback is the hosted product's default (``docs/HOSTED_PLAN.md``: our key with
    a metered free tier); a user who saves their own key overrides it.
    """
    with db.session() as conn:
        row = conn.execute(
            "SELECT openrouter_key_enc, openrouter_model FROM user_settings WHERE user_id = ?",
            (principal.user_id,),
        ).fetchone()

    key = _secret(row["openrouter_key_enc"]) if row else None
    model = (row["openrouter_model"] if row else None) or None
    return UserCtx(
        openrouter_api_key=key or config.shared_openrouter_key(),
        openrouter_model=model or config.default_openrouter_model(),
    )


def _db_list_leagues(principal: Principal) -> list:
    with db.session() as conn:
        rows = _rows(conn, principal.user_id)
    return [
        {
            "league_id": r["league_id"],
            "label": r["user_label"] or r["league_name"] or r["league_id"],
            "season": r["season"] or "",
            "active": i == 0,  # _rows() puts the default first
            "has_espn_swid": bool(r["espn_swid_enc"]),
            "has_espn_s2": bool(r["espn_s2_enc"]),
        }
        for i, r in enumerate(rows)
    ]


def _db_settings_summary(principal: Principal) -> dict:
    ctx = _db_load_league_ctx(principal)
    user = _db_load_user_ctx(principal)
    with db.session() as conn:
        row = conn.execute(
            "SELECT openrouter_key_enc FROM user_settings WHERE user_id = ?",
            (principal.user_id,),
        ).fetchone()

    return {
        "ESPN_LEAGUE_ID": ctx.league_id or "",
        "ESPN_SEASON": ctx.season or "",
        "ESPN_TEAM_ID": ctx.team_id or "",
        "OPENROUTER_MODEL": user.openrouter_model,
        # News feeds are global infrastructure config, not per-account — the hosted UI
        # hides the field rather than pretending each user can edit them.
        "RSS_FEED_URLS": config.rss_feed_urls(),
        "configured": ctx.is_configured,
        "has_espn_swid": bool(ctx.swid),
        "has_espn_s2": bool(ctx.s2),
        # The deployment's shared key doesn't count: this drives "already saved — type to
        # replace it", and the user has saved nothing.
        "has_openrouter_api_key": bool(row and row["openrouter_key_enc"]),
    }


def _upsert_league(conn, league_id: str, season) -> None:
    """The shared row every user_leagues entry points at.

    Deliberately doesn't touch `leagues.name`: that column is ESPN's own name for the
    league, shared by everyone in it, and only a sync (record_league_name) may write it.
    A user's `user_leagues.label` is theirs alone — writing it here meant the first
    person to add a league renamed it for all twelve of them.
    """
    conn.execute(
        """
        INSERT INTO leagues (league_id, season) VALUES (?, ?)
        ON CONFLICT (league_id) DO UPDATE SET
            season = COALESCE(excluded.season, leagues.season)
        WHERE leagues.season IS DISTINCT FROM COALESCE(excluded.season, leagues.season)
        """,
        (league_id, season),
    )


def _make_default(conn, user_id: str, league_id: str) -> None:
    """Point the account at one league. Clear-then-set in a single transaction, which
    the partial unique index on (user_id) WHERE is_default keeps honest."""
    conn.execute(
        "UPDATE user_leagues SET is_default = FALSE WHERE user_id = ? AND is_default",
        (user_id,),
    )
    conn.execute(
        "UPDATE user_leagues SET is_default = TRUE WHERE user_id = ? AND league_id = ?",
        (user_id, league_id),
    )


def _db_add_league(principal: Principal, values: dict) -> None:
    league_id = str(values.get("ESPN_LEAGUE_ID") or "").strip()
    if not league_id:
        raise StoreError("ESPN_LEAGUE_ID is required.")

    ensure_account(principal)
    user_id = principal.user_id

    with db.session(commit=True) as conn:
        existing = conn.execute(
            "SELECT 1 AS hit FROM user_leagues WHERE user_id = ? AND league_id = ?",
            (user_id, league_id),
        ).fetchone()
        if existing:
            raise StoreError(f"League {league_id} has already been added.")

        _upsert_league(conn, league_id, values.get("ESPN_SEASON"))
        conn.execute(
            """
            INSERT INTO user_leagues
                (user_id, league_id, espn_team_id, espn_swid_enc, espn_s2_enc, label,
                 credentials_valid_at)
            VALUES (?, ?, ?, ?, ?, ?, now())
            """,
            (
                user_id,
                league_id,
                values.get("ESPN_TEAM_ID"),
                _seal(values.get("ESPN_SWID")),
                _seal(values.get("ESPN_S2")),
                values.get("label"),
            ),
        )
        _make_default(conn, user_id, league_id)


def _db_save_settings(principal: Principal, values: dict) -> None:
    """Edit the account's active league, plus its Oracle settings.

    Mirrors ``config.save_settings``: keys mapped to ``None`` are left alone, so the UI
    can omit a secret it never received rather than blanking it.
    """
    ensure_account(principal)
    user_id = principal.user_id

    league_id = (values.get("ESPN_LEAGUE_ID") or "").strip() or None

    with db.session(commit=True) as conn:
        row = _active_row(conn, user_id)

        if league_id and (row is None or row["league_id"] != league_id):
            # Either the first league, or the user retyped a different id — which in this
            # schema is a different row, since (user_id, league_id) is the primary key.
            if row is not None:
                conn.execute(
                    "DELETE FROM user_leagues WHERE user_id = ? AND league_id = ?",
                    (user_id, row["league_id"]),
                )
            merged = {
                "ESPN_SWID": values.get("ESPN_SWID") or (row and _secret(row["espn_swid_enc"])),
                "ESPN_S2": values.get("ESPN_S2") or (row and _secret(row["espn_s2_enc"])),
                **{k: v for k, v in values.items() if v is not None},
            }
            _upsert_league(conn, league_id, merged.get("ESPN_SEASON"))
            conn.execute(
                """
                INSERT INTO user_leagues
                    (user_id, league_id, espn_team_id, espn_swid_enc, espn_s2_enc, label,
                     credentials_valid_at)
                VALUES (?, ?, ?, ?, ?, ?, now())
                """,
                (
                    user_id,
                    league_id,
                    merged.get("ESPN_TEAM_ID"),
                    _seal(merged.get("ESPN_SWID")),
                    _seal(merged.get("ESPN_S2")),
                    merged.get("label"),
                ),
            )
            _make_default(conn, user_id, league_id)
        elif row is not None:
            if values.get("ESPN_SEASON"):
                _upsert_league(conn, row["league_id"], values.get("ESPN_SEASON"))

            updates = {
                "espn_team_id": values.get("ESPN_TEAM_ID"),
                "espn_swid_enc": _seal(values.get("ESPN_SWID")),
                "espn_s2_enc": _seal(values.get("ESPN_S2")),
                "label": values.get("label"),
            }
            updates = {k: v for k, v in updates.items() if v is not None}
            if updates:
                assignments = ", ".join(f"{col} = ?" for col in updates)
                # Stamp the cookies as accepted now, so Phase 5 can prefer the most
                # recently validated credentials when several users share a league.
                if "espn_swid_enc" in updates or "espn_s2_enc" in updates:
                    assignments += ", credentials_valid_at = now()"
                conn.execute(
                    f"UPDATE user_leagues SET {assignments} WHERE user_id = ? AND league_id = ?",
                    (*updates.values(), user_id, row["league_id"]),
                )

        key = values.get("OPENROUTER_API_KEY")
        model = values.get("OPENROUTER_MODEL")
        if key is not None or model is not None:
            conn.execute(
                """
                INSERT INTO user_settings (user_id, openrouter_key_enc, openrouter_model)
                VALUES (?, ?, ?)
                ON CONFLICT (user_id) DO UPDATE SET
                    openrouter_key_enc =
                        COALESCE(excluded.openrouter_key_enc, user_settings.openrouter_key_enc),
                    openrouter_model =
                        COALESCE(excluded.openrouter_model, user_settings.openrouter_model)
                """,
                (user_id, _seal(key), model),
            )


def _db_set_active_league(principal: Principal, league_id: str) -> None:
    with db.session(commit=True) as conn:
        row = conn.execute(
            "SELECT 1 AS hit FROM user_leagues WHERE user_id = ? AND league_id = ?",
            (principal.user_id, league_id),
        ).fetchone()
        if not row:
            raise StoreError(f"Unknown league '{league_id}'.")
        _make_default(conn, principal.user_id, league_id)


def _db_delete_league(principal: Principal, league_id: str) -> None:
    """Unlink this account from a league.

    Only the link goes: ``leagues``/``teams``/``rosters``/``matchups`` are shared with
    everyone else in that league, so deleting them would take the data out from under
    them. Orphaned league data is Phase 5's problem, alongside the sync worker.
    """
    with db.session(commit=True) as conn:
        cur = conn.execute(
            "DELETE FROM user_leagues WHERE user_id = ? AND league_id = ?",
            (principal.user_id, league_id),
        )
        if cur.rowcount == 0:
            raise StoreError(f"Unknown league '{league_id}'.")

        remaining = _rows(conn, principal.user_id)
        if remaining and not remaining[0]["is_default"]:
            _make_default(conn, principal.user_id, remaining[0]["league_id"])


def _db_record_league_name(principal: Principal, league_id: str, name: str) -> None:
    if not name:
        return
    with db.session(commit=True) as conn:
        # Upsert rather than update: add_league creates the row first in practice, but a
        # sync triggered any other way shouldn't silently drop the name.
        conn.execute(
            """
            INSERT INTO leagues (league_id, name) VALUES (?, ?)
            ON CONFLICT (league_id) DO UPDATE SET name = excluded.name
            WHERE leagues.name IS DISTINCT FROM excluded.name
            """,
            (league_id, name),
        )


def _db_record_self_team_id(principal: Principal, league_id: str, team_id) -> None:
    if team_id is None:
        return
    with db.session(commit=True) as conn:
        conn.execute(
            "UPDATE user_leagues SET espn_team_id = ? "
            "WHERE user_id = ? AND league_id = ? AND espn_team_id IS DISTINCT FROM ?",
            (str(team_id), principal.user_id, league_id, str(team_id)),
        )


# --------------------------------------------------------------------------------------
# The public interface: dispatch on whether there's an account behind the request
# --------------------------------------------------------------------------------------


def load_league_ctx(principal: Principal) -> LeagueCtx:
    if principal.is_account:
        return _db_load_league_ctx(principal)
    return config.load_league_ctx()


def load_user_ctx(principal: Principal) -> UserCtx:
    if principal.is_account:
        return _db_load_user_ctx(principal)
    return config.load_user_ctx()


def is_configured(principal: Principal) -> bool:
    return load_league_ctx(principal).is_configured


def settings_summary(principal: Principal) -> dict:
    if principal.is_account:
        return _db_settings_summary(principal)
    return config.settings_summary()


def save_settings(principal: Principal, values: dict) -> None:
    if principal.is_account:
        _db_save_settings(principal, values)
        return
    config.save_settings(values)


def list_leagues(principal: Principal) -> list:
    if principal.is_account:
        return _db_list_leagues(principal)
    return config.list_leagues()


def add_league(principal: Principal, values: dict) -> None:
    if principal.is_account:
        _db_add_league(principal, values)
        return
    try:
        config.add_league(values)
    except ValueError as exc:
        raise StoreError(str(exc)) from exc


def set_active_league(principal: Principal, league_id: str) -> None:
    if principal.is_account:
        _db_set_active_league(principal, league_id)
        return
    try:
        config.set_active_league(league_id)
    except ValueError as exc:
        raise StoreError(str(exc)) from exc


def delete_league(principal: Principal, league_id: str) -> None:
    if principal.is_account:
        _db_delete_league(principal, league_id)
        return
    try:
        config.delete_league(league_id)
    except ValueError as exc:
        raise StoreError(str(exc)) from exc


def record_league_name(principal: Principal, league_id: str, name: str | None) -> None:
    """Persist ESPN's own name for a league, so the switcher shows something better
    than a numeric id. Called from the sync, which fetches the name anyway."""
    if principal.is_account:
        _db_record_league_name(principal, league_id, name or "")
        return
    config.sync_league_name(league_id, name or "")


def record_self_team_id(principal: Principal, league_id: str, team_id) -> None:
    """Persist which team the sync resolved as this user's.

    ``is_self`` is derived per request from here rather than stored on the shared
    ``teams`` rows — with two members of one league signed up, a stored flag would belong
    to whoever synced last.
    """
    if principal.is_account:
        _db_record_self_team_id(principal, league_id, team_id)
        return
    config.sync_self_team_id(league_id, team_id)
