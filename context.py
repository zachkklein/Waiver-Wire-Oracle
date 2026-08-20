"""Per-request configuration context.

Today there is one league and one OpenRouter key per process, loaded from
``data/settings.json`` by ``config.load_league_ctx()`` / ``config.load_user_ctx()``.
In the hosted multi-user build (see ``docs/HOSTED_PLAN.md``) they instead come from
the signed-in user, resolved per request.

That's the whole point of this module: nothing that reads a league or an API key may
reach for module-global state, because "the active league" stops being a property of
the process the moment two people use the app at once. Callers pass one of these
objects explicitly. ``config.py`` is the only place allowed to build one from local
settings, and it's the seam that Phase 3 swaps for a database lookup.

Both are frozen so a context can't be mutated halfway through a request.
"""

from dataclasses import dataclass

DEFAULT_OPENROUTER_MODEL = "qwen/qwen3.7-flash"


@dataclass(frozen=True)
class LeagueCtx:
    """One ESPN league, plus the credentials needed to reach it.

    ``swid``/``s2`` are only set for private leagues — public ones load fine without
    cookies. ``team_id`` identifies "your" team; it's the only signal available for a
    public league, so it outranks SWID matching in ``find_self_team_id()``.
    """

    league_id: str | None = None
    season: str | None = None
    swid: str | None = None
    s2: str | None = None
    team_id: str | None = None
    label: str | None = None

    @property
    def is_configured(self) -> bool:
        """True once there's enough to sync (a public league needs no cookies)."""
        return bool(self.league_id and self.season)

    @property
    def key(self) -> str:
        """The value that scopes this league's rows in the database.

        ESPN's league id is already globally unique, so it's reused as-is rather than
        minting a synthetic one — which is why several leagues can share one database.
        """
        return str(self.league_id)

    @property
    def espn_cookies(self) -> dict:
        """Cookies for a request to ESPN's own hosts, empty for a public league.

        Never send these anywhere but ``*.espn.com`` — ``espn_s2`` is a session cookie
        for the user's whole ESPN account.
        """
        if self.swid and self.s2:
            return {"espn_s2": self.s2, "SWID": self.swid}
        return {}


@dataclass(frozen=True)
class UserCtx:
    """Whose OpenRouter credentials the agent runs on."""

    openrouter_api_key: str | None = None
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL

    @property
    def has_key(self) -> bool:
        return bool(self.openrouter_api_key)
