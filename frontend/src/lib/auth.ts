import { createClient, type SupabaseClient } from "@supabase/supabase-js"
import type { AuthConfig } from "./types"

/** Sign-in, when this deployment has accounts.
 *
 * There is one build of this app for two very different deployments, so it can't be
 * decided at build time: `GET /api/auth/config` answers `{enabled: false}` on a
 * self-hosted install (no sign-in screen, every request unauthenticated) and hands over
 * the Supabase project URL and publishable key on the hosted one. Both of those values
 * are public by design — they're what the browser needs to talk to Supabase Auth.
 *
 * Supabase owns the session: it lives in localStorage, refreshes itself, and is picked
 * up out of the URL when a magic link lands back on the page. All this module does is
 * make the current access token reachable from `api.ts`.
 */

let client: SupabaseClient | null = null
let config: AuthConfig = { enabled: false, url: null, publishable_key: null }

/** The most recent access token, cached for the one caller that can't await: image
 * URLs (see `teamLogoUrl`). Everything else goes through `authHeaders()`. */
let cachedToken: string | null = null

export function supabase(): SupabaseClient | null {
  return client
}

export function authEnabled(): boolean {
  return config.enabled
}

export function cachedAccessToken(): string | null {
  return cachedToken
}

export function rememberAccessToken(token: string | null) {
  cachedToken = token
}

let configPromise: Promise<AuthConfig> | null = null

/** Ask the server whether this deployment has accounts, and build the client if so.
 * Memoised — every caller shares one request and one client. */
export function loadAuthConfig(): Promise<AuthConfig> {
  if (!configPromise) {
    configPromise = fetch("/api/auth/config")
      .then((res) => (res.ok ? res.json() : { enabled: false, url: null, publishable_key: null }))
      .then((cfg: AuthConfig) => {
        config = cfg
        if (cfg.enabled && cfg.url && cfg.publishable_key && !client) {
          client = createClient(cfg.url, cfg.publishable_key)
        }
        return cfg
      })
      .catch(() => config)
  }
  return configPromise
}

/** The Authorization header for an API call, or nothing when there are no accounts.
 *
 * Reads the session rather than the cached token so supabase-js can refresh an expired
 * one first — the alternative is a request that 401s a few times an hour for no reason
 * the user could act on. */
export async function authHeaders(): Promise<Record<string, string>> {
  if (!client) return {}
  const { data } = await client.auth.getSession()
  const token = data.session?.access_token ?? null
  cachedToken = token
  return token ? { Authorization: `Bearer ${token}` } : {}
}
