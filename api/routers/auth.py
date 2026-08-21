"""Sign-in support for the hosted build.

Only two endpoints, because Supabase Auth does the actual work in the browser: the app
never sees a password or a magic link, only the JWT that comes back.

``GET /api/auth/config`` is deliberately unauthenticated — it's how one frontend build
serves both deployments. Self-hosted, it answers ``{"enabled": false}`` and the app skips
sign-in entirely; hosted, it hands over the project URL and the publishable key (both
public by design) so the browser can talk to Supabase Auth.
"""

from fastapi import APIRouter

import auth as auth_module
import store
from api.deps import PrincipalDep

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/config")
def get_config():
    return auth_module.public_config()


@router.get("/me")
def get_me(principal: PrincipalDep):
    """Who the caller is, and whether they've connected a league yet.

    Also where an account gets its ``users`` row: the frontend calls this once on load
    after a session appears, which is the first moment we know the account exists.
    """
    store.ensure_account(principal)
    return {
        "user_id": principal.user_id,
        "email": principal.email,
        "leagues": len(store.list_leagues(principal)),
    }
