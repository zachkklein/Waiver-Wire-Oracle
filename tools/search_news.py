# Vector search tool over ingested NFL news, exposed as an LLM tool-calling function.
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from context import LeagueCtx  # noqa: F401  (used in a type hint)
from ingest.news_sync import get_collection

TOOL_SCHEMA = {
    "name": "search_news",
    "description": (
        "Semantically search recent NFL news synced from RSS feeds (ESPN, CBS Sports, "
        "Pro Football Talk, RotoWire, Yahoo, etc.) for injury updates, roster moves, "
        "beat-reporter buzz, and other player/team news relevant to fantasy decisions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Natural-language search query, e.g. 'Christian McCaffrey injury status' "
                    "or 'rookie wide receivers breaking out'."
                ),
            },
            "n_results": {
                "type": "integer",
                "description": "Number of results to return. Default 5, capped at 20.",
            },
            "source": {
                "type": "string",
                "description": (
                    "Optional exact source/feed name to restrict results to, e.g. "
                    "'RotoWire.com Latest NFL News'."
                ),
            },
            "since_days": {
                "type": "integer",
                "description": "Optional: only include articles published within the last N days.",
            },
        },
        "required": ["query"],
    },
}


def search_news(
    query: str,
    n_results: int = 5,
    source: str | None = None,
    since_days: int | None = None,
) -> list[dict]:
    n_results = max(1, min(int(n_results or 5), 20))

    conditions = []
    if source:
        conditions.append({"source": source})
    if since_days is not None:
        cutoff_ts = int(time.time()) - int(since_days) * 86400
        conditions.append({"published_ts": {"$gte": cutoff_ts}})

    where = None
    if len(conditions) == 1:
        where = conditions[0]
    elif len(conditions) > 1:
        where = {"$and": conditions}

    collection = get_collection()
    if collection.count() == 0:
        return []

    result = collection.query(query_texts=[query], n_results=n_results, where=where)

    hits = []
    for doc, meta, dist in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        hits.append(
            {
                "title": meta.get("title"),
                "source": meta.get("source"),
                "link": meta.get("link"),
                "published": meta.get("published"),
                "snippet": doc,
                "distance": round(dist, 4),
            }
        )
    return hits


def run_tool(tool_input: dict, league: "LeagueCtx | None" = None) -> list[dict]:
    # `league` is accepted for a uniform tool interface and ignored: this data is
    # nflverse/RSS, not tied to any one ESPN league.
    return search_news(**tool_input)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Semantic search over synced NFL news.")
    parser.add_argument("query")
    parser.add_argument("--n-results", type=int, default=5)
    parser.add_argument("--source")
    parser.add_argument("--since-days", type=int)
    args = parser.parse_args()

    results = search_news(
        query=args.query,
        n_results=args.n_results,
        source=args.source,
        since_days=args.since_days,
    )
    print(json.dumps(results, indent=2))
