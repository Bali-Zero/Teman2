# LANE E — Zantara WA bot: cycle 359 root causes → cycle 360 on real delivery

**Machine:** Pro (the runtime lives here: outbox, codex daemon, WA sessions; real-thread batteries
with Damar). One interactive seat, no fan-out — Pro is saturated. **Corner:**
`.agents/skills/bot/SKILL.md` §1 LIVE STATE (2026-09-01, cycle 359). **Contract:** `README.md` here.

Cycle 359 was the first battery measured on real delivery: 22 questions, 8 FAIL / 5 SUSPECT.
Four root causes, not eight symptoms. Re-measure `wa_outbox.generation_route` before anything —
generation runs on **codex**, the S4 "Gemini" bullets in the corner are stale.

## E1 — The corpus teaches the price split (data, no code)

- Delete Qdrant `curated_qa` points `57deb254-c2d7-530e-9321-a51f6ad80e1a` and
  `59da08d9-39c5-5373-8928-fbcf6833b319` (orphans: their source file never existed in the repo).
  Review `8b520434`, `eacec21f`, `8ebf681f` under the single-price ruling (2026-07-17, re-ruled
  2026-09-01: one all-inclusive price — if the corpus says otherwise, the corpus is rewritten).
- Find the harvester that would regenerate them and add the FACT-scan (any government-fee token,
  44/808 points) as a pre-ingest gate; fix `training-data/visa/visa_011_notebooklm_session2.md:123`.
- Prove: the Investor KITAS price question on the real thread answers one price.

## E2 — GREETING falls off a cliff (`query_planner.py:263` maps to `[]`)

- A bare "halo" took 7m45s and answered an English error stub. Deterministic scripted
  greeting + capability turn (Dialogflow/Rasa practice) — no LLM, no retrieval, in the client's
  language. Guilt test: "halo", "hi", "ciao", "привет".

## E3 — The abstain gate is blind across languages (spec #5504 → code)

- #5504 is the spec; `wa_package_builder.py` scored evidence from vector chunks alone while it
  already held the correct price (cured, but the abstain is not cleared by design). Implement the
  spec: language-independent evidence scoring, guilt+innocence corpus in ID/EN/IT/RU.

## E4 — The citation rule has no exit (`zantara_core.py:314`) — Zero applies

- The file is off-limits to sessions. Draft the exact replacement paragraph (a licit "no citation
  when no statute applies" path; operational questions cite nothing) into `ZERO-DECISIONS.md`
  item 3 with the two cycle-359 evidence lines (PP 36/2021 on wages; immigration law for "no
  passport over WhatsApp"). Do not edit the file.

## E5 — PR #5337 split-fee veto: SUSPENDED, redesign before any code

- Measured 11/11 vetoed — nine compliant one-price answers and both genuine splits. Three rounds
  spent. Build the corpus from the cycle-359 thread first (compliant × 9, guilty × 2, plus 10
  synthetic), then a detector that scores innocence and guilt; ship only with both numbers.

## E6 — Cycle 360

- After E1-E3: re-run the 22-question battery on real delivery with Damar (thread 30), stratified
  on the 993-conversation ranking. Panel: session + Codex sol xhigh + Gemini; probe Kimi first —
  if 403, say "2 seats". Capture in the corner as cycle 360 with the same table shape as 359.
- Remaining client-facing surfaces still handing out the bot's INBOUND number (11 found 2026-09-01;
  #5486, #5494 cured two): finish the list.

## Guards

- No client PII in outputs, logs, packs, or the corner. Identity-document text never as a CLI
  argument (ledger 2026-08-30: it lands in the process table).
- The evidence pack for each PR carries the measured battery numbers, never a narration.

## LIVE STATE (update before ending the session)

- 2026-09-03: cycle 359 FAIL stands; E1-E6 not started; E4 waits for Zero.
