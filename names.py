"""Player-name normalisation, for linking ESPN players to nflverse stats.

ESPN and nflverse spell the same player differently often enough to matter: ESPN keeps
generational suffixes and drops punctuation ("Aaron Jones Sr.", "DJ Moore",
"De'Von Achane") where nflverse does the opposite ("Aaron Jones", "D.J. Moore",
"Devon Achane"). Eleven players on a single 162-row league had full stat histories the
app could not see because of it.

This runs **once at ingest**, to populate ``players.normalized_name`` and resolve a
``gsis_id`` — not per query. That is the point: a link that fails is then a row with a
NULL gsis_id you can count, rather than a query that silently returns nothing.

Keep this stable. Changing the rules changes what links to what, so a change needs a
re-run of the linking step (``stats_sync.link_players()``) to take effect.
"""

import re

# Trailing generational suffixes. ESPN includes them, nflverse usually doesn't.
_SUFFIX = re.compile(r"\s+(jr|sr|ii|iii|iv|v)\.?$")
_NON_ALNUM = re.compile(r"[^a-z0-9]")


def normalize_player_name(name: str | None) -> str:
    """A comparison key for a player's name.

    Lowercased, trailing suffix removed, then everything but letters and digits
    stripped — which collapses the punctuation and spacing differences too:

        "Aaron Jones Sr."  -> "aaronjones"
        "Aaron Jones"      -> "aaronjones"
        "D.J. Moore"       -> "djmoore"
        "DJ Moore"         -> "djmoore"
        "De'Von Achane"    -> "devonachane"

    Deliberately lossy, so it is only ever safe as a *candidate* match — callers must
    require the match to be unambiguous on both sides before trusting it.
    """
    if not name:
        return ""
    return _NON_ALNUM.sub("", _SUFFIX.sub("", name.strip().lower()))
