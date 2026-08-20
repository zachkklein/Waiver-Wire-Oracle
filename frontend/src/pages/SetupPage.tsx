import { useEffect, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { api } from "../lib/api"
import type { LeaguePreview, Settings, SyncStatus, SyncTarget } from "../lib/types"
import PageHeader from "../components/PageHeader"
import Card from "../components/Card"
import { LoadingState, ErrorState } from "../components/EmptyState"

const SYNC_LABELS: Record<SyncTarget, string> = {
  espn: "League",
  stats: "Player stats",
  news: "News",
}

function Label({ children, hint }: { children: string; hint?: string }) {
  return (
    <div className="mb-1.5">
      <div className="text-sm font-semibold text-text">{children}</div>
      {hint && <div className="mt-0.5 text-xs leading-relaxed text-text-muted">{hint}</div>}
    </div>
  )
}

const inputClass =
  "w-full rounded-xl border border-border bg-surface-raised px-4 py-2.5 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"

export default function SetupPage() {
  const [searchParams] = useSearchParams()
  const isNew = searchParams.get("new") === "1"

  const [settings, setSettings] = useState<Settings | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [leagueId, setLeagueId] = useState("")
  const [season, setSeason] = useState(String(new Date().getFullYear()))
  const [isPrivate, setIsPrivate] = useState(false)
  const [swid, setSwid] = useState("")
  const [s2, setS2] = useState("")
  const [teamId, setTeamId] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [model, setModel] = useState("")
  const [feeds, setFeeds] = useState("")

  const [preview, setPreview] = useState<LeaguePreview | null>(null)
  const [connecting, setConnecting] = useState(false)
  const [connectError, setConnectError] = useState<string | null>(null)

  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const [sync, setSync] = useState<SyncStatus | null>(null)
  const pollRef = useRef<number | null>(null)

  useEffect(() => {
    api
      .settings()
      .then((s) => {
        setSettings(s)
        // Adding another league starts from a blank league form — only the shared
        // Oracle/news fields (hidden in this mode anyway) come from existing settings.
        if (!isNew) {
          setLeagueId(s.ESPN_LEAGUE_ID)
          if (s.ESPN_SEASON) setSeason(s.ESPN_SEASON)
          setTeamId(s.ESPN_TEAM_ID)
          setIsPrivate(s.has_espn_swid || s.has_espn_s2)
        }
        setModel(s.OPENROUTER_MODEL)
        setFeeds(s.RSS_FEED_URLS.join("\n"))
      })
      .catch((e) => setLoadError(String(e)))
  }, [isNew])

  // Poll while a sync is running so the progress list stays live.
  useEffect(() => {
    if (!sync?.running) {
      if (pollRef.current) window.clearInterval(pollRef.current)
      return
    }
    pollRef.current = window.setInterval(() => {
      api.syncStatus().then(setSync).catch(() => {})
    }, 1500)
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current)
    }
  }, [sync?.running])

  if (loadError) return <ErrorState message={loadError} />
  if (!settings) return <LoadingState />

  const connect = async () => {
    setConnecting(true)
    setConnectError(null)
    setPreview(null)
    try {
      const result = await api.leaguePreview({
        ESPN_LEAGUE_ID: leagueId.trim(),
        ESPN_SEASON: season.trim(),
        ESPN_SWID: isPrivate ? swid.trim() || undefined : undefined,
        ESPN_S2: isPrivate ? s2.trim() || undefined : undefined,
      })
      setPreview(result)
      // Deliberately no default: an explicit team id outranks SWID detection in
      // find_self_team_id(), so guessing here could mis-assign the user's team.
    } catch (e) {
      setConnectError(e instanceof Error ? e.message : String(e))
    } finally {
      setConnecting(false)
    }
  }

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      if (isNew) {
        await api.addLeague({
          ESPN_LEAGUE_ID: leagueId.trim(),
          ESPN_SEASON: season.trim(),
          label: preview?.league_name ?? undefined,
          ESPN_TEAM_ID: teamId || undefined,
          ...(isPrivate && swid.trim() ? { ESPN_SWID: swid.trim() } : {}),
          ...(isPrivate && s2.trim() ? { ESPN_S2: s2.trim() } : {}),
        })
        // The new league is now active — reload into the plain setup flow (no ?new)
        // for it, so the "Pull in data" card syncs it.
        window.location.href = "/setup"
        return
      }

      const updated = await api.saveSettings({
        ESPN_LEAGUE_ID: leagueId.trim(),
        ESPN_SEASON: season.trim(),
        ESPN_TEAM_ID: teamId,
        OPENROUTER_MODEL: model.trim() || undefined,
        RSS_FEED_URLS: feeds
          .split("\n")
          .map((f) => f.trim())
          .filter(Boolean),
        ...(preview?.league_name ? { label: preview.league_name } : {}),
        // Secrets are only sent when newly typed, so blanks don't wipe stored values.
        ...(isPrivate && swid.trim() ? { ESPN_SWID: swid.trim() } : {}),
        ...(isPrivate && s2.trim() ? { ESPN_S2: s2.trim() } : {}),
        ...(apiKey.trim() ? { OPENROUTER_API_KEY: apiKey.trim() } : {}),
      })
      setSettings(updated)
      setSaved(true)
      setSwid("")
      setS2("")
      setApiKey("")
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  const runSync = async (targets?: SyncTarget[]) => {
    try {
      await api.startSync(targets)
      setSync({ running: true, results: {}, started_at: null, finished_at: null })
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={isNew ? "Add another league" : "Setup"}
        eyebrow={
          isNew
            ? "Connect another ESPN league. Your OpenRouter key and news feeds are shared across leagues — manage those from the main Setup page."
            : "Connect your ESPN league and pull in data. Everything is stored locally in data/settings.json."
        }
      />

      <div className="flex flex-col gap-5">
        <Card title="Your league">
          <div className="flex flex-col gap-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label hint="From your league URL: fantasy.espn.com/football/team?leagueId=XXXXXXX">
                  League ID
                </Label>
                <input
                  value={leagueId}
                  onChange={(e) => setLeagueId(e.target.value)}
                  placeholder="e.g. 123456789"
                  className={inputClass}
                />
              </div>
              <div>
                <Label hint="The season year you want to load.">Season</Label>
                <input
                  value={season}
                  onChange={(e) => setSeason(e.target.value)}
                  placeholder="2026"
                  className={inputClass}
                />
              </div>
            </div>

            <label className="flex items-start gap-3 rounded-xl bg-surface-raised p-4">
              <input
                type="checkbox"
                checked={isPrivate}
                onChange={(e) => setIsPrivate(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded accent-accent"
              />
              <span>
                <span className="text-sm font-semibold text-text">My league is private</span>
                <span className="mt-0.5 block text-xs leading-relaxed text-text-muted">
                  Public leagues need nothing but the league ID. Private ones need two cookies
                  from a browser where you're signed in to ESPN.
                </span>
              </span>
            </label>

            {isPrivate && (
              <div className="flex flex-col gap-4">
                <p className="rounded-xl bg-surface-raised p-4 text-xs leading-relaxed text-text-muted">
                  In a browser signed in to fantasy.espn.com, open DevTools →{" "}
                  <span className="text-text">Application</span> →{" "}
                  <span className="text-text">Cookies</span> → <code>fantasy.espn.com</code>, then
                  copy the <code>SWID</code> and <code>espn_s2</code> values. They stay on this
                  machine and are never sent anywhere but ESPN.
                </p>
                <div>
                  <Label
                    hint={
                      !isNew && settings.has_espn_swid ? "Already saved — type to replace it." : undefined
                    }
                  >
                    SWID
                  </Label>
                  <input
                    value={swid}
                    onChange={(e) => setSwid(e.target.value)}
                    placeholder={
                      !isNew && settings.has_espn_swid ? "••••••••" : "{XXXXXXXX-XXXX-...}"
                    }
                    className={inputClass}
                  />
                </div>
                <div>
                  <Label
                    hint={
                      !isNew && settings.has_espn_s2 ? "Already saved — type to replace it." : undefined
                    }
                  >
                    espn_s2
                  </Label>
                  <input
                    value={s2}
                    onChange={(e) => setS2(e.target.value)}
                    placeholder={!isNew && settings.has_espn_s2 ? "••••••••" : "AEB..."}
                    className={inputClass}
                  />
                </div>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={connect}
                disabled={connecting || !leagueId.trim() || !season.trim()}
                className="pressable rounded-full bg-accent px-6 py-2.5 text-sm font-bold text-bg hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
              >
                {connecting ? "Connecting" : "Connect league"}
              </button>
              {preview && (
                <span className="text-sm text-status-good">
                  Found {preview.league_name ?? "your league"} · {preview.teams.length} teams
                </span>
              )}
            </div>

            {connectError && <ErrorState message={connectError} />}
          </div>
        </Card>

        {preview && (
          <Card title="Which team is yours?">
            <p className="mb-4 text-sm leading-relaxed text-text-muted">
              {(isNew ? swid.trim() : settings.has_espn_swid)
                ? "Optional — your team is already identified from your SWID cookie. Pick one only if you want to override that."
                : "Public leagues can't detect this automatically, so choose your team here."}
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {preview.teams.map((t) => (
                <label
                  key={t.team_id}
                  className={`flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition-colors ${
                    teamId === String(t.team_id)
                      ? "border-accent/50 bg-accent/10 text-accent"
                      : "border-border text-text-muted hover:bg-surface-raised"
                  }`}
                >
                  <input
                    type="radio"
                    name="team"
                    checked={teamId === String(t.team_id)}
                    onChange={() => setTeamId(String(t.team_id))}
                    className="h-4 w-4 accent-accent"
                  />
                  <span className="truncate font-medium">{t.team_name}</span>
                </label>
              ))}
            </div>
          </Card>
        )}

        {!isNew && (
          <Card title="The Oracle">
            <div className="flex flex-col gap-4">
              <div>
                <Label
                  hint={
                    settings.has_openrouter_api_key
                      ? "Already saved — type to replace it."
                      : "Create one at openrouter.ai → Keys. Needed for the chat page only."
                  }
                >
                  OpenRouter API key
                </Label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={settings.has_openrouter_api_key ? "••••••••" : "sk-or-..."}
                  className={inputClass}
                />
              </div>
              <div>
                <Label hint="Any tool-calling model OpenRouter offers.">Model</Label>
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="qwen/qwen3.7-flash"
                  className={inputClass}
                />
              </div>
            </div>
          </Card>
        )}

        {!isNew && (
          <Card title="News feeds">
            <Label hint="One RSS URL per line. These are searched on the News page and by the Oracle.">
              Feeds
            </Label>
            <textarea
              value={feeds}
              onChange={(e) => setFeeds(e.target.value)}
              rows={5}
              className={`${inputClass} resize-y font-mono text-xs`}
            />
          </Card>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={save}
            disabled={saving}
            className="pressable rounded-full bg-accent px-7 py-3 text-sm font-bold text-bg hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
          >
            {saving ? (isNew ? "Adding" : "Saving") : isNew ? "Add league" : "Save settings"}
          </button>
          {saved && <span className="text-sm text-status-good">Saved</span>}
        </div>

        {saveError && <ErrorState message={saveError} />}

        {!isNew && (
          <Card title="Pull in data">
            <p className="mb-4 text-sm leading-relaxed text-text-muted">
              Save your settings first, then sync. The league takes a few seconds; player stats and
              news take longer on the first run.
            </p>
            <div className="flex flex-wrap gap-2.5">
              <button
                onClick={() => runSync()}
                disabled={sync?.running || !settings.configured}
                className="pressable rounded-full bg-accent px-6 py-2.5 text-sm font-bold text-bg hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
              >
                {sync?.running ? "Syncing" : "Sync everything"}
              </button>
              {(["espn", "stats", "news"] as SyncTarget[]).map((t) => (
                <button
                  key={t}
                  onClick={() => runSync([t])}
                  disabled={sync?.running || !settings.configured}
                  className="rounded-full bg-surface-raised px-5 py-2.5 text-sm font-semibold text-text-muted transition-colors hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {SYNC_LABELS[t]}
                </button>
              ))}
            </div>

            {sync && (
              <div className="mt-5 flex flex-col gap-2">
                {(["espn", "stats", "news"] as SyncTarget[]).map((t) => {
                  const result = sync.results[t]
                  if (!result && !sync.running) return null
                  return (
                    <div
                      key={t}
                      className="flex items-start gap-3 rounded-xl bg-surface-raised px-4 py-3 text-sm"
                    >
                      <span
                        className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                          !result
                            ? "animate-pulse bg-accent"
                            : result.ok
                              ? "bg-status-good"
                              : "bg-status-bad"
                        }`}
                      />
                      <span className="font-semibold text-text">{SYNC_LABELS[t]}</span>
                      <span className={result?.ok === false ? "text-status-bad" : "text-text-muted"}>
                        {result ? result.detail : "Working…"}
                      </span>
                    </div>
                  )
                })}
                {sync.finished_at && !sync.running && (
                  <p className="text-sm text-text-muted">
                    Done. Head to the{" "}
                    <a href="/" className="font-semibold text-accent hover:underline">
                      dashboard
                  </a>
                  .
                </p>
              )}
            </div>
          )}
          </Card>
        )}
      </div>
    </div>
  )
}
