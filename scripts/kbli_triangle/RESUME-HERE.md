# KBLI editorial regen — RESUME HERE

> **TRIGGER WORD: `KBLIREGEN`** — when Zero types it at session start, this file is the resume
> command. Count drafts, probe Codex quota on the Pro, and resume (steps in "HOW TO RESUME" below).

## STATUS 2026-07-12 — Pro REBOOTED overnight, job rebuilt at DURABLE path

- The Pro rebooted ~23:16-23:31 on 07-11: `/tmp/kbli-regen` wiped (macOS clears /tmp on
  boot), writer killed, ~5-7 drafts in the rsync gap lost (resumable writer regenerates).
  The reconcile loop ALSO exited on a false "writer DEAD" verdict — it read ssh-timeout
  (Tailscale flap) as death (family #8). Both cured 2026-07-12:
  - Job dir rebuilt at **`~/kbli-regen`** on the Pro (HOME = survives reboot), seeded from
    the origin branch (817 drafts + fixed writer). Writer relaunched 13:50 (742 to write).
  - `reconcile_loop.sh` now distinguishes ssh rc=255 (flap → keep looping) from pgrep
    rc=1 (real not-running), rsync `--timeout=60`, path via `PRO_JOB_DIR` (default
    `kbli-regen`, HOME-relative).
- M5→Pro connectivity is INTERMITTENT (Tailscale relay "sin", mDNS dead) — every remote
  step needs retry; the loop tolerates it now.

## STATUS 2026-07-11 — RESUMED on GPT-5.6 Terra (writer live on the Pro)

- **Engine switched to `gpt-5.6-terra`** (Zero's directive; batch tier, ~2x cheaper than 5.5).
  Codex CLI on the Pro upgraded 0.142.5 → **0.144.1** (Terra needs ≥0.144.0; npm-managed).
- `editorial_writer.py` grew a `--model` flag (commit f2fda65974); empty = CLI default.
- **Pro writer relaunched detached** 2026-07-11 20:56 (Pro clock):
  `cd /tmp/kbli-regen && nohup python3 scripts/kbli_triangle/editorial_writer.py --workers 2 --model gpt-5.6-terra`
  — log `/tmp/kbli-regen/scripts/kbli_triangle/_terrarun.out`. Full-size Terra probe passed
  (400-word call, ~15k tokens); initial 2-worker collision produced a few 429 backoffs, expected
  to self-heal (single calls pass while workers sleep). If the log shows ONLY quota backoffs and
  zero new drafts after ~30 min → kill and relaunch `--workers 1`.
- **M5 reconcile loop is now a durable script**: `scripts/kbli_triangle/reconcile_loop.sh`
  (rsync-pull Pro→worktree every 15 min, audit = `kbli_apply_editorials.py --dry-run` G0-G6,
  checkpoint commit). Runs detached on M5, log `scripts/kbli_triangle/_reconcile_loop.log`.
  It replaces the transcript-only audit command of 2026-07-10 (W81: the grader is on disk now).

**Mandate**: `/goal` — a magazine-grade editorial for every one of the 1559 KBLI 2025 codes
(`intel_2026.editorial`), then apply → website + native app aligned. Branch
`agent/air-m5/mouth/kbli-editorials`, worktree `.worktrees/mouth-kbli-monumental`.

## WHERE WE ARE

- **688 / 1559 drafts done** (44%), all committed on M5 up to **0e9a4de0f0**, audit CLEAN
  (0 shape / 0 L10 / 0 L3 / 0 fabrications). Drafts live in
  `scripts/kbli_triangle/editorial_drafts/<code>.json` (TRACKED, prettier-ignored).
- **Writer**: `scripts/kbli_triangle/editorial_writer.py` (Codex-driven, WRITER v2 prompt,
  gate-aware retry, resumable — skips existing drafts). PAUSED.

## WHY PAUSED — all writer engines exhausted (time-based recovery only)

- **Codex**: ChatGPT Pro quota **genuinely exhausted** (account-wide, same on M5 & Pro).
  Fails even at `--workers 1` with full editorial prompts (a tiny 40-word probe still
  passes — misleading). Recovers on the rolling ChatGPT Pro window (hours).
- **Claude**: weekly-cap until **Fri 11 Jul 18:00 PDT**.
- **Gemini agy**: auth broken on M5 (`-p` won't bind the prompt, v1.1.0).
- **M5 network**: degraded — `chatgpt.com` hard-refused from M5, GitHub 15s, mDNS/`pro-lan`
  dead. The **Pro** reaches Codex fine (that's why we ran there). See
  [[discovery_kbli_regen_moved_to_pro_m5_network_dead_2026_07_10]].

## HOW TO RESUME (when Codex quota recovers OR Claude cap resets)

Preferred = **run on the Pro** (its network to Codex is healthy; M5's is not):

```bash
# 1. sync M5's latest drafts to the Pro standalone job (so it skips done ones)
rsync -az <wt>/scripts/kbli_triangle/editorial_drafts/ pro:/tmp/kbli-regen/scripts/kbli_triangle/editorial_drafts/
# 2. probe quota with a FULL-SIZE call (not a 1-token PONG):
ssh pro 'export PATH=$HOME/.local/bin:$PATH; codex exec --sandbox read-only --skip-git-repo-check "Write a 400-word paragraph about rice."'
#    -> if it returns text (not "quota — backoff"), quota is back.
# 3. launch Pro writer detached, 1 worker (safer under rate limits):
ssh pro 'export PATH=$HOME/.local/bin:$PATH; cd /tmp/kbli-regen && nohup python3 scripts/kbli_triangle/editorial_writer.py --workers 1 > scripts/kbli_triangle/_prorun.out 2>&1 &'
# 4. each tick: rsync Pro drafts back to M5, audit, commit (the reconcile loop).
```

Reconcile-pull (M5←Pro) works fine even when M5→Pro push crawls.

Audit command (grader, run on M5 after each pull) is embedded in the transcript; it checks
G2 shape + lint L10/L3 + a fabrication scan that ALLOWS any `%` present in `l4_bali.reason`
(l4_bali caps are REAL data — see commit 1d5284891e, do NOT re-flag them).

## STILL TODO (in order)

1. Finish regen: running on Terra since 2026-07-11 21:04 (803+ by 23:00, ~1 draft/min).
2. **bali-cap codes**: ✅ DONE for the 4 that had drafts — 01287/02102/41011 regenerated clean
   2026-07-11 (Terra, prompt 3b already in writer; audit: pct stated, no meta-refs, no verbatim),
   02402 was already clean. The other 6 (52292 59131 69201 86102 86201 86202) get drafts from
   the MAIN run — re-run the bali-cap audit on them when they land (audit snippet: check
   l4_bali.reason % appears in body, no 'reason field'/'l4_bali' strings, no verbatim chunks).
3. **Final independent grading pass** on the full 1559 (Gemini if auth fixed, or Claude at
   cap-reset) — generator≠grader.
4. **Apply**: `python3 scripts/kbli_apply_editorials.py --drafts-dir scripts/kbli_triangle/editorial_drafts`
   → writes `intel_2026.editorial` into the canonical dataset + bumps
   `apps/mouth/data/kbli-dataset-version.json` + runs `sync_kbli_dataset.sh`.
5. **LOOP-3 ship**: lint L11 (post-apply de-boilerplate) → build → PR → prove-live
   `balizero.com/kbli/<code>` → Qdrant `kbli_2025_final_oss` re-ingest (on Pro) → native app
   refresh → team announce. `NEXT_PUBLIC_KBLI_META_EN=1` flip is operator[business], post-GSC.
6. **Push branch to origin** — PARTIALLY unblocked 2026-07-11: branch transferred to the Pro
   repo via git bundle (scp /tmp/kbli.bundle → `git fetch`), so it survives M5 teardown on TWO
   machines now. GitHub push from the Pro is BLOCKED by the husky pre-push pytest gate (full
   backend suite runs there because local PG is provisioned; failures are pre-existing, not
   from this branch — the standing 07-08 blocker). Diagnosis run: `/tmp/pytest-prepush.log` on
   the Pro. NEVER `--no-verify`, never point PRE_PUSH_TEST_DB at a fake db. Fix the red tests
   (or land the fix that unblocks the gate), then `git push origin` from the Pro.
