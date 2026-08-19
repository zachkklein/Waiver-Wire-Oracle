# News search endpoint — thin wrapper over tools/search_news.py.
from fastapi import APIRouter

from tools import search_news

router = APIRouter(prefix="/api", tags=["news"])


@router.get("/news")
def get_news(
    query: str,
    n_results: int = 5,
    source: str | None = None,
    since_days: int | None = None,
):
    return search_news.search_news(
        query=query,
        n_results=n_results,
        source=source,
        since_days=since_days,
    )
