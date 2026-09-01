---
date: 2026-08-30
domain: operations
plan: beyond-sota-craft-wave
type: inventory-and-battle-plan
status: READY — wave 2 launches on Zero's GO, after the rulings batch in §6
supersedes: nothing — extends 00-BATTLE-PLAN.md (whose §2 layout for squads C/A is replaced by §5 here)
---

# Craft wave — inventory of what exists (28–30/8) and the wave-2 battle plan

**Why this file exists.** Zero, 2026-08-30: _"questi interventi avrebbero dovuto cambiare l'assetto
globale del coding nel sistema"_ — then: _"fai una ricerca di tutto ciò che è stato fatto … per non
perdere pezzi validi e già fatti … capire cosa manca e come organizzarlo in sessioni potenti,
multi-LLM, anti-spreco, da spalmare sulle 3 macchine."_ This is that research and that plan.

Every number below was measured on 2026-08-30 ~23:00–23:40 WITA against `origin/main`
(`d586f5259` → `873c286cd`), the live Mini/Pro/M5 filesystems over SSH, and the GitHub API — not
recalled from memory. Where a claim is a seat's verdict rather than a measurement, it says so.

**The verdict the audit reached, in one line:** of the 39 first-PRs the wave was meant to land,
**19 landed, 4 bite today, 14 landed inert, 20 never started** — the way a session writes code
tonight is the same as on 28/8. Wave 2 is designed so that cannot repeat: its unit of delivery is
a _bite observation_, not a merged PR.

---

## 1. What exists — nothing is lost, and this is where each piece lives

### 1.1 Research corpus (all on `origin/main` unless marked)

| Corpus                                                                                                                                                                                                                                                         | Where                                                          | Size                                  | State                                                                                                              |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **13 craft-lane reports** (Fable 5 max; lane 9 was Gemini 3.1 Pro — INDEX §I provenance correction)                                                                                                                                                            | `research/operations/2026-08-28-beyond-sota-<lane>.md`         | ~642 KB, ≈85,044 words                | complete, gated, adversarially reviewed (#5177)                                                                    |
| **Panel INDEX** — the distilled reasoning: §A ahead-list · §B meta-disease table (13 beliefs × falsifying number) · §C cure-class (5 shapes) · §D top-10 moves · §E needs-ruling · §F first wave · §G numbers · §H 39 first-PR rows · §I cross-family verdicts | `research/operations/2026-08-28-beyond-sota-panel-INDEX.md`    | 57 KB                                 | **the single most valuable file — read §B/§C/§D/§I before any wave-2 build**                                       |
| Panel PROTOCOL (method, doors, discarded contaminated run)                                                                                                                                                                                                     | `…-beyond-sota-panel-PROTOCOL.md`                              | —                                     | complete                                                                                                           |
| **Cross-family blind replica** (codex-sol-ultra 13, kimi-k3 13, agy 13, tp1-deepseek-v4-pro 12, tp1-qwen3.8-max 8)                                                                                                                                             | `research/operations/2026-08-28-beyond-sota-xfamily/`          | 59 files, 243,408 words               | **59/65** — missing: qwen lanes 7, 10, 11, 12, 13; deepseek lane 13 (TP1 weekly quota; PENDING-ARMS row via #5291) |
| **16 anatomy reports + `00-SYNTHESIS.md`** (B1-B9 product organs, F1-F4 frontend, X1-X3 engineering process)                                                                                                                                                   | `research/operations/2026-08-28-beyond-sota-anatomy-16-lanes/` | 17 files, ≈66,000 words, ~270 sources | published by #5308 with a "what it got wrong" front                                                                |
| Anatomy program mandate (`00-MANDATE-AND-PARTITION.md`, self-labelled internal)                                                                                                                                                                                | **M5 only**: `~/Desktop/BEYOND-SOTA-2026-08-28/` (7.9 KB)      | —                                     | deliberately withheld from the public repo; `00-SYNTHESIS.md:178` still cites it as readable — cosmetic            |
| Per-lane ranked recommendations R1–R7 (beyond the 3 first-PRs)                                                                                                                                                                                                 | §5 of each craft report                                        | 13 × 6–7 items                        | **untouched by wave 1** except where a first-PR overlapped — see §3.3                                              |

### 1.2 Spec corpus

| Spec                                                                                  | Where                                                                                                                                                                                                                                                                 | State                                                                    |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Battle plan + L00 + L01–L13 SPEC-FINAL (3 first-PRs each, guilt+innocence acceptance) | `docs/plans/2026-08-29-beyond-sota-craft-wave/` (16 files, #5193)                                                                                                                                                                                                     | on main; spec-backs merged into L07/L11 by #5242 #5249 #5250 #5254 #5264 |
| Specs the wave produced as by-products                                                | `docs/specs/delivery-guarantee-gate-v1.md`, `docs/specs/pending-arms-owner-tag-v1.md`, `docs/specs/shell-route-block-v1.md`, `research/operations/specs/L06-queue-field-verdict-successor.md`, `research/operations/specs/W-restore-drill-wiring-harness-evasions.md` | adjudicated, **not armed** (each says so itself)                         |
| Design study loop (product side, L11-adjacent)                                        | `research/design/2026-08-28-{case-code,delegate-flow,sponsor-i18n}-design.md` + 4-seat mockup panels; Merah Putih contest result 30/8                                                                                                                                 | done; feeds VOA, not the craft lanes                                     |

### 1.3 Code that landed (20 of the 40 first-PR slots) — with its in-force status

| Lane-PR                                                                   | PR                      | In force?                  | The observation that proves it (made 30/8)                                                                                               |
| ------------------------------------------------------------------------- | ----------------------- | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| L07-PR1 smoke → blocking                                                  | #5246                   | **BITES**                  | `Visa Oracle fullstack smoke` is required context #12 (`app_id 15368`); its smoke step ran and passed on docs-only #5313                 |
| L06-PR1 (reshaped) required-context guard                                 | #5214                   | **BITES**                  | executed at `immune-enforcement.yml:979` inside required job `antidotes`, no `continue-on-error`                                         |
| L07-PR2 VOA journey probe                                                 | #5215 #5257 #5304       | **BITES** (receptor)       | Mini `com.nuzantara.voa-probe` runs=98, heartbeat 22:54 WITA, `verdict=dark`; CI executor `voa-probe-tests.yml` runs but is NOT required |
| L11-PR1 journey sentinels                                                 | #5225                   | **BITES** (receptor)       | Mini `com.nuzantara.journey-sentinel` hourly, log 22:43 WITA, real finding (`/prime` Maps key, #5252)                                    |
| L01-PR3 appetite rule 14                                                  | #5229                   | armed, 0 catches           | lint on `origin/main` FAILS a pack exceeding a declared ceiling without ack; only 3/77 briefs declare `appetite:`                        |
| L00 R9 staging                                                            | #5190                   | live, teeth from 2/9       | #5177 run: `stage_council_journal: staged … journal.jsonl`; R9 = NOTICE until 2026-09-02, FAIL after (proved with the lint, both dates)  |
| L01-PR1/PR2                                                               | #5208 #5216             | inert by design            | NOTICE-only rules                                                                                                                        |
| L03-PR3 council yield · L05-PR2 correction tax                            | #5245 #5247             | inert                      | nothing schedules them (their own rows #5248, #5313)                                                                                     |
| L04-PR3 size taxonomy · L06-PR3 collision check · L11-PR2 tokens+contrast | #5255 #5262 #5240+#5259 | advisory                   | schedule-only / verdict advisory / `continue-on-error` ×8 with 7 known escapes (#5249)                                                   |
| L05-PR1 hermetic runner · L05-PR3 gate docstring · L06-PR2 `mq state`     | #5226 #5224 #5217       | non-required / no consumer | `mq_state_verdict` referenced only by `mq.sh`                                                                                            |
| L07-PR3 dead-man                                                          | #5258                   | ticking, toothless         | runs=267, `real_fire_gate=disabled` — awaits #5253 NR-2                                                                                  |
| L09-PR1 seat-state · L09-PR3 effort                                       | #5290 #5292             | inert                      | pre-check resolves UNKNOWN (Pro `~/.claude/seat-quota.json` dated 25/8); effort "logged-only pending ruling"                             |
| L12-PR3 restore verifier                                                  | #5260 #5261             | not yet exercised          | `restore-drill.yml` runs monthly on the 1st; last run 2026-08-01                                                                         |

### 1.4 Code that was BUILT and NOT landed — the pieces at real risk of loss

| Squad          | What exists                                                                                                                                                                                                                                                                                                                                                                | Where                                                                                                                            | Risk                                                                                                        |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **D (data)**   | L12-PR1 build: WIP commit `655bcd5a6` (14 files, +1,049/−120: `test_jsonb_codec_parity.py`, `lint_test_pool_codec_parity.py` + tests, 4 caller sites, 2 bare pools converted) **plus uncommitted** +800/−51 in the same 4 files (gate round 2: shrink-only baseline + real-column arming) **plus untracked** `infra/test-pool-parity/baseline.json` and the evidence brief | Pro `.worktrees/craft-d-data-migrations`, branch `agent/nuzantara/craft-d/data-migrations` — **never pushed, no PR ever opened** | one `git worktree remove` away from gone; the ledger says gate round 2 was in flight when the session ended |
| **D**          | grounding worth keeping: the three codec registrations, the 4 double-encoding call sites, `298` is the max migration (spec's `297`/`298` numbers are stale → PR-2 must use **299**), `_schema_versions` checksum sentinel, W130 ownership caveat                                                                                                                           | `SQUAD-LEDGER.md` in that worktree (11 KB, untracked)                                                                            | local file only                                                                                             |
| **F (fleet)**  | held commit `c246e4405b` "correct a measured-false claim in seat_state.sh" (could not push: #5290 was queued, GH006); worktree dirty=2, ahead=4; HANDOFF-TO-W (CI executor for the three `seat_build` shell suites, ~51 assertions) and 4 owed PENDING-ARMS rows                                                                                                           | Mini branch `craft-f-hold/seat-state-comment-fix`; `.worktrees/craft-f-fleet-security/SQUAD-LEDGER.md` (18 KB, untracked)        | handoff readable on Mini only                                                                               |
| **P (probes)** | 193 KB ledger with the full H1/H2/H3 handoff bodies, the L11-PR3 kill-criterion evidence, dedup-flap analysis; worktrees `craft-p-prod-probes` dirty=3                                                                                                                                                                                                                     | Mini `.worktrees/craft-p-*`                                                                                                      | local only; H1/H2 are landed, H3 advisory by its own artefact                                               |
| **W**          | PR #5218 `ci(queue): a regression guard with zero catches today` — Rule-8 SUSPENDED draft (premise false, not implementation)                                                                                                                                                                                                                                              | open draft                                                                                                                       | keep suspended; successor spec is `research/operations/specs/L06-queue-field-verdict-successor.md`          |

### 1.5 Research about the coding approach that lives on M5 only (not on `origin/main`)

All older than the wave but squarely "in merito"; each exists on exactly one disk.

| File                                                                                                                              | Date | Size   |
| --------------------------------------------------------------------------------------------------------------------------------- | ---- | ------ |
| `research/llm-frontier-reports/` (11 files: GPT-5.6, Qwen 3.8, DeepSeek V4, GLM 5.2/5.3, local MLX/Ollama, comparative synthesis) | 21/8 | 68 KB  |
| `research/operations/2026-08-10-merge-os-definitive-pr-system.md`                                                                 | 10/8 | 33 KB  |
| `research/operations/2026-08-14-research-system-forensic-audit-qwen.md`                                                           | 14/8 | 108 KB |
| `research/operations/audit-ricerca-2026-08-14.md`                                                                                 | 15/8 | 49 KB  |
| `research/operations/2026-08-21-xAI-Grok-family-deep-research.md`                                                                 | 21/8 | 25 KB  |
| `docs/prompts/2026-08-15-olympus-code-master-prompt.md`                                                                           | 15/8 | 31 KB  |
| `docs/mandates/2026-08-15-intake-code-master-mandate.md` (+ `…-answer-key-INTERNAL.md`)                                           | 15/8 | 21 KB  |
| `docs/plans/2026-08-15-visa-oracle-doctrine-factory/` (9 files)                                                                   | 15/8 | 168 KB |

Ruling needed (§6 item 9): publish, keep internal, or archive — but **back them up off M5 today**
regardless (M5 is Zero's workstation, not a server).

### 1.6 Findings ledger produced by the wave

- **67 PENDING-ARMS rows opened 29–30/8**; the file grew 1,505 → 1,713 lines; open rows 598 → 662
  (**net +64**). The wave produced more antibody debt than it retired.
- Issues: **#5251** (P→W handoff: H1 landed by #5246 and then _promoted to required_; H2 landed by
  #5304 as a non-required job; H3 advisory by its own artefact's veto) · **#5252** `/prime` Google Maps
  key expired (`operator[GUI]`) · **#5253** NR-1 probe tenancy (ruled `is_probe` 30/8 per the
  conductor's memory) + NR-2 dead-man real-fire (open).
- Rules that flip NOTICE → FAIL on **2026-09-02** inside the required `Harness floor recompute`:
  R9 council_run, R11 cheap-seat floor, R8/R10 seat rules. On main **46 of 69 Gear-3 packs have no
  `council_run`**; of the wave's own 28 Gear-3 PRs, 6 carry no journal and 1 (#5224) has one seat —
  7/28 would have gone red under Tuesday's rule. `EVIDENCE_ROOT_DEPRECATION_DATE` follows on 5/9.
- Memory notes (Pro/Mini shared dir, copies on M5): `project_beyond_sota_program_16_fable_lanes_2026_08_28`,
  `project_beyond_sota_engineering_craft_panel_13_lanes_and_cross_family_2026_08_29`,
  `project_beyond_sota_craft_wave_specs_and_battle_plan_2026_08_29` (the conductor's full timeline,
  including the smoke promotion under Zero's 30/8 ruling), plus the discoveries on fan-out seat burn,
  blind-replica snapshots, seat doors, harness-floor staging, MAX weekly caps.

---

## 2. Correction to the audit's "unseen" item

The audit reported that `Visa Oracle fullstack smoke` became a required context between 29/8
13:45Z and 30/8 with no record. The record exists — in the conductor's memory note, not on main:
promoted ~12:00 WITA on 30/8 under Zero's ruling, via the modern `checks` form of the
branch-protection API. The successor conductor (comment on #5251 at 08:49Z = 16:49 WITA) did not
know. The defect is therefore **"decided in one session, recorded only in that session's memory"**
— the same shape as the untracked squad ledgers. Wave 2 fixes the shape (§5.1 rule 1), not the
instance.

---

## 3. What is missing — organised by the three levers that actually change how code gets written

"Changing the global coding approach" in this organism means changing exactly three things:
**(1) what every session has in its head at turn 1, (2) what can stop a wrong PR, (3) how sessions
coordinate and learn.** Product lanes (B/F) change organs; only these three change the factory.

### 3.1 Lever 1 — the head (0 of 5 landed)

| Item                                                                                 | Spec    | Bite observation                                                                             |
| ------------------------------------------------------------------------------------ | ------- | -------------------------------------------------------------------------------------------- |
| Read-side attestation + scar cold storage (INDEX top move #1; 774 KB injected today) | L02-PR1 | a fresh headless session's turn-1 attestation line ≤ the ruled budget, on all three machines |
| Repomap hard 20 KB cap                                                               | L02-PR2 | `wc -c ~/.nuzantara-repomap.txt` ≤ 20,480 after the next cron tick, red otherwise            |
| Superscar prune to ≥1.5 KB headroom                                                  | L10-PR3 | `test_superscar_budget.py` green with ≥1,500 free bytes; every displaced W-token resolves    |
| Doctrine citation-integrity lint                                                     | L03-PR2 | red on the `sota-architecture-loop` phantom before the cure, green after                     |
| Canon-block comparator for global `CLAUDE.md` (3 copies, 3 answers)                  | L10-PR2 | synthetic divergent block on one machine → P1 line within one proprioception cycle           |

### 3.2 Lever 2 — the stop (2 of ~12 bite)

| Item                                                                                                                       | Spec / origin                                                                                                                                                                                                                                  | Bite observation                                                                                                                                  |
| -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Required-context batch** — the only surface where "landed" becomes "biting"; operator action, never requested as a batch | jobs already built: `VOA probe organ tests`, `Restore drill wiring tests`, `PR collision check` (corpus half), `Canary self-test + incremental mutation` — **not** `Token contrast tripwire tests` (its own squad vetoed it until #5249 lands) | each job's guilt fixture turns a real PR red and the PR cannot merge                                                                              |
| `lane_check` hook gating the stop boundary                                                                                 | L04-PR1                                                                                                                                                                                                                                        | a failing `.lane-check.json` blocks stop, quoting stderr — on all three machines (hook dir is a HOME-fork → three `operator[control-plane]` rows) |
| Trigger-symmetry lint as specced                                                                                           | L06-PR1                                                                                                                                                                                                                                        | guilt fixture exits 1 in required `antidotes`                                                                                                     |
| CI executor for the three `seat_build` shell suites (F handoff, ~51 assertions)                                            | L09-PR3 residue                                                                                                                                                                                                                                | seeded guilt fixture turns a PR red                                                                                                               |
| CI executor for `lint_test_pool_codec_parity.py` (D handoff, model: `asyncpg-lint.yml`)                                    | L12-PR1 residue                                                                                                                                                                                                                                | a new bare `create_pool` in tests turns a PR red                                                                                                  |
| L12-PR1 codec cure + L12-PR2 provenance/checksum                                                                           | L12                                                                                                                                                                                                                                            | `jsonb_typeof` on 4 real columns red on codec revert; tampered migration turns `schema_audit` red                                                 |
| `with_seat` broker (INDEX top move #3)                                                                                     | L13-PR1                                                                                                                                                                                                                                        | a codex/agy/kimi child's `env` carries exactly its seat credential; planted fake PAT trips the guilt fixture                                      |
| Tailnet drift receptor                                                                                                     | L13-PR2                                                                                                                                                                                                                                        | RED on the 2026-08-11 allow-all fixture, GREEN on `policy.hujson`, BLIND → exit 2                                                                 |
| Immune contracts + schema handshake                                                                                        | L08-PR1                                                                                                                                                                                                                                        | W120 fixture red                                                                                                                                  |
| Arm-or-archive: `council_yield_report.py`, `correction_tax.py`, `pr_size_taxonomy.py`, `mq state`                          | L03-PR3 / L05-PR2 / L04-PR3 / L06-PR2 residues                                                                                                                                                                                                 | a scheduled run with real output — or the file deleted with its row closed                                                                        |
| 2/9 readiness                                                                                                              | L00 residue                                                                                                                                                                                                                                    | a report naming every Gear-3 pack that fails R9/R11/R8/R10 on Tuesday, before Tuesday                                                             |

### 3.3 Lever 3 — coordination and learning (0 of 8 landed)

| Item                                                                                                                                           | Spec                    | Bite observation                                                              |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ----------------------------------------------------------------------------- |
| PENDING-ARMS overdue ratchet + reporter self-test                                                                                              | L10-PR1                 | ratchet red on synthetic +1 overdue in CI                                     |
| `fleet_burst` account-sharded fan-out (now unblocked: `seat_state.sh` is on main)                                                              | L09-PR2                 | dry-run asserts one seat per lane, ≤3 spawns, sterile config                  |
| Decision registry v0                                                                                                                           | L03-PR1                 | reused number → red; every `evidence:` path resolves                          |
| Lane outcome telemetry (correction chain, time-to-green, builder attribution)                                                                  | L04-PR2                 | reproduces the 27-of-200 correction count ±3                                  |
| Sentry repoint at the org with traffic; `.bak` purge + guard                                                                                   | L08-PR2/PR3             | nonzero accepted-count; `lint_home_fork.py --discover` covers `.bak`          |
| `operator[secret]` ager + weekly digest                                                                                                        | L13-PR3 (after L10-PR1) | digest lists ≥3 open rotation rows by fingerprint+age                         |
| 6 deferred cross-family replica runs + INDEX §I update                                                                                         | #5291 row               | 65/65 files on disk, §I matrix without "deferred" cells                       |
| Per-lane R1–R7 recommendations never touched (e.g. L05 grader scorecards, L08 burn-rate receptors, L02 JIT scar retrieval, L06 queue batching) | §5 of each report       | out of wave-2 scope by design — they are the wave-3 input, ranked in INDEX §D |

### 3.4 Rulings still pending (consolidated; defaults in §6)

Context budget number · effort default for floor-2 diffs · `appetite` exceeded semantics ·
dead-man real fire (#5253 NR-2) · tailnet ACL apply + ttyd (`operator[GUI]`, X2 P0) · `/prime` Maps
key (#5252) · required-context batch · 2/9 enforcement policy · M5-only research disposition ·
Pro Keychain slots 2–5 re-login (see §4.3) · Sentry quota · Antigravity arm-or-retire.

---

## 4. Why wave 1 leaked — the five design defects wave 2 removes

1. **The coordination channel was unreadable by construction.** `SQUAD-LEDGER.md` was untracked
   and local to each machine; #5251 said so in its first paragraph, and D and F then died into
   exactly that file. F's blocker ("PR-1 not on main") cleared at 03:26Z on 30/8 and nobody could
   see it clear. The only handoff that was ever collected (#5251) was the one posted as an issue.
2. **Teeth were fenced to one squad.** Every `.github/workflows/` edit went through Squad W, so
   every other lane shipped its organ without its executor — 14 of 20 landed PRs are inert for
   this one reason.
3. **Required-context promotion was never batched.** It is the single operator action that makes
   CI work bite; it happened once, ad hoc, and was recorded only in memory.
4. **Output was counted in PRs.** 48 of 117 merged PRs were docs/ledger-only; `.md` was 36% of
   added lines; the ledger gained 64 net open rows. Rule 3 (blind cross-family refutation of every
   diff) was met on 34/70 code PRs — with all three refuter seats alive (codex/agy/kimi PONG at
   23:20 WITA).
5. **Seats were discovered by dying.** Two weekly caps hit on 29/8; the seat-state pre-check
   built to prevent this reads a report that is five days stale.

---

## 5. Wave 2 — strong sessions, multi-LLM by construction, anti-waste, three machines

### 5.1 Binding rules (delta over `00-BATTLE-PLAN.md` §4; everything not listed there still holds)

1. **Ledger = one GitHub issue per squad.** Title `SQUAD <X> — wave 2`; one comment per step
   (GROUND / BUILD / VERIFY / SHIP / BITE-OBSERVED / BLOCKED / NEEDS-RULING). Readable from every
   machine, no union-merge conflicts, `gh issue view` is the conductor's cadence. A local
   `SQUAD-LEDGER.md` is scratch only and carries no state the issue does not.
2. **Every squad may edit `.github/workflows/` for its own lane.** Conditions: Codex GPT-5.6 sol
   blind refutation (xhigh), `actionlint` green, the pre-commit lease on the file, auto-merge OFF
   for that class, conductor merges on gates-green evidence _posted in the issue_. Serialisation is
   by lease, not by squad.
3. **A PR is opened only with a `Bites:` line in its body** naming the consumer and the observation
   that proves the change is in force — and the squad makes that observation before it reports
   the item DONE. "A future job will run it" is not a consumer: the job ships in the same PR.
4. **Ledger rows travel inside arming PRs only.** Found-but-not-fixed → squad issue → the conductor
   folds them into ONE ledger PR per day. Spec corrections → a one-line edit of the `L*.md` inside
   the lane PR, never a separate docs PR.
5. **D3 is satisfied by a real non-Anthropic build lane**, never by `seat_override`: one Codex /
   Kimi-for-coding / GLM-5.2 (TP1) builder per Gear ≥ 2 pack. Multi-LLM is the lint, not a
   preference.
6. **Effort by gear**: Gear 1 `medium`, Gear 2–3 `xhigh`; `max` only on a declared Gear-3
   adjudication. No council unless its gate fires. Refuter default Kimi K3 (flat); Codex sol only
   for workflow / security / migration diffs; agy for cross-file consistency sweeps.
7. **Seats**: probe before launch (`python3 scripts/claude_seat_quota.py --json` on Pro,
   `--from-report` on Mini); quota regex → exit 98 → conductor reassigns; slot 6 (Team) never
   self-served. One seat per squad, one headless `claude -p` lane per seat, ≤3 Claude lanes on Pro,
   2 on Mini, 1 on M5.
8. **Restart = same worktree, same command**; the mandate's first act is reading the squad issue
   and `gh pr list --state open --head <prefix>`. Rule 8 (three reds, same cause → suspend) unchanged.
9. **Done = bite observations made**, reported as a table in the squad issue's closing comment,
   not as a PR count.

### 5.2 Squads (wave 2) — one orchestrator session each (Opus 5 xhigh), builders inside

| Squad                                       | Lanes, in order                                                                                                                                                                                                                     | Machine · seat                                                                     | Builders (non-Anthropic lane in bold)      | Refuter                                                                           | First bite                                                      |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------ | --------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| **S — STOP**                                | required-context batch issue (day 0, 1 h) → L04-PR1 `lane_check` hook → executors for `seat_build` suites and codec-parity lint → L06-PR1 trigger-symmetry → arm-or-archive of the 4 unscheduled instruments → 2/9 readiness report | Pro · slot 2                                                                       | **Codex** (workflow class) + Sonnet 5      | Kimi K3 for Codex-built, Codex sol for Sonnet-built workflow diffs                | guilt fixture reddens a real PR on a required job               |
| **D′ — DATA**                               | day 0: push `agent/nuzantara/craft-d/data-migrations` as-is (rescue) → finish L12-PR1 gate round 2 (baseline + 4 real-column arming) → L12-PR2 (migration **299**, provenance + checksum)                                           | Pro · slot 3 (Docker `postgres:15` lives here)                                     | Sonnet 5 + **GLM-5.2 counter-build** (TP1) | Codex sol, migration upgrade+downgrade in `--sandbox workspace-write`             | codec revert → 3 red in CI shard (already armed in `tests.yml`) |
| **F′ — FLEET & SECURITY**                   | day 0: push `craft-f-hold/seat-state-comment-fix` → L09-PR2 `fleet_burst` → L13-PR1 `with_seat` broker → L13-PR2 tailnet drift receptor → L13-PR3 (after L10-PR1)                                                                   | Mini · slot 4 from 1/9 08:00 WITA (slot 5 until then if free)                      | **Codex** (security class) + Sonnet 5      | Kimi K3 + GLM-5.2                                                                 | a codex child's `env` carries exactly its seat credential       |
| **L — LEARNING & IMMUNE**                   | L10-PR1 ratchet → L08-PR1 immune contracts → L08-PR2 Sentry repoint → L08-PR3 `.bak` purge → L04-PR2 lane outcome telemetry → L03-PR1 decision registry                                                                             | Mini · slot 5                                                                      | Sonnet 5 + **Kimi-for-coding**             | Codex sol                                                                         | ratchet red on +1 overdue in CI                                 |
| **H — HEAD**                                | L02-PR1 attestation + scar cold storage → L02-PR2 repomap cap → L10-PR3 superscar prune → L03-PR2 citation lint → L10-PR2 canon-block comparator                                                                                    | M5 · slot 3 when D′ frees it (day 2); pure repo edits, no daemons — M5 stays light | Sonnet 5 + **Kimi-for-coding**             | Codex sol + agy width (consistency of the injected surface across the 3 machines) | turn-1 attestation ≤ ruled budget on Pro, Mini, M5              |
| **X — replica completion** (no Claude seat) | the 6 deferred TP1 runs when the weekly quota resets → INDEX §I one-file PR                                                                                                                                                         | Mini · API seats only                                                              | tp1-qwen3.8-max, tp1-deepseek-v4-pro       | —                                                                                 | 65/65 files on disk                                             |
| **Conductor**                               | issues cadence every 30 min; merges the workflow class; one daily ledger PR; rulings batch to Zero in ONE message; re-arms PR watches at first act (a fork's watch dies with the fork)                                              | Pro · slot 1, interactive, light                                                   | —                                          | —                                                                                 | zero squads silent > 45 min without an issue comment            |

Machine load respects the measured limits: Pro = conductor + S + D′ (3), Mini = F′ + L (2) plus
the seatless X lane, M5 = H (1) alongside Zero's own interactive session. Seats: 1 conductor,
2 S, 3 D′→H, 4/5 F′, 5 L; slot 6 untouched.

### 5.3 Timeline (estimate, not a vow)

- **Day 0 (31/8)** — rescue pushes (D branch, F held commit), seat probe + Keychain re-login
  (§6 item 10), required-context batch issue, rulings batch to Zero, squad issues created,
  S / D′ / L launched.
- **Day 1 (1/9)** — F′ launches at the 08:00 WITA slot-4 reset; S ships the 2/9 readiness
  report **before 00:00Z on 2/9**; Zero answers the batch (or squads keep placeholders).
- **Day 2 (2/9)** — H launches on M5 as D′ frees slot 3; X lane runs on the TP1 reset.
- **Day 3–4** — close-out: each squad's bite table, the ledger net ≤ 0, fleet align (hook-dir
  copies ×3 as `operator[control-plane]` rows), CAPTURE (memory + AMENDMENTS), and the wave-3
  input list from INDEX §D ranked against what now bites.

### 5.4 Definition of done for wave 2 (numbers, measured the same way as §1)

- ≥ 12 of the 20 unlanded first-PRs landed **and biting**, each with its observation in the table.
- Of the 14 inert wave-1 items, ≥ 8 armed (executor, schedule, or required context) or deleted.
- Turn-1 injected context ≤ the ruled budget on all three machines, by attestation.
- PENDING-ARMS net open rows ≤ 0 over the wave (closed ≥ opened).
- 0 squads silent > 45 min without an issue comment; 0 handoffs that exist only in a local file.
- D3 satisfied on every Gear ≥ 2 pack by a real non-Anthropic build lane — no `seat_override`.

---

## 6. The rulings batch (one message to Zero; each item ships its default if unanswered)

1. **Required-context batch**: promote `VOA probe organ tests`, `Restore drill wiring tests`,
   `PR collision check (advisory)` (its corpus half is blocking already), `Canary self-test +
incremental mutation`. Default: Squad S posts the evidence issue; nothing is promoted.
2. **2/9 enforcement**: enforce R9/R11/R8/R10 as-is on Tuesday (≈25% of Gear-3 PRs go red until
   packs carry journals; `seat_override` stays the human valve) — or move the date once, with a
   compliance target. Default: enforce as-is; S ships the readiness report.
3. **Context budget number** for L02-PR1 (INDEX proposes ≤120 KB from 774 KB; precedent: the
   ruled 17 KB `MEMORY.md`). Default: 120 KB as a NOTICE, no FAIL.
4. **Effort default for floor-2 diffs** (L09-PR3 is logged-only until ruled). Default: `medium`.
5. **`appetite` exceeded** → suspend by default, or notice + acknowledgment (rule 14 today).
   Default: notice + ack, as landed.
6. **Dead-man real fire** (#5253 NR-2). Default: dry-run until VOA go-live.
7. **Tailnet ACL apply + ttyd shell** (`operator[GUI]`, X2 P0 — the PII machine). No default: this
   one cannot be shipped by a session.
8. **`/prime` Google Maps key** (#5252, `operator[GUI]`). No default.
9. **M5-only research (§1.5)**: publish / keep internal / archive. Default: back up to Pro+Mini
   under `~/research-internal/` (not the repo) today; decide later.
10. **Pro Keychain slots 2–5**: `claude_seat_quota.py` reads slot 1 only (session 30%, weekly 11%,
    weekly reset 6/9); slots 2–5 answer 401 / absent — quota-aware launch needs an interactive
    re-login per profile (`operator[GUI]`). Default: F′ and L launch on `--from-report` staleness
    and accept the risk; the conductor treats exit 98 as the signal.
11. **Provenance of the smoke promotion**: record it on main (this file does, §2). Default: done.

---

## 7. Appendix — the measurements this plan stands on (re-run before trusting)

```bash
git fetch origin main
# merged PRs of the wave, with files + bodies (117 at measurement time)
gh pr list -R Bali-Zero/Teman2 --state merged --limit 200 --search "merged:>=2026-08-29" --json number,title,body,files
# required contexts — classic API only (the rules API returns zero rules)
gh api repos/Bali-Zero/Teman2/branches/main/protection/required_status_checks --jq '{n:(.contexts|length),contexts:.contexts}'
# which workflow executes an artefact, and whether it can go red
git grep -l -- "<artefact>" origin/main -- '.github/workflows/' ; git show origin/main:<wf> | grep -c 'continue-on-error: true'
# organs on Mini: state by content, not by exit code
ssh mini 'launchctl print gui/$(id -u)/com.nuzantara.voa-probe | grep -E "runs =|last exit"; tail -2 ~/logs/voa-probe.log'
# 2/9 readiness: Gear-3 packs without a council journal
for d in $(git ls-tree -r --name-only origin/main -- evidence/ | grep pack.yml$ | xargs -n1 dirname | sort -u); do g=$(git show origin/main:$d/brief.yml | grep -E '^gear:' | awk '{print $2}'); c=$(git show origin/main:$d/pack.yml | grep -cE '^council_run:'); [ "$g" = 3 ] && [ "$c" = 0 ] && echo "$d"; done | wc -l   # 46 on 30/8
# rule flip dates
git show origin/main:scripts/evidence_pack_lint.py | grep -nE '(ENFORCEMENT|DEPRECATION)_DATE = '
# Squad D's unlanded build
git -C .worktrees/craft-d-data-migrations diff --stat 655bcd5a6~1 655bcd5a6 | tail -1 ; git -C .worktrees/craft-d-data-migrations diff --stat | tail -1
```

Numbers: 117 PRs · 48 docs/ledger-only · `.md` 36% of +84,038 lines · 16 PRs touch workflows ·
34/70 code PRs name a refuter seat · 33 PRs carry an evidence pack · 69 Gear-3 packs on main,
23 with `council_run`, 22 with ≥2 seats · ledger 598 → 662 open rows · xfamily 59/65 ·
anatomy 17 files · plan 16 files · required contexts 12 · seat pings 30/8 23:20 WITA:
codex PONG, agy PONG, kimi PONG.
