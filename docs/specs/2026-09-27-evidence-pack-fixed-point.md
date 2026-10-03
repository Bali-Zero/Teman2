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

**Gap.** A PII-removal diff can hold while its own evidence text keeps failing gate for a
different, recurring cause: naming a residual (out-of-scope) file, pairing a redacted id with a
per-file occurrence count, miscounting, or hedging a claim it should measure exactly.
`check_pii_scan_clean()` (`scripts/evidence_pack_lint.py:1402-1408`) compares `pack["pii_scan"]`
against the literal string `"clean"`; `check_countable_claims()` (`:3672`) compares scalars under
`diff`/`lanes` (`COUNTABLE_SUBTREES`, `:3498`) against `git diff --numstat` totals. Neither reads
`dissent`, `receipts`, or free prose for a path token, an id-to-count pairing, or an egress claim
— so a pack can pass `evidence_pack_lint: clean` while its own text re-identifies what the diff
just redacted, or names a file the mandate ordered kept out of the evidence.

**Evidence.** Four fresh-gate rounds on the same PII-removal lane found this recurring class:
`gate-7472.md` G3 (a residual-sweep collision the evidence's own disclosure linked to a specific
file, re-identifying a client — first found here, carried forward unfixed into the next round);
`gate-7474.md` H1 (5 of 6 redacted pilot ids — all but one — re-linkable to real names via 4
tracked files, two of which the brief's own `out_of_scope` pointer named by path) and H2
(brief/pack/body claimed "every PRODUCTION extraction call TODAY" uses a legacy prompt — an
unmeasured live-egress claim — plus wrong counts: "one of the names" for 2, "9 other files" for
12, "9+2 fixture occurrences" for 13+4); the same round also blocked on G2, a test-fixture string
carrying a real client's name inside the diff itself — a different, in-diff-content class S6 does
not cover — and disclosed G5 (residual out-of-scope files), also out of S6's scope.
`gate-7481.md` K1 (H2 carried forward unfixed), K2 (same wrong counts, "9" now for 11, still "one
of the names"), K3 (H1 carried forward: the brief named 3 of the same residual files by path,
called "the same real names/ids", and the pack additionally described one of them by its
"PASSPORT NUMBERS in cleartext" content — a locator on top of the path), K4 (`Bites:` regressed
from a post-merge `ls-tree`+pytest probe to a pre-merge lint self-check). `gate-7491.md` K2 — the 11 files and 13+4+1 fixture
occurrences were by then measured TRUE; what was still FALSE was "the same 6 client_ids/7 names
... remain in clear ... across 11 files" (measured: 5 of 6 ids, 5 of 7 names) and "the names occur
twice" (measured: 3 occurrences per file) — and K3, a new regression, where the dissent itself
paired each of two redacted pilot ids with its own per-file occurrence count, next to the two
legacy prompt-template filenames: a per-file count paired with an id, next to the filenames it
disambiguates, is a de-anonymization key of the same class as the G3 finding this lane had already
cured once for a different pair of names.

**Rule.**

- R6.1 — no filename, path, or other locator that isolates one specific residual (out-of-scope)
  file (a content descriptor that in fact isolates one file — e.g. naming the kind of document
  data it holds, or a tracked-since date paired with a distinctive dataset size — counts the same
  as a path; a descriptor is only in scope here if it is actually narrowing, not merely evocative)
  appears anywhere in brief,
  pack, or body, **including inside `dissent` and `receipts`** — that is exactly where the K3
  regression sat. Categories and counts only.
- R6.2 — no client id, redacted placeholder, or pilot id is paired with a per-file occurrence
  count, or with a filename or locator covered by R6.1, in the same claim. A count stands alone as
  a total; an id stands alone as "still re-linkable" or "no longer re-linkable".
- R6.3 — every count — including a claimed total, an absolute/negative claim ("no other file
  references these names"), and a de-identification certification ("every client name replaced")
  — is produced by a command written in the evidence and re-measured at HEAD, not carried forward
  from a prior version's gate report. The single canonical list of forbidden hedges for any such
  claim is: "one of", "some", "a few", and an unqualified "~N" — except an approximate range (e.g.
  "~30-36") is allowed when the evidence names two disagreeing detectors and both counts, since no
  single re-measurable number exists to state instead.
- R6.4 — no "live" or "active" egress/consumer claim without a measured consumer (a process, cron
  entry, or plist state checked at HEAD).
- R6.5 — `Bites:` for a PII lane is a post-merge probe, never a pre-merge lint self-check: for a
  deletion, `git ls-tree origin/main <paths>` → 0; for a redaction (the file stays, only its
  content changes), the same detector command R6.3 requires, re-run against `origin/main` post-
  merge, must show 0 hits of the redacted tokens in the redacted paths — where the same command at
  the merge-base showed > 0, so a no-op "redaction" cannot pass; either way, plus a test run.
- R6.6 — the builder checks against the body **file** it will pass to `gh pr create
--body-file` (not `gh pr view`, which cannot exist before the PR does). The residual-basename
  list is private and reproducible: the lane's GATE session writes it, from its own report, to
  `~/.agent/pii-quarantine/<lane>/r66-residuals.txt` on the lane's host (0600, inside a 0700 dir,
  never committed) — one basename per line, defined as: a file tracked at HEAD that still carries
  the lane's PII AND is absent from `git diff --name-only <mb>..HEAD` (a file the diff touches is
  never a residual, so this is never "39 vs 0" depending on whose list is used). The R6.3 hedge
  list is already public, so it does not belong in this file. Builder command:
  `grep -c -F -f <file> <brief> <pack> <body-file>` plus `grep -c -w -E '<R6.3 hedge list>' <same
three files>`. The PR body pastes only `r66: hmac=<12 hex> lines=<N> residual_hits=<a>
hedge_hits=<b>` (amended by R6.7: the first form, `sha256=<12 hex>`, is a plain hash, and a plain
  hash of a short residual list is a verification oracle) — never the pattern file's contents; the token is emitted by `pii_receipt.py r66`, and the grep
  commands define the counts and serve as their manual cross-check; if `b > 0`, list each hedge hit by line
  number as a quoted citation per the Innocence case below, rather than claiming `b` must be 0. The
  gate verifies by re-running `pii_receipt.py r66 … --check-in` (R6.7) at HEAD for the same token
  and counts, and cross-checking the file against its own report (`N` consistent, 0 basenames
  from inside the diff). A companion id check runs the same three files with `grep -w`, never
  repo-wide (a repo-wide digit search can never reach 0), and checks for an id sitting on the same
  line as a count or an R6.1 locator, not for the bare digit.
- R6.7 — receipts are generated, never typed. Every countable claim R6.3 requires — files,
  occurrences, the per-category split, fixture counts, the R6.6 `r66:` line, the R6.5 redaction
  probe before and after — is the output of the committed script `scripts/evidence/pii_receipt.py`
  run at the FINAL head, pasted into pack.yml VERBATIM as the script's own block. The block names
  the script path, its git blob sha, and the exact invocation (argv, with each private input and
  each `--path` replaced by `@hmac:<16 hex>`, HMAC-SHA256 keyed by the lane salt the script keeps
  beside R6.6's file, 0600 in a 0700 dir, never committed; the token is how a gate proves it
  re-ran on the same bytes, and it is keyed because a plain hash of a one-line category map is
  reversed by hashing every tracked path; the salt is lane state, restored together with the
  private files, and rotating it invalidates earlier blocks). It carries no commit sha, because pasting it moves
  HEAD; it carries `tree_digest` instead — sha256 over (mode, blob, path) of every tracked file outside
  `evidence/`, whatever `--path` scopes the count to — which an edit to the pack cannot move and
  any other edit does. A changed script changes `blob=` and so invalidates every earlier block. Metrics, so no two
  detectors disagree silently: `hits` = per pattern, the lines containing it, summed (one
  `git grep -n -F` per pattern); `lines_any` = lines containing any pattern (`git grep -c -F -f`);
  `occurrences`; `files`; `patterns_present`. The `r66:` line in the body is the block's
  `r66_line` value; its argv binds the brief and the body file by `@text:` digests (CRLF and
  trailing newlines normalised), and exempts only the pack, which holds the block. Prose restates a number only as a quoted block key ("`hits: N` per the head
  block"). A gate re-runs each invocation with `--check-in <pack.yml>`. **Guilt:** a pasted block
  with one digit edited → exit 1 (MISMATCH); a countable claim with no block for its invocation →
  exit 4 (NO-BLOCK); both are red, and a hand-typed number is red even when it is correct, since
  "re-measured by hand" is exactly what each round below claimed. **Innocence:** the same
  invocation after edits confined to `evidence/` → exit 0, byte-identical for `scope_files` and
  `tree_digest`, which exclude `evidence/`; `tree`'s own counts (`files`/`hits`/`lines_any`/
  `occurrences`/`patterns_present`) include `evidence/`'s tracked files by design, so a block is
  byte-identical after an `evidence/`-only edit only while that edit adds no pattern to
  `evidence/`; a prior version's wrong number quoted for correction per the Innocence case.
  **Acceptance:** for every block, `python3 scripts/evidence/pii_receipt.py <mode> <same argv,
private files by path> --check-in <pack.yml>` → 0, and `python3
scripts/evidence/pii_receipt.py --selftest` → PASS; for a `descriptor` block, R6.8's acceptance
  form binds instead of this generic one — a same-argv `--check-in` can still pass an argv that
  omits `--categories` or that floors `--min-files` below 2, both of which R6.8 forbids.
- R6.8 — descriptor non-isolation is measured, not asserted. A category descriptor R6.1 allows
  ships with its predicate: the ordered conjunction of path and content terms its own words assert
  (`pii_receipt.py descriptor --path/--not-path/--text/--not-text`, evaluated over tracked text
  files at HEAD, `evidence/` excluded), pasted per R6.7. The block must show `files` ≥ 2 and
  `covers_category: n/n` — every file of the category, read from the lane's private categories
  file, satisfies the predicate; a count over words the described file does not contain measures
  nothing. `progressive_files` gives the count after each term, so a gate sees which term
  isolates. A descriptor that names script type, file format and field set together is
  presumptively isolating and never ships without its block. A correction note that explains why
  a prior descriptor isolated is itself a descriptor: "the prior descriptor isolated one file" is
  the whole note. `--min-files` never goes below 2, and a block without `covers_category: n/n` is
  red: running without `--categories` cannot show a category coverage fraction, so its verdict is
  UNMEASURED rather than a silent OK. **Guilt:** a predicate that narrows to one file → exit 3
  (ISOLATING); a predicate the category's own file fails → exit 3 (NOT-COVERING); `--min-files`
  below 2 → exit 2, refused before any measurement runs; a run without `--categories` → exit 3
  (UNMEASURED), same as ISOLATING or NOT-COVERING. **Innocence:** a class-only predicate matching
  ≥ 2 files and covering its category → exit 0. **Acceptance:** `python3
scripts/evidence/pii_receipt.py descriptor --label <l> --categories <private> --category <l>
<terms> --check-in <pack.yml>` → 0; this is the form R6.7's Acceptance defers to for `descriptor`
  blocks, since it is the only one that pins both `--categories` and the `--min-files` floor.

**Evidence for R6.2's specific shape:** `gate-7491.md` K3 — pairing each of two redacted pilot
ids with its own per-file occurrence count, next to two named prompt files — is the mechanism: the
per-file count disambiguates which name maps to which id once the filenames are also visible,
exactly reproducing the re-identification `gate-7474.md` G3 already found and cured for a
different collision. The rule generalizes past this one lane: a per-file count next to an id is a
key regardless of which id or file it names.

**Evidence for R6.7/R6.8:** after S6 landed as text, the same lane went a third consecutive round
on each of two causes. Counts: `gate-7481.md` K2 → `gate-7491.md` K2 → `gate-7516.md` B1, then C2
at the next head, where the receipt's written command reproduced one file count while other places
in the same brief and pack still carried the older one (a separate size-figure drift in the same
round is S2's domain — `pii_receipt.py` counts files and occurrences, not byte sizes, so R6.7
does not reach it). Descriptors: `gate-7481.md` K3 →
`gate-7491.md` K3 → `gate-7516.md` B3, then C1, where the rewritten category descriptor still
isolated the residual under the gate's own conjunction, the builder's "non-isolating" measurement
counted words the residual does not contain, and the correction note published a recipe that
isolated it again. Builder Contract §1 suspends a PR at three reds for the same cause; R6.7 and
R6.8 replace a fourth round of prose with a block a gate can diff.

**Innocence case (R6.1/R6.3/R6.6, cicatrix-superscar.md #3 — guard needs guilt _and_ innocence):**
quoting a prior version's WRONG claim, in quotes, for the purpose of correcting it (as this very
section does above, and as a `dissent` entry correcting a builder's mistake does) is not itself a
violation of the hedge ban or R6.1 — a mechanical scanner that cannot tell citation from assertion
must special-case a quoted span attributed to a prior/superseded claim.

**Enforcement.** Mechanically checkable now in `scripts/evidence_pack_lint.py`, without new
schema: R6.1 as a whole-document walk (unlike `check_countable_claims()`'s current
`COUNTABLE_SUBTREES = ("diff", "lanes")` allowlist, this walk must explicitly include `dissent`
and `receipts` rather than skip them) comparing path-shaped tokens against the diff's own
changed-files set. R6.3's numeric counts as an extension of the same function's existing
file-count/diffstat re-measurement, comparing prose to a supplied `--measured` value; its hedge
regex as a fixed denylist over the same walk, with the R6.1 innocence case implemented as a
quoted-span exemption. R6.5 partially checkable via the existing "Bites contract" job
(`scripts/ci/bites_parse.py`), which already validates a structured `bites:` block's shape (not
yet the post-merge-vs-pre-merge distinction this rule adds). **None of R6.1-R6.6 is implemented
in the linter yet.** R6.7/R6.8 ship with their generator: `scripts/evidence/pii_receipt.py`
(stdlib, PII-safe output, `--check-in` for the gate), its guilt+innocence corpus
`scripts/tests/test_pii_receipt.py` and `--selftest`, both executed by `guard-conformance.yml`
on every PR that touches either file; `evidence_pack_lint.py` does not yet demand a block, so the
gate runs `--check-in` by hand. Not mechanically checkable without a live PII detector run
inside CI (out of scope here, same boundary S3 already drew): R6.2's id-to-count pairing (requires
knowing which tokens are ids) and R6.4's "measured consumer" claim (requires process/cron state,
not text). Both stay builder-attested per R6.6 and gate-verified by hand.

**Migration.** No retroactive re-lint of packs already on `main`. Applies to any evidence pack for
a PII-removal or PII-redaction lane authored after this ships; a pack for an unrelated lane is
unaffected. `#7489` (S5, hot-zone egress) merged 2026-09-27T07:31Z as `4a9a788306` (its own
Bites-contract fix followed as `61249b801c`); this section is already re-anchored after S5's,
since this PR's merge-base `fda25b4399` sits after that merge. R6.7/R6.8 bind the next version of
any PII-lane pack authored after they merge; `#7516` is OPEN with auto-merge off (`as_of:
2026-09-27T06:55Z`), so its next head is the first consumer.

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

## S5 — External-seat egress scripts are hot-zone

**Gap.** `HOTZONE_PATTERNS` (`scripts/evidence_pack_lint.py`) has no entry for the wrapper scripts
that forward this repo's own diffs or files to an external model, or for the shared engine that
redacts what those wrappers send. A gear-1 floor lets such a script merge unsigned — no
`harness/fable-gate` verdict is required — even though editing it is exactly the class of change
that can quietly weaken the PII redaction or refusal logic standing between repo content and an
outbound cloud call.

**Evidence.** PR #7466 (PII redaction/refusal guard for `.claude/scripts/codex-spalla.sh`, the
wrapper that forwards `git diff` output to the Codex CLI — OpenAI cloud) floored at gear 1
(`.claude/scripts/**` + `scripts/lib/**` + `scripts/tests/**` carried no hot-zone entry), so no
`harness/fable-gate` verdict was required to merge. Measured on head `92e7cac0a8`: auto-merge
enabled 22:38:45Z, added to the merge queue 22:51:40Z, the fresh gate's REWORK-BUILD verdict (five
blockers — a 10/11 test regression, a hand-typed refusal list, an under-matched rename, transcripts
written 0644, a silent pass4 skip) written 22:54:31Z, PR merged 23:07:43Z. The verdict existed
**13 minutes before** the merge; it did not stop it, because at gear 1 nothing in the merge path
ever reads a verdict — this is the sharper version of the gap: the floor doesn't need a faster
gate, it needs one the queue is required to wait for. The spalla cure lane is still in flight and has
already turned over twice: PR #7470 (its first attempt) was CLOSED unmerged at `2026-09-27T00:07:47Z`,
superseded by #7475; #7475 was itself CLOSED unmerged at `2026-09-27T01:23:30Z`, before this spec's
own v3 rework even landed, superseded by its current attempt, PR #7483 (`as_of` `2026-09-27T02:09:06Z`:
OPEN, auto-merge NOT armed, head `b79840b54`). #7483 may itself be superseded again before this spec
merges (see Migration — a bare PR number here would go stale, per S4 of this same spec, as it already
has three times).

**Rule.** Every path whose job is to forward repository or diff content to an external seat
(Codex, Kimi, Agy/Gemini, Qwen), or that redacts what such a path sends, is hot-zone: floor 3, a
gate verdict required before merge. This covers a wrapper script, its trigger hook, and the
redaction/refusal library or engine it calls — the same shape #7466 touched.

**Enforcement.** Add to `HOTZONE_PATTERNS` in `scripts/evidence_pack_lint.py` and the mirrored
`case` block in `.github/workflows/hot-zone-pr-gate.yml` (kept in sync by hand per the existing
comment at both sites, and now also asserted by `scripts/tests/test_hotzone_lists_sync.py`, wired
into `guard-conformance.yml`): `.claude/scripts/codex-spalla.sh`, `scripts/lib/spalla_redact.sh`,
`.claude/hooks/codex-spalla-trigger.sh`, `scripts/codex_tri_llm_review.py`,
`scripts/review_gate_run.sh`, `scripts/_redact_pii.py`, `infra/workflows/second-army.js`.

A repo-wide sweep over shell, Python **and JS/TS** (`*.sh`/`*.py` first, then `*.js`/`*.cjs`/`*.ts`
against the same pattern — a v2 rework caught the file-type-limited miss class once already and it
recurred: the v2 sweep never looked past `*.sh`/`*.py`) was classified file by file. Shell+Python
(`git grep -ln "git diff" -- '*.sh' '*.py' | xargs grep -l -iE "codex|kimi|agy|gemini|qwen|glm"`)
returns 22 non-test hits; JS/TS (`git grep -ln "git diff\|gh pr diff\|--diff-file" -- '*.js' '*.cjs'
'*.ts' | xargs grep -l -iE "codex|kimi|agy|gemini|qwen|glm"`) returns exactly one:

- IN, newly added: `scripts/codex_tri_llm_review.py` puts the full diff verbatim into a prompt
  (`build_prompt`) and passes it as argv to `codex exec` and `kimi -p`, with no redaction step at
  all. Its trigger, `scripts/review_gate_run.sh`, runs it directly on a PR's diff; the Pro
  LaunchAgent `com.nuzantara.review-gate` (StartInterval 600s) has it loaded — inert today
  (matches nothing) but armed, one edit away from forwarding every agent PR's diff to OpenAI and
  Moonshot unredacted (Esiste≠Armato; the daemon's liveness is tracked separately).
- IN, newly added: `scripts/_redact_pii.py`, the engine `scripts/lib/spalla_redact.sh` pipes every
  outbound body through (fail-closed). #7466's blocker 5 (a silently skipped redaction pass) lived
  here, and the spalla cure lane's every attempt so far (#7470, #7475, #7483) edits this exact file — a PR
  touching only it still floored at 1, which is precisely the "quietly weaken the redaction" this
  Gap names. Cost, stated explicitly rather than left silent: this file has 11 other callers beyond
  the three known egress-wrapper files (`apps/backend-rag/sandbox/egress_proxy.py`,
  `scripts/privacy_preflight.py`, `scripts/bot/build_deid_corpus.py`, `scripts/dynamic_workflow.py`,
  `scripts/nb_curator_artifact_gate.py` among them) — any PR touching the shared redactor now
  floors at 3 too, even one that never itself talks to an external seat. Not all 11 are unrelated
  to egress, though: `egress_proxy.py` IS the sandbox's own network chokepoint, and
  `dynamic_workflow.py:455` uses this same redactor as a PII gate before its OWN council dispatch to
  Gemini/Codex/Kimi — so part of the cost is simply that S5's net was already too narrow to notice
  those two before this file forced the question. Accepted: the engine's correctness is exactly the
  surface this Gap is about, and 3 is a floor a human reviews, not a ban.
- IN, newly added: `infra/workflows/second-army.js`. Its Refute lane (`:540-548`) instructs a Haiku
  agent to shell out to a cross-family seat door (`codex exec -m gpt-5.6-terra`, `agy -p`,
  `python3 scripts/tp1_call.py --model qwen3.7-plus -p`; door table at `:87-125`) with `Run git diff
origin/main...${FROZEN_REF} and try to REFUTE that change` — the frozen diff, forwarded verbatim;
  `grep -n redact infra/workflows/second-army.js` is 0 hits. Live, not theoretical:
  `.claude/skills/dynamic-workflow/brief.template.md:102` records two real runs, and
  `research/operations/second-army-*.md` are their reports. `infra/workflows/run-second-army.mjs`
  (a generic Node runner, `--script`-parameterized, that AsyncFunction-evals whatever script path it
  is given and injects the harness bindings — the diff-forwarding logic lives entirely in
  `second-army.js`, not here) is left OUT: it carries no egress logic of its own to weaken.
- OUT, not an egress wrapper (from the 22-hit sweep itself): `scripts/evidence_pack_lint.py`
  (the pattern list is data it carries, not a script that invokes anything) and
  `scripts/check_adversarial_review.py` (only lists seat/model _names_, no invocation).
- OUT, checked separately because they never say `git diff` literally (so the sweep's own search
  string misses them; classified on request, not overlooked): `scripts/lib/codex_seat.sh` (sourced
  by codex-spalla.sh:134 to pick a seat name only, carries no diff/file content — optional, could
  be added defensively but forwards nothing); `scripts/launch_worker_plane_review_panel.py` and
  `scripts/dynamic_workflow.py` dispatch Gemini/Codex/Kimi on operator-authored plans/briefs, never
  on a `git diff` — a materially different content shape (nothing already in the codebase that
  this repo didn't choose to put there). `scripts/lint_paid_llm_entity.py` sends
  `redact_for_external.py`-redacted changed-file text to TypeSafe Jev (`catE-sovereignty-lint.yml`)
  — a different shape again: a paid per-token API call already gated by its own redaction step, not
  a raw-diff-to-CLI pipe; noted here rather than silently left off the list.
- OUT, pre-existing exclusions (unchanged from the original sweep): `scripts/codex/codex-daily-research-actor.sh`
  and `scripts/codex/codex-nightly-coverage-improver.sh` use `git diff --name-only`/`--shortstat`
  only for their own PR bookkeeping and let the Codex CLI read source files itself, never piping
  content through the wrapper; an archived one-time audit helper under
  `docs/audits/2026-04-29-zero-crash-audit/` is not live automation.
- OUT, false positives: the remaining 14 files (22 sweep hits minus the 2 already-known egress
  paths, the 1 newly-added file, the 3 pre-existing exclusions, and the 2 self-reference exclusions
  above) matched only because they mention "codex"/"kimi"/"gemini"/"glm" inside a
  review-attribution comment (e.g. "codex RED", "kimi-code/k3, refuting this cut") while an
  unrelated line elsewhere in the same file happens to say `git diff` — no invocation of an
  external CLI exists in any of them: `infra/claude-hooks/worktree_isolation.py`,
  `scripts/agent_start.py`, `scripts/arm_keep_worktrees.py`, `scripts/ci/bites_parse.py`,
  `scripts/ci/change_map.py`, `scripts/ci/pr_collision_check.py`, `scripts/consumer_map.py`,
  `scripts/docs_audit.py`, `scripts/docs_inventory_refresh_liveness.py`,
  `scripts/mutation_incremental.py`, `scripts/prepush_classify.py`, `scripts/queue_unstick.py`,
  `scripts/token_lint.py`, `scripts/worktree_gc_universal.py`.

Widening hot-zone to every `codex exec`/`kimi`/`gemini`/`qwen` invocation in the repo (the council
launchers above, or the `scripts/codex/*` autonomous actors) is a separate, larger change this spec
does not make.

**Migration.** The spalla PII-redaction cure is a moving lane, not a fixed PR number (S4: a bare
number here goes stale within an hour, as it already has three times: #7470 → #7475 → #7483). State
as of `2026-09-27T02:09:06Z`: PR #7470 (first attempt) CLOSED unmerged at `2026-09-27T00:07:47Z`,
superseded by #7475; PR #7475 (second attempt) is now itself CLOSED unmerged at `2026-09-27T01:23:30Z`,
superseded by PR #7483 (current attempt). PR #7483, `as_of` the timestamp above, is OPEN, auto-merge
NOT armed, head `b79840b54f419e619f404a128d7a2b61443a51c0`, and touches **four** now-hot-zone paths
(`.claude/scripts/codex-spalla.sh`, `scripts/_redact_pii.py`, `scripts/codex_tri_llm_review.py`,
`scripts/lib/spalla_redact.sh` — one more than #7475 touched, since #7483 also edits
`codex_tri_llm_review.py`), and declares `gear: 2` against today's floor of 2 (SIZE term). The rule
this spec applies, independent of which PR number is current when either merges: **whichever of this
PR and the spalla cure lane's current attempt lands second must satisfy the floor already in force
when it lands.** Concretely, today: if this PR (S5 v3) merges first, #7483's own floor recomputes to
3 (PATH term, now that it touches four S5 paths) and its already-declared `gear: 2` becomes a
downgrade below the floor — `harness-floor.yml` fails closed on #7483's next run, and #7483 must
redeclare `gear: 3` with a full Evidence Pack before it can merge; its own PII-redaction fix does not
get a pass on the very floor it is proving is needed. If #7483 (or its own successor) merges first at
its currently-declared gear 2, nothing about _this_ PR changes: the floor for these paths is still
being added by this PR itself. No other pack on `main` declares a gear against any of the seven S5
paths, so nothing else already merged is retroactively out of compliance.
