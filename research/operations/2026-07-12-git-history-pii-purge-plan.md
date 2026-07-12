---
date: 2026-07-12
domain: compliance
client_case: n/a (infra/security — full-history PII/secret purge)
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

Build the `git-filter-repo` replacement rules from the Phase 1 findings (one
rule per confirmed value — literal string replacement, e.g.
`zantara-secret-2024==>REDACTED-ROTATED-KEY`, or the actual client field
values ==> synthetic placeholders):

```bash
git filter-repo --replace-text /tmp/purge-replacements.txt --force
```

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
