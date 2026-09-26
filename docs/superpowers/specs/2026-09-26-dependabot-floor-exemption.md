# SPEC — third-party Dependabot SHA-bump floor exemption

date: 2026-09-26 · owner: next infra/harness-floor lane · status: **PARKED, pre-implementation**
origin: council review of `agent/air-m5/infra/dependabot-floor-0926` (Builder Contract rule 1 —
"a fix-of-a-fix stops at depth 1 … write the spec"). Two rounds already landed on that branch
(the second attempting F4/F5 fixes on the first); a third round is refused by the contract.

**Status: normative for whoever resumes this lane.** Implementation is a separate PR, after this
spec is read. Where the resumed branch and this spec disagree, say which is wrong in the PR, not
silently in code.

## 0. Problem

`compute_floor()`'s path term floors every `.github/workflows/**` diff at Gear 3 unless the whole
diff is exemptable version-pin churn. Since 2026-09-01 a first-party action (`actions/*`,
`github/*`, …) moving its ref is exempt on content alone. A **third-party** action (sonarsource,
codecov, …) moving its SHA is not — every such bump floors at 3 and needs a full Gear-3 pack, even
when the action is already adopted and every other required check is green.

## 1. Ruling honored

RULED 2026-09-26 (Zero, verbatim: _"non voglio rallentamenti e rotture"_), quoted from the parked
branch's own commit `5190c52b98` (this text is **not yet on `origin/main`** — the parked branch's
2-line diff to `docs/rules/RULINGS.md` is the only place it exists on disk right now):

> #7101 and #7102 were one-line SHA bumps of sonarsource and codecov actions the repo already
> runs, every required check green except Harness floor recompute, blocked five days on the
> first-party-only exemption. The third-party lane keeps every content condition of the
> 2026-09-01 first-party lane (uses-only, identity sequence unchanged, pinned), requires a full
> 40-hex SHA on both sides, and adds provenance proven from the GitHub API: PR opened by
> `dependabot[bot]` and every commit single-parent, authored by `dependabot[bot]`, committed and
> signed by `web-flow`, ending at the head. `harness-floor.yml` fetches those facts; the linter
> judges them, fail-closed.

Whoever resumes this lane honors the ruling by keeping the outcome (an already-adopted
third-party SHA bump, provably Dependabot's alone, floors at 1 when CI is green) — not by
reproducing the parked branch's mechanism, which the council showed does not deliver that outcome
safely.

## 2. What the parked branch does (for orientation, not as a starting diff)

Two commits on `agent/air-m5/infra/dependabot-floor-0926`:

- `5190c52b98` — `_exemptable_uses_identity()` in `scripts/evidence_pack_lint.py` grows a
  `third_party_ok` flag: a non-first-party `uses:` line is exemptable when the caller has proven
  Dependabot provenance AND `_FULL_SHA_RE.match(ref)` (`^[0-9a-f]{40}$`) on the new ref.
  `dependabot_provenance_verdict()` checks PR author, commit authorship/signature/parent-count,
  and that the last commit is the head. `harness-floor.yml` fetches these facts from the GitHub
  API and passes them to the linter.
- `c8f46da2c4` — a follow-up inside the same branch attempting to close two council findings
  (commit-SHA validation, tag-vs-SHA pinning) from a first review round. This is itself the
  "fix-of-a-fix" the Builder Contract's depth-1 rule refers to — a second round did not close the
  surface, which is why a third round is refused in favor of this spec.

## 3. Council findings (verbatim-summarized, Codex, `council-a/out-codex.txt`)

| #   | Severity    | Location                                                                                                  | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| --- | ----------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **BLOCKER** | `scripts/evidence_pack_lint.py:559` (`_exemptable_uses_identity`)                                         | `uses: codecov/codecov-action@<40-hex>#mutable` receives floor 1. `_USES_LINE_RE`'s ref group stops at `#`, so the regex reads `#mutable` as a comment — but YAML does NOT treat `#` as starting a comment when it directly follows the value with no separating whitespace, so `#mutable` is part of the real ref. That whole string is a **valid, mutable git tag name**, distinct from the commit named by the leading 40 hex characters. Reproduced: floor 3 → 1.                                                                 |
| 2   | MAJOR       | `harness-floor.yml:547`, `scripts/evidence_pack_lint.py:637`                                              | `merge_group` provenance never binds the API-attested head to the **patch actually examined**. The workflow sets `EXPECTED=""` on `merge_group`, and `dependabot_provenance_verdict()` only compares `expected_head_sha` to the attested head on a `pull_request` event. Scenario: the queued group contains snapshot H1 (should NOT qualify); mid-run Dependabot recreates the branch as H2; the API attests H2 (clean provenance) while the patch under review is still H1's. Provenance is accepted for a patch it never examined. |
| 3   | MAJOR       | `scripts/evidence_pack_lint.py:750` (`workflow_paths_exempt_from_path_term`, the sequence-equality check) | A reorder across an unchanged action passes. `codecov@OLD → checkout@v4` becomes `checkout@v4 → codecov@NEW`: git can represent this as two hunks (codecov removed then re-added) that leave `checkout` untouched in the diff. Both per-file `minus`/`plus` identity lists then contain only `codecov/codecov-action`, so the existing sequence-equality guard (added 2026-09-01 to catch exactly this class) does not see the full step order change. Before this diff: floor 3. With it: floor 1.                                   |
| 4   | MAJOR       | `scripts/evidence_pack_lint.py:554` (`_USES_LINE_RE`, optional leading dash)                              | Indentation/dash trick removes a step and passes as a pin-only change. `-      - uses: codecov/codecov-action@<OLD>` / `+          uses: codecov/codecov-action@<NEW>` is valid YAML either as a standalone list-item step or, with the dash dropped and re-indented under a preceding `run:`/`env:` block, as plain content (e.g. an env value) — the parser does not distinguish the two roles and both regex-match as the same "identity", so floor drops 3 → 1 even though a step disappeared from the workflow.                  |
| 5   | MINOR       | `scripts/evidence_pack_lint.py:630` (`_read_provenance_file`)                                             | `{"event": []}` or `{"event": {}}` raises an uncaught `TypeError` on the `frozenset` membership check instead of degrading to `provenance=False`.                                                                                                                                                                                                                                                                                                                                                                                     |

Kimi's parallel review (`council-a/out-kimi.txt`) did not reach a verdict — truncated mid-reasoning
(`KIMI_RC=124`, session resumable via `kimi -r session_56774161-…`). Its partial trace raised one
**informational, unresolved** question worth carrying forward but NOT an acceptance criterion
here: under the repo's `HEADGREEN` merge-queue grouping (`max_entries_to_merge=4`), the ruling's
"provided CI is green" is a per-entry policy question, not a bug in this diff — whoever revisits
merge-queue semantics should re-read `council-a/out-kimi.txt` before assuming it is settled.

## 4. Acceptance criteria (falsifiable, one per numbered finding above)

1. **AC1 (kills finding 1).** A test asserts that `owner/repo@<40 lowercase hex chars><anything
not preceded by whitespace>`, e.g. `owner/repo@` + 40 hex chars + `#mutable` with no space
   before `#`, is **NOT** treated as a full-SHA-pinned ref — `compute_floor()` on a diff containing
   only that line change floors at 3, not 1. The fix must extract the real YAML scalar value
   (respecting YAML's whitespace-before-`#` comment rule) before matching `_FULL_SHA_RE`, not
   pattern-match around it.
2. **AC2 (kills finding 2).** A test asserts that on a `merge_group` event, `harness-floor.yml`
   populates a real expected-head value (not `""`) and `dependabot_provenance_verdict()` refuses
   provenance when the API-attested head does not match the snapshot the patch was computed
   against. A guilt fixture with `event=merge_group`, an attested head H2, and a patch reflecting
   H1 must return `proven=False`.
3. **AC3 (kills finding 3).** A test reproduces the split-hunk reorder (an unchanged action's
   `uses:` line staying textually identical while a different action is removed from one position
   and re-added elsewhere) and asserts `workflow_paths_exempt_from_path_term()` does NOT exempt
   that file — the check must compare structural position (e.g. per-step index or surrounding
   context), not merely the sequence of changed-line identities.
4. **AC4 (kills finding 4).** A test reproduces the dash/indentation change (leading `- ` present
   on one side, absent or differently indented on the other, for the "same" `uses:` value) and
   asserts the file is NOT exempted — the parser must preserve and compare the YAML node role
   (list-item step vs. anything else), not only the ref string.
5. **AC5 (kills finding 5, lower priority).** A test asserts `{"event": []}` and `{"event": {}}`
   in a `--provenance-file` degrade to `proven=False` with a stated reason, never an uncaught
   exception.

All five must be demonstrated as **guilt tests that fail on the parked branch's current head
(`c8f46da2c4`)** before being counted as closed — a test that only exercises a hypothetical is not
sufficient; re-run it against that commit first.

## 5. Non-goals

- Redesigning the first-party lane (`FIRST_PARTY_ACTION_OWNERS`, shipped 2026-09-01, untouched by
  this spec and by the council review).
- Resolving Kimi's `HEADGREEN` merge-queue-grouping question — track it separately if it matters.
- Prescribing the exact fix shape (full YAML parsing via a library vs. a hardened line parser) —
  either is acceptable if all five acceptance criteria pass as guilt tests against the parked
  branch's current head.
- Any change to `.github/workflows/auto-merge-whitelist.yml` — that is the sibling parked branch,
  covered by `2026-09-26-automerge-arm-as-user.md`.

## 6. Where the branch is

- Worktree: `.worktrees/infra-dependabot-floor-0926`
- Branch: `agent/air-m5/infra/dependabot-floor-0926` (unpushed)
- Commits: `5190c52b98`, `c8f46da2c4`
- On resume: rebase on fresh `origin/main` first — do not build on top of the parked commits
  without re-reading them against this spec's AC1-AC5, since the second commit already
  demonstrates that patching forward without a spec does not converge.
