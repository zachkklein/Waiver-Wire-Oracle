# League management: list configured leagues, add another one, switch which one is
# active, or remove one. Editing the *active* league's own fields still goes through
# PUT /api/settings (api/routers/settings.py) — this router only adds/switches/removes.
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config

router = APIRouter(prefix="/api", tags=["leagues"])


class NewLeaguePayload(BaseModel):
    ESPN_LEAGUE_ID: str
    ESPN_SEASON: str
    label: str | None = None
    ESPN_SWID: str | None = None
    ESPN_S2: str | None = None
    ESPN_TEAM_ID: str | None = None


@router.get("/leagues")
def list_leagues():
    return config.list_leagues()


@router.post("/leagues")
def create_league(payload: NewLeaguePayload):
    try:
        config.add_league(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return config.list_leagues()


@router.put("/leagues/{league_id}/activate")
def activate_league(league_id: str):
    try:
        config.set_active_league(league_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return config.list_leagues()


@router.delete("/leagues/{league_id}")
def remove_league(league_id: str):
    try:
        config.delete_league(league_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return config.list_leagues()
