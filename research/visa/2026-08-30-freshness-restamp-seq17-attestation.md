---
date: 2026-08-30
domain: visa
client_case: none — production incident and source-ledger attestation
sources:
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-017.source.json
  - apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq17.py
  - production catalog, read-only role (visa_ruleset_activations / visa_rule_packs)
  - PR #5311 adversarial review — codex gpt-5.6-sol xhigh, kimi-code/k3
---

# seq-17 re-stamp — what the attestation rests on, and what it does not

## Why this file exists

`verified_at` on a source record is a **claim that someone read that page at that
instant**. The engine treats it as fact: past `verified_at + max_age_seconds` the
source goes STALE and every decision that depends on it folds to
`HUMAN_REVIEW_REQUIRED`. Inside `max_age_seconds` it decides.

On 2026-08-30 that clause fired for real. The eighteen `OFFICIAL_PORTAL` records
in seq-16 carried `verified_at = 2026-08-23T10:44:48Z` under a seven-day window,
so at **2026-08-30T10:44:48Z** the Visa Oracle stopped answering — every product,
empty candidate list, no error anywhere. seq-17 restamps those eighteen records
to `2026-08-30T13:18:00Z` and changes nothing else.

Two independent adversarial reviewers of that change asked the same question, and
it is the right one: **what in the artifact proves anyone actually looked?**

## The honest answer: nothing in the artifact does

The re-verification was performed — three parallel readers over the eighteen
pages, plus two independent orchestrator spot-checks (E31A and the VOA country
list) — but that work exists only in a session transcript. **No per-record
receipt was written while it happened.** What reached version control is a
constant in a Python file:

```python
RESTAMP_VERIFIED_AT = "2026-08-30T13:18:00Z"
```

Run the fold offline against the seq-16 payload, having read nothing, and it
produces the identical attestation. That is the defect, stated plainly. It does
not change runtime behaviour and it does not make the stamp false — it makes the
stamp **unauditable**, which on a legal-source ledger is its own kind of failure.

This document does not repair that. Reconstructing per-record quotes now, from
memory, would be worse than the gap: it would look like evidence.

## Two claims that were checked and found wrong

Both reviewers produced findings that did not survive verification. Recording
them here because a review's authority comes from what it got right, and a
finding taken on trust is how a wrong fact enters the record.

**"seq-16 does not exist in this repository at all"** — this was MY claim, in the
fold's docstring, and it propagated into the PR brief and evidence pack before
the codex reviewer caught it. It is false. The signed bundle is on the unmerged
branch `origin/feature/visa-oracle`, carrying exactly the digest of the row that
was active (`ef17dc12…4100`), confirmed with `git show`. Reading the chain anchor
from the database was still correct — the database is what production ran, and a
branch is not evidence of that — but "absent from version control" was a claim
nobody had checked. The real gap is narrower: a signed artifact reached
production while its source never reached `main`.

**"Every prior restamp in this lane shipped an evidence document with verbatim
quotes per record"** — the kimi reviewer cited
`research/visa/doctrine-factory/e5/inc4-pack-edits/freshness-restamp-2026-08-19.md`
and siblings, plus a `source-restamp-edits.json` ledger, and built its headline
finding on this being a broken convention. **No such file exists.** Searched: the
worktree, `origin/main`, and every one of the 440 remote branches — zero hits for
`freshness-restamp` or `source-restamp-edits`, and `doctrine-factory` appears
nowhere on `main`. The convention was invented, with plausible paths and dates.
The reviewer's underlying point stands entirely on its own; the precedent it
claimed does not exist.

## What IS verifiable about seq-17

Each of these was executed and is re-executable:

- The fold is deterministic: re-running it on the seq-16 export reproduces the
  activated artifact byte for byte (`payload_sha256 = 97cb9647…`).
- The chain anchor is real: the fold aborts unless the export's recomputed
  RFC-8785 digest equals the `payload_sha256` of the activation that was open in
  production.
- The identity follows the lane's convention, verified rather than assumed:
  `uuid5(NAMESPACE_URL, ".../IMMIGRATION_VISA/<n>")` reproduces the ids of seq-14
  and seq-15 on disk *and* the id of the row that was live.
- The change is exactly the re-stamp: the fold now holds every top-level key and
  every record field to equality except an explicit allow-list, fail-closed, with
  guilt tests for each way a field could drift.
- The signature verifies against the pinned PRODUCTION key.
- After activation, the live endpoint answers `SUPPORTED_CANDIDATES` on cases
  that were folding to `HUMAN_REVIEW_REQUIRED`.

## Two residual risks, named

**`content_sha256` was deliberately not moved.** The judgement was that no page
changed semantically, so the digest still describes the content. If a page *had*
changed and a reader judged the change non-semantic, this pack now pairs a fresh
attestation with a stale fingerprint — and no later hash audit can detect it,
because the re-verification was reading, not re-hashing. Structurally
undetectable by design.

**`version` still reads `2026.8.26`.** Earlier folds set this field to the fold
date. seq-17 inherited seq-16's value, so the catalog holds a pack created on
2026-08-30 whose version says 2026-08-26. Nothing reads this field for decisions
— it is stored as `pack_version` and never compared — and it cannot be corrected
here: the artifact is signed and live, so the only honest remedy is a forward
pack. Noted so the next fold sets it.

## The rule this incident produces

**Write the ledger DURING the reading, not after it.** One line per record at the
moment it is read — URL, HTTP status, the sentence that was checked, the clock —
appended as it happens. Then `verified_at` is the timestamp of a file that
already exists, rather than a constant a script asserts.

And take the earliest reader's instant, not the latest. seq-17 stamps
`13:18:00Z` while the last reader returned at `13:16:40Z`; the difference is
eighty seconds against a seven-day window and changes nothing, but the direction
is wrong — an attestation should never claim the sources are fresher than the
oldest look that backs it.

The next ceremony in this lane is the one that raises the portal window. It is
the place to apply both.
