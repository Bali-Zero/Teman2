---
name: visaoracle
description: "Corner for Visa Oracle v2 — the immigration Decision Tree rebuild (Bali Zero flagship). Load FIRST on any Visa Oracle / visa funnel work."
---

## Notes (moved from description 2026-09-02)

Holds: live state, established truths, research log, loop protocol.

Split 2026-09-09 (context budget — this file was 145 KB/1,689 lines, and being a mandatory
corner skill it exhausted a Codex session's context before work started): the LIVE STATE
chronology and the two superseded snapshots moved into `.agents/skills/visaoracle/references/` —
`live-state-log.md` (full dated log), `CURRENT_STATE.md` (2026-08-15 archaeology snapshot),
`HANDOFF-2026-08-08-voa-conclusive-rate.md` (2026-08-08 diagnosis writeup). This file is now an
index; read `references/live-state-log.md` before claiming a track.

# VISA ORACLE v2 — Decision Tree (corner /visaoracle)

> **CURRENT HANDOFF (read first):** read **LIVE STATE — CURRENT POSITION** below FIRST — it is
> the current summary, refreshed on every state change. Full chronology:
> `.agents/skills/visaoracle/references/live-state-log.md` (read the newest entries before
> claiming a track). `references/CURRENT_STATE.md` is a SUPERSEDED 2026-08-15 snapshot (reviewed
> SHAs, gate matrix, evidence, safe resume sequence as of that date) kept as archaeology; many
> pack activations have shipped since it was last touched.

## Mission

Rebuild the Visa Oracle immigration funnel as Bali Zero's flagship public tool: an interactive
decision tree guiding foreigners to the correct Indonesian visa/stay-permit path. Bar: (a) stunning
interactive aesthetics ("immediatezza estetica"), (b) simple, impeccable content — zero wrong
answers, (c) authoritative enough to demo to Ditjen Imigrasi Jakarta, (d) a true expat guide.
Mandate: Zero, 2026-07-17. Working mode: multi-LLM deep-research ↔ brainstorm loop (unlimited
rounds), all work in worktree `mouth-visa-oracle` until final draft for operator analysis. This is
Subhi's surface (`apps/mouth`) — verification per CLAUDE.md §13 (CI + AI review, generator≠grader).

## ENFORCE-GATE (canonical ruling as of 2026-08-08 — NO-GO / SHADOW)

**The 2026-08-08 Zero ruling supersedes the 2026-07-19 gate proposal.** There
is no automated traffic-volume threshold for ENFORCE: no 1,000 sessions/7d,
no 100 real sessions/14d fallback and no Wilson lower-bound test. Organic
traffic measurements remain useful diagnostic evidence, but they neither
authorize nor mechanically block the mode change. The business-validation
gate is Bali Zero team heavy-testing and verification against the engine in
SHADOW. See
`research/visa/2026-08-08-decision-tree-v2-full-index-design.md` §4.

ENFORCE remains a distinct, explicit Zero-gated action. A session must not
infer pre-authorization from operational checks, a RulePack activation,
traffic counts or this skill. It must keep `VISA_ENGINE_EVALUATE_MODE=SHADOW`
until all of the following are true:

- the Bali Zero team has completed heavy manual SHADOW testing and signed off
  the observed outcomes;
- the current gold-persona replay has zero unexplained divergences;
- current decisions carry valid, in-force citations and no ungrounded claims;
- the kill switch has a current, independently reproducible rollback proof —
  **SATISFIED 2026-08-23**, see LIVE STATE below and
  `research/visa/2026-08-23-killswitch-rollback-proof.md` (this bullet alone; the other six are
  untouched and this does not authorize ENFORCE);
- the DPIA is complete, signed and its residual privacy risks are accepted;
- the real analytics destination/provider is identified and a fresh,
  closed-schema **365-day (12-month)** TTL proof has been independently
  reproduced (corrected 2026-08-23 — Zero's 2026-08-20 retention ruling,
  DPIA V2 §A, superseded the old 90-day provisional; §8 signed 2026-08-23,
  `docs/audits/2026-08-20-visa-oracle-dpia-v2.md`; still unsatisfiable
  today — the destination itself remains unidentified, see LIVE STATE
  below); and
- Zero explicitly authorizes the ENFORCE flip after the preceding blockers
  close.

**Current status: 🟢 ENFORCE IN PRODUCTION since 2026-09-06T01:1xZ — OWNER
OVERRIDE.** Zero flipped `VISA_ENGINE_EVALUATE_MODE=ENFORCE` on Fly
(`nuzantara-rag`) by his own explicit instruction ("accendi tutto",
2026-09-06, after being told the DPIA v2 §8 text still reads "DO NOT
ENFORCE" with two High residual risks open — analytics destination,
cross-border processor register — and that gold-persona divergences were
not re-measured on seq-19). The seven preconditions below remain the
documented standard; the ones still open are now RESIDUAL RISKS to close
in production, not blockers. Rollback is one command:
`fly secrets set VISA_ENGINE_EVALUATE_MODE=SHADOW -a nuzantara-rag`.

Traffic provenance must stay explicit while evidence is collected. Only
requests deliberately labelled `traffic_source=real` are organic evidence;
synthetic lanes stay separate and legacy/NULL rows are not silently promoted
to real traffic. This classification is diagnostic under the current ruling,
not an automated ENFORCE threshold.

## Established truths (GROUND 2026-07-17, scout-verified file:line)

- **v1 is LIVE, not missing** — www.balizero.com/visa, last touched 2026-07-14, 29 commits/90d.
  "Rebuild" = experience + content layer, NOT greenfield.
- Frontend: `apps/mouth/src/app/visa/` — entry branch-selector ("Already in Indonesia?") →
  `/visa/clock` (expiry countdown, 133 lines) | `/visa/match` (4-step wizard:
  nationality→purpose→duration→budget, 315 lines); decision tree logic in
  `apps/mouth/src/lib/visa-oracle/quiz-logic.ts` (84 lines, 7 purposes); AI chat layer
  `apps/mouth/src/components/visa/VisaChat.tsx` (341 lines → `/visa-oracle/chat`); shareable hash
  result URLs; Playwright E2E `apps/mouth/e2e/visa-funnel-fusion.spec.ts`.
- Shared funnel framework: `packages/core/` (`@balizero/core`) — AppFrame / AppWizard /
  AppBranchSelector / useFunnelApp — proven across visa + property-eligibility + tax-calendar.
  REUSE-FIRST candidate #1.
- Also reusable: `apps/mouth/src/components/blog/interactive/DecisionTree.tsx` (553 lines, generic
  tree primitive).
- Backend (FastAPI, all registered in `router_registration.py`): `routers/visa_check.py` (346 l.,
  `/api/visa`: clock+match), `routers/visa_oracle.py` (928 l., `/visa-oracle`:
  recommend/chat/handoff/visa-types), `routers/knowledge_visa.py` (CRUD catalog, backs MCP
  list_visa_types/get_visa_details); services `visa_check/match_tree.py` (the real tree logic),
  `visa_oracle/visa_oracle_service.py` (471 l., scoring), `visa_unified/bridge.py`. Full pytest
  coverage exists.
- Data: `migrations_v2/124_visa_checks.sql` (visa_checks table, hash URLs); seed
  `seed_visa_types_complete_2026.py` = **114 visa codes** (A1→F4, incl. E28A investor, E33A-G
  digital-nomad/retirement family) — the canonical catalog; Qdrant `visa_oracle` collection ~90
  curated points.
- Paper trail: `docs/plans/2026-04-19-4apps/01-visa-check.md` (the executed v1 spec);
  `docs/superpowers/plans/2026-04-04-visa-oracle-implementation.md` + specs;
  `2026-04-21-visa-funnel-fusion.md` (PR #165); `2026-04-21-visa-catalogue-rebuild.md`. Unexplored:
  `apps/mouth/src/app/(assessment)/`, `apps/kb/data/immigration`.
- Unrealized vision from memory: "3D FUNNELS: Waypoint 1.5 (Overworld)" (2026-04-12) — candidate
  inspiration for v2 metaphor.

## Arsenal & seat status (probed live 2026-07-17)

- Gemini 3.1 Pro (High) via `agy` v1.1.3 — ARMED. GOTCHA: flag order changed vs v1.0 — use
  `agy --print-timeout 15m --model "Gemini 3.1 Pro (High)" -p "<prompt>"`; the old
  `agy -p --print-timeout 5m` feeds the FLAGS as prompt (RC=0, garbage out).
- Codex GPT-5.6-sol ultra — ARMED (PONG).
- GLM 5.2 via TP1 seat `tp1-glm-5.2` (OpenAI-compatible base `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`, key loaded by `load_tp1_settings_key()` from `~/.qwen/settings.json`) — ARMED (PONG). TP1 seats are roster lines, not CLIs.
- DeepSeek V4 — **DEAD** (balance -0.04 USD, is_available:false). Operator-only top-up. Declared
  substitute: house Sonnet web-grounded lane (live WebSearch, URL-verified).
- Harness scar (2026-07-17): Agent spawns WITH `name:` can be born dead (mailbox never delivered) —
  spawn anonymous for fan-out.

## Loop protocol (the pallegiamento)

Round N = 4-lane parallel deep research (Gemini width / Codex architecture+red-team / GLM design /
web-grounded verification) → orchestrator reports ALL content faithfully to Zero → brainstorm →
interesting points spawn round N+1 research. No round limit. Opus 5.5 orchestrates only (no hands,
hook-enforced — RULED 2026-08-20: Fable is out of the workflow, CLAUDE.md §5); Sonnet implements; research outputs persisted under `research/visa/` in the worktree
as `2026-07-17-visa-oracle-v2-round<N>-<lane>.md`.

## LIVE STATE — CURRENT POSITION (updated 2026-10-14; update on every state change)

- **2026-10-14 (newest): E33 wave 3 merged, live proof partial, on top of waves 1-2** (waves 1-2: #8437, #8439, #8440, #8441, #8454, #8456, proven live 2026-10-13). Wave 3, all merged 2026-10-14: #8466 prices (55+, selling exception, income or allowance) `7c9184772a` (served chunk read, no walker); #8467 PR-20 "What this permit does not allow" `ac8a106930` (mouth promoted); #8468 llms.txt work clause `a14ee32144` (EN proven live, **ID not proven**, open row); #8469 visa_check catalogue E33/E33G notes `7391929b46`; #8493 PR-8 documentation catalogue `55edebae5b` (all seven catalogued E33 codes AVAILABLE, E33F seen in the browser walk, E33E and E33B AVAILABLE in the synthetic-driver probe, E33/E33A/E33C/E33G not seen live, out-of-catalogue codes UNKNOWN; Zero confirmed audit decision 19); #8494 PR-7 v2 permit length `3d2c743a48` (supersedes #8485; E33F 1 year, E33 5 years; iQOO not run). Zero decisions 2026-10-14: /book retirement card is the E33F row; E33F price rows add the penjamin note; legacy /api/visa/match stays and is corrected; agy-gemini-4-argon on the council reserve bench; generic Retirement rows hidden from public surfaces but kept in the backend catalogue; 'E33F everywhere' (Zantara/WhatsApp, team pricing tools); decision 19 confirmed.
- Merged earlier on 2026-10-14 and previously listed as in flight: #8459 replay freshness test `bd45ad8e33` (observer 4 passed on a fresh worktree) and #8460 income-or-allowance wording `098b7f8025` (promoted `dpl_61kkyURVnGyudqXmenFcmmqT2fP3`, headless replay).
- **In flight, not merged:** catalogue-decisions, zantara-e33f, brochure-prices (the public brochure prints E33E Offshore Rp 14.000.000 vs canonical 45.000.000), stay-invariants, pr10 (E33F card deposit note), vo-copy, tree-invest. **Open (PENDING-ARMS, opened 2026-10-14):** E33 pages re-read before 2027-10-13, runtime staleness check in `documentation_for`, the ID surfaces of 8468, three PR-20 C4 items for seq-30, council seats (Kimi weekly quota, TP1 403), iQOO not attached to Pro since 2026-09-26. The zero runner disk-full incident manual cure is complete; durable fix pending in the infra/healer lane. Detail: `references/live-state-log.md`.
- **2026-10-13 position (production pack seq-29 since 2026-10-13T11:19:00Z; boundary 2026-11-14T00:07:47Z, organ alert T-7 = 2026-11-07).**
  Activation `84e8a5c5-55eb-4649-8dc4-f620c9f9b00b` (rule_pack_id `ed666554-c476-5e67-9c25-921388e64537`, payload
  `3f3b45ed1aaeadc72ec9dd2a5e33519ded3a0ec1da8408fade150a0ae39b9295`, 117 rules, PR #8433, merge `2bf9ed3c93`
  at 2026-10-13T10:46:12Z; signed on M5 by nuzantara-57, `signed_at 2026-10-13T08:56:32Z`; two-login ceremony from
  Pro, dry then apply, roles 0; seq-28 activation `b7c808bd` closed 11:18:58Z). Content: the 2026-10-13 organ re-stamp +
  E31J under 18 and never married + E31D Indonesian sponsor + E28F foreign branch or subsidiary + E31E parent scope.
  Proof-of-armed 13/13 PASS (https://github.com/Bali-Zero/Teman2/pull/8433#issuecomment-6144652983, issuecomment-6144652983):
  sentinel `OK pack 29`, `/evaluate` sequence 29, gold 18/20 (known personas 9 and 10), one open activation. The #8390
  post-organ observation is closed (the suite stayed green after the newer ledger landed). **Next: seq-30 from the
  conductor** (A1 on-shore conversion, E30A/E30B multi-year; branch `agent/nuzantara/backend-rag/vo-seq30-a1-e30-material`),
  signed by the session before 2026-11-07; open PENDING-ARMS row for the seq-29 boundary. Detail: `references/live-state-log.md`.
- **SUPERSEDED by seq-29 (history), 2026-10-12 position (production pack seq-28 since 2026-10-12T03:08Z; boundary 2026-11-12T18:00:16Z, organ alert T-7 = 2026-11-05).**
  Activation `b7c808bd-c0f4-48fe-9fdb-3f7f47f7e86a` (rule_pack_id `b383effb-eea4-5890-9a6a-0f13d816e855`, PR #8300,
  merge `7bb50d079e`; signed on M5 by nuzantara-57, `signed_at 2026-10-11T22:53:04Z`, kid `prod-2026-07-1`; two-login
  ceremony from Pro, roles 0; seq-27 activation `471bddfa` closed). Content: the 2026-10-11 organ re-stamp (organ PR
  #8289, reproduced byte-for-byte, closed superseded) + E33E "E33E Second Home Senior (5 Years)" IDR 45,000,000 +
  AGE_BELOW_55 scoped to RETIREMENT + E33G income gate `work.annual_foreign_income_usd >= 60000`
  (`hf.e33g.annual-income-below-minimum`, `E33G_INCOME_BELOW_THRESHOLD`); 114 rules. Proven live 2026-10-12: sentinel
  `OK pack_sequence 28` 03:09:58Z, `/evaluate` sequence 28 03:10:54Z, E33E quote, AGE_BELOW_55 on retirement 54 only,
  remote 85000 -> E33G / 59999 -> E33G_INCOME_BELOW_THRESHOLD / unknown -> NEEDS_INPUT, headless walks EN/ID, live gold
  18/20 (only 9 and 10, known), one open PRODUCTION activation (PR #8300 comment issuecomment-6117354289). Step B
  (#8280, `2630e98c70`) and the why-copy (#8287, `fdce3f78dd`) are live since 2026-10-11. **TRACK C stays claimed
  (M5 nuzantara-57).** Next: seq-29 candidate (38-visa night program, conductor on Pro `~/visa-night`; unsigned, chained
  to seq-28) before 2026-11-05; test-hygiene follow-ups F1-F3 from #8287's gate; audit PRs PR-7/PR-4 (post-seq-28),
  PR-10, PR-14, PR-15, PR-18, PR-19/20, PR-16; the 13 batch-2 owner decisions. Detail: `references/live-state-log.md`.
- **SUPERSEDED by seq-29 (history):** **seq-29 is to be signed and activated by the session itself (Zero, 2026-10-12)**, process unchanged (red team, two-titolare council, fresh Opus gate, ceremony, proof-of-armed). The 38-visa night program's seq-29 candidate does not exist yet: Pro has been offline on Tailscale since about 11:10Z 2026-10-12, so the night conductor is halted. F1-F3 closed by #8385 (`bc35468022`).
- **SUPERSEDED by seq-29 (history, observation closed 2026-10-13):** **The seq-28 pack tests are pinned to `research/visa/2026-10-11-organ-reattest-seq28` (#8390, `d00c73dd48`)**; open PENDING-ARMS row: observe main after the organ's 2026-10-18T18:00Z ledger lands (visa_engine suite still green).
- **SUPERSEDED by seq-28 (history), 2026-10-11 position (E33 / retirement program; production pack then seq-27, boundary 2026-11-09T13:21:22Z).**
  Census (scratch, read-only): interview space 1.1x10^14 combinations (exact DAG count); 256 covering walks =
  186 SUPPORTED / 57 NO_SUPPORTED_PATH / 9 HUMAN_REVIEW / 4 NEEDS_INPUT, 0 errors; offline replay == live 256/256.
  Correctness is proven only where expectations exist: scenario corpus 116/116 (129 after #8258), gold 20/20.
  E33 audit (90-agent swarm, 61 confirmed findings, 5 HIGH, 20-PR plan, 22 owner decisions); batch 1 decided by Zero
  2026-10-11: ONE seq-28 signing with the E33 content fixes + the freshness re-stamp before 2026-11-05; E33G real
  income gate (interview question on annual foreign-employment income + rule excluding < USD 60,000/yr, stating the
  figure); retirement under 55 gets a notice right after the tile WITH "Continue"; E33A/B/C "price on consultation",
  never an invented price. Batch 2 decisions still open (documents checklist, onshore prices, property route/Hak Pakai,
  dependants, deposit commitment timing, 55-59 caveat E33F, E33B/E33C scope, single timeline, F7 article mislabelling,
  E33D note, extension/10-year model). LIVE today, each proven on production: #8246 (`033772cbdc`) dead end with no
  open door no longer promises one; #8256 (`c4d6ff4005`) Second Home deposit not at a state bank / not own name has its
  own reason; #8258 (`17c363faaa`) 13 age-64 retirement walks + per-sequence census pins; #8259 (`666926365c`) E33/E33E
  price rows no longer say "non-working" (E33F rows deliberately unchanged). In flight: #8265 (retirement reasons name
  USD 3,000/month and USD 50,000; merge queue), #8266 (E33-family copy; armed), R3 (drop the sponsor question from
  retirement; ship pipeline), R2 (retirement_age_notice, RETIREMENT_MIN_AGE=55 pinned to the pack; waits for R3), seq-28
  step A (engine accepts work.annual_foreign_income_usd, default NOT_ASKED). seq-28 chain: A engine fact -> B mouth
  question + E33G_INCOME_BELOW_THRESHOLD copy (only after A is live) -> C fold on top of the weekly organ's re-stamp
  candidate (E33E pricing_key -> "E33E Second Home Senior (5 Years)" 45M; AGE_BELOW_55 scoped to RETIREMENT; E33G
  gte 60000 rule; re-derive gold personas 1/3/4) -> D fingerprint check, adversarial seat, two-titolare council, sign on
  M5, two-login activation from Pro. Proof = sentinel `OK pack_sequence 28` + `/evaluate` sequence 28; target ~2026-10-19/20;
  activation needs B live. Fallback (needs Zero): if content is not ready by 11-05, sign the plain re-stamp as seq-28 and
  move content to seq-29. Regulation check: Permenimipas 3/2025 Pasal 45 revokes only Pasal 43, 45, 52-55 of Permenkumham
  22/2023 (spouse/child-of-WNI, ex-WNI); E33 articles 56-63 stay (incl. 63(2) USD 60,000/yr); pack copies byte-identical;
  no citation change for seq-28 (peraturan.go.id listing unverified, site unreachable; follow-up: any E31 rule resting on
  Pasal 43/45). **Ops note:** the M5 main checkout was 146 commits behind origin/main on 2026-10-11 and
  `.claude/skills/visaoracle` is a symlink into it, so M5 sessions read a stale corner skill until it is fast-forwarded
  (owner action). Detail: `references/live-state-log.md`.
- **SUPERSEDED by seq-28 (history): seq-27 since 2026-10-10T05:23Z (activation `471bddfa-0423-4fa1-b11f-2d9617615a19`,
  PR #8209, merge `2478b87561`; successor of #8204; supersedes organ candidate #8105).** seq-26 with only the 18
  `OFFICIAL_PORTAL` stamps moved to `2026-10-08T13:21:22Z` by the weekly organ; rules, products and prices
  byte-identical. Signed on M5 (kid `prod-2026-07-1`, `signed_at 2026-10-10T03:42:26Z`, payload
  `a9098744e0cd8369fb4fe9ca5bef851705cf43dabb1c69398b63b36985cb42d0`, chained to seq-26). The 18 judgements
  are `judge: fingerprint` (no model read the pages); checked by an independent adversarial seat (live re-read,
  18/18 identical) and a council (codex-gpt-5.6-sol + kimi-code/k3, PASS). **Boundary now 2026-11-09T13:21:22Z**
  (APPROACHING from 2026-11-07T13:21:23Z). Prove-live: sentinel tick 05:23:44Z `OK, pack_sequence 27`;
  `/evaluate` (synthetic_driver) 05:25:27Z `sequence=27 rule_pack_id b0fd0791…`. Open: seq-28 before the new
  boundary (`PENDING-ARMS.md`).
- **Client copy, 2026-10-10:** the Copy/Share summary carries the typical processing time, marked indicative,
  no dates (#8207, live 05:00:30Z: "… IDR 15,000,000 · 2-year stay permit · Typically 7–10 working days
  (indicative)"); 46 never-rendered interview keys deleted EN+ID (#8205, live 04:43:15Z: 0 of 33 chunks carry
  them); the freshness sentinel's holiday-coverage lane (#8206) alerts the owner 60 days before the working-day
  estimate runs out of loaded decrees (today `OK first_gap=2027-11-19 year_to_load=2028`, real tick 05:23:44Z).
  Later the same day: the shared summary keeps the price for candidates without duration options (#8218, live
  08:25Z: "B1 — Visa on Arrival — Tourism (B1): IDR 750,000 · Typically within 1 working day (indicative)");
  an i18n dead-key census guards the dictionary (#8233: 102 unrendered keys frozen, the 46 deleted ones
  tombstoned); the holiday lane keeps naming the gap day and escalates a blind probe after 4 ticks (#8221).
- **SUPERSEDED by seq-27 (history): seq-26 since 2026-10-08T10:08:02Z (activation `1c7ac00b-7c5e-44e9-8efc-392d03fb47ef`, PR #8081,
  merge `f43d4ac0a0`).** E31A–J now offer 1 or 2 years as a duration option on the same
  product: 365 maps to the existing key, 730 to the "2 Years" sibling, one all-inclusive price
  per option, never PNBP (Zero's ruling 2026-10-08); `stay_policy FIXED_DAYS 365..730`. Signed on
  M5, kid `prod-2026-07-1`, `signed_at 2026-10-08T08:58:04Z`, payload
  `05511184caf05119ac0adf644601e322d845c276faad3146ea243c507cf23b7f`, chained to seq-25.
  Stamps unchanged: **boundary stays 2026-11-08T13:32:18Z**. Organ `pro.visa_reattestation`
  (#8075, weekly Monday 02:00 WITA on Pro) armed 2026-10-08T10:11:50Z (bootstrap + kickstart on Pro); sentinel v2 (#8064) re-alerts a
  persistent STALE inside 24 h. Prove-live: sentinel `OK pack 26 (stale 0, approaching 0)`, gold replay `18/20 live on seq-26, unexplained {9, 10} only, HUMAN_REVIEW_REQUIRED 0`.
  Open: seq-27 before the boundary, personas 9/10 ruling (`.claude/skills/modus/PENDING-ARMS.md`).
- **Result-page copy (PR-C1 #8102, merge `11f47173a0`):** the client no longer sees internal
  wording. Zero's own test (2026-10-08) exposed the price subtitle "One number — no PNBP-vs-fee
  split, ever." and a "Timeline unavailable" block, because the backend always emits
  `processing_timeline.status = UNKNOWN` (`evaluate_path.py:993`). Copy EN+ID is rewritten per
  outcome state, `nextStepsFor(state, {studioOnly})` drives the steps, the timeline shows a
  pending paragraph. Guard: census test `_lib/client-copy.test.ts` and CI observer
  `scripts/ci/observe_visa_oracle_client_copy.py`. Mouth merge lands STAGED: `vercel promote`
  is the deploy. Prove-live: Vercel production build `mouth-fe7se9ybt` of commit 11f4717 went live at 13:10Z on its own (should-build judges against the live commit; no promote was needed); headless replay of Zero's scenario on https://balizero.com/visa-oracle at 2026-10-08T13:25:49Z: Supported, E31B, 'Timeline' → 'Processing times are set by Ditjen Imigrasi and vary by office and season. Your Bali Zero advisor confirms the calendar for your case before you book travel.', under the price 'Government fees and Bali Zero service included.', 'What to do next' = Keep this summary / Send it to a Bali Zero advisor on WhatsApp / Book travel only once the timing is confirmed, the new disclaimer, no '01/01' counter, zero banned strings in the page text (artefacts result-20261008T132549Z.{txt,pdf,png} in the session scratchpad). Follow-ups C2, C3, C4 in the next bullet.
- **Result page, C2 and C3 live (2026-10-09), C4 in gate:** PR-C2 #8124 (`06c3346702`, merged
  03:22Z) shows the priced stay-permit length under the price ("2-year stay permit", "Also
  available: 1 year — IDR 11,000,000"), live 03:31Z with no promote. PR-C3 #8129 (`1d5a508366`,
  merged 04:33Z, Fly batch head `68b70014a3`) shows "Typically 7–10 working days" plus an
  indicative calendar window, from the committed snapshot
  `backend/data/bali_zero_processing_times_2026.json` (production
  `visa_types.processing_time_normal`, 37 products); BRIDGING stays UNKNOWN. Census unchanged on
  seq-26: 99 SUPPORTED / 13 NO_PATH / 1 NEEDS_INPUT / 3 HUMAN_REVIEW of 116 walks. C4 interview
  helper copy: successor PR-C4 #8148 merged 2026-10-09T06:27:43Z (`4443d209f1`). Vercel dpl `mouth-jounkfl8j` was aliased about 06:34Z by an automatic promotion, a few minutes after READY. Live 06:34:46Z: on balizero.com/visa-oracle, "Why we ask" on the direction question reads "Your direction decides which questions come next and which visas can fit your plan." and the old "only chooses the next questions" is gone; the full replay still shows the C3 timing and the C2 duration. Predecessors #8119, #8128, #8140 and #8145 were closed after fresh-gate BLOCKs on false sentences, a lost "above" reference, and a red suite. The fix was a per-key truth table written from the code, a Codex full sweep of every changed key (97 rendered + 17 never rendered of 114/115), and the full visa-oracle vitest subtree before push. Rule now in force: an advisor is offered, never promised. Open items: `PENDING-ARMS.md` rows 2026-10-09.
- **Organ hardening (PR-O2 #8100, merge `fa15d34f7e`):** the first real run halted on a judge
  false positive (page dcf08e19, fingerprint `d760e4e8371f04cd…` equal to the seq-25 text). The
  fold now re-proves against a judgement-bound fingerprint baseline and downgrades
  `changed`-on-identical to `none`; each run's ledger is kept under
  `~/.local/state/nuzantara/visa-reattestation/ledgers/` (8 kept). Kickstart result:
  second real run 2026-10-08T12:46:36Z→12:47:06Z on Pro (post-#8100): `fingerprint: 18 of 18 pages identical to their attested read — judged without a model`, judge skipped, ledger kept at `~/.local/state/nuzantara/visa-reattestation/ledgers/20261008T124704Z-seq26` (18 `judge: fingerprint` rows); the fold then refused on a latent guard: `created_at '2026-10-08T12:47:00Z' precedes the ledger's latest evidence 2026-10-08T12:47:02Z` — `fold_pack_generic.py:440` truncates the default created_at to the minute (pre-existing), exposed by the fingerprint speed; PR-O3 in flight. Two LOW notes open in `PENDING-ARMS.md`. Third run (13:21Z, post-#8104) folded OK; seq-27 candidate = organ PR #8105: a signing session reviews the attestation note, signs on M5, runs the ceremony, merges — before 2026-11-08T13:32:18Z (the candidate's own boundary moves to ~2026-11-09).
- **SUPERSEDED by seq-26 (history): seq-25 (activated 2026-10-07T13:49Z from M5, PR #8026, merge
  `2a1e00e0d3`).** The 18 `OFFICIAL_PORTAL` stamps of seq-23 went STALE on 2026-10-01T13:18Z
  and every product answered `HUMAN_REVIEW_REQUIRED` with an empty candidate list for six days
  (scar W141: the sentinel fired into a 401-dead Telegram token, then sat muted on the dedup
  ladder). Cure: a two-login ceremony activated seq-24 (`e1e01743…`, owner-signed 2026-09-27,
  never activated) and then seq-25 (`d2752a16…`, payload `603f777e…9d11`, kid
  `prod-2026-07-1`). seq-25 = seq-24 + the 18 portal stamps re-derived from a read ledger
  written DURING the reading (`research/visa/2026-10-07-freshness-restamp-seq25/`, tool
  `portal_read_receipt.py`, fold `fold_pack_seq25.py`); rules and products byte-identical.
  `verified_at 2026-10-07T13:32:18Z` → **next freshness boundary 2026-11-08T13:32:18Z**: a
  seq-26 re-stamp must be signed and activated before it, and the lane is still a session act,
  not an organ (`.claude/skills/modus/PENDING-ARMS.md`, row 2026-10-07). Proven live: sentinel
  on Pro `OK pack 25 stale 0`; gold replay live 20/20 HTTP 200, `HUMAN_REVIEW_REQUIRED 0`,
  live == offline on every persona (the 3 divergences on personas 1/9/10 are pre-existing
  gold-corpus drift). Every seq-20/seq-22 bullet below is history. Attestation:
  `research/visa/2026-10-07-freshness-restamp-seq25-attestation.md`.
- **This entry was stale by construction, not wrong-by-lying** (VISA-ORACLE-DW-20260919 PLAN
  §1.1): the seq-20 bullet immediately below was last updated 2026-09-11; seq-22 landed
  2026-09-16 (`44b9b36d32`, PR #6675, "land the signed seq-22 bundle, v3") and is now the
  **highest SIGNED production pack on disk** — measured this session via slice A0's own
  `load_highest_signed_pack()`: `rulepack-prod-022.signed.json`, version `2026.9.16`,
  `rule_pack_id 916915d8-1c58-508d-aff7-742a3c012df7`. **What PROD actually serves is
  UNVERIFIED FROM THIS SEAT**, two independent attempts, both inconclusive: (1)
  `curl -s https://nuzantara-rag.fly.dev/api/visa-oracle/rule-pack` → `401`; (2)
  `probe_evaluate.py --full-body` against `/api/visa-oracle/evaluate` with the provisioned
  `~/.config/nuzantara/visa-signing/driver-token` (synthetic auth) passed the auth gate but the
  strict route rejected the current-schema `ApplicantFacts` payload with a sanitized `422`
  (41 `missing` + 56 `extra_forbidden` field errors, `loc` deliberately redacted to a generic
  `"field"` by `_sanitized_validation_detail` in `app/routers/visa_oracle_evaluate.py` — by
  design, not a bug, so this probe cannot see which fields diverged). A third route,
  `scripts/pg.sh` against `visa_ruleset_activations`, was blocked because the `fly` CLI had no
  access token in this session (`fly proxy` → "no access token available… flyctl auth login") —
  a login/credential act reserved for the human, not attempted further. **Do not plan a pack
  change (A8/A9) until a future session closes this with a fresh probe or an authenticated
  `fly`/`pg.sh` session.**
- **Slice A0 landed**: `apps/backend-rag/backend/scripts/visa_engine/review_hold_inventory.py`
  derives every `HUMAN_REVIEW` producer from the signed pack AST plus the backend adapters —
  the missing PR-O1 keystone (PLAN §1.7). Measured against seq-22: **9** pack
  `HUMAN_REVIEW`-stage rules, **7** `on_unknown=HUMAN_REVIEW` escalations (3 overlapping the 9
  plus 4 HARD_FILTER-only), **11** disclosed review flags, **1** engine-level minor-privacy
  hold — **25 total distinct hold producers**, matching PLAN §1.3's hand count exactly. Also
  reports the 3 orphan `REVIEW_GATE_ITEMS` (`overstay`, `blacklist`,
  `immigration_investigation`) `tree.ts` offers a visitor that `fact-mapper.ts`'s
  `REVIEW_FLAG_MAP` silently drops — unresolved, slice A3's job.
- **Active production pack (per this bullet's own last verification, 2026-09-11): seq-20**, version `2026.9.6`, `rule_pack_id ac0a792d-a38d-512e-9ead-54a5d008fb68`,
  109 rules, signed on M5 (`sign_pack.py`, kid `prod-2026-07-1`, `signed_at 2026-09-06T14:59:27Z`)
  and activated (`activation_id e08ebea9-d50f-48a6-989e-b7e4698f96ad`). Prod answers
  `sequence=20 version=2026.9.6`, re-proven by synthetic API + public-browser probes on
  2026-09-11 (Mini). The **21 dead ends / 22 answers over 43 walks is historical**. **Superseded
  by the seq-22-on-disk finding above — this number is no longer re-provable from this seat.**
- **Fresh walk census (2026-09-11, 67 scenarios, current repo + signed seq-20, offline):**
  without disclosure flags, **55 SUPPORTED / 10 NO_SUPPORTED_PATH / 2 NEEDS_INPUT**;
  with the actual frontend flags, **31 SUPPORTED / 7 NO_SUPPORTED_PATH / 29 HUMAN_REVIEW**.
  Same results at the pack's signing instant and the current clock. This is a synthetic
  sample, not organic traffic or exhaustive answer-combination coverage.
- **Review explanations reach the public UI, but coverage is incomplete:** 13/29 sampled
  reviews have a `REVIEW_REASON_COPY` entry; 16/29 use the generic fallback (ambiguous sponsor).
  `DISCLOSED_UNCERTAINTY_REVIEW` also uses that fallback, proven on the public site.
  The existing test admits 25 unmapped codes and misses three additional, reproduced
  `BRIDGING_*` review codes from `on_unknown=HUMAN_REVIEW` hard filters. A fourth omitted
  code (`VOA_NATIONALITY_ONLY`) is structurally eligible but not witnessed by this probe.
  Full audit, evidence, reproducible scripts and proposed success bar:
  `research/visa/2026-09-11-review-reason-audit/README.md`. Audit only; no runtime/copy changes.
- **Evaluate mode: ENGINE, under ENFORCE since 2026-09-06T01:1xZ** — OWNER OVERRIDE by Zero
  ("accendi tutto"), not a session-inferred authorization. Visitors of `/visa-oracle` now see
  real verdicts (SHADOW previously withheld every decision).
- **GARUDA VOA public funnel is LIVE** at `/visa/voa` (`GARUDA_PUBLIC_ENABLED=true` on both the
  Fly backend and the Vercel `mouth` Production env).
- **Rollback commands:**
  - evaluate mode: `fly secrets set VISA_ENGINE_EVALUATE_MODE=SHADOW -a nuzantara-rag`
  - VOA public: `vercel env rm GARUDA_PUBLIC_ENABLED production` + redeploy/promote
- **Open residual risks** (documented ENFORCE preconditions, now open in production not
  blockers): DPIA v2 two High rows (analytics destination, cross-border processor register)
  still unclosed; gold-persona replay not re-measured on seq-20; Bali Zero team manual sign-off
  still outstanding.
- **TRACK C claimed by mini-pro2/2026-09-11 — W-ORACLE window (SHWEB-20260911).** Binding spec:
  `research/visa/2026-09-11-oracle-final-window-spec.md` (v6.2). Chain, one PR each from fresh
  main: PR-O0 docs (this capture) → PR-O1 census with real disclosure flags + AST-derived
  review-code inventory → PR-O2 dedicated EN/ID copy for every known review code → PR-O3
  interview Δ1 (`family_sponsor_confirmed` on retirement/property + undecided) → PR-O4
  review-cause explanation Δ2 + neutral contact fallback. Owner decisions D1/D5/D6 recorded on
  the Mini desk 2026-09-11. Released in PR-O4.
- **TRACK C claimed by air-m5/2026-10-11 — E33/retirement program (audit 2026-10-11, owner decisions 1-4); released when the seq-28 chain and R2 land.**

Full chronology: `references/live-state-log.md` (read the newest entries before claiming a track).

## TRACKS — parallel work groups (multi-session coordination)

The v2 program runs as separate tracks, one per surface, coordinated ONLY through this skill. Any
session on any machine: load /visaoracle → read LIVE STATE → claim a free track → work exclusively
inside that track's path scope. Scopes are disjoint by construction, so parallel tracks cannot
merge-conflict.

| Track               | Path scope (exclusive)                                | Home machine | Dependencies                                                                                                                                                                          |
| ------------------- | ----------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Engine**      | `apps/backend-rag/backend/services/visa_engine/**`    | M5           | Serial chain: PR1 → PR2 (signing) → PR3 (evaluator) → PR4-6. Never parallelize within the chain.                                                                                      |
| **B — Content**     | `research/visa/**` (later curated kb via its own PRs) | Mini         | Bridging Visa branch, D7A/D7B + diaspora gap research: free NOW. The 7 interview categories: only AFTER PR #2602 (catalog bonifica) merges.                                           |
| **C — Experience**  | `apps/mouth/**` visa-oracle surfaces                  | Pro          | Prototypes/design-system with mock data: free NOW. Wiring to the real engine contract: only AFTER PR1 merges (schemas in `apps/backend-rag/backend/services/visa_engine/contracts/`). |
| **D — Ditjen demo** | (defined later)                                       | —            | Blocked until green gold-harness.                                                                                                                                                     |

**Claim protocol**

1. A track with an open `TRACK <X> claimed by …` line in LIVE STATE is TAKEN — pick another or coordinate.
2. Claiming = adding `TRACK <X> claimed by <machine>/<date>` to LIVE STATE in your track's FIRST PR; release it in the PR that closes the track.
3. Every PR from a track updates its own LIVE STATE lines (standing rule: whoever changes state updates this file).

**Quality invariants (identical for every track — parallelism never relaxes them)**

- Own worktree via `scripts/agent_start.py`; the main checkout stays read-only.
- generator≠grader before every push: cross-family adversarial review (Codex or Gemini seat) of the track's diff; the author never grades its own work.
- Final on-disk gate = an Opus 5.5 xhigh-effort session per track (RULED 2026-08-20, was Fable — CLAUDE.md §5); never delegated to the implementer.
- Pre-push runs on the track's own machine (3 machines = 3 independent push queues). On M5: quiet-window rule — first loadavg value < 8 and zero real pytest processes before pushing.
- All established truths in this skill bind every track — including the single all-inclusive client price ruling (never a PNBP-vs-fee split).

## PENDING (W81 ledger, project-scoped)

- SEAT-DEEPSEEK: DeepSeek V4 balance -0.04 USD (probed live 2026-07-17) — panel runs 3-external-seat and house web lane, DECLARED degraded. Arming step: operator
  top-up (Zero). Proof-of-armed: 1-token live probe HTTP 200 with is_available:true.
- R2-BROWSER-LANE deferred: 403-blocked gov wizards (IRCC / Australia / US Visa Wizard) +
  evisa.imigrasi.go.id SPA + Awwwards pixel-study need claude-in-chrome browser automation — run in
  an attended session.
- WORKTREE-REBASE: branch is behind origin/main (2+ commits at last check) — rebase before the final
  draft PR.
- DEEPSEEK-BURN-ATTRIBUTION: fleet key consumed ~$48.75/30d (~1,100 req/day bursts; $10 top-up of
  2026-07-15 burned in 48h). Eliminated: instrumented scripts (ledger=pennies), Fly backend
  (llm_cost_events=0 rows), CI, OpenClaw config, intel pipeline, devils-advocate. Hunt agent
  dispatched (leads: cognitive oracle, war-room-v2, healer, mata-garuda). Do NOT top up until
  attributed.
