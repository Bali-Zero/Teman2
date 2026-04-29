# 99b — STATUS: W0-A interrupted by branch hijack from parallel session (2026-04-29 22:30 WITA)

**Severity**: HIGH — analogous to W0-B 5-trigger abort policy. Awaiting Zero ratification before proceeding.
**Time of detection**: 2026-04-29 ~22:31 WITA (Pro)
**Detector**: discrepancy between `git status` (showing only 1 untracked file) and disk reality (W0.1 files completely gone)

---

## 1. What happened

I was 75% through W0-A — Genoma + validator + tests COMPLETE and validating clean,
bridge_state_reader.py + tests written, mid-RED phase before GREEN — when at
**22:30:03 WITA** another process forcibly switched my branch state out from
under me.

### Reflog evidence

```
06db2cf14 HEAD@{2026-04-29 22:30:06}: checkout: moving from main to nbe/resend-fallback-team-templates
06db2cf14 HEAD@{2026-04-29 22:30:06}: pull origin main: Fast-forward
d1996fba7 HEAD@{2026-04-29 22:30:03}: checkout: moving from feature/innervation-2026-04-29 to main
18b3c3dd9 HEAD@{2026-04-29 22:10:18}: commit: docs(innervation): 99_handoff — stop after FASE 1+2  ← my last commit
```

Sequence:
1. ~22:25-22:30: I was actively writing W0-A files (genome.yaml, validate_genome.py, tests, bridge_state_reader, etc.).
2. **22:30:03**: A separate process executed `git checkout main` from my branch.
   This auto-stashed my tracked-file edits as `stash@{0}: innervation-wip-pre-NBE`.
   Untracked files (the new `.py` files I'd just written) were NOT in the stash —
   they were left in the working tree as orphans.
3. **22:30:06**: That process pulled origin/main (fast-forward to `06db2cf14`)
   and checked out `nbe/resend-fallback-team-templates` (the NBE = Notebook Email
   work mentioned in the WIP stash label).
4. The checkout to a different branch deleted my untracked `.py` files because
   they were not tracked by git, so checkout's "remove untracked files that
   conflict with target branch" semantics dropped them silently.

### What was lost (and where it is now)

| Asset | Status |
|---|---|
| `apps/organism/organism/genome.yaml` (153 lines, signed checksum) | ✅ in `stash@{0}` (`innervation-wip-pre-NBE`) |
| `apps/organism/README.md` Genoma section (+25 lines) | ✅ in `stash@{0}` |
| `.pre-commit-config.yaml` `validate-genome` hook (+12 lines) | ✅ in `stash@{0}` |
| `apps/organism/organism/tools/__init__.py` (empty) | regenerable in 5s |
| `apps/organism/organism/tools/validate_genome.py` (9107 bytes, 10/10 tests passing) | ⚠️ ONLY in `.git/objects/85/bb03df76d9120d53b9f4b969ea90680303fc13` (dangling blob) — **recovered to `/tmp/innervation-recovery-20260429_223214/validate_genome.py`** |
| `apps/organism/tests/tools/__init__.py` (empty) | regenerable in 5s |
| `apps/organism/tests/tools/test_validate_genome.py` (6420 bytes) | ⚠️ ONLY in dangling blob `3c/68b5586a06748add2eb4000e202a8ea7d0471f` — **recovered** |
| `apps/cell/cell/sensors/bridge_state_reader.py` (4695 bytes) | ⚠️ ONLY in dangling blob `ee/25ca6fc652b4ff8dd66f5c4af34acf8cd18dea` — **recovered** |
| `apps/cell/tests/test_bridge_state_reader.py` (6510 bytes) | ⚠️ ONLY in dangling blob `fc/49e78b99b56445561f24b527cab84cc7edf363` — **recovered** |

Total recoverable: **all of W0.1 (3 files, 10 tests passing) + all of W0.3 (2 files, RED phase complete)**. Zero loss after recovery.

Active recovery dir: `/tmp/innervation-recovery-20260429_223214/`. Everything also captured as `innervation-wip-pre-NBE.patch` in the same dir as belt-and-suspenders.

---

## 2. Pattern match — this is the §1.2 cicatrice from the handoff repeating

Handoff §1.2 explicitly named this risk:

> **2. File-loss cicatrice 21:42** (vedi `02_dispatch_resilience_log.md` § 6):
> 17KB di lavoro untracked persi durante auto-pull `nuz-sync` watchdog,
> recuperati da context. Aggiungere LaunchAgent deploy a stesso turno =
> accumulo rischio.

This is the **same root cause exactly one hour later** — `nuz-sync` (or another
sibling automation) doing `git stash && git pull` on a different branch checkout.
The 22:30 timestamp is consistent with a 5-min cron tick, not a manual action.

Cicatrice §[STRUCTURAL] candidate: "untracked files in working tree are silently
lost when sibling automation switches branches via checkout". Mitigation needs
to be at the automation layer (don't checkout-different-branch with untracked
files present) — NOT something I can fix from a Claude Code session.

---

## 3. Threshold trigger — analogous to W0-B abort policy

Zero defined the W0-B 5-trigger abort policy minutes ago for plist deploy.
The analogous trigger fired here for W0-A:

> Branch state diverged: untracked changes from previous attempts OR `git log`
> shows commits beyond `00ccfd0ad` not from FASE 3 → STOP, merge conflicts
> likely, escalate.

Reflog shows HEAD moved off the innervation branch without my action. This
matches the pattern. Per skill `executing-plans` rule "STOP and ask for help
when blocker: missing dependency, instruction unclear, or verification fails
repeatedly", I'm stopping.

---

## 4. State now (22:32 WITA)

- Branch: back on `feature/innervation-2026-04-29` (manually `git checkout`'d).
- HEAD: `18b3c3dd9` (the FASE 2 handoff commit) — unchanged from start of session.
- Working tree: CLEAN. No FASE 3 file present. (W0-A reset to zero by checkout.)
- Stashes (from oldest to newest):
  - `stash@{0}`: `innervation-wip-pre-NBE` — auto-stashed by NBE session at 22:30:03 (153-line genome.yaml + README + .pre-commit hook)
  - `stash@{1}`: `innervation-fase3-preflight-2026-04-29` — my own pre-flight stash (DOCSYNC drift + hr/sp1 + send_email_plan)
  - `stash@{2}`: `feature-innervation-temp-2026-04-29` — pre-existing stash from 21:38
  - `stash@{3..6}`: pre-existing `nuz-sync auto-stash` from earlier today
- Recovery: `/tmp/innervation-recovery-20260429_223214/` has all 4 lost `.py` files + the WIP patch. Mode 0644, mine.
- Quota: still account 1 weekly 59% (no API calls happened during the lost-work window — was all local).

---

## 5. Question for Zero — 3 paths

**Path A — Resume W0-A in this session (defensive)**
1. `git stash pop stash@{0}` to restore genome.yaml + README + pre-commit hook.
2. `cp /tmp/innervation-recovery-20260429_223214/{validate_genome.py,test_validate_genome.py,bridge_state_reader.py,test_bridge_state_reader.py}` back into their proper repo paths + recreate `__init__.py` empty files.
3. `git add -A` IMMEDIATELY (no Write-tool-without-add anymore — this is the cicatrice 21:42 + 22:30 lesson hardened).
4. Verify 10 + (8 RED) tests still in expected state.
5. Continue W0.3 GREEN → W0.2 → W0.6 → W0-B script → W0.7 commit + push + PR.
6. **Pre-condition**: identify the parallel session (NBE) and ensure it has
   either finished or won't re-trigger another branch switch. If the NBE
   session is still running and will trigger `nuz-sync` again, Path A is unsafe.

**Path B — Pause now, ratify recovery, restart W0-A in fresh session later**
1. Apply the recovery from the safe location into a properly-committed branch state RIGHT NOW (so the work is not at risk if `/tmp` is wiped or another branch hijack fires).
2. Open WIP commit on `feature/innervation-2026-04-29`: `wip(innervation/W0-A): partial recovery from 22:30 branch hijack — files restored, no logic verified`.
3. Push to origin (defensive backup against further loss).
4. Stop session here. Document this incident as cicatrice STRUCTURAL.
5. New session resumes from the WIP commit, completes W0.3 GREEN + W0.2 + W0.6 + script + final clean commit + PR.

**Path C — Just write the W0-A status file (this one), commit it, push, and stop.**
The deliverable of this session becomes the incident report itself, not the W0-A code. The recovery files in `/tmp` get attached to the next session via this status doc. **This is the most conservative — matches §1 of the handoff philosophy "audit trail è il deliverable"**.

---

## 6. My default recommendation: **Path B**

Reasons:
- Path A's pre-condition (no further branch hijack) is **not verifiable from
  this session** — the NBE process is independent of me.
- Path C abandons concrete progress (10 tests passing, 4 file restored, RED
  phase complete on bridge reader). That's a win we shouldn't throw away.
- Path B locks the win into a real commit (resilient to `/tmp` wipe + another
  branch hijack) without claiming the work is "done". Then a fresh session
  picks up at the well-defined waypoint of "WIP commit, partial test coverage,
  GREEN phase pending for bridge reader".

**Risk of Path B if NBE session fires again during my recovery**: same as
during my W0.1 work — if it happens DURING `git stash pop` or `git add`, the
WIP commit may not land. Mitigations:
1. Do recovery as a single `git checkout-stash + cp + git add + git commit`
   atomic batch (no Write tool calls in between) so the window is <5s.
2. `git push -u origin feature/innervation-2026-04-29` immediately after commit
   so the work is also on remote.

---

## 7. Telegram alert (queued, NOT sent yet — awaiting Zero ratification)

```
🟡 W0-A INTERRUPTED — branch hijack by parallel NBE session 22:30 WITA
Detector: HEAD reflog moved feature/innervation-2026-04-29 → main → nbe/resend-fallback-team-templates without my action
Lost files (recoverable): validate_genome.py, test_validate_genome.py, bridge_state_reader.py, test_bridge_state_reader.py
Recovery: /tmp/innervation-recovery-20260429_223214/ has all 4 files + WIP patch
Cicatrice match: §1.2 of 99_handoff (file-loss 21:42) repeated 1h later
Default recommendation: Path B (commit recovery as WIP, push, stop session, fresh resume)
Awaiting Zero ratification before any further action
```

I am NOT sending this. I'm putting it here so Zero sees what would be sent if
ratified.

---

## 8. What I did NOT do (transparency)

- I did NOT `git stash pop`. Stash@{0} is intact.
- I did NOT recreate any of the lost files in their repo paths. Recovery is in `/tmp` only.
- I did NOT delete any reflog entries or stash entries.
- I did NOT push anything to origin.
- I did NOT touch any LaunchAgent files (W0-B is correctly still pending).
- I did NOT modify `genome.yaml`, `validate_genome.py`, `bridge_state_reader.py`, or any test in this recovery investigation. The `/tmp` copies are byte-identical to what passed `pytest 10/10`.

The only state-changing actions were:
1. `git checkout feature/innervation-2026-04-29` (to return to the branch I should be on).
2. `cp` of dangling-blob content to `/tmp` (read-only operation on the .git store).
3. Writing this status doc.
