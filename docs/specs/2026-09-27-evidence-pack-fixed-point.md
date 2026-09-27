# Evidence Pack contract — closing the fixed-point and four other gaps (S1-S4)

Status: PROPOSED 2026-09-27. Spec only — no code in this PR. Implementation lands in a follow-up
PR against `scripts/evidence_pack_lint.py` and, where noted, `.github/workflows/harness-floor.yml`.

Precedent and reason this file exists: PR #7430 → #7460 (owner-name → "Zero" codename sweep, 8
versions) carried **byte-identical, clean content** from v5 onward. Every red after v5 was about
the Evidence Pack's own numbers, not the diff. The final fresh gate (`gate-7460.md`, 2026-09-26,
CI run 36274224733) returned REWORK-DESIGN with a fifth wrong pack-only value. Builder Contract
§1: "a fix-of-a-fix stops at depth 1 — if the correction is itself wrong, the surface is
under-specified, so write the spec." This is that spec, scoped to the four gaps that made the
pack wrong through no fault of the author: S1 (a fixed point), S2 (blind spots in the digit
scanner), S3 (an attestation that cannot say what is actually true), S4 (claims that go stale
mid-session). Two further gaps in the same report (receipt-output capture, pre-arm collision
listing) are real but out of this PR's ≤180-line budget and are not addressed here.

## S1 — The size term is a fixed point

**Gap.** `scripts/evidence_pack_lint.py::_size_term_net_lines()` sums churn from
`git diff --numstat <merge-base> <HEAD>` (`harness-floor.yml` computes this numstat over the
**full** diff, no path filter, ~line 446). `_is_size_term_excluded()` (`scripts/
evidence_pack_lint.py:932-961`) excludes lockfiles, generated/vendored dirs, minified bundles and
binaries — but nothing under `evidence/`. So the size term includes the pack's own lines. Any
prose in the pack stating the full-diff size, or the floor source that size determines, is a
number the author needs _before_ writing the pack that produces it. Writing a bigger pack to
explain the size can itself flip the floor source.

**Evidence.** `gate-7460.md`: `brief.yml:9-10` and `pack.yml:7` claimed the full-diff size term
was "below 1828" (the size-term-floor-2 threshold) with floor source `path`. Measured: content-only
1200, evidence/pack+brief 664, full 1864 ≥ 1828 → floor source **both** (confirmed both by CI run
36274224733 and a local `--print-floor-source` re-measure). This is the same PR's **fifth**
pack-only wrong value across eight versions — a different wrong value each round (1634 → 1758 →
"below 1828" → floor-source → this one), never the same cause twice, which is exactly what an
under-specified surface looks like rather than a careless author.

**Rule.** Exclude `evidence/**` from the S1 size term. This is the only fix that actually kills
the fixed point: any variant that instead has the pack _state_ the size (a machine block the lint
fills or verifies) still changes the pack's own byte count when written, which changes the size
term again under the current (non-excluded) rule — a second-order fixed point, not a cure. Once
`evidence/**` is excluded, the size term is a pure function of the reviewable diff and is knowable
_before_ the pack is written, so the pack can state it truthfully in one pass. This mirrors the
existing exclusion philosophy (`_is_size_term_excluded()`'s docstring: exclude churn that doesn't
add review risk) — an Evidence Pack's own lines are exactly that: required scaffolding, not
content under review.

**Enforcement.** One sentence: add an `evidence/` top-level directory check to
`_is_size_term_excluded()` in `scripts/evidence_pack_lint.py` (by `PurePosixPath` first-part
match, same mechanism already used for `SIZE_TERM_EXCLUDE_DIR_NAMES`); no workflow change is
needed since `harness-floor.yml` already routes every size computation through this function via
`--print-floor` / `--print-floor-source` / `--numstat-file`.

**Migration.** No retroactive re-lint of packs already on `main` — floor is computed per-commit at
lint time, not stored. Any PR currently open with a Gear-3 pack (including this sweep's own
rebuild, below) re-measures once this lands; a floor that drops from `both`/`size` to `path` is
not a downgrade the gate needs to re-litigate, since the floor only ever asserted a _minimum_.

## S2 — Countable claims escape through unscanned fields

**Gap.** `check_countable_claims()` only walks `COUNTABLE_SUBTREES = ("diff", "lanes")`
(`scripts/evidence_pack_lint.py:3498`, via `_iter_countable_scalars()`). A digit-bearing claim
placed in `outcome`, a header comment, or top-level prose outside those two keys is invisible to
the rule. Separately, the rule's recognized claim _shapes_ are file-count and diffstat patterns
only (`_FILES_CLAIM_RE`, `_DIFFSTAT_CLAIM_RE`) plus `diff.*` int fields — it has no shape at all
for a "floor: N (source: X)" claim, which is exactly what went wrong here.

**Evidence.** `gate-7460.md`: the wrong floor-source restatement lived in `brief.yml:7,122,221`
and `pack.yml:5-6,70,97,195,263` (prose, not under `diff`/`lanes`) and passed
`evidence_pack_lint: clean` on CI run 36274224733 because nothing in rule 11 looks at floor claims
or at those keys.

**Rule.** Two changes, both needed: (1) scan the whole pack/brief document for the existing
file-count and diffstat shapes, not just `diff`/`lanes` — keep `dissent` and `receipts` exempt
(rule 11's own docstring: those are judgment prose where a number legitimately describes something
other than this diff) as a small denylist instead of the current allowlist, so a claim hiding in
`outcome` or a comment-adjacent scalar is no longer a blind spot. (2) add a new claim shape for
floor/floor-source prose (a regex over `floor:\s*(\d)` and `source:\s*(path|size|both|none)`
co-occurring near a `floor`/`gear` mention), compared against `compute_floor()` /
`compute_floor_source()` run with S1's exclusion applied — this is now a fair comparison because
S1 makes the floor knowable in advance.

**Enforcement.** One sentence: replace the `COUNTABLE_SUBTREES` allowlist walk in
`scripts/evidence_pack_lint.py` with a whole-document walk that exempts `dissent`/`receipts`, and
add a floor-claim regex + comparison alongside the existing file/diffstat checks in
`check_countable_claims()`.

**Migration.** No retroactive re-lint. The next Gear-3 pack (the sweep rebuild, below) is the
first one graded under the expanded scan.

## S3 — `pii_scan` cannot express "touches pre-existing PII"

**Gap.** `check_pii_scan_clean()` (`scripts/evidence_pack_lint.py:1402-1408`) requires the literal
string `"clean"`. It is a binary attestation with no room for "this diff's `+` lines carry PII
that was already on `main` and is not newly introduced" — a real and common state in a repo-wide
mechanical sweep.

**Evidence.** `gate-7460.md` Checks #6: `brief.yml:158` and `pack.yml:202` both say `pii_scan:
clean`, but the diff's `+` lines in `research/compliance/deep_audit_2026-04-24/plan.jsonl` carry
27 client-name hits (6 distinct clients) and 21 gmail addresses, all pre-existing on `main` and
unchanged in content by this PR's substitution. The author had no truthful value to write.

**Rule.** Replace the literal check with a structured value. `pii_scan: clean` keeps working
exactly as today. A new shape:
`pii_scan: {status: touches-preexisting-pii, introduced: 0, carried_preexisting: <N>, files:
[<path>, ...], disposition: "exclude-file" | "merge-after:#<PR>", scanner_cmd, scanner_sha}`.
Gate behavior, mirroring the existing `gear_override`/`appetite_exceeded` acknowledgment pattern
(rules 7 and 14): `introduced: 0` with a non-empty `disposition` → REPORTED (stderr NOTICE), not a
violation. `introduced > 0`, or `touches-preexisting-pii` with no `disposition`, or any other
non-`"clean"` literal → REJECTED. This gives the author a truthful value in exactly the case that
broke here, without weakening the guilt case (a diff that actually introduces PII still fails).

**Enforcement.** One sentence: rewrite `check_pii_scan_clean()` in `scripts/evidence_pack_lint.py`
to accept either the literal `"clean"` or a mapping matching the shape above, applying the
acknowledgment logic.

**Migration.** Packs already on `main` declaring the literal `"clean"` remain valid under the new
rule (it is a superset). No retroactive action.

## S4 — Cross-PR state claims carry no `as_of`

**Gap.** Nothing in the pack/brief schema requires a timestamp next to a claim about another PR's
state, and in a multi-PR lane those claims go stale within minutes.

**Evidence.** `gate-7460.md`: `brief.yml:260` claimed PR #7445 was OPEN; it had closed at
21:30:44Z, before this PR even opened. `brief.yml:90-91,254` and `pack.yml:136-137,343,355,360`
claimed #7457 was "open, owns the deferred files"; it closed at 22:11:17Z, mid-gate-session on the
very run (36274224733) being graded.

**Rule.** Every claim about another PR's OPEN/CLOSED/MERGED/ARMED state must carry an
`as_of: <UTC ISO8601>` next to it. The gate and the lint both treat this class of claim as
**informational only** — never a PASS/FAIL input — because staleness here is a race condition
inherent to a live merge queue, not a defect in the artifact. What the rule buys is not
correctness (no linter can keep a claim from going stale) but honesty about _when_ it was true, so
a gate session knows to re-check rather than trust.

**Enforcement.** One sentence: add a structural check to `scripts/evidence_pack_lint.py` that
finds any scalar matching a cross-PR reference pattern (`#\d{3,5}\b` co-occurring with an
open/closed/merged/armed state word) and requires it to sit in a mapping carrying `as_of`, else
NOTICE (never a violation — this is a hygiene signal, not a fact the linter can itself verify).

**Migration.** Packs already on `main` are exempt (no `as_of` field existed to violate). Applies
to packs authored after this ships.

## S6 — evidence for PII-removal lanes carries categories and counts only

**Gap.** A PII-removal diff can hold while its own evidence text keeps failing gate for the same
cause: naming a residual (out-of-scope) file, pairing a redacted id with a per-file occurrence
count, miscounting, or hedging a claim it should measure exactly. `check_pii_scan_clean()`
(`scripts/evidence_pack_lint.py:1402-1408`) and `check_countable_claims()` (`:3672`) both grade
the diff's own `+`/`-` lines; neither reads brief/pack/body prose for a path token, an
id-to-count pairing, or an egress claim, so an author can pass `evidence_pack_lint: clean` while
the evidence itself re-identifies what the diff just redacted or names a file the mandate ordered
kept out of the evidence.

**Evidence.** Three consecutive REWORK-BUILD rounds on the same PII-removal lane, each blocking on
this class and not on diff content: `gate-7474.md` H1 (pilot ids 70/266/283/350 re-linkable to
real names via three tracked files entered by path in the brief's own `out_of_scope` pointer) and
H2 (brief/pack/body claimed "every PRODUCTION extraction call TODAY" uses a legacy prompt — an
unmeasured live-egress claim — plus three wrong counts: "one of the names" for 2, "9 other files"
for 12, "9+2 fixture occurrences" for 13+4); `gate-7481.md` K1 (H2 carried forward unfixed), K2
(same three counts, now "9" for 11, still "one of the names"), K3 (H1 carried forward: the brief
named the two files a redacted pair maps through), K4 (`Bites:` regressed from a post-merge
`ls-tree`+pytest probe to a pre-merge lint self-check); `gate-7491.md` K2 (still "one of the
names", still wrong file/fixture counts) and K3 — the new regression — where the dissent itself
wrote "id 70 x1, id 83 x2" next to the two prompt-template filenames, which is a de-anonymization
key of the same class as the F1/G3 finding this lane had already cured once for a different pair
of client names.

**Rule.**

- R6.1 — no filename or path of any residual (out-of-scope) file appears in brief, pack or body.
  Categories and counts only.
- R6.2 — no client id, redacted placeholder or pilot id is paired with a per-file occurrence
  count, or with a filename, in the same claim. A count stands alone as a total; an id stands
  alone as "still re-linkable" or "no longer re-linkable".
- R6.3 — every count is produced by a command written in the evidence (the detector invocation)
  and re-measured at HEAD, not carried forward from a prior version's gate report.
- R6.4 — no "live" or "active" egress/consumer claim without a measured consumer (a process, cron
  entry or plist checked at HEAD); forbidden hedges: "one of", "some", "a few", "~N".
- R6.5 — `Bites:` for a PII-removal lane is a post-merge probe: `git ls-tree origin/main <paths>`
  → 0 plus a test run, never a pre-merge lint self-check.
- R6.6 — the builder runs and pastes into the PR body one mechanical pre-check before opening:
  `grep -nE '<residual-basenames>|one of|some of|~[0-9]' evidence/**/brief.yml pack.yml body` → 0
  hits, plus a `git grep` of every pilot/client id used as a plain string → 0 hits outside the
  evidence's own redacted-id table.

**Evidence for R6.2's specific shape:** `gate-7491.md`'s own dissent text — "id 70 x1, id 83 x2" —
next to two named prompt files is the mechanism: the count disambiguates which name maps to which
id once the filenames are also visible, exactly reproducing the re-identification `gate-7474.md`
G3 already found and cured for a different collision. The rule generalizes past this one lane: a
per-file count next to an id is a key regardless of which id or file it names.

**Enforcement.** Mechanically checkable now in `scripts/evidence_pack_lint.py`, without new
schema: R6.1 as a whole-document path-token scan (`git diff --name-only mb..head` supplies the
allowed set; any path-shaped token in brief/pack/body prose outside that set is REJECTED — the
same allow/deny shape `check_countable_claims()` already uses for `dissent`/`receipts`). R6.3 as
an extension of `check_countable_claims()`'s existing file-count/diffstat re-measurement: treat a
PII-lane count claim the same as a diffstat claim already is, comparing prose to a supplied
`--measured` value instead of only to numstat. R6.6's hedge words as a fixed regex denylist
(`\bone of\b|\bsome of\b|\ba few\b|~\d`) scanned over the same whole-document walk as R6.1 —
cheap, deterministic, no PII data needed to run it. Not mechanically checkable without a live PII
detector run inside CI (out of scope here, same boundary S3 already drew): R6.2's id↔count
pairing (requires knowing which tokens are ids) and R6.4's "measured consumer" claim (requires
process/cron state, not text). Both stay builder-attested per R6.6 and gate-verified by hand, as
`check_pii_scan_clean()` already treats the literal-vs-structured PII attestation.

**Migration.** No retroactive re-lint of packs already on `main`. Applies to any evidence pack for
a PII-removal or PII-redaction lane authored after this ships; a pack for an unrelated lane is
unaffected. `#7489` (S5, hot-zone egress) had not merged when this section was written — S6 is
appended after S4, not after S5, and re-sequences if S5 lands first.

## Ship order

1. **PII removal lands first.** #7462 (client-PII removal from `plan.jsonl`) merges before any
   further owner-name sweep PR opens — it is the higher-priority fix and it removes the file the
   sweep's own diff collides with (`gate-7460.md` Checks #3b: CONFLICT modify/delete, both merge
   orders). Its own gate rounds (v4 and on) are tracked separately from this spec.
2. **This spec's lint/workflow changes ship in a follow-up PR**, reviewed and merged on their own
   merit before the sweep is rebuilt against them.
3. **The sweep is rebuilt exactly once**, from a fresh `origin/main` (post #7462, post this spec's
   enforcement PR), reusing #7460's content diff minus `plan.jsonl` (`gate-7460.md`: 269 files,
   598 lines if nothing else has moved by then).
4. **The rebuild's pack is authored by the fixed-point method this spec enables**: measure the
   size term, floor, and floor source _after_ the final content commit (S1 makes this a stable,
   knowable number since `evidence/**` no longer feeds back into it); if a later edit is needed,
   change digits only inside already-existing lines so the line count — and therefore the size
   term — does not move again. `pii_scan` is written using S3's structured shape if any
   pre-existing PII remains in scope; every cross-PR claim carries `as_of` per S4.
