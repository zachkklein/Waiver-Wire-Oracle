# Player stats endpoint — thin wrapper over tools/query_stats.py.
from fastapi import APIRouter

from tools import query_stats

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
def get_stats(
    player_name: str | None = None,
    position: str | None = None,
    team: str | None = None,
    season: int | None = None,
    week_min: int | None = None,
    week_max: int | None = None,
    season_type: str | None = None,
    aggregate: bool = False,
    sort_by: str = "fantasy_points_ppr",
    limit: int = 25,
):
    return query_stats.query_stats(
        player_name=player_name,
        position=position,
        team=team,
        season=season,
        week_min=week_min,
        week_max=week_max,
        season_type=season_type,
        aggregate=aggregate,
        sort_by=sort_by,
        limit=limit,
    )
