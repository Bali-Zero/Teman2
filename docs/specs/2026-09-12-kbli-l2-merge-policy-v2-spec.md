# KBLI L2 OSS-risk MERGE POLICY v2 — deterministic donor allocation and verdict-transition spec

## 0. Status and scope

DRAFT, 2026-09-12. Nothing here is implemented. This spec governs a **follow-up, code-only PR**
against `scripts/build_kbli_l2_oss_risk.py`, `scripts/kbli_filiera/vault_tier_changeset.py` and
`scripts/kbli_filiera/tests/test_l2_merge_policy.py`. PR-B (#6269)'s shipped `v11.0-L2-oss-risk`
canonical data is **out of scope** except where a rule below states how to prove the follow-up PR
reproduces it byte-for-byte (§9). This spec does not re-litigate `docs/specs/2026-09-11-kbli-l2-oss-resnapshot-reingest-spec.md`
§6/§7 (cited below); it resolves what a second adversarial council round found still
under-specified in the cured diff (`evidence/2026-09/agent-air-m5-kbli-l2-pr-b-policy-d805736d/council-journal.jsonl`,
entries 4-5, round 2, 2026-09-12, codex-gpt-6-astra and kimi-code/k3, both **BLOCKING**).

Round 1 (entries 1-3) had already forced one fix-of-a-fix (`_drop_donor`, module docstring
`build_kbli_l2_oss_risk.py:158-163`, commit "a canonical row donates once across both pools").
Round 2 found the **same HIGH survives in a new shape** — donor allocation is still
input-order-dependent — plus a **second HIGH** on verdict transitions. Per the Builder Contract
("fix-of-a-fix stops at depth 1 — if the correction is itself wrong, the surface is
under-specified, so write the spec"), this document is that spec.

## 1. Vocabulary

- **Canonical row**: one entry of `per_skala[]` on a code's record in
  `data/source_documents/KBLI_2025_FINAL_CLEAN.json`, as it stood before this run (`old_ps`,
  `build_kbli_l2_oss_risk.py:322`).
- **OSS row**: one entry of `per_skala[]` freshly parsed from the OSS `ruang_lingkup` payload for
  this run (`new_ps`, produced by `parse_per_skala`, `:99-143`).
- **Donor**: a canonical row consumed by `merge_per_skala` (`:171-218`) to supply an OSS row with
  fields the OSS payload does not carry.
- **Scope identity** (`_row_key`, `:149-151`): the triple `(scope_uraian.strip(), tuple(skala_usaha),
kategori_risiko.strip().lower())`.
- **Tier key** (`_tier_key`, `:154-155`): `(tuple(skala_usaha), kategori_risiko.strip().lower())` —
  scope-blind.
- **L2-owned fields** (`L2_OWNED_PER_SKALA_FIELDS`, `:76-79`): `skala_usaha`, `kategori_risiko`,
  `scope_index`, `scope_uraian`, `perizinan`, `persyaratan`, `kewajiban`, `kewenangan` — always
  taken from the OSS row, never from a donor.
- **Carried fields**: everything else a donor may hold — named explicitly for the tier-only path
  as `TIER_LEVEL_CARRY = ("jangka_waktu_source", "fiktif_positif")` (`:146`); on a scope-identity
  match every non-L2-owned, non-`jangka_waktu` key is carried (`:190-192`), which in practice
  also includes `pb_umku`, `sanksi_*` and any other later-layer key the docstring names (`:30`).
- **Fresh row**: an OSS row with no donor in either pool — goes through the `AUTOMATIC` branch
  (`:211-213`) or the dirty/clean branch (`:214-215`).
- **Split scope**: an OSS scope whose `scope_uraian` no longer matches any canonical row's scope
  (renamed or split, e.g. `"Seluruh"` → `["Sub A", "Sub B"]`) but whose `(skala, tier)` existed —
  eligible only for the tier-only pool.
- **Verdict**: one of `OPEN` / `AMBIGUOUS` / `BLOCKED` / `NO_BESAR`, computed by
  `besar_block_verdict` (`:231-264`) from the Besar-scale rows of `new_ps`.
- **`l4_bali` transform-owned statuses**: the three literal strings this transform itself writes
  — `BLOCCATO_CLASSE_RISCHIO`, `BLOCCATO_DIPENDE_SCOPE`, `OK_or_HIGHER_RISK` (`:399-401`).
- **Cure-owned `l4_bali` block**: any record whose `l4_bali.status` is **not** one of the three
  strings above — includes `PRESERVE_STATUSES` (`:83-84`), `verdict_state`-only blocks (237 live
  records per council entry 5), and statuses such as `CHIUSO_MORATORIA_BALI` /
  `CHIUSO_PMA_NO_BESAR` / `NON_CLASSIFICABILE` that a later cure layer wrote.

## 2. Donor allocation — the decidable rule

**Two-pass, input-order-independent.** `merge_per_skala` must allocate donors in two passes over
`new_ps`, not interleaved per row as today (`:185-210`):

1. **Pass 1 — scope identity.** Iterate `new_ps` once; for every row whose `_row_key` matches a
   remaining entry in `by_scope`, claim that donor (FIFO within the same key's list, as
   `test_duplicate_keys_donate_once_in_order` already pins) and immediately remove it from
   `by_tier` too (`_drop_donor`, unchanged). Do **not** attempt a tier-only fallback for any row
   in this pass.
2. **Pass 2 — tier fallback.** Iterate the new rows left unmatched after pass 1, in the same
   order; for each, claim a donor from what remains of `by_tier` (already scope-claimed donors
   are gone).

**Invariant:** for a fixed `old_ps`, permuting the rows of `new_ps` yields the same merged output
up to row order — i.e., which canonical row donates to which OSS row does not depend on which row
the OSS API happened to list first.

**Why today's single pass violates it.** Round 2's codex and kimi findings name the same defect
twice: `build_kbli_l2_oss_risk.py:199` ("the tier fallback consumes donors before later exact
scope matches") and `:185-210` + `test_l2_merge_policy.py:342-349` ("a tier-only match steals the
donor from a later scope-identity match when the original scope survives in `new_ps`").
Concretely: `old_ps = [Seluruh/Besar/Tinggi carrying fiktif_positif]`; OSS now returns
`new_ps = [Sub A/Besar/Tinggi, Seluruh/Besar/Tinggi]` — a split scope _and_ the original scope, in
that order (OSS's actual order, not a construct). Today's per-row loop processes `Sub A` first,
finds no scope match, falls through to the tier pool, and **wins** the donor via
`_pop_donor(by_tier, ...)` at `:199` — before `Seluruh`, the row genuinely identical to the donor,
gets a turn; `_drop_donor` at `:201` then empties `by_scope` too, so `Seluruh` gets nothing.
Reverse the OSS order to `[Seluruh, Sub A]` and the outcome flips: `Seluruh` now wins the scope
match, `Sub A` gets nothing. Same code, same donor, two different owners, decided only by the
order OSS happened to enumerate the scopes. `test_l2_merge_policy.py:342-350`
(`test_a_tier_donor_is_never_reused_by_scope_identity`) currently _asserts_ the wrong-order
outcome (`[True, False]` for `[Sub A, Seluruh]`) as correct — the endorsement round 2 names.

Under the two-pass rule both orderings resolve identically: pass 1 scans every row for a scope
match before any tier fallback runs, so `Seluruh` claims the donor regardless of position, and
`Sub A` is left to the (now-empty) tier pool and becomes fresh. §8 names the rewritten test.

## 3. Carried fields on match vs split

- **Scope-identity match** (pass 1): the OSS row keeps every L2-owned field from OSS. Every other
  key the donor holds — `jangka_waktu_source`, `fiktif_positif`, `pb_umku`, `sanksi_*`, any future
  later-layer key — is carried verbatim (`:190-192`), because the scope is provably the same
  activity: nothing about the donor's non-L2 facts stopped applying.
- **Tier-only match** (pass 2, split scope): only `TIER_LEVEL_CARRY` — `jangka_waktu_source`,
  `fiktif_positif` — may be carried (`:202-204`). A scope-specific key such as `pb_umku` or a
  `sanksi_*` entry is a fact about _that named activity_, not about the (skala, tier) pair in the
  abstract; carrying it across a rename/split would attach one scope's penalty or licence history
  to an unrelated new scope. This is already correct in the current code and unaffected by §2's
  two-pass change; §8 keeps the existing guilt/innocence pair for it
  (`test_scope_split_carries_only_tier_level_facts`).
- **Fresh row** (no donor in either pool after both passes): carries nothing. Its `jangka_waktu`
  is decided by §4.

## 4. `jangka_waktu` rules

Definitions: `is_clean_jangka(v)` (`:65-66`) accepts `"Otomatis"`, a bare 1-3 digit count, or
`"N Hari[ Kerja]"`; anything else (`""`, `"-"`, garbage) is dirty. `jangka_waktu_source` marks a
value as **sourced** — written by a named later-layer enrichment, not raw OSS text.

1. **Never write a dirty value, in any branch.** Whatever candidate a branch computes for
   `jangka_waktu`, if `is_clean_jangka(candidate)` is false, the row's `jangka_waktu` becomes `""`
   instead of the dirty candidate. This must apply uniformly to the scope-identity carry
   (`:193-194`), the tier-only carry (`:205-206`) and the fresh branch (`:214-215`) — today only
   the fresh branch enforces it; the two carry branches copy `o.get("jangka_waktu")` /
   `t.get("jangka_waktu")` verbatim even when that stored value is itself dirty (kimi round 1,
   `:182-186`: "a scope-matched row copies the old jangka_waktu verbatim when OSS sends a dirty
   value, so a dirty '-' can be written").
2. **Never overwrite a clean OSS value with the `AUTOMATIC` default.** In the fresh branch
   (`:211-213`), a Rendah/Menengah-Rendah tier currently forces `jangka_waktu = "Otomatis"`
   unconditionally, even if OSS's own `new_ps` row already carried a clean value (e.g. `"5"`).
   The rule: check `is_clean_jangka` on the OSS-supplied value **first**; only fall back to
   `"Otomatis"` (and stamp `jangka_waktu_source = "PP28_rule_risk_class"`) when OSS's own value is
   not clean. `"Otomatis"` is the answer for silence, not an override of a legitimate OSS answer
   (kimi round 2, `:211-213`: "clobbers a clean OSS value and mak[es] it sticky via
   jangka_waktu_source" — the stamped source then makes the wrong value sticky per rule 3 below).
3. **Which `jangka_waktu_source` each branch stamps:**

   | branch                                               | stamps a NEW source?                                              | value                                        |
   | ---------------------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------- |
   | scope-identity match                                 | no — carries donor's own `jangka_waktu_source` key if present     | donor's `jangka_waktu` (subject to rule 1)   |
   | tier-only match                                      | no — carries donor's `jangka_waktu_source` via `TIER_LEVEL_CARRY` | donor's `jangka_waktu` (subject to rule 1)   |
   | fresh, automatic tier, OSS value not clean           | yes                                                               | `"PP28_rule_risk_class"`, value `"Otomatis"` |
   | fresh, automatic tier, OSS value clean (new, rule 2) | no                                                                | OSS's own clean value                        |
   | fresh, non-automatic tier, OSS value not clean       | no                                                                | `""`                                         |
   | fresh, non-automatic tier, OSS value clean           | no                                                                | OSS's own clean value                        |

4. **Stickiness is intended, bounded by rule 1.** Once `jangka_waktu_source` is set on a canonical
   row — by this transform or by `scripts/enrich_kbli_jangka_waktu.py` — every future run that
   matches that row (scope or tier) preserves its `jangka_waktu` instead of taking a fresh,
   possibly-dirty OSS value (`o.get("jangka_waktu_source")` truthy branch condition, `:193`,
   `:205`). This is deliberate: a sourced value is a deliberate enrichment decision, not raw OSS
   text, and only a cure or `enrich_kbli_jangka_waktu.py` itself should change it. Rule 1 bounds
   it — a sourced value that is itself somehow dirty is never perpetuated; it degrades to `""`
   rather than sticking forever.

## 5. `l4_bali` rewrite rule

**Rewrite `l4_bali` iff the code's current `l4_bali.status` is one of the three transform-owned
strings (§1) AND the newly computed verdict differs from what that status encodes** — measured by
`new_l4_status != old_status` OR `new_blocked != old_blocked` (either is sufficient; together they
cover OPEN↔AMBIGUOUS, which both carry `blocked=False` and so are invisible to a blocked-flag-only
check, and BLOCKED↔{OPEN,AMBIGUOUS}, which flip `blocked`).

This replaces two things in the current code:

- **`l4_verdict_moved`'s reliance on a `"verdict"` key** (`:221-228`, `test_l2_merge_policy.py:353-363`).
  237 live records carry `verdict_state` instead of `verdict` (council entry 3); comparing against
  a missing key manufactured moves and clobbered cure labels (kimi round 1 H2, `93111`/`93119`
  `CHIUSO_MORATORIA_BALI → BLOCCATO_CLASSE_RISCHIO`). The fix in place (only a `blocked` flip
  counts when `"verdict"` is absent) _overcorrects_: it also suppresses a genuine `OPEN →
AMBIGUOUS` move on records whose `status` **is** transform-owned but whose `verdict` key is
  missing (codex round 2 HIGH: a new low-risk Besar scope beside a high-risk one computes
  AMBIGUOUS but keeps `status=OK_or_HIGHER_RISK, verdict_state=open`). `status` is always present
  and always transform-authored when it is one of the three owned strings, so comparing `status`
  — not `verdict` — is decidable regardless of whether a later pass also wrote `verdict_state`.
- **No cure-ownership check before a rewrite fires on a `NO_BESAR`-turned-verdict code.** Today
  `NO_BESAR` skips the rewrite (`l4_moved = False` unconditionally, `:388-395`) — correct while the
  code stays `NO_BESAR`. But 20 live codes carry `l4_bali = {verdict: "NO_BESAR", blocked: true,
status: "CHIUSO_MORATORIA_BALI", ...}` (kimi round 2 MED). `CHIUSO_MORATORIA_BALI` is **not** in
  `PRESERVE_STATUSES` (`:83-84`), so once a future snapshot adds a Besar row, the code exits the
  `NO_BESAR` branch, the verdict recomputes to e.g. `OPEN`, `new_blocked=False != old_blocked=True`,
  and the ordinary flip path (`:403-434`) rewrites `status` to `OK_or_HIGHER_RISK` — silently
  discarding the moratorium closure a human cure had recorded, because the code checked only
  whether the _flag_ changed, not whether the _record_ was ever the transform's to rewrite.

**Rule, stated once:** widen the ownership test used everywhere a rewrite is gated — not
`old_status not in PRESERVE_STATUSES` (`:384`), but `old_status in
{BLOCCATO_CLASSE_RISCHIO, BLOCCATO_DIPENDE_SCOPE, OK_or_HIGHER_RISK}`. Any code outside that set —
including today's `PRESERVE_STATUSES` and every other cure status — is cure-owned: `l4_bali` is
**never** auto-rewritten by this transform, `NO_BESAR` or not. When such a code's freshly computed
verdict would, if applied, produce a different `status`/`blocked` than what the cure recorded,
emit one row to a **review-flag list** printed in the `SUMMARY` line (§8 replaces the current
hardcoded `needs_review = 0` at `:473` with the real count) instead of writing it. Rationale: a
cure status exists precisely because a human or a dedicated adjudication layer
(`cure_l4bali_perpres_adjudication.py`) decided the block on grounds this transform cannot
re-derive from OSS risk tiers alone (Perpres 49/2021 Lampiran II, moratorium exceptions); silently
flipping it on a data refresh is the same class of error §7 ruling 1 of the September spec already
withdrew for the `NO_BESAR` inference itself.

## 6. Absence episodes

Two decisions, both currently unresolved in the code:

1. **`--apply` without `--fetched` on a 404 for a previously-scoped code: fail closed.** Today
   (`:350-355`) the record is unconditionally stamped `_l2_status = ABSENT_PENDING` and
   `absent_probes` is (re)written even when `args.fetched` is `None` — `probes` can be
   materialized as `[]` with no dated evidence appended (codex round 2 MED, `:353`; kimi round 1
   LOW, `:332-334`; kimi round 2 LOW, `:352-355,473`). Methodology P3 counts corroboration in
   **dated** probes ≥72h apart; an undated or empty `absent_probes` entry cannot be corroborated
   and cannot expire, so it is worse than not recording anything. **Rule:** when `--apply` is
   passed and a previously-scoped code 404s without `--fetched` on the command line, the transform
   leaves that record completely untouched (as if `no_evidence`), increments a new
   `absent_needs_fetched` counter, and the `SUMMARY` line reports it — forcing a rerun with
   `--fetched` before the code counts toward the P3 clock at all. This is a per-record skip, not a
   process-wide hard failure (§10 raises the harder question of whether it should be).
2. **A 200 whose scope exists but has zero risk rows: closes the episode.** `parse_per_skala`
   returning `[]` (`:363-367`, `empty_oss_risk`) neither pops a stale `absent_probes` list nor
   resets a prior `absent_pending_corroboration` status — codex round 2 MED (`:363`: "a 200 with a
   scope but no risk rows leaves the previous absence episode open"). **Rule:** treat a 200 with a
   non-empty `data` array (the scope endpoint answered) as presence for the purpose of closing an
   absence episode, exactly like the non-empty branch already does (`rec.pop("absent_probes",
None)`, `:417,440`) — the endpoint existing, even with no risk rows to report, is stronger
   evidence than a 404, and P3's asymmetric bar (removal needs corroboration, presence does not)
   applies the same way here. `_l2_status` is still set to `"empty_oss_risk"`, distinct from both
   `"absent_pending_corroboration"` and `"no_oss_risk"` (never had scope) — it records a real,
   distinct signal (scope exists, no risk rows today) without perpetuating the closed episode's
   stale probe dates.
3. **Quarantine skip is unchanged** (`:326-333`): a `per_skala_disputed_*` key skips the record
   before any absence logic runs, regardless of 200/404. No rule change; §8 keeps the existing
   guilt/innocence pair for it.

## 7. Change-set reader (`vault_tier_changeset.py`)

`read_triples` (`:51-55`) returns `None` for both "this code has no file at this vault root"
(expected — feeds `old_only`/`new_only`, `changeset()` `:62-69`) and "this vault root does not
exist at all" (a caller error — wrong `--old`/`--new` path). Today both look identical to
`changeset()`: if a code is missing on **both** sides it is silently skipped (`:62-63`, `continue`)
— counted in neither `changed`, `old_only`, `new_only`, nor `both`. Two nonexistent root paths
therefore produce `both=0 changed=0 old_only=[] new_only=[]`, exit 0 (codex round 2 MED, `:53`:
"two nonexistent vault paths pass as changed=0 exit 0") — a typo'd path is indistinguishable from
"the two vaults are identical and nothing new was published."

**Rule:** `changeset()` (or `main()` before calling it) must check `old_root.is_dir()` and
`new_root.is_dir()` and raise (`SystemExit(2)` from `main()`, an exception from the library
function) with a message naming the missing path, **before** iterating any code. A missing
_per-code file_ under an existing vault root stays exactly as it is today — legitimate
`old_only`/`new_only` evidence, never an error.

## 8. Test contract

For every rule above: a guilt test (a mutation that must turn the test red under today's code) and
an innocence test (the rule's correct behaviour, unchanged by an unrelated mutation). Hermetic —
no unit test reads the live `data/source_documents/KBLI_2025_FINAL_CLEAN.json`; every test builds
its `old_ps`/canonical slice from an in-file fixture or an inline dict.

| rule                                     | guilt test                                                                                                                                                                                                                                                                  | innocence test                                                                                                                                                                                                                                                                                                                                                                                                  |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| §2 two-pass allocation                   | feed `new_ps = [Sub A, Seluruh]` (today's `test_a_tier_donor_is_never_reused_by_scope_identity`, **rewritten**: rename to `test_donor_allocation_is_order_independent`, assert scope-identity wins → `[False, True]`, i.e. `Sub A` has no `fiktif_positif`, `Seluruh` does) | run the same fixture with `new_ps` reversed to `[Seluruh, Sub A]`; assert the merged output is identical up to row order (the permutation invariant of §2)                                                                                                                                                                                                                                                      |
| §4.1 never write dirty on carry          | donor's own stored `jangka_waktu = "-"`, OSS sends `"-"` too → merged `jangka_waktu == ""`, not `"-"`                                                                                                                                                                       | donor's stored value is clean (`"7"`) → preserved as today                                                                                                                                                                                                                                                                                                                                                      |
| §4.2 clean OSS beats `AUTOMATIC` default | fresh Rendah-tier row, OSS `jangka_waktu = "5"` (clean) → merged value stays `"5"`, no `jangka_waktu_source` stamped                                                                                                                                                        | fresh Rendah-tier row, OSS `jangka_waktu = "-"` → `"Otomatis"` + `jangka_waktu_source = "PP28_rule_risk_class"`, as today                                                                                                                                                                                                                                                                                       |
| §5 status-gated rewrite                  | canonical `l4_bali = {verdict: NO_BESAR, blocked: True, status: CHIUSO_MORATORIA_BALI}`, feed a Besar-Tinggi row so the verdict recomputes `OPEN` → `l4_bali` byte-identical after the run, one row appended to the review-flag list                                        | canonical `status = OK_or_HIGHER_RISK, verdict_state: "open"` (no `verdict` key), feed rows that recompute `AMBIGUOUS` → `status` rewritten to `BLOCCATO_DIPENDE_SCOPE` (this is the rewrite of today's `test_l4_is_rewritten_when_the_verdict_moves`, `:201-216`, which today only exercises the `blocked`-flip case; add this OPEN→AMBIGUOUS-without-a-verdict-key case as a second method on the same class) |
| §6.1 fail-closed on missing `--fetched`  | previously-scoped code 404s, `--apply` with no `--fetched` → record byte-identical to before, `absent_needs_fetched` counter is 1                                                                                                                                           | same code, `--apply --fetched 2026-09-11` → `absent_pending_corroboration` + `absent_probes == ["2026-09-11"]`, as today's `test_lost_scope_is_pending_not_absent_and_never_had_scope_stays_no_oss_risk`                                                                                                                                                                                                        |
| §6.2 empty-scope 200 closes the episode  | code has `absent_probes = ["2026-09-01"]`, next run 200s with `data: []` risk rows for that scope → `absent_probes` popped, `_l2_status == "empty_oss_risk"`                                                                                                                | a code with no prior absence episode gets the same empty-risk 200 → `_l2_status == "empty_oss_risk"`, no `absent_probes` key ever created                                                                                                                                                                                                                                                                       |
| §7 missing vault root                    | `changeset(Path("/does/not/exist"), Path("/also/missing"), gt)` → raises                                                                                                                                                                                                    | existing roots, one code missing on both sides → skipped silently, `both`/`changed` unaffected, as today's `test_changed_old_only_new_only`                                                                                                                                                                                                                                                                     |

Two existing tests must be rewritten, not just left passing, because they pass for the wrong
reason:

- `test_canonical_no_besar_codes_keep_their_perpres_layer_labels` (`:134-150`) reads the live
  `CANONICAL` file — non-hermetic (kimi round 2 MED, `:31,134`). Rewrite it against a fixture slice
  containing at least one transform-owned-status Besar-scope code and one cure-owned-status
  `NO_BESAR` code, asserting the same two properties (no "reserved for UMKM" text; any
  `CHIUSO_PMA_NO_BESAR` reason cites "Lampiran II") on the fixture instead of production data.
- `test_l4_is_rewritten_when_the_verdict_moves` (`:201-216`) only exercises the `blocked`-flag
  flip (`BLOCKED → OPEN`). Add the OPEN↔AMBIGUOUS-without-a-`verdict`-key case from the §5 table
  above as a second test method in the same class, so the status-gated comparison (not just the
  flag) is under test.

## 9. Regeneration proof for the follow-up PR

Run the v2 transform against `origin/main`'s canonical with the frozen September raw
(`/tmp/l2b/sept.jsonl`, vault manifest sha256
`e18a5cf3fb99e99de81cc4ea502c96ccb4cbc759f08195d7069a171df8bfb955` — the same manifest quoted in
the September spec §7 and PR-B's evidence pack). **Acceptance:** either (a) byte-identical to the
shipped `v11.0-L2-oss-risk` canonical already on `main` — v2's rule changes happened to touch no
row PR-B's data actually contains — or (b) a listed, per-code diff between the v2 output and the
shipped canonical, with each differing code attributed to one of §2/§4/§5/§6/§7 by name. No
silent, unattributed change is acceptable; the diff table is part of the follow-up PR's evidence
pack, same as the September spec's rule-5 field table (§6 of that spec).

## 10. Open questions for the owner (Zero)

1. **Enforcement level of §6.1's fail-closed rule.** The spec above has `build_kbli_l2_oss_risk.py`
   skip the individual record and report an `absent_needs_fetched` counter in `SUMMARY`, without
   failing the run. Should a nonzero `absent_needs_fetched` count also make the **process** exit
   nonzero (so CI/the ship-lifecycle gate treats "some absences were recorded without a date" as a
   hard stop, not an advisory line to notice), or is a `SUMMARY` counter plus a PENDING-ARMS row
   the intended level of friction? This is a ship-lifecycle policy choice, not something decidable
   from the current code or the September spec.
