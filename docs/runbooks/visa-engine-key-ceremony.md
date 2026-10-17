# Visa Engine — Ed25519 Key Ceremony (2026-07-19)

## What

Two Ed25519 signing keypairs were minted for RulePack signing (spec §3,
`apps/backend-rag/backend/services/visa_engine/bundle.py`). The runtime NEVER
reads a private key — it only pins **public** keys via the environment
variable `VISA_ENGINE_TRUST_STORE_KEYS_JSON`, loaded through
`StaticTrustStore.from_env`. `bundle.py` itself ships no signing code by design (FIREBREAK — see
`bundle.py` module docstring); the offline operator CLI `sign_pack.py` lives
under `backend/scripts/visa_engine/` (see the FIREBREAK reminder below). Key
generation and signing happen only in the offline environment, never in
autonomous code.

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
`5683e090f3d228`, run from Pro: `activation_id` `1c7ac00b-7c5e-44e9-8efc-392d03fb47ef` at `2026-10-08T10:08:02Z`.

Prove-live (2026-10-08): POST /api/visa-oracle/evaluate with the E31 spouse persona + intent.stay_days → pack 26, E31A duration_options [(365, 11.000.000), (730, 15.000.000)]; 365 → 365, 730 → 730, 1095 → 730 + extension_required; Fly build f43d4ac0a0.

Gotchas measured this run:

- GitHub answered HTTP 499 to `enablePullRequestAutoMerge` for minutes; arm in a retry loop
  with a pause, do not conclude the PR cannot be armed.
- `merge=union` on `PENDING-ARMS.md` turns an edit of an existing row into a silent
  duplicate (the old and the new line both survive); fold the row by hand after the merge.
- A fresh gate compares a receipt `ts` with the commit dates: a receipt typed after its
  commit is a BLOCK. Capture the timestamp with `date -u` at the moment of the read.

## Signing + activation note (2026-10-10, seq-27)

`rulepack-prod-027.source.json` is the weekly re-attestation organ's candidate (organ PR #8105, head `a2ceaeeef8`; the same payload under JCS, the file Prettier-formatted as the pre-commit hook requires, which does not move the digest). Its read ledger is
`research/visa/2026-10-08-organ-reattest-seq27/` (without a second copy of the candidate file): the 18 `OFFICIAL_PORTAL` sources of the signed
seq-26 re-stamped to `2026-10-08T13:21:22Z` (verified_by `organ-sonnet-20261008`), chained to
seq-26 (`05511184…3b7f`), version `2026.10.8`, `rule_pack_id b0fd0791-98c5-5132-8905-8985c6ed4803`,
`payload_sha256` `a9098744e0cd8369fb4fe9ca5bef851705cf43dabb1c69398b63b36985cb42d0`. Rules,
products (every E31A–J `duration_options`) and the 10 non-portal records are byte-identical to
seq-26. The new freshness boundary is `2026-11-09T13:21:22Z` (32 days), against seq-26's
`2026-11-08T13:32:18Z`.

All 18 judgements are `judge: fingerprint`: the visible-text fingerprint of each page equals the
attested read of 2026-10-07 (`no model consulted`). No model read the pages; the session that signs
this pack does its own adversarial check, recorded in the evidence pack. The generic fold re-run
from the ledger reproduces the source byte for byte (`TestLedger` in `test_seq27_pack.py`).

Signing and activation follow the seq-26 recipe above (`sign_pack` with `--kid prod-2026-07-1
--environment PRODUCTION --sequence 27 --i-know-this-is-production`, key file
`~/.config/nuzantara/visa-signing/2026-07-prod-1.ed25519.pem` on M5; then the two-login activation
on the PG primary via `activate_pack`). Signed offline on M5 on 2026-10-10 (`signed_at`
2026-10-10T03:42:26Z); the bundle landed in the same PR as the source, so `TestSignedBundleTiesToSource`
and `scripts/ci/observe_visa_seq27_signed.py` were green when seq-27 merged; the observer was retired
on 2026-10-12 because seq-28 superseded seq-27, and `scripts/ci/observe_visa_seq28_signed.py` replaces it. The council seat that ran on
the default Codex account model (`gpt-6-astra`) is recorded under that name and kept out of the quorum;
`codex exec` from `~/.codex` needs an explicit `-m gpt-5.6-sol` to sit the titolare seat.

## Signing + activation note (2026-10-11, seq-28)

`rulepack-prod-028.signed.json` is the weekly re-attestation organ's re-stamp of seq-27 plus four
owner-decided content edits, signed in ONE signing. Read ledger:
`research/visa/2026-10-11-organ-reattest-seq28/` (organ PR #8289, head `0e56a429a1`, superseded by
this PR). The organ's pure candidate (the 18 `OFFICIAL_PORTAL` stamps moved to
`2026-10-11T18:00:16Z`, verified_by `organ-sonnet-20261011`, nothing else) has JCS digest
`6db76810d95a927646c37c6513055ac24e7033df5a0a138cc02d907ab99766fb`; the generic fold on the ledger
reproduced it byte for byte before the content edits were applied. Signed offline on M5 by the owning
session `nuzantara-57`, `kid: prod-2026-07-1`, `signed_at` 2026-10-11T22:53:04Z (the value inside the
bundle), `sign_pack` self-verified, version `2026.10.11`, `rule_pack_id
b383effb-eea4-5890-9a6a-0f13d816e855`, `payload_sha256`
`a23a5bf55a77a658aef4ff06637cdb6fea476c5569d3d47a56896af2b8557046`, chained to the signed seq-27
(`previous_payload_sha256` `a9098744e0cd8369fb4fe9ca5bef851705cf43dabb1c69398b63b36985cb42d0`),
sequence 27 to 28, `rollback_of_payload_sha256` null. Rules 113 to 114.

The four content items (owner decisions, Zero, 2026-10-11):

1. The organ re-stamp of the 18 portal sources (pure candidate above).
2. E33E carries its own 5-year price key `E33E Second Home Senior (5 Years)` (IDR 45,000,000,
   one price, stay fixed at 1825 days) instead of `Retirement (Offshore)`.
3. `AGE_BELOW_55` on E33E/E33F is scoped to the RETIREMENT purpose (`hf.e33e.age-below-55`,
   `hf.e33f.age-below-55` modified).
4. E33G requires `work.annual_foreign_income_usd >= 60000` (`el.e33g.remote-work` modified) and a
   new hard filter `hf.e33g.annual-income-below-minimum` excludes REMOTE_WORK below USD 60,000 with
   `on_unknown: NO_EFFECT` (Pasal 63(2) of Permenkumham 22/2023, "paling sedikit US$60.000 per tahun").

New earliest portal freshness boundary: `2026-11-12T18:00:16Z` (stamp + 32 days), against seq-27's
`2026-11-09T13:21:22Z`. Seq-29 is due before it; the organ alerts at T-7.

Pre-signing review, none of it the organ or the build lane: the W141 check (18/18 fingerprints
recomputed, 18/18 live re-read HTTP 200 and equal; 17 `judge: fingerprint` rows plus 1 model-judged
row, the Bridging page `3da72c7b`, which the signing session read itself), the independent adversary
(persona walk on the folded source, no blocking defect), and the two-titolare council, both `SIGN`:
codex `gpt-5.6-sol` (rollout `01a12c37-3f73-76a0-8cff-c14c82f4067f`) and kimi `k3` (session
`session_f95638dc-ca65-48e9-bdc5-c3c44a91dbd9`). Detail and receipts:
`evidence/2026-10/agent-mini-pro2-backend-rag-vo-seq28c-fold-1011-c669824d/` and the attestation
`research/visa/2026-10-11-organ-reattest-seq28-attestation.md`. The bundle was signed at file sha256
prefix `fc3cf948731087f2` and Prettier-formatted after signing (as seq-25/26/27; the husky Prettier check
requires it), file prefix now `00f1d66dd0d77f52`; the signature covers the JCS payload, so
`payload_sha256` is re-verified unchanged and the signed-bundle tie tests pass on the formatted file.
The bundle lands in the same PR as the
source, so `TestSignedBundleTiesToSource` and `scripts/ci/observe_visa_seq28_signed.py` are green at
merge, and so is the mouth pin of `E33G_ANNUAL_INCOME_THRESHOLD_USD`.

**Activation: PENDING.** It happens from Pro right after merge, the same two-login ceremony as the
seq-25 and seq-26 notes above, on the PG primary. The `activation_id` and timestamp are recorded in the
follow-up ledger PR; nothing is recorded here until the ceremony has run.

## Signing + activation note (2026-10-13, seq-29)

`rulepack-prod-029.signed.json` is the weekly re-attestation organ's re-stamp of seq-28 plus the E31
content batch, signed in ONE signing. Read ledger: `research/visa/2026-10-13-organ-reattest-seq29/`
(organ candidate PR #8410, superseded by this PR and not to be merged). The pack was built by the
visa-night conductor on Pro (branch `agent/nuzantara/backend-rag/vo-seq29-fold-1012`, head
`31eb2ade20`), rebased cleanly on `origin/main` `4646f043d6`. The generic REAL fold on the ledger
reproduces the source byte for byte (`created_at` 2026-10-13T00:30:00Z, payload digest
`3f3b45ed1aaeadc72ec9dd2a5e33519ded3a0ec1da8408fade150a0ae39b9295`), chained to the signed seq-28
(`previous_payload_sha256` `a23a5bf55a77a658aef4ff06637cdb6fea476c5569d3d47a56896af2b8557046`),
sequence 28 to 29, version `2026.10.12`, `rollback_of_payload_sha256` null. Rules 114 to 117.

What the pack contains:

1. The organ re-stamp: the 18 `OFFICIAL_PORTAL` records move to `2026-10-13T00:07:47Z`; the 10
   non-portal records (primary law and implementing regulation) are identical to seq-28. New earliest
   portal freshness boundary: `2026-11-14T00:07:47Z` (stamp + 32 days), against seq-28's
   `2026-11-12T18:00:16Z`.
2. E31J (sibling) is limited to under 18 and never married: `hf.e31j-adult-excluded`
   (`E31J_REQ_UNDER_18`) and `hf.e31j-married-excluded` (`E31J_REQ_UNMARRIED`) are added,
   `review.e31j-marital-status-other` routes marital status OTHER to human review
   (`E31J_MARITAL_STATUS_OTHER_REVIEW`, `on_unknown: NO_EFFECT`), and `el.e31j-dependency-age` is
   retired. Source: the Lampiran row of Kepmen M.IP-08.GR.01.01/2025 for index E31J ("belum berusia
   18 (delapan belas) tahun dan belum kawin"), Permenkumham 11/2024 Pasal 33(2)(h) angka 9.
3. E31D (stepchild) requires an Indonesian sponsor: `hf.e31d-sponsor-not-indonesian`
   (`E31D_REQ_SPONSOR_INDONESIAN`).
4. E28F (IKN subsidiary) requires a foreign branch or subsidiary: `el.e28f.ikn-subsidiary` modified
   (`investment.foreign_branch_or_subsidiary == true`).
5. E31E (parent) adult and married exclusions are scoped to the PARENT relation:
   `hf.e31e-adult-excluded` and `hf.e31e-married-excluded` modified.

Delta against seq-28 source: +4 (`hf.e31d-sponsor-not-indonesian`, `hf.e31j-adult-excluded`,
`hf.e31j-married-excluded`, `review.e31j-marital-status-other`), -1 (`el.e31j-dependency-age`), ~3
(`el.e28f.ikn-subsidiary`, `hf.e31e-adult-excluded`, `hf.e31e-married-excluded`); 114 + 4 - 1 = 117.
The mouth copy carries the four new reason sentences in EN and ID.

Review chain, none of it the signer's own work: the conductor's build on Pro; the Codex red teams;
the council on the final content, Codex `gpt-5.6-sol` SIGN and Kimi `k3` SIGN; the fresh Opus gate on
Pro, READY-TO-SIGN on `31eb2ade20` (the council votes and the gate verdict are recorded in
`evidence/2026-10/agent-air-m5-backend-rag-vo-seq29-land-1013-9070d845/journal.jsonl` and on Pro under
`~/visa-night`, not in the fold-1012 evidence directory); the organ attestation
`research/visa/2026-10-13-organ-reattest-seq29-attestation.md` (adversarial review: Codex
`gpt-5.6-sol`, `LEDGER: CONFIRMED` on `85c1f3cd90`); then, on the owning session's side, the
signer-side reproduction (REAL fold re-run byte-identical, W141 re-checked: 18 portal stamps, boundary,
10 non-portal records identical, rule delta above, suites) and an independent grounding ruling on all
eight rule items, all SIGN. That ruling **overrules the recorded Codex dissent on E31J** (HIGH,
marked PLAUSIBLE): the Kepmen M.IP-08/2025 PDF was downloaded from the source record's canonical URL,
its sha256 `b8e326667c892ab2...` equals the record's `content_sha256`, and the E31J Lampiran row states
under-18 and never-married verbatim, so the cap the 2026-07-21 note could not find on the portal page
is in primary law. The missing Permenkumham 11/2024 ref in the rule's `source_refs` is a citation
completeness gap, not a grounding gap.

Signed offline on M5 by the owning session `nuzantara-57` under Zero's standing authorization of
2026-10-12: `kid: prod-2026-07-1`, `signed_at` 2026-10-13T08:56:32.221637Z (the value inside the
bundle), `sign_pack` signed and self-verified, `rule_pack_id` `ed666554-c476-5e67-9c25-921388e64537`,
`payload_sha256` `3f3b45ed1aaeadc72ec9dd2a5e33519ded3a0ec1da8408fade150a0ae39b9295`, public key
`gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA` (the `prod-2026-07-1` entry of the trust store above).
The bundle was signed at file sha256 prefix `f475ebf43bfe0cb9` and Prettier-formatted after signing (as
seq-25..28; the husky Prettier check requires it), file prefix now `8daa66acd3ba3f6a`; the signature
covers the JCS payload, so `payload_sha256` is unchanged and `TestSignedBundleTiesToSource` passes on
the formatted file.

The bundle landed in the same PR as the source (#8433), so `TestSignedBundleTiesToSource`,
`TestReattestationIsReal` and `scripts/ci/observe_visa_seq29_signed.py` were green at merge.
`scripts/ci/observe_visa_seq28_signed.py` (asserts the highest signed pack is 28) was retired in the
same PR. `scripts/ci/observe_visa_seq29_candidate.py` (unsigned-candidate gate, census and mouth copy
guard) was added by that branch and stays green on the signed tree; nothing in the bites check requires
keeping it any longer.

**Activation: done 2026-10-13T11:19:00Z.** PR #8433 merged 2026-10-13T10:46:12Z as
`2bf9ed3c93c345db1ebd7675fed60111b4bf15e3`; the backend was live on it (post-deploy-verify exit 0 at
11:13:51Z). The ceremony ran from Pro, dry run first and then apply, the two-login procedure of the
seq-25 and seq-26 notes above, on the PG primary, with ceremony roles left 0. `activation_id`
`84e8a5c5-55eb-4649-8dc4-f620c9f9b00b` (`rule_pack_id` `ed666554-c476-5e67-9c25-921388e64537`); the
seq-28 activation `b7c808bd-c0f4-48fe-9fdb-3f7f47f7e86a` closed at 11:18:58Z. Proof-of-armed 13/13
PASS: https://github.com/Bali-Zero/Teman2/pull/8433#issuecomment-6144652983

Ceremony gotcha: the activation script reads `PACK` relative to `apps/backend-rag`, so a copy of the
bundle extracted with `git show` is passed by a path relative to that directory.

## Signing + activation note (2026-10-16, seq-30)

`rulepack-prod-030.signed.json` folds the six scheduled items of the E28 family close-out and the
E30/visit-family queue on top of signed seq-29 (`fold_pack_seq30.py`, `--check` reproducible):
`created_at` `2026-10-16T12:00:00Z`, `created_by` `agent.air-m5.backend-rag.vo-seq30-e28-1016`,
`rule_pack_id` `2e113982-c3ec-59f4-bfe5-88ec87f298a2`, `payload_sha256`
`972f339283e6a66962f3dd8f4dbb1c4a5014c5b16352234e425abfed988df413`, chained to signed seq-29
(`previous_payload_sha256` `3f3b45ed1aaeadc72ec9dd2a5e33519ded3a0ec1da8408fade150a0ae39b9295`),
sequence 29 to 30, version `2026.10.16`, `rollback_of_payload_sha256` null. Products 38, rules 117
to 118.

What the pack contains:

1. `SEQ29-A2` (`el.e28a.investment` passive shareholders): drops the `investment.proposed_role in
[SHAREHOLDER_DIRECTOR, SHAREHOLDER_COMMISSIONER]` conjunct and `"investment.proposed_role"` from
   `required_facts` so a passive PT PMA shareholder meeting the IDR 2.5bn paid-up and IDR 10bn total
   investment thresholds is admitted to `E28A` (verified against saved official page
   `research/visa/2026-10-15-e28-pages/text/df3ba889-20261015T142247Z.txt`).
2. `SEQ29-D1` (E28D/E28F director/commissioner requirement): `el.e28d.branch-or-subsidiary` and
   `el.e28f.ikn-subsidiary` require `investment.proposed_role in [SHAREHOLDER_DIRECTOR, SHAREHOLDER_COMMISSIONER]`
   with `on_unknown: NEEDS_INPUT` (Permenkumham 22/2023 Pasal 44(1), 46(1); saved official pages
   `dd5e2a06-20261015T142249Z.txt` and `74e25e50-20261015T142250Z.txt`).
3. `S02` (A1 onshore conversion exclusion): new rule `hf.a1.onshore-conversion-excluded` (`A1_NOT_CONVERTIBLE`)
   excludes `A1` when `process.wants_onshore_conversion == true` (Permen Imipas 10/2026
   `808d691c-374e-5581-8186-9eb54d0ca7ab` and Imigrasi Alih Status portal
   `dcf08e19-fbc3-5f96-93fa-0325b1ffe91d`: "Izin Tinggal yang berasal dari Bebas Visa Kunjungan tidak dapat
   dialihstatuskan").
4. `SEQ29-E30-02` (E30A/E30B duration options): `E30A` gains 365/730-day `duration_options` (IDR 9,000,000 /
   11,500,000) and `E30B` gains 365/730/1460-day `duration_options` (IDR 9,000,000 / 11,500,000 / 15,000,000).
5. `SEQ29-S1` (E28B/E28D/E28F `sponsor_types`): `E28B`, `E28D`, and `E28F` `sponsor_types` move from
   `["INVESTMENT"]` to `["NONE"]` (`Anda tidak membutuhkan penjamin/sponsor untuk mengajukan visa ini`,
   verified against `research/visa/2026-10-15-e28-pages/e28-pages.receipts.jsonl`; the 28 `source_records`
   remain byte-identical to signed seq-29).
6. `SEQ29-N1` (E28C/E28D/E28F titles): `E28C.names.id`, `E28D.names.id`, and `E28F.names.{id,en}` match the
   current headings on `imigrasi.go.id`.

Signed offline on M5: `kid: prod-2026-07-1`, `signed_at` `2026-10-16T12:24:48.389183Z`, `sign_pack`
signed and self-verified, `rule_pack_id` `2e113982-c3ec-59f4-bfe5-88ec87f298a2`, `payload_sha256`
`972f339283e6a66962f3dd8f4dbb1c4a5014c5b16352234e425abfed988df413`, public key
`gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA`. Pre-Prettier file sha256 prefix `b845fbefa5782a1e`,
post-Prettier file sha256 prefix `31c611994ea43a9d`; JCS `payload_sha256` unchanged. The bundle lands
in the same PR as the source, with `scripts/ci/observe_visa_seq30_signed.py` replacing
`scripts/ci/observe_visa_seq29_signed.py`.

**Activation: done 2026-10-16T14:35:48Z** (measured 2026-10-17 by the Dux's verifier with a read-only SELECT,
the sentinel's own active-pack query on `visa_ruleset_activations`: exactly one open activation, rule pack
`2e113982-c3ec-59f4-bfe5-88ec87f298a2`, sequence 30, version `2026.10.16`; seq-29's system period closed at the
same instant; #8624 merged 2026-10-16T14:20:35Z as `3f23a84da7`; backend /health build_sha `7163570a88` contains it).
The `activation_id` itself was not read in that measurement.

## Signing + activation note (2026-10-17, seq-31)

`rulepack-prod-031.signed.json` carries the E28A own-shareholding re-key on top
of signed seq-30 (`fold_pack_seq31.py`, `--check` reproducible): `created_at` `2026-10-17T03:30:00Z`,
`created_by` `agent.air-m5.backend-rag.vo-seq31-e28a-own-share-1017`, `rule_pack_id`
`4bff6af7-395d-5c98-9b43-0a45e04ee651`, `payload_sha256`
`7a5d80c670c61b5c63d18e8d07c1368173e0f954a319962d0064b57dc4efdff4`, chained to signed seq-30
(`previous_payload_sha256` `972f339283e6a66962f3dd8f4dbb1c4a5014c5b16352234e425abfed988df413`),
sequence 30 to 31, version `2026.10.17`, `rollback_of_payload_sha256` null. Products 38, rules 118 to 118
(one modified, one retired, one inserted). All 28 `source_records` and the 18 `OFFICIAL_PORTAL` stamps
are byte-identical to signed seq-30, so the freshness boundary does not move.

What the pack contains (one content item, owner ruling 1 of 2026-10-15, handoff `SEQ29-A1`):

1. `el.e28a.investment` tests `investment.own_shareholding_idr >= 10,000,000,000` (the applicant's OWN
   shareholding value in the sponsoring company; the saved official E28A page
   `research/visa/2026-10-15-e28-pages/text/df3ba889-20261015T142247Z.txt` states no company
   total-investment figure) instead of `investment.investment_capital_idr`. The IDR 2.5bn paid-up bound
   and the PT PMA commitment stay. Its SUPPORT reason code is renamed `E28A_INVESTMENT_ELIGIBLE` to
   `E28A_OWN_SHAREHOLDING_ELIGIBLE` (the sentence changes meaning); the mouth copy for the new code was
   promoted before activation (an unknown SUPPORT code is not fatal: the live client falls back to
   `UNMAPPED_REASON_COPY` and shows a generic sentence, as two reviewers found, but that sentence is not the
   intended copy).
2. `hf.e28a.total-investment-below-min` (`E28A_TOTAL_INVESTMENT_BELOW_MIN`) is retired and
   `hf.e28a.own-shareholding-below-min` (`E28A_OWN_SHAREHOLDING_BELOW_MIN`) is appended: the semantics
   changed, so the code is renamed, and the old code stays replayable in the mouth copy table.
3. `hf.e28a.paid-capital-below-min` is untouched; the IDR 2.5bn paid-up bound is a PT PMA company
   prerequisite, not a personal visa figure (the pack carries only `explanation_key`; the user-facing
   sentence is in `engine-adapter.ts`).

No regulation number is written into the pack for this item: the pinpoint for the shareholding figure is
UNVERIFIED in this repository (TO VERIFY against source); the rules cite the E28A record the pack already
carries.

Signed offline on M5 by the owner: `kid: prod-2026-07-1`, `signed_at` `2026-10-17T04:10:55.436728Z`,
`sign_pack` signed and self-verified, `rule_pack_id` `4bff6af7-395d-5c98-9b43-0a45e04ee651`,
`payload_sha256` `7a5d80c670c61b5c63d18e8d07c1368173e0f954a319962d0064b57dc4efdff4`, public key
`gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA`. Pre-Prettier file sha256 prefix `827c7977a1039710`,
post-Prettier file sha256 prefix `4c29ee47390124c9` (one post-sign Prettier pass, file mode set to 0644 like
the other bundles); the repo verifier still verifies the bundle under the pinned key and the JCS
`payload_sha256` is unchanged. The bundle lands in the same PR as the source, with
`scripts/ci/observe_visa_seq31_signed.py` replacing `scripts/ci/observe_visa_seq30_signed.py` and the
`no-path-doors.replay.json` header bumped to seq-31 (file, sequence, version, `as_of`).

Activation ordering: the SUPPORT code of `el.e28a.investment` is renamed to `E28A_OWN_SHAREHOLDING_ELIGIBLE`,
so activation must wait until the mouth deploy carrying that copy is live.

**Activation: done 2026-10-17T05:39Z**, `activation_id` `45f5e1b8-5437-480d-9cc8-3cc03ca5d60d` (merged as #8650,
`01cb59e6dc`, mouth promoted before activation; ceremony script `~/.tmp/visa-ceremony/ceremony-seq31.sh` on Pro).
Active pack before: `30|972f3392…|bf4f5f6a…`; after: `31|7a5d80c6…|45f5e1b8…`. Proof: a synthetic /evaluate on
sequence 31 (IDR 10 billion `E28A_OWN_SHAREHOLDING_ELIGIBLE`, IDR 9,999,999,999
`E28A_OWN_SHAREHOLDING_BELOW_MIN`) and the sentinel OK pack_sequence 31 at 05:40:22Z.

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
