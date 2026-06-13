# WR3 Quality Decisions — F18 / F20 / F21 (operator-decided, NOT executed)

> **Status: DECISIONS RECORDED — NOT EXECUTED.** This is a decision record, not
> an implementation. It chooses, for each of the three WR3 feature-debt findings
> (F18 / F20 / F21), the **highest-quality** option among the fork the spec
> already lays out, and fixes a single **master ordering** so every node/session
> follows the same plan. The actual code/cron/SQL changes remain **operator-
> gated** — each is tagged "operator-decided, NOT executed by this doc".
>
> Date: 2026-06-12 · Decider: Antonello ("WR3 scegli tu per la qualità più
> alta") · Author of record: Claude (Opus 4.8), L2 docs authority ·
> Specs: [`WR3-DEBT-INDEX.md`](WR3-DEBT-INDEX.md),
> [`WR3-F18-evoskill-zero-pressure.md`](WR3-F18-evoskill-zero-pressure.md),
> [`WR3-F20-manifest-validator-incompatible.md`](WR3-F20-manifest-validator-incompatible.md),
> [`WR3-F21-reflexion-cron-theater.md`](WR3-F21-reflexion-cron-theater.md).

---

## 0. The quality principle that decides all three

> **A system that runs green but produces nothing is worse than one that's off.**
> Green-theater is a **FALSE health signal**: it tells the operator "this is
> working / evolving / enforced" while it produces, validates, or learns
> nothing. A false-green costs more than an honest "off" because it (1) consumes
> real resources (cron slots, DeepSeek spend, a Sunday window), (2) corrupts the
> operator's mental model, and (3) suppresses the alarm that would otherwise
> trigger the real fix.

This is **SYMBIOSIS Law 7** made operational: *"se non gira, non è
un'invenzione — è un'ipotesi."* A loop that exits 0 while synthesizing nothing
is not a working invention; it is an **untested hypothesis wearing a green
checkmark**. The whole F18/F20/F21 cluster is one disease — "armed but inactive
/ green but empty" — and the cure is the same everywhere: **prefer
truth-of-signal over appearance-of-working.**

Two corollaries used below:

- **C1 — Off-honestly beats green-theater.** When a loop has no real input
  (no curriculum, no episodes), the highest-quality action is to **suspend the
  cron** so it stops emitting a false-green signal — UNTIL the input exists.
  Suspending is not giving up; it is refusing to lie about progress.
- **C2 — Never weaken the contract to make the green light return.** When a
  validator/gate rejects reality, the high-quality fix is to make **reality
  conform to the contract** (deterministic production), not to **relax the
  contract to accept the broken reality**. Relaxing the gate makes the green
  checkmark mean nothing — the opposite of truth-of-signal.

---

## F18 — EvoSkill loop runs but proposes nothing (zero pressure by construction)

**Ground truth (verified in spec, re-read this turn):** the loop engine is
HEALTHY — `vendor/evoskill/src/loop/runner.py:319` sets the pass bar
(`avg_score >= 0.8`), `:323` marks a sample a failure only below it, and
`:326-328` `continue`s with *"All samples passed, no proposal needed"* when
`len(failures) == 0`. The seed dataset
`agent-library/.evoskill/data/seed-patterns.csv` is **synthetic** rows the base
program maps at ~100% — so `len(failures) == 0` **by construction** and the
proposer never fires. The cron `com.balizero.agent-library-evolver.weekly`
(Sun 03:00 WITA) runs and exits clean every week, learning nothing.

### DECISION — Option (b) NOW (suspend the cron), then Option (a) LATER (build a real curriculum). Two-phase.

- **Phase 1 (now):** **SUSPEND** `com.balizero.agent-library-evolver.weekly`.
- **Phase 2 (later, once a real curriculum exists):** **resume** with a
  curriculum drawn from **real cicatrix scars the base program actually FAILS**
  — replacing the synthetic `seed-patterns.csv` so `avg_score < 0.8` fires the
  proposer for real.

### RATIONALE (tied to §0)

The evolver is the **purest F18-class green-theater**: the loop is genuinely
healthy, which is exactly its trap — it is **green every Sunday and graduates
nothing, by design of its dataset**, not by a bug. Running it weekly asserts
"the skill library evolved" while it provably cannot evolve from a curriculum
the base program already solves at 100%. By C1, the highest-quality action is to
**stop asserting false progress**: suspend the cron, removing the false
"we're-evolving" signal *and* the recurring DeepSeek judge spend (~$0.055/run per
the audit) and the Sunday slot — none of which buy anything until there is real
pressure to learn from.

Phase 2 is the real fix the spec's Option (a) describes — but it is **content
work that must be panel-reviewed before it becomes the judge's ground truth**
(F18 §5: *"a poisoned curriculum is worse than an empty one"*). So we do NOT
build it inline here; we suspend first (honest off), then resume with a reviewed
curriculum. This is independent of the supervisor blocker (F18 §5: the evolver
infra is healthy; the fix is dataset/scheduling, not pipeline repair).

### Contour fixes to close alongside the suspend (record, from F18 §2)

- Add `TELEGRAM_BOT_TOKEN` to the evolver **wrapper env** so suspend/failure
  actually alert (today any wrapper alert is **skipped silently** — same
  green-cron-no-signal family the principle condemns).
- Resolve the **weekly-vs-daily double-LaunchAgent** ambiguity (settle which
  schedule is authoritative in the plist set) before Phase-2 resume.

### Operator action — **operator-decided, NOT executed by this doc**

- Suspend: `launchctl bootout gui/$UID/com.balizero.agent-library-evolver.weekly`
  then `launchctl disable gui/$UID/com.balizero.agent-library-evolver.weekly`
  (persists across reboot). Reverse with `enable` + `bootstrap`.
- Phase 2 (separate, reviewed task): author the scar-derived curriculum, panel-
  review it, replace `seed-patterns.csv`, then re-enable the cron.

---

## F20 — Manifest validator is dead code, incompatible with the only real manifest

**Ground truth (verified in spec, re-read this turn):**
`scripts/wr3_episode_manifest.py` defines 18 `MANDATORY_FIELDS` (`:20-39`), a
`validate_manifest()` (`:123-142`) that raises on missing fields (`:125`),
requires `critic_verdict ∈ {PENDING, PASS, FAIL, DEGRADED}` (`:129`),
`wr3_room_version == "0.1.0"` (`:134`), and non-empty `claim_ids` (`:141`); plus
a deterministic `ManifestBuilder.finalize/write` (`:87-116`). **No live pipeline
calls the builder** — the real manifest is authored by a **free-form LLM
subagent** prompted as a *string* at `scripts/wr3_supervisor.py:403`. The only
real manifest on disk
(`apps/war-room/output/episode/content-creator-3-roads-2026-05-29/episode_manifest.json`)
shares **2 of 18 field names**, has `claim_ids = None`, `wr3_room_version =
None`, and `critic_verdict = "PASS-WITH-NOTES"` (not in the enum) — it would
hard-fail the validator on the first gate. The validator is wired into **no**
pipeline/CI/cron.

### DECISION — Option (a): make `wr3-post-assembler` call `ManifestBuilder.write()` DETERMINISTICALLY. Reject Option (b) (relax the validator to match the LLM free-form output).

### RATIONALE (tied to §0, C2)

The validator encodes the **legal-traceability contract** of WR3: `claim_ids`
binding every regulatory/numeric claim back to NB ground truth, per-asset
sha256 hashes, and a `critic_verdict` from a **closed set**. Option (b) —
relaxing the validator to accept the current free-form manifest (16/18 fields
missing, `claim_ids = None`) — is **quality surrender by C2**: it makes the
green checkmark mean nothing and **silently drops the legal-claim audit trail**,
which is the entire reason WR3 grounds its facts in NotebookLM. A manifest with
`claim_ids = None` that "passes" is a worse lie than no validator at all.

The highest-quality fix is to make **production emit the 18 fields
deterministically** via `ManifestBuilder.write()` — *not* via an LLM prompt that
may hallucinate or omit them — then wire `validate_manifest()` into the
supervisor's `assembly_ready → critic_verdict` transition **and** a CI gate, so
the validator stops being dead code and rejects malformed manifests at the
moment of assembly. Determinism here is itself an anti-hallucination measure:
the manifest is the audit record, and an audit record an LLM free-writes is not
trustworthy.

**`PASS-WITH-NOTES` caveat (flag for confirmation):** the real manifest's
`critic_verdict = "PASS-WITH-NOTES"` is *not* in the schema enum. Add it to the
allowed set **ONLY IF** `wr3-critic` legitimately emits it as a distinct verdict
(i.e. it is a real critic output, not an LLM paraphrase of "PASS"). If it is a
genuine verdict, widen the enum deliberately as part of the deterministic
builder work; if it is an LLM artifact, the deterministic builder eliminates it.
**Do not silently widen the enum** (F20 §4) — that changes what "passed" means
to every downstream consumer.

### DEPENDENCY

**Moot until the supervisor runs.** Wiring a validator into a dead pipeline
(`com.balizero.wr3.supervisor` exit=78) changes nothing observable and there are
no fresh episodes to validate. F20's fix lands **AFTER** the supervisor is
revived, **in the post-assembler** (the producer side), then the validator is
wired into the live transition + CI.

### Operator action — **operator-decided, NOT executed by this doc**

- After supervisor revival: refactor `wr3-post-assembler` to call
  `ManifestBuilder.finalize/write()` (replace the free-form prompt at
  `wr3_supervisor.py:403`); wire `validate_manifest()` into
  `assembly_ready → critic_verdict` + add a CI gate; resolve `PASS-WITH-NOTES`
  (confirm-then-widen, or eliminate via determinism). Reviewed before merge.

---

## F21 — Reflexion cron is theater: a declared stub exits 0 every Sunday

**Ground truth (verified in spec, re-read this turn):** the WR3 reflexion target
`~/.claude/skills/bali-zero-brand/wr3/_reflexion-synthesis.py` is an **816-byte
DECLARED STUB** — line 4 *"PLACEHOLDER (S7.3 stub) — full implementation lands
at S7.5."*, lines 21-22 print to stderr then `sys.exit(0)`. It reads nothing,
writes nothing. The cron `com.balizero.wr3.reflexion.weekly` (Sun 02:30 WITA) is
**green every Sunday**; `wr3/_proposed/` is **empty** and there is **no
`lessons.md` under `wr3/`** after 12+ Sundays. The real sibling to port from,
`~/.claude/skills/bali-zero-brand/_reflexion-synthesis.py`, is a genuine
**314-line** implementation. The plist is **unversioned** (Pro-only
`~/Library/LaunchAgents/`).

### DECISION — Option (a) real implementation (port the WR2 314-line pattern), GATED behind the supervisor. Two-phase: SUSPEND now, IMPLEMENT later.

- **Phase 1 (now):** **SUSPEND** `com.balizero.wr3.reflexion.weekly` so it stops
  emitting a false-green signal.
- **Phase 2 (after supervisor revived + episodes flow):** port the real WR2
  314-line synthesizer; also version the plist into `infra/launchagents/`
  (Option (b), folded in — not an alternative).

### RATIONALE (tied to §0, C1)

The 816-byte `sys.exit(0)` stub is the **purest green-theater in the system**: a
weekly cron that asserts "reflexion done" while reading and writing nothing, for
12+ consecutive weeks. By C1, the immediate highest-quality action is to
**suspend it** — an honest "off" that stops the false "WR3 is learning each
week" signal *right now*, with zero dependency on anything upstream (the suspend
half needs no supervisor).

The real fix (Phase 2) is Option (a): port the proven WR2 sibling
(`_reflexion-synthesis.py`, 314 lines) to actually read last-7-days episodes
(`apps/war-room/output/episode/<last-7d>/*`) + the human-review queue
(`output/queue/wr3-human-review-queue.json`), synthesize **≤10 lessons** →
`wr3/<agent>/lessons.md`, write skill drafts → `wr3/_proposed/<date>-<slug>.md`,
with the **Sonnet → Gemini** cascade on quota-exhaust (per CLAUDE.md Multi-LLM
cascade + the contract `docs/wr3/contracts/reflexion-synth.yaml`). Option (b)
(version the plist into `infra/launchagents/`) is folded in, not an alternative
— a fleet/rebuild currently loses the unversioned schedule.

But Phase 2 is **gated on the supervisor** (F21 §4, load-bearing caveat): with
`com.balizero.wr3.supervisor` exit=78 and **zero episodes in 12 days**, even a
faithful port would emit nothing — there is **no input corpus**. Porting it now
would just replace a 816-byte green-theater stub with a 314-line green-theater
implementation. So: off-honestly **now**, real implementation **later** once
there is input. Same principle, applied in time order.

### Operator action — **operator-decided, NOT executed by this doc**

- Suspend now:
  `launchctl bootout gui/$UID/com.balizero.wr3.reflexion.weekly` +
  `launchctl disable …` (reverse with `enable` + `bootstrap`).
- Phase 2 (after supervisor + episodes): port WR2 314-line synthesizer, version
  the plist into `infra/launchagents/`, wire the Sonnet→Gemini cascade. Reviewed
  before it runs against real artifacts.

---

## CROSS-CUTTING — the master ordering (STEP 0–5)

The single highest-leverage action is **STEP 0: revive the WR3 supervisor**. It
is the **shared upstream blocker**: F20 (post-assembler must emit a manifest)
and F21 (reflexion needs an episode corpus) **both** depend on episodes flowing,
which the dead supervisor prevents. Fixing either before the supervisor produces
**green-but-still-empty** results — exactly the failure §0 condemns.

> **STEP 0 is NOT one of F18/F20/F21 — but it gates two of them.** It is a
> **separate diagnosis** (the supervisor's `exit=78`), and it is the **true
> first task**. Recommendation: open a dedicated `WR3-supervisor-revival`
> diagnosis/spec — do not bury the revival inside F20 or F21.

| Step | Action | Gated on | Independent of supervisor? |
|---|---|---|---|
| **0** | **Revive `com.balizero.wr3.supervisor` (exit=78)** — separate diagnosis, the true first task | — | n/a (it *is* the blocker) |
| **1** | **F18 Phase-1** — suspend the evolver cron (+ contour: `TELEGRAM_BOT_TOKEN`, weekly-vs-daily) | — | ✅ yes — do now |
| **2** | **F21 Phase-1** — suspend the reflexion cron (stop false-green) | — | ✅ yes (suspend half) — do now |
| **3** | **F20** — deterministic `ManifestBuilder.write()` in post-assembler + wire `validate_manifest()` into the live transition + CI | STEP 0 | ❌ — after supervisor revived |
| **4** | **F21 Phase-2** — port the WR2 314-line reflexion + version the plist + cascade | STEP 0 + episodes flowing | ❌ — after supervisor revived & episodes exist |
| **5** | **F18 Phase-2** — resume the evolver with a real, panel-reviewed scar curriculum | a reviewed curriculum exists | ✅ — independent of supervisor (needs curriculum, not episodes) |

**Why this order is the highest-quality one:** STEPS 1 and 2 stop two
false-green signals **immediately** with no upstream dependency (truth-of-signal
first). STEP 0 unblocks the only work that can produce real value (episodes).
STEPS 3–4 then build real enforcement/learning **on top of real input** — never
green-on-empty. STEP 5 is decoupled (curriculum, not episodes) and gated only on
a reviewed curriculum.

---

## What's executable autonomously vs operator-gated

| Item | Autonomous (L2 docs / non-prod) | Operator-gated | Why gated |
|---|---|---|---|
| **This decision record** (write/commit/PR) | ✅ | — | docs-only, L2 authority |
| **STEP 0** supervisor `exit=78` revival | — | ✅ | prod cron + separate diagnosis; touches the live episode pipeline |
| **STEP 1** suspend evolver cron (`launchctl bootout/disable`) | — | ✅ | mutates a live LaunchAgent on the Pro |
| F18 contour: `TELEGRAM_BOT_TOKEN` in wrapper env / weekly-vs-daily | — | ✅ | touches wrapper env + plist set; secret handling |
| **STEP 2** suspend reflexion cron (`launchctl bootout/disable`) | — | ✅ | mutates a live LaunchAgent on the Pro |
| **STEP 3** F20 deterministic builder + validator wiring + CI gate | — | ✅ | prod code on the assembly path; manifest = legal audit record; reviewed before merge |
| `PASS-WITH-NOTES` enum decision | — | ✅ | changes the meaning of "passed" for all consumers — confirm-then-widen |
| **STEP 4** F21 reflexion port + plist versioning + cascade | — | ✅ | real 314-line code run against episode artifacts; reviewed before it runs |
| **STEP 5** F18 curriculum rebuild + cron resume | — | ✅ | curriculum becomes the judge's ground truth — panel-reviewed before it lands |

**Net:** the only thing this doc executes is **itself** (the decision record).
Every operational change (the two suspends, the supervisor revival, the two real
implementations, the curriculum) is **operator-gated** and reviewed — consistent
with each spec's `NOT EXECUTED` guardrail.

---

## Index pointer (post-#1345-merge)

`WR3-DEBT-INDEX.md` currently exists only on the unmerged PR #1345 branch
(`agent/nuzantara/docs/wr3-f18-f20-f21-specs`), not on `main`. To avoid a merge
race, this doc does **not** edit the index here. **After #1345 merges**, add to
`WR3-DEBT-INDEX.md`:

```markdown
## Decisions

- [`WR3-QUALITY-DECISIONS.md`](WR3-QUALITY-DECISIONS.md) — operator-decided
  highest-quality option per finding (F18 suspend-then-curriculum; F20
  deterministic builder, reject relax; F21 suspend-then-WR2-port) + master
  STEP 0–5 ordering with supervisor `exit=78` revival as the true first task.
```

---

## Reference

- Index: [`WR3-DEBT-INDEX.md`](WR3-DEBT-INDEX.md) (cross-cutting blocker note).
- F18: [`WR3-F18-evoskill-zero-pressure.md`](WR3-F18-evoskill-zero-pressure.md)
  — `runner.py:319/:323/:326-328`, seed `seed-patterns.csv`, cron
  `com.balizero.agent-library-evolver.weekly`.
- F20: [`WR3-F20-manifest-validator-incompatible.md`](WR3-F20-manifest-validator-incompatible.md)
  — `scripts/wr3_episode_manifest.py` (`MANDATORY_FIELDS:20-39`,
  `validate_manifest():123-142`, `ManifestBuilder:87-116`), free-form producer
  `wr3_supervisor.py:403`, real manifest
  `apps/war-room/output/episode/content-creator-3-roads-2026-05-29/episode_manifest.json`.
- F21: [`WR3-F21-reflexion-cron-theater.md`](WR3-F21-reflexion-cron-theater.md)
  — stub `wr3/_reflexion-synthesis.py` (816 B, `sys.exit(0)`), real sibling
  `_reflexion-synthesis.py` (314 lines), contract
  `docs/wr3/contracts/reflexion-synth.yaml`, plist
  `com.balizero.wr3.reflexion.weekly`.
- Shared blocker: `com.balizero.wr3.supervisor` exit=78 (STEP 0, separate
  diagnosis).
- Audit source: Fable-5 system audit 2026-06-11 (findings F18/F20/F21).
- Principle: SYMBIOSIS Law 7 — *"se non gira, non è un'invenzione — è
  un'ipotesi."*
