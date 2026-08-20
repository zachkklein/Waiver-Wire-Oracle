# League data endpoints: standings, roster, matchups — thin wrappers over tools/query_roster.py.
from fastapi import APIRouter

from api.deps import LeagueDep
from tools import query_roster

router = APIRouter(prefix="/api", tags=["league"])


@router.get("/teams")
def get_teams(league: LeagueDep):
    return query_roster.query_roster(league, view="teams", include_logos=True)


@router.get("/roster")
def get_roster(league: LeagueDep, team: str | None = None):
    return query_roster.query_roster(league, view="roster", team=team, include_logos=True)


@router.get("/matchups")
def get_matchups(league: LeagueDep, week: int | None = None, team: str | None = None):
    return query_roster.query_roster(
        league, view="matchup", team=team, week=week, include_logos=True
    )
