# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Waiver Wire Oracle — a personal fantasy football assistant for one ESPN league. It combines ESPN league data, nflverse player stats, and RAG over NFL news RSS feeds, queried by an LLM agent with tool-calling. Everything runs locally against a single SQLite file and a local Chroma vector store. A FastAPI + React web app (`api/`, `frontend/`) sits on top of the same CLI tools/agent for browsing the league and chatting with the Oracle in a browser.

## Commands

```bash
# Setup
python3 -m venv venv          # use Python 3.11 — nfl-data-py's pandas pin has no 3.13 wheel
source venv/bin/activate
pip install -r requirements.txt

# Ingest, via the CLI entrypoint (each source is independently idempotent/re-runnable;
# main.py sync runs every source even if one fails, and reports per-source pass/fail)
python3 main.py sync                            # all three: espn, stats, news
python3 main.py sync espn stats                 # a subset
python3 main.py sync stats --years 2024 2025    # stats defaults to ESPN_SEASON if omitted
python3 main.py sync news --feeds <url> <url>   # news defaults to RSS_FEED_URLS if omitted

# Or run an ingest script directly (bypasses main.py, same effect, no failure isolation)
python3 ingest/espn_sync.py
python3 ingest/stats_sync.py [year ...]
python3 ingest/news_sync.py [feed_url ...]

# Query tools directly (each is also usable as a standalone CLI for debugging)
python3 tools/query_stats.py --player "Josh Allen" --season 2024 --week-min 14 --week-max 15
python3 tools/query_roster.py --view matchup --team "Herb"
python3 tools/search_news.py "mccaffrey injury" --since-days 3

# Run the agent
python3 main.py chat        # or: python3 agent/chat.py

# Run the web app
python3 main.py serve --reload   # FastAPI on :8000 (serves frontend/dist in production)
cd frontend && npm install && npm run dev   # Vite dev server on :5173, proxies /api to :8000
cd frontend && npm run build                # production build, served by main.py serve
```

There is no test suite or linter configured for the Python side yet. The frontend has `tsc -b` as part of `npm run build`.

## Architecture

**Data flow:** three `ingest/*.py` scripts populate two local stores, which three `tools/*.py` modules read from, which `agent/chat.py` exposes to an LLM as tools:

```
espn_sync.py   ──┐
stats_sync.py  ──┼─→ data/db.sqlite (teams, rosters, matchups, player_stats)
                 │
news_sync.py   ──┴─→ data/chroma/ (Chroma collection "nfl_news")

query_roster.py, query_stats.py ─→ read data/db.sqlite
search_news.py                  ─→ read data/chroma/ (RAG retrieval)

agent/chat.py ─→ orchestrates all three tools via an LLM tool-calling loop

api/*.py       ─→ FastAPI wrappers around tools/*.py + a streaming variant of
                   agent/chat.py's tool loop (api/chat_service.py), for the web UI
frontend/src   ─→ React/Vite app consuming api/*.py over /api/*
```

All config (league ID, ESPN cookies, DB/Chroma paths, RSS feeds, model settings) is centralized in `config.py`, which loads from `.env` (see `.env.example`). Every script does `sys.path.insert(...)` + `import config` so any file can be run directly from its own directory, not just from repo root.

**`ingest/espn_sync.py`** — pulls the full league via `espn-api`, syncing **all** teams' rosters (not just the user's), and flags the user's own team via `teams.is_self`, matched by comparing `ESPN_SWID` against each team's `owners` list. `matchups` is populated from `league.box_scores(week)` (actual + projected scores), not the lighter `scoreboard()` call. Safe to re-run: `teams`/`matchups` upsert on their primary keys, `rosters` does delete-then-insert per team.

**`ingest/stats_sync.py`** — pulls nflverse weekly stats via `nfl-data-py`. Stores both `player_name` (nflverse's abbreviated form, e.g. `"J.Allen"`) and `player_display_name` (full name, e.g. `"Josh Allen"`) — the latter was added specifically so name search works for full names; don't drop it. Converts numpy scalars to native Python types before binding to sqlite3 (numpy float32/int64 aren't directly bindable). `player_stats` PK is `(player_id, season, week, season_type)`.

**`ingest/news_sync.py`** — the RAG ingestion half: fetches RSS via `feedparser`, strips HTML, chunks (~800 chars, 100 overlap), embeds with Chroma's bundled local `DefaultEmbeddingFunction` (ONNX MiniLM — no embedding API key needed), and upserts into Chroma with deterministic chunk IDs (`sha256(entry_id::chunk_index)`) so re-syncing never duplicates.

**`tools/*.py`** — each exposes the same two-symbol interface: `TOOL_SCHEMA` (a tool definition dict: `name`/`description`/`input_schema`) and `run_tool(tool_input: dict)`. `query_stats.py` validates `sort_by` against an allow-list before interpolating it into SQL (it's a column identifier, can't be parameterized) — extend that allow-list rather than removing the check if adding sortable columns.

**`agent/chat.py`** — a manual tool-calling loop against **OpenRouter** (OpenAI-compatible Chat Completions API), defaulting to `qwen/qwen3.7-flash` via `config.OPENROUTER_MODEL`. Each `TOOL_SCHEMA`'s `input_schema` is adapted to OpenAI's `{"type": "function", "function": {...}}` shape by `_to_openai_tool()` at call time, since the tool schemas keep the simpler `name`/`description`/`input_schema` shape rather than OpenAI's nested one.

**`main.py`** — the CLI entrypoint, with `sync`, `chat`, and `serve` subcommands. `cmd_sync()` runs each requested target (`espn`/`stats`/`news`) independently and catches exceptions per-target rather than letting one failure abort the rest — this matters in practice, since `stats` will legitimately fail before nflverse publishes a season's data while `espn`/`news` still succeed. Note: the `targets` positional arg intentionally has no `choices=` on its `argparse` definition — `nargs="*"` combined with `choices` throws on zero arguments (argparse validates the empty list itself against `choices`), so target validation is done manually against `SYNC_TARGETS` instead.

**`api/`** — FastAPI app for the web UI, no auth (single-user personal app). `api/routers/{league,stats,news,meta}.py` are thin wrappers that call straight into `tools/*.py`'s plain Python functions (not through the `TOOL_SCHEMA`/`run_tool` LLM-tool interface — that's only for the agent). `api/routers/chat.py` + `api/chat_service.py` reuse `agent.chat.SYSTEM_PROMPT`/`TOOLS`/`execute_tool` but reimplement the completion loop with `stream=True`, buffering `delta.tool_calls` by index across chunks (id/name/arguments each arrive split across multiple deltas) since OpenRouter's streaming tool-call format can't be handled by the CLI's non-streaming `run_turn`. The endpoint streams newline-delimited JSON events (`token`/`tool_call`/`tool_result`/`done`/`error`); the frontend is stateless server-side and resends the full message history each turn. In production `api/main.py` mounts `frontend/dist` as static files, so `main.py serve` alone serves the whole app.

**`frontend/`** — Vite + React + TypeScript + Tailwind v4. `src/lib/api.ts` has one fetch wrapper per `api/` endpoint plus `streamChat()`, an async generator that reads the ndjson chat stream. The chat system prompt asks the model for `##`-prefixed markdown headers, but smaller models don't always comply — `src/components/ChatMessage.tsx`'s `normalizeHeaders()` rewrites known plain-text header lines to markdown before rendering, so the three-section format (Changes to Starters / Waiver Wire Moves / People to Keep Your Eye On) still renders correctly either way. Assistant messages render via `react-markdown` + `remark-gfm` (tables, autolinks) with a full set of themed component overrides (headings, lists, links, code, blockquotes, tables) in `ChatMessage.tsx` — extend that `markdownComponents` map rather than letting new markdown constructs fall back to unstyled defaults.
