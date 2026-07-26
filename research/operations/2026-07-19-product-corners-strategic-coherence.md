---
date: 2026-07-19
domain: operations
client_case: none
adversarial_review: glm-5.2
sources:
  - 4-lane read-only Workflow wf_0ba0d328 (corner readers KBLI/Visa/intake + cross-organ promise mapper; every claim file:line-cited; journal in session transcript dir)
  - .claude/skills/kbli-navigator/SKILL.md (396 ll) · .claude/skills/visaoracle/SKILL.md (256 ll) · .claude/skills/intake/SKILL.md (228 ll)
  - apps/organism/organism/organs_registry.yaml (2089 ll, full pass) · scripts/automation_catalog.json · INDEX.md
  - apps/backend-rag routers visa_oracle.py / knowledge_visa.py / kbli_notebook.py · _abstain_policy.py (live read)
  - docs/plans/2026-07-17-visa-oracle-v2/00-product-design.md §10-11 · research/operations/2026-07-19-kbli-batch-b-design.md (frontmatter+60)
---

# TRACK PRODOTTO — strategic coherence of the product corners (KBLI · Visa Oracle · intake)

> Twin-Fable mandate (Zero, 2026-07-19), M5 leg — complementary to the Pro leg's TRACK
> GUARDIANI (monitoring-plane audit). Question: where do the three product roadmaps step on
> each other or leave uncovered ground, and which client-facing promises rest on organs the
> guardians track is auditing. Method: 4 read-only lanes (one per corner + one cross-cutting
> promise→organ mapper), synthesis + on-disk re-probes by the conductor. Scope discipline:
> `research/operations/2026-07-19-guardians-*` never read; monitoring-plane scripts never
> opened — only their registry rows and corner-side prose cited.

## §Meta-pattern (the one defective belief generating the findings)

**Each corner is internally rigorous; the SPACE BETWEEN corners is unowned.** All three
files show mature per-corner discipline (abstain gates, quarantine-as-success, per-batch
Zero GO, generator≠grader ships) — and none of the three declares the other two as a
consumer, a dependency, or a hand-off target. Every high-severity finding below is an
instance of the same shape: a promise, organ, or name that lives at a corner BOUNDARY and
therefore belongs to nobody. The cure class is likewise single: make cross-corner edges
explicit (consumer-maps that name sibling corners, registry rows for promise-bearing
runtimes, one source-of-truth per overlapping content area).

## 1. Findings (ranked; ✔ = confirmed on disk, H = hypothesis)

### F1 ✔ — Intake's entire runtime is OUTSIDE the proprioception net (scar #2, promise-bearing)
The intake corner carries the hardest client promise of the three ("every document lands on
the RIGHT client or is honestly quarantined", intake/SKILL.md:8-10) — yet its 8 runtime
organs on disk (`com.nuzantara.intake-worker`, `intake-blob-retention`,
`wa-mirror-intake-sweeper`, `drive-intake-drain`, `dropbox-intake`, `intake-review-reader`
(+liveness), `intake-gate-count-pusher`; plists under `infra/launchagents/`) have **ZERO
rows in `apps/organism/organism/organs_registry.yaml` and ZERO entries in
`scripts/automation_catalog.json`** (both greps empty, re-run by the mapper this session).
Nothing in the healer/state-bridge/sentinel net notices if they die or run stale code —
corroborated first-hand: intake-worker was caught running stale pre-merge code only by a
manual session restart (intake/SKILL.md:165-169). **→ HANDOFF TO TRACK GUARDIANI**: the
monitoring-plane audit should treat "an entire promise-bearing organ family absent from the
registry" as a top-tier finding of ITS OWN scope; the fix (registry rows + bridge_source
for the intake family) belongs to the guardians surface, not this track (file-scope split).

### F2 ✔ — A 7-day TTL quietly defeated a recovery promise (retention vs recovery, unowned interaction)
`com.nuzantara.intake-blob-retention` (TTL=7d) unlinked **97.7%** (24,806/25,400) of the
raw blobs the "drain the backlog via re-processing" lever depends on — Station 1 re-OCR is
structurally BLOCKED (intake/SKILL.md:121-125). Discovered by manual investigation, not by
any monitor (the cron is registry-invisible per F1). The corner names the cure (TTL
extension / cold blob-archive) but no owner. Lesson worth generalizing: **any retention
cron whose target another promise plans to re-read is a cross-promise interaction that
needs a declared owner.**

### F3 ✔/H — Cross-corner consumer gaps: the maps never name the siblings
- KBLI's mandatory consumer-map (Operating Rule #6) enumerates mouth SSR, gold, KG/Qdrant,
  native app, NB — **never visa or intake** (kbli-navigator/SKILL.md:283-286), while its own
  north star says clients make "licensing/investment decisions" on this data — exactly what
  an investor-visa consultation consumes (PMA OPEN/RESTRICTED/CLOSED is still
  cross-vintage-unaudited per FATAL-2). H: a visa-side consumer verification step for PMA
  facts is a gap nobody owns.
- Visa Oracle's v2 draft plans "Retirement & second home" and "Business/Tourism depth"
  interview lanes (00-product-design.md:586-588) that topically overlap the dedicated
  `/secondhome` (E33) and `/garuda_voa` (B1/VOA) corners — **no source-of-truth or hand-off
  declared** in either direction. H: duplicated/diverging client messaging once built.
  → Legge-5-adjacent: content ownership is a business call (§Solo-operatore).
- Intake classifies visa/KITAS/NIB docs but routes them onward to nobody ("renewal doc
  arrived → notify visa pipeline" does not exist in the corner file; intake/SKILL.md:8-9
  vs whole-file absence). H: a real product loop (doc event → compliance/visa action) is
  unclaimed — note the CRM compliance-alert family already scans `visa_expiry` columns
  (automation_catalog.json:178-180) yet intake's file never mentions it: the two halves of
  the same client promise don't know about each other.

### F4 ✔ — Visa ENFORCE precondition has a threshold gate but no STALL alarm
The flip to real engine verdicts is gated on 4 SHADOW-measured criteria; **G-a itself IS
the volume-accumulation criterion** (≥1,000 requests over ≥7 consecutive days, ≥30 codes —
visaoracle/SKILL.md:35-43), so accumulation is tracked. The narrower, real gap: G-a is a
*threshold* gate, not a *stall alarm* — a code-path change that silently stops routing
traffic to the SHADOW logger leaves the count frozen below threshold, and steady-red is
indistinguishable from slow-accumulation; nothing alerts (scar #2 shape applied to a
review-gate precondition). Cure = a no-growth-in-48h stall flag on `visa_decisions` counts
— **handed off to TRACK GUARDIANI** together with F1 (probe/digest wiring is
monitoring-plane surface; if the guardians leg declines it, the next Track A visa lane can
carry a product-side variant). (Wording corrected per GLM R1 — the first draft's "nothing
tracks accumulation" was contradicted by its own citation.)

### F5 ✔ — Correlated-failure concentration under all three corners at once
- `backend.api` (one Fly deployable) serves KBLI chat tools AND visa oracle routers AND all
  4 channels simultaneously (organs_registry.yaml:38-54) — one bad deploy stalls both
  corners' live answering.
- `apps/mouth` (one Vercel deploy) serves `/kbli/<code>` AND `/visa-oracle` on the same
  push — no per-corner canary.
- The SAME 3 external seats (Codex/GLM/Gemini) are the ship-gate for KBLI lots, Visa
  tracks, and the intake refinery **in parallel right now**; CLAUDE.md documents these
  seats going dark simultaneously (401/quota/dead-balance). An arsenal-wide outage stalls
  all three pipelines at once — a risk no single corner file can see (each sees only its
  own dependency). Mitigation already in flight this same day: Kimi K3 third family +
  kimi_client.py (cascade-debt PR) widen the gate pool.
- Redis lease registry is NOAUTH-degraded from sessions ("LEASE-GUARD SKIPPED" declared in
  every KBLI gate, kbli-navigator/SKILL.md:151-152) — same fleet-wide `agent_lock:*`
  mechanism CLAUDE.md §7 documents; H: latent collision-safety gap for ANY corner running
  concurrent hot-zone edits.

### F6 ✔ — Name collisions that will eventually misroute a search or a session
"GARUDA" = three unrelated things live today: GARUDA-FILIERA (KBLI corpus certification),
GARUDA B1/VOA (visa product corner), mata-garuda (OSINT organ family). Plus "visa expiry"
(CRM compliance family) vs "Visa Oracle" (public funnel) — disjoint systems, one word.
And the documented '10 miliar' trap: BKPM paid-up (2.5 mld, BKPM 5/2025) vs immigration
E28A (10 mld) — the KBLI corner already warns a blind sweep on one would clobber the other
(kbli-navigator/SKILL.md:199-203). Cheap cure: a disambiguation line in each corner's
header; never dispatch/sweep on the bare token "garuda"/"visa"/"10 miliar".

### F7 ✔ — Unblocked-but-unclaimed edges inside the corners' own ledgers (scar #2, product-plane)
- Visa Track B FASE-2: its blocking PR #2602 recorded merged 2026-07-17 — gate open, no
  LIVE STATE claim of a started next step (visaoracle/SKILL.md:157,161). [merged per
  corner-file/git-log narrative — NOT content-verified per W88; re-verify before building]
- Visa Track C real-engine wiring: PR1 contracts recorded merged 2026-07-18 — dependency
  satisfied, wiring unclaimed (SKILL.md:160,166-171). [same W88 caveat]
- KBLI SKILL's §next-actions list is stale relative to its own §LIVE STATE (items (3)/(4)
  superseded by Lots 1-5 done; SKILL.md:375-382 vs :79-154).
- Visa PR2b/PR3 merged with no LIVE STATE entries (self-flagged; SKILL.md:203-207).
These are documentation-drift wounds: a future session trusting the narrative would
mis-scope. Cure: corner-file hygiene rule — the merge that opens a gate updates the LIVE
STATE line in the same PR (W86 logic applied to corner ledgers).

### F8 ✔ — The W87 Postgres split is a cross-corner trap by design
Intake's ground truth is LOCAL `nuzantara_dev` (127.0.0.1), deliberately NOT the prod MCP
(intake/SKILL.md:29-31): any sibling corner/tool that assumes `postgres-nuzantara` (prod)
is authoritative silently sees ZERO of intake's 71.8k proposals / 247k queue rows. Correct
per-corner; dangerous cross-corner if undocumented outside the intake file. Cure: one line
in the other two corners' access notes ("intake state is local-Pro only").

## 2. Promise→organ dependency picture (client promises on audited organs)

Monitoring-plane-DEPENDENT promises (rows exist in organs_registry.yaml — i.e., the Pro
twin's audit perimeter carries these client promises): KBLI/visa live answering
(backend.api + qdrant + redis + postgres + all 4 channel webhooks) · KBLI page
discoverability (seo_cell_daily/28d) · regulatory freshness (regulatory_watcher_daily) ·
visa-catalog cache invalidation (infra.redis).
Monitoring-plane-INVISIBLE promises (no rows — F1): the entire intake family; the KBLI
Phase-3 "dedicated OSS re-snapshot cron" (promised in the plan, no plist found — unbuilt);
Visa SHADOW-stall blindness (F4). The visa/KBLI ABSTAIN honesty gates are in-process code
(_abstain_policy.py — kbli 0.20 / visa 0.12 verified live) — correctly not cron-monitored.

## §Solo-operatore (Legge 5 / business decisions surfaced, not acted)

1. Content ownership ruling for the overlap "visa-oracle interview lanes vs /secondhome vs
   /garuda_voa" (F3b) — who is the source of truth per topic.
2. The stale visa-oracle mission line "zero wrong answers" on a live-but-mock surface —
   disclosed and managed, but the copy is Zero's to keep or soften.
3. Batch-B Legge-5 ratifications (AQL default, Tier-4 volume) and Visa v2 §10's 4 open
   decisions — already queued to Zero; noted here only because BOTH corners queue on the
   same scarce Zero-attention slot (an implicit cross-corner scheduling collision).
4. Intake root-cause levers (retention-TTL extension / cold archive; identity-backfill)
   need an owner assignment — cheap builds, unowned.

## 3. Recommended next lanes (this track's follow-ups, disjoint from guardians)

1. **Corner cross-links PR** (docs-only, high value/cost ratio): add to each corner file a
   "Sibling corners" block — KBLI names visa/intake as consumers (PMA facts, doc events);
   visaoracle names secondhome/garuda_voa overlap + intake doc-events; intake names the
   compliance-alert family + W87 split warning. Cures F3/F6/F8 at the documentation layer.
2. **SHADOW stall flag** (F4): handed off to TRACK GUARDIANI with F1 (monitoring-plane
   surface); product-side variant available to the next Track A lane if declined.
3. **Corner-ledger hygiene rule** (F7): one line in each corner's operating rules — "the PR
   that opens a gate updates LIVE STATE in the same PR".
4. F1/F2/F4 fixes belong to TRACK GUARDIANI (registry rows, stall flag) and to Zero
   (retention policy) — handed off via this artifact, not built here.

## Adversarial review

Seat: **glm-5.2** (first-call, per the 2026-07-19 promotion; single-file agentic read +
4 bounded spot-checks it ran itself: intake greps 0/0 in registry+catalog confirmed, 8
intake plists confirmed, blob-retention 594/25,400 confirmed, G-a text read). 4 findings,
all re-probed on disk by the conductor before applying (W65):

1. **F3-as-drafted WRONG/OVERSTATED (most severe)** — "nothing tracks whether SHADOW
   accumulates" was contradicted by the draft's own citation: G-a IS the accumulation
   criterion (re-probed: SKILL.md:35-43). APPLIED: rewritten to the narrow, real claim
   (threshold gate ≠ stall alarm) and renumbered F4.
2. **Soft SCOPE-VIOLATION** — the draft handed F1's monitoring fix to TRACK GUARDIANI but
   kept F3's probe-in-digest for itself (same surface class). APPLIED: stall flag handed
   off to GUARDIANI alongside F1, product-side variant noted as fallback.
3. **F7 UNVERIFIED-NOT-FLAGGED** — "merged, gate open" claims rest on corner-file/git-log
   narrative, exactly the proxy class W88 warns about. APPLIED: W88 caveat added to both
   claims; re-verify content before building on them.
4. **RANKING** — the cross-corner consumer gaps embody the meta-pattern and outrank a
   single gate's stall-alarm nit. APPLIED: sections swapped (consumer gaps now F3).

Verified-clean by the reviewer: F1 (0/0 greps + 8 plists — solid), F2 (97.7% math checked),
F4c compliance cite (automation_catalog:178 portal-deadline-watchdog), no internal
contradiction between F1's "catalog empty for intake" and F4c's catalog cite (different
families). F5/F8 citations plausible, not re-verified within its budget — flagged as such.
