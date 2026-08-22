-- Phase 4: the *_enc columns now hold ciphertext (docs/HOSTED_PLAN.md).
--
-- No schema change -- the columns were always TEXT and always named for this. What
-- changes is that the Phase 2 migration's note ("nothing writes them yet") is no longer
-- true, and anyone reading this schema straight from the database deserves to know that
-- the contents are AES-256-GCM ciphertext rather than a cookie they can use, and that
-- the key is not in here.

COMMENT ON COLUMN user_leagues.espn_swid_enc IS
    'AES-256-GCM ciphertext (secretbox.py), keyed by SECRET_ENCRYPTION_KEY in the '
    'application environment. Bound to (user_id, league_id, column) as additional '
    'authenticated data, so it will not decrypt in any other row.';

COMMENT ON COLUMN user_leagues.espn_s2_enc IS
    'AES-256-GCM ciphertext (secretbox.py) of the ESPN session cookie -- a credential '
    'for the user''s whole ESPN account, not just this league. Bound to '
    '(user_id, league_id, column); the key lives only in the application environment.';

COMMENT ON COLUMN user_settings.openrouter_key_enc IS
    'AES-256-GCM ciphertext (secretbox.py) of the user''s own OpenRouter API key. '
    'Bound to (user_id, column); the key lives only in the application environment.';
