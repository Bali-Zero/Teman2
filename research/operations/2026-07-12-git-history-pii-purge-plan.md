---
date: 2026-07-12
domain: compliance
client_case: n/a (infra/security — full-history PII/secret purge)
adversarial_review: devils-advocate (2026-07-13, DeepSeek unavailable 402 — Sonnet-direct + live repo verification; 2 critical + 2 high findings, folded into the 2026-07-13 amendment section below)
sources:
  - discovery_pii_client_record_public_docs_redacted_2026_07_12.md (memory)
  - discovery_caseos_r3_gates_and_apikey_substring_p0_2026_07_12.md (memory)
  - PENDING-ARMS.md (.claude/skills/modus/)
---

# Full-history PII/secret purge — plan (NOT executed, awaiting operator GO)

## Why this exists

`docs/CRM_AUTOMATION_GUIDELINE.md` had a real client record (company name, legal
address, NIB, NPWP, phone/email, SK number, capital, incorporation date, 4
officer/shareholder names — Ukraine client segment) embedded as a worked example.
HEAD is fixed (PR #2310, values replaced with gate-inert synthetic placeholders).
Git **history** still contains every value, in every commit that ever touched that
file, on a **public** repo (`Balizero1987/Teman2`).

Separately, this session closed a P0 where `zantara-secret-2024` was a live public
admin key (rotated 2026-07-12, #2296) — its literal value is also frozen in old
commits (docs, a couple of scripts) even though it's dead in prod now.

Since a history rewrite is expensive and disruptive (rewrites every commit hash
downstream of any touched commit, forces everyone with a local clone to
re-clone), the right call is to **scan for everything purge-worthy once, then
purge once** — not discover a second exposure next month and repeat this whole
operation.

## Non-negotiable framing

- **This plan prepares everything. It does not execute the rewrite or the
  force-push.** Those two steps are explicitly operator-gated — same class as
  `git push --force` (global safety rule) plus a legal dimension (UU PDP: a
  purge decision for real client PII is Zero's call, not a default autonomous
  action).
- Everything through "Phase 2: dry-run rewrite on a throwaway clone" is safe,
  reversible, and can be done autonomously — it never touches the real remote.
- **Phase 3 (force-push to origin) requires an explicit, scoped GO from Zero**
  on the actual findings report — not a standing generic authorization.

## AMENDMENT 2026-07-13 — adversarial review findings, folded in before execution

A `devils-advocate` review of this plan (run before Phase 2/3, per project
CLAUDE.md §6's 4-LLM-panel discipline for pre-execution critical-path plans)
found real defects, not formalities. Folded in below; the original Phase 1/2/3
text further down is superseded where it conflicts with this section.

**1. Wrong tool for whole-file removal.** The original Phase 2 showed only
`git filter-repo --replace-text ...` — that is a **content-substitution**
operation (matches bytes inside a blob, replaces them). It does NOT remove a
file from the tree, does not shrink the commit's file list, and for a file
whose content differs byte-for-byte across historical revisions (normal for a
multi-edit doc), a single replace-text rule cannot reliably match every past
version. Whole-file removal from history needs a **separate, distinct
filter-repo pass** using `--invert-paths --path <exact-path>` (or
`--paths-from-file`), run and verified independently from the replace-text
pass. Using replace-text for a file-removal target would leave the filename,
its existence, its size history, and its commit metadata all still visible in
history — "content scrambled," not "purged."

**2. Scope is NOT 4 values — it's 4 credential values + 3 distinct file paths.**
Re-scanning history (2026-07-13, this amendment) for every path variant of the
known dossier found THREE, not one:
  - `paco-pak-due-diligence-2026-05-22.html` (repo root, commit `e47949b7a3`) — dead in HEAD already (never re-added after an early rename)
  - `research/property/paco-pak-due-diligence-2026-05-22.html` (removed from HEAD via PR #2329, 2026-07-12)
  - `research/visa/clients/2026-06-03-paco-pak-S9-dossier.md` — found ONLY because this amendment's re-check followed the duplicate-path thread; led to discovering the entire `research/visa/clients/` directory (6 files, 2 named clients: paco-pak + **marc-buckner**, a second client not previously flagged) was live in HEAD — removed via PR #2332, 2026-07-12.

  **Every one of these 3 paths needs its own `--invert-paths --path` rule** in
  the Phase 2 filter-repo pass — a single rule for one path does not cover the
  others; they are different blobs at different tree locations.

**3. Fleet-coordination is now VERIFIED, not aspirational.** Before any Phase
3 execution, the operator (Zero) must re-run (not assume) this two-part check:
  ```bash
  gh pr list --state open --json number,headRefName --limit 100
  git worktree list   # on EVERY machine — M5 + Pro + Mini, via ssh pro/mini
  ```
  Then for each open branch, diff it against `origin/main` and confirm no
  branch **modifies** (status `M`, not `A`) any of the 4 target files/values —
  a branch that merely carries the pre-removal state of a file (status `A`
  because the file existed on that branch before removal landed on main) is
  harmless; a branch that actively edits the target file's content is not, and
  must be resolved (merged, rebased, or explicitly excused) before force-push.
  **This was actually run 2026-07-13**: 21 open PRs, 12 worktrees on M5 alone
  — zero branches modify any target, all touches were the harmless `A` case.
  Re-run this check again immediately before Phase 3 fires, since branches are
  created continuously on this fleet (verified: multiple new PRs opened during
  this same session).

**4. "Scan once, purge once" is being knowingly overridden — say so, don't
imply otherwise.** The operator authorized a **targeted purge** of exactly the
values/paths confirmed live-or-recently-live today (2 rotated API keys + 1
rotated Sentry token + 3 dossier file paths for 2 named clients) — NOT the
full 6402-gitleaks + 206-trufflehog backlog from the Phase 1 scan, most of
which remains untriaged. **This targeted purge is purge #1 of at least 2.** A
second rewrite will be needed once that backlog is triaged (separate,
lower-urgency lane — see `2026-07-13-full-history-scan-findings.md`). This
fleet-disruption cost (force-push + fleet-wide re-clone) will be paid twice,
not once, and that is accepted here as a reasonable urgency/cost trade-off,
not an oversight.

**5. GitHub-side caching — checked, not just noted.** Repo is confirmed
`public: true` (`gh api repos/Balizero1987/Teman2 --jq '.private'` → `false`).
Before declaring Phase 3 complete, also check fork count
(`gh api repos/Balizero1987/Teman2 --jq '.forks_count'`) — if non-zero, forks
may retain the purged blobs independent of the origin rewrite, and that's a
residual-exposure fact to report to Zero, not something the purge itself can
fix.

---

## Phase 0 — Setup (autonomous, no repo risk)

Install the two scanners, in an isolated location, no writes to the repo:

```bash
brew install gitleaks trufflehog
pip install --user git-filter-repo   # the rewrite tool itself, for Phase 2
```

Verify:
```bash
gitleaks version
trufflehog --version
git-filter-repo --version
```

## Phase 1 — Full-history scan (autonomous, read-only, safe)

Three passes, each answering a different question. All read-only against the
**real** repo clone (no clone needed for scanning — these tools read `.git`
without mutating it).

### 1a. Targeted scan — patterns we already know are dangerous
Reuse the exact regexes from the pre-commit PII gate + the API-key literal,
run against every commit in history (not just HEAD), via `git rev-list --all`
+ `git grep` per-commit (fast path, not a naive `git show` loop):

```bash
cd ~/Desktop/nuzantara
git rev-list --all | while read sha; do
  git grep -lE '(NIB|NPWP)[[:space:]:]*[0-9]{10,20}|zantara-secret-2024|admin-key-2024' "$sha" \
    2>/dev/null && echo "  ^ found in $sha"
done > /tmp/history-scan-known-patterns.txt
```

### 1b. gitleaks — generic secret patterns, full history
```bash
gitleaks detect --source ~/Desktop/nuzantara --log-opts="--all" \
  --report-path /tmp/gitleaks-full-history-report.json --report-format json
```
Catches: AWS keys, generic API tokens, private keys, DB connection strings,
anything matching gitleaks' ~150 built-in rules — independent of our own
pattern list, so it catches classes of secret we didn't think to look for.

### 1c. trufflehog — verified-secret + entropy scan, full history
```bash
trufflehog git file://$HOME/Desktop/nuzantara --json > /tmp/trufflehog-full-history-report.json
```
TruffleHog's differentiator: it attempts **live verification** of found
credentials (e.g. actually pings the API the key belongs to) — separates
"looks like a secret" from "is currently a working secret," which matters for
triage priority.

### 1d. Synthesize
One combined findings report: commit SHA, file, line, what kind of value,
which scanner(s) flagged it, whether it's still live (already rotated ones —
like the API key — get a LOW severity tag; anything unrotated gets FLAGGED for
Zero).

Deliverable: `research/operations/<date>-full-history-scan-findings.md` — every
finding listed, nothing silently dropped (no silent caps, per this repo's own
workflow discipline).

## Phase 2 — Dry-run rewrite (autonomous, zero risk to the real repo)

**Never touches `~/Desktop/nuzantara` or `origin`.** Work happens in a
throwaway clone:

```bash
cd /tmp
git clone --no-local ~/Desktop/nuzantara nuzantara-purge-test
cd nuzantara-purge-test
```

**Two distinct operations, run as two distinct filter-repo passes (per the
2026-07-13 amendment above — do not conflate them):**

**Pass A — string replacement (for short credential values):**
```bash
cat > /tmp/purge-replacements.txt <<'EOF'
zantara-secret-2024==>REDACTED-ROTATED-KEY-2296
admin-key-2024==>REDACTED-ROTATED-KEY-2296
<sentry-token-value>==>REDACTED-ROTATED-SENTRY-TOKEN
EOF
git filter-repo --replace-text /tmp/purge-replacements.txt --force
```

**Pass B — whole-file removal (for the 3 dossier file paths — run AFTER Pass A,
same clone, filter-repo composes sequentially):**
```bash
git filter-repo --invert-paths \
  --path paco-pak-due-diligence-2026-05-22.html \
  --path research/property/paco-pak-due-diligence-2026-05-22.html \
  --path research/visa/clients/2026-06-03-paco-pak-S9-dossier.md \
  --path research/visa/clients/2026-06-03-marc-buckner-S9-dossier.md \
  --path research/visa/clients/2026-05-31-marc-buckner-visa-guidance.html \
  --path research/visa/clients/2026-05-31-marc-buckner-visa-guidance.pdf \
  --path research/visa/clients/S9-cases-FROZEN.json \
  --path research/visa/clients/_render_marc_buckner.py \
  --force
```

Verify: `--invert-paths` removes the path (and the blob, once unreferenced)
from every commit — confirm with `git log --all --follow -- <path>` returning
nothing, not a scrambled-content file.

Verify against the SAME scanners from Phase 1, on the rewritten clone — the
findings list must go to zero:

```bash
gitleaks detect --source /tmp/nuzantara-purge-test --log-opts="--all"
trufflehog git file:///tmp/nuzantara-purge-test --json
```

Also verify nothing else broke: run the test suite on the rewritten clone,
confirm branch/tag count matches expectations, confirm no unrelated content
was mangled by an over-broad replacement pattern (same discipline as scar
family #3 — guard-over-match: a replacement rule too broad could clobber
legitimate content that happens to contain the same substring).

**Output of Phase 2**: a report showing (a) the rewritten clone is clean per
both scanners, (b) tests pass, (c) a diff-of-diffs summary of exactly what
changed, commit by commit, so Zero can review the actual blast radius before
authorizing Phase 3.

## Phase 3 — THE ACTUAL PURGE (operator-gated, NOT autonomous)

Only after Zero reviews the Phase 2 report and gives an explicit GO on the
**specific findings list** (not a generic "yes go ahead" — the GO should name
which findings are being purged, since new commits may have landed on origin
between Phase 2 and this step and need re-checking):

1. Re-run Phase 1 scan against current `origin/main` (catch any commits landed
   since the dry run).
2. Re-run Phase 2 rewrite against the up-to-date clone.
3. **Coordinate with anyone else who has a local clone or an open branch** —
   after the force-push, every existing local clone is stale and must be
   re-cloned (not pulled) to avoid a divergent-history mess. This repo has an
   active multi-session fleet (M5/Pro/Mini + parallel agent worktrees) — this
   step alone is why Phase 3 cannot be casual.
4. `git push --force --all && git push --force --tags` to `origin`.
5. On every machine/worktree: **delete and re-clone**, do not attempt to
   reconcile a rewritten history with `git pull`.
6. Verify on GitHub's side: confirm the old commits are unreachable (GitHub
   itself may cache old commit data for a grace period — worth an explicit
   support request to purge their cache/CDN copies too, since a force-push
   alone doesn't guarantee GitHub's internal caches drop instantly).
7. Legal follow-up (Zero's call, not code): whether UU PDP obligations require
   notifying the affected client given the exposure window, independent of the
   technical purge.

## What I will NOT do without a fresh, scoped GO

- Run Phase 3 itself (the force-push).
- Decide unilaterally which findings from Phase 1 are "worth" purging vs
  noise — that judgment call, especially anything PII-adjacent, goes to Zero
  with the full findings list, not a filtered summary.
- Touch `origin/main` branch protection settings to permit the force-push (this
  repo has strict branch protection — force-push to `main` is blocked by
  default and enabling it temporarily is itself a config change requiring
  explicit authorization).

## Estimated cost/time

- Phase 0+1 (install + full scan, 3 tools): ~15-30 min, fully autonomous, zero
  risk — can run today.
- Phase 2 (dry-run rewrite + verify): ~30-60 min depending on repo size and
  finding count, fully autonomous, zero risk to real repo.
- Phase 3: blocked on Zero's review of the Phase 2 report + explicit GO;
  execution itself ~15 min plus fleet re-clone coordination (all machines).
