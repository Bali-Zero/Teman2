# Spec — one `seat_override` key silences four seat rules, and only careful authorship has kept that narrow so far

**Date:** 2026-08-31 · **Status:** SPEC, not implemented · **Surface:** `scripts/evidence_pack_lint.py`
(rules R8/R9/R10/R11, functions `_seat_rule_verdict`, `_r9_r11_verdict`)

This is a spec, not a patch. The defect described below was **found**, not **introduced**, by
any diff currently in flight — it has sat in `scripts/evidence_pack_lint.py` since the seat-rules
program landed (PR-A #5054 for R8/R10, a follow-up PR for R9/R11). Every claim in it was
independently re-verified this session by reading the real file at the lines cited, and — for the
two live PRs — by re-running the real linter against the real pack, staged the same way
`harness-floor.yml` stages it. Where a re-check of the source overturned or refined the original
finding, that is called out explicitly rather than silently smoothed over.

---

## 1. The mechanism, verified

`scripts/evidence_pack_lint.py` (3,951 lines) implements four seat-discipline rules, each with its
own path-pattern trigger and its own message, but only **two** shared verdict helpers behind them:

```python
# L1980-2004, verbatim
def _seat_rule_verdict(
    rule: str,
    is_violation: bool,
    message: str,
    pack: dict[str, Any],
    today: datetime.date | None,
) -> tuple[list[str], str | None]:
    """Shared phasing+override plumbing for the seat rules (R8-R11 — R8/
    R10 land here, R11/R9 reuse this same helper in a follow-up PR): not
    a violation -> clean; else an explicit pack-level `seat_override:
    <non-empty reason>` wins outright (reported, never failed, and
    reported even after the flip — an override is a human call, not a
    rollout clock); else NOTICE before SEAT_RULES_ENFORCEMENT_DATE, hard
    violation on/after. `today` is overridable for tests, same convention
    as check_lanes_build_seat_diversity's own `today` parameter."""
    if not is_violation:
        return [], None
    override = pack.get("seat_override")
    if isinstance(override, str) and override.strip():
        return [], f"{rule} (overridden): {message} — {override.strip()}"
    if today is None:
        today = datetime.datetime.now(datetime.timezone.utc).date()
    if today < SEAT_RULES_ENFORCEMENT_DATE:
        return [], f"{rule}: {message}"
    return [f"{rule}: {message}"], None
```

`SEAT_RULES_ENFORCEMENT_DATE` (L1849) is `datetime.date(2026, 8, 31)` — **today**. R8 is already in
hard-enforcement mode, not the pre-flip NOTICE period.

```python
# L2126-2147, verbatim — a second, independently-defined helper, same key
def _r9_r11_verdict(
    rule: str,
    is_violation: bool,
    message: str,
    pack: dict[str, Any],
    today: datetime.date | None,
) -> tuple[list[str], str | None]:
    """Shared phasing+override plumbing for R9/R11 — not a violation ->
    clean; else an explicit pack-level `seat_override: <non-empty reason>`
    wins outright (reported, never failed — a human call, not a rollout
    clock); else NOTICE before R9_R11_ENFORCEMENT_DATE, hard violation
    on/after. `today` overridable for tests."""
    if not is_violation:
        return [], None
    override = pack.get("seat_override")
    if isinstance(override, str) and override.strip():
        return [], f"{rule} (overridden): {message} — {override.strip()}"
    if today is None:
        today = datetime.datetime.now(datetime.timezone.utc).date()
    if today < R9_R11_ENFORCEMENT_DATE:
        return [], f"{rule}: {message}"
    return [f"{rule}: {message}"], None
```

`R9_R11_ENFORCEMENT_DATE` (L2123) is `datetime.date(2026, 9, 2)` — **two days from today**. R9 and
R11 are still in their NOTICE period; that date is when they start hard-failing too (§7 returns to
why this matters for timing).

Four call sites, four different rule identities, one shared key:

| rule (internal name) | number | function                  | verdict helper       | line        |
| -------------------- | ------ | ------------------------- | -------------------- | ----------- |
| `ground_truth`       | R8     | `check_ground_truth_lane` | `_seat_rule_verdict` | L2040       |
| `pii_local`          | R10    | `check_pii_local_seat`    | `_seat_rule_verdict` | L2089/L2104 |
| `seat_floor`         | R11    | `check_cheap_seat_floor`  | `_r9_r11_verdict`    | L2234       |
| `council_run`        | R9     | `check_council_run_gear3` | `_r9_r11_verdict`    | L2317       |

**Claim 1, confirmed exactly:** `override = pack.get("seat_override")` (L1997) is read and acted on
_before_ `SEAT_RULES_ENFORCEMENT_DATE` is ever consulted. This is not incidental — the docstring
says so explicitly ("an override is a human call, not a rollout clock"). **This part is a
deliberate, reasonable design choice, not the defect**: a human waiver expiring on a rollout clock
would be strange. The defect is scope, not permanence — see below.

**Claim 2, confirmed exactly:** `_r9_r11_verdict` reads the identical top-level key at L2140. A
pack has exactly one `seat_override:` field. Whatever string lives there answers for R8, R9, R10
_and_ R11 simultaneously, because all four call sites resolve the same dict key with no rule
argument threaded into the lookup.

### Why this is a defect and not a design — the precedent that got it half-right

This repo already has a working precedent for a reasoned-override escape hatch: rule 7's
`gear_override` (the "ceiling" check, `compute_ceiling`, L757-868). It reads
`pack.get("gear_override")` at **L859** — but `compute_ceiling` asserts exactly **one** thing (is a
Gear-1-shaped diff over-provisioned to Gear-3), so a single flat key is safe _by construction_:
there is only ever one thing on the pack for that key to mean. The seat-rules program's own header
comment (L1834-1837) explicitly models `seat_override` on `gear_override` — "mirroring rule 7's
`gear_override`" — but generalized the _surface pattern_ (a reasoned, always-reported, never-expiring
string escape) across four independent rules while keeping the gear_override precedent's _flat,
single-key shape_. That's the part that broke the 1:1 invariant that made the original pattern
safe. The override concept is sound; the shared key is not.

---

## 2. Blast radius, measured — not asserted

Every `pack.yml` this repo has ever tracked is still on `main`: `git log --diff-filter=D --
'evidence/**/pack.yml'` returns zero deletions, ever. So "every pack currently on `main`" and
"every pack this repo has ever produced" are the same set for merged work.

```
pack.yml tracked on main:                 109
pack.yml with a real top-level
  seat_override field (yaml-parsed,
  pack.get("seat_override") truthy):        2
```

("Real" matters: a naive `git grep -n seat_override` returns **26 files** — most of them packs
whose authors _discuss_ the mechanism in prose to say they deliberately did **not** use it
("D3 satisfied by a real build lane, never by seat_override"), plus the module's own docstrings,
the test corpus, and a registry of test names. Conflating a mention with a use would have been
exactly the "lint reads the narrative, not the scalar" trap this repo has been bitten by before —
so every count below is a `yaml.safe_load` field read, never a string match.)

Two more real usages exist only on open branches, not yet on `main`: PRs **#5302** and **#5309**.
I checked all 13 currently-open Gear-3 PRs that carry an evidence pack (§4) for a real
`seat_override` field, individually — **only these two have one.** Total, all-time, repo-wide:
**4 real usages out of 111 packs ever authored (109 merged + 2 open) — 3.6%.**

For each, here is what its own text says it excuses, versus what I independently verified it
actually silences (path-pattern hits via the module's own `_any_path_matches` /
`compute_seat_floor`; R9 quorum via the pack's own `council_run:` journal, read the same way
`check_council_run_gear3` reads it):

| pack                                                                   | status        | text names                | R8 hit? | R9: real 2-seat quorum without override?                   | R10 hit? | R11 (100% mechanical)? | **actually silenced today**   |
| ---------------------------------------------------------------------- | ------------- | ------------------------- | ------- | ---------------------------------------------------------- | -------- | ---------------------- | ----------------------------- |
| `agent-air-m5-backend-rag-visa-window-seq18-0831-fc4f8acb`             | merged, #5333 | R8 only                   | yes     | yes (`kimi-code/k3` + `codex-gpt-5.6-sol`, both `ok:true`) | no       | no                     | **R8 only**                   |
| `agent-air-m5-mouth-voa-magic-link-reship-53a888a3`                    | merged, #5196 | **R8 and R9, explicitly** | yes     | yes (same 2 seats, both `ok:true`)                         | no       | no                     | **R8 only, today** (see note) |
| `agent-air-m5-db-garuda-magic-link-owner-48dc7852` (PR **#5302**)      | open          | R8 only                   | yes     | yes (verified live, §3)                                    | no       | no                     | **R8 only**                   |
| `agent-air-m5-db-definer-owner-invariant-0830-ed4038d8` (PR **#5309**) | open          | R8 only                   | yes     | yes (verified live, §3)                                    | no       | no                     | **R8 only**                   |

**Every real usage this mechanism has ever had, in its entire history, has silenced exactly one
rule (R8).** R10 and R11 have never even been _in play_ for any of the four — their path patterns
don't hit any of these diffs, so there was nothing for the shared key to accidentally mask there.

**The one case that matters most is the second row, and it is the strongest evidence in this
document that the hazard is real, not hypothetical.** That pack's own `seat_override` text says,
verbatim: _"This override is shared plumbing and silences TWO rules on this pack — R8 and R9 — so
it states a reason for each rather than one reason wearing two hats."_ Its author had already
discovered, by hand, when this pack merged (#5196, 2026-08-29), the exact defect this spec is about — and compensated for it
by writing a compound justification instead of the tool enforcing the boundary. Its notes
(pack.yml L481-486) diagnose the R9 hit as a _then-live CI staging bug_ (`harness-floor.yml` copied
only `pack.yml`+`brief.yml` into its check directory, never the `journal.jsonl` sitting next to the
pack, so a real quorum was structurally invisible to the linter). That specific CI gap is the one
this repo's own memory records as cured (`stage_council_journal.py`, referenced at
`harness-floor.yml` L938-954, which I read and confirmed stages the journal today). Re-run against
**today's** CI shape, that pack's real 2-seat journal resolves and R9 does not need the override —
which is why the table reads "R8 only, today" rather than "R8 and R9": the R9 half of that
author's justification answered a bug that has since been fixed, not a permanent structural need.
**The R8 half remains fully valid.** Either way, the fact that a human had to reason this precisely
by hand, in prose, to keep one waiver from over-reaching is itself the finding: the tool should
carry that boundary, not the author.

---

## 3. Are #5302 / #5309 masking a live R9/R10/R11 violation right now? Verified, with one self-correction

Method: fetched each PR's real `pack.yml`, `brief.yml`, and `journal.jsonl` at its head SHA,
staged them exactly as `harness-floor.yml`'s Step 7 does (`pack.yml`+`brief.yml` at the canonical
staged paths, `journal.jsonl` alongside the pack — the same layout `stage_council_journal.py`
produces), and ran the real `scripts/evidence_pack_lint.py` against it with the PR's real
changed-files list.

**My first pass was wrong, and the error is worth recording.** I initially staged only
`pack.yml`+`brief.yml` (mirroring the _old_, buggy CI shape from §2) and got a `council_run
(overridden)` NOTICE on both PRs — appearing to confirm R9 _was_ being masked. Once I staged the
journal file too (matching what `harness-floor.yml` actually does today), that NOTICE disappeared
entirely on both PRs: R9 resolves clean, unaided by the override. **This reverses my own first
reading and confirms the other agent's report** — the two live PRs really do carry a genuine
2-distinct-seat quorum (`codex-gpt-5.6-sol` + `kimi-code/k3`, both `role:review, ok:true`, in
`journal.jsonl`), and R9 does not need the waiver on either one. I'm recording the false start
because it is exactly the "does the diagnosis match what actually reached the code" question this
repo asks of every finding, including its own.

Final, verified state for both #5302 and #5309:

- **R8 (ground_truth):** hits (`*/visa_engine/*` on `scripts/visa_engine/operational_preflight.py`).
  No ground_truth lane declared. **Silenced by the override.**
- **R9 (council_run):** hits (`gear: 3`). Genuine 2-seat quorum present. **Not masking anything —
  clean on its own merits.**
- **R10 (pii_local):** `_any_path_matches(changed_files, PII_PATH_PATTERNS)` → `False` for both.
  **Not applicable — nothing there to mask.**
- **R11 (seat_floor):** `compute_seat_floor(changed_files)` → `False` for both (migrations, `.py`,
  tests and docs specs are not 100%-mechanical). **Not applicable.**

**"It is not currently masking anything beyond R8" is the honest finding for both live PRs**, and
I want to state plainly that this is not a weak result — it means the two real, currently-open
uses of this mechanism are doing exactly the narrow job their authors intended.

### Non-vacuity proof (real packs, not fixtures)

Stripping the `seat_override:` line from each real pack (nothing else changed) and re-running the
identically-staged linter:

```
$ python3 scripts/evidence_pack_lint.py .../pack_stripped.yml --repo-root ... \
    --changed-files-file .../pr5302_changed_files.txt --source-path evidence/2026-08/.../pack.yml
evidence_pack_lint: FAIL — 1 violation(s):
  - ground_truth: diff touches a ground-truth path (... visa_engine ...) but declares no
    well-formed {role: ground_truth, seat, nb, query_hash} lane
EXIT CODE: 1
```

Identical result for #5309's pack. This is claim 3's "proven load-bearing by stripping the field"
— confirmed, on the real packs, with the real changed-files list, with everything else CI stages
held constant. (The FAIL, not NOTICE, is itself informative: `SEAT_RULES_ENFORCEMENT_DATE` is
2026-08-31 — **today** — so R8 is already in hard-enforcement mode, not the pre-flip grace period.)

---

## 4. CI wiring — exactly one place, narrowly gated

`evidence_pack_lint.py` is referenced in exactly two workflow files:

- **`.github/workflows/harness-floor.yml`**, step _"Gear-3 — validate evidence/pack.yml against
  the Evidence Pack contract"_ (L827-991), the **only** place any workflow runs the full lint
  against a real PR's own pack. Its condition, read directly (L828-831):

  ```yaml
  if: |
    steps.kill_switch.outputs.disabled != 'true' &&
    steps.brief.outputs.present == 'true' &&
    steps.gearcheck.outputs.gear == '3'
  ```

  `steps.brief.outputs.present` requires the PR's own diff to touch `evidence/brief.yml` (or its
  resolved per-PR equivalent); `gearcheck.outputs.gear` must be exactly `'3'`. Confirmed by direct
  read, not inference: claim 4 is exactly right.

- **`.github/workflows/guard-conformance.yml`** (L310-316) runs `pytest
scripts/tests/test_evidence_pack_lint.py` and `evidence_pack_lint.py --selftest` — the linter's
  **own** guilt/innocence test corpus. It never touches a real PR's pack. It proves the rules work
  in the abstract; it is not a second enforcement point.

**Consequence, stated plainly:** a Gear-1 or Gear-2 PR is never seat-rule-checked, regardless of
what paths it touches. R8-R11 exist only inside the Gear-3-and-briefed lane.

### Measured exposure, today (2026-08-31) — corrects an illustrative figure

The task that produced this spec offered "22 of 34" as an illustrative framing for how much of the
open-PR set bypasses this linter. I measured the real numbers instead of reusing that figure:

```
open PRs (gh pr list --state open):                                    38
  of which touch an evidence brief+pack pair, declaring gear:3
  (i.e., structurally CAN reach the Step-7 seat-rule check):            13   (34%)
  of which never touch an evidence pack at all — never reach
  the seat-rule linter this cycle, regardless of content:                25   (66%)
of the 13 that DO reach it, carry a real seat_override:                  2   (15% of exposed, 5% of all open)
```

The shape of the illustrative figure was directionally right (most open PRs bypass this gate
entirely) but the actual denominator is 38, not 34, and the actual bypass count is 25, not 22.

---

## 5. Requirements any fix must satisfy

1. **Rule-scoping.** A waiver must name what it waives. Two shapes were considered (see §6);
   either satisfies this requirement — what matters is that `pack.get("seat_override")` (or its
   replacement) can no longer answer for a rule its author never looked at.
2. **Non-breaking migration.** #5302 and #5309 are live, currently-green, currently-open PRs at
   the moment this spec is written. A fix that requires the new shape immediately turns both red
   with no warning — a regression this spec exists to prevent, not cause. The existing file
   already has a working precedent for exactly this kind of transition:
   `SEAT_RULES_ENFORCEMENT_DATE` (L1849) and `R9_R11_ENFORCEMENT_DATE` (L2123) both give packs a
   NOTICE period before a new requirement starts failing the build. Any fix should accept the
   legacy flat string (deprecated, phased NOTICE-then-FAIL of its own on a new date constant, same
   pattern) _and_ the new scoped shape, so existing green PRs keep working unmodified through a
   transition window, with a NOTICE nudging them toward the new form.
3. **Non-vacuity proof, on real data.** §3 above already IS this proof for R8: PR #5302's and
   #5309's real packs, with `seat_override` stripped, real `--changed-files-file`, real staged
   `brief.yml`, FAIL with `ground_truth` — not a synthetic two-line fixture. Whoever implements
   the fix should extend this same real-pack method one step further: take PR #5302's real pack
   with its override rewritten to name **only** `r8`, but with one entry deliberately dropped from
   its real `journal.jsonl` (breaking genuine R9 quorum) — the fixed linter must FAIL on
   `council_run` despite the R8-scoped override being present and valid. That is the proof that
   scoping actually contains the blast radius, not just relabels it.
4. **The scope check belongs in the shared helper, not each call site.** The bug was introduced by
   generalizing `_seat_rule_verdict`/`_r9_r11_verdict` across four rules without threading rule
   identity into the override lookup itself — the four call sites (`check_ground_truth_lane`,
   `check_pii_local_seat`, `check_cheap_seat_floor`, `check_council_run_gear3`) each already pass
   their own `rule` string into the helper for the _message_. The fix should make the helper look
   up the override _by that same `rule` key_, so a future fifth rule reusing the helper inherits
   correct scoping by construction, instead of relying on every future author to remember to scope
   their own override read by hand.
5. **The audit signal should stay meaningful.** The header comment (L1834-1837) says the override
   is "ALWAYS-reported... so X3 (ASSEMBLY-LINE.md gate-lifecycle ledger) can count how often it
   fires" — that ledger's stated purpose is a quarterly audit where "a gate that has never blocked
   anything is deleted" (`docs/factory/ASSEMBLY-LINE.md` L231). A single aggregate "seat_override
   fired N times" count cannot tell that audit which of the four rules is actually the one being
   escaped — which is exactly the information a per-rule breakdown would restore for free once
   scoping exists.

---

## 6. Two shapes worth pricing against those requirements

**(a) One key, structured value** — `seat_override: {r8: "reason", r9: "reason"}` (or keyed by the
internal rule names `ground_truth`/`council_run`/`pii_local`/`seat_floor`, which are already the
`rule` strings each call site passes today, so reusing them avoids inventing a second vocabulary).
One place to look for "does this pack have any override at all"; requires the four call sites (or
the shared helper, per requirement 4) to branch on `isinstance(override, str)` (legacy) vs.
`isinstance(override, dict)` (scoped) during the migration window.

**(b) Four keys, one per rule** — `ground_truth_override` / `council_run_override` /
`pii_local_override` / `seat_floor_override`, each read exactly the way `gear_override` already is
at L859: `pack.get(f"{rule}_override")`, no new type-branching, no nested-value parsing. This is
the more direct copy of the one precedent in this file that is already known to be safe, and is
probably the smaller diff. Its cost: the one real historical case that genuinely needed to justify
two rules at once (§2, row 2) would write two separate keys instead of one shared paragraph — a
strictly worse authoring experience for that one case, in exchange for making the common case (one
rule, one reason) impossible to get wrong.

Neither is mandated here. (b) is more consistent with existing precedent and cheaper to implement;
(a) reads better for the genuinely-dual-purpose case. Pricing this trade-off is implementation
work, not spec work.

---

## 7. Should this be fixed at all — recommendation, priced against §4's exposure fact

Priced honestly: this is a narrow-exposure, low-frequency mechanism. Only 34% of open PRs even
reach the check it lives in; of those, only 15% (2 PRs, out of 38 total open) currently use it at
all; across the _entire_ history of this repo, only 4 packs out of 111 ever have, and in every
single one of those 4, the actual damage the code _permits_ (silencing R9/R10/R11 by accident)
has never once happened — the one pack that came closest was saved by an unusually careful human,
not by the tool.

That argues against dropping everything for this. It does not argue for shelving it, for two
reasons specific to timing, not to the abstract severity of the defect:

- **`R9_R11_ENFORCEMENT_DATE` is 2026-09-02 — two days from today.** R9 and R11 flip from NOTICE to
  hard FAIL on that date. NOTICE-phase rules generate no pressure to reach for `seat_override`;
  FAIL-phase rules do. The realistic moment for a Gear-3 PR to reach for this waiver _because_ R9
  or R11 is now failing its build, for the first time, is the week this spec is being written —
  exactly when a diff that also has a genuine, unrelated R8 or R10 problem could get all four
  waived by one hastily-written sentence, with no test anywhere that would catch it.
- **The fix is small and additive.** Requirement 2 above means no currently-green PR needs to
  change on the day this lands; the shape in §6(b) needs no new parsing logic at all, just three
  more `pack.get(...)` reads mirroring the one at L859 that already exists and is already proven
  safe.

**Recommendation: fix it, sized as a small (Gear-1/2) PR, landed before or shortly after
2026-09-02** — not because the historical record shows damage (it doesn't), but because the record
also shows the near-term conditions that would start producing that damage are two days away, and
the fix costs less than the incident it would prevent.
