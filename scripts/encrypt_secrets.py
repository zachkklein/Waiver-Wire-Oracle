"""Encrypt stored credentials that aren't yet, and re-encrypt any on an old key.

    SECRET_ENCRYPTION_KEY=... python3 scripts/encrypt_secrets.py [--dry-run]

Two jobs, which are the same job:

* **Backfill.** Rows written before Phase 4 hold plaintext ESPN cookies and OpenRouter
  keys. Run this once after setting ``SECRET_ENCRYPTION_KEY`` and the database stops
  containing any.
* **Rotation.** Put a new key first in ``SECRET_ENCRYPTION_KEY``, keep the old one after
  it, redeploy, run this, then drop the old key. Every value is re-encrypted under the
  new one; the key fingerprint stored with each value is what makes "is anything still on
  the old key?" a question with an answer.

Idempotent — a second run finds nothing to do. Safe to run against a live database: each
row is updated in its own statement, and the application decrypts old and new forms
alike, so there is no window where a user's cookies stop working.

Never prints a credential; only counts and row addresses.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
import secretbox
import store

# The AAD builders come from store.py rather than being restated here. They have to agree
# exactly — a mismatched address produces ciphertext the app can't decrypt — so there is
# one definition of them, in the module that reads and writes these columns.
LEAGUE_COLUMNS = ("espn_swid_enc", "espn_s2_enc")


def _needs_work(value) -> bool:
    """True for a plaintext value, or one encrypted under a non-primary key."""
    if not value:
        return False
    return secretbox.sealed_kid(value) != secretbox.primary_kid()


def _describe(value) -> str:
    if not secretbox.is_sealed(value):
        return "plaintext"
    return f"key {secretbox.sealed_kid(value)}"


def _rewrite(conn, table: str, column: str, aad: str, value, where: dict, dry_run: bool):
    plaintext = secretbox.unseal(value, aad=aad)
    if dry_run:
        return
    conditions = " AND ".join(f"{c} = ?" for c in where)
    conn.execute(
        # table/column are this module's own constants, never user input.
        f"UPDATE {table} SET {column} = ? WHERE {conditions}",
        (secretbox.seal(plaintext, aad=aad), *where.values()),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would change, write nothing"
    )
    args = parser.parse_args()

    if not secretbox.is_configured():
        raise SystemExit(
            f"{secretbox.ENV_VAR} is not set — there is no key to encrypt with. "
            "Generate one with: python3 secretbox.py"
        )
    print(f"Encrypting with key {secretbox.primary_kid()}.")

    done = 0
    with db.session(commit=not args.dry_run) as conn:
        tables = db.table_names(conn)
        missing = {"user_leagues", "user_settings"} - tables
        if missing:
            raise SystemExit(
                f"No {', '.join(sorted(missing))} table in this database — accounts live "
                "in Postgres (apply supabase/migrations, and set DATABASE_URL)."
            )

        leagues = conn.execute(
            "SELECT user_id, league_id, espn_swid_enc, espn_s2_enc FROM user_leagues"
        ).fetchall()
        for row in leagues:
            for column in LEAGUE_COLUMNS:
                if not _needs_work(row[column]):
                    continue
                print(f"  user_leagues {row['user_id']} / {row['league_id']} "
                      f"{column}: {_describe(row[column])} -> {secretbox.primary_kid()}")
                _rewrite(
                    conn,
                    "user_leagues",
                    column,
                    store._league_aad(row["user_id"], row["league_id"], column),
                    row[column],
                    {"user_id": row["user_id"], "league_id": row["league_id"]},
                    args.dry_run,
                )
                done += 1

        settings = conn.execute(
            "SELECT user_id, openrouter_key_enc FROM user_settings"
        ).fetchall()
        for row in settings:
            value = row["openrouter_key_enc"]
            if not _needs_work(value):
                continue
            print(f"  user_settings {row['user_id']} openrouter_key_enc: "
                  f"{_describe(value)} -> {secretbox.primary_kid()}")
            _rewrite(
                conn,
                "user_settings",
                "openrouter_key_enc",
                store._user_aad(row["user_id"]),
                value,
                {"user_id": row["user_id"]},
                args.dry_run,
            )
            done += 1

    scanned = len(leagues) * len(LEAGUE_COLUMNS) + len(settings)
    verb = "would re-encrypt" if args.dry_run else "re-encrypted"
    print(f"{verb} {done} of {scanned} credential slots; the rest were already current.")


if __name__ == "__main__":
    main()
