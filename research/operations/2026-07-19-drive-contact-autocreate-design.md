# CLIENTI-NON-A-CRM — drive/doc contact auto-create (design spec, wave 1)

date: 2026-07-19
domain: operations
client_case: none (infrastructure — intake identity backfill)
sources: local census on nuzantara_dev (this doc), PR #2669 (wa-intake autocreate precedent), migration 246, `.claude/skills/intake/SKILL.md`
status: DESIGN — pending adversarial gate (Codex), then measured apply

## Mandate (Zero, 2026-07-19)

Attack the 88%-ceiling: entities named by drive/doc signals that are absent from the
CRM. Auto-create missing contacts at scale, precedent PR #2669 (WA unknown-phone
autocreate). Non-negotiable constraints:

- PII stays LOCAL (nuzantara_dev book; no cloud egress of names/ids).
- Auto-create ONLY on strong evidence: subject name + consistent identifying
  document. Everything else → QUARANTINE review.
- Every created contact carries provenance `auto_created_from_drive` and is
  batch-reversible.
- NEVER merge with existing contacts without strong-id. Mis-attribution is the
  red line (worse than a missing contact).
- Sequence: dry-run census with numbers → adversarial gate on the design →
  measured-batch apply. Intake corner updated at every state change.

## Census (dry-run, executed 2026-07-19 on nuzantara_dev)

Perimeter: `document_routing_proposal` in status `review_pending` (20,160) +
`quarantine` (25,352) with saved `stage_output.extract.fields` (35,281 of 45,512)
and identity doc_type ∈ {passport, kitas, visa, ktp, npwp} → 8,255 docs.

Validity rules: name ≥5 chars with ≥2 letters, not placeholder; passport/kitas
id normalized `[^A-Za-z0-9]`-strip upper, ≥6 chars with ≥1 digit; npwp 15/16
ASCII digits; nik exactly 16 digits. Existing-client match on normalized
passport_number / kitas_number / npwp (nik matched against npwp-16).

| Bucket | docs | distinct persons (sid) |
|---|---|---|
| **A — auto-creatable** (valid name + valid strong-id, id on NO existing client, all docs agree on the name) | 3,348 | 2,586 |
| B — quarantine: name conflict on same id (≥2 distinct names) | 4,008 | 410 |
| B — quarantine: id already on an existing client (data-quality lead; NEVER merge) | 403 | 179 |
| B — quarantine: incomplete (name or id missing/fragment) | 295 | — |
| C — discard (no identity signal) | 201 | — |

A by doc_type (docs → persons): passport 2,098→1,596 · kitas 902→837 · visa
211→181 · ktp 101→59 · npwp 36→27.

**Cross-sid name overlap inside A** (the over-creation risk): 2,586 sids map to
1,980 distinct normalized names; **289 names cover 895 sids** (multi-sid: same
person with passport+kitas, passport renewals, or true homonyms — 120 of the
289 span different id KINDS). Creating 1-per-sid would mint duplicate cards for
the same human; merging them by name would be name-only merging (banned).

**Wave-1 A-effective: 1,691 contacts** (sids whose name is EXCLUSIVE to that
sid) — zero duplication risk, zero merge. The 895 multi-sid ones go to
quarantine "multi-sid review" (human decides same-person vs homonym).

## Design

New batch program `scripts/intake_drive_contact_autocreate.py` (local-only, reads
and writes nuzantara_dev; NO Fly writes). Modes:

- `--census` — re-runs the bucket census (repeatable, read-only, ids/counts only).
- `--apply --batch-size 200 --max-batches N` — default DRY-RUN; real writes
  require BOTH `--apply` and env `INTAKE_DRIVE_AUTOCREATE_ENABLED=true` set in
  the batch process env only (precedent: killswitch default OFF, never a
  daemon/Fly flag).
- `--rollback-batch <batch_id>` — batch reversal (below).

### Per-candidate write path (one TX per candidate)

Candidate = wave-1 A-effective sid (exclusive name). In ONE transaction:

1. `client_enricher.acquire_strong_id_lock(conn, kind, value)` — the m248
   advisory-lock protocol (`strongid:{kind}:{canonical}`, seed 4248) serializes
   against the enricher, the auto-attach gates, and concurrent batches.
2. Re-check under lock: id still on NO client (normalized equality against the
   matcher's own projections — the census check re-run per-row). Hit → skip to
   quarantine bucket (`id_appeared`), never merge.
3. `INSERT INTO clients`: `full_name` = the (unique) extracted name ·
   strong-id column (`passport_number` | `kitas_number` | `npwp`) = modal raw
   extracted value · `origin='drive-intake'` · `status='unlabeled'` ·
   `created_by='system:drive-intake-autocreate'` · `lead_metadata` JSONB =
   `{"auto_created_from_drive": true, "batch_id": "<run-id>", "source_proposal_ids": [...], "sid_kind": "passport|kitas|npwp|nik"}`.
4. Append (proposal_ids, new client_id) to the batch report (ids only, on disk).

**KTP/NIK exception (59 persons):** NIK is NOT written to `clients.npwp`
(NIK-as-NPWP semantics unverified for this book; a wrong tax-id on the card
poisons strong-id matching). NIK goes to `lead_metadata.identity_nik` only;
the contact is created from the KTP name. Future corroboration via nik column
support is wave-2.

**No new unique index in wave 1** (precedent 246 built one for phone): the
strong-id advisory lock + in-TX recheck + single-writer batch process gives the
same guarantee without a 3-column×format index; measured dup population for
these ids on clients is ZERO by construction (bucket A excludes existing ids).

### Post-create reroute (attach stays gated)

After each batch: route-only reroute of the affected queue_ids through the
existing machinery (`intake_reprocess_backlog.py` route-only contract:
stage_output PRESERVED — the blobs are retention-evicted). Docs then find their
new client as CONF_STRONG_EXACT candidate → LINK_CANDIDATE. Auto-attach
killswitches stay OFF: **0 auto-attach in this program**; attaching remains
HITL (or the LEVA gates when separately armed). Never-wrong-attach preserved:
this program creates CONTACTS, it does not attach documents.

### Batch reversal (the gap in the precedent, closed)

`--rollback-batch <batch_id>`: soft-delete (`deleted_at=NOW()`,
`deleted_by='system:drive-intake-rollback'`) of rows WHERE
`origin='drive-intake' AND lead_metadata->>'batch_id' = $1` AND ALL guards:

- no documents row references the client;
- no practices row references the client;
- `updated_by` unchanged from `created_by` (no human touched the card).

Guarded rows are reported (ids) and left alone. Reversal is per-batch, never
book-wide.

### Fly / delivery interaction

Created contacts have NO phone → any future intake delivery of their docs fails
CLOSED (`identity_unresolved`) by the PR #2787 identity chain — correct and
intended: a drive-minted contact gains Fly presence only when a human enriches
it with a verified phone.

### Batching & verification

Lots of 200; after each lot: count check (created == planned), sample re-read
of N=10 rows by id (columns match plan), reroute executed, corner updated.
Stop-on-anomaly: any mismatch freezes the program (no next batch) until
diagnosed.

## Expected outcome (wave 1)

- ~1,691 new contacts with strong-id keys (passport/kitas/npwp) — the CRM key
  book grows by ~10× on passports (313 → ~1,900).
- The A-bucket docs whose sid was created re-route to LINK_CANDIDATE (measured
  after apply; upper bound 3,348 docs).
- Quarantine review queues gain structured lots: multi-sid (895 sids/289
  names), name-conflict (410 ids), id-exists (179), incomplete (295).
- Compounding: every future doc naming these ids corroborates deterministically
  (the 100%-precision tier).

## REVISION v2 (post adversarial gate — Codex sol xhigh, VERDICT: FINDINGS, 11 BLOCKER)

Gate run 2026-07-19. Every finding answered below; v2 SUPERSEDES the
conflicting v1 sections. NO-GO on apply stands until re-gate.

1. **Identity ≠ client (B1):** kept as `clients` rows BY MANDATE and by house
   convention (the #2669 precedent creates clients from a bare unknown phone;
   `status='unlabeled'` + `origin` IS the neutral registry embodied in the
   book). The missing relationship evidence is supplied by the CORPUS
   provenance: these docs live in Bali Zero's staff-curated client-service
   Drive folders — someone at BZ filed this person's document as part of a
   service relationship. Subjects from forward-prone doc_types stay out:
   wave-1 A restricted to docs whose folder path is a client-service root.
2. **Evidence gate (B2):** A-candidates additionally require: `validate.valid`
   not false where present; name+id from the SAME doc (already true — same
   fields blob); id passes the SAME validator the matcher uses (passport 6-9
   alnum per `routing.py` validator — census ≥6-no-max replaced); blob-hash
   dedup BEFORE "all docs agree" (agreement counted on DISTINCT blobs only —
   copies can't vacuously self-confirm).
3. **"ID absent ≠ person absent" (B3):** new census exclusion — candidate name
   trigram-similar ≥0.45 to ANY existing live client name → quarantine
   `possible_existing_person` (renewed-passport/name-variant risk), never
   create.
4. **Name-variant latent duplicates (B4):** cross-sid clustering by trigram
   ≥0.6 (not just exact-name collision) → the cluster goes to multi-sid
   quarantine. A-effective shrinks; that is the point.
5. **Stale snapshot (B5):** apply revalidates PER CANDIDATE in-TX: latest
   proposal per queue, status unchanged, extract-fields fingerprint (sha256 of
   the fields JSON) equal to census-time, reusing the reroute machinery's
   protections.
6. **Advisory lock ≠ constraint (B6) + non-atomic report (B11) + tombstone
   (B10) + NIK invisibility (B7):** ONE mechanism — new LOCAL table
   `intake_identity_ledger` (kind, canonical_value, client_id, batch_id,
   status planned/created/rerouted/rolled_back, source ids, fingerprints,
   UNIQUE(kind, canonical_value)), created by the program (local-only, like
   the rest of the local-authoritative intake state; NOT in migrations_v2 —
   prod never runs this). The ledger row and the clients INSERT commit in the
   SAME TX → DB-level uniqueness across batches/restarts, crash-safe recovery
   (report generated FROM the ledger), rollback sets status='rolled_back' and
   KEEPS the row (tombstone: census skips ledgered keys), NIK lives as a
   ledger row (kind='nik') even though clients.npwp is never written.
7. **NPWP company namespace (B8):** census/apply exclusion extends to
   `companies` npwp (mirror of `routing.py` cross-table ambiguity rule).
8. **Rollback guards (B9):** reversal TX takes the strong-id advisory locks +
   `SELECT ... FOR UPDATE` on the client row, sweeps ALL FK references to the
   client (documents, practices, plus information_schema-driven FK sweep),
   and requires the clients row content (name/id columns) to equal what the
   ledger recorded — not `updated_by` heuristics.
9. **Reroute contract (B12/M):** the rerouter is parameterized for the exact
   queue_ids of the batch (both review_pending and quarantine sources);
   "rerouted" is verified per queue_id by reading the resulting proposal
   state, recorded in the ledger row.
10. **Canonicalization divergence (B13/M):** census/apply/lock all use the
    MATCHER's own normalization (`routing.py`), incl. the passport 6-9 bound.
11. **Killswitch hardening (B14/M):** batch size hard-capped at 200 in code;
    `--apply` requires `--manifest <sha256>` equal to the digest printed by
    the immediately-preceding dry-run of the SAME candidate set; env flag +
    manifest are the two independent authorities.
12. **Denominators (B15/NIT):** outcomes reported per kind; KTP/NIK counted
    separately from queryable-strong-key contacts.

## REVISION v3 (post gate round-2 — 8 residual blockers, all closed below)

Gate round-2 run 2026-07-19 (Codex sol xhigh). v3 SUPERSEDES conflicting v1/v2
text. Grounding re-verified on disk/DB this session (worker plist env,
`routing.py`, `client_core.py`, lock-taker grep).

1. **Reroute CAN auto-attach — confirmed real, suppressed (R2-1).** The live
   worker (`launchctl print gui/$UID/com.nuzantara.intake-worker`, verified
   2026-07-19) runs with `INTAKE_WRITER_ENABLED`, `INTAKE_AUTO_ATTACH_ENABLED`,
   `INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED` AND
   `INTAKE_NAMEID_AUTO_ATTACH_ENABLED` all `true` (armed by the m248/LEVA
   program). Rerouting wave docs through it would fire LEVA-3 on doc→card pairs
   where the card was MINTED from that very doc — circular self-confirmation,
   and a blast-radius change Zero never approved (the GO covers CREATE;
   attach stays HITL). Fix, two independent layers:
   - **Per-batch suppression at the single chokepoint.** The batch reroutes
     with `pipeline_version='v2.3-drive-autocreate'`;
     `_try_auto_attach_after_route` (routing.py:1230 — the ONE place all three
     gates fire) skips every gate when the row carries the suppressed tag.
     Wired so the tag actually REACHES the chokepoint (W99: check≠action —
     a test proves the marker survives the worker's routing-JSON rewrite).
     Guilt test: armed env + suppressed tag → zero gate evaluations. Innocence
     test: armed env + normal tag → gates still fire (the Lane-A wire must not
     be disarmed by this program).
   - **Post-reroute assertion.** After each lot: `status='auto_routed'` count
     over the lot's queue_ids MUST be 0; any hit → program freeze + ledger
     ERROR row + no next batch. Recorded per lot in the batch report.

2. **Ledger UNIQUE does not constrain clients/companies (R2-2).** Honest
   boundary: a GLOBAL unique index on the key columns is impossible on this
   book (measured: the 62130 case — 7 live clients share one normalized
   passport). Only `client_enricher` and `auto_attach` take the
   `strongid:{kind}` advisory lock (grep verified); REST/human writers do not,
   so the lock + in-TX recheck serializes against every AUTONOMOUS writer but
   NOT against a concurrent human PATCH. Closure: (a) in-TX recheck under lock
   queries `clients` (both normalization projections) AND `companies` npwp;
   (b) **post-lot key sweep** — after each lot, re-run the duplicate query for
   every key the lot wrote: any key now on >1 live row → freeze + report
   (data-quality lead; NEVER auto-merge, NEVER auto-delete). The residual
   human-race window is thereby detected within one lot (≤200 rows), not
   silently accumulated.

3. **Full A-predicate re-run pre-INSERT (R2-3).** Census and apply share ONE
   predicate function (`candidate_predicate(conn, sid)` — same module, same
   code path): name validity, id validity (v3 validator below), name
   exclusivity, cross-sid trigram clustering, trigram-vs-existing-clients
   exclusion, companies-npwp exclusion, `validate` gate, blob-hash-distinct
   agreement, folder-root restriction. At apply time the FULL predicate re-runs
   per candidate inside the TX under the strong-id lock; the census-time
   fields-fingerprint (sha256) is a cheap short-circuit only — equality is NOT
   accepted as a substitute for re-evaluation.

4. **KTP/NIK excluded from wave 1 (R2-4).** The 59 KTP/NIK-only persons are
   OUT — creating a card whose only key is invisible to the matcher adds no
   corroboration and carries homonym risk with zero offsetting value. Wave-1
   kinds: passport, kitas, npwp. NIK returns in wave 2 with real `clients.nik`
   column support (§Solo-operatore).

5. **Rollback full-row business fingerprint (R2-5).** At create time the
   ledger stores sha256 over the canonical JSON (sorted keys) of the FULL
   business row (every human-editable column: name, ids, phone, email, status,
   assigned_to, notes, metadata — not just name/id). Rollback requires:
   strong-id advisory locks + `SELECT … FOR UPDATE` + full-row fingerprint
   equality + information_schema-driven FK sweep = zero references. ANY drift
   → row is guarded (reported, left alone). "Human touched it" is decided by
   content, never by `updated_by` heuristics (W88: verify by CONTENT, not
   proxy).

6. **Validator SSOT named honestly (R2-6).** Verified on disk: NO existing
   validator applies a 6-9 bound — `routing._normalize_passport` is
   strip+upper only; `crm.client_core.ClientValidator.validate_passport` is
   `[A-Z0-9]+` with no length rule. The v2 claim "passport 6-9 per routing.py
   validator" was FALSE. v3 separates the two layers by name:
   - **Matching normalization** = `routing.py`'s own projections
     (`_normalize_passport`, `_ascii_digits`) — census/apply/lock all use
     THESE for any equality against the book (R1-B13 unchanged).
   - **Creation validity** = new named validator owned by this program
     (`drive_autocreate_validity.py`, unit-tested, guilt+innocence per kind):
     passport `^(?=.*[0-9])[A-Z0-9]{6,9}$` (ICAO 9303 upper bound 9);
     kitas ≥6 alnum with ≥1 digit; npwp exactly 15/16 ASCII digits.
     Creation validity is deliberately STRICTER than matching normalization —
     a value good enough to match against is not automatically good enough to
     mint identity from.
   - **`validate` stage gate:** census v2 measures `stage_output->'validate'`
     presence over the perimeter FIRST; the gate is then fixed as strict
     `valid IS TRUE` if the stage has meaningful coverage, else the stage is
     declared absent-by-construction in the census v2 artifact and the
     evidence bar rests on the validator + distinct-blob agreement (the gate
     never silently degrades: whichever branch census v2 proves is written
     into the manifest the re-gate reviews).

7. **v2 internal contradictions cleaned (R2-7).** (a) §Solo-operatore listed
   "name-variant clustering" as wave-2 while B4 uses trigram ≥0.6 clustering
   in wave 1: RESOLVED — the clustering EXCLUSION gate is wave-1 (it shrinks
   A-effective); what is wave-2 is the review UX for the quarantined clusters.
   (b) "GO already given" vs "NO-GO stands": RESOLVED — Zero's GO covers the
   PROGRAM (mandate); the APPLY is gated by the adversarial re-gate. Status
   line, single source: **apply = NO-GO until the re-gate returns GO-WAVE-1 on
   spec v3 + census v2 together.**

8. **Census v2 BEFORE GO (R2-8).** The GO decision applies to census-v2
   numbers, not the v1 1,691. Census v2 re-runs the full bucket census with
   EVERY v2+v3 gate armed (validator bounds, distinct-blob agreement,
   trigram≥0.45 vs existing clients, cross-sid trigram≥0.6 clustering,
   companies-npwp exclusion, folder-root restriction, NIK exclusion,
   `validate` branch per point 6), reports per-kind (passport/kitas/npwp)
   counts for A-effective/quarantine-buckets/discard, and prints the
   candidate-set manifest digest. The re-gate receives spec v3 + census v2
   output as one package; GO-WAVE-1 binds to that digest (R1-B14 manifest
   rule).

## Census v2 (executed 2026-07-19, all v3 gates armed — the numbers GO binds to)

Implementation: `apps/backend-rag/scripts/intake_drive_contact_autocreate.py`
(`--census`, read-only) + `backend/services/intake/drive_autocreate_validity.py`
(creation validity, 17 guilt+innocence tests green). The candidate predicate is
ONE Python function (`classify_perimeter`) census and apply share; the census
tests import it from the script file itself (no drift twin). Report artifact:
`/tmp/06ffbfc2/tmp/census_v2.json`.

Perimeter 7,895 docs (passport/visa/kitas/npwp; KTP excluded per v3 §4).
`validate` stage coverage = **1.0** → STRICT `valid IS TRUE` branch armed.
Existing key book (clients passport/kitas/npwp + companies.npwp_company):
1,988 keys. Ledger: absent (0 tombstones).

| Bucket (first-match-wins order) | docs |
|---|---|
| B incomplete (name or valid-id missing under the v3 validator) | 2,304 |
| B name conflict on same id (distinct-blob agreement) | 1,847 |
| B validate stage not `true` | 1,559 |
| B non-drive provenance (wa-mirror etc. — out of wave 1) | 850 |
| B multi-sid / trigram≥0.6 name cluster | 710 |
| **A effective** | **281** |
| B id already on an existing client/company | 231 |
| B name trigram≥0.45 similar to an existing live client | 92 |
| C discard (no signal) | 21 |

**A-effective: 252 contacts** — passport 158 · kitas 88 · npwp 6.
Manifest digest (sha256 over sorted kind|canonical|name lines):
`d2cbcb5b840b682de6b9704c3ac6c074fa95d5f897f0ed98da04b07126415e04`.

Honest reading of the shrink (1,691 → 252, −85%): that is the gates working,
not value lost. The passport length histogram is the proof the v1 bar was
rotten: 1,759 extracted "passport numbers" are 35 chars long (whole MRZ lines)
plus a 10-43-char junk tail — v1's ≥6-no-max validity would have minted
identity from OCR debris. Relative key-book impact stays structural: kitas
1 → 89 (×89), passport 313 → 471 (+50%), npwp 291 → 297. Compounding: every
future doc bearing one of these 252 ids corroborates deterministically (the
100%-precision tier), and the quarantine lots (multi-sid, name-conflict,
possible-existing) are structured review feeds, not losses.

Drive-root allowlist observed (all Bali Zero staff/service roots — the B1
provenance restriction is drive-only + this declared list): DATA ADI 2,777 ·
PEMEGANG KITAS 1,868 · EXTEND VISA 1,796 · staff folders (ADITYA/YANTI/LIA/
YUDI/NOVI/DINOK/MEGI/DAVID/YOYOK/gendu/MERP) 201.

## REVISION v3.1 (post gate round-3 — 8 BLOCKER + 2 MAJOR + 1 MINOR, all addressed)

Gate round-3 (Codex sol xhigh) reviewed spec v3 + census v2 + code and found
the prose ahead of the executable — every finding below is now CLOSED IN CODE
(census/validator) or BUILT (suppression), not re-worded:

1. **R3-1 allowlist enforced:** `DRIVE_ROOT_ALLOWLIST` (16 declared roots) is
   a predicate gate (`B_root_not_allowlisted`), tested guilt+innocence.
2. **R3-2 perimeter + manifest:** perimeter takes the LATEST proposal per
   queue (`DISTINCT ON (queue_id) … ORDER BY id DESC`); the manifest now
   binds, per candidate: proposal ids, queue ids, blob hashes, per-doc
   sha256 fields-fingerprints — plus a header with validate branch+coverage,
   both trigram thresholds, the allowlist, companies column and code git SHA.
   Apply re-derives and compares BEFORE any write.
3. **R3-3 STRICT truly strict:** `validate_valid != "true"` excludes —
   missing/null stage included (guilt test: `has_validate=False` under
   STRICT lands in `B_validate_not_true`).
4. **R3-4 projections mirror routing verbatim:** `canonical_alnum` strips
   ONLY `[\s.\-/]` (routing._normalize_id); `CLIENT_KEYS_SQL` uses the same
   class. `AB#123456` keeps its `#` on both sides and fails creation
   validity (guilt test) — never silently cleaned into a different key.
5. **R3-5 human-writer race — accept-and-detect, declared:** the uncommitted
   concurrent human INSERT is invisible to any read the batch can do; no DB
   constraint can exist on this book (62130: 7 live clients, one passport).
   Closure: immediate post-lot sweep + DELAYED re-sweep (next-lot start + a
   final end-of-program sweep) + freeze-on-hit; a late human duplicate is a
   detected data-quality lead (NEVER auto-merged/deleted). Declared residual:
   duplicates created after the final sweep — same exposure every manual CRM
   create already has today.
6. **R3-6 suppression BUILT, not claimed:**
   `routing.AUTO_ATTACH_SUPPRESSED_PIPELINE_VERSIONS` (frozenset,
   `v2.3-drive-autocreate`) checked at the `_try_auto_attach_after_route`
   chokepoint; tag travels queue row → routing JSON → chokepoint. Tests:
   guilt (armed env + suppressed tag → gates monkeypatched to raise, never
   called), innocence (normal tag → gates still fire), edge (missing tag not
   suppressed). Post-lot assertion extends to: 0 `auto_routed` among batch
   qids AND 0 new `intake_commit_audit` rows for them.
7. **R3-7 rollback hardening (apply-PR commitment):** fingerprint over the
   FULL business-column projection derived from information_schema (every
   writable column except volatile bookkeeping timestamps, list recorded in
   the ledger row); rollback TX = strong-id locks + `FOR UPDATE` + in-TX FK
   re-sweep (children block on the parent row lock during FK check, so the
   re-sweep after acquiring it sees late arrivals) + post-rollback sweep for
   after-commit children (report-only lead).
8. **R3-8 local-book attestation:** `attest_local_book()` refuses unless
   `current_database()='nuzantara_dev'` AND server address is unix-socket/
   loopback — census and apply alike, before ANY read.
9. **R3-9 evidence bar declared:** ONE strictly-validated doc (coherent name
   + creation-valid id + `validate.valid=true`) IS the bar — the mandate's
   "nome + documento identificativo coerente". Distinct-blob logic is kept
   ONLY for conflict detection (copies can't manufacture conflict OR
   agreement); agreement is not pretended to add confirmation.
10. **R3-10 clustering decontaminated:** two-pass predicate — pre-pass finds
    eligible candidates, trigram-vs-existing runs on eligible names, cluster
    pairs run on post-existing-gate names and only SID-DIVERSE collisions
    cluster (`_clustered_names`, guilt+innocence incl. same-sid innocence).
11. **R3-11:** buckets reported in execution order.

### Census v2.1 (executed 2026-07-19, all round-3 fixes armed)

Perimeter 7,895 (latest-proposal-per-queue) · validate coverage 1.0 → STRICT.
Execution-order buckets: discard 22 · incomplete 3,179 (the faithful
projection no longer "cleans" symbol-bearing ids — they fail validity now) ·
non-drive 546 · root-not-allowlisted 0 · id-exists 231 · name-conflict 1,277 ·
validate-not-true 1,557 · validate-false 0 · possible-existing 93 ·
multisid/cluster 499 · **A-effective 491 docs → 435 contacts** (passport 208 ·
kitas 221 · npwp 6). Pre-pass eligible 1,002; existing-similar names 67;
clustered names 171. Manifest digest:
`(see /tmp/06ffbfc2/tmp/census_v2_1.json — bound to code SHA at run time)`.
Decontamination effect vs v2: A 252 → 435 (+183 legitimate candidates the
polluted cluster gate was burning); kitas book impact 1 → 222.

## REVISION v3.2 (post gate round-4 — 3 residual findings, closed in code)

Round-4 confirmed R3-1/3/4/8/9/11 closed and R3-5/7 honestly declared; found
3 residuals, each now closed:

1. **R4-1 (suppression bypassed — the W99 trap, caught by the gate):**
   `build_routing_proposal` puts `pipeline_version` at the TOP LEVEL of the
   proposal payload; the first chokepoint draft read
   `proposal["routing"]["pipeline_version"]` — a shape that never occurs in
   production — and the guilt tests hand-built exactly that phantom shape.
   FIXED: the chokepoint reads the top-level field (nested kept as tolerance
   for hand-built payloads), and a NEW end-to-end test
   (`test_suppressed_pipeline_version_end_to_end`) drives the REAL path —
   `route_stage` → `build_routing_proposal` → chokepoint — with the armed
   env and gates monkeypatched to raise: verdict
   `skipped=suppressed_pipeline_version`, proposal stays `review_pending`.
2. **R4-2 (manifest binding):** per-candidate evidence is now bound as
   per-document TUPLES `(pid,qid,status,blob_hash,fields_fp)` — a status
   flip or evidence reshuffle changes the digest — and the header carries
   `script_sha256` + `validator_sha256` (exact bytes of the reviewed files)
   alongside the git head, so a dirty worktree can no longer masquerade as a
   commit. The executable apply consumer remains a post-GO deliverable by
   design (apply is not built before GO-WAVE-1); the digest contract it must
   satisfy is now fully specified by `_build_manifest`.
3. **R4-3 (non-transitive trigram decontamination):** cross-sid pairs are
   computed on the FULL post-hard-gate eligible set BEFORE the
   similar-to-existing exclusion — if A~existing and A~B (different sid) but
   B!~existing, A buckets `possible_existing` and B now buckets
   `multisid_or_cluster` (bucket order does the assignment). Census v2.2:
   clustered names 171 → 182; A-effective UNCHANGED at 435/491 docs (the
   newly clustered names' docs were already quarantined by earlier gates in
   this dataset) — the number is now certifiable, not coincidental.

Census v2.2 artifact: `/tmp/06ffbfc2/tmp/census_v2_2.json` (manifest header
binds script/validator sha256 + git head).

## §Meta-pattern

The 88% ceiling was never a matching defect — the book lacked the KEYS. Every
prior lever (panel width, re-OCR, folder matching) optimized matching against
an empty key book. The structural cure is key-book growth with provenance, and
the only safe scale-path is create-don't-merge under strong-id locks.

Round-2 meta: two v2 claims died on physical verification (worker killswitches
ARE armed; the "6-9 routing validator" does not exist). The malattia is #6
phantom-citation — a design that cites an environment or a symbol without
re-probing it THIS turn inherits the error at apply time, where it costs real
rows. v3 was therefore grounded probe-first (plist read, grep, DB census)
before any prose. Census v2 then falsified the v1 sizing itself (1,691 → 252):
the MRZ-line histogram shows the earlier "valid id" bar was measuring OCR
debris, not identity.

## §Solo-operatore

Zero's GO covers the program; apply is gated by GO-WAVE-1 (re-gate on spec v3 +
census v2, killswitch process-env-scoped + manifest digest). Wave-2 items
returning to Zero as separate proposals: `clients.nik` column support (schema
change), multi-sid review UX, name-variant cluster review UX.

## v3.3 — Round-6 closures (apply built, 2026-07-19)

Round-5 left one blocker (R5-1 manifest self-reference), closed by the gate's
own prescription: apply/rollback were built, `_compute_census` extracted as
the single shared code path, and the regenerated digest re-gated. Round-6
returned 8 findings on the built code; all closed same-day:

- **R6-1 (red-line collision race):** a DB unique constraint is impossible —
  the live book already carries duplicate keys (62130: 7 clients, one
  passport). Authority = detect-fast + freeze + ledger-reversible: in-TX
  post-insert owner re-count (`CollisionDetected` → the create's own TX rolls
  back), post-commit per-candidate re-count (freeze + rollback pointer), lot
  sweeps. Proven by a two-connection test that commits a competitor inside
  the race window (`test_in_tx_collision_second_connection_rolls_back`).
- **R6-2 (vacuous reroute verification, W84 class):** supersede and queue-
  reset now prove EXACT cardinalities; drain timeout FREEZES (an idle worker
  is a failure, not a pass); every lot queue must show a NEW proposal
  (id > superseded pid) in a non-auto terminal, counted 1:1.
- **R6-3 (phantom column):** the audit assertion referenced
  `intake_commit_audit.created_at`; the schema has `committed_at`. Fixed; a
  test extracts the query verbatim from the script and executes it against
  the real schema.
- **R6-4 (evidence recheck incomplete + unlocked):** `_locked_evidence_matches`
  now FOR-UPDATE-locks queue + latest proposal and re-derives the FULL Doc
  through the census parser (`_doc_from_row` shared, `PERIMETER_ONE_SQL`);
  every predicate-bearing field must be byte-identical.
- **R6-5 (manifest under-binding):** header now hashes routing.py and
  client_enricher.py bytes (`routing_sha256`, `client_enricher_sha256`) —
  editing the suppression or the lock invalidates an approved digest.
- **R6-6 (scope defaulted, not enforced):** `--max-batches != 1` or batch
  size outside 1..200 is REFUSED at entry.
- **R6-7 (rollback schema drift):** ledger row re-read FOR UPDATE in-TX;
  current business-column set must EQUAL the stored set else `schema_drift`
  guard — a column added after create can carry invisible human data.
- **R6-8 (PII in freeze reports):** sweep violations and collision reports
  carry kind + integer ids only; canonical values never serialize.

Meta: R6-2/R6-3 are the same organism-wide diseases (#2 esiste≠armato:
assertions that pass vacuously; #6 phantom-citation: a column name cited
without probing the schema) reappearing INSIDE a design explicitly built
against them — the gate loop exists because the author cannot see their own
instances.

## v3.4 — gate round 9 closures (2026-07-19, digest e2b50dde…)

Round 9 (gpt-5.6-sol xhigh, census v2.6) returned 5 findings; all closed
same-day, census v2.7 regenerated with INVARIANT substantive numbers
(perimeter 7,895 · A_effective 435 = 208/221/6 · key book 1,988) — digest
`e2b50dde39e24697b8a7bb7995eff831bbc3659c972635f781aa0d04073a982d`.

- **R9-1 (rollback impossible before verified reroute):** the CAS read a
  NULL `reroute_proposal_ids` as the empty set, so ANY pre-verify freeze
  (post-commit collision, sweep, drain timeout, crash) classified every
  queue as moved-on and made rollback structurally impossible. Closed
  WITHOUT schema change: `source_proposal_ids` — each queue's latest pid,
  captured under the evidence FOR UPDATE locks and verified current by
  `_locked_evidence_matches` — is the pre-reroute expected set. Per-queue
  phase verdict: verified-reroute product → restore; OUR-tag unverified
  fresh → restore; own-original superseded (mid-reroute) → skip; own-original
  still in review (pre-reroute) → skip; anything else → abort ALL (soft-delete
  included). Both directions behaviorally tested.
- **R9-2 (Arm B ≠ census ID projection):** the probe's Python consumer
  returned None for an id object with no `value` member, while the census
  projection serializes the whole object and the digit-extracting npwp
  validator can mint a SID from it — same row, SID in census, invisible to
  the gate. Closed by projecting every id key in SQL with the EXACT census
  expression; the Python re-parse is deleted. Guilt test: malformed
  `{"raw": "…15 digits…"}` npwp shape now yields `cluster_appeared`.
- **R9-3 (name-gate TOCTOU):** probes are unlocked READ COMMITTED reads.
  Closed to the same residual bound the program already accepts for key
  collisions: gates re-run in-TX post-insert (`_PostInsertGuard "<r>_post"`)
  and re-run per created row in `--verify-batch` at T+delay and T+1d.
  Residual = two-uncommitted-writers; consequence bounded (dup → AMBIGUOUS,
  never auto-attach).
- **R9-4 (drain null-fail-open):** `NOT (stage='route' AND status='done')`
  is NULL for stage IS NULL → row silently excluded → counted as drained.
  Closed with `IS DISTINCT FROM` both sides; test extracts the predicate
  VERBATIM from source and proves the null shape stays pending.
- **R9-5 (behavioral closure):** 6 new real-DB tests (36 total in
  apply+validity): gates guilt A/B + innocence + malformed shape, rollback
  NULL-recorded both directions, drain null shape, verify document_gate
  exit 4 with a clean self-evidence-only pass.

Meta (continuing v3.3's line): R9-1 and R9-4 are both the **fail-open
default of an absent state** — a NULL column read as "empty set" and a NULL
stage read as "not pending". The disease is trusting a comparison operator's
NULL semantics to fail closed; the antidote is naming the absent state
explicitly (phase verdict / IS DISTINCT FROM) and writing the guilt test for
the absent shape first.

## v3.5 — Codex gate round 11 (2026-07-20): the manifest must be honest about the LIVE world

Verdict FINDINGS (5), all confirmed on source re-read; all cured same-day.

- **R11-1 (nested `value` member):** the R10-4a typed oracle checked only the
  OUTER field shape — `->>'value'` SERIALIZES a nested object/array to JSON
  text, and the letter-accepting name validator would take
  `{"value":{"label":"JOHN SMITH"}}` as a person name (literal JSON on a
  minted card). Closed: the `value` member is now itself CASE-typed
  (string/number only, else NULL) in the ONE shared projection. Guilt+
  innocence extended in the malformed-shape test.
- **R11-2 (census/apply asymmetry — npwp names invisible to census
  clustering):** census cluster pressure derives from `pre.a_sids`, which the
  `B_npwp_person_ambiguous` bucket never reaches, while the APPLY-time
  probes scan EVERY latest proposal (R10-1) — so a candidate the live gates
  would skip TODAY was still sold by the manifest as a would-be create
  (A_effective overstated). Closed with a census live-gate PRE-FLIGHT: the
  exact `_live_name_gates` the apply runs are executed per candidate at
  census time and failures demote to the new `B_live_gate_would_flag`
  bucket (docs re-bucketed, per-kind recount). Apply still re-runs the gates
  under lock — this is manifest honesty, not the gate itself. Note the
  digest consequence: the manifest now binds live-world name state too, so
  a conflicting doc arriving between census and apply invalidates the
  digest (fail-closed refuse, re-census).
- **R11-3 (unattested worker):** manifest hashes bind the WORKTREE bytes;
  the reroute lot is consumed by the launchd worker running the DEPLOY
  checkout with whatever modules it LOADED at boot — a stub/stale worker
  drains without producing the proposal freshness requires. Closed twice:
  `stages_sha256` joins the manifest (the drain dispatcher was unbound),
  and an ARMED apply now runs `_worker_attestation()` — deploy-file bytes
  == manifest hashes for all 7 intake modules, worker PID booted AFTER the
  newest attested file mtime (`ps -o etime=`, locale-free), and the daemon
  env carries neither `INTAKE_WORKER_STUB` nor any auto-attach arming flag
  (batch-process-only arming). Any probe error is a failure (fail-visible,
  W84). Escape: `--skip-worker-attest`, dev/test rigs only. OPERATIONAL
  CONSEQUENCE: wave-1 is structurally blocked until the Lane B branch
  (batch-qualified suppression prefix in routing.py) is merged, pulled into
  `~/nuzantara-deploy` and the worker kickstarted — the attestation makes
  this precondition mechanical instead of procedural.
- **R11-4 (vacuous rollback):** unknown/mistyped batch id returned
  `rolled_back: 0`, exit 0 — automation would read a typo as "reverted".
  Closed: any-status existence check first (mirrors `run_verify`), exit 2
  `unknown_batch`.
- **R11-5 (overstated consequence bound):** the R9-3 comment claimed "dup
  keys land AMBIGUOUS, never auto-attach" as if it bounded ALL consequences;
  the true residual is a HUMAN attach onto a conflict-tainted card before
  the delayed verify, after which automated rollback correctly refuses
  (fk_refs guard → exit 4). Closed: comment rewritten to the honest bound
  (detection + guarded rollback + short verify delay, not immunity), and
  `run_verify` now PERSISTS a `verify_conflict:<gate>` guard_reason on the
  ledger row — the verdict no longer dies with the process stdout.

Meta (v3.3→v3.4 line continued): rounds 9-11 are one disease in three
organs — **the audited artifact and the live world drift apart silently**
(census vs probe, worktree bytes vs loaded worker, stdout verdict vs
durable state). The antidote is always the same move: make the SAME code
path read the SAME state at both ends, and persist what the audit saw.

## v3.6 — Codex gate round 13 (2026-07-20): closing the loop, declaring the residuals

Verdict FINDINGS (4). Two cured, two declared as accepted residuals rather
than chased into a fifth theoretical bypass — see rationale below.

- **R13-1 (structural-char-free JSON literal):** R12-1's structural-character
  guard missed bare JSON literal tokens — `valid_name("false")` returns
  `"FALSE"` (5 letters, no structural chars, not on the placeholder list).
  Closed: `_NAME_PLACEHOLDER_RE` now also names `NULL|TRUE|FALSE|UNDEFINED`.
  Guilt+innocence: `false`/`true`/`null`/`undefined` (any case/whitespace)
  rejected; `"FALSE POSITIVE"` / `"TRUEMAN JACKSON"` (substrings, guard
  family #3 — never bare-containment) still valid.
- **R13-2 (provenance token too permissive):** the R12-2 fix accepted ANY
  path-like command-line token resolving under the deploy root — an
  external worker invoked as `/other/worker.py --config <root>/config`
  would attest, because the CONFIG argument (not the executable) happened
  to point under root. Closed: only the EXECUTABLE token counts — argv[0],
  or argv[1] when argv[0] is a known shell/interpreter basename (this
  repo's real launchd shape: `/bin/bash <root>/…/worker-run.sh`). Guilt:
  external executable + root-pointing flag now fails
  `worker_not_running_from_deploy_root`. Innocence: the real bash-wrapper
  invocation shape still attests.

**Declared, not chased — R13-3 and R13-4:**

- **R13-3 (backdated-mtime bypass of the byte/boot-time attestation):** an
  operator who deliberately preserves an old mtime while replacing deploy
  files could defeat the `worker booted AFTER newest mtime` check even
  though the running PID's IN-MEMORY code is stale. This requires
  DELIBERATE SELF-SABOTAGE of a safety check on one's own single-operator
  tool (`touch -d "1 hour ago"` after editing) — outside any realistic
  accidental-failure threat model for this system, and closing it properly
  needs the WORKER itself to self-report a loaded-code fingerprint (a
  `worker.py` change, not a census-script change) — a materially bigger
  lift than a round-13 patch. Logged in PENDING-ARMS as a future worker.py
  self-attestation lane, not fixed here.
- **R13-4 (freshness-to-ledger-UPDATE TOCTOU on `reroute_verified`):** a
  real gap — freshness read, the attest callback (a subprocess call, which
  cannot share a DB transaction with the freshness query), and the ledger
  `reroute_verified=TRUE` UPDATE are three non-atomic steps; a proposal
  could theoretically flip between them. But `reroute_verified` is
  BOOKKEEPING about the reroute step, not itself a safety gate — the
  actual safety gates (sole-owner, name-conflict, document_gate) are
  INDEPENDENTLY re-run by `--verify-batch` at T+delay and T+1d regardless
  of this flag's value (R10-1/R9-3's existing residual language already
  covers exactly this shape: "the residual — a competitor's TX still
  uncommitted through in-process checks — is undetectable in-process by
  construction; the detector is the delayed re-sweep, consequence bounded:
  dup key → AMBIGUOUS, never auto-attach, reversible"). R13-4 is the same
  residual family manifesting through a new window, already inside the
  accepted and DETECTED bound. Not fixed further.

Meta (v3.4→v3.5→v3.6 line, closing the arc): eight rounds (6→13) of deep
adversarial review on ~1,900 lines converged from real closable defects
(6-11) to increasingly contrived findings requiring a threat model this
program does not have — an adversary tampering with the SAME machine's
filesystem timestamps or process identity, when that adversary already
controls the killswitch, the manifest, and the deploy pipeline. The
disciplined stopping rule: fix what threatens the stated bound
(never-wrong-attach, detectable, reversible) at reasonable cost; DECLARE
the rest with the reasoning on record (no silent caps) rather than chase
an unbounded adversarial regress on an already NO-GO-gated, killswitch-off,
manifest-pinned, review-terminal, reversible tool. Round-13 closes the
gate arc for wave-1 GO; the two declared residuals are follow-up lanes, not
blockers.

## v3.7 — Codex gate rounds 14-15 (2026-07-20): R14-1 cwd-independence bypass, then CLEAN

Round 14 verdict: FINDINGS(1) — R14-1: the R13-2 executable-token tightening
left the cwd fallback as an INDEPENDENT alternative — an external absolute
executable with cwd merely SET to the deploy root still attested, defeating
the point of R13-2. Concrete guilt: `/somewhere/else/worker.py --loop` with
cwd=`<deploy_root>` attested despite the executable being elsewhere.

Closed: cwd is no longer an independent signal. New rule — if the
executable token is ABSOLUTE, cwd is never consulted (realpath must land
under root, full stop); if RELATIVE, cwd resolves it to an absolute path
BEFORE the same realpath-under-root check — the one legitimate role for
cwd. Empty token / unresolvable cwd are now explicit failures, never a
silent pass. Guilt (absolute-external + cwd-under-root still fails) +
innocence (relative-token + cwd-under-root correctly resolves) tests added.
58/58 green.

**Round 15 verdict: VERDICT CLEAN — wave-1 GO.** Confirmed no independent
cwd acceptance remains; symlink/`..`-traversal escapes resolve before the
boundary comparison; empty/unavailable cases fail explicitly. R13-3 and
R13-4 stand as accepted declarations (round-14's judgment not reopened).

**The gate arc for the drive-contact-autocreate program (rounds 6→15,
2026-07-19/20) is CLOSED with a CLEAN verdict.** Census v2.12 (post-fix,
population unchanged 275/317 across every cure since v2.9 — every round
closed a THEORETICAL gap, none touched the live book's actual candidate
set): digest `0c773f7af5547cf5c117aca06f985656e60994646b14fad7072723e179c2c4d9`.

Meta (closing the v3.4→v3.7 arc): ten rounds, one program, one shared
disease across every closed finding — **an artifact (manifest, attestation,
validator, ledger) trusted a PROXY for live/current/coherent state instead
of checking it directly** (census vs probe symmetry, worktree bytes vs
loaded worker, any-token vs the-executable, cwd-as-signal vs
cwd-as-resolution-aid, stdout verdict vs persisted state). The antidote
was always the same: name the proxy, replace it with the real check, write
the guilt case that the proxy would have missed. Two residuals (R13-3
mtime-backdating self-sabotage, R13-4 the freshness-to-ledger TOCTOU
window) are DECLARED, not fixed — logged in PENDING-ARMS with the
reasoning on record, because closing them fully requires either a
different threat model than this single-operator tool has, or a change to
worker.py itself (a follow-up lane, not a wave-1 blocker).
