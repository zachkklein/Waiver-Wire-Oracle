"""Shared configuration.

Values come from three places, in priority order:

1. ``data/settings.json`` — written by the in-app setup screen (``PUT /api/settings``)
2. environment / ``.env`` — handy for headless or container setups
3. built-in defaults

Paths and the OpenRouter base URL are plain module constants. Everything a user can
change is resolved lazily through ``__getattr__`` so a save from the setup screen takes
effect immediately, without restarting the server — callers still just read
``config.ESPN_LEAGUE_ID`` as before.
"""

import json
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR") or os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "db.sqlite")
CHROMA_PATH = os.path.join(DATA_DIR, "chroma")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "qwen/qwen3.7-flash"

# Sensible starting feeds so a fresh install has news to search without hunting for URLs.
DEFAULT_RSS_FEED_URLS = [
    "https://www.cbssports.com/rss/headlines/nfl/",
    "https://www.espn.com/espn/rss/nfl/news",
    "https://profootballtalk.nbcsports.com/feed/",
    "https://www.rotowire.com/rss/news.php?sport=NFL",
]

# User-settable keys. ESPN_SWID/ESPN_S2 are only needed for private leagues;
# ESPN_TEAM_ID identifies "your" team when there are no cookies to match against.
SETTING_KEYS = (
    "ESPN_LEAGUE_ID",
    "ESPN_SEASON",
    "ESPN_SWID",
    "ESPN_S2",
    "ESPN_TEAM_ID",
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "RSS_FEED_URLS",
)

SECRET_KEYS = ("ESPN_SWID", "ESPN_S2", "OPENROUTER_API_KEY")

_cache: dict = {"mtime": None, "data": {}}


def _load_settings() -> dict:
    """Read settings.json, re-reading only when the file changes on disk."""
    try:
        mtime = os.path.getmtime(SETTINGS_PATH)
    except OSError:
        _cache["mtime"], _cache["data"] = None, {}
        return {}

    if _cache["mtime"] != mtime:
        try:
            with open(SETTINGS_PATH) as f:
                loaded = json.load(f)
            _cache["data"] = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            _cache["data"] = {}
        _cache["mtime"] = mtime
    return _cache["data"]


def save_settings(values: dict) -> None:
    """Merge `values` into settings.json. Keys mapped to None are left untouched,
    so the UI can omit secrets it never received rather than blanking them."""
    merged = dict(_load_settings())
    for key, value in values.items():
        if key in SETTING_KEYS and value is not None:
            merged[key] = value

    os.makedirs(DATA_DIR, exist_ok=True)
    tmp_path = f"{SETTINGS_PATH}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(merged, f, indent=2)
    os.replace(tmp_path, SETTINGS_PATH)  # atomic, so a crash can't truncate settings
    _cache["mtime"] = None


def is_configured() -> bool:
    """True once there's enough to sync a league (a public league needs no cookies)."""
    return bool(_resolve("ESPN_LEAGUE_ID") and _resolve("ESPN_SEASON"))


def settings_summary() -> dict:
    """Settings safe to hand to the browser — secrets reported as set/unset only."""
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
    stored = _load_settings().get(name)

    if name == "RSS_FEED_URLS":
        if isinstance(stored, list) and any(str(u).strip() for u in stored):
            return [str(u).strip() for u in stored if str(u).strip()]
        from_env = [u.strip() for u in os.getenv("RSS_FEED_URLS", "").split(",") if u.strip()]
        return from_env or list(DEFAULT_RSS_FEED_URLS)

    if stored not in (None, ""):
        return str(stored)

    from_env = os.getenv(name)
    if from_env:
        return from_env

    return DEFAULT_OPENROUTER_MODEL if name == "OPENROUTER_MODEL" else None


def __getattr__(name: str):
    """Resolve user-settable keys on access (PEP 562) so saves apply without a restart."""
    if name in SETTING_KEYS:
        return _resolve(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
