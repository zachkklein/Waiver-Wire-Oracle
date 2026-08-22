"""Encrypting stored credentials at rest.

The database holds three secrets per account: an ESPN ``SWID``, an ``espn_s2`` session
cookie, and optionally an OpenRouter API key. ``espn_s2`` is the one worth designing
around — it is a session cookie for the user's entire ESPN account, not just their
fantasy league, and it is unavoidable for private leagues. This module makes a database
dump (a backup, a leaked snapshot, a provider's disk) useless without a key that lives
only in the application's environment.

**Only the account-backed store is encrypted.** A self-hosted install keeps its league in
``data/settings.json`` in the clear, and deliberately so: the key would have to sit in
``.env`` next to that file, on the same machine, readable by the same user, so the whole
exercise would be theatre. The threat this addresses is a *copy of the database* turning
up somewhere the application's environment did not.

Scheme: **AES-256-GCM**, one random 12-byte nonce per encryption, with the value's
"address" (table, column, user, league) bound in as additional authenticated data. That
AAD is the part worth explaining: without it, anyone who can write to the database could
paste another user's ``espn_s2`` ciphertext into their own row and have the server
faithfully decrypt it and call ESPN with it. Ciphertext is therefore only valid in the
exact row and column it was written to.

Stored form is ``v1.<kid>.<base64url(nonce || ciphertext||tag)>``, where ``kid`` is a
short fingerprint of the key. The fingerprint buys two things: decryption picks the right
key outright instead of trying each one, and :mod:`scripts.encrypt_secrets` can tell
which rows are still on an old key, which is what makes rotation a finite job rather than
a hope.

Configuration is ``SECRET_ENCRYPTION_KEY``: one key, or several separated by commas, in
which case **the first is used for new writes and the rest only decrypt**. Rotating is
therefore: generate a key, prepend it, redeploy, run
``python3 scripts/encrypt_secrets.py``, drop the old key. Generate one with::

    python3 secretbox.py

The app refuses to start with accounts enabled and no key (``api/main.py``), so there is
no mode where a hosted deployment quietly writes plaintext. Values written before this
phase are stored bare, and :func:`unseal` passes anything without the ``v1.`` prefix
through unchanged so an existing database keeps working while the backfill script runs.
"""

import base64
import hashlib
import os
from functools import lru_cache

ENV_VAR = "SECRET_ENCRYPTION_KEY"

VERSION = "v1"
KEY_BYTES = 32  # AES-256
NONCE_BYTES = 12  # GCM's standard nonce size
KID_CHARS = 8


class SecretError(RuntimeError):
    """A credential could not be sealed or unsealed — a misconfiguration, not a bug."""


def generate_key() -> str:
    """A fresh key, in the form ``SECRET_ENCRYPTION_KEY`` expects."""
    return base64.urlsafe_b64encode(os.urandom(KEY_BYTES)).decode()


def _decode_key(text: str) -> bytes:
    try:
        raw = base64.urlsafe_b64decode(_pad(text))
    except Exception as exc:  # noqa: BLE001 - any decode failure is the same user error
        raise SecretError(
            f"{ENV_VAR} is not valid base64. Generate one with: python3 secretbox.py"
        ) from exc
    if len(raw) != KEY_BYTES:
        raise SecretError(
            f"{ENV_VAR} must decode to {KEY_BYTES} bytes, but got {len(raw)}. "
            "Generate one with: python3 secretbox.py"
        )
    return raw


def _pad(text: str) -> str:
    return text + "=" * (-len(text) % 4)


def _kid(key: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(key).digest()).decode()[:KID_CHARS]


@lru_cache(maxsize=4)
def _parse_keys(raw: str) -> tuple:
    """Every configured key as ``(kid, key_bytes)``, primary first.

    Cached on the raw environment string, so this runs once per process rather than on
    every request, and still picks up a change (in tests, mostly) without a restart.
    """
    keys = []
    seen = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        key = _decode_key(part)
        kid = _kid(key)
        if kid in seen:  # the same key listed twice is harmless, just noise
            continue
        seen.add(kid)
        keys.append((kid, key))
    return tuple(keys)


def _keys() -> tuple:
    return _parse_keys(os.getenv(ENV_VAR) or "")


def is_configured() -> bool:
    """True when this deployment can encrypt. Read fresh, like every other setting."""
    return bool(_keys())


def primary_kid() -> str | None:
    """Fingerprint of the key new writes use — what rotation compares against."""
    keys = _keys()
    return keys[0][0] if keys else None


def check_config() -> None:
    """Validate the configured keys at startup, so a typo fails once rather than on the
    first user who tries to save an ESPN cookie."""
    _keys()


def is_sealed(value) -> bool:
    """Whether a stored value is ciphertext, as opposed to a pre-Phase-4 plaintext."""
    return isinstance(value, str) and value.startswith(f"{VERSION}.")


def sealed_kid(value) -> str | None:
    """Which key a stored value was encrypted with, or None if it isn't ciphertext."""
    if not is_sealed(value):
        return None
    parts = value.split(".", 2)
    return parts[1] if len(parts) == 3 else None


def seal(value, *, aad: str) -> str | None:
    """Encrypt a credential for storage, bound to ``aad`` — see the module docstring.

    Empty values stay ``None`` rather than becoming ciphertext for the empty string:
    every caller treats "no secret" and "" the same, and ``has_*`` in the settings
    summary is a plain truthiness check on the stored column.
    """
    if not value:
        return None

    keys = _keys()
    if not keys:
        raise SecretError(
            f"{ENV_VAR} is not set, so this credential can't be encrypted. Generate a "
            "key with `python3 secretbox.py` and set it in the environment."
        )

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    kid, key = keys[0]
    nonce = os.urandom(NONCE_BYTES)
    blob = nonce + AESGCM(key).encrypt(nonce, str(value).encode(), aad.encode())
    payload = base64.urlsafe_b64encode(blob).decode().rstrip("=")
    return f"{VERSION}.{kid}.{payload}"


def unseal(value, *, aad: str) -> str | None:
    """Decrypt a stored credential, or pass a legacy plaintext through unchanged.

    A value that *looks* encrypted but won't decrypt raises rather than returning
    ``None``: the difference between "this user has no ESPN cookie" and "this server
    can't read the one it has" matters, and silently reporting the second as the first
    would send the user off to re-enter credentials that were fine all along.
    """
    if not value:
        return None
    if not is_sealed(value):
        return str(value)  # written before Phase 4; scripts/encrypt_secrets.py fixes it

    _, kid, payload = value.split(".", 2)
    key = dict((k, v) for k, v in _keys()).get(kid)
    if key is None:
        raise SecretError(
            f"A stored credential was encrypted with key '{kid}', which isn't in "
            f"{ENV_VAR}. Add that key back (it may decrypt only — list it after the "
            "primary one), or clear the credential and have the user re-enter it."
        )

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    try:
        blob = base64.urlsafe_b64decode(_pad(payload))
        plaintext = AESGCM(key).decrypt(blob[:NONCE_BYTES], blob[NONCE_BYTES:], aad.encode())
    except Exception as exc:  # noqa: BLE001 - GCM gives one answer: it didn't verify
        raise SecretError(
            f"A stored credential failed to decrypt (key '{kid}'). Either it was "
            "tampered with, or it was moved from the row it was encrypted for."
        ) from exc
    return plaintext.decode()


if __name__ == "__main__":
    print(generate_key())
