# Waiver Wire Oracle

A personal fantasy football assistant that combines your ESPN league data, NFL player stats, and current NFL news into a chat agent you can ask roster, start/sit, and waiver-wire questions.

It runs entirely locally — a Python backend backed by SQLite and a local vector store, with an LLM agent that answers questions by calling tools rather than guessing from training data. You can use it as a terminal chat agent or through a local web app (FastAPI + React) that adds a dashboard for your roster, matchups, standings, player stats, and news alongside the same chat agent, streamed and rendered as markdown.

It's built to be **self-hosted**: clone it, run it, and point it at your own league from a setup screen in the browser — no config files to edit, and your ESPN credentials never leave your machine.

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

api/*.py       ──▶  FastAPI wrappers around the tools + a streaming version of the chat loop
frontend/src   ──▶  React web app (dashboard + chat) that talks to api/*.py over HTTP
```

- **`ingest/espn_sync.py`** — pulls your league via [`espn-api`](https://github.com/cwendt94/espn-api): every team's roster, league standings, and the current week's matchups/box scores.
- **`ingest/stats_sync.py`** — pulls weekly NFL player stats (yardage, TDs, targets, fantasy points) via [`nfl-data-py`](https://github.com/nflverse/nfl_data_py).
- **`ingest/news_sync.py`** — pulls NFL news from RSS feeds, chunks it, and embeds it into a local [Chroma](https://www.trychroma.com/) vector store using Chroma's bundled local embedding model (no external embedding API needed). This is the RAG component: `search_news` retrieves relevant article snippets by semantic similarity, and the agent uses them as grounded context instead of relying on its own (possibly stale) knowledge.
- **`agent/chat.py`** — a terminal chat loop. On each turn, the LLM decides whether it needs to call `query_stats`, `query_roster`, or `search_news`, executes the call, and reasons over the result before responding.
- **`api/`** — a FastAPI app exposing the same tools as a JSON API (`/api/roster`, `/api/stats`, `/api/matchups`, `/api/teams`, `/api/news`, `/api/meta`), a streaming `/api/chat` endpoint that reuses `agent/chat.py`'s system prompt and tools, and `/api/settings` + `/api/sync` behind the Setup page.
- **`frontend/`** — a React + Vite + TypeScript app: a dashboard (your team, matchup, standings), roster/matchup/standings/player/news pages, an "Oracle" chat page that streams the agent's responses and renders them as markdown, and a Setup page for connecting your league and running syncs.

All three ingest scripts are safe to re-run — they upsert rather than duplicate, so you can re-sync as often as you like (e.g. weekly, or before each waiver decision).

## Getting started

This is designed to be self-hosted: you run your own copy against your own league, and nothing leaves your machine except calls to ESPN, nflverse, your RSS feeds, and your chosen LLM provider.

### Prerequisites

- Python 3.11 (nfl-data-py's pandas dependency has no prebuilt wheel for 3.13 — use 3.11)
- Node 18+ (for the web app)
- An ESPN fantasy football league — public leagues need nothing but the league ID
- An [OpenRouter](https://openrouter.ai) API key, if you want the Oracle chat page

### Install and run

```bash
git clone <your-fork-url> waiver-wire-oracle
cd waiver-wire-oracle

python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && npm run build && cd ..
python3 main.py serve
```

Open `http://localhost:8000`. On a fresh install you'll land on the **Setup** page — enter your league there and click through. No config files to edit.

### Setup page

| Field | Needed? | Where it comes from |
|---|---|---|
| League ID | Always | Your league URL: `fantasy.espn.com/football/team?leagueId=XXXXXXX` |
| Season | Always | The year you want to load, e.g. `2026` |
| SWID / espn_s2 | **Private leagues only** | DevTools → Application → Cookies → `fantasy.espn.com`, while signed in |
| Your team | Public leagues | Pick from the list after clicking **Connect league** |
| OpenRouter key | For the Oracle only | [openrouter.ai](https://openrouter.ai) → Keys |
| News feeds | Optional | Four NFL feeds are preconfigured; edit the list to taste |

**Public leagues need no cookies at all.** Enter the league ID and season, hit *Connect league*, and choose which team is yours. Private leagues need the two cookies so ESPN will return the league — those are stored locally in `data/settings.json` (gitignored) and are only ever sent to ESPN.

Then hit **Sync everything** on the same page to pull in your league, player stats, and news. Player stats and news take a minute on the first run.

### Configuring without the UI

Every setting also reads from environment variables / `.env`, which is handy for headless or container setups — copy `.env.example` to `.env` and fill in `ESPN_LEAGUE_ID`, `ESPN_SEASON`, `ESPN_SWID`, `ESPN_S2`, `ESPN_TEAM_ID`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `RSS_FEED_URLS` (comma-separated). Anything saved from the Setup page takes precedence over `.env`. Set `DATA_DIR` to move the SQLite file, Chroma store, and settings somewhere else (e.g. a mounted volume).

### Refreshing your data

Re-sync whenever you want fresher data — weekly, or before each waiver decision. Either hit **Sync everything** on the Setup page, or use the CLI:

```bash
# Sync all three sources (re-run any time)
python3 main.py sync

# Chat with the agent in the terminal instead of the browser
python3 main.py chat
```

#### Web app

```bash
# Terminal 1: the API
python3 main.py serve --reload

# Terminal 2: the frontend (first time: cd frontend && npm install)
cd frontend && npm run dev
```

Then open `http://localhost:5173`. The Vite dev server proxies `/api/*` to the FastAPI app on port 8000. For a single-process production build:

```bash
cd frontend && npm run build   # writes frontend/dist
cd .. && python3 main.py serve --port 8000   # now also serves the built frontend
```

`main.py sync` runs all three ingest sources and keeps going even if one fails (e.g. stats syncing has nothing to pull before the season starts) — it reports per-source success/failure and exits non-zero only if something actually failed. Sync a subset instead with `python3 main.py sync espn stats`, pass explicit stats years with `--years 2024 2025`, or override the RSS feeds for one run with `--feeds <url> <url>`.

Each ingest/agent script is also runnable directly if you want to bypass `main.py` (e.g. for debugging one source in isolation):

```bash
python3 ingest/espn_sync.py
python3 ingest/stats_sync.py
python3 ingest/news_sync.py
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

`agent/chat.py` talks to [OpenRouter](https://openrouter.ai)'s OpenAI-compatible Chat Completions API, so you can point it at nearly any model OpenRouter offers, including free/cheap ones — change the model on the Setup page (or `OPENROUTER_MODEL` in `.env`). The default, `qwen/qwen3.7-flash`, is inexpensive and supports tool calling well. Pick a model that supports tool calling; the agent relies on it for every answer.

## Project structure

```
waiver-wire-oracle/
├── .env                  # optional config for headless setups (gitignored)
├── config.py              # resolves settings: settings.json -> .env -> defaults
├── data/                  # all gitignored
│   ├── settings.json       # written by the Setup page (league ID, cookies, API key)
│   ├── db.sqlite           # teams, rosters, matchups, player_stats
│   └── chroma/              # embedded news vector store
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
├── api/
│   ├── main.py                # FastAPI app (mounts routers + serves frontend/dist in prod)
│   ├── chat_service.py         # streaming version of agent/chat.py's tool loop
│   └── routers/                # league, stats, news, meta, chat, settings
├── frontend/
│   ├── src/pages/               # Dashboard, Roster, Matchups, Standings, Players, News, Chat, Setup
│   ├── src/components/          # shared UI (badges, cards, chat bubbles, markdown rendering)
│   └── src/lib/                 # api.ts (fetch wrappers), types.ts
└── main.py                   # CLI entrypoint (sync, chat, serve subcommands)
```

Each `tools/*.py` file also works as a standalone CLI for testing — run any of them with `--help` (or `-h`) to see its arguments. Same for `main.py` (`python3 main.py --help`, `python3 main.py sync --help`).

## Status

This is an active personal project, built to be cloned and self-hosted. Currently implemented: ESPN/stats/news ingestion, SQL and vector-search query tools, a terminal chat agent, a unified `main.py` CLI, a local web app (FastAPI + React) covering the dashboard, roster, matchups, standings, players, news, and a streaming chat page, and an in-app Setup page so a fresh clone can be configured entirely from the browser.

Not built, by design: there's **no authentication and no multi-user support** — it assumes one person running one copy against one league, and anyone who can reach the URL gets full access to your league data and can spend your OpenRouter credits. Don't expose it to the open internet without putting something in front of it (a private network like Tailscale, or an identity proxy like Cloudflare Access).

Worth knowing: ESPN publishes no official fantasy API. `espn-api` works against undocumented internal endpoints, so ESPN can change or block them without notice, and there's no "Sign in with ESPN" to integrate — private leagues require copying two cookies by hand.
