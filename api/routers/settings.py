# Setup endpoints: read/write app settings, validate an ESPN league, and run ingests.
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

import config

router = APIRouter(prefix="/api", tags=["settings"])


class SettingsPayload(BaseModel):
    # Secrets are optional: the UI omits them when unchanged rather than sending back
    # the masked placeholder, and save_settings() leaves omitted keys alone.
    ESPN_LEAGUE_ID: str | None = None
    ESPN_SEASON: str | None = None
    ESPN_SWID: str | None = None
    ESPN_S2: str | None = None
    ESPN_TEAM_ID: str | None = None
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str | None = None
    RSS_FEED_URLS: list[str] | None = None


class LeaguePreviewRequest(BaseModel):
    ESPN_LEAGUE_ID: str
    ESPN_SEASON: str
    ESPN_SWID: str | None = None
    ESPN_S2: str | None = None


@router.get("/settings")
def get_settings():
    return config.settings_summary()


@router.put("/settings")
def put_settings(payload: SettingsPayload):
    config.save_settings(payload.model_dump(exclude_none=True))
    return config.settings_summary()


@router.post("/settings/league-preview")
def league_preview(req: LeaguePreviewRequest):
    """Connect to ESPN with the supplied details and list the league's teams, so the
    user can confirm the league loaded and choose which team is theirs."""
    from espn_api.football import League

    try:
        league = League(
            league_id=int(req.ESPN_LEAGUE_ID),
            year=int(req.ESPN_SEASON),
            espn_s2=req.ESPN_S2 or config.ESPN_S2,
            swid=req.ESPN_SWID or config.ESPN_SWID,
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


_sync_state: dict = {"running": False, "results": {}, "started_at": None, "finished_at": None}
_sync_lock = threading.Lock()

SYNC_TARGETS = ("espn", "stats", "news")


class SyncRequest(BaseModel):
    targets: list[str] | None = None


def _run_sync(targets: list[str]) -> None:
    # Imported lazily — stats pulls in nfl-data-py/pandas, which is slow to import
    # and shouldn't delay API startup.
    from ingest import espn_sync, news_sync, stats_sync

    results: dict = {}
    for target in targets:
        try:
            if target == "espn":
                league, self_team_id = espn_sync.run()
                results[target] = {
                    "ok": True,
                    "detail": f"{len(league.teams)} teams, matchups through week {league.current_week}",
                    "self_team_found": self_team_id is not None,
                }
            elif target == "stats":
                count = stats_sync.run(None)
                results[target] = {"ok": True, "detail": f"{count} player-week stat lines"}
            elif target == "news":
                count = news_sync.run(None)
                results[target] = {"ok": True, "detail": f"{count} news chunks"}
        except Exception as exc:
            results[target] = {"ok": False, "detail": str(exc)}

        with _sync_lock:
            _sync_state["results"] = dict(results)

    with _sync_lock:
        _sync_state["running"] = False
        _sync_state["finished_at"] = datetime.now(timezone.utc).isoformat()


@router.post("/sync")
def start_sync(req: SyncRequest, background: BackgroundTasks):
    targets = req.targets or list(SYNC_TARGETS)
    invalid = [t for t in targets if t not in SYNC_TARGETS]
    if invalid:
        raise HTTPException(400, f"Unknown sync target(s): {', '.join(invalid)}")

    with _sync_lock:
        if _sync_state["running"]:
            raise HTTPException(409, "A sync is already running.")
        _sync_state.update(
            running=True,
            results={},
            started_at=datetime.now(timezone.utc).isoformat(),
            finished_at=None,
        )

    background.add_task(_run_sync, targets)
    return {"running": True, "targets": targets}


@router.get("/sync")
def sync_status():
    with _sync_lock:
        return dict(_sync_state)
