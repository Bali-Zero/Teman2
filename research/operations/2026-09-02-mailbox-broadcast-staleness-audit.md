---
adversarial_review: codex
---

# 2026-09-02 — fleet-mailbox broadcast staleness audit

**Context**: follow-up to the `mailbox_deliver_once` mandate (2026-09-01 tokenaudit finding, "decine,
ripetuti" `queue_unstick`-style pages at session start). That investigation found no defect in
`infra/claude-hooks/mailbox_inject.py` — deliver-once-per-session is already correct (PR #5051,
2026-08-27) and was already live on Pro/Mini; only M5 was running a pre-S3 stale copy (HOME-fork
drift, tracked in `.claude/skills/modus/PENDING-ARMS.md`, `owner: operator[control-plane]`).

This audit asks a different question: even at "delivered once per session, correctly", is a fresh
session's startup tax (37 live broadcasts on Pro at last count, each ~300 tokens, drained
`MAX_MESSAGES_PER_FIRE=3` at a time over its first ~13 tool calls) actual signal, or mostly stale
noise the sender never retracted?

## Method

`ssh pro`, for every live `*.md` file under `~/.nuzantara-mailbox/broadcast/` (i.e. not yet
renamed `.superseded-`/`.expired-`/`.delivered-`/`.skipped-oversize-`), extracted the `key:`
front-matter line. 34 of the sampled files carried a `queue_unstick:<PR#>` key (the other 3 were
one-off direct-style broadcasts: `pii-gate-prs-hold*`, `git-show-ref-path-zsh-trap` — out of scope,
not sent by a cron with a resolve-state to check against). For each of the 34 PR numbers, ran
`gh -R Bali-Zero/Teman2 pr view <n> --json state,mergeStateStatus`.

## Result

| bucket | count | share |
|---|---|---|
| MERGED | 18 | 53% |
| CLOSED (not merged) | 10 | 29% |
| OPEN but no longer DIRTY (BLOCKED/UNKNOWN) | 5 | 15% |
| OPEN and still DIRTY (genuinely current) | 1 | 3% |

**33/34 (97%) were stale** — the page's own subject (a DIRTY PR needing manual conflict
resolution) was no longer true. Oldest live broadcast at sample time: mtime 2026-08-31T05:14:43Z
(3 wall-days old, well inside the 48h `DEFAULT_TTL_SECONDS`/`--ttl 48` window every message
carries via its `expires:` front matter — TTL alone does not catch this, since the sender keeps
re-signalling the SAME PR with a fresh timestamp as long as it stays dirty, and the mailbox has no
way to know the underlying condition resolved without being told).

## Root cause

`scripts/queue_unstick.py::send_dirty_signal` broadcasts a `queue_unstick:<PR#>` page whenever a
PR is DIRTY and the local `dirty_seen` fingerprint (head SHA + conflict-file-set hash) changed
since the last signal for that PR. It has no symmetric "this PR is no longer dirty, take the page
back" step — once sent, a page lives until its TTL expires, sender-blind to the resolution.

## Fix (PR opened same day, `agent/air-m5/infra/mailbox-retract-stale`)

1. `scripts/fleet_mail.sh`: new `retract --key <k>` subcommand — best-effort, fail-open rename of
   every live broadcast matching `key:` to `.retracted-<ts>` (same self-cleaning pattern
   `mailbox_inject.py` already uses).
2. `scripts/queue_unstick.py`: each tick now also checks `seen_dirty` (state file) against the
   PRs `fetch_open_prs()` returned this tick — any number in state that is either ABSENT (merged/
   closed) or present-but-not-DIRTY anymore gets retracted via `fleet_mail.sh <host> retract` and
   dropped from state. Sender-side retraction is best-effort: a failed retract still drops the PR
   from state (the shortened TTL below bounds the worst case) rather than retrying forever.
3. `DIRTY_SIGNAL_TTL_HOURS` default lowered from the fleet-wide 48h default to 12h for
   `queue_unstick` pages specifically (`--ttl 12` on the `fleet_mail.sh` call) — an "act now, this
   PR is stuck" page has no value 12h later even absent an explicit retraction.
4. `scripts/queue_stall_notify.py`'s broadcast (`send_notification`) gets the same `--ttl 12` —
   not retraction (0 `queue_stall:*` broadcasts existed in this sample; that surface is unmeasured,
   left for a future pass per CLAUDE.md §"cura ciò che il diff introduce, manda a spec ciò che
   eredita" rather than speculatively extended here).

## Decision rule applied

Team-lead's threshold: ship the fix only if ≥50% of sampled broadcasts were stale. Measured 97% —
well above threshold.

## Adversarial review

codex-gpt-5.6-sol reviewed the cure this audit's finding drove (`scripts/queue_unstick.py`'s
`resolved_dirty_prs()`, commits 5b22365c3a + 6369c1b3d7) across two rounds — full detail in
`evidence/2026-09/agent-air-m5-infra-mailbox-retract-stale-035ce205/council-journal.jsonl`.

- **Round 1 (FAIL, CONFIRMED):** `resolved_dirty_prs()` compared `merge_state_status != "DIRTY"`,
  mis-classifying GitHub's transient `UNKNOWN` mergeStateStatus as resolved-and-retractable — a
  genuinely-still-DIRTY PR can read `UNKNOWN` for tens of seconds right after `main` moves, per
  this same file's own documented rewarm logic. This audit's own 97% headline figure includes 5
  OPEN-but-non-DIRTY PRs in the stale bucket; excluding the ones that could plausibly have been a
  transient `UNKNOWN` at sample time still leaves the floor at 82% (28/34), unaffected as a ship
  decision but the finding was real and fixed on the branch, not spec'd away.
- **Round 2 (PASS, on the fixed head):** re-reviewed the whole diff fresh — confirmed `UNKNOWN`
  and `None` both now `continue` (never resolved); only an absent PR (merged/closed) or a present
  PR with a definite non-DIRTY, non-UNKNOWN status resolves. Verified both new tests (guilt:
  `UNKNOWN` must not resolve; innocence: `CLEAN` and absent-PR still resolve) are non-vacuous. No
  new defect introduced by the fix. Zero objections survived against this audit's own numbers.

tp1-qwen3.8-max also reviewed round 1 (PASS with non-blocking findings) but did not catch the
`UNKNOWN` case codex found in the same round — recorded honestly in the council journal rather
than reconciled.
