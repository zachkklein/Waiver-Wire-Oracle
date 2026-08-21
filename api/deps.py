"""Request-scoped dependencies: who is asking, which league they're looking at, and
whose Oracle credentials to run on.

This is the one seam between "self-hosted, one person, ``data/settings.json``" and
"hosted, many accounts, ``user_leagues``". ``auth.py`` decides which of the two a
deployment is; ``store.py`` resolves the contexts accordingly. Nothing below this file —
no router, no tool, no ingest — knows the difference: they receive a ``LeagueCtx`` and a
``UserCtx`` and that's all they've ever needed.

Routers must depend on these rather than calling ``config.load_*_ctx()`` or
``store.load_*_ctx()`` directly, otherwise that seam stops being one file.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

import auth
import store
from auth import LOCAL_PRINCIPAL, AuthError, Principal
from context import LeagueCtx, UserCtx


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def _principal(request: Request, allow_query_token: bool = False) -> Principal:
    if not auth.is_enabled():
        return LOCAL_PRINCIPAL  # self-hosted: there is nobody else to be

    token = _bearer(request)
    if token is None and allow_query_token:
        token = request.query_params.get("access_token")
    if not token:
        raise HTTPException(401, "Sign in to continue.", {"WWW-Authenticate": "Bearer"})

    try:
        return auth.verify_token(token)
    except AuthError as exc:
        raise HTTPException(401, str(exc), {"WWW-Authenticate": "Bearer"}) from exc


def current_principal(request: Request) -> Principal:
    return _principal(request)


def current_principal_from_url(request: Request) -> Principal:
    """As above, but also accepts the token as an ``access_token`` query parameter.

    Strictly for endpoints the browser reaches through an ``<img src>`` — team logos —
    where there is no way to set an Authorization header. Don't reach for it anywhere
    else: a token in a URL ends up in access logs and referrers.
    """
    return _principal(request, allow_query_token=True)


PrincipalDep = Annotated[Principal, Depends(current_principal)]


def current_league(principal: PrincipalDep) -> LeagueCtx:
    return store.load_league_ctx(principal)


def current_league_from_url(
    principal: Annotated[Principal, Depends(current_principal_from_url)],
) -> LeagueCtx:
    return store.load_league_ctx(principal)


def current_user(principal: PrincipalDep) -> UserCtx:
    return store.load_user_ctx(principal)


LeagueDep = Annotated[LeagueCtx, Depends(current_league)]
LeagueFromUrlDep = Annotated[LeagueCtx, Depends(current_league_from_url)]
UserDep = Annotated[UserCtx, Depends(current_user)]
