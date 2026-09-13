# GATE REPORT — PR #6243 — final on-disk gate (fresh Opus 5, outside the chain)

**VERDICT: PASS-WITH-CONDITIONS**

Mission SHWEB-20260911 / window W1-SH-TECH · colour BLUE · Gear 2 · PR #6243
Gated HEAD `416e4e09faa5bd562f3cd93867c6f29ed7da9e72` · base `ea50eb262f9ed96ce070cb407b55202002b0dae8`
HEAD re-confirmed equal to the PR head at gate time:
`gh pr view 6243 --json headRefOid --jq .headRefOid` -> `416e4e09faa5bd562f3cd93867c6f29ed7da9e72` (exit 0)

---

## FINDINGS

### F1 [MAJOR] The PR body is stale relative to the frozen head

Command: `gh pr view 6243 --json body --jq .body`
Excerpt: "Three declared deltas on top of the patch, each registered in the brief: **D1** ... **D2** ... **D3** ..."
and "POST review (refuter on HEAD): Codex Sol, pending." and table rows "Full `npm run build` | Vercel preview
of this PR (same buildCommand as production), pending" / "Browser on the preview ... | pending" and
"`vitest run second-home secondhome llms-article-exports kbli-llms-corpus` | 31 files / 552 tests passed".

Against `brief.yml`, which declares FIVE deltas (D1..D5) and records those items as done:
"Declared delta D5 (POST refuter round 2 F3/F4, ordered by the imperator 13:37Z): generate-llms-full.ts
declares ARTICLES_ONLY first and sets FULL_ONLY only when ARTICLES_ONLY is off (+ 2 comment lines)..."
and acceptance #5 "status: verified # after D5: vitest 31 files/553".

Why it matters: D5 is NOT cosmetic. It adds `isCanonical` to the article record and
`.filter((a) => a.isCanonical)` on the freshness list, changing what `llms.txt` publishes. The PR body is
the record that survives the merge and today under-describes the change set. Not a blocker (the change
itself is in mandate and tested), but it must be corrected before arming.

### F2 [MAJOR] POST refuter round 3 is not on disk

Command: `gh pr diff 6243 --name-only | grep reviews/`
Output: reviews/post-refuter-codex-sol-round1.txt, post-refuter-codex-sol-round2.txt,
post-refuter-codex-sol.prompt.txt, pre-review-codex-sol.prompt.txt, pre-review-codex-sol.txt,
second-reader-kimi-k3.txt -> round 1 and round 2 only, no round 3.
`brief.yml` declares it: refuter_post: "... round 2 REWORK on a3e1ee39bd ..., round 3 on the refrozen head".
This gate does NOT substitute for it: generator != grader applies to the refuter too.

### F3 [MINOR] Backend Shard 3 is red from infrastructure, not from code

Command: `gh pr checks 6243 --json name,state,link --jq '.[] | select(.state=="FAILURE")'`
Output: `Backend Shard 3  https://github.com/Bali-Zero/Teman2/actions/runs/34606686982/job/103287471285`
Run id 34606686982 · Job id 103287471285.
Command: `gh api repos/Bali-Zero/Teman2/actions/jobs/103287471285 --jq '.conclusion + steps(failure)'`
Output: `failure | Initialize containers` and `failure | Upload shard receipts`.
Command: `gh api repos/Bali-Zero/Teman2/check-runs/103287471285/annotations`
Excerpt:
failure: Docker pull failed with exit code 1
warning: Docker pull failed with exit code 1, back off 6.862 seconds before retry.
warning: Docker pull failed with exit code 1, back off 2.761 seconds before retry.
failure: No files were found with the provided path: /home/runner/work/_temp/shard-receipts/.
The failure is at container initialisation: no test ever executed. Cause is KNOWN, so a rerun is
legitimate and is not a blind rerun of an unexplained red.

### F4 [MINOR] "Harness floor recompute" red is an external status

Per docs/runbooks/merge-queue-discipline.md §6septies this is an external status, not code. No action
required of the build.

### F5 [MINOR] Acceptance #7 is `status: pending` by design

`brief.yml` last acceptance: "WHEN the merged commit is promoted by Vercel, THEN balizero.com/llms-id.txt
and /llms-full.txt SHALL match the release sources except the generation date ... status: pending".
This is a post-merge prove-live obligation, not a gap in this PR.

---

## WHAT PASSED

**1. Perimeter — PASS.** `gh pr diff 6243 --name-only` -> 30 files, all inside the declared perimeter.
No lockfile (package-lock.json / pnpm-lock / yarn.lock absent from the diff), no `npm audit fix`, no
version bump of js-yaml/sharp/mysql2, no MDX, no price list, no fact registry, no DB/migration, no
apps/mouth/src/app/(visa-oracle)/**, no apps/mouth/src/app/visa/** beyond the two studio files, no
packages/core/**, no root layout.tsx, no team-roster.ts, no globals.css, no apps/website/**.
`.secrets.baseline` carries 38 entries, ALL `"is_secret": false`, ALL anchored to
`"filename": "evidence/2026-09/agent-air-m5-mouth-shweb-w1-tech-20260911-1bf4ea22/contract-lock.json"`,
with 0 content lines removed (the single `^-` line is the diff header).

**2. Diff content — PASS.** `git diff ea50eb262f..416e4e09fa -- <product files>`:

- StudioApp.tsx and ScenarioToggle.tsx: exactly one added line each,
  `fontVariantNumeric: "tabular-nums",` with `fontFamily: "var(--font-serif, Georgia, serif)"` untouched.
  Cormorant preserved. No other visual change.
- package.json: the build script line only, `LLMS_GENERATE_FULL_ONLY=1` -> `LLMS_GENERATE_ARTICLES_ONLY=1`.
- generate-llms-full.ts: precedence is GUARDED —
  `const FULL_ONLY = process.env.LLMS_GENERATE_FULL_ONLY === "1" && !ARTICLES_ONLY;`
  and the KBLI block is `if (!ARTICLES_ONLY && fs.existsSync(KBLI_DATA_PATH))`.
  `isCanonical` is used only by the freshness `.filter`; it is never serialised into the EN/ID exports
  (the forEach emits title/category/url/publishedAt/excerpt/content only), so export shape is unchanged.
- The translation filter is IN MANDATE, not scope creep. W1-studio-tech.md:20 requires
  "draft/noIndex esclusi, traduzioni nel full ma freshness senza URL duplicate".
- No `--no-verify`: deltas D2 (Prettier) and D3 (research gate) are precisely the pre-commit hooks firing.

**3. Waiver retirement — PASS, verified against an independent source (the real lockfile).**
Command: `node -e` over /Users/balizero/nuzantara/package-lock.json
node_modules/@hono/node-server 2.0.11
node_modules/find-my-way 9.7.0
node_modules/gray-matter/node_modules/js-yaml 3.15.1
node_modules/js-yaml 4.3.1
These match the justification written into npm_audit_gate.py verbatim. The recorded real audit
(npm-audit-gate.txt) shows `gate_rc=1` on js-yaml GHSA-2883, mysql2 GHSA-3f6p/GHSA-rgwj and sharp
GHSA-rgj7 only — none of the four retired ids. `WAIVE` is now `{}`.

**4. Negative cases — PASS (item 5 of the mandate).**

- Retired-waiver reintroduction: `test_retired_advisories_get_no_standing_waiver` loops the four
  retired ids through the SHIPPED WAIVE via `run_cli` and asserts `== 1` for each, so restoring any
  waiver turns it red. Its docstring is honest about the limit: "Upstream the two Hono advisories are
  Moderate, which BLOCKING ignores by design, so this proves the waiver is gone — not that a real
  Moderate reintroduction would block." That is exactly Codex Sol PRE-review F3, cured.
- Old build flag: llms-article-exports.test.ts reads the REAL flag out of package.json —
  `scripts.build.match(/^(LLMS_GENERATE_\w+)=1 tsx scripts\/generate-llms-full\.ts &&/)` then
  `expect(flag).not.toBeNull()` — so reverting the build line breaks the test. Recorded proof
  (negative-old-build-flag.txt): mutated to FULL_ONLY -> "Tests 2 failed (2)", both inherited cases.
- The test also runs `it.each([["0"],["1"]])` so the inherited-FULL_ONLY=1 path is pinned, and asserts
  the exact ordered five-entry freshness block plus `toHaveLength(1)` on the canonical URL.

**5. Brief and evidence — PASS.**

- Slug: `python3 scripts/ci/evidence_paths.py --ref agent/air-m5/mouth/shweb-w1-tech-20260911`
  -> `slug: agent-air-m5-mouth-shweb-w1-tech-20260911-1bf4ea22`, identical to the directory used.
- brief.yml carries gear: 2, colour: BLUE, adversarial_review with pre_review "Codex Sol (gpt-5.6-sol)",
  second_reader "Kimi K3", refuter_post, and `pii: none`.
- Review verdicts quoted in the brief are FAITHFUL to the files:
  pre-review-codex-sol.txt line 1 "VERDICT: GO-WITH-CONDITIONS" (brief: GO-WITH-CONDITIONS);
  second-reader-kimi-k3.txt line 4 "**VERDICT: HOLDS-WITH-CONDITIONS**" (brief: HOLDS-WITH-CONDITIONS);
  post-refuter round1 line 1 "VERDICT: REWORK" (brief: "round 1 REWORK");
  post-refuter round2 line 3 "VERDICT: REWORK" (brief: "round 2 REWORK 13:22Z").
  No misreported review. NOT REWORK-BUILD on this axis.
- Size exception declared and ACCURATE: brief says "evidence +1028";
  `git diff --numstat ea50eb262f..416e4e09fa -- evidence/ | awk` -> `+1028 -0`. Exact match.
  (This cures round-2 MINOR 5, which had caught a +608 vs +868 discrepancy.)
- contract-lock.json: baseSha `ea50eb262f9ed96ce070cb407b55202002b0dae8` matches the gate base;
  frozenAt is self-explaining ("lock contents frozen before BUILD; head freezes are listed in
  headFreezes") and headFreezes lists `a3e1ee39bd` plus the refrozen head described as "the
  evidence-only commit that adds this line, child of commit 40646c54be (D5)". Self-consistent: the
  head commit cannot contain its own SHA.
- Bites line PRESENT in the PR body, naming a CONSUMER and an OBSERVATION:
  "Bites: the Studio visitor on balizero.com/visa/second-home/studio and the EN/ID crawlers of
  balizero.com/llms-id.txt / /llms.txt. Observation: after promotion, /llms-id.txt carries the release
  date and the release's canonical ID records instead of `Last updated: 2026-08-11` / 785 records..."
  Builder Contract 2 satisfied.

**6. Live/preview claim — internally consistent, NOT re-observed by this gate.**
preview-verification.md cites deployment `dpl_DnyvbuFFWcEh8oWesLqzBUw5jqxS` at commit `d5e267c735` and
round-2 deployment `dpl_Dxv7wxRwHBVgLJET6V1vjWA7Tawk` at commit `40646c54be`, both READY.
`git merge-base --is-ancestor` confirms d5e267c735, 40646c54be, ccb05384b1, a3e1ee39bd, 10ce4e8659 and
b87db24a30 are ALL ancestors of 416e4e09fa. And `git diff --name-only 40646c54be..416e4e09fa` returns
only evidence/** paths, so 40646c54be is genuinely the last product-tree commit of this head — the
preview was built from the shipped product tree. Marked: CLAIMED BY WINDOW, NOT RE-OBSERVED BY GATE.

**7. PII / secrets — PASS.** `gh pr diff 6243 | grep -nEi` for emails, +62 phone numbers, `sk-`, `ghp_`,
`AKIA` tokens on added lines -> no results. Evidence files carry no client PII.

---

## SPOT-CHECK COMMANDS AND EXIT CODES (run by this gate, on the exported read-only tree)

    gh pr view 6243 --json headRefOid --jq .headRefOid        exit 0   416e4e09fa… (matches gated head)
    git diff --check ea50eb262f..416e4e09fa                   exit 0   (clean, no whitespace errors)
    <venv>/python3 -m pytest scripts/ci/test_npm_audit_gate.py -q -p no:randomly
                                                              19 passed in 0.05s
    vitest run src/lib/llms-article-exports.test.ts \
               src/lib/kbli-llms-corpus.test.ts --reporter=dot
                                                              Test Files 2 passed (2)
                                                              Tests 19 passed (19)

Note on the vitest lane: the exported tree needed `node_modules` symlinks to the repo's installed
modules (root + apps/mouth) and the root `vitest` binary; both symlinks were created INSIDE the gate
scratchpad, never in the repo or in the window's worktree. Nothing was CANNOT-VERIFY.

---

## PWC CONDITIONS (one line each, ledger-ready)

1. PR #6243 body: restate deltas as D1-D5, replace the three "pending" rows (POST refuter, npm run build, browser) with their actual outcome, correct the test count from 552 to 553 — before arming.
2. PR #6243: obtain Codex Sol POST refuter round 3 on HEAD 416e4e09fa and commit it to evidence/2026-09/agent-air-m5-mouth-shweb-w1-tech-20260911-1bf4ea22/reviews/.
3. PR #6243: rerun Backend Shard 3 (known cause: "Docker pull failed with exit code 1" at step Initialize containers, run 34606686982 job 103287471285, no test executed) and require green.
4. PR #6243 post-promotion prove-live: /llms-id.txt shows the release date and canonical ID records, /llms.txt freshness lists each URL exactly once, served price nodes compute font-variant-numeric tabular-nums with Cormorant (closes acceptance #7).

---

## GATE RECEIPT

    mission     SHWEB-20260911
    window      W1-SH-TECH
    colour      BLUE
    gear        2
    PR          6243
    gated HEAD  416e4e09faa5bd562f3cd93867c6f29ed7da9e72
    base        ea50eb262f9ed96ce070cb407b55202002b0dae8
    gate        fresh Opus 5, outside the contribution chain, read-only

    COMMANDS AND EXIT CODES
    git fetch -q origin agent/air-m5/mouth/shweb-w1-tech-20260911          exit 0
    gh pr view 6243 --json headRefOid                                      exit 0  (HEAD match)
    git archive 416e4e09fa | tar -x -C <scratch>/tree                      exit 0
    gh pr diff 6243 --name-only                                            exit 0  (30 files, in perimeter)
    git diff --numstat ea50eb262f..416e4e09fa                              exit 0
    git diff ea50eb262f..416e4e09fa -- <product files>                     exit 0
    git diff --check ea50eb262f..416e4e09fa                                exit 0
    pytest scripts/ci/test_npm_audit_gate.py -q -p no:randomly             19 passed
    vitest run llms-article-exports.test.ts kbli-llms-corpus.test.ts       19 passed / 2 files
    node -e (read package-lock.json versions)                              exit 0
    python3 scripts/ci/evidence_paths.py --ref <branch>                    exit 0  (slug match)
    git merge-base --is-ancestor <6 preview/proof commits> HEAD            exit 0  (all ancestors)
    git diff --name-only 40646c54be..416e4e09fa                            exit 0  (evidence-only)
    gh pr checks 6243 --json name,state,link                               exit 0
    gh api repos/Bali-Zero/Teman2/actions/jobs/103287471285                exit 0
    gh api repos/Bali-Zero/Teman2/check-runs/103287471285/annotations      exit 0
    gh pr view 6243 --json body                                            exit 0
    gh pr view 6243 --json autoMergeRequest,mergeStateStatus               exit 0  (auto=null, BLOCKED)

    VERDICT: PASS-WITH-CONDITIONS

    BLOCKER count: 0
    MAJOR:  F1 (stale PR body), F2 (refuter round 3 absent)
    MINOR:  F3 (Shard 3 infra red), F4 (Harness = external status), F5 (acceptance #7 pending by design)

    This gate did not edit, commit, push, arm, merge, deploy or post any status, and wrote nothing
    outside its own scratchpad. The verdict is NOT published by the gate; the imperator posts it.
    Repo working tree at gate close: only `?? shared/hotfix_audit.jsonl`, untracked, pre-existing at
    session start, owned by the operator/hotfix lane — left untouched.

---

# DELTA RECEIPT 4ec63cdbe7

Read-only delta re-check of PR #6243 against the CURRENT head, same rules as the gate above.
Previous gated HEAD `416e4e09faa5bd562f3cd93867c6f29ed7da9e72` -> new HEAD
`4ec63cdbe7978aa30600f28387af9238837d7ff0`.

## Checks

**(1) PR head equals 4ec63cdbe7 — PASS**
`gh pr view 6243 --json headRefOid --jq .headRefOid`
-> `4ec63cdbe7978aa30600f28387af9238837d7ff0` exit 0

**(2) The new head descends from the gated head — PASS**
`git merge-base --is-ancestor 416e4e09fa 4ec63cdbe7` exit 0
The gate's verdict is therefore carried forward on a strict descendant, not a rewritten branch.

**(3) The delta touches evidence only — PASS**
`git diff --stat 416e4e09fa..4ec63cdbe7` exit 0
.../FINAL-motore-design-2026-09-11.pinned.txt | 95 ----------------------
.../brief.yml | 4 +-
2 files changed, 2 insertions(+), 97 deletions(-)
`git diff --name-status 416e4e09fa..4ec63cdbe7`
D evidence/2026-09/agent-air-m5-.../FINAL-motore-design-2026-09-11.pinned.txt
M evidence/2026-09/agent-air-m5-.../brief.yml
`git diff --name-only 416e4e09fa..4ec63cdbe7 -- ':!evidence/**' | wc -l` -> `0`
NO product file, no test, no script, no .secrets.baseline. The brief.yml hunk is exactly the
size_exception block: "evidence +1028 (... the v5 FINAL spec pinned)" becomes
"evidence +933 (... v5 FINAL by sha256 only)". +2/-2 as declared.

**(4) The deleted file remains pinned by sha256 — PASS, chain verified end to end**
`git show 416e4e09fa:.../FINAL-motore-design-2026-09-11.pinned.txt | shasum -a 256`
-> `4bf043675730c225e255590edf8a41e821f14d4700f9a90da8c5085a78b50d04`
`git show 4ec63cdbe7:.../contract-lock.json | grep finalSpecSha256`
-> line 16 `"finalSpecSha256": "4bf043675730c225e255590edf8a41e821f14d4700f9a90da8c5085a78b50d04",`
`git show 4ec63cdbe7:.../M5-package-MANIFEST.sha256 | grep 4bf04367`
-> line 31 `4bf0436757...50d04  ./pacchetto/FINAL-motore-design-2026-09-11.md`
`shasum -a 256 /Users/balizero/Desktop/SHWEB-20260911-mouth-final/pacchetto/FINAL-motore-design-2026-09-11.md`
-> `4bf043675730c225e255590edf8a41e821f14d4700f9a90da8c5085a78b50d04`
All four agree. The deleted `.pinned.txt` was byte-identical to the authority `.md`, the digest
survives in TWO committed records, and the off-repo authority file still hashes to it today.
The authority link is intact; only the duplicated copy is gone.

**(5) Total churn below the 1828 ceiling — PASS**
`git diff --numstat ea50eb262f..4ec63cdbe7 | awk '{a+=$1;d+=$2} END{print a+d}'` -> `1756` (< 1828)
Breakdown re-measured, and the brief's revised size_exception is EXACT on all three blocks:
product + research +460 / -57 (claimed +460/-57)
evidence +933 / -0 (claimed +933)
.secrets.baseline +306 / -0 (claimed +306)
1028 - 95 = 933, so the revised figure is arithmetically consistent with the deletion.

**(6) Whitespace clean — PASS**
`git diff --check ea50eb262f..4ec63cdbe7` exit 0

## Delta verdict

**PASS-WITH-CONDITIONS — carried over unchanged.** No new finding.

The delta is evidence hygiene on a strict descendant: it removes one duplicated copy of the authority
spec and corrects the size_exception count to match. It touches no product file, no test and no
security surface, so every PASS in the gate above still holds on 4ec63cdbe7 without re-execution.
The four conditions are unchanged and F1 is now PARTIALLY addressed only in the brief, not in the PR
body — condition 1 still stands.

    mission     SHWEB-20260911     window W1-SH-TECH     colour BLUE     gear 2     PR 6243
    prior gated HEAD  416e4e09faa5bd562f3cd93867c6f29ed7da9e72
    new HEAD          4ec63cdbe7978aa30600f28387af9238837d7ff0   (descendant, verified)
    base              ea50eb262f9ed96ce070cb407b55202002b0dae8

    git fetch -q origin agent/air-m5/mouth/shweb-w1-tech-20260911      exit 0
    gh pr view 6243 --json headRefOid --jq .headRefOid                 exit 0   (4ec63cdbe7, match)
    git merge-base --is-ancestor 416e4e09fa 4ec63cdbe7                 exit 0
    git diff --stat 416e4e09fa..4ec63cdbe7                             exit 0   (2 files, evidence only)
    git diff --name-status 416e4e09fa..4ec63cdbe7                      exit 0   (1 D, 1 M)
    git diff --name-only 416e4e09fa..4ec63cdbe7 -- ':!evidence/**'     exit 0   (0 files)
    git show 416e4e09fa:<deleted file> | shasum -a 256                 exit 0   (4bf04367…50d04)
    git show 4ec63cdbe7:contract-lock.json | grep finalSpecSha256      exit 0   (match)
    git show 4ec63cdbe7:M5-package-MANIFEST.sha256 | grep 4bf04367     exit 0   (match)
    shasum -a 256 <off-repo authority .md>                             exit 0   (match)
    git diff --numstat ea50eb262f..4ec63cdbe7 | awk                    exit 0   (1756 < 1828)
    git diff --check ea50eb262f..4ec63cdbe7                            exit 0

    DELTA VERDICT: PASS-WITH-CONDITIONS (carried over, no new finding)
    BLOCKER 0 · MAJOR F1 F2 (unchanged) · MINOR F3 F4 F5 (unchanged)

    This delta check edited, committed, armed, merged and posted nothing, and wrote only to this file.
