"""Who is making the request.

There are two modes, decided by whether Supabase Auth is configured in the environment:

* **Self-hosted (the default).** ``SUPABASE_URL``/``SUPABASE_PUBLISHABLE_KEY`` are unset,
  so there is no sign-in and every request runs as :data:`LOCAL_PRINCIPAL` — one person,
  whose league lives in ``data/settings.json``. ``git clone && main.py serve`` still needs
  no external services, which is the whole point of keeping this optional.
* **Hosted.** Supabase Auth issues a JWT per signed-in account. :func:`verify_token`
  checks it and yields that account's id, which ``store.py`` turns into *that user's*
  leagues. Nothing else in the app knows auth exists.

One frontend build serves both: it asks ``GET /api/auth/config`` whether to show a
sign-in screen at all.

**Supabase's current key system only — no legacy keys anywhere.** Two consequences worth
stating, because they're the reason the code is this short:

1. Tokens are verified against the project's **JWT Signing Keys** (asymmetric, ES256 or
   RS256) fetched from its public JWKS endpoint. There is deliberately no support for the
   legacy shared HS256 "JWT secret": a shared secret would have to sit in this process's
   environment, and anything that can *verify* with it can also *mint* tokens. With
   asymmetric keys the server holds only a public key and cannot forge a session.
2. The only Supabase key this app ever holds is the **publishable** key, which is public
   by design and is served straight to the browser. There is no secret (service-role) key
   here at all — the backend reaches the database over ``DATABASE_URL`` as the table
   owner and never touches the PostgREST API, so it has nothing to authenticate to.
"""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Principal:
    """The account a request runs as.

    ``user_id`` is ``None`` in self-hosted mode, and that is not a degenerate case to
    guard against everywhere — it's the ordinary single-user install. ``store.py`` is the
    only module that branches on it.
    """

    user_id: str | None = None
    email: str | None = None

    @property
    def is_account(self) -> bool:
        return self.user_id is not None


# The implicit "user" of a self-hosted install. Every CLI entrypoint runs as this.
LOCAL_PRINCIPAL = Principal()

AUDIENCE = "authenticated"

# Only asymmetric algorithms. Adding HS256 here would reintroduce the shared-secret model
# this deployment deliberately doesn't use -- see the module docstring.
ALGORITHMS = ["ES256", "RS256"]


def supabase_url() -> str | None:
    return (os.getenv("SUPABASE_URL") or "").rstrip("/") or None


def supabase_publishable_key() -> str | None:
    """The publishable key (``sb_publishable_...``). Public by design — it ships in the
    browser bundle, and the browser can do nothing with it that RLS doesn't already
    allow. ``SUPABASE_ANON_KEY`` is read as a fallback purely so an older ``.env``
    doesn't silently turn accounts off; see :func:`check_config`."""
    return os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or None


def is_enabled() -> bool:
    """True when this deployment has accounts. Read fresh so tests can toggle it."""
    return bool(supabase_url() and supabase_publishable_key())


def check_config() -> None:
    """Fail at startup on a legacy key, rather than per request on something subtler.

    The legacy ``anon`` key is itself a JWT, so it's recognisable on sight: it's a
    long ``eyJ...`` string rather than ``sb_publishable_...``. It would still *work*,
    which is exactly why it's worth rejecting loudly — otherwise a deployment quietly
    stays on the key system we've moved off, and rotating it stays all-or-nothing.
    """
    key = supabase_publishable_key()
    if key and key.startswith("eyJ"):
        raise RuntimeError(
            "SUPABASE_PUBLISHABLE_KEY looks like the legacy anon key (a JWT starting "
            "'eyJ'). This app uses Supabase's current key system: copy the key named "
            "'publishable' (it starts with 'sb_publishable_') from Project Settings -> "
            "API Keys."
        )

    if os.getenv("SUPABASE_JWT_SECRET"):
        raise RuntimeError(
            "SUPABASE_JWT_SECRET is set, but this app verifies tokens against the "
            "project's JWT Signing Keys (asymmetric) and never with a shared secret — "
            "a secret that can verify a token can also mint one. Remove it, and make "
            "sure Authentication -> JWT Keys has a current signing key."
        )


def public_config() -> dict:
    """What the browser needs to sign in — safe to serve unauthenticated."""
    return {
        "enabled": is_enabled(),
        "url": supabase_url(),
        "publishable_key": supabase_publishable_key(),
    }


class AuthError(Exception):
    """The token was missing, malformed, expired, or signed by someone else."""


@lru_cache(maxsize=4)
def _jwks_client(url: str):
    # Caches keys in-process and refetches on an unknown `kid`, so rotating the project's
    # signing key heals itself without a redeploy — which is the point of having the
    # signing key be rotatable separately from the publishable key in the first place.
    import jwt

    return jwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json")


def verify_token(token: str) -> Principal:
    """Verify a Supabase access token and return the account it identifies."""
    import jwt

    url = supabase_url()
    if not url:
        raise AuthError("Auth is not configured on this server.")

    try:
        key = _jwks_client(url).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
            issuer=f"{url}/auth/v1",
        )
    except Exception as exc:
        raise AuthError(f"Could not verify token: {exc}") from exc

    user_id = claims.get("sub")
    if not user_id:
        raise AuthError("Token has no subject.")

    return Principal(user_id=str(user_id), email=claims.get("email"))
