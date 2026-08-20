# League data endpoints: standings, roster, matchups — thin wrappers over tools/query_roster.py.
from fastapi import APIRouter

from tools import query_roster

router = APIRouter(prefix="/api", tags=["league"])


@router.get("/teams")
def get_teams():
    return query_roster.query_roster(view="teams", include_logos=True)


@router.get("/roster")
def get_roster(team: str | None = None):
    return query_roster.query_roster(view="roster", team=team, include_logos=True)


@router.get("/matchups")
def get_matchups(week: int | None = None, team: str | None = None):
    return query_roster.query_roster(view="matchup", team=team, week=week, include_logos=True)
