# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Waiver Wire Oracle — a personal fantasy football assistant for one ESPN league. It combines ESPN league data, nflverse player stats, and RAG over NFL news RSS feeds, queried by an LLM agent with tool-calling. Everything runs locally against a single SQLite file and a local Chroma vector store; there is no server/website yet (planned, not started — `main.py` is currently just a stub).

## Commands

```bash
# Setup
python3 -m venv venv          # use Python 3.11 — nfl-data-py's pandas pin has no 3.13 wheel
source venv/bin/activate
pip install -r requirements.txt

# Ingest (run in this order the first time; each is independently idempotent/re-runnable)
python3 ingest/espn_sync.py                    # -> teams, rosters, matchups tables
python3 ingest/stats_sync.py [year ...]         # -> player_stats table; defaults to ESPN_SEASON
python3 ingest/news_sync.py [feed_url ...]      # -> Chroma "nfl_news" collection; defaults to RSS_FEED_URLS

# Query tools directly (each is also usable as a standalone CLI for debugging)
python3 tools/query_stats.py --player "Josh Allen" --season 2024 --week-min 14 --week-max 15
python3 tools/query_roster.py --view matchup --team "Herb"
python3 tools/search_news.py "mccaffrey injury" --since-days 3

# Run the agent
python3 agent/chat.py
```

There is no test suite, linter, or build step configured yet.

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
```

All config (league ID, ESPN cookies, DB/Chroma paths, RSS feeds, model settings) is centralized in `config.py`, which loads from `.env` (see `.env.example`). Every script does `sys.path.insert(...)` + `import config` so any file can be run directly from its own directory, not just from repo root.

**`ingest/espn_sync.py`** — pulls the full league via `espn-api`, syncing **all** teams' rosters (not just the user's), and flags the user's own team via `teams.is_self`, matched by comparing `ESPN_SWID` against each team's `owners` list. `matchups` is populated from `league.box_scores(week)` (actual + projected scores), not the lighter `scoreboard()` call. Safe to re-run: `teams`/`matchups` upsert on their primary keys, `rosters` does delete-then-insert per team.

**`ingest/stats_sync.py`** — pulls nflverse weekly stats via `nfl-data-py`. Stores both `player_name` (nflverse's abbreviated form, e.g. `"J.Allen"`) and `player_display_name` (full name, e.g. `"Josh Allen"`) — the latter was added specifically so name search works for full names; don't drop it. Converts numpy scalars to native Python types before binding to sqlite3 (numpy float32/int64 aren't directly bindable). `player_stats` PK is `(player_id, season, week, season_type)`.

**`ingest/news_sync.py`** — the RAG ingestion half: fetches RSS via `feedparser`, strips HTML, chunks (~800 chars, 100 overlap), embeds with Chroma's bundled local `DefaultEmbeddingFunction` (ONNX MiniLM — no embedding API key needed), and upserts into Chroma with deterministic chunk IDs (`sha256(entry_id::chunk_index)`) so re-syncing never duplicates.

**`tools/*.py`** — each exposes the same two-symbol interface: `TOOL_SCHEMA` (a tool definition dict: `name`/`description`/`input_schema`) and `run_tool(tool_input: dict)`. `query_stats.py` validates `sort_by` against an allow-list before interpolating it into SQL (it's a column identifier, can't be parameterized) — extend that allow-list rather than removing the check if adding sortable columns.

**`agent/chat.py`** — a manual tool-calling loop against **OpenRouter** (OpenAI-compatible Chat Completions API), defaulting to `qwen/qwen3.7-flash` via `config.OPENROUTER_MODEL`. Each `TOOL_SCHEMA`'s `input_schema` is adapted to OpenAI's `{"type": "function", "function": {...}}` shape by `_to_openai_tool()` at call time, since the tool schemas keep the simpler `name`/`description`/`input_schema` shape rather than OpenAI's nested one.
