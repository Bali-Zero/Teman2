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
secret value since the 2026-07-25 relabel (ERRATA below, digest
`ab319439ecf92a0f`) — the key material of the table above under the
relabeled kids, `valid_to` and `revoked_at` both `null` for both entries.
Every signed production pack's protected header carries
`kid: prod-2026-07-1`; an array still naming the minted `2026-07-prod-1`
rejects them all with `unknown signing key_id`:

```json
[
  {
    "kid": "test-2026-07-1",
    "public_key": "hPwtyP1ekdj_n-BK4M97dyWnRxW1RJ-uGcnVsX5buHM",
    "environment": "TEST",
    "valid_from": "2026-07-19T00:00:00Z",
    "valid_to": null,
    "revoked_at": null
  },
  {
    "kid": "prod-2026-07-1",
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

## Signing note (2026-09-27, seq-24)

`rulepack-prod-024.signed.json` (E33F: a retiree without a confirmed sponsor
becomes a candidate) was signed offline on M5 with the same production key,
`kid: prod-2026-07-1`, `signed_at` 2026-09-27T01:31:02Z, `payload_sha256`
`5a569091f84a858f1957cdf96086ee7212f67d13a8225d64492a7212093cd272`, chained
to the signed seq-23 (`previous_payload_sha256`
`e5f791b5232fd1369ef3b94ca7bb5f349f9bb6eb4073895aa9f7deb682e72204`). It was
checked on landing with `verify_rule_pack` against the PRODUCTION entry of the
array above, before and after Prettier (the signature covers the JCS-canonical
payload, so the file's formatting does not matter). **Signed, not activated.**
The standing regression is
`test_seq24_pack.py::TestSignedBundleTiesToSource`.

## Signing + activation note (2026-10-07, seq-25 — and seq-24's deferred activation)

`rulepack-prod-025.signed.json` (the 18 `OFFICIAL_PORTAL` sources re-stamped from
the 2026-10-07 read ledger, `research/visa/2026-10-07-freshness-restamp-seq25/`;
rules and products byte-identical to seq-24) was signed offline on M5 with the
production key, `kid: prod-2026-07-1`, `signed_at` 2026-10-07T13:39:07Z,
`payload_sha256`
`603f777e5fdd8ffbd5824282593b6584893f39b0b6b192f59c4563ae6d9c9d11`, chained to the
signed seq-24 (`5a569091f84a858f1957cdf96086ee7212f67d13a8225d64492a7212093cd272`).
Digest re-verified unchanged after Prettier.

**Activated the same day, two activations in order** (the anti-rollback gate anchors
`previous_payload_sha256` on the pack active at that instant, so seq-24 had to go
first): seq-24 `activation_id e1e01743-b290-4dee-9c45-08218e58a228` (reason
`seq24-e33f-penjamin-261007`), then seq-25 `activation_id
d2752a16-cd3f-46f0-81f0-fe32dcc43c05` (reason `seq25-portal-restamp-261007`), actor
`consul-session-m5`, 13:49Z. Exactly one open activation afterwards (seq-25).

Ceremony mechanics measured this run, where they differ from the 2026-09-06 notes:

- The PG primary is now machine `5683e090f3d228` (`fly machines list -a
nuzantara-postgres` → ROLE primary); `0801696b541568`, named in every earlier
  entry, is STOPPED. Target the primary explicitly:
  `flyctl proxy 15433:5433 <primary>.vm.nuzantara-postgres.internal -a nuzantara-postgres`
  on Pro (the only host with Fly auth), then `ssh -N -L 15433:127.0.0.1:15433 pro`
  from M5. Check `pg_is_in_recovery()` is `f` before minting anything.
- `~/.config/nuzantara/visa-signing/activation-operator-password` is NOT the
  superuser password — it belongs to the persistent login role
  `visa_activation_operator`. The superuser (`postgres`) password is the machine's
  `OPERATOR_PASSWORD`: fetch it machine-side on Pro into a 0600 file
  (`flyctl ssh console -a nuzantara-postgres --machine <primary> -C "printenv
OPERATOR_PASSWORD" > ~/.tmp/visa-ceremony/su.pw`), read it into a shell variable,
  delete the file at cleanup. Never print it.
- Ephemeral logins `visa_pack_writer_ceremony_<yymmdd>` (`IN ROLE visa_pack_writer`)
  and `visa_activation_ceremony_<yymmdd>` (`IN ROLE visa_activation_executor`),
  `VALID UNTIL` +3h, `GRANT CONNECT` each; cleanup = `REVOKE CONNECT` then `DROP
ROLE`, then `select count(*) from pg_roles where rolname like 'visa_%_ceremony_%'`
  must read 0.
- While Pro's `flyctl proxy` was open, M5's own read-only tunnel
  (`com.nuzantara.fly-pg-tunnel`, :15432) died "during handshake" and respawned by
  itself ~30 s after the ceremony proxy closed (two WireGuard proxies on one
  account). Expect `scripts/pg.sh` on M5 to be unavailable for the ceremony's
  duration; verify through the sentinel on Pro or after the respawn.

## Signing + activation note (2026-10-08, seq-26)

`rulepack-prod-026.signed.json` (seq-25 plus `duration_options` on E31A–E31J; stamps
unchanged) was signed offline on M5, `kid: prod-2026-07-1`, `signed_at`
2026-10-08T08:58:04Z, `payload_sha256`
`05511184caf05119ac0adf644601e322d845c276faad3146ea243c507cf23b7f`, version `2026.10.8`,
`rule_pack_id 16cdbc81-c9b0-5475-b7cf-63f642c140b5`, chained to the signed seq-25
(`603f777e…9d11`). Activation is the same two-login ceremony as above on the PG primary
`5683e090f3d228`, run from Pro: `activation_id` `<ACTIVATION_ID>` at `<ACTIVATED_AT>`.

Gotchas measured this run:

- GitHub answered HTTP 499 to `enablePullRequestAutoMerge` for minutes; arm in a retry loop
  with a pause, do not conclude the PR cannot be armed.
- `merge=union` on `PENDING-ARMS.md` turns an edit of an existing row into a silent
  duplicate (the old and the new line both survive); fold the row by hand after the merge.
- A fresh gate compares a receipt `ts` with the commit dates: a receipt typed after its
  commit is a BLOCK. Capture the timestamp with `date -u` at the moment of the read.

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

- `sign_pack.py` DOES ship in this repo, at
  `apps/backend-rag/backend/scripts/visa_engine/sign_pack.py`. What does not
  ship is any private key, and what never happens is signing from inside a
  server process: the script is an offline operator CLI, run by hand on M5
  during RulePack authoring, and nothing in `backend/services/` imports it.
  (This line used to read "No `sign_pack.py` ships in this repo", which is
  false and cost a signing session real time in 2026-09-15's seq-21 ceremony
  — the operator went looking for a script the runbook said was absent.)
- Test suites use ephemeral, in-fixture Ed25519 keys — never the keys
  described in this document.
- Runtime code path (`bundle.py`) never opens a private-key file; it only
  ever sees public keys via `StaticTrustStore.from_env`.
