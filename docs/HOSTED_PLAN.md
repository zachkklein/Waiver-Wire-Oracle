# Hosted multi-user plan

Turning Waiver Wire Oracle from a clone-and-self-host tool into a website with
accounts. Tracked on the `hosted-multi-user` branch.

**Chosen shape: Option A — split hosting.** Vercel serves the SPA, a managed
container (Fly / Railway / Render) runs FastAPI plus the sync worker, Supabase
provides Postgres and Auth.

---

## Why not all-serverless (yet)

Vercel supports FastAPI, but the app can't run there as it stands:

| Package | Size | Needed for |
| --- | --- | --- |
| kubernetes | 84 MB | (a `chromadb` dependency) |
| onnxruntime | 80 MB | news embeddings |
| pandas | 70 MB | `stats_sync` only |
| numpy | 60 MB | stats + chroma |
| chromadb_rust_bindings | 49 MB | news |
| grpc | 39 MB | (chromadb) |
| openai | 20 MB | chat |
| **total site-packages** | **546 MB** | |

After stripping dev cruft that's still ~350–400 MB of genuinely-needed code,
over any serverless bundle cap. Two harder blockers than size:

1. **Chroma is a local file store.** `data/chroma/` must persist between
   requests; serverless gives an ephemeral `/tmp`.
2. **Sync isn't request-shaped.** `espn_sync` loops `box_scores(week)` for every
   week; `stats_sync` downloads and parses nflverse parquet.

A later all-serverless migration (Option B) is possible by moving vectors to
pgvector, query embeddings to a hosted API, and `stats_sync` to GitHub Actions —
which together drop ~420 MB. None of it is blocked by the work below, so it can
happen after launch.

## Target topology

| Concern | Where |
| --- | --- |
| Postgres (all tables + pgvector later) | Supabase |
| Auth / accounts / JWT | Supabase |
| Logo cache | Supabase Storage, or ephemeral (it's only a cache) |
| FastAPI app + sync worker | Managed container, ~$5–10/mo |
| Static frontend | Vercel |

RAM, not CPU, is the sizing constraint: Chroma's bundled ONNX MiniLM wants
~0.5–1 GB resident. Note that moving to pgvector does **not** remove this on its
own — queries still need embedding in-process unless embeddings also move to a
hosted API.

---

## Data model

The multi-league work already done is most of the multi-tenant model:
`teams` / `rosters` / `matchups` are keyed by `league_id`, which is ESPN's own
globally-unique id. Those tables **do not change**.

```
users(id, email, ...)                          -- new (or delegated to Supabase Auth)
user_leagues(user_id, league_id, espn_team_id,
             espn_swid_enc, espn_s2_enc, label) -- new: the join + per-user creds
leagues(league_id, season, name, last_synced_at)-- new: shared league metadata
teams / rosters / matchups                      -- UNCHANGED, already league-scoped
player_stats, news vectors                      -- UNCHANGED, global by design
```

Consequence: twelve people in one league share one copy of the data, and sync is
per-league rather than per-user.

## Storage and cost

Measured from the live single-league database:

| Data | Size | Scope |
| --- | --- | --- |
| `rosters` (162 rows) | 24.5 KB | per league |
| `teams` (10 rows) | 4 KB | per league |
| `matchups` | 4 KB (wk 1) → ~12 KB full season | per league |
| team logo cache | 146 KB | per league |
| `player_stats` (5,597 rows) | 717 KB **per season** | shared |
| Chroma news vectors | 3.6 MB | shared |

A league costs ~190 KB, most of it logo images; a user joining an existing league
costs about a kilobyte. At 1,000 users across ~400 leagues that's ~76 MB of
league data plus ~10–50 MB shared — inside every free Postgres tier.

The news store is the only thing that grows unbounded (every sync appends
chunks). Add a retention policy, e.g. drop chunks older than ~90 days.

**Infra ~$5–25/mo.** The only cost that scales per-user is LLM tokens: a single
Oracle question is a multi-turn tool loop, roughly 15–25K tokens end to end. At
flash-tier pricing that's a fraction of a cent per question — cents per user per
month, but unbounded without caps.

### API key policy

Default to **our** key with a metered free tier (e.g. 20 questions/month on a
cheap model), and offer bring-your-own-key as an opt-in that lifts the cap.
Requiring BYO key up front costs most non-technical signups. If BYO ships, check
whether OpenRouter's OAuth/PKCE key provisioning is still offered so we never
hold the raw secret.

> The OpenRouter key is *not* the biggest liability — `espn_s2` is. It's a
> session cookie for the user's whole ESPN account and is unavoidable for private
> leagues. Secret storage is designed around that; the OpenRouter key rides along.

---

## Phases

### Phase 1 — Kill the global config *(~1–2 days, the only tricky one)*

`config.ESPN_LEAGUE_ID` resolves through a module-level `__getattr__` to a single
"active league" **per process**. With concurrent users, one user switching
leagues changes what another user's next request reads. The notion of an active
league has to move from the process to the request.

Introduce `LeagueCtx` (league_id, season, swid, s2, team_id) and `UserCtx`
(openrouter key/model), resolved once per request and passed explicitly. Blast
radius — 26 `config.<SETTING>` reads across 11 files:

| File | Sites |
| --- | --- |
| `ingest/espn_sync.py` | 8 |
| `api/routers/logos.py` | 3 |
| `api/chat_service.py` | 3 |
| `agent/chat.py` | 3 |
| `ingest/stats_sync.py` | 2 |
| `api/routers/settings.py` | 2 |
| `api/main.py` | 2 |
| `tools/query_roster.py` | 1 |
| `ingest/news_sync.py` | 1 |
| `api/routers/meta.py` | 1 |

`query_stats` / `search_news` need no ctx — they read global data. `config.py`
shrinks to "build a ctx from settings.json/env" so the CLI keeps working.

**Done when:** the single-user app behaves identically and nothing outside the
ctx loader reads `config.ESPN_*`.

**Status: done.** `context.py` holds the frozen `LeagueCtx` / `UserCtx`; `config.py`
exposes `load_league_ctx()` / `load_user_ctx()` / `rss_feed_urls()`; `api/deps.py`
provides `LeagueDep` / `UserDep`, the two functions Phase 3 rewrites. `__getattr__` was
deleted outright, so a stray `config.ESPN_LEAGUE_ID` now raises `AttributeError` rather
than silently reading process state. Verified: all endpoints 200, the streaming chat
tool loop runs, `main.py sync espn` works, and two threads querying different
`LeagueCtx`s concurrently return different leagues' data.

### Phase 2 — SQLite → Postgres *(~1–2 days, mostly tedium)*

Add `users`, `user_leagues`, `leagues`; league-scoped tables unchanged. Real
budget item: queries are raw SQL with `?` placeholders and Postgres wants `%s`,
so every query in `query_roster`, `query_stats`, `meta`, `logos` needs touching —
worth a thin layer rather than a find-and-replace. Retire the hand-rolled
`_migrate_legacy_tables` / `_migrate_added_columns` in favour of real migrations.

**Done when:** same app, Postgres-backed, still single user.

### Phase 3 — Auth and onboarding *(~2–3 days)*

Supabase Auth (magic link or Google) issues a JWT; a FastAPI dependency verifies
it and yields `user_id`. Frontend gets a sign-in page and an auth guard in
`App.tsx`, replacing the current `configured → /setup` redirect.

The onboarding form already exists: `SetupPage.tsx`'s `?new=1` mode plus
`POST /api/settings/league-preview` is exactly the new-user flow (validate creds,
list teams, pick yours). It just writes to `user_leagues` instead of
`settings.json`. `LeagueSwitcher` reads from there too.

**Done when:** two browsers signed in as different accounts see different leagues
at the same time.

### Phase 4 — Encrypt secrets at rest *(~half a day)*

AES-GCM or Fernet with a key from the environment, covering `espn_s2` / `swid`
and any stored OpenRouter key. Keep the `has_*` boolean pattern
`settings_summary()` already uses.

**Done when:** a database dump contains no plaintext credentials.

### Phase 5 — Real sync *(~2 days)*

Move off `BackgroundTasks` to a worker with a per-league lock. Sync once per
league regardless of how many users are in it. Pick credentials from any linked
user, preferring the most recently validated; when cookies expire, mark that link
stale and prompt only that user. Trigger on staleness at page load (~15 min)
rather than a blanket cron — 400 leagues on an hourly cron is a lot of traffic
aimed at ESPN's private endpoints.

**Done when:** two users in one league trigger one sync.

### Phase 6 — Ship *(~1–2 days)*

Fix the `/roster` deep-link 404 (`StaticFiles(html=True)` has no SPA fallback);
mandatory once links are shareable. Add per-user rate limits and token metering.
Decide logo storage.

---

## Open decisions

1. **Does self-hosting survive?** Recommend yes — if Phase 1 is done cleanly the
   CLI keeps working by building a ctx from local `settings.json`, so both
   stories coexist cheaply.
2. **Chroma or pgvector.** Lean pgvector: one datastore to operate, and the news
   store is global and read-mostly so migration is easy.
3. **Vercel plan.** Hobby is free but its terms restrict commercial use; price in
   Pro if this becomes a real product.

## Risk worth going in clear-eyed on

`espn-api` works against ESPN's private fantasy endpoints, not a public API.
Fine for a personal tool and fine for a friends-and-family site; running it as a
public service that stores strangers' ESPN session cookies and calls ESPN on
their behalf at scale is a different posture. Not a blocker, but it's the kind of
thing that gets IP-blocked — build the lazy-refresh behaviour early rather than
retrofitting it.
