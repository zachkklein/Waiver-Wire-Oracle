# Proxies ESPN team logos through the app, with an on-disk cache.
#
# Two kinds of URL show up in teams.logo_url: ESPN's stock logo packs on g.espncdn.com
# (public), and members' own uploads on mystique-api.fantasy.espn.com, which 401 without
# the league's espn_s2/SWID cookies. The browser has neither and shouldn't be handed
# them, so every logo is fetched here instead and cached under data/logos/.
import hashlib
import os
import sqlite3
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, HTTPException, Response

import config
from api.deps import LeagueDep
from context import LeagueCtx

router = APIRouter(prefix="/api", tags=["league"])

LOGO_DIR = os.path.join(config.DATA_DIR, "logos")

# logo_url comes from ESPN's own API rather than user input, but the proxy will only
# ever fetch from ESPN regardless.
ALLOWED_HOSTS = (".espn.com", ".espncdn.com")

EXTENSIONS = {
    "image/svg+xml": ".svg",
    "image/png": ".png",
    "image/jpg": ".jpg",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}
CONTENT_TYPES = {ext: ct for ct, ext in EXTENSIONS.items()}

# Logos change only when a team owner uploads a new one, and the cache key includes the
# URL, so a long browser TTL is safe.
CACHE_CONTROL = "public, max-age=86400"


def _allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h.lstrip(".") or host.endswith(h) for h in ALLOWED_HOSTS)


def _lookup_logo_url(league_id: str, team_id: int) -> str | None:
    if not os.path.exists(config.DB_PATH):
        return None
    conn = sqlite3.connect(config.DB_PATH)
    try:
        row = conn.execute(
            "SELECT logo_url FROM teams WHERE league_id = ? AND team_id = ?",
            (league_id, team_id),
        ).fetchone()
    except sqlite3.OperationalError:
        return None  # teams table not created yet
    finally:
        conn.close()
    return row[0] if row and row[0] else None


def _cached_path(league_id: str, team_id: int, url: str) -> str | None:
    """The URL's digest is part of the filename, so re-uploading a logo misses the
    cache instead of serving the old image forever."""
    digest = hashlib.sha256(url.encode()).hexdigest()[:12]
    prefix = f"{league_id}-{team_id}-{digest}"
    if not os.path.isdir(LOGO_DIR):
        return None
    for name in os.listdir(LOGO_DIR):
        if name.startswith(prefix):
            return os.path.join(LOGO_DIR, name)
    return None


def _fetch(url: str, league: LeagueCtx) -> tuple[bytes, str]:
    # Only ESPN's own API needs the cookies; the CDN doesn't, so don't hand them over.
    host = (urlparse(url).hostname or "").lower()
    cookies = league.espn_cookies if host.endswith(".espn.com") else {}

    res = requests.get(url, cookies=cookies, timeout=15)
    res.raise_for_status()

    content_type = res.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in EXTENSIONS:
        raise HTTPException(502, f"ESPN returned a non-image logo ({content_type or 'unknown'}).")
    return res.content, content_type


@router.get("/team-logo/{team_id}")
def get_team_logo(team_id: int, league: LeagueDep):
    league_id = league.key
    url = _lookup_logo_url(league_id, team_id)
    if not url:
        raise HTTPException(404, "No logo synced for this team.")
    if not _allowed(url):
        raise HTTPException(502, "Refusing to proxy a logo from a non-ESPN host.")

    cached = _cached_path(league_id, team_id, url)
    if cached:
        with open(cached, "rb") as f:
            body = f.read()
        media_type = CONTENT_TYPES.get(os.path.splitext(cached)[1], "application/octet-stream")
        return Response(body, media_type=media_type, headers={"Cache-Control": CACHE_CONTROL})

    try:
        body, content_type = _fetch(url, league)
    except HTTPException:
        raise
    except requests.RequestException as exc:
        raise HTTPException(502, f"Could not fetch logo from ESPN: {exc}") from exc

    os.makedirs(LOGO_DIR, exist_ok=True)
    digest = hashlib.sha256(url.encode()).hexdigest()[:12]
    path = os.path.join(LOGO_DIR, f"{league_id}-{team_id}-{digest}{EXTENSIONS[content_type]}")
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, path)

    return Response(body, media_type=content_type, headers={"Cache-Control": CACHE_CONTROL})
