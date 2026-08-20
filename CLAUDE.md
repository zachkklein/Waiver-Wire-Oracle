# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Waiver Wire Oracle — a personal fantasy football assistant for one or more ESPN leagues. It combines ESPN league data, nflverse player stats, and RAG over NFL news RSS feeds, queried by an LLM agent with tool-calling. Everything runs locally against a single SQLite file and a local Chroma vector store. A FastAPI + React web app (`api/`, `frontend/`) sits on top of the same CLI tools/agent for browsing the league and chatting with the Oracle in a browser.

It's meant to be **cloned and self-hosted** by one person: a fresh install is configured entirely from the in-app Setup page (`/setup`), so `.env` is optional and exists mainly for headless/container setups. There is no auth and no multi-tenancy — everyone hitting the URL shares one "active" league at a time (see the multi-league note under `config.py` below), so don't assume anything here is multi-user.

## Commands

```bash
# Setup
python3 -m venv venv          # use Python 3.11 — nfl-data-py's pandas pin has no 3.13 wheel
source venv/bin/activate
pip install -r requirements.txt
# League/keys are configured at http://localhost:8000/setup after `main.py serve`;
# .env is only needed for headless setups (see .env.example).

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

**Data flow:** three `ingest/*.py` scripts populate two stores, which three `tools/*.py` modules read from, which `agent/chat.py` exposes to an LLM as tools:

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

All config is centralized in `config.py`. Paths (`DATA_DIR`, `DB_PATH`, `CHROMA_PATH`) and `OPENROUTER_BASE_URL` are plain module constants; everything a user can change is read fresh from disk in priority order: `data/settings.json` (written by the in-app Setup page) → env/`.env` → built-in defaults. Saving from the Setup page (or switching the active league) therefore takes effect without restarting the server — **don't convert these into module-level constants**, and don't add new user-settable values without adding them to `LEAGUE_FIELDS` (if it varies per league) or `GLOBAL_SETTING_KEYS` (if it's shared) — both are folded into `SETTING_KEYS`. `save_settings()` merges (ignoring `None`) and writes atomically, so the UI can omit unchanged secrets rather than blanking them.

**Two database backends (`db.py`)** — everything goes through `db.connect()` / `db.session()`, never `sqlite3` directly (`sqlite3` is imported in exactly one file, and it should stay that way). With `DATABASE_URL` unset the app uses the local `data/db.sqlite`, so `git clone && main.py serve` still needs no external services; set it and the same code runs on Postgres (Supabase, for the hosted build). Rules that keep this working:
- **Write SQL in SQLite's `?` placeholder style.** `db._to_pg()` rewrites it for psycopg, doubling literal `%` and converting `?` outside string literals. Never hand-write `%s`.
- **Read rows by name** (`row["team_name"]`), never by index — `sqlite3.Row` supports both, psycopg's `dict_row` only the former.
- **Keep DDL in the subset both backends share**: `CREATE TABLE IF NOT EXISTS`, `TEXT`/`INTEGER`/`REAL`, composite `PRIMARY KEY`, `ON CONFLICT (...) DO UPDATE SET x = excluded.x`. One schema string then runs on both, which is why `init_db()` is a harmless no-op against Postgres.
- **Booleans stay `INTEGER` 0/1, not Postgres `BOOLEAN`** — the frontend renders them with a ternary and expects a number (see the `is_self` note below).
- Backend-specific introspection lives behind `db.table_names()`, `db.column_names()` and `db.is_initialized()` (the last replaces the old `os.path.exists(DB_PATH)` check, which only made sense for a file).

Postgres connections are **pooled** (`psycopg_pool`, lazily created in `db._get_pool()`). Opening one per request meant a TLS handshake to the database's region every time — measured at ~0.7s of pure overhead per request against a remote Supabase. `_PgConnection.close()` returns the connection to the pool and rolls back first, so it goes back `IDLE`: psycopg is not autocommit, so even a plain SELECT leaves it `INTRANS`, and handing it back that way makes the pool log "rolling back returned connection" on every request.

Expect Postgres to feel slow in local development — roughly 110ms per round trip from a laptop to a cloud region, versus ~1ms for the SQLite file. That's geography, not the code: in production the app and database sit in the same region. It's also a good reason to keep developing against SQLite (just leave `DATABASE_URL` unset). Because round trips dominate, prefer one query over several: `/api/meta` runs its five aggregates as subqueries in a single statement for exactly this reason, and it's refetched on every navigation.

Schema changes go in `supabase/migrations/*.sql` **and** the `SCHEMA` string in the relevant `ingest/*.py`, which must stay identical. `scripts/migrate_to_postgres.py` copies an existing SQLite database over (idempotent, upserts on primary keys); `player_stats` and the news store are global, so they can equally just be re-synced.

Supabase exposes every `public` table through PostgREST using the anon key that ships in the browser. All tables therefore have **RLS enabled with no policies** — the backend connects directly to Postgres as the table owner and bypasses RLS, so this denies the REST API without affecting the app. The database linter reporting `rls_enabled_no_policy` at INFO is the intended state, not a bug to fix.

**Contexts, not globals (`context.py`)** — there is deliberately **no `config.ESPN_LEAGUE_ID` attribute**; reading one raises `AttributeError`. "The active league" is a property of the *process*, which stops being meaningful the moment two people use a hosted build at once (see `docs/HOSTED_PLAN.md`). Instead `config.load_league_ctx()` returns a frozen `LeagueCtx` (league_id/season/swid/s2/team_id, plus `.key` for scoping SQL, `.is_configured`, and `.espn_cookies`) and `config.load_user_ctx()` a `UserCtx` (OpenRouter key + model); callers take one as an argument. `config.rss_feed_urls()` stays a plain module read — news feeds are global infrastructure config, not per-user. In `api/`, routers depend on `LeagueDep`/`UserDep` from `api/deps.py` rather than calling the loaders directly: those two dependency functions are the single seam that the hosted build swaps for a JWT → `user_leagues` lookup. Don't reintroduce a module-level "current league" in any form.

**Multi-league**: `data/settings.json` holds a `leagues` list (each entry keyed by its own `ESPN_LEAGUE_ID`, plus `ESPN_SEASON`/`ESPN_SWID`/`ESPN_S2`/`ESPN_TEAM_ID`/`label`) and an `active_league_id`. `ESPN_*` attributes on `config` always resolve to the *active* league's fields — `OPENROUTER_API_KEY`/`OPENROUTER_MODEL`/`RSS_FEED_URLS` stay top-level/global, shared across every league. `config.save_settings()` edits the active league's fields (or global fields); `config.add_league()`/`set_active_league()`/`delete_league()`/`list_leagues()` manage the list, backing `api/routers/leagues.py`. Pre-multi-league `settings.json` files (flat `ESPN_*` keys, no `leagues`) and pure-`.env` setups (nothing persisted yet) are handled by `_active_league()`'s fallback chain — the former migrates to a one-entry `leagues` list in place on first read, the latter resolves virtually from env without writing a file until a second league is added. Don't assume there's always a persisted `leagues` entry; go through `_active_league()`/`_resolve()`, not `_load_settings()` directly, when you need the active league's fields.

**`ingest/espn_sync.py`** — pulls the full league via `espn-api`, syncing **all** teams' rosters (not just the user's), and flags the user's own team via `teams.is_self`. `find_self_team_id()` prefers an explicitly configured `ESPN_TEAM_ID` (the only signal available for public leagues, which have no cookies), falling back to matching `ESPN_SWID` against each team's `owners` list. `espn_s2`/`swid` are optional — public leagues load fine with them as `None`. `matchups` is populated from `league.box_scores(week)` (actual + projected scores), not the lighter `scoreboard()` call. `teams`/`rosters`/`matchups` are keyed by `league_id` (ESPN's own league id, reused as-is — already globally unique, no synthetic id needed) so multiple leagues can share one `db.sqlite` without collisions; `init_db()` runs a one-time migration (`_migrate_legacy_tables()`) that renames pre-multi-league tables aside, recreates them with the `league_id` column, and backfills existing rows with the currently active league's id — safe to re-run (a no-op once the column exists). `player_stats` (nflverse) and the Chroma news store stay unscoped: they aren't tied to any one ESPN league. Safe to re-run: `teams`/`matchups` upsert on their primary keys, `rosters` does delete-then-insert per team (both scoped to `league_id`). `teams.logo_url` holds ESPN's own team-logo URL; `_migrate_added_columns()` (driven by the `ADDED_COLUMNS` map) `ALTER TABLE`s in columns added after a table's first release — use it for any further additive column, since unlike the `league_id` migration those need no backfill.

**`ingest/stats_sync.py`** — pulls nflverse weekly stats via `nfl-data-py`. Stores both `player_name` (nflverse's abbreviated form, e.g. `"J.Allen"`) and `player_display_name` (full name, e.g. `"Josh Allen"`) — the latter was added specifically so name search works for full names; don't drop it. Converts numpy scalars to native Python types before binding to sqlite3 (numpy float32/int64 aren't directly bindable). `player_stats` PK is `(player_id, season, week, season_type)`.

**`ingest/news_sync.py`** — the RAG ingestion half: fetches RSS via `feedparser`, strips HTML, chunks (~800 chars, 100 overlap), embeds with Chroma's bundled local `DefaultEmbeddingFunction` (ONNX MiniLM — no embedding API key needed), and upserts into Chroma with deterministic chunk IDs (`sha256(entry_id::chunk_index)`) so re-syncing never duplicates.

**`tools/*.py`** — each exposes the same two-symbol interface: `TOOL_SCHEMA` (a tool definition dict: `name`/`description`/`input_schema`) and `run_tool(tool_input: dict, league: LeagueCtx | None = None)`. The `league` argument is supplied by the caller and is deliberately *not* in `TOOL_SCHEMA`, so the model can never ask for a league it shouldn't see; `query_stats`/`search_news` accept and ignore it (nflverse/RSS data isn't league-specific). `query_stats.py` validates `sort_by` against an allow-list before interpolating it into SQL (it's a column identifier, can't be parameterized) — extend that allow-list rather than removing the check if adding sortable columns. `query_roster.py` takes a `LeagueCtx` as its first argument and scopes every `teams`/`rosters`/`matchups` query by `league.key` — including the `team_names` lookup used to label matchups, since `team_id` values are only unique within a league, not across leagues sharing the same database. `query_stats.py`/`search_news.py` stay unscoped (nflverse/RSS data isn't league-specific). `query_roster.py` also takes `include_logos` (default `False`), which adds `logo_url`/`home_logo_url`/`away_logo_url` to its output — the `api/` routers pass `True`, the agent never does, since logo URLs are pure noise in an LLM's tool results.

**`agent/chat.py`** — a manual tool-calling loop against **OpenRouter** (OpenAI-compatible Chat Completions API), defaulting to `qwen/qwen3.7-flash` via `config.OPENROUTER_MODEL`. Each `TOOL_SCHEMA`'s `input_schema` is adapted to OpenAI's `{"type": "function", "function": {...}}` shape by `_to_openai_tool()` at call time, since the tool schemas keep the simpler `name`/`description`/`input_schema` shape rather than OpenAI's nested one.

**`main.py`** — the CLI entrypoint, with `sync`, `chat`, and `serve` subcommands. `cmd_sync()` runs each requested target (`espn`/`stats`/`news`) independently and catches exceptions per-target rather than letting one failure abort the rest — this matters in practice, since `stats` will legitimately fail before nflverse publishes a season's data while `espn`/`news` still succeed. Note: the `targets` positional arg intentionally has no `choices=` on its `argparse` definition — `nargs="*"` combined with `choices` throws on zero arguments (argparse validates the empty list itself against `choices`), so target validation is done manually against `SYNC_TARGETS` instead.

**`api/`** — FastAPI app for the web UI, no auth (single-user, self-hosted). `api/routers/settings.py` backs the Setup page: `GET/PUT /api/settings` (secrets are never returned to the browser — `config.settings_summary()` reports them as `has_*` booleans, and the UI omits them on save unless retyped; `PUT` edits the *active* league's fields plus global fields via `config.save_settings()`), `POST /api/settings/league-preview` (validates ESPN credentials and returns the team list so the user can pick their team — used both when editing the active league and, unsaved, when connecting a new one), and `POST/GET /api/sync` (runs ingests via `BackgroundTasks` with polled status, importing `nfl-data-py` lazily so API startup stays fast; always syncs the currently active league). `api/routers/leagues.py` manages the league list itself: `GET /api/leagues` (all leagues, secrets redacted, active one flagged — via `config.list_leagues()`), `POST /api/leagues` (add a new league without touching the active one, then make it active), `PUT /api/leagues/{id}/activate`, `DELETE /api/leagues/{id}`. `api/routers/logos.py` serves `GET /api/team-logo/{team_id}`, which proxies the active league's team logos and caches them under `data/logos/`. Proxying isn't optional: ESPN serves its stock logo packs publicly from `g.espncdn.com`, but members' own uploads live on `mystique-api.fantasy.espn.com` and **401 without the league's `espn_s2`/`SWID` cookies** — which the browser doesn't have and shouldn't be given — so the frontend never links a team logo directly, it goes through `teamLogoUrl()` in `src/lib/api.ts`. The cache filename embeds a digest of the source URL, so re-uploading a logo misses the cache rather than serving the old image forever; the proxy refuses any host outside `.espn.com`/`.espncdn.com`. `api/routers/{league,stats,news,meta}.py` are thin wrappers that call straight into `tools/*.py`'s plain Python functions (not through the `TOOL_SCHEMA`/`run_tool` LLM-tool interface — that's only for the agent); `meta.py` scopes its `teams`/`rosters`/`matchups` queries by `league.key` from `LeagueDep`, same as `query_roster.py`. `api/main.py`'s startup hook runs `espn_sync.init_db()` once (schema creation/migration only, no ESPN calls) so `db.sqlite` always has the `league_id` column before any request is served, even on a DB from before multi-league support. `api/routers/chat.py` + `api/chat_service.py` reuse `agent.chat.SYSTEM_PROMPT`/`TOOLS`/`execute_tool` but reimplement the completion loop with `stream=True`, buffering `delta.tool_calls` by index across chunks (id/name/arguments each arrive split across multiple deltas) since OpenRouter's streaming tool-call format can't be handled by the CLI's non-streaming `run_turn`. The endpoint streams newline-delimited JSON events (`token`/`tool_call`/`tool_result`/`done`/`error`); the frontend is stateless server-side and resends the full message history each turn — the Oracle answers about whichever league is currently active. In production `api/main.py` mounts `frontend/dist` as static files, so `main.py serve` alone serves the whole app.

**`frontend/`** — Vite + React + TypeScript + Tailwind v4. `src/lib/api.ts` has one fetch wrapper per `api/` endpoint plus `streamChat()`, an async generator that reads the ndjson chat stream. `App.tsx` fetches `/api/meta` on every navigation and redirects to `/setup` when `configured` is false, and shows a "nothing synced yet" banner when `configured && !has_data` — so every page can assume it either has data or the user has been told why it doesn't. `SetupPage.tsx` deliberately preselects no team after a league preview: an explicit `ESPN_TEAM_ID` outranks SWID detection in `find_self_team_id()`, so guessing would silently mis-assign the user's team.

**`LeagueSwitcher.tsx`** (mounted in `TopBar.tsx`, replacing the old static "Week X"/"Preseason" label) — fetches `/api/leagues` and renders a dropdown of every configured league plus a "+ Add another league" item. Picking a different league calls `PUT /api/leagues/{id}/activate` then does a full `window.location.reload()` — every page fetches its own data fresh on mount scoped server-side to whichever league is active, so a reload is the simplest way to refresh the whole app at once rather than threading a league-changed event through every page. `SetupPage.tsx` has two modes driven by the `?new=1` query param (only reachable via the switcher's "+ Add another league" item): normal mode edits the *active* league's fields via `PUT /api/settings` (unchanged from before multi-league support) and shows the Oracle/News cards; `?new=1` mode starts the league-connect form blank, hides the Oracle/News/Sync cards (those are global — edit them from the non-`?new` Setup page instead), and submits via `POST /api/leagues` instead, then hard-navigates to plain `/setup` (now editing the newly-added, now-active league) so the "Pull in data" sync card is available for it. Both modes reuse the same `POST /api/settings/league-preview` "Connect league" flow to validate credentials and list teams before submitting.

*Design system ("Night Game")* — all tokens live in `src/index.css` under `@theme`; use the semantic names (`bg`, `surface`, `surface-raised`, `border`, `text`, `text-muted`, `text-faint`, `accent`, `pos-*`, `status-*`) rather than raw hex. The ground is a deep turf black-green and the single accent is trophy brass.

The look is deliberately **soft, not boxy** — an earlier hard-edged/monospace/all-caps pass was rejected for reading machine-made, so keep these rules:
- **Rounded geometry everywhere.** Cards `rounded-2xl`, inputs `rounded-xl`, buttons/badges/chips `rounded-full`, avatars circular (`TeamBadge`, which renders the team's ESPN logo when there is one and falls back to colored initials on a missing or failed image). Nothing square-cornered.
- **Two faces only.** `font-display` is **Fraunces** (soft serif) for headings, team names, and card titles — always paired with the `soft` utility, which dials its `SOFT` variation axis up and tightens tracking. Everything else, including all figures, is **Plus Jakarta Sans** (`font-sans`) with `tabular-nums` on numbers. There is no monospace UI type; `font-mono` appears only inside chat code blocks.
- **Sentence case.** No `uppercase` + wide `tracking-*` micro-labels; use normal-case `text-xs text-text-muted` instead.
- **Depth over borders.** Prefer `shadow-soft`/`shadow-lift` and `hover:-translate-y-0.5` over dividing lines; row separation comes from padding and `hover:bg-surface-raised`.
- The `pressable` utility gives primary buttons a tactile bottom-shade that presses in on `:active` — use it on primary actions only.

`DashboardPage.tsx` is built to fill the viewport exactly rather than scroll: the root is `lg:h-full lg:min-h-0`, the header/stat/shortcut rows are `shrink-0`, and only the matchup+standings row is `lg:flex-1` — deliberately *without* `min-h-0`, so it can absorb spare height but never compress below its content. The standings card shows a five-team window centred on your own rank (`STANDINGS_WINDOW`, clamped at either end of the table), which is what makes that row short enough to fit; adding rows or padding there is what will bring the scrollbar back. Verified at a 697px-tall viewport, the tightest realistic case.

Note that SQLite returns booleans as `0`/`1`, so guard them with a ternary in JSX (`{t.is_self ? <x/> : null}`) — `{t.is_self && <x/>}` renders a literal `0` on screen. The chat system prompt asks for `##` headers and `- ` bullets, but smaller models drift — `src/components/ChatMessage.tsx`'s `normalizeMarkdown()` repairs the two observed failures before rendering: header lines that lost their `##`, and literal `•` characters emitted inline (sometimes several per line) instead of list items. Keep both repairs; the three-section format (Changes to Starters / Waiver Wire Moves / People to Keep Your Eye On) depends on them. Assistant messages render via `react-markdown` + `remark-gfm` (tables, autolinks) with a full set of themed component overrides (headings, lists, links, code, blockquotes, tables) in `ChatMessage.tsx` — extend that `markdownComponents` map rather than letting new markdown constructs fall back to unstyled defaults.
