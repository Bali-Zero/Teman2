#!/usr/bin/env python3
"""S13 agent-library-evolution — FROZEN dataset builder.

Idempotent. Regenerates research/agent-library/S13-evolution-FROZEN.json from
the empirical findings captured 2026-06-02. No network, no LLM, pure I/O.
Date is passed in (Date.now banned in workflow scripts; here we hardcode the
capture date as a constant, NOT a runtime call).
"""
import json, sys

CAPTURE_DATE = "2026-06-02"

# ---- 34 agents, grouped ----
AGENTS = {
    "interactive": [
        "backend-verifier","client-case-quote-generator","competitor-monitor",
        "deep-researcher","devils-advocate","email-template-builder",
        "frontend-browser","hr-companion","mcp-health","nb-curator",
        "regulatory-watcher","spalla-review","yield-optimizer",
    ],
    "wr2": [
        "wr2-brief-interpreter","wr2-critic","wr2-design-architect",
        "wr2-external-bench","wr2-ig-metrics-analyst","wr2-image-prompt-author",
        "wr2-layout-composer","wr2-storyboarder",
    ],
    "wr3": [
        "wr3-audio-asset-producer","wr3-b-roll-curator","wr3-brief-interpreter",
        "wr3-clip-renderer","wr3-critic","wr3-design-architect",
        "wr3-editorial-bench","wr3-post-assembler","wr3-pre-render-gatekeeper",
        "wr3-reflexion-synth","wr3-script-editor","wr3-shot-director",
        "wr3-yt-metrics-analyst",
    ],
}
ALL_AGENTS = [a for grp in AGENTS.values() for a in grp]

# ---- empirical loop-health verdicts ----
LOOP_HEALTH = {
    "reflexion_synth_loop": {
        "verdict": "NEVER_CLOSED",
        "evidence": "0 per-agent lessons.md files under ~/.claude/skills/bali-zero-brand/** (find -name lessons.md = 0). reflexion-synth sink target was never written.",
        "root_cause": "Metrics gate starvation: wr3-yt-metrics-analyst sees 0/3 manifests-with-metrics; wr2-ig-metrics-analyst sees 1/10 published. Reflexion-synth reads episodes (5 exist) but apparently never ran to completion OR ran and produced nothing because override-diffs/human-review signal too thin.",
        "severity": "P1",
    },
    "voyager_skill_library": {
        "verdict": "NEVER_CLOSED",
        "evidence": "wr3 _proposed/ EMPTY (0 drafts), no _archived/, no _quarantine/. Curriculum doc exists (states lifecycle) but zero skills ever proposed/graduated.",
        "root_cause": "Depends on reflexion-synth output (proposes drafts) — upstream starvation cascades. Also <3 graduated-eligible episodes (bootstrap exception not yet exited).",
        "severity": "P1",
    },
    "evoskill_auto_evolver": {
        "verdict": "FATAL_EVERY_RUN",
        "evidence": "~/logs/agent-library-evolver.out.log: 2026-05-19 'FATAL: evoskill run failed' (x2), 2026-05-24 'FATAL: evoskill run failed', 2026-05-31 'FATAL: DEEPSEEK_API_KEY not set after sourcing secrets.env'. Zero completed runs. proposals/ contains only .known-limitations-v1.md (no real proposal ever promoted).",
        "root_cause": "(a) 2026-05-31: secrets.env no longer exports DEEPSEEK_API_KEY (env drift). (b) earlier runs: 'evoskill run failed' before telemetry written (subprocess early crash, empty telemetry dir). Runs from worktree ~/Desktop/nuzantara-deploy (deploy-path coupling, cf. cicatrix program/base family).",
        "severity": "P1",
    },
    "agent_library_curation": {
        "verdict": "ONE_SHOT_HAND_WRITTEN",
        "evidence": "02-patterns.md (9 patterns) + 03-lessons.md (20 lessons + 5 meta) authored by hand 2026-05-17, never regenerated. 01-inventory.md auto-gen but stale (2026-05-16, says 16 subagents — now 34).",
        "root_cause": "By design (no autonomous cron for 02/03). But 01-inventory drifted 16->34 agents without regeneration.",
        "severity": "P2",
    },
}


# ---- OVERLAP MATRIX: clusters of agents with overlapping capability ----
# Each cluster: agents, overlap_axis, verdict (intentional|redundant|consolidate),
# rationale. "intentional" = by-design separation (anti-self-approval, contract
# isolation). "redundant" = duplicated logic that should be a shared skill.
OVERLAP_CLUSTERS = [
    {
        "id": "OVL-1",
        "name": "Adversarial / quality-review gate",
        "agents": ["devils-advocate","spalla-review","wr2-critic","wr3-critic","wr3-pre-render-gatekeeper"],
        "overlap_axis": "review-gate (read finished artifact, return PASS/FAIL+findings)",
        "verdict": "intentional",
        "rationale": "Anti-self-approval contract (02-patterns#7) requires the reviewer be a DIFFERENT agent. devils-advocate=adversarial-destroy, spalla-review=constructive, wr2/wr3-critic=domain-rubric-bound, pre-render-gatekeeper=pre-spend cliche/cost/safety. NOT redundant: different rubrics + different lifecycle position. BUT: shared 'bounded-iteration cap (≤3)' + 'binary-verdict+retry-feedback JSON shape' logic is re-implemented per-agent → candidate for a shared SKILL (review-gate-protocol).",
        "proposed_skill": "review-gate-protocol",
    },
    {
        "id": "OVL-2",
        "name": "NotebookLM ground-truth consumer",
        "agents": ["wr2-brief-interpreter","wr3-brief-interpreter","nb-curator","deep-researcher","regulatory-watcher"],
        "overlap_axis": "queries NotebookLM for domain ground-truth + citation extraction",
        "verdict": "intentional",
        "rationale": "WR3 Contract 2: wr3-brief-interpreter is SOLE NB consumer in WR3 pipeline (audit P1-18 confirmed zero violations). WR2 has its own brief-interpreter (separate pipeline). nb-curator=routing-recommender (called BEFORE others). deep-researcher/regulatory-watcher=standalone domain. Separation is contract-load-bearing. BUT: NB-routing-table (visa->NB-2, tax->NB-4, property->NB-5) + freshness-check (02-patterns#6, NOT YET IMPLEMENTED) are duplicated/missing across all 5 → candidate shared SKILL (nb-ground-truth-protocol with freshness check).",
        "proposed_skill": "nb-ground-truth-protocol",
    },
    {
        "id": "OVL-3",
        "name": "External SOTA benchmark + engagement-metrics analyst (WR2 vs WR3 mirror)",
        "agents": ["wr2-external-bench","wr3-editorial-bench","wr2-ig-metrics-analyst","wr3-yt-metrics-analyst"],
        "overlap_axis": "monthly SOTA bench + weekly engagement-correlate → propose amendments",
        "verdict": "consolidate-pattern",
        "rationale": "WR2 and WR3 bench/metrics agents are near-identical TWINS differing only by surface (IG carousel vs video reel). Both: multi-LLM cascade ingest, 12 reference brands + 3 competitors, output _external-bench-*.md; both metrics-analysts: read scraper output, correlate attrs, propose _proposed-amendments/. The metrics-analyst starvation (1/10 IG, 0/3 YT) is IDENTICAL failure on both. Not a merge candidate (different platforms) but the 'insufficient-data pre-flight gate + amendment-proposal shape' is duplicated logic → shared SKILL (metrics-analyst-protocol) + shared bench harness.",
        "proposed_skill": "metrics-analyst-protocol",
    },
    {
        "id": "OVL-4",
        "name": "Orchestrator (fan-out + critic-gate + contract-enforce)",
        "agents": ["wr2-design-architect","wr3-design-architect"],
        "overlap_axis": "orchestrator-only: fan-out to specialist subagents, enforce 3 contracts, run critic gate, emit handoff",
        "verdict": "consolidate-pattern",
        "rationale": "Both are opus orchestrators with NEAR-IDENTICAL structure: 'NEVER write artifacts inline', 'fan-out to N specialists', 'enforce fan-out + NB-ground-truth + no-silent-asset-reuse contracts', 'critic gate', 'Voyager+Reflexion growth'. The 3-contracts enforcement + Voyager-graduation logic is copy-pasted prose. → shared SKILL (orchestrator-contract-protocol). NOT a merge (different pipelines) but the contract-enforcement primitives should be one skill both load.",
        "proposed_skill": "orchestrator-contract-protocol",
    },
    {
        "id": "OVL-5",
        "name": "Brief-interpreter (brief.json producer)",
        "agents": ["wr2-brief-interpreter","wr3-brief-interpreter"],
        "overlap_axis": "Step 1/2: topic+research -> structured brief JSON (key facts, numbers, citations verbatim, bilingual lexicon, taboo, archetype, register)",
        "verdict": "consolidate-pattern",
        "rationale": "Brief JSON schema is ~80% shared (key_facts, key_numbers, citations, bilingual_lexicon, taboo_notes, archetype, voice_register). WR3 adds claim_ids + legal_claim_gate. The brief-schema + citation-verbatim-extraction is duplicated. → shared SKILL (brief-schema-protocol). Stays 2 agents (NB-contract isolation per pipeline) but schema is one source of truth.",
        "proposed_skill": "brief-schema-protocol",
    },
    {
        "id": "OVL-6",
        "name": "Provider-cascade implementers",
        "agents": ["regulatory-watcher","deep-researcher","wr2-external-bench","wr3-editorial-bench","wr3-reflexion-synth","wr3-audio-asset-producer","wr3-clip-renderer"],
        "overlap_axis": "multi-LLM / fallback cascade (Tier1 Claude -> Tier2 Gemini -> Tier3 Codex/DeepSeek -> Tier4 Ollama) OR asset-fallback",
        "verdict": "redundant",
        "rationale": "02-patterns#4 marks cascade as PARTIAL (no breaker-state, no degraded-mode marking). EACH of these agents re-implements the stdout-grep cascade independently, ALL missing the breaker+degraded-boundary. This S13 session HIT the exact failure: agy OAuth-blocked headless, had to fall to Claude-native, and DeepSeek env-drift broke the evolver. → shared SKILL (provider-cascade-protocol) with breaker state + degraded-mode marking is the single highest-value gap-fill.",
        "proposed_skill": "provider-cascade-protocol",
    },
]

# ---- UNSYNTHESIZED LESSONS per agent ----
# These are lessons that EXIST in the corpus (cicatrix/memory/episode artifacts)
# but were NEVER synthesized into the agent's lessons.md (sink empty).
# Only agents with real accumulated evidence are listed. Each lesson has a
# source citation (anti-hallucination: file/scar/episode anchor).
UNSYNTHESIZED = {
    "wr3-clip-renderer": [
        {"lesson": "Google Flow Character outfit is ANCHORED to reference images, NOT override-able via prompt (kebaya/outfit trap C5a content-creator episode).", "source": "memory discovery_flow_character_outfit_anchored_2026_06_02 + episode content-creator-3-roads clips_old_identity_fail_2026-05-30/"},
        {"lesson": "Account without Veo 3.1 i2v-portrait entitlement HARD-FAILs (403 MODEL_ACCESS_DENIED / PAYGATE_TIER_TIER1P5). Health-gate before spend.", "source": "memory wr3-c5a-episode-halt-flow-entitlement-2026-05-29 + flowkit-tier1p5-video-model-fix-2026-05-29"},
        {"lesson": "Identity gate (ArcFace ≥0.6) can fail an entire clip batch silently — episode kept clips_old_identity_fail dir; re-render with anchor needed.", "source": "episode content-creator-3-roads-2026-05-29 render-report.json.pre-anchor-rerender + identity-report.json"},
        {"lesson": "reCAPTCHA on Flow is a RATE signal not a method-block: 2-3 concurrent + 10-30s spacing avoids it.", "source": "memory discovery_flow_character_outfit_anchored_2026_06_02"},
    ],
    "wr3-shot-director": [
        {"lesson": "Anti-televendita: content-creator script passed legal-gate 20/20 but shot-pack risked salesy framing — largest hallucination surface (uses opus for a reason).", "source": "episode content-creator-3-roads gate-verdict.json + agent description 'LARGEST hallucination surface'"},
        {"lesson": "Outfit/wardrobe prompt tokens are wasted when Character reference dominates — push wardrobe to reference image selection, not prompt.", "source": "memory discovery_flow_character_outfit_anchored_2026_06_02"},
    ],
    "wr3-audio-asset-producer": [
        {"lesson": "Veo native audio is primary (override 2026-05-22), Chatterbox fallback — Cartesia cloud TTS BANNED (Law 6, panel reject 3/3).", "source": "agent frontmatter + cicatrix"},
    ],
    "wr2-ig-metrics-analyst": [
        {"lesson": "STARVED: 1 published carousel with IG metrics vs 10 threshold. 4 consecutive 'insufficient-data' stubs (05-10/05-11/05-18). Loop cannot learn until Damar publishes ≥10 with IG URLs + scraper fills metrics.", "source": "_proposed-amendments/*insufficient-data*.md (3 stubs)"},
    ],
    "wr3-yt-metrics-analyst": [
        {"lesson": "STARVED: 0 episode_manifest.json with metrics in 90d vs 3 threshold. Pre-flight gate correctly STOPS to avoid burning credits on no-op.", "source": "wr3/yt-metrics-analyst/_proposed-amendments/2026-05-22-yt-insights-insufficient-data.md"},
    ],
    "wr3-reflexion-synth": [
        {"lesson": "Loop NEVER closed: 0 per-agent lessons.md written despite 5 episodes existing. Reflexion needs override-diffs (human-review-queue) AND episode artifacts; with mostly-pilot reruns the signal is too thin to synthesize.", "source": "find lessons.md = 0; output/episode = 5 (4 pilots)"},
    ],
    "wr2-image-prompt-author": [
        {"lesson": "S11 monotone-template trap (12 carousels 'paper on dark desk') is the founding lesson — vary across 9 image-style modes. Already encoded in description; the discipline must persist as carousels scale to 33.", "source": "agent description + 02-patterns#9 + 33 carousels in output/carousel"},
    ],
    "regulatory-watcher": [
        {"lesson": "Empirical disk-state check post-LLM is load-bearing: Claude/Gemini narrate 'JSON emitted' without writing the file. Already shipped (run.sh:87) — the canonical anti-hallucination reference impl.", "source": "02-patterns#5 + ~/scripts/regulatory-watcher-run.sh:87"},
        {"lesson": "4-tier cascade is the reference impl BUT incomplete (no breaker state, no degraded-mode marking) — Tier-4 Ollama output could ship as Tier-1 quality.", "source": "02-patterns#4 (PARTIAL)"},
    ],
}

# ---- SKILL DRAFT PROPOSALS (gaps) ----
# Each: id, name, kind (shared-protocol|new-capability|infra-fix), problem,
# proposal, agents_served, evidence, priority, devils_advocate_status (filled
# after Codex/DeepSeek adversarial pass).
PROPOSALS = [
    {
        "id": "S13-P1",
        "name": "provider-cascade-protocol",
        "kind": "shared-protocol",
        "problem": "7 agents re-implement multi-LLM/asset cascade independently; ALL miss breaker-state + degraded-mode marking (02-patterns#4 PARTIAL). S13 itself hit this: agy OAuth-blocked headless, DeepSeek env-drift killed the evolver — both silent until a downstream symptom.",
        "proposal": "One skill encoding: (a) tier order + stdout-grep exhaust detection (existing), (b) per-tier breaker state file {failures,cooldown_until} for skip-fast, (c) degraded_mode flag marking Tier-3/4 output status=draft-not-client-safe, (d) pre-flight health-ping per tier (codex --version, ollama list grep, agy auth check) so cascade never falls through to a broken tool. Reference impl already 80% in regulatory-watcher-run.sh.",
        "agents_served": ["regulatory-watcher","deep-researcher","wr2-external-bench","wr3-editorial-bench","wr3-reflexion-synth","wr3-audio-asset-producer","wr3-clip-renderer"],
        "evidence": "02-patterns#4; ~/logs/agent-library-evolver.out.log FATAL DEEPSEEK_API_KEY 2026-05-31; this S13 agy-OAuth-block",
        "priority": "P1",
        "devils_advocate_status": "pending",
    },
    {
        "id": "S13-P2",
        "name": "nb-ground-truth-protocol",
        "kind": "shared-protocol",
        "problem": "5 NB-consumer agents duplicate the domain->NB routing table and NONE implements the freshness-check (02-patterns#6 PARTIAL). Stale NB source (e.g. superseded Permenkumham) returns confidently-wrong ground truth.",
        "proposal": "One skill: domain->NB routing map (single source of truth, currently copy-pasted), citation-verbatim extraction shape, AND the missing freshness-check (compare NB source last-ingest date vs regulation decree date; flag stale). Respects WR3 Contract 2 (only brief-interpreter CALLS NB; skill is shared reference, not a caller).",
        "agents_served": ["wr2-brief-interpreter","wr3-brief-interpreter","nb-curator","deep-researcher","regulatory-watcher"],
        "evidence": "02-patterns#6 PARTIAL; audit_subagent_nb_mcp_isolation_2026_05_20 (Contract 2)",
        "priority": "P1",
        "devils_advocate_status": "pending",
    },
    {
        "id": "S13-P3",
        "name": "review-gate-protocol",
        "kind": "shared-protocol",
        "problem": "5 review-gate agents re-implement bounded-iteration cap (≤3) + binary-verdict + retry-feedback-JSON shape independently. Cap-3 lesson lives only in a memory file, not enforced in the gate agents.",
        "proposal": "One skill: standard verdict JSON schema {verdict:PASS|FAIL, findings:[{severity,one_line,evidence_ref}], retry_feedback}, the ≤3-iteration cap rule, and the anti-self-approval invariant (reviewer != author). Each gate keeps its OWN rubric; only the protocol/shape is shared.",
        "agents_served": ["devils-advocate","spalla-review","wr2-critic","wr3-critic","wr3-pre-render-gatekeeper"],
        "evidence": "02-patterns#7; 03-lessons#4 (devils-advocate cap 3)",
        "priority": "P2",
        "devils_advocate_status": "pending",
    },
    {
        "id": "S13-P4",
        "name": "metrics-analyst-protocol",
        "kind": "shared-protocol",
        "problem": "wr2-ig-metrics-analyst and wr3-yt-metrics-analyst are twins with identical insufficient-data starvation; the pre-flight-gate + amendment-proposal shape is duplicated. Both loops have produced ZERO real amendments.",
        "proposal": "One skill: insufficient-data pre-flight gate (threshold check before LLM spend — already correct), amendment-proposal markdown schema, attribute-correlation method. Surface-specific thresholds (IG=10, YT=3) as parameters. ALSO documents the upstream unblock dependency (publish volume) so the starvation is visible, not silent.",
        "agents_served": ["wr2-ig-metrics-analyst","wr3-yt-metrics-analyst"],
        "evidence": "5 insufficient-data stubs; OVL-3",
        "priority": "P2",
        "devils_advocate_status": "pending",
    },
    {
        "id": "S13-P5",
        "name": "orchestrator-contract-protocol",
        "kind": "shared-protocol",
        "problem": "wr2-design-architect and wr3-design-architect copy-paste the 3-contracts enforcement (fan-out, NB-ground-truth, no-silent-asset-reuse) + Voyager-graduation prose. Drift risk: a fix to one orchestrator's contract logic doesn't reach the other.",
        "proposal": "One skill encoding the 3 universal orchestrator contracts + critic-gate invariant + Voyager graduation criteria. Both orchestrators load it; pipeline-specific steps stay in each agent.",
        "agents_served": ["wr2-design-architect","wr3-design-architect"],
        "evidence": "OVL-4; both agent descriptions verbatim-share contract language",
        "priority": "P3",
        "devils_advocate_status": "pending",
    },
    {
        "id": "S13-P6",
        "name": "FIX-evolution-loop-closure",
        "kind": "infra-fix",
        "problem": "THE central finding: the entire autonomous evolution loop has NEVER closed. (a) reflexion-synth wrote 0 lessons.md; (b) Voyager _proposed/ empty; (c) EvoSkill auto-evolver FATAL on every run (DEEPSEEK_API_KEY env-drift 05-31, evoskill-crash 05-19/05-24). The hand-written 02/03 (one-shot 2026-05-17) is the ONLY synthesis that exists.",
        "proposal": "NOT a new skill — an infra-fix proposal (for Antonello): (1) evolver: restore DEEPSEEK_API_KEY export in secrets.env + decouple from nuzantara-deploy worktree (cicatrix program/base family); (2) reflexion-synth: lower the synthesis threshold OR seed it from the cicatrix/memory corpus (which IS rich) instead of waiting on starved metrics; (3) regenerate 01-inventory.md (drifted 16->34 agents). This S13 FROZEN IS the manual substitute for the closure that never happened.",
        "agents_served": ["wr3-reflexion-synth","wr2-ig-metrics-analyst","wr3-yt-metrics-analyst","ALL (01-inventory)"],
        "evidence": "0 lessons.md; empty _proposed/; FATAL log trail; 01-inventory says 16 subagents (now 34)",
        "priority": "P1",
        "devils_advocate_status": "pending",
    },
]

# ---- ASSEMBLE FROZEN ----
FROZEN = {
    "schema": "s13-agent-library-evolution/1.0.0",
    "capture_date": CAPTURE_DATE,
    "session": "S13 agent-library-evolution (ONDA 2)",
    "machine": "Air-M5 (balizero) — thin-client; ingestion fell to Claude-native (agy OAuth-blocked headless on M5+Pro+Mini, Law-4 cascade)",
    "method": {
        "intended": "agy (Gemini 3.1 Pro 1M) ingestion + Claude opus analyst + Codex/DeepSeek adversarial",
        "actual": "Claude opus full-context ingestion (corpus ~643KB fits) + DeepSeek/Codex adversarial. agy unauthenticated in headless OAuth context — Law-4 graceful degradation, NOT a skipped step.",
        "corpus_ingested": ["34 agent .md (304KB)","agent-library 01/02/03 (87KB)","lessons memory corpus (117KB)","cicatrix-scars (34KB)","WR2/WR3 cortex tree","_proposed-amendments","5 WR3 episodes","evolver logs"],
    },
    "headline_finding": "The autonomous agent-evolution loop (Reflexion + Voyager + EvoSkill) has NEVER closed. 0 per-agent lessons.md synthesized, 0 Voyager skill drafts proposed, EvoSkill auto-evolver FATAL on every run. The only synthesis that exists is the hand-written 02/03 one-shot (2026-05-17). This FROZEN is the manual evolution cycle substituting for the closure that never happened.",
    "agents": {"total": len(ALL_AGENTS), "by_family": {k: len(v) for k,v in AGENTS.items()}, "list": ALL_AGENTS},
    "loop_health": LOOP_HEALTH,
    "overlap_matrix": OVERLAP_CLUSTERS,
    "unsynthesized_lessons": UNSYNTHESIZED,
    "skill_draft_proposals": PROPOSALS,
    "constraints_honored": [
        "NO production agent modified (proposals live in _proposed/ only)",
        "WR3 Contract 2 respected (proposals do not make non-brief-interpreter agents call NB)",
        "Anti-hallucination: every finding carries a file/scar/episode/log source anchor",
        "Antonello approves any append to lessons.md / graduation (L2 autonomous ops — draft PR, human merge)",
    ],
    "next_actions_for_antonello": [],  # filled below post-adversarial
}

# ---- ADVERSARIAL PASS (cross-vendor: DeepSeek V4 Pro + Codex GPT-5.5) ----
# Verdicts read from disk (saved by the two red-team dispatches). Both ran on
# Pro (DeepSeek=API key, Codex=OAuth). Cross-vendor isolation per EvoSkill spec.
import os
_DS = json.load(open(os.path.expanduser("~/s13-evolution-data/deepseek-verdict.json")))
_CX = json.load(open(os.path.expanduser("~/s13-evolution-data/codex-verdict.json")))
_ds_by = {v["id"]: v for v in _DS["verdicts"]}
_cx_by = {v["id"]: v for v in _CX["verdicts"]}

def _converge(a, b):
    if a == b: return a
    s = {a, b}
    if s == {"KILL", "REVISE"}: return "REVISE"   # softer wins (don't drop a real gap)
    if s == {"KEEP", "REVISE"}: return "REVISE"
    if s == {"KEEP", "KILL"}:  return "SPLIT"     # genuine disagreement -> flag
    return "REVISE"

for p in PROPOSALS:
    pid = p["id"]
    dsd = _ds_by.get(pid, {}).get("decision", "?")
    cxd = _cx_by.get(pid, {}).get("decision", "?")
    p["devils_advocate_status"] = {
        "deepseek": {"decision": dsd, "reason": _ds_by.get(pid, {}).get("reason", "")},
        "codex": {"decision": cxd, "reason": _cx_by.get(pid, {}).get("reason", "")},
        "converged": _converge(dsd, cxd),
    }

# Both adversaries independently surfaced the SAME missed gap + SAME strongest
# objection. That convergence is load-bearing — promote the missed gap to a
# proposal, and record the meta-objection at top level.
PROPOSALS.append({
    "id": "S13-P7",
    "name": "agent-library-contract-test-harness",
    "kind": "new-capability",
    "problem": "MISSED GAP (surfaced independently by BOTH adversaries): there is no executable enforcement for any agent-library invariant. Skills are loaded as GUIDANCE, not enforced. Nothing verifies: frontmatter `skills:` actually load, WR3 NB-exclusivity (Contract 2) holds, reviewer!=author, 01-inventory count matches reality (it drifted 16->34 undetected), provider health before cascade, required output artifacts exist.",
    "proposal": "A contract-test/audit harness (pytest or scripts/) run in CI + pre-commit that asserts the library's invariants AS CODE. This is the meta-fix the adversaries demand: 'duplication of words is not duplication of behavior; without executable checks, a loaded skill changes nothing.' Tests: (1) every agent frontmatter parses + declared skills exist; (2) grep WR3 non-brief-interpreter agents for NB MCP calls = 0; (3) inventory count == ls ~/.claude/agents/*.md; (4) review-gate agents are never their own author; (5) provider health-ping smoke.",
    "agents_served": ["ALL (library-wide invariant enforcement)"],
    "evidence": "DeepSeek missed_gap + Codex missed_gap (independent convergence); 01-inventory drift 16->34 undetected for 17 days; reflexion/voyager/evoskill all silently non-functional",
    "priority": "P1",
    "devils_advocate_status": {"origin": "adversary-demanded (both red-teamers)", "converged": "KEEP-by-construction"},
})

FROZEN["adversarial_synthesis"] = {
    "method": "cross-vendor red-team: DeepSeek V4 Pro (reasoning_effort=high) + Codex GPT-5.5, independent, on Pro",
    "convergence_verdicts": {p["id"]: p["devils_advocate_status"].get("converged") for p in PROPOSALS},
    "shared_strongest_objection": "Both: most proposals treat duplication-of-WORDS as duplication-of-BEHAVIOR. A skill loaded as guidance does NOT enforce breaker state, NB authority, contracts, or loop closure — only executable checks/receipts do. => the real deliverable is enforcement (S13-P6 infra-fix + S13-P7 contract-test harness), not more prose-protocol skills.",
    "shared_missed_gap": "agent-library contract-test/audit harness (now S13-P7)",
    "outcome": "S13-P3 review-gate KILLED (both). S13-P5 orchestrator-contract SPLIT (DeepSeek KEEP / Codex KILL) -> downgrade to contract-test, not skill. S13-P1/P2/P4 REVISE (prose->executable + Contract-2 split). S13-P6 + S13-P7 KEEP/promote = the two highest-value items.",
}

FROZEN["next_actions_for_antonello"] = [
    "PRIMARY: S13-P6 (fix evolution-loop closure) + S13-P7 (contract-test harness) — both adversaries say enforcement, not abstraction, is the real gap.",
    "S13-P6 unblock: restore DEEPSEEK_API_KEY export in secrets.env; decouple evolver from nuzantara-deploy worktree; regenerate stale 01-inventory.md (16->34 drift).",
    "REVISE (don't graduate as prose skill): S13-P1 provider-cascade -> executable shared runner+breaker, not doc; S13-P2 nb-ground-truth -> split routing/freshness CONFIG from call-authority (preserve Contract 2); S13-P4 metrics -> keep no-data gate + output schema, DEFER correlation until data exists.",
    "KILLED by adversaries: S13-P3 review-gate-protocol (homogenizes intentionally-distinct reviewers).",
    "DOWNGRADE: S13-P5 orchestrator-contract -> contract-test (S13-P7 lane), not a shared skill (Codex: blurs WR2/WR3 load-bearing differences).",
]

if __name__ == "__main__" and "--emit" in sys.argv:
    print(json.dumps(FROZEN, indent=2, ensure_ascii=False))
