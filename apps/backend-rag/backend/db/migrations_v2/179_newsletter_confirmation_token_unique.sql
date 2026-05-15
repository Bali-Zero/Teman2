-- migration 179_newsletter_confirmation_token_unique
-- TODO(#80) defense-in-depth: prevent two newsletter subscribers from
-- accidentally sharing the same confirmation_token. Probability of
-- collision is 1-in-2^256 (secrets.token_urlsafe(32) → 256 bits) — but
-- enforcing it at the schema layer is cheap and protects against
-- "fix later" code mistakes that would let two unconfirmed rows share
-- a token.
--
-- Partial index: only enforce uniqueness when confirmation_token IS NOT
-- NULL, because the confirm flow sets it to NULL after use.

CREATE UNIQUE INDEX IF NOT EXISTS uq_newsletter_confirmation_token
    ON newsletter_subscribers (confirmation_token)
    WHERE confirmation_token IS NOT NULL;

-- === ROLLBACK ===
DROP INDEX IF EXISTS uq_newsletter_confirmation_token;
