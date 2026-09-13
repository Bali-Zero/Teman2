# B1 — ledger rows, held here because the shared ledger is deadlocked

**Written 2026-09-12 by the B1 Dux window (Pro, session `d3bc5d81`, generation 4).**
These rows belong in `.claude/skills/modus/PENDING-ARMS.md`. They are NOT appended
there by this PR, on the staff room's ruling: that file carries a `merge=union`
driver which git honours and GitHub's merge machinery does not, so two open PRs
touching it disagree permanently and re-probing never clears it. Measured
2026-09-12 06:36Z, two open PRs already touch it — **#6269** and **#6080**, the
latter `DIRTY` on that file alone. Opening a fifth writer would compound a
stalemate rather than risk one.

**Handoff:** whoever holds the union appends these rows, from a branch cut from
fresh `origin/main`, verifying `git diff origin/main -- <file>` is `+N/-0`.
Until then this file is the record.

---

## PWC-CONDITIONS for #6268 (B1.2 PR-A, the eleven dense-path variants) — MERGED

- **C1 — discharged by event.** PR-B #6270 was merged immediately after #6268
  (both are on `origin/main`); between the two merges the registry had no guard,
  so an unlabelled score literal would not have gone red. The window is closed.
- **C2 — discharged.** Run `34667113354` (`Harness floor recompute`) was
  re-triggered with `gh run rerun`, never with `gh workflow run --ref`.
- **C3 — DISCHARGED BY THIS WINDOW.** "The next B1 brief.yml records envelope id,
  deadline and seats." Both B1 briefs authored after that verdict do:
  `evidence/2026-09/agent-nuzantara-backend-rag-b1-5-query-vectors-7057dd74/brief.yml`
  and `…-b1-4-support-signal-0956ceb5/brief.yml` each carry `generation: 4`,
  `deadline_utc: 2026-09-12T14:00:00Z`, the deadline authority with its fleet
  envelope id, the rulings applied with their envelope ids, and a `seat_probe`
  block with a live probe result per seat.

## PWC-CONDITIONS for #6270 (B1.2 PR-B, the tripwire guard) — MERGED

- **C1 — CORRECTION OF RECORD.** #6270's body claimed "`ruff check` /
  `ruff format --check` clean" for the guard file. That is **false**: `ruff check`
  exits 1 with one `I001` (import block un-sorted — `backend.tests.fixtures…`
  grouped with `pytest`; `known-first-party` lacks `backend`), the only `I001`
  under `backend/tests/`. It is not CI-blocking, because lint runs on
  `backend/app/` only. Corrected here rather than by pushing to a frozen branch.
- **C2 — OBSERVATION CARRIED.** B1-design §4 asks the PR body to show the guard
  going red on a re-introduced unlabelled value; #6270's body showed guilt A and
  B only. The gate measured the missing one: planting `{"text": …, "score": 0.87}`
  without `score_kind` in one variant turns **G4 red on that node id**, plus
  G5/G6 body parity. B1.2 is not declared closed without this line.
- **C3 — method, for whoever hits it next.** Red checks on a PR whose merge ref
  predates a just-merged sibling are re-triggered with a fresh `pull_request`
  event (close/reopen), never `gh run rerun`, because the stale run checked out
  the old merge ref.

## PWC-CONDITIONS for #6274 (B1.3, the frozen benchmark) — MERGED

- **C1 — the imperator's, not this window's.** Three unpragma'd digests in that
  PR's evidence (`pack.yml:32,34`; `baseline-report.json:4`); the imperator ships
  a small audit PR on main. No B1 PR touches `.secrets.baseline`.
- **C2 — CORRECTION OF RECORD.** #6274's body claimed "one pragma per long-hex
  line". False at that head: only `pack.yml:31` carried one.
- **C3 — CORRECTION OF RECORD.** That pack's `code_sha` `951bad7b` was three
  commits behind the head (floor receipt 6297 vs 6408 measured).
- **C4 — OWED BY B2.1.** The agreement between the pinned generic-word rule and
  the labels is protected only by the manifest sha freeze. A test is owed when
  the rule activates, and it is written into B2's opening brief.

## B1.5 (#6284) — facts for the ledger

- **The batch.** 23 provider attempts of an authorized 40, 0 failures, artifact
  sha256 `0021c3275b7bd9f8…`, query-list sha256 `6b1beb37e45384ae…` stable across
  the dry-run, the aborted attempt and the shipped artifact.
- **An aborted attempt preceded it**, 0 provider attempts, receipt preserved as
  `b1-5-precall-aborted.json` under ruling I24a.
- **The cost telemetry was ATTEMPTED and failed.** The product's `record_llm_call`
  writes `llm_cost_events` (migration 112) on every embedding call, so the batch
  attempted ~23 Postgres inserts through the product path. All failed on
  authentication and the JSONL fallback failed too (`/data` is not writable from
  a worktree). **No row was written.** The receipts, not the telemetry, are the
  record of spend.
- **FOLLOW-UP OWED, from fresh `origin/main`** (never by re-signing a gated head):
  a test binding the artifact FILE's sha256 to the value recorded in
  `b1-5-precall.json`. Today that binding is checked by hand — by the Dux and by
  an independent read-only audit — and not by CI.

## B1.4 (#6285) — facts for the ledger

- **Support-signal method CHOSEN** (staff room, ruling I26): candidate (iii),
  the Codex seat through the unchanged `CodexExecClient.generate` adapter,
  majority-of-3 with a split vote read as NOT_SUPPORTED; fallback (ii), the local
  Ollama judge. Recorded in `README.md` §Sequencing, closing item (e) for Wave 2.
- **The frozen 16-pair set is recorded UNFIT ON ITS OWN** to select a support
  signal: its negatives are built by deleting the trigger token. The manifest
  stays frozen as merged; distractor pairs become mandatory in B2.1's supplement.
- **OWED BY B2.1 — a third set.** The distractor probe's negatives all ANNOUNCE
  their insufficiency, so they measure "entity present plus a disclaimer". The
  hard case — entity present, referent wrong, no meta-commentary — is measured by
  neither set.

## Seat facts worth keeping

- **The organism board and memory were both wrong about Codex on Mini.** Probed
  live 2026-09-12 04:47Z: `CODEX_HOME=~/.codex-acct2`, `gpt-5.6-sol` answered
  PONG, and it then carried two council rounds. The board reported `UNKNOWN_ERR`
  and a memory entry dated the same day said the seat was dead. A seat that did
  not run is not a seat that agreed — and a seat reported dead is not a seat that
  is dead. Probe before believing either.
