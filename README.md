# Waiver Wire Oracle

A personal fantasy football assistant that combines your ESPN league data, NFL player stats, and current NFL news into a chat agent you can ask roster, start/sit, and waiver-wire questions.

It runs entirely locally today — a Python CLI backed by SQLite and a local vector store, with an LLM agent that answers questions by calling tools rather than guessing from training data. A web front end is planned but not yet started; this README documents the current CLI-based project.

## How it works

Three ingest scripts pull data from external sources into local storage. Three tool modules read that storage and expose it to an LLM. An agent loop ties the tools together with a chat interface.

```
espn_sync.py   ──┐
stats_sync.py  ──┼──▶  data/db.sqlite  (teams, rosters, matchups, player_stats)
                 │
news_sync.py   ──┴──▶  data/chroma/   (embedded NFL news, for semantic search)

query_roster.py, query_stats.py  ──▶  read data/db.sqlite
search_news.py                   ──▶  semantic search over data/chroma/ (RAG)

agent/chat.py  ──▶  LLM chat loop that calls the three tools above on demand
```

- **`ingest/espn_sync.py`** — pulls your league via [`espn-api`](https://github.com/cwendt94/espn-api): every team's roster, league standings, and the current week's matchups/box scores.
- **`ingest/stats_sync.py`** — pulls weekly NFL player stats (yardage, TDs, targets, fantasy points) via [`nfl-data-py`](https://github.com/nflverse/nfl_data_py).
- **`ingest/news_sync.py`** — pulls NFL news from RSS feeds, chunks it, and embeds it into a local [Chroma](https://www.trychroma.com/) vector store using Chroma's bundled local embedding model (no external embedding API needed). This is the RAG component: `search_news` retrieves relevant article snippets by semantic similarity, and the agent uses them as grounded context instead of relying on its own (possibly stale) knowledge.
- **`agent/chat.py`** — a terminal chat loop. On each turn, the LLM decides whether it needs to call `query_stats`, `query_roster`, or `search_news`, executes the call, and reasons over the result before responding.

All three ingest scripts are safe to re-run — they upsert rather than duplicate, so you can re-sync as often as you like (e.g. weekly, or before each waiver decision).

## Getting started

### Prerequisites

- Python 3.11 (nfl-data-py's pandas dependency has no prebuilt wheel for 3.13 — use 3.11)
- An ESPN fantasy football league
- An API key for the LLM provider you want to use (see [Choosing a model](#choosing-a-model))

### Installation

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

Fill in `.env`:

| Variable | Required | Description |
|---|---|---|
| `ESPN_LEAGUE_ID` | Yes | From your league URL: `fantasy.espn.com/football/team?leagueId=XXXXXXX` |
| `ESPN_SEASON` | Yes | League year, e.g. `2026` |
| `ESPN_SWID` | Private leagues only | `SWID` cookie from a logged-in fantasy.espn.com session |
| `ESPN_S2` | Private leagues only | `espn_s2` cookie from the same session |
| `OPENROUTER_API_KEY` | Yes (default setup) | From [openrouter.ai](https://openrouter.ai) → Keys |
| `OPENROUTER_MODEL` | No | Defaults to `qwen/qwen3.7-flash` |
| `RSS_FEED_URLS` | Yes | Comma-separated NFL news RSS feed URLs |

`ESPN_SWID`/`ESPN_S2` are found via your browser's dev tools (Application → Cookies → fantasy.espn.com) while logged into your league.

### Running it

```bash
# Sync your data (re-run any time to refresh)
python3 ingest/espn_sync.py
python3 ingest/stats_sync.py
python3 ingest/news_sync.py

# Chat with the agent
python3 agent/chat.py
```

```
Waiver Wire Oracle — ask about your roster, stats, or news. Type 'exit' to quit.

You: Should I start Kenny Gainwell or Dalton Kincaid this week?
Oracle:   [query_stats({"player_name": "Kenny Gainwell", ...})]
          [query_stats({"player_name": "Dalton Kincaid", ...})]
          [search_news({"query": "Kenny Gainwell Dalton Kincaid", ...})]
...
```

## Choosing a model

`agent/chat.py` talks to [OpenRouter](https://openrouter.ai)'s OpenAI-compatible Chat Completions API, so you can point it at nearly any model OpenRouter offers, including free/cheap ones, by changing `OPENROUTER_MODEL` in `.env`. The default, `qwen/qwen3.7-flash`, is inexpensive and supports tool calling well.

## Project structure

```
waiver-wire-oracle/
├── .env                  # your local config (gitignored)
├── config.py              # loads .env into shared constants (paths, keys, league ID)
├── data/
│   ├── db.sqlite           # teams, rosters, matchups, player_stats (gitignored)
│   └── chroma/              # embedded news vector store (gitignored)
├── ingest/
│   ├── espn_sync.py         # ESPN league → SQLite
│   ├── stats_sync.py        # nflverse stats → SQLite
│   └── news_sync.py         # RSS news → Chroma (RAG ingestion)
├── tools/
│   ├── query_stats.py       # SQL lookup: player stats, weekly or aggregated
│   ├── query_roster.py      # SQL lookup: roster, standings, matchups
│   └── search_news.py       # vector search: NFL news (RAG retrieval)
├── agent/
│   └── chat.py               # tool-calling chat loop
└── main.py                   # CLI entrypoint (not yet implemented)
```

Each `tools/*.py` file also works as a standalone CLI for testing — run any of them with `--help` (or `-h`) to see its arguments.

## Status

This is an active personal project. Currently implemented: ESPN/stats/news ingestion, SQL and vector-search query tools, and a terminal chat agent. Not yet built: `main.py` as a proper CLI entrypoint, and a web front end (planned).
