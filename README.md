# Waiver Wire Oracle

A personal fantasy football assistant that combines your ESPN league data, NFL player stats, and current NFL news into a chat agent you can ask roster, start/sit, and waiver-wire questions.

It runs entirely locally — a Python backend backed by SQLite (or Postgres, if you point it at one) and a local vector store, with an LLM agent that answers questions by calling tools rather than guessing from training data. You can use it as a terminal chat agent or through a local web app (FastAPI + React) that adds a dashboard for your roster, matchups, standings, player stats, and news alongside the same chat agent, streamed and rendered as markdown.

It's built to be **self-hosted**: clone it, run it, and point it at your own league from a setup screen in the browser — no config files to edit, and your ESPN credentials never leave your machine. You can add more than one ESPN league and switch between them from a dropdown in the app; the Oracle's OpenRouter key and news feeds are shared across all of them.

## How it works

Three ingest scripts pull data from external sources into local storage. Three tool modules read that storage and expose it to an LLM. An agent loop ties the tools together with a chat interface.

```
espn_sync.py   ──┐
stats_sync.py  ──┼──▶  data/db.sqlite  (leagues, teams, rosters, matchups, players, player_stats)
                 │
news_sync.py   ──┴──▶  data/chroma/   (embedded NFL news, for semantic search)

query_roster.py, query_stats.py  ──▶  read data/db.sqlite
search_news.py                   ──▶  semantic search over data/chroma/ (RAG)

agent/chat.py  ──▶  LLM chat loop that calls the three tools above on demand

api/*.py       ──▶  FastAPI wrappers around the tools + a streaming version of the chat loop
frontend/src   ──▶  React web app (dashboard + chat) that talks to api/*.py over HTTP
```

- **`ingest/espn_sync.py`** — pulls your league via [`espn-api`](https://github.com/cwendt94/espn-api): every team's roster, league standings, and the current week's matchups/box scores.
- **`ingest/stats_sync.py`** — pulls weekly NFL player stats (yardage, TDs, targets, fantasy points) via [`nfl-data-py`](https://github.com/nflverse/nfl_data_py), then links them to ESPN's players. ESPN and nflverse use different player ids *and* spell names differently ("Aaron Jones Sr." vs "Aaron Jones", "DJ Moore" vs "D.J. Moore"), so a `players` table holds both ids and `stats_sync` resolves the link once at ingest — which is what makes "how are the players on my roster actually performing?" a single SQL join.
- **`ingest/news_sync.py`** — pulls NFL news from RSS feeds, chunks it, and embeds it into a local [Chroma](https://www.trychroma.com/) vector store using Chroma's bundled local embedding model (no external embedding API needed). This is the RAG component: `search_news` retrieves relevant article snippets by semantic similarity, and the agent uses them as grounded context instead of relying on its own (possibly stale) knowledge.
- **`agent/chat.py`** — a terminal chat loop. On each turn, the LLM decides whether it needs to call `query_stats`, `query_roster`, or `search_news`, executes the call, and reasons over the result before responding.
- **`api/`** — a FastAPI app exposing the same tools as a JSON API (`/api/roster`, `/api/stats`, `/api/matchups`, `/api/teams`, `/api/news`, `/api/meta`), a streaming `/api/chat` endpoint that reuses `agent/chat.py`'s system prompt and tools, `/api/settings` + `/api/sync` behind the Setup page, and `/api/leagues` for adding/switching/removing leagues.
- **`frontend/`** — a React + Vite + TypeScript app: a dashboard (your team, matchup, standings), roster/matchup/standings/player/news pages, an "Oracle" chat page that streams the agent's responses and renders them as markdown, a Setup page for connecting your league and running syncs, and a league switcher dropdown in the top bar for multi-league setups.

All three ingest scripts are safe to re-run — they upsert rather than duplicate, so you can re-sync as often as you like (e.g. weekly, or before each waiver decision). A re-sync that finds nothing changed writes nothing at all: the upserts are guarded so unchanged rows are skipped entirely.

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

### Multiple leagues

You can connect more than one ESPN league to the same install. Use the league switcher dropdown in the top bar (shows your current league's name) → **+ Add another league**, fill in that league's ID/season/cookies/team, and it becomes the active league. Switching leagues from the dropdown re-scopes the whole app (roster, matchups, standings, Oracle) to that league's synced data — each league needs its own sync (Setup page → Sync everything) the first time you add it.

Your OpenRouter API key/model and RSS news feeds are **shared** across every league — set those once from the Setup page while any league is active.

### Configuring without the UI

Every setting also reads from environment variables / `.env`, which is handy for headless or container setups — copy `.env.example` to `.env` and fill in `ESPN_LEAGUE_ID`, `ESPN_SEASON`, `ESPN_SWID`, `ESPN_S2`, `ESPN_TEAM_ID`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `RSS_FEED_URLS` (comma-separated). Anything saved from the Setup page takes precedence over `.env`. `.env` only configures a single league (there's no `.env` equivalent for a second one — add it from the UI); a second league added from the UI is stored in `data/settings.json` even if your first one is still coming from `.env`. Set `DATA_DIR` to move the SQLite file, Chroma store, and settings somewhere else (e.g. a mounted volume).

### Storage

By default everything lives in one SQLite file (`data/db.sqlite`) plus a local Chroma
store — no external services, which is the point of a clone-and-run install.

Set `DATABASE_URL` to a Postgres connection string and the app uses Postgres instead.
The SQL is written once and translated per backend (`db.py`), so both paths run the same
queries. This is how the hosted deployment points at Supabase; the schema lives in
`supabase/migrations/`, and `scripts/migrate_to_postgres.py` copies an existing SQLite
database across (idempotently — it upserts on primary keys).

Two things worth knowing if you do:

- Expect it to feel slower in local development. Round trips to a cloud region are
  ~100ms against ~1ms for a local file, so the app is much snappier with `DATABASE_URL`
  unset. That gap disappears in a deployment where app and database share a region.
- Use a **pooled** connection string if your provider offers one (Supabase: port 6543).
  The app keeps its own connection pool, but a serverful deployment will still hold more
  connections than a direct endpoint likes.

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
├── config.py              # resolves settings: settings.json -> .env -> defaults,
│                          #   and builds the per-request LeagueCtx/UserCtx
├── context.py             # LeagueCtx / UserCtx — passed explicitly, never module globals
├── auth.py                # who is asking: Supabase JWT, or the single local user
├── store.py               # where their leagues live: settings.json, or user_leagues
├── db.py                  # SQLite or Postgres, chosen by DATABASE_URL
├── names.py               # player-name normalisation (ESPN ↔ nflverse linking)
├── data/                  # all gitignored
│   ├── settings.json       # written by the Setup page (leagues list, active league, API key)
│   ├── db.sqlite           # leagues/teams/rosters/matchups (keyed by league_id), players, player_stats
│   ├── logos/               # cached ESPN team logos
│   └── chroma/              # embedded news vector store
├── supabase/migrations/   # Postgres schema + accounts, for the hosted deployment
├── ingest/
│   ├── espn_sync.py         # ESPN league → database
│   ├── stats_sync.py        # nflverse stats → database (+ links players to ESPN ids)
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
│   ├── deps.py                 # the one seam: request → Principal → LeagueCtx/UserCtx
│   └── routers/                # auth, league, leagues, stats, news, meta, chat, settings
├── frontend/
│   ├── src/pages/               # Dashboard, Roster, Matchups, Standings, Players, News, Chat, Setup
│   ├── src/components/          # shared UI (badges, cards, chat bubbles, markdown rendering)
│   ├── src/auth/                # sign-in screen and gate (only when accounts are on)
│   └── src/lib/                 # api.ts (fetch wrappers), auth.ts, types.ts
├── scripts/
│   └── migrate_to_postgres.py  # copy an existing SQLite database into Postgres
└── main.py                   # CLI entrypoint (sync, chat, serve subcommands)
```

Each `tools/*.py` file also works as a standalone CLI for testing — run any of them with `--help` (or `-h`) to see its arguments. Same for `main.py` (`python3 main.py --help`, `python3 main.py sync --help`).

## Status

This is an active personal project, built to be cloned and self-hosted. Currently implemented: ESPN/stats/news ingestion, SQL and vector-search query tools, a terminal chat agent, a unified `main.py` CLI, a local web app (FastAPI + React) covering the dashboard, roster, matchups, standings, players, news, and a streaming chat page, an in-app Setup page so a fresh clone can be configured entirely from the browser, and support for multiple ESPN leagues (add/switch/remove from a top-bar dropdown) against the same install.

Also runs on Postgres (`DATABASE_URL`), with the schema in `supabase/migrations/`, and now with **optional accounts**: set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` and the app grows a magic-link sign-in screen, with each account's leagues, ESPN cookies and OpenRouter key stored per user. Progress toward a fully hosted version is tracked in `docs/HOSTED_PLAN.md`.

**Leave those unset and nothing changes** — that's the default, and the self-hosted story stays first-class: no sign-in, no external services beyond ESPN, one league at a time from `data/settings.json`. But in that mode there is **no authentication**, so anyone who can reach the URL gets full access to every league you've added and can spend your OpenRouter credits. Don't expose it to the open internet without putting something in front of it (a private network like Tailscale, or an identity proxy like Cloudflare Access) — or turn on accounts.

Still missing for a real hosted deployment: stored ESPN cookies are not yet encrypted at rest, sync is still per-request rather than a shared worker, and there are no rate limits or token metering (Phases 4–6 of the plan).

Worth knowing: ESPN publishes no official fantasy API. `espn-api` works against undocumented internal endpoints, so ESPN can change or block them without notice, and there's no "Sign in with ESPN" to integrate — private leagues require copying two cookies by hand.
