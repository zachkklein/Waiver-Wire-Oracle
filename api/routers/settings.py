# Setup endpoints: read/write the caller's settings, validate an ESPN league, and run
# ingests. Where those settings live — data/settings.json or the caller's user_leagues
# row — is store.py's business, not this router's.
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

import auth
import store
from api.deps import LeagueDep, PrincipalDep
from auth import Principal
from context import LeagueCtx

router = APIRouter(prefix="/api", tags=["settings"])


class SettingsPayload(BaseModel):
    # Secrets are optional: the UI omits them when unchanged rather than sending back
    # the masked placeholder, and the store leaves omitted keys alone.
    ESPN_LEAGUE_ID: str | None = None
    ESPN_SEASON: str | None = None
    ESPN_SWID: str | None = None
    ESPN_S2: str | None = None
    ESPN_TEAM_ID: str | None = None
    label: str | None = None
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str | None = None
    RSS_FEED_URLS: list[str] | None = None


class LeaguePreviewRequest(BaseModel):
    ESPN_LEAGUE_ID: str
    ESPN_SEASON: str
    ESPN_SWID: str | None = None
    ESPN_S2: str | None = None


@router.get("/settings")
def get_settings(principal: PrincipalDep):
    return store.settings_summary(principal)


@router.put("/settings")
def put_settings(payload: SettingsPayload, principal: PrincipalDep):
    try:
        store.save_settings(principal, payload.model_dump(exclude_none=True))
    except store.StoreError as exc:
        raise HTTPException(400, str(exc))
    return store.settings_summary(principal)


@router.post("/settings/league-preview")
def league_preview(req: LeaguePreviewRequest, current: LeagueDep):
    """Connect to ESPN with the supplied details and list the league's teams, so the
    user can confirm the league loaded and choose which team is theirs.

    Cookies fall back to the caller's current league's when the form omits them — the UI
    leaves the secret fields blank unless they're retyped."""
    from espn_api.football import League

    try:
        league = League(
            league_id=int(req.ESPN_LEAGUE_ID),
            year=int(req.ESPN_SEASON),
            espn_s2=req.ESPN_S2 or current.s2,
            swid=req.ESPN_SWID or current.swid,
        )
    except ValueError:
        raise HTTPException(400, "League ID and season must be numbers.")
    except Exception as exc:
        raise HTTPException(
            400,
            "Could not load that league. Check the league ID and season — and if the "
            f"league is private, that the SWID and espn_s2 cookies are current. ({exc})",
        )

    return {
        "league_name": getattr(league.settings, "name", None),
        "current_week": league.current_week,
        "teams": [
            {"team_id": t.team_id, "team_name": t.team_name} for t in league.teams
        ],
    }


# Sync progress, keyed by league rather than held in one process-global dict. With
# accounts, two people can be syncing different leagues at once and neither should see
# the other's progress or be turned away by it. It's still in-process and still
# BackgroundTasks — Phase 5 replaces the whole thing with a worker holding a per-league
# lock so that twelve members of one league trigger one sync, not twelve.
_sync_states: dict[str, dict] = {}
_sync_lock = threading.Lock()

SYNC_TARGETS = ("espn", "stats", "news")

# nflverse stats and the news vector store are global data shared by every league, so a
# signed-in user re-ingesting them isn't "their" sync at all — it's an expensive job
# aimed at everyone's data. On the hosted build the operator runs those; only the
# per-league ESPN pull is user-triggerable.
SHARED_TARGETS = ("stats", "news")


def _idle_state() -> dict:
    return {"running": False, "results": {}, "started_at": None, "finished_at": None}


def _state_for(league_key: str) -> dict:
    return _sync_states.setdefault(league_key, _idle_state())


def _run_sync(league_key: str, targets: list, ctx: LeagueCtx, principal: Principal) -> None:
    # Imported lazily — stats pulls in nfl-data-py/pandas, which is slow to import
    # and shouldn't delay API startup.
    from ingest import espn_sync, news_sync, stats_sync

    results: dict = {}
    for target in targets:
        try:
            if target == "espn":
                league, self_team_id = espn_sync.run(ctx, principal)
                results[target] = {
                    "ok": True,
                    "detail": f"{len(league.teams)} teams, matchups through week {league.current_week}",
                    "self_team_found": self_team_id is not None,
                }
            elif target == "stats":
                # Pass the season explicitly: there is no ambient "active league" for
                # stats_sync to fall back to once requests carry their own.
                count = stats_sync.run(None, default_season=ctx.season)
                results[target] = {"ok": True, "detail": f"{count} player-week stat lines"}
            elif target == "news":
                count = news_sync.run(None)
                results[target] = {"ok": True, "detail": f"{count} news chunks"}
        except Exception as exc:
            results[target] = {"ok": False, "detail": str(exc)}

        with _sync_lock:
            _state_for(league_key)["results"] = dict(results)

    with _sync_lock:
        state = _state_for(league_key)
        state["running"] = False
        state["finished_at"] = datetime.now(timezone.utc).isoformat()


class SyncRequest(BaseModel):
    targets: list[str] | None = None


@router.post("/sync")
def start_sync(
    req: SyncRequest, background: BackgroundTasks, principal: PrincipalDep, league: LeagueDep
):
    allowed = ("espn",) if auth.is_enabled() else SYNC_TARGETS
    targets = req.targets or list(allowed)

    invalid = [t for t in targets if t not in SYNC_TARGETS]
    if invalid:
        raise HTTPException(400, f"Unknown sync target(s): {', '.join(invalid)}")
    shared = [t for t in targets if t not in allowed]
    if shared:
        raise HTTPException(
            403,
            f"{', '.join(shared)} is shared data that the server keeps up to date for "
            "every league, so it can't be synced from here.",
        )

    if not league.is_configured:
        raise HTTPException(400, "Connect a league before syncing.")

    with _sync_lock:
        state = _state_for(league.key)
        if state["running"]:
            raise HTTPException(409, "A sync is already running for this league.")
        state.update(
            running=True,
            results={},
            started_at=datetime.now(timezone.utc).isoformat(),
            finished_at=None,
        )

    background.add_task(_run_sync, league.key, targets, league, principal)
    return {"running": True, "targets": targets}


@router.get("/sync")
def sync_status(league: LeagueDep):
    with _sync_lock:
        return dict(_state_for(league.key) if league.league_id else _idle_state())
