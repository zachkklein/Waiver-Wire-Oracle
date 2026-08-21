"""Shared configuration.

Values come from three places, in priority order:

1. ``data/settings.json`` — written by the in-app setup screen (``PUT /api/settings``,
   ``POST /api/leagues``, etc.)
2. environment / ``.env`` — handy for headless or container setups
3. built-in defaults

Paths and the OpenRouter base URL are plain module constants. Everything a user can
change is read fresh from disk on each access, so a save from the setup screen takes
effect immediately, without restarting the server.

Multiple ESPN leagues can be configured (``data/settings.json``'s ``leagues`` list); one
is "active" at a time (``active_league_id``). ``load_league_ctx()`` builds a
:class:`~context.LeagueCtx` for that active league, and ``load_user_ctx()`` a
:class:`~context.UserCtx` from the global OpenRouter settings.

**These two loaders are the only supported way to read a league or an API key.** There
is deliberately no ``config.ESPN_LEAGUE_ID`` attribute any more: "the active league" is
a property of this process, and that stops being meaningful the moment two people use a
hosted build at once. Callers take a context object as an argument instead. See
``context.py`` and ``docs/HOSTED_PLAN.md``.

``RSS_FEED_URLS`` stays a module-level read (``rss_feed_urls()``): news is global
infrastructure config, not per-user.
"""

import json
import os

from dotenv import load_dotenv

from context import DEFAULT_OPENROUTER_MODEL, LeagueCtx, UserCtx

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR") or os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "db.sqlite")
CHROMA_PATH = os.path.join(DATA_DIR, "chroma")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Sensible starting feeds so a fresh install has news to search without hunting for URLs.
DEFAULT_RSS_FEED_URLS = [
    "https://www.cbssports.com/rss/headlines/nfl/",
    "https://www.espn.com/espn/rss/nfl/news",
    "https://profootballtalk.nbcsports.com/feed/",
    "https://www.rotowire.com/rss/news.php?sport=NFL",
]

# Per-league fields — live inside one entry of settings.json's "leagues" list, keyed by
# ESPN_LEAGUE_ID. ESPN_SWID/ESPN_S2 are only needed for private leagues; ESPN_TEAM_ID
# identifies "your" team when there are no cookies to match against.
LEAGUE_FIELDS = (
    "ESPN_LEAGUE_ID",
    "ESPN_SEASON",
    "ESPN_SWID",
    "ESPN_S2",
    "ESPN_TEAM_ID",
)

# Global fields — shared across every league, stored at the top level of settings.json.
GLOBAL_SETTING_KEYS = (
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "RSS_FEED_URLS",
)

# All user-settable keys. Don't add a new user-settable value without adding it here
# (as a LEAGUE_FIELDS entry if it varies per league, GLOBAL_SETTING_KEYS otherwise).
SETTING_KEYS = LEAGUE_FIELDS + GLOBAL_SETTING_KEYS

SECRET_KEYS = ("ESPN_SWID", "ESPN_S2", "OPENROUTER_API_KEY")

_cache: dict = {"mtime": None, "data": {}}


def _migrate_legacy(data: dict) -> dict:
    """Fold pre-multi-league settings.json (flat ESPN_* keys, no "leagues" list) into
    a single league entry. Returns `data` unchanged (same object) when there's nothing
    to migrate, so callers can tell with `is not`."""
    if "leagues" in data:
        return data
    if not any(data.get(k) for k in LEAGUE_FIELDS):
        return data  # fresh install, or headless/.env-only — nothing persisted to migrate

    league_id = str(data.get("ESPN_LEAGUE_ID") or "")
    entry = {k: data[k] for k in LEAGUE_FIELDS if data.get(k) is not None}
    entry["label"] = league_id or "My league"

    migrated = {k: v for k, v in data.items() if k not in LEAGUE_FIELDS}
    migrated["leagues"] = [entry]
    migrated["active_league_id"] = league_id
    return migrated


def _write_settings(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp_path = f"{SETTINGS_PATH}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, SETTINGS_PATH)  # atomic, so a crash can't truncate settings
    _cache["mtime"] = None


def _load_settings() -> dict:
    """Read settings.json, re-reading only when the file changes on disk. Migrates
    legacy single-league files in place on first read."""
    try:
        mtime = os.path.getmtime(SETTINGS_PATH)
    except OSError:
        _cache["mtime"], _cache["data"] = None, {}
        return {}

    if _cache["mtime"] != mtime:
        try:
            with open(SETTINGS_PATH) as f:
                loaded = json.load(f)
            data = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            data = {}

        migrated = _migrate_legacy(data)
        if migrated is not data:
            _write_settings(migrated)
            return _load_settings()  # re-read so mtime/cache reflect the migrated file

        _cache["data"] = data
        _cache["mtime"] = mtime
    return _cache["data"]


def _leagues() -> list:
    return list(_load_settings().get("leagues") or [])


def _active_league_id():
    return _load_settings().get("active_league_id")


def _active_league() -> dict:
    """The currently active league's field dict. Falls back to ESPN_* env vars
    (unpersisted) when no league has been added yet, so headless/.env-only setups and
    installs that predate this feature keep working without a settings.json write."""
    leagues = _leagues()
    active_id = _active_league_id()
    for entry in leagues:
        if entry.get("ESPN_LEAGUE_ID") == active_id:
            return entry
    if leagues:
        return leagues[0]

    env_league_id = os.getenv("ESPN_LEAGUE_ID")
    if not env_league_id:
        return {}
    return {
        "ESPN_LEAGUE_ID": env_league_id,
        "ESPN_SEASON": os.getenv("ESPN_SEASON"),
        "ESPN_SWID": os.getenv("ESPN_SWID"),
        "ESPN_S2": os.getenv("ESPN_S2"),
        "ESPN_TEAM_ID": os.getenv("ESPN_TEAM_ID"),
        "label": env_league_id,
    }


def save_settings(values: dict) -> None:
    """Merge `values` into settings.json. Keys mapped to None are left untouched, so
    the UI can omit secrets it never received rather than blanking them. ESPN_* fields
    update the active league (creating one from the current env/defaults first if none
    exists yet); everything else is global."""
    data = dict(_load_settings())

    league_updates = {k: v for k, v in values.items() if k in LEAGUE_FIELDS and v is not None}
    label_update = values.get("label")
    global_updates = {k: v for k, v in values.items() if k in GLOBAL_SETTING_KEYS and v is not None}

    if league_updates or label_update:
        leagues = list(data.get("leagues") or [])
        active_id = data.get("active_league_id")
        idx = next((i for i, e in enumerate(leagues) if e.get("ESPN_LEAGUE_ID") == active_id), None)
        if idx is None:
            if leagues:
                idx = 0  # active_league_id stale/missing — fall back to the first league
            else:
                leagues = [dict(_active_league())]  # materialize the implicit env-based league
                idx = 0

        entry = dict(leagues[idx])
        entry.update(league_updates)
        if label_update:
            entry["label"] = label_update
        entry.setdefault("label", entry.get("ESPN_LEAGUE_ID") or "My league")
        leagues[idx] = entry

        data["leagues"] = leagues
        data["active_league_id"] = entry.get("ESPN_LEAGUE_ID")

    for key, value in global_updates.items():
        data[key] = value

    _write_settings(data)


def add_league(values: dict) -> dict:
    """Add a new league alongside any existing ones, and make it active."""
    league_id = str(values.get("ESPN_LEAGUE_ID") or "").strip()
    if not league_id:
        raise ValueError("ESPN_LEAGUE_ID is required.")

    data = dict(_load_settings())
    leagues = list(data.get("leagues") or [])

    if not leagues:
        implicit = _active_league()  # don't lose an env-based league when adding a second
        if implicit.get("ESPN_LEAGUE_ID"):
            leagues.append(implicit)
            data.setdefault("active_league_id", implicit["ESPN_LEAGUE_ID"])

    if any(e.get("ESPN_LEAGUE_ID") == league_id for e in leagues):
        raise ValueError(f"League {league_id} has already been added.")

    entry = {k: values[k] for k in LEAGUE_FIELDS if values.get(k) is not None}
    entry["ESPN_LEAGUE_ID"] = league_id
    entry["label"] = values.get("label") or league_id

    leagues.append(entry)
    data["leagues"] = leagues
    data["active_league_id"] = league_id

    _write_settings(data)
    return entry


def sync_league_name(league_id: str, name: str) -> None:
    """Persist ESPN's own league name as this league's label, so the switcher shows
    something more useful than the numeric ID. Called from espn_sync.run() (which
    fetches the name anyway) so labels self-heal on the next sync, covering leagues
    that predate the "Connect league" preview flow (legacy migrations, .env-only
    setups) without requiring a manual re-save in Setup. No-ops if the name is empty
    or already matches."""
    if not name:
        return

    data = dict(_load_settings())
    leagues = list(data.get("leagues") or [])
    idx = next((i for i, e in enumerate(leagues) if e.get("ESPN_LEAGUE_ID") == league_id), None)

    if idx is None:
        implicit = _active_league()  # materialize the implicit env-based league, if it's this one
        if implicit.get("ESPN_LEAGUE_ID") != league_id:
            return
        leagues = [dict(implicit)]
        idx = 0
        data.setdefault("active_league_id", league_id)

    if leagues[idx].get("label") == name:
        return

    leagues[idx] = {**leagues[idx], "label": name}
    data["leagues"] = leagues
    _write_settings(data)


def sync_self_team_id(league_id: str, team_id: int | None) -> None:
    """Persist which team is the user's, as resolved during a sync.

    `is_self` used to be a column on the shared `teams`/`matchups` rows, which broke as
    soon as two members of the same league used the app — whoever synced last owned the
    flag. It's now derived per request from `LeagueCtx.team_id`, so the resolved value
    has to be stored somewhere the request can see it. Here that's settings.json; in the
    hosted build it's `user_leagues.espn_team_id`, which is per-user by construction.

    No-ops when nothing was resolved or the value already matches, so it doesn't rewrite
    settings on every sync.
    """
    if team_id is None:
        return

    data = dict(_load_settings())
    leagues = list(data.get("leagues") or [])
    idx = next((i for i, e in enumerate(leagues) if e.get("ESPN_LEAGUE_ID") == league_id), None)

    if idx is None:
        implicit = _active_league()  # materialize the implicit env-based league, if it's this one
        if implicit.get("ESPN_LEAGUE_ID") != league_id:
            return
        leagues = [dict(implicit)]
        idx = 0
        data.setdefault("active_league_id", league_id)

    if str(leagues[idx].get("ESPN_TEAM_ID") or "") == str(team_id):
        return

    leagues[idx] = {**leagues[idx], "ESPN_TEAM_ID": str(team_id)}
    data["leagues"] = leagues
    _write_settings(data)


def set_active_league(league_id: str) -> None:
    data = dict(_load_settings())
    leagues = list(data.get("leagues") or [])
    if not any(e.get("ESPN_LEAGUE_ID") == league_id for e in leagues):
        raise ValueError(f"Unknown league '{league_id}'.")
    data["active_league_id"] = league_id
    _write_settings(data)


def delete_league(league_id: str) -> None:
    data = dict(_load_settings())
    leagues = list(data.get("leagues") or [])
    remaining = [e for e in leagues if e.get("ESPN_LEAGUE_ID") != league_id]
    if len(remaining) == len(leagues):
        raise ValueError(f"Unknown league '{league_id}'.")

    data["leagues"] = remaining
    if data.get("active_league_id") == league_id:
        data["active_league_id"] = remaining[0]["ESPN_LEAGUE_ID"] if remaining else None
    _write_settings(data)


def list_leagues() -> list:
    """Every configured league, secrets redacted, active one flagged — for the league
    switcher and the setup page. Falls back to a single synthetic entry describing the
    env-configured league when nothing has been persisted yet."""
    leagues = _leagues()
    if not leagues:
        implicit = _active_league()
        if implicit.get("ESPN_LEAGUE_ID"):
            leagues = [implicit]

    active_id = _active_league_id() or (leagues[0]["ESPN_LEAGUE_ID"] if leagues else None)
    return [
        {
            "league_id": e.get("ESPN_LEAGUE_ID"),
            "label": e.get("label") or e.get("ESPN_LEAGUE_ID"),
            "season": e.get("ESPN_SEASON") or "",
            "active": e.get("ESPN_LEAGUE_ID") == active_id,
            "has_espn_swid": bool(e.get("ESPN_SWID")),
            "has_espn_s2": bool(e.get("ESPN_S2")),
        }
        for e in leagues
    ]


def is_configured() -> bool:
    """True once there's enough to sync a league (a public league needs no cookies)."""
    return load_league_ctx().is_configured


def settings_summary() -> dict:
    """Settings safe to hand to the browser — secrets reported as set/unset only.
    Describes the active league plus the global (Oracle/news) settings."""
    summary = {
        "ESPN_LEAGUE_ID": _resolve("ESPN_LEAGUE_ID") or "",
        "ESPN_SEASON": _resolve("ESPN_SEASON") or "",
        "ESPN_TEAM_ID": _resolve("ESPN_TEAM_ID") or "",
        "OPENROUTER_MODEL": _resolve("OPENROUTER_MODEL") or "",
        "RSS_FEED_URLS": _resolve("RSS_FEED_URLS"),
        "configured": is_configured(),
    }
    for key in SECRET_KEYS:
        summary[f"has_{key.lower()}"] = bool(_resolve(key))
    return summary


def _resolve(name: str):
    """One setting, in priority order: settings.json, then env, then a default.

    Internal — outside callers go through load_league_ctx()/load_user_ctx() so that a
    league is always something they were handed, never something they looked up.
    """
    if name == "RSS_FEED_URLS":
        stored = _load_settings().get("RSS_FEED_URLS")
        if isinstance(stored, list) and any(str(u).strip() for u in stored):
            return [str(u).strip() for u in stored if str(u).strip()]
        from_env = [u.strip() for u in os.getenv("RSS_FEED_URLS", "").split(",") if u.strip()]
        return from_env or list(DEFAULT_RSS_FEED_URLS)

    if name in LEAGUE_FIELDS:
        stored = _active_league().get(name)
    else:
        stored = _load_settings().get(name)

    if stored not in (None, ""):
        return str(stored)

    from_env = os.getenv(name)
    if from_env:
        return from_env

    return DEFAULT_OPENROUTER_MODEL if name == "OPENROUTER_MODEL" else None


def load_league_ctx() -> LeagueCtx:
    """The active league, as a context to pass down into tools and ingests.

    This is the seam the hosted build replaces: there, the request's league comes from
    the signed-in user's `user_leagues` row rather than from local settings, and
    everything downstream keeps working unchanged because it only ever sees a LeagueCtx.
    """
    return LeagueCtx(
        league_id=_resolve("ESPN_LEAGUE_ID"),
        season=_resolve("ESPN_SEASON"),
        swid=_resolve("ESPN_SWID"),
        s2=_resolve("ESPN_S2"),
        team_id=_resolve("ESPN_TEAM_ID"),
        label=_active_league().get("label"),
    )


def load_user_ctx() -> UserCtx:
    """Whose OpenRouter key the agent runs on — globally configured, for now."""
    return UserCtx(
        openrouter_api_key=_resolve("OPENROUTER_API_KEY"),
        openrouter_model=_resolve("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL,
    )


def rss_feed_urls() -> list:
    """News feeds — global infrastructure config, not per-league or per-user."""
    return _resolve("RSS_FEED_URLS")
