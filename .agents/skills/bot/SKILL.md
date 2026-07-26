---
name: bot
description: "Zantara WA bot corner — the live shared context for ALL work on the Zantara WhatsApp Meta bot (+62 821-3465-159): outbox/inbox pipeline, agentic RAG brain, answer cache, model routing, prompt chain, team check-in program. Load BEFORE touching any WA-bot code or data, or when Zero says /bot, 'zantara wa', 'il bot', 'meta inbox', 'cache risposte'. Holds: established truths (verified, with method), Zero's rulings, LIVE STATE of the ship chain, blood-bought operating rules."
---

# /bot — Zantara WA Meta bot corner

> Created 2026-07-17 on Zero's order ("il tuo lavoro deve essere focalizzato su zantara Wa Meta").
> This file is the HOT CONTEXT shared by every session working on the bot. It states what is
> PROVEN, what is DECIDED, and what is IN FLIGHT. **Update §1 LIVE STATE whenever it changes —
> this corner is only useful if it stays true.**

## 0. The product (what all of this serves)

WhatsApp Business (Meta Cloud API) number **+62 821-3465-159** = Zantara. Two audiences, one number:

- **Clients**: a perfect consultant on immigration / tax / company / license / real-estate legal.
  Grounded answers with citations, abstains instead of inventing, prices ONLY from PricingTool,
  ONE all-inclusive client-facing price (never PNBP-vs-fee splits — Zero ruling 2026-07-17).
- **Bali Zero team**: work-support assistant. Check-in via WA (opens the free Meta 24h window),
  CRM nudges, PII-light briefings. Persona = "assistente operativo interno", not sales.

## 1. LIVE STATE (last update 2026-07-27 — keep current)

- **🚫 DO NOT RE-OPEN: coalescing of a RETRYING outbox row is sound (REFUTED 2026-07-27).**
  The suspicion was that `_coalesce_thread_bursts` kills a customer question that is only
  waiting for its retry — its predicate filters `status='pending'` but not `attempts` or
  `next_retry_at`. Measured instead of argued: **9 rows** ever carried
  `error='superseded_by_coalescing'`; **7** had `attempts=0` (the intended burst case) and only
  **2** were killed mid-backoff (outbox 161 on 07-19, 182 on 07-25). Both threads were answered
  right after — 161→row 162 `done` at +49s, 182→183/184 `done` at +83s/+126s — and
  `wa_inbox_bot._load_thread_context` keeps the superseded question in the model's context: it
  loads `_HISTORY_TURNS + 1 = 13` messages and demotes the question from "the query" to a `user`
  turn. Coalescing also RESETS the attempt budget (the successor starts at `attempts=0`), which
  is better for the client than draining the victim's remaining attempts.
  **Probe gotcha that cost an hour**: an earlier pass concluded "0 successful sends afterwards"
  by counting `status='sent'`. This table only ever writes **`failed`** and **`done`** (verified
  by `GROUP BY` over all 184 rows) — the zero was the wrong question, not an absence.
  Residual, logged not fixed: the superseded question is answered as context rather than as the
  question, so a reply may address a nudge ("ci sei?") instead of the substantive ask. Bounded by
  the 12-turn window, unobserved in prod.

- **🗣️ IN FLIGHT — PR #3260 (abstain voice + per-sender WA memory).** Two client-facing gaps:
  (a) the refusal copy now names the stake, says a Bali Zero colleague must look at it, and asks
  for a document or a reference date — and it deliberately does NOT promise "a colleague will
  reply here", because nothing notifies a human today (`wa_outbox.apology_sent_at` /
  `ack_sent_at` are **0-for-184 rows** since 2026-06-02); RUSSIAN + UKRAINIAN added to all four
  stub keys, because `detect_query_language` emits ten values, the table carried three, and
  `get_localized_stub` degrades to ENGLISH _silently_. (b) W-1 follow-up to P0-MEM #3036:
  `derive_wa_memory_subject` keys long-term memory per sender as `wa:<32 hex>` — **HMAC**, not a
  bare hash (a phone number has almost no entropy), trust taken from the dedicated
  `X-WA-Bot-Profile-Key` and never from a body field, its OWN salt (rotating it is a memory
  WIPE), fail-closed to today's containment when unset. Near-miss caught while wiring: gating the
  read on the new subject alone would have handed every WA client the shared bucket's PROFILE and
  HISTORY — FACTS and PROFILE/HISTORY now gate independently.

- **⚙️ IN FLIGHT — PR #3261**: `security.yml` cancels superseded PR runs, never on main (it owns
  4 of the 25 required checks). Honest limit recorded in the PR: `cancel-in-progress: false`
  protects only a run that has already STARTED — a QUEUED run is superseded regardless.

- **⚠️ COORDINATION: check main by CONTENT before building a bot-adjacent fix.** On 2026-07-27
  three separate lanes independently built the same `<Money>` mock fix, and one branch was one
  push away from DELETING a sibling's already-merged guard. Root cause measured: the pre-push
  allowlist sends frontend-only diffs through the full backend suite, so the machine ran 6
  concurrent pushes at load 33 — see memory
  `discovery_the_prepush_allowlist_is_how_the_fleet_saturates_itself_2026_07_27`.

- **🗣️ CLIENT VOICE: persona + greeting SHIPPED & PROVEN LIVE; deny narration NOT YET (2026-07-26).**
  Three things landed and were verified INSIDE the running container (`flyctl ssh` pinned to
  `--machine 1781e5eda03438`; the machine is picked at RANDOM without it), never from a merge status.
  - **`ZANTARA_PROMPT_VERSION=v5` ARMED in Fly secrets** (was `v4`) — the audience-composed prompt
    is now the live one. Container-verified: `PROMPT_VERSION_ACTIVE=v5`, `crm_query` present in the
    team/creator builds (37063/37483 chars) and **absent from client** (36258) — the C20 asymmetry
    is real in prod, not just in tests. Wiring confirmed deployed: `audience_derived=1`,
    `get_master_template(audience)`×3, `skipping legacy persona prepend`×1.
  - **Persona leak CURED + proven.** The pre-arm answer told a client _"so we can get this over to
    the client"_; post-arm the same probe passes. This was inert until the secret flip — the deploy
    alone would not have done it.
  - **Greeting by the founder's codename CURED + proven (PR #3182).** An anonymous caller was
    getting _"Salut Zero, …"_. NOT a memory bleed — ruled out by measurement: `memory_facts`,
    `episodic_memories` and `collective_memories` all returned **0 rows** for that user id.
    v4's `GREETING_RULES` hardcodes the name in all four worked flows while rule 1 of the SAME block
    correctly says `[Name]`. Now name-neutralized for ALL audiences via fail-loud
    `GREETING_NAME_NEUTRALIZATIONS`; container-verified 4 → **0** name-greetings, `[Name]` = 6.
  - **Deny narration: #3170 had NO measurable effect. Corrected 2026-07-27 — the earlier
    "suggestive, p≈0.08" line in this corner was wrong and is retracted.** TWO post-fix runs of
    N=10 existed (03:05Z and 04:12Z, same content-verified container); the first write-up pooled
    only the more favourable one. Honest tally, anonymous caller asking _"Quanti clienti attivi
    abbiamo?"_:

    |                                          | pre-fix (N=5) | post A (N=10) | post B (N=10) | pooled post | Fisher p |
    | ---------------------------------------- | ------------- | ------------- | ------------- | ----------- | -------- |
    | `sources` clean — server-side tourniquet | 5/5           | 10/10         | 10/10         | **20/20**   | —        |
    | tool-name / auth-model / credential leak | 0/5           | 0/10          | 0/10          | **0/20**    | —        |
    | names the CRM                            | 3/5           | 5/10          | 3/10          | 8/20 (40%)  | **0.62** |
    | promises to obtain the count             | 4/5           | 6/10          | 3/10          | 9/20 (45%)  | **0.32** |
    | says "database"                          | 1/5           | 3/10          | 3/10          | 6/20 (30%)  | 1.00     |

    **No data leaks in any run** — the server-side layer holds 100%, and that is the part that
    matters. But the narration is statistically unchanged. The two post-fix runs are mutually
    consistent (p=0.65 / 0.37), so pooling them is legitimate; discarding one was not.
    Method scar: not a single sample this time, a _selected_ sample — see
    `lesson_four_of_my_own_probes_lied_in_four_different_ways_2026_07_27`.

    **Why the prompt fix could not work, discovered 2026-07-27:** at least one narration channel
    is not in the prompt at all. When the verifier scores a draft < 0.7, `reasoning.py` injects
    the retry instruction as a **user turn**, and the model answers it — _"Message reçu pour les
    corrections de conformité factuelle"_, _"Capisco, mi scuso per l'errore precedente"_,
    _"Terima kasih atas koreksinya"_, _"Got it. Let's correct this…"_ — client-facing, in four
    languages. No edit to `zantara_core_v5` can reach that path. Fixed at the injection site by
    `build_rephrase_prompt()` + explicit OUTPUT RULES (gag scoped to the META layer only; "admit
    it if the context is insufficient" is preserved and pinned by innocence tests).

- **📏 METHOD — two traps this campaign paid for, do not repeat:**
  - **A single sample is not a baseline.** An "8/8 pass" under v4 vs "5/8" under v5 nearly got
    reported as a regression; N=5 showed the surface is nondeterministic. Compare TALLIES.
  - **Needle census beats intuition.** `numero esatto` appears **0** times in the prompt and leaked
    **4/5**; `database` appears **8** times and leaked **1/5**. Frequency does not predict leakage,
    which is how the priming theory was refuted and the real licensor found. See memory
    `lesson_the_load_bearing_rule_is_not_the_named_rule_2026_07_26`.

- **🇫🇷 ONE QUESTION NEVER ANSWERS CORRECTLY — and it is a NO-COVERAGE failure, not a language one
  (reframed by measurement 2026-07-27; the 2026-07-26 "symptom of a retrieval miss" framing was
  half right and is superseded).** _"My KITAS extension was rejected last week and immigration did
  not explain why."_ → **11/12 answered in FRENCH, 1/12 dumped the raw KG scaffold. Zero correct
  answers in 12 live runs.** The "English" run was not an English answer — it was the internal
  block. Language was labelling two ways of failing, not success vs failure.
  - **The correlation the old plan asked for is untestable**: `evidence_score` was **0.850 in all
    16 runs** across two unrelated questions. It has no variance (see the abstain-gate bullet).
  - **Ruled out BY MEASUREMENT, each one**: self-correction (fires, but the drift appears without
    it) · memory contamination (three fresh `user_id`s drifted 3/3; and `memory_facts` has had zero
    writes since 2026-07-24 for anyone) · the composed prompt (no French in any of the three
    audience templates, container-read) · the KG (0 French rows of 119,732) · the language detector
    (all patterns score 0 on this sentence → falls through to the `"en"` default) · French in the
    corpus (0/8 chunks, read server-side) · Italian density of the evidence (the arm that answers
    ENGLISH 4/4 is _more_ Italian, 13.1% vs 12.7% — hypothesis refuted by its own pre-registered
    prediction) · a generic no-coverage fallback (a DIFFERENT uncovered English question answers
    in English 2/2).
  - **It is specific to English on this query.** Same question in Italian → Italian; in
    Indonesian → Indonesian; prefixing _"Reply in English."_ does **not** win. A different
    uncovered English question → English.
  - **The structural defect, which IS actionable:** retrieval returns E31B/E28A/E31H/E33A/E32A
    (family / investor / ex-citizen visas) for a rejected-extension question — nothing on point —
    and when a trusted tool has run, `evidence_score` is pinned at 0.85 regardless of relevance, so
    the abstain gate cannot catch it and the model confabulates instead of admitting the gap.
    **Fix the blind spot (below) and the KB coverage; the exact reason one string attracts French
    is the least actionable part.**
  - **Retracted trends** (each read from ≤5 points, then falsified): "context_length grows
    monotonically"; "ctx=16 → scaffold dump".
  - GOTCHA that cost real time: this drift silently broke an unrelated probe — an escalation check
    with English-only markers reported `0/3` while the answers _did_ escalate, in French. **Any
    assertion on generated text must be language-agnostic.**

- **🚨 THE ABSTAIN GATE IS BLIND TO A SUCCESSFUL-BUT-WRONG RETRIEVAL (2026-07-27).** Read the scope
  carefully — an earlier draft of this entry said "unreachable / nothing ever reaches them" and that
  was **WRONG**, falsified the same night by a live WhatsApp message: the gate DID fire,
  `abstain_reason='no_relevant_context'`, which only happens at `evidence_score < 0.05`.
  - **What is true.** `_reasoning_evidence.py::compute_evidence_score` returns the constant 0.85
    whenever `trusted_tools_used`, **without looking at the sources at all**; otherwise it falls
    through to a keyword score. So the gate sees a real number when retrieval FAILS, and a
    flattering constant when retrieval SUCCEEDS — including when it succeeds at fetching entirely
    off-topic documents. **The blind spot is the successful-but-irrelevant retrieval**, which is
    exactly the 12/12-wrong KITAS case.
  - **Ordering matters and is easy to misread**: the score is computed at `reasoning.py:559` with
    the PRE-flipper flag; `apply_shared_trusted_flippers` (`:594`) then sets
    `trusted_tools_used=True` merely because `detect_llm_has_tools()` is true — that predicate tests
    only that the gateway **has tools configured**, not that one ran. The GENERATION gate
    (`should_apply_low_evidence_policy`) is bypassed on that post-flipper flag, so it is far weaker
    than the LABEL gate in `orchestrator_response.py`, which reads the score itself.
  - **Measured both ways, same endpoint**: 16/16 synthetic runs → 0.850, `abstain=False`; one real
    WA request on the same question → `< 0.05`, abstained. Same code, different luck in the ReAct
    loop. **So do not call `evidence_score` a constant — call it a number that stops being
    informative the moment a tool succeeds.**
  - **Do NOT lower the 0.85 constant** — that degrades every correct answer too, and the thresholds
    are panel-ruled. The missing signal is _relevance_, and per-source `score` values already exist
    (0.667, 0.6, 0.571 … observed live). Needs the 4-LLM panel, plus a tripwire exercising the
    successful-retrieval-but-wrong-documents case end-to-end — the 38 existing tests all check the
    comparison, none checks that its input can vary. Memory:
    `discovery_the_abstain_gates_are_well_tested_and_unreachable_2026_07_27` (filename kept for the
    link; its body carries the same correction).

- **🔇 A CORRECT ABSTENTION REACHES THE CLIENT AS SILENCE (2026-07-27, observed live).** By design:
  `wa_inbox_bot.py:346` raises on `data["abstain"]` — _"RAG refused — do not guess. Let the worker
  park it; operator can take over."_ — and the worker's guard turns that into retry/backoff and
  eventually `failed`, "never a wrong send". Verified on Zero's own message: thread 77, outbox 182,
  `status=failed`, `attempts=2`, **`body IS NULL`** — nothing was ever generated or sent. The
  posture (silence beats a wrong answer) is defensible; the two things around it are not:
  1. **Nobody takes over.** The design hands off to an operator lane that CLAUDE.md §2 says does not
     exist. All-time: **143 failed vs 38 done**, 26 distinct threads, `apology_sent_at` = 0 over the
     last 7 days. The client is left waiting, with no signal that anything happened.
  2. **Each abstention costs up to 5 full RAG runs.** The retry re-runs the entire pipeline for a
     question that will abstain identically every time.

  Cheapest honest fix: treat abstain as a TERMINAL outcome rather than a retryable failure, and send
  a real hand-off line ("I don't have verified information on this — a Bali Zero specialist will
  follow up"), which protocol 3 already permits. Wording needs a Zero ruling.

- **🧱 KG SCAFFOLD REACHES CLIENTS ON THE WEB CHAT — the stripper covers 1 of N consumers
  (2026-07-27).** `/api/agentic-rag/query` returned, as the ENTIRE answer, `## SUGGESTED WORKFLOW
(from visa_subgraph, confidence: 78%)` (631 chars, no prose) on **4/12** runs of the
  KITAS-rejection class — and **3/4** on its Italian phrasing. `wa_inbox_bot.py` strips it
  (`_KG_WORKFLOW_SCAFFOLD_RE`, carefully anchored), so WhatsApp is clean — but `apps/mouth` calls
  the same endpoint from three places and `git grep "SUGGESTED WORKFLOW" apps/mouth` returns
  **zero**. Two consequences: (a) the web chat may render internal telemetry — needs browser QA to
  confirm it reaches a rendered surface; (b) on WhatsApp a scaffold-only answer strips to empty
  and `wa_inbox_bot` correctly raises rather than send a blank — so **the client gets no reply at
  all, and no apology** (`apology_sent_at` = 0 over 7 days). Do NOT just add a server-side strip:
  the fast-path is deliberate and has a test asserting the block is in `result.answer`; the
  response already carries a separate `workflow` key, so the structural fix is to stop embedding
  it in `answer` — a contract change that needs the consumer map first.

- **🧠 WHATSAPP CLIENTS NOW HAVE NO LONG-TERM MEMORY AT ALL — by design, decision needed
  (2026-07-27).** `memory_facts` (26,141 rows / 140 users) and `episodic_memories` (1,721) both
  stopped writing at the SAME instant, 2026-07-24T00:59:40Z; `collective_memories` has 0 rows
  ever. Not a fault: PR #3036 (P0-MEM) made both chokepoints skip the shared `wa-mirror-internal`
  pseudo-identity that Path B resolves EVERY WhatsApp sender to — and all WA memory was keyed on
  that bucket. The bleed is contained; the price is total amnesia for WA clients. The real fix, if
  memory is wanted back, is to key on the RESOLVED SENDER (already resolved server-side for the
  persona override, PR #3062) rather than on the shared auth identity. The 26k existing rows sit
  under the shared id and must not be read back. **Business decision, not a bug report — take it
  to Zero.**

- **🧟 `collective_memories` is a DEAD ORGAN (2026-07-26).** `get_collective_context()` reads table
  `collective_memories` = **0 rows**, while `collective_memory` (singular) holds 6. Every request
  pays for the lookup and injects nothing; nothing alarms. Also note it is called with **no user and
  no query filter** (`limit=10`, global top-N by confidence) — if that table is ever populated, it
  becomes a cross-audience channel into anonymous clients' prompts. Gate it by audience before
  filling it.

- **📐 THE SPEC IS NOW THE PLAN OF RECORD — and it is being EXECUTED (2026-07-25, Fable/M5).**
  `research/operations/2026-07-24-zantara-bot-consultant-assistant-spec.md` (added by this PR) is
  FINAL: TAC over a 12-lane workflow, 3-seat cross-family council (Codex red-team / Gemini
  costruttivo / Kimi refuter), every P0 disk-re-verified, **9 Zero rulings ratified in §12/§14**.
  It defines two meta-patterns (A: _Esiste≠Armato_ — capabilities wired to the DEAD legacy path;
  B: broken identity/data-contract boundaries) and the sequenced workstreams
  **W-1 → W0 → W1 → W2 → W3 → W4 → W5 → W6 → W7**. W-1 (P0-MEM #3036, P0-ID/P0-ARG #3062) is
  SHIPPED. Execution of W0/W1/W2/W3 started 2026-07-25.
- **📊 TRAFFIC MEASURED (answers Zero ruling #4, "quantify the weekly client drop first")**:
  over 30 days the Meta number's ledger holds **28 inbound customer messages across 4 threads**;
  22 bot replies sent and `read`. Of 89 `failed` outbox rows, **78 are `24h_window_closed`** and
  they concentrate on a handful of dormant / outbound-initiated threads (one has 0 inbound ever).
  ⇒ **essentially zero real clients are being dropped by the 24h window** — the "81% failure"
  headline is an artifact, not a business problem, and does not justify a paid Meta template.
  ⇒ Strategic consequence: **production traffic is far too thin to be the feedback loop.** The
  golden multi-turn eval is not a nice-to-have, it is the bot's only sensor (spec W-1, in build).
- **First real multi-turn golden baseline, run against LIVE prod (`eval-baseline` lane, Fly `rag`
  machine, 2026-07-25)**: `pass_rate 0.7619 (16/21), n_errors 0, must_not_assert_violations 0` —
  but `mean_key_facts_coverage` came back exactly **0.0**: coverage substring-tested whole prose
  sentences that no answer echoes verbatim. Cured with short anchors (`fix-eval-keyfacts` lane,
  committed in worktree — NOT merged, NOT deployed); 5 of 23 facts remain un-anchored **by
  design** (they describe bot BEHAVIOUR, not answer content) and still score 0 — a disclosed
  limitation, not a tuned-away one. **Read the 76% narrowly: it does NOT measure whether the
  right facts appeared in the answer.**
- **🔴 NEW client-facing defects, found by probing the REAL prod path (not in the spec's C-matrix)**:
  a synthetic client question through `POST /api/agentic-rag/query` (`channel=whatsapp`) returned,
  verbatim, to a _client-role_ caller:
  - **C17 — Path B ships the RAW answer.** `wa_inbox_bot.generate_bot_reply` applies ONLY
    `answer.replace("[ESCALATE]","")`. `channels/format.py::format_rich_text` (which does
    `_strip_markdown` + channel handling, and is fully tested) has **ZERO non-test callers in the
    whole codebase** — dead code. So `###` headings, `**bold**` and `[1, 5]` citation markers reach
    WhatsApp raw. Purest Pattern-A instance found so far.
  - **C18 — internal scaffolding delivered to clients.** The KG block appended by
    `orchestrator_core.py:~816` — `## SUGGESTED WORKFLOW (from visa_subgraph, confidence: 78%)`,
    `**Confidence**: medium — 3 source(s), relationship strength 90%`, `IMPORTANT: ... verify with
the user` — is sent verbatim. Worse, it can CONTRADICT the answer: an E33G remote-worker answer
    (which forbids local employment) arrived with the IMTA/TKA **local work-permit** workflow attached.
  - **C19/C20 — the persona is ADDITIVE, not composed.** `prompt_builder.py:549-552` merely
    _prepends_ `CREATOR_PERSONA`/`TEAM_PERSONA` to the master prompt; **there is no CLIENT_PERSONA**
    and nothing is removed for clients. So the client is the _default_ case while the base prompt is
    written in an internal register ("a client asks…", "check with the team") — the live answer
    literally said _"You can pass this information directly to the client"_ to a client-role caller —
    and it carries the full **`crm_query` playbook** (`client_stats`, `search_clients`, …) in every
    anonymous caller's system prompt. Tool-schema minimisation (T-VIS) does not cover the PROMPT layer.
    ⇒ Cure = audience-COMPOSED prompt (client/team/creator) as `zantara_core_v5`, additive behind the
    versioned door, never editing v4 in place.
  - **Near-miss caught before ship**: a first-draft `client-voice` regex (`_BARE_CITATION_RE`),
    meant to strip the internal `[1]`/`[3]` citation markers from C17/C18, would have CORRUPTED
    Indonesian legal citations — measured `'Perpres 10/2021 Pasal 6 [1] dan [3] berlaku.'` →
    `'Perpres 10/2021 Pasal 6 dan berlaku.'` (bracketed Pasal numbers read as citation markers).
    Caught by adversarial review BEFORE ship; cured by anchoring the strip to trailing source
    markers only. Cicatrix family #3 (guard over-match). State: committed in
    `client-voice`/`fix-client-voice` worktree lanes — NOT merged, NOT deployed.
  - **The denial oracle survives paraphrase, and is worse than the literal string.** Asked
    (client-role) _"quanti clienti attivi abbiamo?"_, the bot never said "denied": it invented
    _"problema tecnico … sistemi di accesso al CRM … account staff autenticato … ti do il numero
    esatto dei clienti dal database live"_ — disclosing the CRM's existence, disguising the
    security control as an outage, leaking the auth model, and promising a stranger the client
    count. A guard that greps for "denied"/a literal refusal string is UNDER-match (cicatrix
    family #3 twin): assert on the FACT disclosed, never the sentence form. State: bug LIVE in
    prod (measured today); cure in flight (`deny-narration` finding → `fix-deny-audit` lane) —
    NOT merged, NOT deployed.
  - **`zantara_core_v5` is built and execution-verified, but the door does not know it yet.**
    Client prompt measured ZERO `crm_query`/`timesheet`/`team_knowledge` and zero third-person
    "the client"; team/creator keep the CRM playbook (`build-prompt-v5` lane). But setting
    `ZANTARA_PROMPT_VERSION=v5` today serves **v1** (22,638 chars) instead of v5 — a silent
    REGRESSION from the v4 armed in prod (36,106 chars) — because the versioned door doesn't
    recognize `"v5"` and falls back silently. `wire-v5-door` lane is wiring the door + making
    unknown versions fail loud instead of silently serving v1. State: v5 built in a worktree,
    NOT merged, NOT deployed; prod is still v4. **DO NOT flip the flag to v5 before that lands.**
- **🔴 P0 — PII log leak, WhatsApp phone numbers in cleartext prod logs (pre-existing, proven by
  execution today, cure in flight — `fix-authz-pii-log` lane).** `tool_authorizer.py:381-389
_audit()` logs `user=%s` from `user_email`, and `tool_executor.py:296` passes `user_id` as
  `user_email`; on WhatsApp `user_id = whatsapp_<phone>`. So a client's phone number is written to
  production logs in cleartext — on the **ALLOW path too**, i.e. every tool call, not just
  denials. UU PDP Art. 67-68 / SYMBIOSIS Law 2. State: bug LIVE in prod; fix NOT merged, NOT
  deployed.
- **🔑 T4 keystone: the bridge already exists, one hop is missing.**
  `whatsapp_identity.resolve_sender_identity` already returns `team_member_email` (DB branch), and
  `_resolve_trusted_wa_profile` already calls it server-side behind the dedicated
  `X-WA-Bot-Profile-Key`. It is simply never fed to `get_agent_role(email)`
  (`team_agent_config.py:498`) — which is why `agent_role` is always `None` on WA and
  `SENSITIVE_TOOLS={crm_query,timesheet,team_knowledge}` hard-deny every team member.
  **T8 measured**: `team_members` with WhatsApp = **17**, VASSAL `TEAM_AGENTS` = **16**, in BOTH =
  **15** → 15/17 get a working principal on day one; 2 have WA but no role, 1 the reverse (the
  env-only branch returns no email at all and must degrade observably).
- **🧰 TOOL-SEAT LIVENESS (probed live 2026-07-25 — Esiste≠Armato applies to our own instruments)**:
  `kimi -m kimi-code/k3` ✅ · `agy` ✅ · **`codex` ❌ 401 Unauthorized** (OAuth revoked → interactive
  `codex login`, `operator[GUI]`) · **`wa-tester` ❌ `PAIRED_BUT_CONNECT_FAILED — logged out`**
  (device unlinked; re-pair needs a QR scan from Zero's phone → `operator[physical]`) — the
  end-to-end channel probe is DOWN, so prove-live currently runs through the in-container brain
  probe + the outbox/ledger state delta. **`flyctl` auth lives ONLY on Mini** (Pro's `FLY_API_TOKEN`
  is unauthorized and `~/.fly/config.yml` has no usable token) — the M5 `fly` shell wrapper, which
  ssh's to Pro, is dead; deploy/secrets/logs must go `ssh mini`.
- **Operational traps that cost hours 2026-07-25 — read before repeating them**:
  - M5 lacked the Postgres role `nuzantara` (hardcoded `backend/tests/conftest.py:28`), so 7
    tests in `test_migration_113.py` ERRORED (not skipped) and killed EVERY full-suite pre-push
    from this machine. Cure: `CREATE ROLE nuzantara LOGIN SUPERUSER` locally.
  - A pre-push suite longer than GitHub's HTTPS idle timeout leaves `git push` HANGING FOREVER on
    a `(CLOSED)` socket AFTER the gate already passed — green gate, no push, no error. Cure:
    batch every ready branch into ONE push (the hook unions all refs, so N branches cost 1 suite)
    plus `-c http.lowSpeedTime=120` so a dead socket errors instead of hanging.
  - `kill -TERM` on a `git push` does NOT kill its pre-push hook subtree; orphaned hooks kept two
    full suites running for 44 minutes. Sweep orphaned ANCESTORS (`ps -eo pid,ppid | awk
'$2==1'`), and kill CHILDREN FIRST or init re-adopts them.
- **P0-ID WA persona-override forgery — SHIPPED+DEPLOYED+PROVEN (PR #3062, 2026-07-24)**: the
  trusted "creator/team" persona override in `agentic_rag.py` was forgeable — a first server-side
  fix (re-resolving the WA sender phone instead of trusting a client-declared `profile` field) was
  still bypassable, because the phone came from the client-controlled `user_id` field and the
  owner's WA number is documented-public: any holder of the widely-shared `X-Internal-Key` could
  send `user_id="whatsapp_<owner's public number>"` and get the creator persona. Caught by an
  independent adversarial review dispatched specifically to try to break the design. Fixed with a
  SECOND, dedicated secret exclusive to `wa_inbox_bot.py` (`X-WA-Bot-Profile-Key` /
  `WA_INBOX_BOT_PROFILE_KEY`), modeled on the existing `wa_mirror_crm_write_key` precedent — the
  override now requires the dedicated key AND `resolve_sender_identity` resolving to owner/team; no
  request body field can influence the outcome. A second fresh review of the v2 design (not the
  same reviewer, no context on v1's failure) gave SHIP, independently re-verified on disk before
  trusting it. Also closed **P0-ARG** in the same PR: `tool_executor.execute_tool` stripped
  LLM-injected reserved arg keys (`_caller_profile`, `_user_id`) so a forged tool-call argument
  can never survive to override the server's real profile. Merged (squash `5d689084d1`), deployed,
  prove-live: container content-verified (grepped the running machine's actual deployed source),
  secret confirmed present in prod env, zero errors in prod logs post-deploy. Detail: memory
  `discovery_p0id_narrow_first_fix_insufficient_2026_07_24`. **This is the security prerequisite
  team-assistant V1 (§1 below) relies on for a safe owner/team persona — it was hardened, not
  newly built, by this PR.**
- **GEMINI PREPAY DEPLETION P0 (2026-07-22) — RESOLVED via top-up + verifier revival PROVEN LIVE**:
  while carrying the RAG verifier revival to prove-live, live prod logs revealed the WHOLE bot was
  degraded — NOT by the verifier but by `429 RESOURCE_EXHAUSTED "prepayment credits are depleted"`
  on BOTH `gemini-3.5-flash` (primary) AND `gemini-2.5-flash` (fallback): the prepay Gemini key's
  balance hit zero (the `discovery_gemini_api_key...2026_07_19` risk realized). Symptom: agentic LLM
  dead → can't drive tool-retrieval → `Chunks retrieved: 0` → **abstain on EVERYTHING** (visa/tax/
  company all `confidence:0.0`); verifier can't run either (also Gemini). Only verbatim FAQ cache
  still served (no Gemini). Embeddings + Qdrant were fine — Gemini-only outage. Zero topped up the
  prepay on project `nuzantara` (AI Studio, operator/billing). **Post-top-up prove-live (fly logs,
  this turn)**: 0× 429, retrieval alive (`Chunks retrieved: 13`, confidence 0.85, real E35/E28
  sources), and the **verifier producing real parsed verdicts** — `🛡️ [Verifier] Status:
PARTIALLY_VERIFIED | Score: 0.75`, `[VerificationStage] ... verdict_available=True`,
  `[self-correct] verify=24.11s` (self-correction fires). **Verifier revival (PR #2973, fence-parse
  → `generate_structured`) = DONE + PROVEN LIVE.** The pre-topup "intermittent ~1/3 schema-fails" was
  the depletion front, NOT strict schema (anyOf/bounds refuted on real Gemini). **OPEN follow-ups
  (non-blocking)**: (a) enable prepay **auto-recharge / low-balance alert** (billing, operator) — the
  only structural cure while Fly arch is "Gemini always"; (b) verifier robustness (round-3
  schema-loosen held unpushed at `8604d7ae96`, ship only with a real before/after schema-fail
  measurement); (c) architectural non-Gemini fallback on Fly so a 429-Gemini never zeroes the bot.
  Detail: memory `discovery_prod_verifier_dead_fence_parse_not_leaked_key_2026_07_21` +
  `discovery_gemini_api_key_project_orphan_ledger_undercount_2026_07_19` (§RESOLVED).
- **🔒 P0 SECURITY — CRM/PII public exposure FIXED + DEPLOYED + PROVEN (PR #2962, 2026-07-21)**: `/api/blog/ask` (+ WA-unknown ReAct) could exfiltrate CRM whole-book PII (`crm_query`) and the full staff roster incl. pin/religion (`team_knowledge`); `/api/team/clock-in`+`/clock-out`+`/my-status` allowed impersonation (identity from body, no auth). Tourniquet (2 Codex red-team rounds, generator≠grader): `SENSITIVE_TOOLS={crm_query,timesheet,team_knowledge}` denied for `agent_role=None` in `tool_authorizer.py`; `_resolve_actor_identity` in `team_activity.py` ignores body identity for non-admin (closes email+user_id); `Depends(get_current_user)` on clock-in/out/my-status. PROVE-LIVE prod: blog/ask → `tool_authz decision=deny role=none tool=team_knowledge` (log) + graceful 0-PII answer; clock-in/out/my-status no-auth → 401; health 200. Staff no-regression + non-admin→own-identity verified by red-team + 13 unit tests (`test_team_activity_clock_identity_tourniquet.py`). Full principal-based rework (unified server-side principal, unconditional reserved-arg strip, clamp `CRMTool.limit`, timesheet email from principal, remove legacy `agent_role=None→allow`) is a SEPARATE non-P0 follow-up. Memory `discovery_crm_pii_public_exposure_blog_ask_timesheet_2026_07_21`.
- **🎫 Collateral finding (open ticket): JWT expiry NOT enforced in prod**: `jwt_enforce_expiry=False` default (`config.py:501`, "Phase 1 audit mode"), no prod override (`JWT_ENFORCE_EXPIRY` absent from fly secrets) → expired JWTs accepted app-wide (`verify_exp` in hybrid_auth.py:473/517, auth.py:126, websocket.py:93, deps/auth.py:70). Flip = ops decision (verify refresh-token works first, blind flip logs out live sessions). Memory `discovery_crm_pii_public_exposure_blog_ask_timesheet_2026_07_21`.
- **🎫 Collateral finding (open ticket): orphan test tree**: `apps/backend-rag/tests/` (top-level, 1189+ lines) is NOT collected by any CI workflow nor the pre-push (both scope `backend/tests/`; `pytest.ini testpaths=backend/tests`) → false coverage (scar #2). Tests there never run in gate.
- **🎚️ VERBATIM FAQ → JELAS-only (Zero 2026-07-21) — DONE+VERIFIED**: refined the 19/7 "all verbatim"; deleted 215 non-JELAS from Redis `notebooklm:qa:*` (AFTER = 139 = 103 JELAS + 36 E33, non-JELAS=0); Qdrant `curated_qa` 808 pts intact (grounding preserved). This PR retires the `--verbatim-all` override so a re-harvest can't undo it. Memory `ops_verbatim_rollback_jelas_only_2026_07_21`.
- **WA OUTBOX P0 (2026-07-19) — FIXED #2812 + DEPLOYED 12:45 UTC + VERIFIED**: the per-thread
  advisory lock passed raw `int thread_id` into `hashtext('wa_outbox_thread_' || $1::text)` —
  asyncpg types `$1` TEXT from the cast and refuses int (`DataError: expected str, got int`),
  so the scheduler crashed EVERY tick and the bot was mute ~4h (2,495 crashes). Fix:
  `str(thread_id)` at lock AND unlock (must hash to the same key). Unit mocks never caught it —
  they don't do asyncpg's client-side type validation. Deploy got lost twice (concurrency-cancel
  - ~2h runner queue); caught by the new fly-logs accumulator (O0-P1). Verified: zero
    occurrences after 12:44 UTC. **Lesson: lock/unlock key args must be same TYPE, and mocks of
    asyncpg conns lie about type checking.** **Client-side PROVE-LIVE**: backlog claimed at
    12:13Z right after deploy; fresh inbound answered in 150ms (row 157); only failures =
    `24h_window_closed` on a thread idle since June (correct Meta-policy behavior) —
    independently confirmed by the wa-tester battery from Zero's own number (bot reply ~36s,
    Meta `read` receipt, all corrected facts verbatim in Bahasa).
- **PR #2825 (injection gap #23) MERGED + DEPLOYED + PROVEN**: overstay/penangkalan/deportation/
  re-entry-ban keywords added to the visa domain classifier — queries previously classed
  "general" never searched curated_qa. Prove-live: probe → log
  `✅ [CuratedQA] Injected 2 curated evidence block(s)`, answer carries 60-day threshold /
  10+10 ban / Rp 90jt pencabutan (PP 45/2024 VI.E).
- **PR #2822 (QdrantClient.get) MERGED + DEPLOYED**: flags moved to JSON body (`with_payload`/
  `with_vector`) — was silently returning empty payloads. Consumer-map finding: sole non-test
  caller is the memory_vector router which is NOT mounted in prod (F29 note in handlers.py) →
  preventive hardening, no live surface.
- **CHATKB cantiere: 21 dossiers GATED (396 Q&A)** across visa/company/tax/property (Waves 1-3,
  Fable gate 7/7+8/8+6/6 PASS). Zero ruling 2026-07-19: **promote ALL answers VERBATIM** (team
  review after, not before) — execution gated on PR #2810 rails (pricing-detector, source
  allowlist, `verbatim_eligible`, still OPEN); PR #2856 (compound-CONFIDENCE degrade at
  harvest) MERGED. Team review packs: 21 batches Bahasa + 21 editable docx in
  `~/Desktop/TEAM-REVIEW-2026-07-20/`.
- **CHATKB review pipeline (2026-07-21)**: corrections dir
  `research/curated-qa-corrections-2026-07-21/` (rounds 1-4 applied+harvested). Dossier 11
  (company-kbli-signed-lots) **round 5 APPLIED TO PROD** batch `company-b02dc5cb2e89`: Q5/Q6
  KBLI 70100 PMA-block fix (no Usaha Besar row in OSS → a PT PMA cannot register under 70100;
  the wrong "register now" answer grounded prod RAG from round 4 until the re-harvest), Q13
  66123 hedged Bali-moratorium caveat (LOW confidence). Adversarial review FIX-THEN-SHIP
  caught the 64200→64210 vintage error. Capture + operator recipe:
  `research/company/2026-07-21-kbli-signed-lots-round5-verification.md` + README Round-5
  section (PR #2989).
- **GARUDA-E23 law_refs delta-harvest LIVE**: Perpres 20/2018 (revoked in full by PP 34/2021)
  re-cited to PP 34/2021 Pasal 19/6 on 2 prod points (Q2/Q6), answers untouched, neighbors
  no-drift.
- **Team-assistant V1 — MERGED, NOT "in flight" (PR #2872, 2026-07-20)** _(corrected 2026-07-25 —
  this line and §6 both claimed IN FLIGHT for five days)_: sender-identity wiring into the live
  meta-inbox path landed. **Phase 2 (4 read-only CRM scoped tools) is ALSO MERGED (PR #2890)** —
  it is not "parked pending Zero GO". What is actually missing is ARMING + a principal:
  `WA_TEAM_CRM_TOOLS_ENABLED` is UNSET in prod (default false), and even armed it would deny,
  because `agent_role` is never derived on the WA path (see the T4 keystone in §1). Merged ≠ live.
- **wa-tester LID under-match (task #26) — FIXED (#2903)**. Superseded by a NEW problem: the
  wa-tester session itself is **logged out** (`PAIRED_BUT_CONNECT_FAILED`), so the end-to-end
  channel probe is down until someone re-pairs it by QR (`operator[physical]`).
- **PR #2586 MERGED**: 4 production bugs of the outbox worker fixed (burst duplicate replies,
  takeover-during-generation send, generating-crash orphan, FAQ prewarm scope mismatch) +
  per-thread advisory lock, claim-token fencing, lease heartbeat, burst coalescing, K workers
  (`WA_OUTBOX_WORKERS=2`), admission semaphore (`WA_BOT_MAX_CONCURRENT_GENERATIONS=3`).
- **PR #2588 (cache F1b) MERGED + DEPLOYED**: FAQ cache wired into the orchestrator the WA bot
  uses, provenance-mandatory cache writes, curated_qa Qdrant collection + grounding injection,
  harvester/converter tooling. **E33 216 loaded and verified live**: Redis 216 keys + Qdrant 216
  points.
- **PR #2611 (Gemini 3.5 Flash) MERGED + DEPLOYED**: PRIMARY/CHANNEL = `gemini-3.5-flash`,
  proven in prod (GA, function calling OK). FALLBACK stays `gemini-2.5-flash`.
- **PROVE-LIVE done** on the real bot path: 200 responses in 1.6–3.9s.
- **LANGFUSE INCIDENT (2026-07-05 → 2026-07-17, bot dead 11 days)**: a dependabot bump
  (langfuse 3.14.6 → 4.x) renamed `Langfuse.start_as_current_span()` to
  `start_as_current_observation(..., as_type="span")` — the old name doesn't exist in v4 at all.
  `_process_query_traced` in `agentic_rag.py` called the v3 name unguarded, so every
  `/api/agentic-rag/query` call raised `AttributeError` before the orchestrator ever ran. Outbox
  outcome: 61 failed sends vs 1 success. Emergency mitigation was the Fly secret
  `LANGFUSE_ENABLED=false` (kill-switch in `observability.py::is_enabled`) — **NO LONGER ACTIVE
  (corrected 2026-07-25)**: `flyctl secrets list -a nuzantara-rag` shows no `LANGFUSE_ENABLED`
  entry and the Langfuse keys are deployed, so `observability.py`'s default `"true"` applies and
  **tracing is ON in prod**. The "still active" framing below is historical. **Durable fix**: this
  PR — `backend/core/observability.py::start_traced_span()` resolves v4-first/v3-fallback via
  `hasattr` and fails open (no-op span + WARNING log) on any mismatch, applied at both real call
  sites (`agentic_rag.py`, `tone_council.py`). Re-enabling tracing in prod (`fly secrets unset
LANGFUSE_ENABLED` or set back to `true`) is an operator action AFTER this PR merges+deploys —
  not done yet as of this update.
- **Corner PR #2612 MERGED** (prior §1 refresh, superseded by this update).
- **F2 (team check-in) NOT started** — begins after F1 ships. F3 (member profiles) after F2.
- **Prompt v4 + versioned door MERGED (#2629) AND prod FLIPPED `ZANTARA_PROMPT_VERSION=v4` —
  PROVEN-LIVE 2026-07-18.** `zantara_core_v4.py` (deadline-neutral KBLI guidance, phantom KBLI
  codes fixed 55130/55194→55203/55901/55400, `{today_wita}` date injection,
  `_safe_template_fill()` — the WORKED_EXAMPLES `.format()` P0 stays fixed) + `prompt_builder.py`
  imports `ZANTARA_MASTER_TEMPLATE` from `prompt_manager` (the door). Prod log proof:
  `PromptManager: using zantara_core_v4` (clean INFO, no fallback); battery on the door 2/2 PASS.
  **Gotcha that almost shipped**: v4 was drafted BEFORE the #2736 trigger fix and re-listed bare
  visa codes ("C1","C2","D1"⊂"D12") as get_pricing triggers — auto-merge was disarmed, the fix
  folded in (parity commit `9b0e9ac120`), THEN merged. The deploy alone would have REGRESSED
  ask_legal to v3's stale copy — the env flip is part of the ship, not an afterthought. v2/v3's
  stale trigger copies are now dead code behind the door. Design doc:
  `research/operations/2026-07-17-zantara-prompt-v4-design.md`.
- **Bot quality campaign 5 lanes SHIPPED+PROVEN (2026-07-18)** — memory
  `ops_zantara_bot_quality_campaign_4_lanes_2026_07_18` holds full detail: (A) 60s timeouts
  root-caused to a broken verifier minting fake score=0.5 on empty Gemini responses → doomed
  ~23s self-correction loop (#2712 `verdict_available` flag; C1→KITAS 2×timeout→35.3s) + 6
  missing Qdrant `status_vigensi` indexes + `ENABLE_RERANKER` secret unset; (B) Fonti leak
  proven never-reached WA clients; (C) stale WA number purged from 70 prod pricing points
  (#2708); (D) unsolicited price dumps killed (#2707 intent-gated boost, word-boundary); (E)
  zantara_core.py v1 trigger fix (#2736, operator two-key window) — bare visa codes are NOT
  pricing triggers, visa-TYPE questions ground on current codes names-only + one-line cost offer.
- **Full-domain cache lane OPEN** (design pending). Tracked in the main session's task list.

## 2. ESTABLISHED TRUTH (verified — do not re-litigate, do not re-derive)

1. **Two WA code paths exist.** Path B is the live one for this number: Meta webhook →
   `meta_inbox_*` tables → `wa_outbox` ledger → `wa_outbox_worker.py` (claim/fence/coalesce) →
   `wa_inbox_bot.py` → POST `/api/agentic-rag/query` → agentic RAG orchestrator → Gemini.
   Path A (OpenClaw bridge on Pro, gpt-5.5) is LEGACY — not this number's brain.
2. **Bot autoreply is LIVE in prod**: `WA_INBOX_BOT_AUTOREPLY=true` (verified via fly ssh
   printenv). Human takeover/release works from the console (see §6).
3. **Latency (10–50s) comes from the agentic RAG loop, not the model.** The cure is
   cache-first + curated grounding + faster model — never bypassing the abstain gates.
4. **Cache safety contract**: cache hits bypass the abstain gate → ONLY pre-vetted content may
   enter the cache; every entry carries
   `{source_ref, source_date, domain, confidence_class, source_priority}` (enforced by
   `NotebookLMCacheService.set()` — ValueError without them). curated_qa is GROUNDING injection
   (never verbatim serving); abstain gates stay live on that path.
5. **Prompt split-brain (audit 2026-07-17)**: the agentic RAG brain imports prompt **v1
   directly** (`prompt_builder.py:25`) — the `ZANTARA_PROMPT_VERSION=v3` env in prod only arms
   v3 on `zantara_ai_client.py`. v3's worked examples never reach the WA path. Also verified:
   NO current-date injection anywhere; stale "18 June 2026" KBLI deadline announced as future;
   v3 villa example teaches phantom codes (55130/55194 NOT in KBLI 2025 — real code is 55203);
   whatsapp_persona injects the full price list beside the "only get_pricing" rule; few-shots
   carry pre-BKPM-5/2025 capital claims. Cure = **v4 behind the same env flag**, one versioned
   entry point for ALL consumers + parity test. Never edit v1/v2/v3 in place.
   **RESOLVED 2026-07-18**: door merged (#2629) and prod flipped to v4 — see §1. The audit
   findings above are historical context; the split-brain no longer exists. Exception to
   "never edit v1 in place" happened ONCE under operator two-key window (#2736 trigger fix,
   before the door existed in prod) — with the door live, prompt changes go to v4 only.
6. **Meta 24h window**: per-thread, resets on every user message, service replies inside it are
   free. Business-initiated outside it needs a paid approved template — which Zero has REJECTED
   for attendance nudges (reactive-only ruling).
7. **Embedding model FROZEN** `text-embedding-3-small` 1536 dims (curated_qa included) — flat
   payloads only.

## 3. Anatomy (the 10 anelli, with file paths)

| #   | Organ                                   | Where                                                                                                      | State                                                    |
| --- | --------------------------------------- | ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| 1   | Meta webhook (ack<200ms, dedup, replay) | `backend/app/routers/whatsapp_chat.py`                                                                     | solid, untouched                                         |
| 2   | Message ledger                          | `meta_inbox_threads/_messages` tables                                                                      | solid, untouched                                         |
| 3   | Reply queue + send                      | `backend/services/integrations/wa_outbox_worker.py`                                                        | rebuilt #2586                                            |
| 4   | Reply generator                         | `backend/services/integrations/wa_inbox_bot.py`                                                            | semaphore added #2586                                    |
| 5   | RAG brain                               | `backend/services/rag/agentic/` (orchestrator_core, reasoning, llm_gateway)                                | wiring touched (#2588), reasoning/gates INTACT by design |
| 6   | Cache/corpus layer                      | `backend/services/caching/notebooklm_cache_service.py`, `curated_qa` collection, `scripts/curated_qa_*.py` | built #2588                                              |
| 7   | Model                                   | `backend/llm/config.py:12-20` (ModelName)                                                                  | 3.5 Flash PR queued                                      |
| 8   | Persona/prompt                          | `backend/prompts/` chain (v1→v2→v3 + whatsapp_persona + channel_overlays) + `prompt_builder.py` (agentic)  | v4 lane open; files off-limits w/o mandate               |
| 9   | Team check-in (F2)                      | does not exist yet on this path                                                                            | designed in spec v2                                      |
| 10  | Operator console                        | `apps/wa-meta-inbox` (thin proxy → `/api/wa-inbox/*`)                                                      | live on Pro                                              |

## 4. Zero's rulings (business decisions — do not re-open)

1. WA check-in **AFFIANCA** kita clock-in (both write `team_timesheet`), does not replace it.
2. **WA reactive-only**: nudges/briefings only inside an open 24h window; proactive reminders
   stay Telegram/email; NO paid Meta template.
3. Team persona (non-check-in) = **assistente operativo interno**, not sales consultant.
4. clock_in/clock_out MCP RBAC widening beyond admin = OK (partial ruling, only the 2 clock tools).
5. **Gemini 3.5 Flash in prod** = GO ("proviamo 3.5 flash in prod").
6. **Full-domain cache program** = GO (visa/company/tax/property like the E33 216, with
   auto-regeneration + obsolescence archiving, reuse-first).
7. **Prompt SOTA audit + alignment** = AUTHORIZED (v4 additive, flag-gated).
8. **One client-facing price** — never split PNBP vs fee (memory `feedback_single_price_no_pnbp_fee_split`).

## 5. Blood-bought operating rules

- **Provenance beats freshness-illusion (W90)**: no cache entry without source_date; a cache
  answer whose source predates a regulatory change is a lie with a citation.
- **The abstain gates are the product**: any "optimization" that serves un-vetted content past
  them is a safety regression, not a speedup (cf. 5 named gates SSOT `_abstain_policy.py`).
- **Generator≠grader everywhere**: the diff author never gates its own diff; corpus loads get
  blind verification (KBLI-filiera method) before serving clients.
- **Prices**: PricingTool is the ONLY source. The prompt chain currently violates this in
  spirit (injected price list) — do not copy that pattern into new code.
- **PII**: team briefings are PII-light (counts + practice codes, never client names on WA).
  Client PII never enters cache keys, logs, or this corner file.
- **Waiter-pollers stall**: background-task completion notifications to subagents are
  unreliable — probe objective state (git ls-remote, gh pr view, ps with EXACT patterns) and
  nudge with proof. A wrong ps pattern refutes YOU, not the agent (lived twice on 2026-07-17).
- **Push discipline (M5)**: pre-push gate 11–32 min > Bash cap → `run_in_background` + prove
  with `git ls-remote`; push at low honest load (`sysctl -n vm.loadavg` < 8).

## 6. Artifacts & access

- **Spec v2 (design contract)**: session scratchpad `zantara-wa-spec-v2.md` (panel-corrected,
  P1–P14; content summarized in memory + this corner survives it).
- **Decision memory**: `~/.claude/projects/-Users-balizero-nuzantara/memory/decision_zantara_wa_team_checkin_go_2026_07_17.md`.
- **Console (read/reply/takeover)**: live on Pro, LaunchAgent `com.balizero.wa-meta-inbox`,
  `http://localhost:7791` (loopback-only; from M5: `ssh -L 7791:localhost:7791 pro`).
- **Env knobs**: `WA_INBOX_BOT_AUTOREPLY`, `WA_OUTBOX_WORKERS`,
  `WA_BOT_MAX_CONCURRENT_GENERATIONS`, `ZANTARA_PROMPT_VERSION`, `CURATED_QA_INJECTION_ENABLED`,
  `DOMAIN_ABSTAIN_THRESHOLDS`.
- **Corpora**: `data/curated_qa/*.jsonl` (E33 216 via `curated_qa_convert_e33.py`; golden 28).
- **Team phone SSOT**: `team_members.whatsapp` (F2 detection key). **Coverage measured
  2026-07-25**: 17 rows carry a WhatsApp number; `TEAM_AGENTS` (VASSAL roles,
  `team_agent_config.py`) has 16 entries; **15 appear in both** → 15/17 team members get a real
  principal once T4 lands. 2 have WhatsApp but no VASSAL role, 1 the reverse. Note the env branch
  (`WHATSAPP_TEAM_NUMBERS`) resolves a team member WITHOUT an email, so those senders can never
  obtain an `agent_role` — that path must degrade observably, not silently.
- **Team-assistant V1 (task #29) — CLOSED/MERGED (#2872 + #2890, 2026-07-20)**, corrected
  2026-07-25. The remaining work is not "plumbing identity" but **T4** (derive `agent_role` from
  the already-resolved `team_member_email`) + **T-VIS** (per-request tool minimisation) + arming
  the flag. See §1.

## 7. Collaboration protocol (the TRACK)

- Load this corner FIRST on any bot theme. `mem query "zantara wa"` for history.
- Whoever changes state (merges a PR, deploys, loads a corpus, flips an env) **updates §1 in the
  same PR/turn** — a stale corner is worse than no corner.
- Every build lane runs in its own worktree via `scripts/agent_start.py` (lane `backend-rag`);
  main checkout is read-only for agents.
- Fable sessions orchestrate + final-gate; edits/commits/pushes go to Sonnet implementers
  (hook-enforced). Adversarial review before merge on client-facing surfaces.
- Off-limits without a fresh mandate: `zantara_core.py` (+ prompt chain in place), `fly.toml`,
  `.env*`. The prompt v4 lane has Zero's mandate but is ADDITIVE ONLY (new file + flag).
