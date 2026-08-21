# League management: list the caller's leagues, add another one, switch which one is
# active, or remove one. Editing the *active* league's own fields still goes through
# PUT /api/settings (api/routers/settings.py) — this router only adds/switches/removes.
#
# "The caller's" is doing real work here: on a self-hosted install that's the one league
# list in data/settings.json, and on the hosted build it's this account's user_leagues
# rows. store.py picks; nothing in this file needs to know which.
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import store
from api.deps import PrincipalDep

router = APIRouter(prefix="/api", tags=["leagues"])


class NewLeaguePayload(BaseModel):
    ESPN_LEAGUE_ID: str
    ESPN_SEASON: str
    label: str | None = None
    ESPN_SWID: str | None = None
    ESPN_S2: str | None = None
    ESPN_TEAM_ID: str | None = None


@router.get("/leagues")
def list_leagues(principal: PrincipalDep):
    return store.list_leagues(principal)


@router.post("/leagues")
def create_league(payload: NewLeaguePayload, principal: PrincipalDep):
    try:
        store.add_league(principal, payload.model_dump(exclude_none=True))
    except store.StoreError as exc:
        raise HTTPException(400, str(exc))
    return store.list_leagues(principal)


@router.put("/leagues/{league_id}/activate")
def activate_league(league_id: str, principal: PrincipalDep):
    try:
        store.set_active_league(principal, league_id)
    except store.StoreError as exc:
        raise HTTPException(404, str(exc))
    return store.list_leagues(principal)


@router.delete("/leagues/{league_id}")
def remove_league(league_id: str, principal: PrincipalDep):
    try:
        store.delete_league(principal, league_id)
    except store.StoreError as exc:
        raise HTTPException(404, str(exc))
    return store.list_leagues(principal)
