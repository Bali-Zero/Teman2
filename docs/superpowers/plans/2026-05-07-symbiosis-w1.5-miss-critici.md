# Symbiosis W1.5 — Implementation plan

**Date**: 2026-05-07
**Branch**: `feat/symbiosis-W1.5-organi-2026-05-07`
**Design ref**: `docs/superpowers/specs/2026-05-07-symbiosis-w1.5-miss-critici-design.md`
**Issue**: #490

---

## Step-by-step

### Step 1 — Create design + plan (commit 1)

- Write `docs/superpowers/specs/2026-05-07-symbiosis-w1.5-miss-critici-design.md`
- Write this plan
- Commit message: `docs(symbiosis): W1.5 MISS CRITICI design + plan`
- Push within 30s of commit

**Verification**: `git log --oneline -1` shows the commit; `git push` exit 0.

### Step 2 — TDD: red test for the 9 entries

Add `TestW1_5MissCritici` class to
`apps/organism/tests/tools/test_validate_genome.py` with 4 test methods
(one per organ family):

- `test_w1_5_nlm_bridge_enrolled` — checks `nlm.bridge` exists with
  daemon+critical+http bridge to :18790/health
- `test_w1_5_cell_observatory_triplet_enrolled` — checks 3 cell.observatory
  ids with correct types + state_file bridge on the daemon
- `test_w1_5_post_publish_poller_enrolled` — checks
  `pro.post_publish_poller` exists with cron+error+launchctl recovery
- `test_w1_5_sota_m13_quartet_enrolled` — checks all 4 sota.m13_*
  exist with correct expected_hb_seconds matching schedule + dependency
  on wr2.supervisor

Run the suite — expect 4 reds.

### Step 3 — Add the 9 genome.yaml entries (green)

Append the 9 entries after `pro.secrets_sync_mini` (line 1201) per the
design doc §5.1.

### Step 4 — Update checksum, re-apply header preamble

```bash
cd apps/organism
python -m organism.tools.validate_genome --update-checksum
```

`yaml.safe_dump` strips the header comments (lines 1–43). Re-apply by
hand via Edit tool — preserve exact header content from the W1 file.

### Step 5 — Validate + run all tests

```bash
cd apps/organism
python -m organism.tools.validate_genome organism/genome.yaml
python -m pytest tests/tools/test_validate_genome.py -v
```

Expected: validator PASS + all tests green (existing 18 + 4 new = 22+).

### Step 6 — Commit + push

```bash
git add apps/organism/organism/genome.yaml apps/organism/tests/tools/test_validate_genome.py
git commit -m "feat(organism): enroll Wave 1.5 MISS CRITICI organi (78→87) — Closes #490"
git push origin feat/symbiosis-W1.5-organi-2026-05-07
```

### Step 7 — Open PR with auto-merge

```bash
gh pr create --title "feat(organism): enroll Wave 1.5 MISS CRITICI organi (78→87)" \
  --body "<from design §10>" \
  --base main --head feat/symbiosis-W1.5-organi-2026-05-07
gh pr merge --auto --squash
```

### Step 8 — Tri-LLM cross-check on the design

Run in parallel after PR is open (cap 2 LLMs minimum):

- Codex sandbox: `codex exec --sandbox read-only "review docs/superpowers/specs/2026-05-07-symbiosis-w1.5-miss-critici-design.md for design gaps"`
- Gemini: `gemini -m gemini-3.1-pro-preview -p "review the design at <path> for accuracy"`
- DeepSeek: only if Codex or Gemini fails with rate-limit

If 2/3 converge → mark `tri-llm: 2/3 PASS` in the PR body and orchestrator return.

## Risks

1. **Checksum drift after `--update-checksum`** — header preamble stripped.
   Mitigation: explicitly `Edit` the header back after the checksum
   recompute, then `validate_genome` again to confirm checksum still
   matches (header lines don't enter the canonical JSON hashing).

2. **`sota.m13_collect` has no schedule** — RunAtLoad-only. Treating it
   as a daily cron with `expected_hb_seconds=90000` matches W1 conventions
   for orphan-schedule plists. Risk: spurious heartbeat-stale alerts if
   the operator never re-triggers it. Acceptable per design D3.

3. **`cell.observatory_selfcheck` was at exit code 1 at smoke time** —
   pre-existing failure mode. Enrollment doesn't change that; the
   Supervisor will surface the heartbeat-stale state as `warning` per
   the severity setting. Out of scope to fix here.

4. **Branch hijack mid-session** — same risk as W1. Mitigation: 30-min
   WIP commit cadence, `git branch --show-current` check before each
   Edit/Write, atomic compound `git add && commit && push <30s`.

## Out of scope

See design doc §11.
