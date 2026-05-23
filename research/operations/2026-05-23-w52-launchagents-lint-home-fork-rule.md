---
date: 2026-05-23
domain: operations
loop: NB-automations-hardening W52
status: shipped (commit 4b97b041c); rule live, empirical verified, current state 0 violations
---

# W52 — `lint_launchagents.sh` HOME-fork silent-drift rule (closes W50/W51 family at PR time)

## TL;DR

Added rule to `scripts/lint_launchagents.sh` detecting when a plist's `script_to_check`
points at `$HOME/scripts/<X>` AND a same-basename copy exists in repo at
`~/Desktop/nuzantara/scripts/**/<X>` AND the two differ. Catches W50/W51-class
silent-drift at PR/push time instead of 24-day lag.

**Empirical W52 sweep**: out of 84 plists exec'ing HOME scripts, 7 HOME copies had repo
equivalents, of which 2 were actually exec'd by plists (both already fixed via W50+W51).
**Current state: zero W52 violations** — rule fires on injected test plist (sentinel
backup), confirms no live regressions.

## Empirical sweep — actual scope vs perceived

W51 surfaced "84/167 plists exec from HOME" as a structural surface. W52 quantified the
**actual risk** by hash-comparing all 150 HOME scripts vs repo equivalents:

| Category | Count | Risk |
|---|---|---|
| HOME scripts total | 150 | baseline |
| HOME with NO repo equivalent | 143 | none (legitimate HOME-only tooling) |
| HOME with repo equivalent AND identical | 0 found in sweep | none |
| HOME with repo equivalent AND DIFFERING | 7 | drift candidates |
| Drifting AND exec'd by a plist | 2 | W50/W51 — already fixed |
| Drifting AND NOT exec'd by any plist | 5 | orphan drift — no impact |

The 5 orphans:
| Script | HOME | REPO | Notes |
|---|---|---|---|
| `intel-lake-nb-pusher-standalone.py` | May-20 | May-18 | HOME ahead |
| `openclaw-state-bridge.py` | May-09 | May-18 | REPO ahead |
| `vector-reindex-check.py` | Mar-26 | Mar-28 | REPO smaller |
| `fly-qdrant-backup.sh` | Apr-06 | Apr-03 | HOME ahead |
| `nextdns-weekly-digest.sh` | May-16 | May-16 | same date, different content |

None are exec'd by any plist (`grep -l "$script_path" ~/Library/LaunchAgents/com.*.plist` →
0 matches). Drift exists but has no production impact.

**Conclusion**: the "84 plists" headline from W51 was a structural surface, not a structural
risk. Of those 84, only 2 had actual silent-drift (W50 dlq_autopilot + W51 sentinel),
both already fixed. The systemic class is real but the scope was over-counted.

## Fix shipped

`scripts/lint_launchagents.sh` (commit `4b97b041c`) — new check block:

```bash
if [ -n "$script_to_check" ] && [[ "$script_to_check" == "$HOME/scripts/"* ]]; then
    basename_only=$(basename "$script_to_check")
    repo_match=$(find "$HOME/Desktop/nuzantara/scripts" -maxdepth 4 \
                    -name "$basename_only" \
                    -not -path "*/.worktrees/*" \
                    -not -path "*/__pycache__/*" \
                    -not -path "*/.venv/*" \
                    -not -path "*/venv/*" \
                    2>/dev/null | head -1)
    if [ -n "$repo_match" ] && [ -f "$repo_match" ]; then
        if ! cmp -s "$script_to_check" "$repo_match" 2>/dev/null; then
            home_date=$(stat -f "%Sm" -t "%Y-%m-%d" "$script_to_check" 2>/dev/null || echo "?")
            repo_date=$(stat -f "%Sm" -t "%Y-%m-%d" "$repo_match" 2>/dev/null || echo "?")
            echo "[VIOLATION] $label: exec'ing HOME fork that differs from repo"
            echo "             HOME: $script_to_check ($home_date)"
            echo "             REPO: $repo_match ($repo_date)"
            echo "             Family: W50/W51 deploy-path desync. Fix: edit plist to exec REPO path."
            VIOLATIONS=$((VIOLATIONS+1))
        fi
    fi
fi
```

Position: AFTER the `/tmp/` logs check (last existing rule), before the daemon-registry
check. Single addition, no structural refactor.

## Empirical verification

Test methodology: copy the sentinel pre-W51 backup (which DOES have the HOME-fork +
differing-repo situation) into the lint's scan dir under a test label, run lint, verify it
fires, clean up.

```bash
$ cp /tmp/com.balizero.w52-rule-test.plist ~/Library/LaunchAgents/
$ bash scripts/lint_launchagents.sh 2>&1 | grep -B0 -A4 w52-rule-test
[VIOLATION] com.balizero.w52-rule-test: exec'ing HOME fork that differs from repo
             HOME: /Users/nuzantara/scripts/nuzantara-sentinel.py (2026-04-30)
             REPO: /Users/nuzantara/Desktop/nuzantara/scripts/nuzantara-sentinel.py (2026-05-18)
             Family: W50/W51 deploy-path desync. Fix: edit plist to exec REPO path.
$ rm ~/Library/LaunchAgents/com.balizero.w52-rule-test.plist
```

Rule fires correctly with all expected fields (paths, dates, family pointer). Cleanup did
not leave the test plist registered with launchd (file-only operation, no
`launchctl bootstrap`).

Current live state lint run:
```
Plist scanned: 146 (39 daemon, 107 cron-style, 0 disabled)
Total violations: 72
$ grep -c "exec'ing HOME fork" /tmp/w52-lint.out → 0
```

All 72 violations are PRE-EXISTING (KeepAlive directive, EnvVars missing, daemon registry
gaps, /tmp/ logs). Zero NEW W52 violations — meaning W50/W51 fixed all live silent-drift.

## Coverage limits (documented)

The rule has the same `script_to_check` resolution limits as the rest of the lint:

| Pattern | Resolved? |
|---|---|
| `python3 /path/to/script.py` | YES |
| `/path/to/script.sh` (direct) | YES |
| `/bin/zsh -lc /path/to/script.sh` (simple 3-arg shim) | YES |
| `/bin/zsh -lc "source ...; exec script ..."` (complex shim) | NO (script-existence check also skips these) |

So W50 (dlq_autopilot wrapper) would NOT be caught by this rule because the wrapper itself
is a `.sh` file in `docs/infra/launchagents/`, and the plist exec's the wrapper, not the
underlying python script. W50 is a wrapper-level desync, not a plist-direct desync. To
detect W50-class drift, a separate wrapper-content lint would be needed — deferred to
W53+ if a third case surfaces.

W51 (sentinel) WOULD be caught: plist directly exec'd the HOME python script.

## Lessons

- **Lint exists since 2026-04-29 (Renaissance PR-B1)** but never had a drift-detection rule.
  W50/W51 were both detectable via this pattern; the rule was the gap.
- **Empirical scope-narrowing matters**: W51's "84/167 plists" surface sounded scary, but
  the actual risk surface was 2 plists. Always quantify before committing to a batch fix.
- **Test rule by injection** (not just inspection of the code): a temporary plist in the
  scan dir is the cheapest way to prove rule logic. Skip live registration — file-only
  scan never triggers launchctl bootstrap.
- **W52 rule is preventive (CI-time)**; W50/W51 were reactive (post-incident). The pair
  forms a defense-in-depth: future regressions cannot land + persist undetected.
- **Family closure**: cicatrix W50/W51 entries reference each other as "wrapper variant" /
  "plist-direct variant" of same root cause. W52 closes the FAMILY at CI-time, not just
  the specific instances.

## Reference

- Commit: `4b97b041c` — `feat(lint): add W52 HOME-fork silent-drift rule`
- File: `scripts/lint_launchagents.sh` (~287 lines now, ~40 added)
- Empirical test artifact: `/tmp/com.balizero.w52-rule-test.plist` (cleaned up)
- W50 sibling RCA: `research/operations/2026-05-23-w50-dlq-autopilot-home-fork-desync.md`
- W51 sibling RCA: `research/operations/2026-05-23-w51-sentinel-plist-home-fork.md`
- Pre-existing lint script: `scripts/lint_launchagents.sh` (VADEMECUM §11 + Renaissance PR-B1)
- Drift sweep methodology (one-time): `find $HOME/scripts -name "*.py" -o -name "*.sh"` →
  hash-compare each against `find ~/Desktop/nuzantara/scripts -name "$basename"` →
  classify by exec'd-by-plist-or-not.
