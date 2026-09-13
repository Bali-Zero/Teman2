# Astra round 5 — council delta (v6) → REWORK

Seat: codex `gpt-6-astra`, `model_reasoning_effort=xhigh`, `--sandbox read-only`, Pro, 2026-09-11 ~04:05–04:30 WITA. Bound to v6 sha256 `d8c56bad…`/`b745d4e1…`/`70e901d5…` (full digests below), against `origin/main = 6a17724545`. Verdict: REWORK — 25 BLOCKER, 26 MEDIUM, 27 MEDIUM, 28 LOW, all applied in v7. Verbatim final message (`codex exec -o`):

VERDICT: REWORK

25. **BLOCKER — B2.1(g) requires mutually exclusive candidate runs.**  
    **Evidence:** [B2-engine.md:48](/Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room-v6/research/operations/2026-09-11-bot-staff-room/B2-engine.md:48) requires mandatory negatives to cross the real finalizer “with substantive candidate text”, then requires unsupported cases never to reach it with substantive text. K3’s upstream approach preserves D4/D8 and finding 17; the combined acceptance instructions cannot both hold.  
    **Exact edit:** Replace the substantive-text mandate with: “Use two separately reported, frozen tracks: direct-finalizer characterization with substantive synthetic texts, preserving identical-input outcomes; and end-to-end candidate delivery through the actual upstream consumer, requiring unsupported cases to produce no generation and terminate as stub/handoff. Unsupported releases observed in characterization are documented vulnerabilities, never safety passes. Any unsupported substantive advice emitted by the end-to-end candidate fails acceptance, including cautioned advice.” Retain the grounded-cautioned positive control.

26. **MEDIUM — The new upstream mechanism lacks an explicit permitted terminal route.**  
    **Evidence:** [B2-engine.md:34](/Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room-v6/research/operations/2026-09-11-bot-staff-room/B2-engine.md:34) limits `wa_codex_leg.py` changes to `CodexLegResult` and completed-result construction. On inspected `origin/main` **6a1772454552**, a package marked unbuildable returns a fall-off reason at `wa_codex_leg.py:580-581`; the worker raises at `wa_outbox_worker.py:1026-1027` and enters its retry/failure ladder. Ordinary finalization occurs after generation at `wa_codex_leg.py:928-945`. Merely stopping package construction therefore does not implement the promised safe-abstention disposition.  
    **Exact edit:** Add an explicit B2.1 exception for a support-negative branch **before broker offer/generator invocation**, including the package-result contract it consumes. Require that branch to reach the unchanged finalizer’s safe-abstention handling using the sealed decision and unchanged score/context, then return the terminal stub/handoff through the existing worker fence. Require tests proving no broker offer, no generation, no generation-failure retry classification, and preserved D6 telemetry semantics. Clarify that this exception is distinct from B2.3b’s additive telemetry work.

27. **MEDIUM — The newly defined four bilingual pairs do not exist in the cited golden set.**  
    **Evidence:** [B1-design.md:58](/Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room-v6/research/operations/2026-09-11-bot-staff-room/B1-design.md:58) describes four existing EN/ID topic pairs. On `origin/main`, `test_evidence_cross_language.py:180-187` contains two Indonesian price questions, Indonesian NIB/OSS and capital questions, and English price/NIB/OSS/capital/duration questions. Registration duration has no Indonesian counterpart. B2.1(a) nevertheless requires all four topics in EN and ID.  
    **Exact edit:** Replace “the golden set’s four EN/ID topic pairs” with “four topic pairs constructed for the manifest from the golden questions, adding an independently reviewed synthetic Indonesian registration-duration counterpart before freeze”. Preserve both original Indonesian price questions and existing contexts; explicitly require each tagged topic in both query languages and both context languages.

28. **LOW — The new release citation points to a rejection.**  
    **Evidence:** README D8 and B2 Ground/Mechanism identify `wa_finalize.py:890` as the cautioned release. On `origin/main`, **890–894 returns `FinalizeOutcome.DEFECT`** following an egress veto. The cautioned `SEND` is **905–909**; the log at 896–898 is correctly cited. These locations are unchanged from base `bfb033a108`.  
    **Exact edit:** Replace every “release `:890`” with “release `:905-909`”, and extend the associated `:822-898` range to `:822-909`, including the disposition ledger. Qualify “releases any cautioned answer” with “subject to the unchanged text-cleaning and egress checks”.

```text
d8c56bad05391bd04b584c869af7c64f0e1c1787af31265b12b1a0137ff226aa  /Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room-v6/research/operations/2026-09-11-bot-staff-room/README.md
b745d4e125e486ff4c2d66e0419a6b57e041e5c373a569ce47a05b359aae5780  /Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room-v6/research/operations/2026-09-11-bot-staff-room/B1-design.md
70e901d5c7474f29a94a32c35c42373137b6d701e0c2bb15a98f9e505774886e  /Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room-v6/research/operations/2026-09-11-bot-staff-room/B2-engine.md
```
