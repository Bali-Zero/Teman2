---
date: 2026-08-31
domain: operations
client_case: none
sources:
  - "scripts/evidence_pack_lint.py (the three enforcement-date constants and their rules)"
  - ".github/workflows/harness-floor.yml (the staging contract this measurement replicates)"
  - "gh pr list --state open (43 PRs, 2026-08-31)"
  - "git show origin/<branch>:<pack> for every open PR carrying an evidence pack"
discovered_by: "Squad S (STOP), wave 2 lane 6, in response to Zero's «anche subito se siamo pronti»"
adversarial_review: gemini-3.1-pro
adversarial_review_second_seat: glm-5.2
adversarial_review_note: >-
  TWO blind cross-family reviews of this report's method and claims, both seats
  != the author (claude-opus-5). Round 1 (Gemini 3.1 Pro) returned 4 blockers:
  the §1 buckets were arithmetic bent to look disjoint, the denominator was 43
  where it should be 20, the 23 pack-less PRs were dismissed without measurement
  (six turned out to be Gear-3), and the harness's isolation limit was
  undeclared. Round 2 (GLM-5.2), on the corrected report, returned 6 findings
  round 1 had missed, 2 blocking: the seat-outage claim carried no evidence
  pointer, the declared limit was never bounded, §5 used a different harness
  from §2 without saying so, and §7 rested on a counterfactual nobody had run.
  Every finding is recorded with its disposition in the accompanying evidence
  pack's dissent block. An earlier draft of this frontmatter claimed
  `exempt-machine-report`; the nb-curator artifact gate refused it — correctly,
  since this file declares sources and discovered_by and is therefore a research
  deliverable, not a generated snapshot — and that refusal is why a real review
  was obtained instead of a stamp.
---

# 2/9 enforcement readiness — what is ready, what is not, and why the reasons differ

**Question.** Three rules flip from NOTICE to hard FAIL soon: `SEAT_RULES_ENFORCEMENT_DATE`
(R8/R10) and `R9_R11_ENFORCEMENT_DATE` on 2026-09-02, `EVIDENCE_ROOT_DEPRECATION_DATE` on
2026-09-05. Zero asked for them to move **if we are ready**. This measures "ready".

**Answer.** One of the three is ready and has been moved. The other two are not, for
different reasons, and moving them together would have hidden that.

---

## 1. The result

43 open PRs. **20 carry an evidence pack**; 23 do not (see §5 — six of those 23 *should*).
Each of the 20 was linted twice: once with today's dates, once with a single constant
pulled into the past so that rule alone is in force.

| constant | current | newly RED if moved ALONE (of the 20 with a pack) | verdict |
| --- | --- | --- | --- |
| `SEAT_RULES_ENFORCEMENT_DATE` (R8/R10) | 2026-09-02 | **0** | **READY — moved to 2026-08-31** |
| `EVIDENCE_ROOT_DEPRECATION_DATE` | 2026-09-05 | **3** (#5072 #5037 #4640) | not moved — §4 |
| `R9_R11_ENFORCEMENT_DATE` | 2026-09-02 | **9** | not moved — §3 |

Of the 20: 7 clean under **all three**, 4 already red today for reasons no date causes
(§6), 9 reddened by R9. **The 3 reddened by `EVIDENCE_ROOT` are a SUBSET of those 9, not a
fourth bucket** — #5072, #5037 and #4640 fail both rules. An earlier draft of this section
presented the buckets as disjoint and summing to 43; a blind refuter caught that they do
not, and it was arithmetic bent to make the causes look tidier than they are.

## 2. Method, its trap, and its declared limit

`harness-floor.yml` does not lint a pack where it lives. It **stages** pack and brief into a
synthetic tree as the canonical `evidence/{pack,brief}.yml`, stages the council journal
beside the pack, and passes `--source-path <the pack's REAL path>` so Rule 9 judges the real
path. This harness replicates that.

**The trap.** The first version omitted `--source-path`. Every single pack then reported
`evidence_root_deprecated`, and the headline would have been "16 PRs go red" from a cause
that does not exist. The numbers above are from the corrected harness.

**DECLARED LIMIT, and it bounds what this report may be cited for.** The harness lints each
pack **in isolation** — it does not reconstruct the PR's working tree. Rules that read the
diff (the deterministic gear floor, R11's mechanical-path classification, the size rules)
are therefore *not* exercised as CI exercises them. Raised by a blind refuter; stated rather
than papered over — and then BOUNDED, because a second reviewer pointed out that declaring a
limit without bounding it leaves the headline number unciteable:

`R9_R11_ENFORCEMENT_DATE` governs R9 **and R11**, so if R11 could fire on any of these packs
the "9" would be an undercount. R11 fires only on a diff that is **100% mechanical paths**
(i18n/locale strings, test fixtures, `PENDING-ARMS.md`, a mouth catalog asset). Measured by
running the lint's own `compute_seat_floor` over each PR's real changed-file list: **0 of the
20** qualify. R11 cannot fire on any of them, so 9 is the whole cost of that constant here.

**A second limit, same source.** Each constant was moved *alone*, which is a temporal state
that will never exist in production: on 2026-09-02 R8/R10 and R9/R11 flip together. The
isolation is the point — it is the only way to price them separately — but the union is not
simply the sum, because a PR can be red under both (three are).

## 3. The nine, and the hypothesis the measurement killed

R9 requires a Gear-3 pack to carry a council journal with **≥2 distinct review seats marked
`ok: true`**, from `COUNCIL_REVIEW_SEATS = (codex-gpt-5.6-sol, kimi-code/k3, tp1-qwen3.8-max)`.

| PR | journal | review seats declared | allowlisted `ok:true` |
| --- | --- | --- | --- |
| #5343 #5340 #5338 #5336 | yes | `agy-gemini-3.1-pro` (ok:true), `codex-gpt-5.6-sol` (ok:**false**) | 0 |
| #5302 #5158 #5072 #5037 #4640 | **none** | — | 0 |

Two causes. This split accounts for **these nine**; it is not a complete taxonomy of how R9
can fail (a malformed journal, or one where every seat is `ok:false`, would be neither).

**Cause A — five carry no council journal at all.** R9 doing its job. The fix is theirs and
the cost is the one the rule was designed to impose.

**Cause B — four carry a journal whose one reachable reviewer scores zero.** Each records
Gemini 3.1 Pro `ok:true` (the review that found, among other things, a zero-click RCE and a
false innocence claim) and `codex-gpt-5.6-sol` `ok:false`, an honestly-recorded outage.
**The outage claim, with its evidence**, because a second reviewer correctly refused to take
it on the words "measured on Pro" — the whole Cause A / Cause B split rests on it, and if the
seats were in fact reachable the framing inverts from "rule failing" to "squad failing":

```
$ codex exec -m gpt-5.6-sol   -c model_reasoning_effort=low --sandbox read-only \
    --skip-git-repo-check -o out.txt "Reply with exactly: SOL-OK"   < /dev/null
ERROR: Your workspace is out of credits. Add credits to continue.     # rc=1, out.txt never created
$ codex exec -m gpt-5.6-terra ...  (same invocation)
ERROR: Your workspace is out of credits. Add credits to continue.     # rc=1
$ python3 -c "<POST /chat/completions model=qwen3.8-max via TP1>"     # 20 KB prompt
TimeoutError: The read operation timed out                            # at 400s; repeated at 7.8 KB
```

A method note that belongs with it: a first pass at this probe grepped the Codex RUN LOG for
`SOL-OK` and found it — that was the prompt echoed back, not a reply, and the `-o` output file
had never been created. The container is not the entity.

So: **two of the three allowlisted seats are unreachable from Pro on 2026-08-31**, and
`gpt-5.6-terra` had successfully BUILT a diff roughly an hour before answering this way, so
the seat went dry mid-session rather than having been dead all along.

### The obvious cure, tested and rejected

"Widen `COUNCIL_REVIEW_SEATS` to the seats the fleet actually routes to." Tested: a variant
adding `agy-gemini-3.1-pro` and `tp1-glm-5.2`, re-run over all nine.

**It frees zero.** R9 wants **two** `ok:true` seats; those four packs have **one**. Widening
raises the count 0 → 1 against a threshold of 2.

That is a statement about **the packs as they stand**, and a refuter correctly noted it is
not the whole question: had the allowlist included `tp1-glm-5.2` from the start, the author
could have routed a second review there and reached 2. Both are true, and they belong to
different owners:

- **Squad S's own gap.** On those four, only one reachable cross-family reviewer was
  actually run. Running a second (`tp1-glm-5.2`, live and used elsewhere in this wave) was
  available and was not done. That is a squad failing, not a rule failing.
- **A doctrine question, not a squad's to decide.** `COUNCIL_REVIEW_SEATS` names three seats
  with no stated justification — checked rather than assumed after a reviewer asked whether
  one existed elsewhere: `grep -rn COUNCIL_REVIEW_SEATS` over the tree returns the constant
  itself, one docstring mention in the same file, and nothing in any `.md` at all — while `00-BATTLE-PLAN.md` §4 rule 3 and the wave-2 plan §5.2
  route refutation across Kimi K3, Codex sol, GLM-5.2 and agy by diff class. The lint and
  the doctrine it implements do not name the same set — and neither half of the fix works
  alone: a wider list without a second review still counts 1, and a second review on a
  non-allowlisted seat still counts 0.

## 4. `EVIDENCE_ROOT_DEPRECATION_DATE` — three PRs, all old-layout

#5072, #5037 and #4640 still write the deprecated `evidence/pack.yml` root, and each is also
in the R9 nine — specifically in **Cause A**, the no-journal group of §3 (a reviewer noted the
subset claim in §1 did not say WHICH group, and it should: they fail both rules, and neither
failure is the seat-outage one). The rule is about layout and the fix is available (move the pack under
`evidence/<YYYY-MM>/<slug>-<8hex>/`). Not moved, for one reason: the date is five days out,
and pulling it forward buys five days at the price of hard-blocking three PRs whose authors
have had no notice. Ready in every sense except that one.

### 4b. RE-MEASURED 2026-09-01 — the one reason §4 gave is gone

§4's verdict rests on exactly one reason: *"pulling it forward buys five days at the price of
hard-blocking three PRs whose authors have had no notice."* That reason no longer holds. Measured
2026-09-01T08:46Z, one day after §4 was written:

| PR | state on 2026-09-01 | writes `evidence/pack.yml` at the ROOT? |
|---|---|---|
| #5072 | OPEN | **no** — migrated to `evidence/2026-09/agent-air-m5-ops-practice-status-log-0827-e4d14e87/` |
| #5037 | OPEN | **no** — migrated to `evidence/2026-08/agent-pro-visa-oracle-slice0-migrations-e59cb527/` |
| #4640 | **CLOSED** | n/a |

Swept across ALL open PRs, not just those three: **zero** open PRs write `evidence/pack.yml` or
`evidence/brief.yml` at the repo root. So `EVIDENCE_ROOT_DEPRECATION_DATE` (2026-09-05) and
`EVIDENCE_ROOT_BRIEF_DEPRECATION_DATE` (2026-09-12) now each cost **0** newly-red PRs, where §4
measured 3 and the rule-12 comment measured 6. **Neither date needs pulling forward — both simply
arrive free.** Nothing here proposes moving a date; it removes the stale reason for deferring one.

**How this was measured, because an absent result is the one to distrust.** Two independent probes
(`gh pr view --json files` and the paginated `gh api .../pulls/N/files`) agree per PR, and neither
was truncated — the three PRs have 9, 5 and 15 files, far under the 100-file cap that would have
made a short answer look like a clean one. Positive control: the same sweep DOES find `evidence/`
paths on five open PRs (#5432 #5337 #5158 #5072 #5037), so a zero at the root is a real zero and
not a probe reading nothing.

**Why this note exists at all.** §4's number was accurate the day it was written and wrong the day
after, and its conclusion inverts with it — which is the failure this document elsewhere warns
about. Anyone reading §4 alone would defer a date that is now free.

## 5. The 23 without a pack — six of them should have one

Treating "no pack" as out of scope was the report's own blind spot until a refuter pushed on
it, so it was measured — with a **different harness** from §2's, which a reviewer was right to
flag as a tension: §2's lints a staged pack and never sees a diff, while this recompute feeds
each PR's real changed-file list and per-file additions/deletions (from the PR files API)
straight into the lint's `--print-floor`. Two code paths, two scopes; naming which produced
which number is what makes either citeable.

- **6 have floor 3** — #5337, #5333, #5218, #5028, #4717, #4569. A Gear-3 diff with no
  evidence pack is non-compliance **by omission**, today, independent of any date.
- **17 have floor 1 or 2** — no pack required; genuinely out of scope.

The dates do not change this either way; it is recorded because a readiness report that
counted only the PRs it could conveniently lint would be measuring its own convenience.

## 6. Already red today, caused by no date

- **#5324, #5327** — `brief_ref` resolution. Both declare the per-PR path
  (`evidence/2026-08/<slug>/brief.yml`) where CI's staging requires the literal
  `evidence/brief.yml`. The same trap Squad S hit on #5325 and cured; the local lint points
  the *wrong way* here, because locally the per-PR value resolves and the correct one does
  not. Reported to the owning squad.
- **#4644, #4645** — a missing mandatory `lanes:` field.

## 6bis. This report's own pack is the finding, demonstrated on itself

While correcting §3's charge that Squad S had run only one reachable reviewer, the second one
was run. This report went through **two blind cross-family reviews**: Gemini 3.1 Pro (4
blockers, including the disjoint-buckets arithmetic and the six Gear-3 PRs with no pack) and
GLM-5.2 (6 findings round 1 missed, including that the seat-outage claim carried no evidence
pointer and that the R11 half of the shared constant was never bounded). Both `ok: true`.
Both genuinely cross-family. Between them they changed four numbers and one conclusion.

**R9 scores this pack ZERO.** Two reachable cross-family reviews, neither seat allowlisted.

That is the whole of Cause B in one artefact, and it is worth more than the argument in §3:
a pack whose *second* reviewer caught two blockers the first missed still fails the rule that
exists to ensure a second reviewer was consulted. The count R9 wants is satisfied; the brands
are wrong.

## 7. What shipped, what did not, and the inconsistency it leaves

**Shipped**: `SEAT_RULES_ENFORCEMENT_DATE` → 2026-08-31, with the measurement recorded at
the constant. Zero of the 20 packs affected.

**Not shipped**: the other two. §6 item 2 of the wave-2 plan defaults to "enforce as-is";
this report does not override that default, it prices it.

**And it leaves an asymmetry worth naming, because a refuter named it first.** R8/R10 govern
the *declaration* of seats and R9/R11 the *validation* of what those seats produced; they
shared a date because they are two halves of one lifecycle. Moving one and not the other
enforces the declaration while the verification stays advisory for two more days. A reviewer called the
justification for that a post-hoc rationalisation, on the grounds that the alternative was
never measured. It now is: **all three moved together reddens 9 of the 20**; `SEAT_RULES`
alone reddens **0**. So the choice is not between elegance and expediency — it is between
enforcing a zero-cost rule today and withholding it in order to keep company with one that
would block nine PRs, four of them for a seat outage rather than a defect. Stated as a
measurement because it was challenged as an assertion.

## Adversarial review

Two blind cross-family reviews of this report's method and claims, both by seats other than
the author (`claude-opus-5`). Every finding and its disposition is recorded in the dissent
block of the accompanying evidence pack; this section is the summary the R1 gate reads.

**Round 1 — `gemini-3.1-pro`, 4 blockers.** The §1 buckets were presented as disjoint and
summing to 43 when three PRs fail under both rules — arithmetic bent to make the causes look
tidier than they are. The denominator was 43 where only 20 PRs carry a pack. The 23 pack-less
PRs were dismissed as out of scope **without measurement**; measured after the challenge, six
are Gear-3 and non-compliant by omission, a finding this report would otherwise not contain.
And the harness's isolation from the PR diff was an undeclared limit.

**Round 2 — `glm-5.2`, on the corrected report, 6 findings round 1 missed, 2 blocking.** The
seat-outage claim on which the whole Cause A / Cause B split rests cited only "measured on
Pro", with no command and no artefact — if those seats were reachable the framing inverts
from *rule failing* to *squad failing*, and the exact invocations and their verbatim errors
are now in §3. The isolation limit was declared but never **bounded**: `R9_R11` governs R11
too, so the nine could have been an undercount — now measured at 0 of 20 diffs being 100%
mechanical, R11's only trigger. §5's gear-floor recompute used a different harness from §2's
and did not say so. §7's asymmetry argument rested on a counterfactual nobody had run.

**Method note, recorded because it is the reason a review happened at all.** An earlier draft
of this frontmatter claimed `adversarial_review: exempt-machine-report`. The nb-curator
artifact gate refused it — correctly: this file declares `sources` and `discovered_by`, which
makes it a research deliverable rather than a generated snapshot, and stamping it would have
made that gate write a false statement and the R1 gate pass on it. The refusal is why a real
review was obtained instead of a stamp, and the second seat was run only because §3 of this
very report accused the squad of not running one.
