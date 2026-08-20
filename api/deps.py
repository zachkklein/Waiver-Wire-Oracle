"""Request-scoped dependencies.

Today both contexts come from local settings, so every request resolves the same
league — this app is still single-user. The point of funnelling them through here is
that the hosted build (``docs/HOSTED_PLAN.md``, Phase 3) only has to change these two
functions: the league comes from the request's ``user_leagues`` row and the key from
the signed-in user, and no router or tool below changes at all.

Routers must depend on these rather than calling ``config.load_*_ctx()`` directly,
otherwise that swap stops being a one-file change.
"""

from typing import Annotated

from fastapi import Depends

import config
from context import LeagueCtx, UserCtx


def current_league() -> LeagueCtx:
    return config.load_league_ctx()


def current_user() -> UserCtx:
    return config.load_user_ctx()


LeagueDep = Annotated[LeagueCtx, Depends(current_league)]
UserDep = Annotated[UserCtx, Depends(current_user)]
