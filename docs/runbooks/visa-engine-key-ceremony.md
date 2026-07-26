# Visa Engine — Ed25519 Key Ceremony (2026-07-19)

## What

Two Ed25519 signing keypairs were minted for RulePack signing (spec §3,
`apps/backend-rag/backend/services/visa_engine/bundle.py`). The runtime NEVER
reads a private key — it only pins **public** keys via the environment
variable `VISA_ENGINE_TRUST_STORE_KEYS_JSON`, loaded through
`StaticTrustStore.from_env`. `bundle.py` ships no `sign_pack.py` script by
design (FIREBREAK — see `bundle.py` module docstring): key generation and
signing happen only in the offline environment, never in autonomous code.

## Keys (public)

| kid              | environment | public_key (base64url raw)                    | sha256 fp (first 16) | valid_from             |
| ---------------- | ----------- | --------------------------------------------- | -------------------- | ---------------------- |
| `2026-07-test-1` | TEST        | `hPwtyP1ekdj_n-BK4M97dyWnRxW1RJ-uGcnVsX5buHM` | `254a379f37c2c486`   | `2026-07-19T00:00:00Z` |
| `2026-07-prod-1` | PRODUCTION  | `gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA` | `ccfe7538608881f1`   | `2026-07-19T00:00:00Z` |

All values above are public (public keys, fingerprints, custody locations) —
no secret material is recorded in this file or anywhere in the repo.

## Private-key custody

PKCS8 PEM files, `chmod 0600`, containing directory `chmod 0700`, at:

```
~/.config/nuzantara/visa-signing/<kid>.ed25519.pem
```

on **M5** (`Air-M5`, user `balizero`) **only**. Not in Keychain, not on
Pro/Mini, never committed to the repo, never pasted into transcripts or logs
(cicatrix family #4 — Secret in the clear). Off-machine backup: AES-256
encrypted dmg at `gdrive:nuzantara-backups/visa-signing/visa-signing-backup-2026-07-19.dmg`
(139776 bytes, uploaded 2026-07-19 via Pro rclone; passphrase held by the
operator only). Local Desktop copy removed after verified upload.

## Trust-store JSON (verbatim, public)

The exact JSON array staged as the `VISA_ENGINE_TRUST_STORE_KEYS_JSON`
secret value — reconstructed from the table above, `valid_to` and
`revoked_at` both `null` for both entries:

```json
[
  {
    "kid": "2026-07-test-1",
    "public_key": "hPwtyP1ekdj_n-BK4M97dyWnRxW1RJ-uGcnVsX5buHM",
    "environment": "TEST",
    "valid_from": "2026-07-19T00:00:00Z",
    "valid_to": null,
    "revoked_at": null
  },
  {
    "kid": "2026-07-prod-1",
    "public_key": "gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA",
    "environment": "PRODUCTION",
    "valid_from": "2026-07-19T00:00:00Z",
    "valid_to": null,
    "revoked_at": null
  }
]
```

## Armed state

Staged as a Fly secret named `VISA_ENGINE_TRUST_STORE_KEYS_JSON` on app
`nuzantara-rag` — digest `a68f076bc9993f0c`, status **Staged** (activates on
the next deploy). No consumer reads this env var yet — it stays inert until
the SHADOW wiring stage of the visa-engine strangler plan lands.

## ERRATA (2026-07-25, first real signing — kid pattern bug + fix)

**Bug:** the ceremony minted kids `2026-07-test-1` / `2026-07-prod-1`, but the
engine's own `IDENTIFIER_PATTERN` (`models.py:90`, `^[A-Za-z][A-Za-z0-9_.:-]{0,127}$`)
requires kids to **start with a letter**. A `ProtectedHeader` built with a
digit-start kid fails model validation, so `sign_pack.py` rejected
`--kid 2026-07-prod-1` at the first real signing. The ceremony's roundtrip
checks verified `StaticTrustStore.from_env` resolution (which does NOT
pattern-validate kids — `TrustedSigningKey.key_id` is a plain `str`), so the
mismatch only surfaced at first use.

**Fix (executed, 2026-07-25):** the kids are RELABELED, same key material:

| old kid (broken) | new kid          | public_key (unchanged)                        |
| ---------------- | ---------------- | --------------------------------------------- |
| `2026-07-test-1` | `test-2026-07-1` | `hPwtyP1ekdj_n-BK4M97dyWnRxW1RJ-uGcnVsX5buHM` |
| `2026-07-prod-1` | `prod-2026-07-1` | `gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA` |

- The Fly secret `VISA_ENGINE_TRUST_STORE_KEYS_JSON` was re-staged with the
  relabeled array — new digest **`ab319439ecf92a0f`** (supersedes
  `a68f076bc9993f0c` above).
- Private-key custody filenames on M5 keep the old names; `--kid` and
  `--key-file` are independent arguments.
- First real pack signed with `prod-2026-07-1` and **verified against the
  relabeled trust store** (`VerifiedRulePack`).
- Lesson for future ceremonies: mint kids matching the engine's
  `IDENTIFIER_PATTERN` at birth (start with a letter).

## Ceremony verification performed (2026-07-19, M5 session)

Real-code roundtrip via `StaticTrustStore.from_env`:

- Both `kid`s resolved from the JSON array above.
- Signatures produced with the real private keys verified successfully
  against the pinned public keys.
- Tampered-message probes **REJECTED**.
- Environment-scope probes (e.g. asking the TEST or PROD key to speak for a
  STAGING environment) **REJECTED**.

## Rotation

1. Mint a new kid (e.g. `2027-01-prod-1`) with the same procedure.
2. Append its entry to the JSON array.
3. Set `valid_to` on the entry being superseded.
4. Re-stage the `VISA_ENGINE_TRUST_STORE_KEYS_JSON` Fly secret.
5. Deploy.

## Revocation (emergency)

1. Set `revoked_at` on the compromised entry — this takes effect immediately
   per `StaticTrustStore`'s revocation semantics (inclusive check).
2. Re-stage the secret.
3. Deploy.
4. Re-sign any affected RulePacks with a fresh key.

## FIREBREAK reminder

- No `sign_pack.py` ships in this repo. Signing only happens in the offline
  environment (M5) during RulePack authoring.
- Test suites use ephemeral, in-fixture Ed25519 keys — never the keys
  described in this document.
- Runtime code path (`bundle.py`) never opens a private-key file; it only
  ever sees public keys via `StaticTrustStore.from_env`.
