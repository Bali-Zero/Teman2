---
name: bot
description: "Zantara WA bot corner — shared context for the Zantara WhatsApp bot. Load before touching WA-bot code/data, or when Zero says /bot, 'zantara wa', 'il bot', 'meta inbox', 'cache risposte'."
---

## Notes (moved from description 2026-09-02)

The Zantara WhatsApp Meta bot number: +62 821-3465-159. Covers: outbox/inbox pipeline, agentic RAG brain, answer cache, model routing, prompt chain, team check-in program. Holds: established truths (verified, with method), Zero's rulings, LIVE STATE of the ship chain, blood-bought operating rules.

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

## 1. LIVE STATE (last update 2026-09-03 — keep current)

- **🧭 CYCLE 359's FOUR ROOT CAUSES: TWO CURED, ONE DRAFTED FOR ZERO, ONE STILL OPEN — AND THE
  CORNER'S OWN "GEMINI" BULLETS ARE CONFIRMED STALE (2026-09-03, lane E on Pro).** Re-measured
  before anything else, exactly as the mandate required: `SELECT generation_route, count(*) FROM
wa_outbox` returns **`codex` on all 58 rows since 2026-08-27** and NULL only on the older ones.
  The codex route is the live one; every S4-cutover bullet below describes a state that is gone.
  - **✅ ROOT CAUSE 4 (greeting) — CURED, PR #5613.** A bare `halo` cost **7m45s** and answered an
    English error stub. Nothing in the chain was broken: `QueryDomain.GREETING` maps to `[]`
    collections by design, so `build_context_package` raises `PackageUnbuildable("greeting_domain")`
    and — with the Gemini leg cut — there is no second generator, so the row takes the full
    five-attempt ladder. `wa_greeting.match_greeting` (pure, no I/O) now answers it from a script
    **before the package build**, in the greeting's own language. **The expensive half is
    innocence**: `halo, berapa harga PT PMA?` is a pricing question wearing a polite hat and must
    reach the normal route — 24 innocence cases against 30 guilt.
    - **The cross-family refuter earned its seat.** Codex GPT-5.6 Sol returned **BLOCK** with a real
      blocker the author had not seen: `"Halo admin?"` matched, so a client asking for a **person**
      got a capability list — this module's own defect pointed the other way. `admin`/`team`/
      `everyone` are no longer vocatives. It also found `"Assalamu'alaikum"` (apostrophe → two
      unknown tokens) and `"Selamat pagi, Kak"` (phrases were keyed on the WHOLE message) still
      costing 7m45s, and `"Hi kak"` answered in English. All cured; the placement objection was
      answered in prose, not code — see the module docstring.
    - **Declared gap:** `generation_route` stays NULL on a scripted greeting (that column is one
      half of the codex OFFER's CAS fence, and the row is never offered), so a greeting is not yet
      countable in SQL. `CodexLegResult.served_by` is its only marker. Same ledger family as "an
      abstain leaves no record".
  - **✅ ROOT CAUSE 2 (the corpus teaches the split) — GATE SHIPPED (PR #5615), DATA HALF EXECUTED,
    AND IT IS BIGGER THAN THIS CORNER RECORDED.** The two named orphans are **deleted from prod**
    (`points_count 808 → 806`, snapshot **with vectors** at
    `~/.nuzantara-lane-e-backups/curated_qa_2026-09-03_five_points.json`, 0600 — fully restorable),
    and a re-scan of all 806 finds **zero** Investor-KITAS answers still carrying a PNBP figure.
    - **⚠️ The second id in this corner was WRONG.** It reads `59da08d9-…-5373-…`; the live point is
      **`59da08d9-39c5-5373-8928-fbcf6833b319`**. The DB is the authority — retrieve by content,
      not by a remembered id.
    - **The gate, measured on all 808 before deletion:** 758 name no government fee (untouched);
      **27 name one with NO figure and PASS** — and those are the model answers (_"rather than quote
      a figure that may age, ask our team"_); **26 name one WITH a figure and are refused** unless
      the row carries an explicit flag **and** a written note. Recall on the known offenders: **9/9**.
    - **A proximity rule was built and REJECTED on its numbers** — at every window from 40 to 160
      characters it caught at most 8 of 9 while blocking 11-13 compliant rows. **No lexical rule
      separates "the government charges X, we charge Y" from "our X already includes it"; that
      difference is semantic.** Do not re-derive it — the gate is deliberately high-recall and
      refuse-by-default, and the escape hatch is a human's written note.
    - **🔴 SEVEN MORE `curated_qa` OFFENDERS ARE STILL LIVE**, snapshotted and ready: the three the
      mandate asked to review — `8b520434` (E33E#Q13, _"which we quote separately"_), `eacec21f`
      (FINAL#Q11), `8ebf681f` (FINAL#Q13) — **plus four the FACT-scan found that nobody had named**:
      `11b7e26d`, `12d804e9`, `1b53de60`, `e407d532`. Deleting them applies a standing ruling, but it
      more than triples an explicit two-row order on production client-facing data, so it was
      surfaced rather than taken. **One decision, seven rows.**
    - **🔴 THE WORSE CARRIER IS IN A DIFFERENT COLLECTION, AND IT IS A WORKED EXAMPLE, NOT A
      MENTION.** `training_conversations_hybrid` (3,638 points) holds **8** teaching the split, and
      **6 of them model a consultant giving an ITEMISED PT PMA quote** — _"Jasa Pendirian: IDR
      20.000.000 / Biaya PNBP (Negara): IDR 5.000.000"_ — in Indonesian, Javanese **and** English,
      duplicated, on the single most common pricing question. The bot is not merely reading the
      split; it has been shown how to perform it.
    - **The training-data file has FOUR occurrences, not the one this corner named.**
      `visa_011_notebooklm_session2.md:123` is fixed (backed up first); lines **315, 547 and 711**
      carry it too, and `grep -rc PNBP training-data/` returns **36 lines across 5 files**
      (`legal_058` 14, `visa_016` 12, `visa_011` 4, `visa_010` 3, `realestate_046` 3). That whole
      directory is **gitignored** — it is local staging, unreviewable in a PR — and
      `scripts/reingest_training_data.py` is the ingest path where the same detector belongs.
  - **📝 ROOT CAUSE 3 (the citation rule) — DRAFTED FOR ZERO, MERGED (PR #5611).** The exact
    replacement paragraph is in `docs/plans/2026-09-03-relaunch-lanes/ZERO-DECISIONS.md` §Item 3.
    **Where it bites, verified by grep:** `MANDATORY LAW CITATION` appears in `zantara_core.py` and
    nowhere else, and `CITATION_RULES` is read by `zantara_core_v4.py:517`, `zantara_core_v5.py:259`
    **and `wa_package_builder.py:41-45` — the live codex-leg persona**. One bullet governs every
    prompt version and the WhatsApp product. `zantara_core.py` was not touched.
  - **🔴 ROOT CAUSE 1 + THE BIGGEST FINDING (the cross-language abstain gate) — NOT STARTED.** Spec
    `research/operations/2026-09-01-wa-evidence-relevance-cross-language-spec.md` is complete and
    panel-blocked-into-shape; nothing is built. **Do not tune a third threshold.** The direction is
    fixed by the spec: retrieval similarity becomes the PRIMARY relevance signal (the embeddings are
    multilingual by construction), lexical overlap is corroborating at most, the `len(w) > 3` filter
    goes or becomes vocabulary-aware so `PT`/`PMA`/`NIB`/`OSS` survive, and the golden set reports
    the abstain rate **separately** for the Indonesian and English subsets — a blended rate hides
    exactly this defect.
  - **🟡 PR #5337 (split-fee veto) — STILL SUSPENDED, not reopened.** 11/11 vetoed, nine compliant
    one-price answers and both genuine splits. **The corpus built for THIS lane is the head start
    nobody had**: 9 measured offenders and 27 measured compliant rows, verbatim, already in
    `backend/tests/unit/services/test_curated_qa_government_fee_gate.py`. A detector that scores
    innocence and guilt should be built from those, not from scratch.
  - **🟡 CYCLE 360 — NOT RUN.** E1-E2 are merged-or-armed but only the corpus half is proven; the
    end-to-end proof on WhatsApp thread 30 with Damar has not happened, and until it does **nothing
    here is proven live**. The two citation-rule cases (bank transfer → no `📜`; passport photo →
    no `📜`; a substantive immigration answer → `📜` still present, the innocence half) go in the
    same battery table.

- **🩺 CYCLE 359 — THE FIRST BATTERY EVER MEASURED ON REAL DELIVERY, AND IT DOES NOT PASS.
  22 questions, 21 delivered+read, 8 FAIL / 5 SUSPECT (2026-09-01, WhatsApp thread 30, sender is
  Damar of Bali Zero; corpus stratified on the 993-conversation frequency ranking, so
  document-operations and payments — 27% of real demand, never measured before — led the battery).**
  Judged by four independent sources: the session, Codex GPT-5.6 Sol xhigh, Gemini 3.1 Pro, and the
  published literature. **Kimi K3 was DEAD (403, weekly quota) — the panel was 2 seats, not 3; a
  seat that did not run is not a seat that agreed.**
  - **⚡ WHATSAPP GENERATION RUNS ON CODEX, NOT GEMINI — the S4 bullets below are STALE.**
    `wa_outbox.generation_route='codex'` on every row, observed by two independent agents. That
    column is written only when `wa_codex_leg.attempt()` offers a job, gated on
    `WA_GENERATION_PROVIDER=="codex"`. Every "S4 cutover is the owner's switch alone, not flipped"
    claim below describes a state that no longer exists. **Do not build on those bullets without
    re-measuring `generation_route` first.**
  - **THE FOUR ROOT CAUSES** (not eight symptoms — two live in the same file):
    1. **The evidence gate ignored the price it was already holding.** `wa_package_builder.py`
       fetched the correct Rp 20.000.000 into `pricing_block`, then computed `evidence_score` and
       `context_length` from vector `chunks` ALONE, nine lines later, and froze `abstain=True`.
       Cured in **PR #5504** — but that PR deliberately does NOT claim to clear the abstain, see
       the cross-language defect below.
    2. **The corpus still teaches the price split** — §Q11/Q14 volunteered `PNBP Rp9.500.000`
       beside the Bali Zero price. Sources found: Qdrant `curated_qa` points
       `57deb254-c2d7-530e-9321-a51f6ad80e1a` (answers "how much does the Investor KITAS COST" with
       the government fee ONLY) and `59da08d9-39c5-5373-8928-fbcf6833b319` ("**We always keep these
       two costs distinct**" — the split as written doctrine). Both are **ORPHANS: no
       `GARUDA-E28A-DEFINITIVE-CHATKB-2026-07-18.md` exists anywhere in the repo or its git
       history**, so deleting them from Qdrant fixes today and nothing else — the next harvest can
       regenerate them. Their source file is dated ONE DAY AFTER the 2026-07-17 single-price
       ruling: the corpus was generated in violation of a rule already in force. **A FACT-scan
       (any government-fee token, not a phrase list) finds 44 of 808 points touching government
       fees**; most are legitimate under the ruling, but `8b520434` (E33E#Q13, "…which we quote
       separately"), `eacec21f` (bare PNBP figures) and `8ebf681f` ("two entirely separate things")
       are further offenders. Secondary live carrier: `training-data/visa/visa_011_notebooklm_session2.md:123`
       → `training_conversations_hybrid`. **RULED OUT** by direct query: the price-list JSON
       (`notes` empty on all 3 Investor KITAS entries), `zantara_core.py`, `backend/kb/`, and the KG
       `HAS_FEE` graph (node `biaya_9500000` exists in `kg_nodes` with **zero incoming edges**, so
       it is unreachable by `kg_subgraph_visa.py`'s fee query).
    3. **The citation rule has no exit.** `zantara_core.py:314` — "**MANDATORY LAW CITATION**: at
       the END of every response … you **MUST** cite the source law", and when the KB lacks the
       article, "cite the regulation name only". There is no licit path to cite NOTHING, so an
       operational question ("posso pagare con bonifico?") forces the model to invent a plausible
       statute — it produced **PP 36/2021 on WAGES**. Same mechanism cited immigration law as the
       basis for not sending a passport over WhatsApp. Two defects, one rule.
    4. **`QueryDomain.GREETING` maps to `[]` collections** (`query_planner.py:263`). A bare "halo"
       classifies correctly and then falls off a cliff: `package_unbuildable_greeting_domain`,
       5 failed attempts, **7m45s**, and an English technical-error stub to an Indonesian greeting.
       The greeting is the front door — most real clients open with exactly this. Published practice
       (Google Dialogflow CX, Rasa fallback) is a deterministic scripted greeting+capability turn
       reached BEFORE retrieval, never a generation attempt with no topic.
  - **🔴 THE BIGGEST FINDING IS NOT ON THAT LIST — THE ABSTAIN GATE IS BLIND ACROSS LANGUAGES.**
    `calculate_evidence_score` derives semantic relevance (0.0–0.6, explicitly the PRIMARY factor)
    from lexical keyword overlap with an **English-only stop-word list**. Measured on the live
    scorer: the SAME question against the SAME catalogue entry scores **0.08 in English context and
    0.80 in Indonesian context** — and symmetrically 0.80/0.08 the other way. **A factor of ten
    decided by language alone, against a 0.15 threshold.** `0.08` is not weak overlap: it is the
    "no semantic relevance" branch, `min(source_quality*0.2, 0.1)`. Second, independent defect in
    the same function: `if len(w) > 3` discards every token of ≤3 chars, so
    `"Harga PT PMA berapa all in?"` reduces to the two most generic words in it, `harga` and
    `berapa` — **`PT`, `PMA`, `NIB`, `OSS` are all thrown away**; `KITAS`, `NPWP`, `E28A` survive by
    an accident of length. **`_abstain_policy.py` ALREADY DIAGNOSED THIS in its own comment and
    answered it by LOWERING THE BAR** (`tax: 0.10`, `visa: 0.12`) — a workaround that relieves two
    domains, leaves the measurement broken everywhere, and reduces the safety gate to do it. **Do
    not add a third lowered threshold.** Spec (acceptance criteria, innocence requirements, golden
    set): `research/operations/2026-09-01-wa-evidence-relevance-cross-language-spec.md`.
  - **🕳️ AN ABSTAIN LEAVES NO RECORD.** `wa_outbox` and `meta_inbox_messages` carry **no**
    confidence, evidence or abstain column — verified by introspecting every `public` table for
    `confidence|evidence|abstain|score`. An abstain is stored as `status='done'`, byte-identical to
    a good answer; the only fall-off signal is `generation_fall_off_reason`, populated on 1 of 22
    rows. **Consequence: every past cycle called "green" proves nothing about abstains — they are
    invisible to any automated check and visible only by reading the text.** This blocks the spec's
    golden-set criterion in production. Separate ledger item.
  - **💰 CONFIRMED: THE E33E RENEWAL IS SOLD BELOW THE GOVERNMENT FLOOR. Rp 10.500.000 floor
    vs our Rp 10.000.000 all-inclusive price — we lose Rp 500.000 per renewal before any margin.
    BUSINESS DECISION (Legge 5), flagged to Zero 2026-09-01, NOT fixed by a session.** Verified by
    direct fetch of `imigrasi.go.id/wna/daftar-visa-indonesia/E33E`, which itemizes the Rp 13.000.000
    FIRST-ISSUANCE total verbatim as: `Biaya Visa tinggal terbatas Rp 500.000` + `Biaya Verifikasi
Visa Rp 2.000.000` + `Biaya Izin Tinggal Terbatas (ITAS) masa berlaku 5 Tahun Rp 7.000.000` +
    `Biaya Izin Masuk Kembali (IMK) masa berlaku 5 Tahun Rp 3.500.000`. A renewal is not an entry,
    so visa and verification do not recur: **ITAS 7.000.000 + IMK 3.500.000 = 10.500.000**. Tariff
    rows corroborated in PP 45/2024 Lampiran C (ITAS and IMK tables are keyed ONLY by duration —
    there is no separate, cheaper "perpanjangan" schedule to find) and by Kanim Jakarta Pusat's
    published fee table. **The escape hatch does NOT exist**: UU 63/2024 removed the separate IMK
    _document/application_, NOT the _fee_ — PP 45/2024 postdates that law and still carries a
    9-tier IMK tariff, and the government's own page bills IMK as its own line. **Root cause, and
    the actionable part: one inherited number across three products of different durations.**
    `E33E Extend` (5 years, floor 10.500.000), `E33F Extend` (1 year, floor ITAS 3.000.000 + IMK
    1.500.000 = 4.500.000) and `Retirement Extend` are ALL priced at Rp 10.000.000. E33F carries a
    healthy margin at that price; E33E is underwater — nobody recalculated when the duration went
    from one year to five. Residual uncertainty, declared: no single official sentence states "an
    E33E extension re-pays ITAS and IMK" — it is a strong convergent inference from duration-only
    tariff keying plus the analogous ITAP-extension page listing IMK as a cost component. Risk is
    ASYMMETRIC DOWNWARD: if a renewal also draws verification, the floor rises to 12.500.000.
  - **📘 REGULATORY FACTS ESTABLISHED FROM PRIMARY SOURCES (2026-09-01) — the corpus is WRONG on
    both, in opposite directions:**
    - **Passport validity is TWO rules, never one number.** NEW ITAS/VITAS application: _"Paspor
      Kebangsaan yang sah dan masih berlaku **paling singkat 6 (enam) bulan**"_ — Permenkumham
      22/2023 Pasal 34 (E23), 39 (E28A), 56 (E33), 61 (E33E), 62 (E33F), 63 (E33G); **flat, NOT
      scaled to permit length** — Pasal 62's FIVE-YEAR permit still asks 6 months, which refutes the
      "18 months for 1 year / 30 for 2 years" folk rule outright. **EXTENSION: no minimum at all** —
      Pasal 115 ayat (3) huruf a, _"**tidak mensyaratkan masa berlaku minimum** Paspor Kebangsaan
      yang sah dan masih berlaku"_, confirmed verbatim on imigrasi.go.id's Perpanjangan ITAS page
      (session-verified by direct fetch, as was the E28A page: "1 atau 2 tahun" permit, 6 months
      passport). Statutory origin of the "6": UU 6/2011 Pasal 8 ayat (1) penjelasan. **Our two
      stores BOTH carry a blanket constant and they disagree**: `visa_types` has "6 months" on
      **114 rows in 3 phrasings, zero rows say anything else**, identical on a 1-year and a 5-year
      permit; `training-data/visa/*.md` says "18 bulan" uniformly, including on the D1 tourist visa.
      Neither is per-product; neither encodes the extension waiver. The bot's answer was right on
      new applications and **wrong on extensions** — it sent a client to renew a passport for no
      reason.
    - **E33E is 55+, not 60.** **Permenkumham 11/2024 amended Pasal 61/62 lowering it**:
      _"lanjut usia berusia **55 (lima puluh lima) tahun** atau lebih"_. Our own KB agrees
      (`E33E - Retirement KITAS (55+)`, `age_requirement: "55+"`), as does the price list
      ("Senior 55+ route"). The bot answered 60 — **it is reading the pre-amendment 2023 text**.
      Not a slip: expired corpus. A 56-year-old asking for E33E is being turned away.
  - **🧪 PANEL DISCIPLINE — a cross-family verdict is not a fact.** Gemini ranked "PT PMA paid-up
    capital is Rp 10 miliar, not 2.5" as defect #1 at **stated 100% confidence**, citing
    **BKPM 4/2021**. It is **WRONG**: the bot cited the newer **BKPM 5/2025**, our Stage-1 frozen
    fixture verified 2.5 mld against it under adversarial review (Kimi K3, 2026-08-19, SHA-256
    pinned), and **Codex PASSED the same answer**. Adopting that verdict would have turned the one
    answer that had IMPROVED since July into a wrong one. Gemini's second factual claim (passport
    18/30 months) is refuted above by the regulation itself. **Codex Sol was the strongest seat** —
    it alone caught the below-floor E33E price and the Q18/Q5 privacy contradiction, and it alone
    said "unsure" where it did not know (the E33F threshold). Weight seats by whether they mark
    their own uncertainty.
  - **🔐 THE PRIVACY RULE DOES NOT SURVIVE THE THREAD.** Q5 correctly refuses a passport photo in
    chat; seven turns later Q18 asks for _"nama lengkap + nomor paspor"_ — precisely the pair that
    binds a person to their document, on a channel with history, backups and exports. Avoidable
    UU PDP exposure. Ask for the eVisa application number only; if absent, an authenticated link.
  - **🌐 LANGUAGE IS THREAD-STICKY AND IT BIT US.** An Italian question at Q14 made Q20 answer an
    Indonesian question entirely in Italian, six turns later. Note for whoever fixes it: this is
    **industry-standard behaviour, not a unique bug** — Zendesk documents per-conversation sticky
    detection as deliberate. The evidence-backed shape is current-message detection as PRIMARY with
    thread-sticky as FALLBACK for messages too short to classify (~<5 words), never the reverse;
    a stored client language preference outranks both.
  - **📏 METHOD SCAR, MINE.** My overnight corpus sweep reported "5 offenders, 808 scanned, 1
    residual" and was **falsely reassuring**: it searched the phrasings I had catalogued
    ("we always show the two figures separately") and missed "**We always keep these two costs
    distinct**" — the same teaching, different words. Scan for the FACT (any government-fee token),
    never for the phrasing. W82 class. I also graded three answers too generously (Q5, Q10, Q18);
    Codex found all three.
  - **⏱️ CADENCE BREACH, for the record**: 22 messages in 56 minutes against a stated ≤10/hour
    limit. That limit protects the number's Meta quality rating, which was GREEN before and after.

- **🔇 THE PRODUCT HAS SERVED NOBODY SINCE 2026-07-30 01:23:58Z — 24 DAYS — AND EVERY GAUGE READ
  GREEN THE WHOLE TIME (measured 2026-08-23 on Fly prod, read-only SQL; this supersedes every
  entry below as the lane's actual state, because they all describe a lane whose product was
  already off the air).** The daemon-revival entry immediately below is TRUE and was worth doing;
  it is also not the thing that mattered, and neither was the DLP batch shipped the same morning.
  Both landed on a code path that was carrying **zero client traffic**.
  - **The two signals that speak for the product**, both measured on machine `1781e5eda03438`:
    last `wa_outbox` row with `status='done'` = **2026-07-30 01:23:58Z**; last `inbound_webhooks`
    row where `channel='whatsapp'` = **the same instant**. Zero inbound in the last 7 days.
    `wa_outbox` totals 325 rows, 217 of them `failed`. Delivery-STATUS webhooks
    (`wa_status_pending`) kept arriving until 2026-08-14 13:25Z — so Meta was still talking to us;
    it is the MESSAGE webhooks that stopped.
  - **Why nothing went red.** Simultaneously green: `/health` 200 + DB connected; the broker gauge
    advancing every 30s; `breaker_state='closed'`, `consecutive_failures=0`; the codex seat probe
    `{"verdict":"ok"}`; `WA_INBOUND_BOT_AUTOREPLY='true'`. Every one measures a COMPONENT. None
    measures THROUGHPUT. The broker gauge proves the daemon is polling — it polls an empty queue
    exactly as eagerly as a full one. **A queue depth of zero and a queue depth of
    zero-because-nothing-arrives are the same number.** Nothing in the repo watched the difference:
    `grep -rln "inbound_webhooks" scripts/` returned nothing, and `wa_mirror_freshness_liveness.py:104`
    watches `whatsapp_message_context` — the personal-mirror table, last written 2026-05-25 — not
    the bot product. **The missing organ is PR #4630** (`scripts/wa_bot_throughput_sentinel.py`):
    replayed against this incident it fires p0 at **+1.5h**, and an exhaustive 10-day scan bounds
    its longest silent window at 13.0h (one overnight).
  - **Ruled out with evidence, each re-measured, not inferred**: Meta token — `debug_token`
    `is_valid:true`, `expires_at:0`, SYSTEM_USER, 41 scopes incl. `whatsapp_business_messaging`.
    Phone `1104946272705747` — `+62 821-3465-159`, `verified_name:BALI ZERO`,
    `quality_rating:GREEN`, CLOUD_API. WABA `1236411107897853` — `account_review_status:APPROVED`.
    Our endpoint — `GET /webhook/whatsapp` answers **403** to a wrong `hub.verify_token`, i.e. the
    Meta handshake works. Code — `git log --since=2026-07-26 --until=2026-08-03 --
.../routers/whatsapp_chat.py` is **empty**; the only backend commit in the 07-29..07-31 window
    is a frontend pricing change. Flag — autoreply is `'true'`.
  - **STILL OPEN, and it needs a phone**: `GET /{WABA}/subscribed_apps` answers
    `500 {"code":1,"error_subcode":99}` reproducibly (3/3), which is consistent with a lapsed
    `messages` subscription but does not prove it. The discriminator is one WhatsApp message sent
    to the number from a handset (`operator[physical]`): a row appearing in `inbound_webhooks`
    within seconds means the subscription lives and clients simply stopped writing; nothing
    appearing means it is gone and is restored from Business Manager (`operator[gui]`).
  - **The separate downstream disease, now named by query.** The 217 failures decompose as: **94
    `24h_window_closed`** (2026-06-17 → 2026-08-14), 62 `superseded_by_coalescing` (benign burst
    dedup), 44 `auto-reply not enabled` (June, flag genuinely off), ~17 assorted (RAG abstained /
    empty answer / 500 / 401) — across 38 threads, of which only 4 carry `human_handling=true`,
    which kills the human-takeover explanation. The 94 are **not wasted RAG calls**: control flow
    is `:734` status→generating, `:754` ack, `:797`/`:823` generate, **`:962` persist body**,
    `:1034` window check, `:1061` fail — so the answer IS written to `meta_inbox_messages.body`
    before the window check discards the send, and `wa_inbox.py` (the human takeover queue) reads
    those rows. The cost is real, the draft survives. Moving the check before generation would save
    the call and destroy the draft — a trade-off, **not an obvious win**, and it turns on whether
    anyone actually works that queue. Owner decision, not a session's.
  - `attempts=0` on the failed rows is not a puzzle: of the seven paths that set `status='failed'`
    in `wa_outbox_worker.py`, only `:868` and `:1085` increment `attempts` first; `:675`, `:704`,
    `:1012` and `:1047` (the 24h check) all fire on the generation-SUCCESS path. Same reason
    `apology_sent_at` is NULL on all 325 rows — `_maybe_send_apology` is only reached from the two
    incrementing paths, so those 94 clients were never even told the bot had given up. (Outside the
    24h window Meta forbids free-form messages anyway, so an apology is not sendable without an
    approved template — a platform constraint, not our bug.)
  - **🔴 SECURITY, independent of the outage, found on the way**: `WHATSAPP_APP_SECRET` and
    `META_APP_SECRET` are **both UNSET** in prod, and `_verify_whatsapp_signature`
    (`whatsapp_chat.py:1163-1167`) does `return True` when the secret is missing — documented as
    "dev mode". The production webhook therefore **accepts unsigned POSTs**: anyone who knows the
    URL can inject forged inbound WhatsApp messages, which are persisted and processed. Closing it
    needs the App Secret from Business Manager (`operator[gui]`), then `fly secrets set`.
  - Memory: `discovery_the_whatsapp_bot_answered_nobody_for_24_days_while_every_gauge_read_green_2026_08_23`.

- **💀 THE PRO DAEMON HAS BEEN DEAD FOR ~70 HOURS AND EVERY HEALTH INDICATOR READS GREEN — the
  S3-ARMED entry below is not wrong, it EXPIRED 2.5 hours after it was written (2026-08-23,
  measured on Pro at SHA `148f0bfca`, probes between 01:00Z and 01:40Z).**
  - **The state.** `launchctl print system/com.balizero.wa-codex-broker` → `active count = 0`,
    `state = spawn scheduled`, **`runs = 7514`**, **`last exit code = 1`**, `job state = exited`;
    zero matching processes in `ps`. Downstream ground truth — prod
    `SELECT * FROM wa_broker_gauge` via `fly ssh console` — **`broker_last_seen_at =
2026-08-20 03:45:11Z`**, frozen, while `breaker_state = closed` and
    `consecutive_failures = 0`. **The breaker is green because the daemon never connects far
    enough to fail.** A dashboard reading it reported health for the whole outage.
  - **🔻 Cause — HALF identified, and the first draft of this entry got it WRONG. An adversarial
    pass (Kimi K3, on the frozen diff) forced the correction; this is the corrected version.**
    The tempting story was pure pin drift: `wa_codex_daemon.run_forever()` raises `RuntimeError`
    BEFORE the loop when `codex --version` ≠ `WA_CODEX_CLI_VERSION_PIN` — fail-closed by design
    (spec chaos row 8), comment _"a daemon that cannot legally exec must not sit green (scar
    family #2)"_ — uncaught → exit **1** → `KeepAlive{SuccessfulExit:false}` +
    `ThrottleInterval 30` relaunches forever. **The timeline refuses that as the ORIGINAL cause.**
    Stamps: gauge froze **03:45:11Z 08-20** · **Pro REBOOTED 09:49:54Z 08-20**
    (`sysctl -n kern.boottime`) · **codex-cli 0.149.0 installed 20:45:25Z 08-20** (`stat` on the
    resolved binary) · measured ~01:20Z 08-23. Two arithmetic consequences: (a) **launchd's
    `runs` counter resets at boot**, so the 7,514 restarts span the **63.50 h since boot** —
    implied spacing **30.42 s** against a 30 s floor; (b) the window since the CLI upgrade is only
    52.58 h, capping restarts at **6,309** at that floor, and we observe **7,514** — **so the
    crash-loop began at least 10 h BEFORE the upgrade.** The pin mismatch is therefore a real
    **second** cause (certainly active since 20:45Z 08-20) layered on a **first cause that is
    still unknown** and lives in a root-only log. The gauge also froze **6.08 h before the
    reboot**, so the daemon was already failing under the pre-reboot launchd session.
  - **⚠️ WITHDRAWN from the first draft, so nobody re-derives it:** that draft read the implied
    spacing as "throttle floor + ~3.3 s of real work per cycle" and offered it as evidence the
    process reached the `codex --version` call. It proves nothing — `ThrottleInterval` is measured
    **from launch, not from exit**, so any runtime under 30 s yields the same ~30 s spacing. It
    was also computed from the wrong start time.
  - **The bump is safe — and NOW it is genuinely verified rather than assumed.** `codex --version`
    prints `codex-cli 0.149.0` and the daemon's own `_SEMVER_RE` (`(\d+\.\d+\.\d+)`) parses it to
    `0.149.0`, so a pin of `0.149.0` matches. The adapter's exact call shape — `_FIXED_ARGV_PREFIX`
    = `exec --sandbox read-only --skip-git-repo-check --ephemeral --ignore-user-config
--ignore-rules` plus the `-` stdin sentinel, **all five flags together** — ran live against
    0.149.0 today and returned its expected token, rc 0. (The first draft probed with ONE flag and
    still said "verified"; that is what made the claim overstated then.) **But safe ≠ sufficient:
    the bump clears a blocker that certainly exists now, it does not address the first cause.**
  - **Not a HOME-fork.** `cmp -s /usr/local/libexec/wa-codex-broker-wrapper.sh
infra/launchagents/wrappers/…` → IDENTICAL. Superscar #1 is clean here; this is #2.
  - **The seat sentinel — the organ that would have caught this within the hour — was never
    armed, and the reason is not an operator error.** `/usr/local/var/wa-codex-broker` does not
    exist and `crontab -l | grep -c seat-sentinel` = 0. Zero DID run the provisioning on 08-20
    (the installed wrapper + runtime tree, `08:39` local = `00:39Z`, prove it) — but the
    seat-probe section was added by **#4405 (`ecd3a3da0`), merged 07:48Z the same day**, AFTER
    that run. **A provisioning run cannot install a section that does not yet exist.**
  - **The meta-pattern, worth more than the incident.** Three organs each behaved correctly and
    the chain still went dark: the daemon refused loudly; the wrapper's sidecar is deliberately
    unwatched (`expected_hb_seconds=0`, because the wrapper itself names the server-side gauge as
    the ground truth); and the gauge went stale with the breaker still reading green. **Not a
    component that lies — a correct fail-closed refusal wired to an alarm channel nobody armed.**
    Same lesson the ledger already carries in another costume: _"armata" non è uno stato, è un
    istante_ — the 08-20 entry was TRUE at 01:11→01:12Z and nothing existed to notice it stop
    being true.
  - **Cure = READ THE LOG FIRST, then the pin bump** (`operator[credential]`: both
    `/Users/zantara-codex/logs/wa-codex-broker.err` and the `0600` env file are root/other-user
    owned, and Pro has no passwordless sudo — probed). **Do not skip the log**: the pin bump alone
    may leave the daemon down, because it does not touch the first cause. Re-running the
    provisioning does not touch the pin either — it skips an existing env file by design. Exact
    paste + the correct proof-of-armed in
    `research/operations/2026-08-23-bot-subscription-path-readiness.md` §3. **Prove it by two
    ADVANCING gauge reads, never by one fresh-looking timestamp and never by `breaker_state`.**
  - **Ladder status from Zero, today:** **G-P2** (Art. 56 basis artifact) — _"non ora"_, stays
    `operator[business]`, and it is the ONLY item no amount of building can advance. **G-P6**
    (bounded credential residual) — **ACCEPTED at the §4.2 bound**, recorded; **the gate is NOT
    closed**, because the spec's own row requires the bound to be _verified, not assumed_ (scope
    inventory of what a stolen `auth.json` reaches + a revocation test) and neither probe has
    run. **WhatsApp is still served by Gemini** — `WA_GENERATION_PROVIDER` is absent from
    `fly secrets list -a nuzantara-rag`, so it defaults off, as intended.

- **📉 IMPLICIT PREFIX-CACHE: VERIFIED HEALTHY, NOTHING TO BUILD — July's 0% was the LEDGER'S
  blindness, and the live answering model has been the FALLBACK since 08-10 (2026-08-20, measured
  on `llm_cost_events` read-only + git forensics; adversarial pass: Kimi K3 — 2 claims tightened,
  1 refuted and re-cured with new queries).** The 2026-08-11 panel bullet below left ONE caching
  task: verify the byte-identical static prefix. Done:
  - **The request shape is cache-correct.** Assembly traced on origin/main: static template first
    (`{today_wita}` at char ~87 = daily variance only), `{user_memory}` at 83-90% of the template,
    `{query}` right after it, per-request blocks (curated_qa grounding, KG workflow, entities)
    tail-appended via `additional_context`, the self-correction retry resends the system prompt
    byte-identical, chat contents append-only. Static prefix ≈8.2k tokens (char-derived,
    corroborated by the hit sizes below) — above the implicit-cache minimum, which on the 3.x
    family is **4,096 tokens (up from 2,048 on 2.5; ai.google.dev/gemini-api/docs/caching,
    fetched 2026-08-20)**.
  - **`system_instruction` participates in the prefix match — settled by construction, not by
    clustering**: two gateway calls at 08-09 21:57Z have `input_tokens` 10,631/10,757 with
    `cache_hit_tokens` 8,166/8,167 — their contents were ~2.5k tokens, SMALLER than the hit, so
    the matched prefix can only include the system prompt. (The distribution agrees: 286 hits,
    min 7,923 / p25 8,183 ≈ the static prefix; p50-p75 at 12-14k = matches extending past it
    into user_memory and/or contents.)
  - **The gateway ledger was BLIND until 2026-08-09 17:47Z.** #2845 (07-19) started recording
    gateway cost events without extracting `cached_content_token_count` (its diff contains zero
    cache fields), so `cache_hit_tokens` sat at 0 by construction; #3914 wired
    `extract_gemini_usage` into the gateway and the first real gateway hit appears 36 minutes
    after its merge (18:23Z). July's 0.0% over ~23M input tokens is unmeasured and not
    recoverable from the ledger — do NOT read it as "caching was broken", and do NOT read the
    per-model aggregates (3.5-flash "2.1%" vs 2.5-flash "12.4%") as a model property: 3.5's
    denominator is ~100% blind tokens (its traffic ended 08-09), while 2.5 carried the sighted
    days. The same artifact explains the verifier's 0-of-483 on 3.5 vs 9.5% on 2.5.
  - **Sighted hit rate: 11-21% of input tokens on the probe-burst days** (08-09/10/11), ~16% of
    calls with any hit (286 of ~1,776). The ceiling on cold same-bucket bursts is ~50% (8k prefix
    on 16k avg input); no shape defect was found in the traced assembly — the residual gap is
    attributable to Google's best-effort TTL/routing PLUS prefix fragmentation (per-language
    byte-0 header, team/creator persona prepends), which this data cannot apportion. The only
    code-side lever left is EXPLICIT caching, which per the panel's own math pays only above
    ~3.6-4.8 calls/hour sustained; background traffic is **3-17 calls/DAY (~$0.05/day)** —
    SKIPPED, with numbers.
  - **The verifier caches only across self-correction re-verifications** (shared
    preamble+query+context prefix; only the draft differs): 110 hits on its 2.5 rows, min 238 /
    p50 ~2k ≈ the shared portion, 63% of input when it hits. Its ~55-token static preamble alone
    can never meet any documented minimum — fine as-is, nothing worth restructuring.
  - **🔀 SIDE-FINDING, corner-correcting: the live answering model is `gemini-2.5-flash` since
    2026-08-10** — 100% of `rag.gateway.chat` rows since then (1,615 calls), zero 3.5 attempts
    recorded. Mechanism found in git, not guessed: #3939 (merged 08-10, "wire the model knob that
    already existed as a secret nobody read") made the RAG honor the pre-existing
    `PRIMARY_MODEL_NAME` Fly secret — the same secret the credit-sentinel bullet below records as
    `gemini-2.5-flash`. So the #2611 promotion to 3.5-flash was silently undone by wiring the
    knob: deliberate mechanism, but whether 2.5-as-primary is the INTENDED steady state is a Zero
    call nobody has made explicitly. (Cache-wise it is mildly favorable: 2,048 minimum vs 4,096.)
  - **The #1 consumer of the metered seat is our own probing, not clients**: the 08-09→08-11
    probe batteries burned ~$13 (28M input tokens, 1,695 gateway calls) against a ~$0.05/day
    background. Future batteries: fire the variants inside a tight time window and reuse
    phrasings — the docs' own guidance is "send requests with similar prefix in a short amount
    of time"; on 08-10 that shape got 13.9% cached for free.
  - **Consequence for the "semantic cache + local intent tier" lane** (2026-08-19 near-free-tools
    panel, lane 1): PREMATURE at ~0 client traffic, and cache hits bypass the abstain gate (§2
    truth #4) so it is safety-sensitive by construction. Deferred to go-public, not built
    quietly.
  - Small gap, noted not built: 1,089 calls / 0.8M input tokens in 45d carry an EMPTY `endpoint`
    label in `llm_cost_events` — unattributed call sites.

- **⚡ BOT-V4 S3 ARMED (2026-08-20) — THE PRO DAEMON IS LIVE AND HEARTBEATING IN PROD; THE LANE
  IS NO LONGER DARK SERVER-SIDE, STILL FLAG-OFF FOR WA (supersedes the S2 headline below as the
  lane's current state).** Zero executed the three operator steps on Pro (provisioning script @
  `7f64f86a1`, 08:39 WITA; one-time `codex login` as zantara-codex — `codex-cli 0.147.0`,
  matching the env pin; `sudo launchctl bootstrap system`); the session minted `WA_BROKER_KEY`
  entirely in root-land (python heredoc → 0600 env file + 0600 `/var/root` import file) and
  shipped it WITH the canary record in ONE `fly secrets import` on stdin — the key never touched
  argv, shell history, or the session transcript. Proof-of-armed, all measured: `launchctl
print` → state=running, pid 78690, never exited, user zantara-codex; `wa_broker_gauge` row
  present AND ADVANCING (`broker_last_seen_at` 01:11:48Z→01:12:48Z, breaker closed, 0
  consecutive failures) — the daemon itself is the keyed prober, so keyed claims are landing
  200 end-to-end without any session ever holding the key; unkeyed claim still 401 (negative
  control); `rag` machine STARTED on the post-import release (scar checked, did not bite).
  Benign measured footnotes (recorded in the closing PR's script comments): sysadminctl's
  `-password` did not take — the account has NO `AuthenticationAuthority`, which is safer (no
  hash, nothing to authenticate against) and it did not hang; the runtime venv is Python 3.14.6
  (daemon needs stdlib+httpx only). **WhatsApp still runs on Gemini** — what remains before any
  real client text: the seat sentinel (own PR, ledger row), the G-P1..P6 ladder, and the S4
  cutover which is the owner's switch alone (`WA_GENERATION_PROVIDER` — no session may flip it).

- **🏗️ BOT-V4 S2 BUILT AND DEPLOYED FLAG-OFF (2026-08-20) — THE BROKER EXISTS IN PROD, DARK;
  THE PRO DAEMON EXISTS ON MAIN, UNPROVISIONED; REAL WA STILL NO-GO (supersedes the spec-shipped
  headline below as the lane's current state).** Six PRs, every one through the adversarial
  gate before merge (generator≠grader; Codex seat quota-dead until Aug 22 → Kimi K3 was the
  cross-family seat): #4346 (router+service+m270) · #4348 (leg) · #4347 (worker wire) · #4351
  (finalization) · #4373 (package wire + m271-274) · #4377 (Pro daemon + process-group kill +
  provisioning; Kimi ladder FIX-FIRST(9)→cured→SHIP→hygiene-cures→SHIP on the cure delta).
  Single S2 deploy from Pro 2026-08-19T22:15Z (v4154): migrations 270-274 verified in the prod
  ledger by direct query; PROVE-LIVE green — `/health` 200, `POST /api/wa-broker/claim` and
  `/complete` answer **401 "wa-broker key required"** without a key (live but dark, by design),
  `rag` machine STARTED post-deploy (the stopped-after-deploy scar did not repeat), `drive†`
  standby. First deploy attempt aborted honestly: the release machine died pulling the 628MB
  image inside flyctl's default wait — retry with `--release-command-timeout 10m` landed it;
  migrations never ran on the failed attempt (verified by its logs: only "Pulling container
  image"). Merge-queue footnote: the PR was ejected TWICE by the known apt-mirror stall in
  `scripts/ci/apt_install.sh zsh` (W118 class, now failing loud with a named cause — the
  CodeQL reds on the queue refs were the ejection's EFFECT, completed minutes after);
  third traversal merged. Engineering findings worth reuse: CPython 3.11
  `BaseSubprocessTransport._wait()` resolves only when ALL pipe transports disconnect — an
  orphaned grandchild holding inherited stdout keeps `proc.wait()` pending forever on a dead,
  OS-reaped child (measured >90s), hence the daemon client's bounded reap
  (`_REAP_ABANDON_S=5s`) + `start_new_session` + `killpg`; and the /complete byte-cap must be
  measured with the EXACT wire encoder (`_encode_body` is both measuring stick and wire —
  60k 3-byte chars pass the 65,536-char cap and 413 at the router's 128KiB stream cap).
  **WhatsApp still runs on Gemini** (`WA_GENERATION_PROVIDER` defaults off, test-pinned).
  What remains before any real client text: Pro provisioning + codex login (ledger rows,
  operator-gated), Fly secrets `WA_BROKER_KEY` + `WA_CODEX_CANARY_TOKENS`, seat sentinel,
  the G-P1..P6 ladder, and the S4 cutover which is the owner's switch alone.

- **📐 BOT-V4 BROKER SPEC SHIPPED (#4333, merged 2026-08-19T00:47:54Z) — THE CHATGPT-PROVIDER
  ROUTE NOW HAS A PANEL-SIGNED BUILD CONTRACT; STILL DOCS-ONLY, REAL WA STILL NO-GO (2026-08-19,
  supersedes the liveness-smoke headline immediately below as the lane's current state).**
  Zero closed the account-privacy gate by attestation and ordered the transition («già fatto,
  quindi passiamo a chatgpt» — recorded in memory
  `decision_wa_openai_provider_subscription_path_owner_ruling_2026_08_15`, §2026-08-19). The
  resulting spec (`research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md`) went
  through FOUR adversarial rounds — Codex GPT-5.6 BLOCKED(22)→BLOCKED(5 NEW)→FIX-FIRST(4)→SHIP,
  Kimi K3 FIX-FIRST(10)→FIX-FIRST(3)→FIX-FIRST(2)→SHIP, agy SHIP, plus a fresh-context Sonnet
  proofread that caught a real stale-sibling contradiction — every finding dispositioned in the
  spec's §8.
  - **Architecture that survived the panel** (v1's pull-park design did NOT): the broker leg
    runs SYNCHRONOUSLY inside the existing `wa_outbox` claim — thread lock held, zero new row
    states, coalescing/fence/reclaimer untouched by construction; a new `broker_jobs` table is
    transport with a full PII lifecycle (`completed_pending_consume`→`consumed`, payload
    NULL-at-terminal, verified 7d purge); ONE finalization pipeline serves both providers so
    every gate runs on the RETURNED text; the codex path uses deterministic retrieval
    (conditionally Gemini-free — an S2 zero-LLM acceptance test decides, not an assertion);
    Pro side runs as a dedicated login-less `zantara-codex` user with egress secret/canary
    scans.
  - **Stage-1 pre-registration is FROZEN at the same merge**
    (`research/operations/2026-08-19-bot-stage1-registration.md` + 72 synthetic fixtures in
    `scripts/bot/fixtures/stage1_synthetic/`, SHA-256-pinned): 6 scoring categories, zero
    tolerance on fabrication/scaffold-leak/price-splitting with dual-scorer adjudication,
    per-domain accuracy floors, transport-error and scorer-blinding invalidation rules. Kimi K3
    refuted it (FIX-FIRST, 5 gate-coverage findings, folded before the freeze) → SHIP. The 4
    encoded facts verified: 2.5 mld paid-up (BKPM 5/2025), 80y Hak Pakai + 80y HGB (PP 18/2021),
    Rp 1,000,000/day overstay (PP 45/2024).
  - **What is still NO-GO, by the spec's own ladder**: real client text touches the codex route
    only after gates G-P1..P6 (live Codex data-control verification `operator[gui]`; UU PDP /
    Art. 56 basis artifact `operator[business]`; named DLP policy with measured recall;
    shadow-sink design; quota classifier from S1.5; owner acceptance of the probed credential
    residual). Cutover (S4) is the owner's switch alone. Next build step: S2 flag-OFF per the
    spec; S1/S1.5 can run offline in parallel.

- **🧪 CHATGPT PRO ADAPTER LIVE TEST — SYNTHETIC LIVENESS SMOKE GREEN (NOT the full Stage 1
  evaluation); DORMANT ADAPTER MERGED + DEPLOYED; REAL WA STILL NO-GO (2026-08-19, supersedes
  the stale #4216/#4301 implementation snapshot immediately below).**
  Zero authorized the start of live testing on 2026-08-18 (route + advance authority recorded in
  memory `decision_wa_openai_provider_subscription_path_owner_ruling_2026_08_15`, §2026-08-18
  riconferma; the label "point 7" used by earlier drafts was that session's own checklist
  numbering and resolves to nothing in this corner or the plan), scoped to synthetic,
  de-identified, operator-controlled probes only. #4216 source head
  `6cb663dd66c67ed8d84dc204508eafe3c6d0c5de` carries a 12-file net diff and remains strictly
  NO-WIRING.
  Independent Fable review repeated 513/513 focused tests, confirmed the 12-file/no-importer
  fence, returned PASS, moved #4216 to ready, and armed the canonical queue. The unchanged head
  was ejected twice by required merge-group `Immune enforcement` runs `32157479924` and
  `32159641457`: both failed only at `Codex seat corpus` after 71s/79s, with no output after step
  start because bounded `apt_install.sh zsh zsh` could not deliver `zsh`; neither pytest corpus
  started. The affected CI/helper/test blobs were identical across PR/merge-group/main, while the
  PR run and local re-runs passed 13/13 + 14/14 + 56/56. A rerun of only the failed workflow
  (same code, no change) then passed in 5m59s (`apt update` timed out, cached install delivered
  `/usr/bin/zsh`, and both 14/14 + 56/56 corpora ran). Independent Fable issued
  `PASS-REQUEUED-FINAL`; the third and explicitly final merge-group
  `67eb3be94cb9be9abaae00b372446389e971cf4f` passed all 26/26 workflows. GitHub merged #4216 at
  `2026-08-18T17:26:10Z`, and `origin/main` was independently observed at that exact commit.
  CI deploy workflow `32165589346` then passed on that same SHA: pre-deploy validation + 82 core
  tests, pre/post SQL and Python migrations, Fly rolling deploy (6m22s), health, and synthetic RAG
  smoke all succeeded with no rollback. An independent probe returned `HTTP 200` and
  `{"status":"healthy"}` from `https://nuzantara-rag.fly.dev/health`. Commit-pinned inspection
  confirmed the adapter is present but has zero runtime importer, config flag, or gateway
  reference outside the two dormant adapter modules and their tests: deployed does **not** mean
  activated, serving, shadowing, or connected to WhatsApp.
  On Pro, `codex-cli 0.147.0` reports `Logged in using ChatGPT`. From the exact PR head, a real
  `CodexExecClient` Terra call returned an exact random synthetic sentinel in 6.9s. The role-aware
  multi-turn blind harness then ran sequentially across Terra/Luna/Sol and all 3/3 returned the
  exact synthetic token from the prior user turn (0 errors; 8.6s/6.6s/6.7s).
  No WhatsApp, Meta, CRM, DB, Qdrant, client, or OSINT input was read; no message was sent.
  Observed isolation: no API key forwarded, no session file change, no sentinel persistence hit,
  no child/tempdir residue, owner-only `0600` ephemeral artifacts deleted after inspection.
  Two gates were discovered live: (1) non-login Pro processes need a `PATH` including
  `/opt/homebrew/bin` because `codex` is a Node shebang script — `WA_CODEX_BIN` alone cannot find
  `node`; (2) codex-cli echoes the prompt into its private transient stderr pipe, although the
  adapter never logs, persists, returns, or exposes that pipe on success; on a non-zero exit it
  scans that stderr only after whole-line stripping of the echoed prompt and surfaces only
  sanitized typed errors, never the raw pipe. The authenticated seat
  is personal ChatGPT Pro; its account-level **Improve the model for everyone** setting is not
  yet verified. Official policy says Pro Codex conversations may be used for training unless that
  control is off. Therefore the live verdict is **GO only for synthetic, de-identified,
  operator-controlled Pro probes** and **NO-GO for client text/PII, WA mirror, live shadow, Fly
  credentials, activation, serving, cutover, or any outward test send**. The completed CI-green
  merge/deploy changed code availability only and did not activate the provider. The corrected
  authoritative plan is
  `research/operations/2026-08-18-bot-openai-shadow-wiring-plan.md`; next gate is the account
  privacy check plus a named Pro-side fail-off broker/supervisor design and independent review.
  Generator-not-grader and Legge 5 remain unchanged despite the owner authorization.
  **Current state of the two gate-prep PRs** (the historical snapshot's DRAFT/BLOCKED wording for
  them is superseded too): #4194 (threat model + privacy plan) and #4197 (failure matrix) were
  reconciled to the final adapter evidence head `1dcdd670d` — subscription-provider coverage,
  single-token `adversarial_review: kimi-k3` frontmatter, Fable gate recorded in the documents'
  own Adversarial-review sections (the PR descriptions still carry draft-era text) — then
  un-drafted and entered the merge queue on 2026-08-19.

- **🤖 HISTORICAL OPENAI WA-PROVIDER SNAPSHOT — SUPERSEDED BY THE LIVE TEST ENTRY ABOVE.**
  Retained only as the chronology that produced #4216/#4301; do not use its old branch heads,
  merge status, bench shape, or authorization wording as current state.
  This lane is governed by two session memories, not by this file — `.agents/skills/bot/SKILL.md`
  said nothing about it before this entry: `decision_wa_openai_provider_subscription_path_owner_ruling_2026_08_15`
  (Zero's 2026-08-15 ruling: WA runtime OpenAI provider goes through the **ChatGPT Pro
  subscription** via headless `codex exec`, NEVER a per-token `OPENAI_WA_PROVIDER_API_KEY` —
  supersedes the 5-family council's NO-GO-on-subscription verdict, residual ToS risk accepted by
  the owner) and `project_bot_openai_lane_governance_codex_orchestrator_2026_08_15` (fence:
  implementation lane in `.worktrees/bot-openai-adapter` is client-standalone + tests + ADR
  **NO-WIRING** only — config.py/llm_gateway.py/secrets/deploy/real-traffic all forbidden; close
  gate is freeze diff → lead net-diff check → **final Kimi K3 + Google/agy Gemini review of the
  FROZEN diff** → only then a PR). Zero reconfirmed the ROUTE on 2026-08-18 — this is a GO to
  keep advancing the lane, strictly inside that existing governance; it does **not** authorize
  wiring or a live WA-channel cutover.
  - **#4216** (adapter, `feat(bot): OpenAI WA provider lane (NO-WIRING)`) — its own body says
    `DRAFT — HOLD. Not for merge. Remaining gates before any wiring: security review +
shadow-hook design`, i.e. the hold is **not** the route question (that paragraph calls the
    business/cost gate CLOSED) — it is two separate, still-open technical gates. Also
    `mergeStateStatus=DIRTY`/`mergeable=CONFLICTING` against current `origin/main` as of this
    check — readying it would not even let CI run (0-workflow DIRTY pattern, cicatrix #9 "Gate
    e required"), and resolving the conflict would touch the "frozen head `b7b2d6652`" the whole
    28-round review chain was run against. **Left in draft.**
  - **#4194** (verifier V1/V4, `docs(bot): OpenAI-provider threat model + privacy plan`) — the PR
    body reads as complete, but the doc it ships (`research/operations/2026-08-15-bot-openai-provider-threat-model.md`
    on that branch) says otherwise, in its own text, as of its last commit (`28f70f026`,
    "freeze-review prompts updated ... **Still not executed — standing by for team-lead's
    explicit freeze signal, per the HOLD order**"): a `§Freeze re-review` section titled
    "prepared prompts, NOT YET RUN", and the fence-compliance checklist states plainly `#4194
... stays DRAFT/HOLD throughout and updates only against the frozen diff`. The doc reviewed
    commits `b36fc9521`/`8a7aa9be5`; #4216's actual frozen head is `b7b2d6652` (4 boundary
    commits) — a later state than what got reviewed. Today's route reconfirmation is not the
    "team-lead's explicit freeze signal" this doc is waiting for (a different, technical
    checkpoint). **Left in draft — trust the artifact's own self-declaration over its PR
    summary (W65/W113 discipline).**
  - **#4197** (BOT-V3 failure matrix, `docs(bot): failure matrix, idempotency, rollback proof`) —
    content-checked, not just status-checked: its frontmatter still frames the choice as the
    OLD council recommendation ("NO-GO on ChatGPT/Codex OAuth ... CONDITIONAL-GO on the OpenAI
    API"), which the 2026-08-15 owner ruling **inverted**. Grepped the doc on that branch for
    `codex_exec`/`codex.exec`/`subscription provider`/`owner ruling`/`ADR §30`/`supersede`:
    **zero hits**. Every failure-matrix row analyzes `openai_responses_client.py` (the dormant
    API-key alternative) as "the OpenAI shadow" — none analyzes `codex_exec_client.py` (the
    actually-selected provider, subprocess/stdin auth-death failure modes, not HTTP
    401/429/5xx). `mergeStateStatus=BLOCKED`. **Left in draft** — readying it would present a
    gate-prep document as covering the chosen provider when it covers the shelved one.
  - **Net**: none of the three PRs met the "body declares deliverable complete AND the only hold
    was the route" bar this session was given to ready them on. Two hold on gates unrelated to
    the route (#4216 security-review/shadow-hook-design, #4197's content gap on the wrong
    provider); one (#4194) explicitly says it is waiting for a freeze signal this session cannot
    supply on its own authority. Whoever runs the actual freeze re-review (Kimi K3 + Google/agy
    on the frozen `b7b2d6652` diff) should also update #4197 to cover `codex_exec_client.py`
    before that PR is judged complete.
  - **#4301 plan red-teamed and narrowed 2026-08-18.** The first draft called for a default-OFF
    shadow flag and incorrectly said the existing corpus/bench could prove context parity,
    tool-calling shape, and #4197 rows. Independent Kimi K3 (`FIX-FIRST`) and Gemini 3.1 Pro
    (`BLOCKED`) both rejected that claim: `wa_blind_bench.py` exercises the dormant Responses API
    key lane, the ADR declares the corpus V5-INCOMPLETE (synthetic-only, role-blind, single-turn),
    and `CodexExecClient` has only a single text prompt rather than Gemini's native system/history/
    tool channels. The corrected plan is now **offline evidence before any shadow wiring**:
    operator machine only, de-identified fixtures only, no flag/config/gateway/live path, and no
    claim of native parity. It also records a newly measured adapter blocker: codex-cli 0.147.0
    supports `--ephemeral`, but frozen #4216 does not pass it, so local session persistence must be
    closed and tested before replay. See
    `research/operations/2026-08-18-bot-openai-shadow-wiring-plan.md`. No code, config, secret,
    real traffic, deploy, cutover, or merge was authorized by this correction.

- **🔇 THE ONLY EXITS THAT LEAVE THE CLIENT SILENT WERE THE ONLY ONES THAT TOLD NOBODY
  (2026-08-12, CURED).** `generate_bot_reply` notifies a human at the BOTTOM of the function,
  and three of its five exits are `raise` statements that jump straight over it. So every path
  that produced a reply notified, and the three that leave the client with NOTHING notified
  nobody — the contract inverted. Sharpest instance: the empty-after-`[ESCALATE]`-strip raise
  sits **two statements after** `human_reason = "persona_escalate_marker"`, so the client asked
  for a human and the request died with the message. Cure: `_tell_a_human` called immediately
  before each of the three; the raise itself is UNCHANGED, so the worker still parks and retries
  and nothing new is sent to the client. Per-thread dedup (30 min) means five retries produce one
  alert.
  - **What this is worth, measured live, not argued:** `meta_inbox_threads` = **40** threads,
    **32** with at least one bot give-up, **4** ever touched by a human (`handling_version > 0`,
    max 1). The corner previously carried "28 / 26 / 4" — the human-touch count has **not moved**
    while give-ups grew. The five threads silenced on **2026-07-28** (team-beta day) carry 34
    give-ups between them and `handling_version = 0` on every one.
  - **Declared scope: 3 of 5, on purpose.** The two `BotStandingCondition` exits (flag off; no
    customer message in window) are NOT notified — that class means "standing condition, not
    incident", and the flag-off branch alone is 44 of the recorded give-ups (3-19 June).
  - **Latency of the cure vs reality:** `empty RAG answer` has **never** appeared in the
    `meta_inbox_messages` give-up ledger, and the `[ESCALATE]` marker is emitted by no prompt.
    Both cured paths are real in code and unobserved on WhatsApp — do not cite this entry as
    evidence that clients were being silenced by _those two_; the evidence above is about what
    happens when any give-up occurs.
  - **CORRECTS the 2026-07-27 bullet below** (`§ "THE WHATSAPP PATH THROWS THE REFUSAL AWAY"`),
    which still reads **"Zero abstains, ever."** True the day it was written; **false since
    2026-07-28**, when five threads gave up with the error
    `RAG abstained for thread N (reason='no_relevant_context')`.
    That specific hole was closed on 2026-08-11 by #4039
    (`_safe_abstain_reply` + `human_reason="rag_abstain"`); this entry closes the rest of the class.

- **📚 HALF THE CURATED GROUNDING STORE IS SERVED, UNREVIEWABLE, AND CANNOT BE WITHDRAWN
  (2026-08-11).** The `curated_qa` Qdrant collection holds **808 points**. Exactly **396** map to a
  row in `apps/backend-rag/data/curated_qa/*.jsonl` (verified by recomputing
  `_stable_point_id(question, domain)` for every row — all 396 present, none missing). The other
  **412 map to nothing on disk**: all `domain=visa`, all `source_date` in 2026-07, **61 of them in
  the verbatim class `JELAS`**. They carry none of the Phase-0 payload fields (`batch_id`,
  `active`, `invalidated_at`, `verbatim_eligible`, `client_specific`), and no manifest references
  them — `curated_qa_drift_report.py` reports `21 files, in_sync=21, zero source_missing`, so the
  disk↔manifest view is clean and blind to all of this.
  - **They ARE served.** `orchestrator_core._inject_curated_qa_grounding` filters with
    `metadata.get("active", True) is False` — missing `active` means active, deliberately ("a
    pre-Phase-0 point written before this rail existed — treated as active, not silently
    dropped"). Every one of the 412 lacks the field.
  - **They cannot be withdrawn.** `curated_qa_regen_trigger.quarantine_row` takes a corpus ROW and
    derives its target via `_stable_point_id`. A point with no row on disk can never be selected,
    so a regulatory delta can invalidate the 396 tracked answers and leave anything untracked
    serving the superseded fact indefinitely.
  - **Sampled, not assumed**: the 9 orphans that assert a land-tenure duration read substantively
    CORRECT (E33/Second Home, SHM-Sarusun, USD 1M threshold). This is a governance gap, not a
    proven wrong answer — do NOT sell it as the cause of the beta's Hak Pakai 65 / HGB 70 error.
  - **REFUTED, so nobody re-derives it**: the elegant hypothesis that the 412 are id-derivation
    twins of the current rows (the `domain:` prefix was folded into the digest later — the
    FATAL-1 note in `_stable_point_id`) is FALSE. Recomputing all 396 rows under three older
    derivations matched **zero** live points. They are different questions, not old copies.
  - **`faq_committed` is `false` on all 21 manifests**, so the exact-match FAQ sink — the one that
    bypasses the abstain gate — carries none of this corpus. The abstain-bypass exposure is
    currently theoretical; the grounding exposure is live.
  - Countable from now on: `scripts/curated_qa_serving_audit.py` (pure reporter, never writes).

- **🕳️ THE WEBHOOK ROUTER'S FALLBACK BRANCH WAS DEAD FOR ~5 MONTHS, AND NOTHING NOTICED BECAUSE
  NOTHING EVER RAN IT (2026-08-11, PR #4081).** `whatsapp_chat.process_whatsapp_message` answers
  from OpenClaw when it responds and from the RAG orchestrator when it does not. The second path
  could not execute at all, for two independent reasons, both live on `origin/main`:
  (a) `whatsapp_persona.build_system_prompt` had its `time_of_day` parameter renamed
  `_time_of_day` on **2026-03-17**, against a call site written **2026-02-07** that still passed
  `time_of_day=` → `TypeError`; (b) `get_orchestrator(request)` was called **without `await`**
  though it is `async def` → `'coroutine' object has no attribute 'process_query'`. Both land in
  the same `except Exception`, so the client would have received `"Ops, errore tecnico 😬"`
  instead of the RAG answer.
  - **Bounded — do NOT retell this as an outage.** That error reply is persisted to
    `conversation_messages`, and it appears **0 times against 154 outbound WhatsApp messages in
    July**. The branch has never actually been taken and no client was hit. It was a hole in the
    net under "OpenClaw did not answer", not a live failure.
  - **How it was found, because the method is the transferable part**: not by reading, but by
    driving. A mutation run on a new formatting cure showed the fallback call site could be
    DELETED with nothing turning red — the corpus only ever drove the OpenClaw branch. Writing the
    test that reaches the other branch is what made both `TypeError`s appear. A keyword mismatch
    and a missing `await` are invisible to imports, to ruff, and to every test that drives only
    the sibling branch.
  - Guard now armed: `test_the_persona_builder_accepts_every_keyword_the_router_passes` AST-reads
    the router's ACTUAL keywords and binds them against the signature, so the next rename on
    either side fails in CI. Class audit for other un-awaited `async def` calls across routers /
    deps / integrations / channels: 12 candidates, **all 12 verified false positives** — no second
    instance, bounded to what that heuristic can see.

- **🎠 THE BIGGEST ERROR CLASS IN THE BOT'S LEDGER IS BY DESIGN AND IS NOT CLIENT-FACING — check
  before treating it as the top problem (2026-08-11).** `meta_inbox_messages.error` ranks:
  `24h_window_closed` **84** · `superseded_by_coalescing` 62 · `bot_generate_failed_after_5_attempts`
  60 · 2 others. The 84 look alarming and are not client questions at all: 4 distinct threads, all
  bodies exactly 89 chars, prefix `"Carousel pronto: https://drive.google.com/"` — they are **WR2
  carousel-ready notifications**, and `wr2_html_render_apply.py` says so verbatim next to the send:
  _"WA above stays best-effort (24h-window may be closed for months); THIS is the delivery leg the
  human actually sees"_ (the Telegram P0 + review-queue entry). Thread 30 retried 45 times over 49
  days — exactly the "closed for months" the comment predicts.
  - The real (small) defect is the **ledger's readability**, same shape already recorded for the
    give-up sentinel: a deliberately best-effort leg and a genuine failure are spelled identically,
    so the error ranking mis-ranks the bot's problems for whoever reads it next.

- **📊 WHAT CLIENTS ACTUALLY ASK — 993 REAL TEAM CONVERSATIONS, AND THE RANKING CORRECTS OUR OWN
  PROBING (2026-08-11).** Zero handed the session a Case Captain intelligence pack derived from the
  team's WhatsApp history (`~/Desktop/WA-Case-Captain-Intelligence-2026-08-11`, local, `0600`,
  read-only — **not in the repo, and it must not be**). Verified before use, not believed: 14/14
  sha256 in its manifest match, **zero client PII** across every md/json (pattern-scanned), the
  sqlite carries **no raw-chat column**, and all **7 acceptance gates hold with 0 violations**
  (including "0 assets simultaneously generator- and grader-eligible"). Of 12,270 candidates,
  **0 are production-eligible, 0 authorise `send_whatsapp`, 0 a CRM mutation, 0 an automated HR
  action** — the whole registry is review-only by construction.
  - **The client-topic ranking (`DOMAIN`, out of 3,439 classified):** IMMIGRATION **709** ·
    FOLLOW_UP_STATUS **550** · DOCUMENT_OPERATIONS **533** · PAYMENTS **392** · CORPORATE **346** ·
    PRICING_SALES **314** · COMPLAINT_RETENTION 172 · TAX_ACCOUNTING 162 · PROPERTY 139.
  - **It found a hole in MY measurement, which is the point of having it.** Every probe campaign
    this session covered immigration / corporate / tax / property / KBLI / compliance and
    **zero** document-operations and **zero** payments — 27% of what clients actually ask, never
    measured, and invisible until the real distribution named it. A probe set built from what the
    engineer finds interesting will mis-rank the product every time.
  - **896 candidates are `CURATED_QA_STAGING`**, every one of them flagged
    `synthetic_rewrite_required` AND `independent_review_required` (896/896 both). That is the
    lane that could close the recall gap logged below — but nothing here is ingestible as-is, and
    the safety claim the design rests on is REAL and already armed in code:
    `apps/backend-rag/scripts/curated_qa_source_allowlist.py` carries
    `FORBIDDEN_SOURCE_MARKERS = ("meta_inbox_messages",)` with case-insensitive guilt tests.
  - **⚠️ THREE OF THE PACK'S 15 CITED IMPLEMENTATION SURFACES ARE WRONG — checked against
    `origin/main`, not against a checkout.** `curated_qa_source_allowlist.py` is under
    `apps/backend-rag/scripts/`, NOT `backend/services/rag/`; `curated_qa_pricing_detector.py` is
    under `backend/services/misc/`, NOT `backend/services/rag/`; and
    **`scripts/whatsapp_corpus/compile_team_dashboard_assets.py` EXISTS NOWHERE ON `origin/main`
    — it is a phantom**, cited as the "existing review-only registry pattern", i.e. as the very
    precedent the registry design claims to follow. Nothing in this repo generates that document,
    so the citations cannot be fixed at a generator: **re-grep every path before building on it.**

- **🚨 THE #2 CLIENT TOPIC IS THE ONE CAPABILITY THE BOT DOES NOT HAVE — AND IT ASKS FOR PASSPORT
  NUMBERS (2026-08-11, 9 synthetic questions, no client PII).** Probing the two classes the
  ranking exposed as unmeasured, plus the no-CRM class asked **three times** (the beta-test claim
  "four behaviours" is a claim about VARIANCE — one run cannot test it):
  - **FOLLOW_UP_STATUS (550 conversations, 16% of the corpus).** Three identical asks →
    `ctx=0, evidence=0.0, abstain=true` all three, and lengths **240 / 429 / 1,721** — a 7×
    spread on one question. All three solicit **full name, passport number or application ID**,
    which the bot has no CRM to look anything up with: it invites a client to send identity
    documents into a channel where nothing will consume them. A second batch (6 runs, fresh
    subject each, `max_steps` 1/2/3) reproduced the solicitation **6/6 — so 9 of 9 across both
    batteries.** That is the stable defect on this class.
  - **What did NOT survive re-measurement, and the correction matters more than the finding.**
    Two of the first three opened with "I **still** need…" on a FIRST message with
    `conversation_history: []`, and an earlier draft of this entry called that "the
    false-continuity defect, third reproduction today". The hypothesis under test was that the
    ReAct loop narrates its OWN failed retrieval step back to the client (the class cured in
    `reasoning.py` this morning), which predicts the wording tracks `max_steps`. **It does not:
    0/6, including 2/2 at `max_steps=2` — the exact setting that produced it twice an hour
    earlier.** Memory contamination was already ruled out by construction (every probe gets its
    own fresh subject). So on this class the false continuity is a **stochastic wording, not a
    structural defect**, and nothing in the loop should be "fixed" for it. Whether the drift seen
    on OTHER shapes is the same nothing is unmeasured — do not generalise this either way.
  - **Already blocked on WhatsApp, and not by luck** — `wa_inbox_bot._abstain_answer_worth_sending`
    (PR #4050, written this morning after a two-seat adversarial review) refuses to send when
    `context_length <= 0 or evidence <= 0.0`, which is exactly this shape. The gate was written
    against a different measurement and covers this one. **Open question, NOT established:** no
    channel adapter contains a single reference to `abstain` (measured: 0 across every file in
    `channels/`), but I did not establish that any non-WhatsApp surface renders this payload —
    `instagram_chat.py` (284 lines) produces no RAG answer at all. Measure it before curing it.
  - **DOCUMENT_OPERATIONS (533, #3): hedge-then-generalize.** Retrieval SUCCEEDS (`ctx=8`) and the
    answer still opens "the specific list of documents … is not detailed in the provided context",
    then answers anyway from general knowledge. The asks are about OUR intake requirements
    ("original akta or is a scan enough?" → `ctx=1`, answered with generic Indonesian practice) —
    a business fact, not a legal one, and generic practice is not an answer to it.
  - **PAYMENTS (392, #4): one honest, one gap, one off-target.** "How do I pay you?" → an honest
    352-char refusal that routes to the team (the shape we want). "Do your prices include VAT?" →
    honest KB gap. But **"can I pay in two instalments?" was answered about PT PMA capital
    deposits** — the client asked about paying Bali Zero, the bot answered about paying the state.
    Same class as the beta test's chart-of-accounts miss, on the 4th-most-common topic.
  - Health on this batch: **9/9 answered, 0 over the 4,096 limit**, 15–56s.

- **🔢 THE LONGEST ANSWER IS NOT A LONG ANSWER — IT IS 6,823 COPIES OF ONE LINE (2026-08-11,
  measured live, cured in `orchestrator_core._format_workflow_for_prompt`).** Probing ten core
  service questions cold (one run each, `channel=whatsapp`, generic questions, no client PII),
  nine came back between 116 and 2,799 characters and one — "What is LKPM and how often must I
  file it?" — came back **123,745 characters**. Structure, not length, is the finding: **6,835
  lines, 13 distinct, of which 6,823 CONSECUTIVE copies of the literal `?. Unknown action`**,
  reproduced byte-for-byte on a second run (125,084 chars, the same 6,823).
  - **Cause: two step vocabularies that never agreed** (the shape of W114, not a schema that
    drifted). Censused across the repo instead of inferred from the producer that bit: six
    producers emit `{"step": n, "action": …}` (`kg_subgraph_visa|company|tax|property`,
    `kg_langgraph_orchestrator`, `personalized_workflow`); **one** — `kg_graph_nodes.py`, the
    `source: "graph_traversal"` path — emits `{"step_id", "title", "entity_type", "relationship",
"depth"}`. Zero overlap, so **every graph_traversal step was unreadable by construction**, and
    the default `.get("action", "Unknown action")` turned "I cannot read this" into output. That
    same producer is the only UNBOUNDED one: one step per traversed entity.
  - **It is not only a client defect.** `_format_workflow_for_prompt`'s own docstring says the
    block feeds the SYSTEM PROMPT, so those ~124k characters are also paid for on the way IN, on
    every query that reaches the path — relevant to the Gemini prepay depleting for the 4th time
    on 2026-08-10, though no one has yet attributed a share of that burn to this.
  - **Cured at the reader** (both vocabularies; an unreadable step renders nothing; an all-unreadable
    list is not dressed up as a workflow; capped at 12 with the drop DECLARED — W97). **NOT cured:
    the KG returning 6,823 "steps" for one question.** Do not read the cure as having fixed that.
- **🔎 `ctx=1` IS THE NORM, NOT THE EXCEPTION — 6 of 10 core questions retrieve ≤1 chunk
  (2026-08-11).** Same ten-question probe: `context_length` min 0, max 4, **≤1 on 6/10**, while
  `evidence_score` sat at **0.85 on 7/10**. Note what that pair means before building on it: a high
  evidence score is NOT a claim about retrieval depth, so the two numbers do not corroborate each
  other and a dashboard reading only evidence would call this healthy. One run each — this sizes
  the question, it does not settle it (the same question measured 1,364 / 13,671 / 2,123 chars on
  three runs earlier in this loop; this surface is stochastic).
- **🚫 "What is the minimum paid-up capital for a PT PMA?" RETURNS NOTHING AND ANSWERS WITH A
  QUESTION (2026-08-11).** `ctx=0`, `evidence=0.0`, `abstain=true`, `abstain_reason=no_relevant_context`
  — and the 116-character body the client would see is _"Would you also like to know about the full
  PT PMA company setup process, including other requirements and timelines?"_. A high-frequency,
  high-stakes question whose answer the organism HAS (BKPM 5/2025: paid-up PMA = **2.5 mld**, and
  the >10 mld per-KBLI-per-lokasi rule survives). The grounding gate shipped this same day would
  correctly refuse to send that text (`context_length == 0`), so the client gets the stub — but the
  stub is not the defect. **Retrieval returning zero for this question is.**
  - **SHARPENED the same day, and it refutes the reading above.** Asked the SAME FACT five ways
    (English abstract / English concrete / English naming the number / `Berapa modal disetor
minimum untuk PT PMA?` / Italian), **four of five retrieve fine** and give the correct 2.5 mld
    — the Indonesian one even cites Peraturan BKPM 5/2025 by name. The only `ctx==0` is the
    **canonical English phrasing**, the one a client is most likely to type. So this is **not an
    absent fact and not a broken KB**: it is a recall gap on one wording, and the wording it misses
    is the likeliest one. A cure aimed at "the fact is missing" would have been aimed at nothing.
  - **And the ctx=0 body is FALSE CONTINUITY, twice.** With `conversation_history: []` the two runs
    produced _"I hope that explanation clarifies the distinction between paid-up capital and the
    total investment plan…"_ (263 chars) and _"Would you also like to know about the full PT PMA
    company setup process…?"_ — both are the CLOSING line of a conversation that never happened.
    Same class as the monologue leak, on a different path. The grounding gate shipped this same day
    refuses to send either (`context_length == 0`), which is exactly what it was built for.
  - **Third finding in the same five, unrelated to capital:** the ITALIAN wording was answered in
    ENGLISH, `ctx=1`, `evidence=0.85` — retrieval fine, language wrong. Third independent
    reproduction of drift today, and the second where retrieval SUCCEEDED.
- **🗣️ LANGUAGE DRIFT IS QUESTION-DEPENDENT, NOT LANGUAGE-DEPENDENT — reproduced 2026-08-11.**
  "What is the corporate income tax rate in Indonesia?" asked in ENGLISH came back **wholly in
  Italian** ("Per l'imposta sul reddito delle società (PPh Badan)…"), with correct content, ctx=2,
  evidence 0.85 — i.e. retrieval SUCCEEDED. This is the beta-test finding (Dewa Ayu, two English
  questions answered in Italian) reproduced on a different question. It also corrects the reading
  that probe 28 licensed: that probe asked ONE question in eight languages and got 16/16 right, so
  "no drift" was a statement about that question, never about the bot. **Vary the question, not
  just the language, or you will keep measuring the wrong axis.**

- **🧪 TWO ADVERSARIAL SEATS + WEB RESEARCH ON THE FOUR OPEN WEAKNESSES (2026-08-11). The most
  useful result is where they DISAGREE — read that first.**
  - **The panel said: fix the monologue leak at the generation layer (Gemini `response_schema`
    separating thought from reply), not with a cleaner regex.** Both Codex gpt-5.6-sol and Gemini
    3.1 Pro said it independently. **The research REFUTES that as currently actionable**:
    `googleapis/python-genai` **issue #2121** documents that thought content arrives inside
    `part.text` with a literal `THOUGHT:` prefix while **`part.thought` is `false`/`null` on every
    part** — so a client that correctly checks the structured flag still gets fooled, because the
    flag is wrong at the source. Google closed it "not planned". Live `<think>`/`<final>` tag
    leakage is open across three independent frameworks (openclaw #15353, #48587) as of Feb-Mar
    2026, and is reported to worsen under high context usage. **So the cleaner regex is a
    workaround for a documented upstream bug, not a design shortcut** — do not rip it out for the
    "proper" fix until #2121 moves. Also on this stack: with thinking disabled a model can emit a
    tool call as plain visible text, no error.
  - **Where both seats AGREED, and they were right — the abstain-with-content rule as first
    shipped was WRONG.** Gating the send on TEXT LENGTH "measures fluency, not support" (Codex)
    and "a disclaimer does not mitigate bad legal advice" (Gemini). Corrected: send only when
    evidence was actually RETRIEVED (`context_length > 0` AND `evidence_score > 0`), which is also
    what this corner's own numbers said — the 5 useful abstains had ctx 1-2, the 2 junk ones had
    ctx 0. Shipped on `backend-rag-wa-escalation-lane`, mutation-verified.
  - **On whether a caution label is enough for regulated advice, the honest answer is NOBODY
    KNOWS.** The research found **no controlled study** comparing suppress vs caution-label vs
    human-route with harm as the outcome in a legal/medical/financial context. What IS measured:
    confident-but-wrong AI advice collapsed users' willingness to say "I don't know" from **44% to
    3%** and their accuracy from **27% to 9%** while stated confidence rose 30%→76% (trivia
    domain, not domain-matched). And **there is no regulatory requirement that AI advice carry a
    confidence disclaimer** — EU AI Act Art. 86, FDA CDS 2026, NAIC and FINRA all impose
    transparency/oversight, none specifies a confidence element. Do not cite one.
  - **Non-determinism (finding 2/3) has named mechanisms, and one is architectural**: an
    LLM as the EXCLUSIVE collection gate is the wrong design at this scale (Codex) — use a
    deterministic domain→collection map with mandatory collections, let the LLM only ADD. Plus:
    ANN/HNSW traversal can omit true neighbours entirely, so the retrieved SET varies, not just
    its order; temperature 0 is not determinism (request batching flips tokens); an uncalibrated
    `evidence_score` bucketing to 0.85/0.6/0.0 must not drive safety decisions until calibrated.
    Measured cure: hybrid BM25+dense with RRF fusion, recall@10 **65-78% → 91%**; hybrid+rerank
    **+17.4% Recall@5** over RRF alone. **Also demanded and NOT yet built: a reason code on empty
    retrieval** — `ROUTER_SELECTED_NONE` / `TIMEOUT` / `FILTER_ZERO_RESULTS` / `TOOL_ERROR` must
    never all collapse into "evidence 0".
  - **Caching: the cheap win is doing nothing, correctly.** Implicit caching is ON by default
    since Gemini 2.5, costs no storage fee, and strictly dominates explicit caching below ~3.6-4.8
    calls/hour. Our 9,507-token prefix clears every documented minimum. The ONE requirement is
    that the static prefix sit at the very start of every request, **byte-identical**, before any
    per-call content — otherwise the match silently fails and the discount is zero. That is the
    thing to verify, not a caching feature to build.
  - **False continuity is the weakest-evidenced of the four**: no academic source, no named
    taxonomy, one OpenAI bug acknowledgment without published mechanism. Treat any causal claim as
    OUR hypothesis to test. Codex's lead is the sharpest available: the phrase we saw — "The
    previous answer was rejected because…" — fingerprints **retry/evaluator context
    contamination**, i.e. a failed attempt being appended into the next generation, NOT a generic
    persona tic. Ruling out long-term memory (done) does not rule that out. **Next step: dump the
    fully assembled Gemini request for a retry, not the app-level `conversation_history`.**
  - **Blind spots the whole probe set cannot see BY CONSTRUCTION** (Codex's list, worth keeping):
    factual correctness (on-topic ≠ correct — needs an expert-labelled claim benchmark with
    effective dates); multi-turn corruption and session bleed (every probe is cold); cross-client
    authorization on a SHARED number; prompt injection via retrieved documents; actual WhatsApp
    delivery (an endpoint 200 is not a delivered message); escalation abandonment (Telegram
    accepting ≠ a human acting); burst load; noisy real inputs (voice notes, typos,
    code-switching); provider/model degradation.
  - **And a correction to my own numbers**: reporting "~10% of ordinary questions exceed the
    limit" next to production's "4/311 ≈ 1.3%" is a contradiction unless the populations differ —
    repeated runs of three questions are a REPEATABILITY test, not a prevalence estimate, and I
    presented them as one. Separately, "~0% cache hits" contradicts the 14.5-17% in the same
    breath: cached TOKENS and cache-HIT requests are different measures. Both corrected here.

- **✂️ A REPLY TOO LONG FOR WHATSAPP IS CUT MID-WORD AND NOTHING SAYS SO — measured at ~10% of
  ORDINARY questions, worst case 13,671 chars (2026-08-11).** `whatsapp_service.send_message`
  enforces the Cloud API's 4,096-char body limit with `text[:4096]`: a silent cut, mid-word, with
  no marker. Two live probes (37 everyday client questions, cold start, no history,
  `channel=whatsapp`, no client PII) crossed it four times — **"What is Hak Pakai and how long
  does it last?" returned 13,671 chars, so 9,575 (70% of the answer) would vanish**; "How long
  does company registration take?" 7,837 (−3,741); "KITAS investor requirements" 6,841 (−2,745);
  "difference between KITAS and KITAP" 4,520 (−424). Production agrees at a lower rate on a much
  smaller sample: 4 of 311 bot replies, worst 7,521.
  - **It is not a fixed set of long questions — it is a fixed rate of long RUNS.** The Hak Pakai
    question asked three times returned **1,364 / 13,671 / 2,123** chars. A spot check will miss
    it; the cure has to be unconditional, not aimed at "the long ones".
  - **Lower bound, stated as such**: the live bot ships up to 12 prior turns
    (`_HISTORY_TURNS = 12`), which can only make answers longer.
  - Cure in flight (PR-B, branch `backend-rag-wa-escalation-lane`): cut at a boundary + a short
    localized note. **The note deliberately never promises the remainder** — nothing retains it,
    so "ask me to continue" would be the same class of lie the abstain path used to tell.
  - **A dependency was itself broken**: `utils/message_chunker.chunk_message` promised in its
    docstring "each within max_length" while its line-splitting branch appended a whole
    over-long line — so text with no `\n\n` and no `\n`, i.e. an ordinary LLM paragraph, came
    back as ONE oversized chunk. Instagram's limit is 1,000, where that overflows four times
    likelier.

- **🎲 ABSTAIN FIRES ~1 TIME IN 3 ON QUESTIONS THE BOT ANSWERS WELL — it is not only an outage
  symptom (2026-08-11).** A 20-question probe recorded 4 abstains and they read like KB gaps.
  Re-asking the three main ones three times each says otherwise: **4 abstains in 12
  observations** — PT PMA setup 1/4, Hak Pakai 1/4, "Qual è la differenza tra KITAS e KITAP?"
  2/4. The non-abstaining runs are not marginal: the Italian KITAS/KITAP question retrieves **8
  sources from `visa_oracle` at `evidence_score 0.85`** two runs out of three, and on the third
  returns `abstain=true`, `context_length=0`, `evidence_score=0.0`,
  `abstain_reason="no_relevant_context"`. Same question, same payload, no history either time.
  - **Why this matters more than the depletion**: on today's Meta path an abstain is
    `raise RuntimeError` → 5 retries → silence. The credit depletion made that 100% for 34h; this
    makes it ~33% **every day**, on the agency's core questions. Do NOT file the discarded-abstain
    defect as outage-only.
  - **Phrasing moves the retrieval path**: _"PT PMA company registration requirements"_ scores
    `evidence 0.4`; _"What are the requirements to open a PT PMA in Indonesia?"_ scores `0.85`
    across three collections. Measured, not cured.

- **🔀 `sources` COMES BACK AS DICTS ON SOME RUNS AND PLAIN STRINGS ON OTHERS — same question
  (2026-08-11).** Census over 17 answers: **dict 13, str 3**, and the shape tracks the score —
  str runs scored `evidence` 0.6 / 0.6 / 0.4, dict runs mostly 0.85. `orchestrator_response.py:48`
  types it `list[Any]`, so this is declared, not drift. **Nothing crashes**:
  `pipeline.py::_normalize_citations` guards with `if not isinstance(src, dict): continue`.
  The open question was whether the str path therefore reaches the client with **zero
  citations**. **Probed, and the answer is that this surface cannot answer it**: across 12 calls
  the response carries **no `citations` key at all** (0/12), so the normalizer's behaviour is
  invisible from `/api/agentic-rag/query`. **Hypothesis NOT TESTED — not disproved.** Whoever
  picks this up must measure it where the citation pipeline actually runs (the web-chat surface),
  not here. Without that control the probe would have printed "0 citations on str runs" and it
  would have read as a confirmed finding.

- **🌍 THE APOLOGY AND ACK THE OUTBOX WORKER SENDS ARE IN ENGLISH FOR 6 OF 9 SAMPLED
  NON-ENGLISH MESSAGES (2026-08-11).** `wa_outbox_worker` derives the language with
  `backend.services.communication.detect_language`, and measured on nine realistic client
  openers it returns **`'auto'`** for _"Buongiorno, quanto costa aprire una PT PMA a Bali?"_,
  _"Non ho capito niente di quello che mi hai scritto"_, _"Selamat pagi, berapa biaya untuk
  membuat PT PMA?"_, Russian, German and Spanish — while it DOES catch _"Ciao, ho bisogno di
  rinnovare il mio KITAS"_ → `it` and _"Saya mau perpanjang KITAS…"_ → `id`. It is
  marker-based and misses ordinary phrasings: its Italian list is
  `ciao/come/cosa/sono/voglio/posso/grazie/quando/dove/perché`, and "buongiorno", "quanto",
  "costa", "aprire" are not in it.
  - **Do NOT "fix" the fallback — it is deliberate and says so.** `_apology_text`'s own comment
    reads _"'auto'/unknown falls back to English via the .get(..., default) below, mirroring
    whatsapp_ack.ack_text()'s pattern. Deliberately NOT a new translation subsystem"_. The
    fallback behaves exactly as designed; **what is wrong is the input it is handed**. An
    earlier draft of this entry implied the `.get` "missed the dict" by accident — it does not.
  - **The same class was cured yesterday on ONE consumer and not swept.** The detector's
    docstring carries a 2026-08-10 correction: `'auto'` is "a real, frequently-returned value"
    and callers were written against a vocabulary the function does not emit — measured then on
    `_add_emotional_acknowledgment`, which was defaulting to Italian. The other consumers
    (`wa_outbox_worker` apology + ack, `nurturing_message`) were not revisited. Curing one
    consumer of a shared detector moves which caller is wrong; it does not reduce the count.
  - **Where the cure belongs**: the detector's markers, not any consumer's fallback. Cyrillic
    (ru/uk) is decidable by SCRIPT and cannot false-positive on Latin text — that is the
    cheapest real win; Italian/Indonesian need higher-signal markers. Not done here: it is a
    shared function with ~4 consumers and deserves its own change and its own gate.
  - The table itself holds only `en/id/it/ru/uk`, so **German and Spanish are English by
    construction** — that part is the known stub gap, the news is IT/ID/RU failing anyway.
  - This is the C4 apology the client gets _after_ `_maybe_send_ack` has already promised
    someone is checking. Wrong language on the promise AND on the apology.
  - **Trap for whoever fixes it**: there are TWO language vocabularies in this lane —
    `detect_language` → `'it'`, and `get_localized_stub` → `'ITALIAN'`. Verified:
    `get_localized_stub(..., 'it')` returns the **ENGLISH** text with no warning, as do `'IT'`
    and `'italian'`. Wiring one into the other emits English under Italian and says nothing.
    Pinned by `test_an_unknown_language_name_must_not_silently_become_an_english_apology`
    (branch `backend-rag-wa-escalation-lane`), which goes red the day the two converge.

- **🔬 TWO OF MY OWN INSTRUMENTS LIED, AND BOTH ARE WORTH KNOWING BEFORE YOU REUSE THEM.**
  (a) The probe prints `collections_queried EMPTY on ALL = LLM-picks-collections stage down
(outage signature)` — it read empty on all 17 answers **which all answered**, so the field is
  simply not exposed in that response payload. That legend was written from the depletion
  post-mortem and would hand the next reader a false P0. (b) Its `DETERMINISTIC` verdict is
  scoped to its own three runs and is **contradicted** by the earlier probe where the same three
  questions abstained; only pooling the two gives the 4-in-12 above. A repeatability verdict
  computed inside one run cannot see the run beside it. (c) An earlier version died on the first
  row with `'str' object has no attribute 'get'` — the heterogeneity above. **A probe must
  survive the shape it exists to observe**; it now records the shape instead of dying on it.

- **🔴 GEMINI PREPAY CREDITS DEPLETED — FOURTH TIME, AND IT IS LIVE (2026-08-10 ~17:50Z).**
  Measured on the prod machine, not inferred from symptoms: a 9-token call returns
  `429 RESOURCE_EXHAUSTED — "Your prepayment credits are depleted"`, `llm_gateway` logs
  `All Gemini models failed`, and the OpenRouter fallback refuses by design
  (`OPENROUTER_ENABLED` off, PII boundary). **Window is tight, not estimated**: a 10-turn probe
  answered normally at **17:46Z** (5-90s latencies); 11 calls at **17:53Z** all came back
  degraded in 1-4s — either the localized abstain stub (274 chars) or the crash stub
  ("I'm hitting a technical problem", 97-120 chars, in the asker's language).
  - **The sentinel did NOT miss it — say that before blaming it.** `cron-llm-credit-sentinel.yml`
    ran at **17:09Z** and got a real PONG (`state=ok`, 7 in / 2 out). Real cadence is ~1h
    (GitHub `schedule` is best-effort), so a gap of up to an hour is the design, not a fault.
  - **Top-up is `operator[business]`**: AI Studio, project `nuzantara` no. **930328104463**.
    Escalated to Zero by hand via the Telegram gateway. **Send that P0 from Pro, not M5** —
    on M5 `tg_notify.py` finds no token and spools `p0_unsent` (fail-visible, but nobody reads
    it at once); the same command on Pro returned `sent`.
  - **Client harm so far: none, and say so.** `meta_inbox_messages` has **0 messages in the
    last 12 hours** — the bot is not public and it was night in Bali. The next client to write
    is the one who gets nothing.
  - **Noted, not a defect today**: the sentinel probes with `PRIMARY_MODEL_NAME=gemini-2.5-flash`
    while the RAG's default is `gemini-3.5-flash`. Same prepay balance, so a depletion is
    account-level and both see it — do not "fix" this without a reason.

- **🧵 PROBE 22 — THE FIRST MULTI-TURN MEASUREMENT (2026-08-11, before the depletion).** Every
  earlier probe sent `conversation_history: []`; the live bot ships **12 turns**
  (`wa_inbox_bot._HISTORY_TURNS`), so everything measured until now was cold-start. Four
  conversations, 10 turns, 10/10 HTTP 200, history carried forward exactly as the bot does.
  - **The message the WA path throws away sometimes PROMISES A CALLBACK, on a shape probe 21
    never tested.** Frustration turn ("I don't understand anything you're saying") →
    `abstain=True`, `context_length=0`, answer = _"Certainly. I will proceed with connecting
    you to our team."_ `ESCALATION_PROTOCOL` lists frustration as a trigger; nothing performs it.
  - **And it sometimes is UNGROUNDED ADVICE.** LKPM, second ask: `abstain=True`,
    `context_length=0`, **2 057 characters** of specific filing procedure written from model
    memory. This is the measured argument for the in-flight cure sending a localized **stub**
    rather than the answer — "send the low-confidence answer" (question #31, Zero's call) would
    ship exactly this. The cure does not pre-empt #31 in either direction.
  - **Loop escalation never fires.** Same question ×4 → four DIFFERENT answers (247 439 / 2 057
    / 4 873 / 3 586 chars), zero escalation, though the protocol lists "same question 3+ times".
    **The beta test's _identical_ brush-off ×4 did NOT reproduce** — that behaviour is not
    stable; the missing escalation is.
  - **A 247 439-character answer** — 33× the longest reply production has ever sent (**7 521**,
    measured) and 60× WhatsApp's 4 096 body limit, which `whatsapp_service.py` enforces by
    hard-truncating. **Not yet reproducible, and for a reason unrelated to the question**: the
    follow-up probe ran during the depletion above, so it measured the outage. Re-probe after
    the top-up before theorising.
  - **The 2026-07-30 correction-as-query defect did not reproduce as a wrong answer**: "in
    italiano per favore" after a C7A question returned an Italian _clarifying question_
    (D7A vs C7), on-subject. One run — this sizes a shape, not a rate.
  - **Internal monologue can arrive as the answer** — 2 of the 10 turns began literally
    `internal_monologue\nThe user asked "How much?"…`, and nothing on this path strips it
    (`_strip_kg_workflow_scaffold` is anchored on the KG block's two literals). **Never observed
    in production: 0 of 311 outbound bot messages** carry the token or the planning phrases.
    Reachable on the endpoint, not an incident — and the follow-up probe could NOT size it,
    because it ran during the outage (`0/8` there measures the outage's poverty, W107).
  - **Measurement trap, mine**: the probe's "promises a contact" detector matched the literal
    `connect you` and scored the frustration case **False** against _"connecting you"_ — an
    under-match in my own instrument (family #3). The finding came from re-reading the answer.

- TRACK BOT-KBLI claimed by M5/2026-08-11

- **🧪 BATTERY v5 — THE FOUR OPEN BETA CURES, RE-MEASURED 13 DAYS LATER (2026-08-10).** The
  2026-07-28 team beta left four cures open and nobody had asked whether they were still
  true. 14 questions, prod container, synthetic senders. Script: session scratchpad
  `wa_probe5.py`. Verdicts, worst first:
  - **Cure #2 is HALF alive — do NOT say "the land-tenure defect persists".** Hak Pakai still
    answers **25+20+20 = 65 years** (truth 30+20+30 = **80**), the exact number Dea caught;
    **HGB now answers 80, correctly.** Worse than the figure: that answer carries
    `abstain=True`, `evidence=0.0`, **`sources: []`** and still prints
    `📜 Source: Golden Route: Buy Property as Foreigner in Indonesia` — the client reads a
    provenance the response object does not have. And **the same question in Indonesian
    abstains honestly**. `hak pakai` has **0 occurrences in the whole repo** (real `grep`, not
    the shell's ugrep-with-`--ignore-files`), so no repo-side audit can ever see this — same
    shape as the tax_genius finding.
  - **Cure #1 is 3-of-4 — the fourth is SILENCE, and it is now explained.**
    `crm-direct`/`crm-id`/`crm-assumed` all refuse honestly, naming the missing access.
    `crm-indirect` ("Any deadlines I should worry about for my clients this week?") returns a
    **0-character answer, 5 times out of 5** — deterministic. Chain from the prod log:
    QueryPlanner calls it `domain=greeting, collections=[]` → model calls `crm_query` →
    authorizer denies → **the denial is scored as a successful tool run worth 0.85** (cured,
    see below) → `LLMGateway: Empty response … FinishReason.STOP` ×3 → nothing. On WhatsApp
    `wa_inbox_bot` raises, so the client gets 5 retries then silence + apology.
  - **NEW, client-visible: the model's INTERNAL MONOLOGUE ships.** 2 of 4 runs of the
    chart-of-accounts question open with the literal token
    `internal_monologue The user is asking about…` (2689 and 4044 chars), survive
    `format_rich_text`, and would be sent. The prompt says "silently check"; the model
    labels it anyway. The other 14 battery questions showed **zero** — it concentrates on
    this question / on long answers. `zantara_core.py` is OFF-LIMITS: cure at the channel
    boundary, with `_strip_kg_workflow_scaffold`'s precedent.
  - **Self-consistency fails on one fact.** "What is the fine per day for overstaying?" →
    full answer, Rp 1,000,000/day, `src=8`, cites PP 45/2024. "If I overstay by one day, how
    much do I pay?" → `abstain=True`, `src=0`, 83 chars that are _only_
    "Would you like me to explain…" — zero content. The personal phrasing, the one a client
    actually uses, retrieves nothing.
  - **`evidence_score` is a 3-valued flag, and 1.0 arrives with ZERO sources.** Across 14
    probes: `0.85`×9, `0.0`×4, **`1.0`×1** — the 1.0 is the out-of-domain surf question that
    gets the `Got it! 😊` brush-off with `src=0`.
  - Held up well, worth not re-litigating: **0 language drift, 0 markdown leak, 0 bare
    citations** in 14 answers; a nonexistent KBLI code (`99999`) is correctly refused;
    median latency **21.2s**, max 40.5s — better than the 57s/73s of 2026-07-30.
  - **Probe gotcha that cost real time:** v5's `as_whatsapp()` returned
    `SILENCE:empty-after-scaffold-strip` for _any_ empty text, including answers that
    arrived empty with the stripper never removing a byte. It named a cause it had not
    checked, and nearly sent a cure to the wrong function. Attribute emptiness by measuring
    length before AND after each stage.

- **🚫 A DENIED TOOL CALL SCORED 0.85 — the highest evidence in the system (2026-08-10, CURED).**
  `tool_authz decision=deny (principal_present=False)` was followed by
  `[Trusted Tools] crm_query used successfully (obs_len=54) … score=0.85`. **`obs_len=54` is
  exactly `len(_ANONYMOUS_DENIAL_OBSERVATION)`.** It passed because the gate judged the
  observation's PROSE (no "error"/"not found"/"no relevant") and LENGTH (floor 50) — and the
  denial string is bland _by design_: P0-DENY (2026-07-25) rewrote it to "name no tool, no
  control, no internal system". That blandness is what a failure-word scan cannot see, and 54
  clears the floor by four characters. Cured by recognising a denial against the **one function
  that mints it** (`_tool_denial.py`), never against its prose. **The twin site
  (`detect_quotable_relevance_veto`) deliberately did NOT get the same check** — on the measured
  denial it is a no-op, and the only case it changes would suppress a veto. Do not "restore
  symmetry" there without a measurement; the asymmetry is documented at the site.

- **🎯 12-QUESTION DEFECT BATTERY, RUN INSIDE THE PROD CONTAINER (2026-08-10).** Fired at
  `RAG_WORKER_URL` with the exact payload `wa_inbox_bot.py` sends (`channel=whatsapp`,
  `max_steps=2`, empty history), synthetic questions, synthetic phone numbers. 12/12 HTTP 200.
  Script: session scratchpad `wa_probe.py` — **read the C17 correction below before reusing it**,
  it scores the ENDPOINT and two of its counters do not describe the WhatsApp client.
  - **French drift REPRODUCED, 2/12, on BOTH shapes the ledger recorded.** `#0` the known
    KITAS-rejection question (EN in → **FR** out: _"Bonjour, Pour analyser le rejet de l'extension
    du KITAS…"_) and `#8` `"Zantara jelaskan visa C7A"` (ID in → **FR** out: _"Salut ! Voici les
    informations officielles…"_). The 2026-07-30 live exchange was not a one-off — it reproduces
    on demand. Note both drifted answers are on-topic and confident: **the language selector is
    an independent defect, not a symptom of empty retrieval.**
  - **`evidence_score` = 0.850 on ELEVEN of twelve.** The twelfth (`#1`, land tenure) is 0.14 and
    is also the only `abstain=True`. This is the blind-spot bullet below, now measured at n=12
    instead of inferred: the score is informative only when retrieval fails.
  - **The one honest abstention is ALSO the one carrying a wrong fact.** `#1` abstained (correct)
    AND its text hit the forbidden land-tenure pattern. On WhatsApp `wa_inbox_bot.py:346` raises
    on abstain → **the client gets silence**, so the wrong figure never ships; but neither does
    anything else.
  - **CRM honesty is FIXED — the beta-test "semuanya sudah aman" did NOT reproduce.** `#3` and
    `#4` both refuse cleanly and name the missing capability. Residual, smaller: `#4` prints the
    internal tool name (`` `crm_query` ``) to a client-role caller — deny-narration, not a leak of
    data.
  - **PT PMA pricing is clean.** `#5` returned ONE all-inclusive figure (IDR 20,000,000) with no
    government-fee split and no fabricated "1.2 billion" — Zero's 2026-07-17 ruling holding on the
    fast path.
  - **🔴 The KG scaffold carries a SUPERSEDED CAPITAL FIGURE.** `#7` (asked for the chart of
    accounts) answered with `## SUGGESTED WORKFLOW (from company_subgraph, confidence: 67%)` whose
    step 2 is **"Prepare minimum capital: Rp 10,000,000,000"**. Under BKPM 5/2025, minimum issued
    and paid-up capital is **Rp 2.5 billion per PT PMA**, unless another law provides otherwise.
    The separate total-investment threshold above Rp 10 billion generally excludes land and
    buildings and applies per 5-digit KBLI per project location; express sector and project
    exceptions change the aggregation unit or the land-and-building treatment. WhatsApp strips
    the scaffold, so this is a **web-chat** exposure — and it is a wrong legal number, not
    cosmetic noise. Do NOT cure it with a blind sweep on the string "10 miliar" (see #3720).
  - **⏱️ Median 74.6s, max 113.2s.** Up again from the ~35s the 2026-07-18 campaign left and worse
    than the two-point 57/73s reading of 2026-07-30. n=12 on a cold-ish path, stated as such.
  - `model` came back `None` on all twelve — the response does not carry the model on this route,
    so a battery cannot attribute behaviour to a model here.

- **🇫🇷 THE FRENCH DRIFT IS NEITHER ENGLISH-ONLY NOR NO-COVERAGE-ONLY — both scopings falsified by
  ONE live exchange (2026-07-30).** Read from the ledger, not from a probe: Ari (team sender) asked
  in Indonesian `"Zantara jelaskan visa C7A"` (msg 598) and got **2,834 chars in French** (msg 599,
  `delivered`) — with CORRECT, on-point C7A content (single-entry musician-performance visa,
  including the paid-performance exception). The 2026-07-27 entry below scopes this drift as
  "specific to English on this query" and reframes it as a NO-COVERAGE failure. Today: **Indonesian
  in, French out, retrieval on-point.** Both of those scopings remain true _of that one KITAS
  question_ and neither generalises — language selection is an independent defect that also fires
  when the KB does cover the ask. Do not collapse the two into one cause without measuring again.
- **🔁 A CORRECTION IS CONSUMED AS A NEW SEARCH QUERY — observed in prod, same exchange
  (2026-07-30).** Ari answered the French reply with `"bahasa indonesia anjay"` (msg 600 — "in
  Indonesian, damn"). The bot switched to Indonesian and answered about the **C9B
  Indonesian-language-course visa** (msg 601): it searched the KB for the WORDS OF THE CORRECTION
  instead of re-answering C7A.
  - **The history is NOT the gap** — verified on disk, not assumed:
    `wa_inbox_bot._load_thread_context` ships `_HISTORY_TURNS = 12` prior turns and
    `agentic_rag.py:582` forwards them into `query_kwargs`, so the model saw the C7A turn.
  - **The gap is that the retrieval key is the RAW latest message.** `process_query_core` threads
    `query=query` into the FAQ cache, the semantic cache, `_inject_curated_qa_grounding`, entity
    extraction and the KG fast-path, and `grep -riE 'rewrit|contextualiz|standalone|follow-?up|coref'`
    over `services/rag/` finds **no query-contextualisation step anywhere**. Every pre-ReAct stage
    keys on whatever the client last typed, whether or not it is a question.
  - This is the **observed twin** of the coalescing residual logged below as "unobserved in prod":
    there a real question is demoted to context; here a non-question is promoted to the query.
  - **Design constraint for the cure, before anyone writes it:** a contextualised query CHANGES THE
    FAQ/SEMANTIC CACHE KEY, and cache hits bypass the abstain gate (§2.4). Contextualise the
    RETRIEVAL query only, or keep the cache keyed on the raw message — never silently both. Needs
    the 4-LLM panel.
- **⏱️ LATENCY BACK UP — 57s and 73s** on the two replies of 2026-07-30 (`sent_at − created_at`,
  msgs 599/601), against the ~35s the 2026-07-18 campaign left behind. Two points, stated as such.
- **📖 THE CORNER YOU WERE HANDED MAY BE FOUR DAYS OLD — check before you "discover" anything
  (2026-07-30, cost most of a session).** The canonical file is **`.agents/skills/bot/SKILL.md`**
  since #3019; `.claude/skills/bot` is a SYMLINK to it. The Skill tool loads from the **main
  checkout**, and on M5 that checkout is **291 commits behind**, from before the move — so it
  serves the real, tracked, pre-#3019 file: **795 lines dated 2026-07-29 in the worktree vs 386
  lines dated 2026-07-25 on M5's main**. Working from the stale copy, this session "found" the
  language drift as new and reported that the corner's retrieval-miss framing needed correcting —
  the corner had already carried that correction for three days. Asking git for the old path does
  NOT rescue you: `git show origin/main:.claude/skills/bot/SKILL.md` FAILS ("exists on disk but not
  in origin/main") because the tracked object at that path is the symlink. **Re-read the corner from
  `.agents/skills/bot/SKILL.md` in a fresh worktree before trusting what it says is not yet known.**
- **🧪 FIRST REAL TEAM BETA — 78 questions, 13 people, 2026-07-28. FOUR CURES OPEN.**
  The bot is **not public yet, by design** (Zero) — the low inbound traffic was never a
  distribution problem, so do not "fix" it. Answer sheet (Zero's Drive, 13 named grants):
  `docs.google.com/spreadsheets/d/1p41FiRQDWwD72cUgYH0dCG7a5e5c2-wRZIuOGOTGnWQ`. **It is
  NOT readable via MCP** (403 — the prod identity is outside the domain); re-read it with
  Drive `files().export_media(mimeType=…xlsx)` + openpyxl. Result: 75 answered,
  **50 OK · 4 SALAH · 5 RAGU · 19 unscored**; zero client PII pasted (verified by pattern
  across every answer). Open cures, worst first:
  1. **One missing capability, four behaviours, one of them a lie.** The bot has no CRM
     access (deliberate, not yet granted). Across the 5 CRM questions it answered four
     different ways: two honest refusals (Dea, Asya), one canned greeting (Krisna), one
     silence (Surya), and to Adit **"semuanya sudah aman"** — an invented reassurance about
     a colleague's real client deadlines, stated confidently. _Ledger re-read 2026-07-30: the
     canned greeting was not a one-off — Krisna asked the identical LKPM question **four times**
     (msgs 580/582/584/588, 11:43→12:03) and got the identical `"Got it! 😊 …"` brush-off, in
     English, all four times. The behaviour is stable and it reads as stonewalling._
     The defect is not the missing tool, it is the absence of ONE honest way to say
     "I don't have access".
  2. **Wrong land-tenure durations** (caught by Dea): Hak Pakai given as 25+20+20=65 years,
     the truth is **30+20+30=80**; HGB given 70, truth 80. This lands in property advice.
  3. **Language drift confirmed AND reproducible** (Dewa Ayu): two English questions
     answered wholly **in Italian** — with correct content and citations. Note the
     correction to prior doctrine: retrieval had SUCCEEDED here, so drift is **not always**
     a symptom of empty retrieval; it is an independent language-selection defect.
  4. **Off-target answer** (Asya): asked for the _chart of accounts_, answered about
     mandatory financial reports.

  **Do NOT "fix" Ari's row** (this is not a fifth cure — it is the opposite): asked about a
  KITAS rejection, the bot said the rule is not in the verified database and it would check
  with the team. That is the intended behaviour — the gap is in the KB, and Ari's and Subhi's
  notes in the sheet are material to ingest. Detail: memory
  `project_zantara_team_beta_test_2026_07_28`.

- **🚨 GEMINI CREDIT SENTINEL ARMED + PROVEN LIVE (PR #3410, merged 2026-07-28 12:53Z).**
  Third depletion in a week (26/7 17:10Z → 28/7 02:52Z, ~34h mute) — the agentic LLM is what
  picks the collections, so a dead LLM means `collections_queried=[]` → 0 chunks → abstain on
  everything → the outbox worker reads the abstention as a FAILURE, burns 5 retries, and the
  user gets **silence**. Measured: 89 consecutive queries, 0 chunks, 0 responses; Qdrant was
  green throughout. `LLMCreditSentinel` now probes with a 9-token call and alerts Surya on
  WhatsApp + Zero on Telegram. **Real cadence is ~1 hour, not the requested 20 minutes**
  (GitHub runs `schedule` best-effort; measured 54–211 min gaps) — say "within an hour",
  never "within 20 minutes". Top-up stays `operator[business]`: project **`nuzantara`,
  number 930328104463** (five other Google projects have confusable names).
  Detail: memory `ops_gemini_credit_sentinel_armed_2026_07_29`.
- **🔴 THREE FAST-PATHS RETURN BEFORE THE ABSTAIN GATE — AND BEFORE ANALYTICS (2026-07-27).**
  In `orchestrator_core.py::process_query_core`, three branches `return CoreResult(...)`
  early: Phase-6 multi-agent (`:1237`), SpecializedServiceRouter (`:1260`), KG fast-path
  (`:1283`). The single `_log_query_analytics` call is at `:1416` and the abstain gate is
  further down still, so **all three skip both**. Two of the three hardcode `sources=[]`
  (multi-agent, specialized router); the KG fast-path does attach real `neo4j_kg_entity`
  sources. Consequence for anyone reading dashboards: `query_analytics` holds 6771 rows and
  **zero** are `multi-agent-coordinator` — that measures the blindness, not the rarity. Never
  cite that table as evidence a fast-path is unused.
  - **PROVEN CLIENT HARM (live probe, 2026-07-27, `ask_legal` E23 cost+timeline)**: returned
    `sources: []`, `context_length: 0`, `evidence_score: 0`, `abstain: false`,
    `abstain_reason: null` — with an **invented government fee "up to IDR 1.2 billion"**
    printed beside the real PricingTool figure, a **split price** (service fee + government +
    notary, against the 2026-07-17 single-all-inclusive ruling), and a fabricated **38-60 day**
    phase breakdown matching `TimelineAgent`'s prompt template line for line.
  - **Why it fabricates**: `TimelineAgent`'s prompt literally asks the model to fill in
    "1. Document preparation: X days / 2. Submission: Y days …"; with an empty grounding block
    `_synthesize_outputs` degrades to "be specific". Nothing on the path can say "I don't
    know". The 2026-07-18 grounding work is intact and deliberate — it left TimelineAgent to
    inherit facts _transitively via legal_analysis_ — but that inheritance conveys nothing
    when there is no evidence to inherit. **The gap is the zero-evidence case, not the
    grounding design: do not "fix" TimelineAgent by feeding it grounding directly.**
  - **`requires_multi_agent()` fires on cost+timeline keywords** (EN/ID/IT
    substrings) — the "how much and how long" shape. Do NOT claim it is the most
    common client question: measured on the real inbound corpus it is 2 of 59
    WhatsApp inbound messages with text (3.4%), and the full-domain-cache design
    itself notes ~72 inbound is too small a sample to rank query frequency. The
    severity here comes from WHAT it answers (prices, legal deadlines) with zero
    evidence, not from how often.
  - **Fix in flight**: evidence precondition on the Phase-6 branch (run it only when
    `curated_qa_context` is non-empty; otherwise fall through to the ReAct loop, which
    retrieves and can abstain). Guilt+innocence in
    `test_curated_qa_grounding_injection.py`; O9/O10 in `test_orchestrator_state_machine_wave2.py`
    updated to satisfy the precondition (what they assert is unchanged).
  - **STILL OPEN**: (a) the SpecializedServiceRouter branch has the same source-free shape and
    is NOT covered by that fix; (b) none of the three early returns writes analytics.

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

  **RE-MEASURED 2026-08-11 — the verdict HOLDS, but the numbers above are stale by 7×, and a
  stale number inside a "DO NOT RE-OPEN" is what buys the next session an afternoon.** The entry
  was written on 07-27; the team beta was 07-28, and the population exploded the next day.
  Lifetime `superseded_by_coalescing` is now **62 rows, not 9** — and the mid-backoff share, the
  case this entry concedes is not the intended one, went from **2 of 9 (22%)** to **32 of 62
  (52%)**: `attempts` 0→30 · 1→4 · 2→12 · 3→10 · 4→6. So the reassuring ratio is gone.
  **The second premise is what still carries it, and it was re-tested, not assumed: all 32
  killed mid-backoff had an outbound reply in the same thread within 30 minutes, and ZERO were
  never answered.** Re-open only if that second number ever moves — the attempts ratio alone is
  not the finding.

- **📊 THE BETA WEEK IS THE ONLY LOAD TEST THIS BOT HAS EVER HAD — and half the outbox rows
  failed (measured 2026-08-11 on 27/07–05/08, 131 rows).** `done` 68 · `failed` 63. The failure
  breakdown is the point: **53 = `superseded_by_coalescing`** (benign per the entry above),
  8 = `bot_generate_failed_after_5_attempts`, 2 = `24h_window_closed`. Read the sentinel before
  reading "48% failed" as an outage — most of it is bursts being merged, working as designed.
  Client-visible latency in that week: **median 302s, p90 990s** (inbound→first outbound, ≥15
  chars, capped at 2h). The p90 tracks `RETRY_BACKOFF_BASE_SECONDS = 30` compounding across five
  attempts (30/60/120/240/480 ≈ 15.5 min), so ~10% of beta messages needed several attempts.
  Note this is a DIFFERENT measure from the `sent_at − created_at` figures elsewhere in this
  file: this one is the wait the human actually experiences.

  **NOT a defect, killed here so nobody re-finds it:** a first pass read "35 of 224 inbound
  (15.6%) never answered". Decomposed: **34 are simply the last message in their thread** (there
  is no reply yet because there is no reply yet) and 1 is a sub-15-char ack. **Genuinely dropped
  substantive questions: ZERO**, in both the bot-off and bot-on eras. The 15.6% measured thread
  endings, not silence.

- **🔇 ZERO TRAFFIC SINCE 2026-08-05 17:39Z (measured 08-11).** Six days, no inbound, no
  outbound. Everything merged after that date — the two language-detector fixes (#3959 08-09,
  #3969 08-10) and everything shipped on 08-11 — is **merged, not proven live**. There is no
  post-fix corpus to evaluate and there will not be one until traffic returns AND the Gemini
  prepay is topped up (`operator[business]`, project `nuzantara`, number 930328104463). Do not
  read the absence of new drift reports as evidence a language fix worked.

- **📎 THE INTERNAL FILENAME REACHED REAL RECIPIENTS — 6 outbound messages (measured 08-11).**
  `[CURATED {source_ref} {date}]` handed the model an internal filename as the only "source" it
  had, and the model cited it: `CURATED FINAL.md#Q16` / `#Q17` printed into WhatsApp threads on
  07-24 and 07-28 (five of the six on beta day, so mostly colleagues — but nothing in the code
  path distinguishes a colleague from a client). Sizing: **808/808 live Qdrant points carry an
  internal `source_ref` and zero carry a citable regulation name**. Cure in PR #4067 — the header
  now says the section is not citable and the refs move to the log line.

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

- **🔇 THE WHATSAPP PATH THROWS THE REFUSAL AWAY — this is why "oggi tace" (2026-07-27).** The
  copy in #3260 improves every channel that renders the RAG answer, and reaches the bot on NONE
  of them, because `wa_inbox_bot.py` (~line 346) does `if data.get("abstain"): raise
RuntimeError(...)` before a message is ever composed. Its docstring states it as a contract:
  "On ABSTAIN or any RAG error → raise … the operator can take over the thread." Measured: that
  operator does not come. Over the whole history of `meta_inbox_threads` — **28 threads, 26 with
  at least one `failed` outbox row, and exactly 4 EVER touched by a human**
  (`handling_version > 0`, max 1). ~22 threads hit a failure and nobody arrived.

  **CORRECTION (same day, before this entry ever landed) — those failures were NOT abstains.**
  An earlier draft of this bullet let the 26-of-28 number imply that clients had been silenced by
  discarded refusals. They had not. `meta_inbox_messages.error` records the last exception after
  the sentinel `bot_generate_failed_after_5_attempts:`, and classifying all 52 give-ups gives:
  **44 = `wa-inbox bot auto-reply not enabled in v1`** (2-18 June — the bot was simply switched
  off), 5 = `no customer message in thread <n>`, 2 = RAG `500` (12 July), 1 = `401 Unauthorized`.
  **Zero abstains, ever.** _[STALE since 2026-07-28 — see the 2026-08-12 entry at the top of §1:
  five threads (249/250/252/259/263) gave up with the error
  `RAG abstained for thread N (reason='no_relevant_context')`
  on the team-beta day, so the defect below stopped being latent
  the day after this was written. Cured 2026-08-11 by #4039. The counts in the paragraph above —
  28/26/4 — are also stale: re-measured 2026-08-12 they are **40 / 32 / 4**, i.e. the
  human-touch number never moved.]_ So the discard is a LATENT defect: real in the code, never yet fired
  in production. Current state is healthy — week of 19 July: **0 generation failures on 13
  inbound** (small sample, stated as such).

  > ### ⛔ THE TWO SENTENCES ABOVE ARE NO LONGER TRUE — "zero abstains, ever" DIED THE NEXT DAY
  >
  > **Re-classified 2026-08-11 over the whole history, not just up to 07-27.** This bullet was
  > written on 2026-07-27. The team beta was **07-28**. The discard is not latent: it **fired
  > six times in production that morning**, threads 249 / 250 / 252 / 255 / 259 / 263, all
  > between 02:02 and 02:29Z, every one of them
  > `wa-inbox bot: RAG abstained for thread <n> (reason='no_relevant_context')`. A seventh row
  > the same morning is thread 270, `answer empty after workflow-scaffold strip`, which the same
  > `raise` discards by the same route.
  >
  > **What the asker experienced, measured rather than inferred:** each of the six threads DID
  > get an outbound eventually — at **+11, +12, +16, +23, +32 and +38 minutes**. Not permanent
  > silence, so do not upgrade this to "clients were abandoned". But nothing arrived while the
  > retry ladder burned, and whether those later replies answered the abstained question or a
  > subsequent one in the thread is NOT established here — do not assert either.
  >
  > **The cost is new information, and it is the part the 07-27 analysis could not have had.**
  > That analysis correctly established that the 44 `not enabled in v1` give-ups were CHEAP —
  > `is_bot_autoreply_enabled()` is the first statement of `generate_bot_reply`, so those five
  > attempts were no-ops. **Abstain is the opposite case.** The `raise` sits at
  > `wa_inbox_bot.py:357`, _after_ the `/api/agentic-rag/query` round-trip inside the P9
  > semaphore — so every retry is a FULL RAG call. Six abstains plus one empty-after-strip, five
  > attempts each: **~35 complete RAG round-trips that could not have produced anything**, on the
  > single day this bot has ever carried real load, inside the window the Gemini prepay was being
  > drained. The retry ladder cannot rescue an abstain the way it can rescue a flag flipped
  > mid-backoff: the same query against the same KB abstains again.
  >
  > **This does NOT reopen the ladder on its own.** Skipping retries or suppressing the apology
  > is still forbidden below without its own evidence, and the send-or-stay-silent half is still
  > a Legge-5 call for Zero. What changes is that the call is no longer being made about a
  > hypothetical: it has fired, on real people, and it costs ~5 full generations per occurrence.
  >
  > _And the lesson is the one this very bullet already taught, one layer up: its own method note
  > says two disagreeing probes are what caught a wrong number. Here nothing disagreed — the
  > classification was simply run before the event it would have caught. A measurement is stamped
  > with the day it was taken, and this file did not carry that stamp where it mattered._

  _Method note: the first classifying query returned "0 abstains" AND a second returned "0
  failures per week", which contradicted a count of 52. The bug was mine — `split_part(error,':')`
  meant the stored value has a suffix, so `error = '<sentinel>'` matched nothing. Two of my own
  probes disagreeing is what surfaced it; a single probe would have shipped the wrong number._

  **The evidenced sibling defect, found by the same classification: the ledger is unreadable.**
  All 52 give-ups are filed under one sentinel, `bot_generate_failed_after_5_attempts`, so two
  weeks of the bot being deliberately off is spelled exactly like a production RAG outage.

  _Two claims in an earlier draft of this bullet were WRONG and are corrected here, because an
  adversarial seat (Codex gpt-5.6-sol, xhigh, briefed to refute) returned DO-NOT-SHIP on the
  first cure built from them:_
  - _"each burned 5 generation attempts" — **false**. `is_bot_autoreply_enabled()` is the FIRST
    statement of `generate_bot_reply`, before `_load_thread_context` and before any RAG call, so
    those 44 rows cost five cheap no-ops, not five LLM round-trips. There was no saving to buy._
  - _"permanent conditions" — **overstated**. The flag is read from the environment on every
    call, so a rollout flipping it ON mid-backoff still rescues the row; and "no customer
    message" means "none in the last 13 records" (`_HISTORY_TURNS + 1`), a window artifact._

  The shipped cure is therefore diagnostic ONLY: `BotStandingCondition` (a `RuntimeError`
  subclass) makes the worker write a distinct ledger line at INFO. Retry/backoff, `attempts`,
  fencing and the C4 apology are UNCHANGED. **Do not re-propose skipping the retry ladder or
  suppressing the apology** — the apology matters precisely because `_maybe_send_ack` runs BEFORE
  generation and does NOT consult `WA_INBOX_BOT_AUTOREPLY`, so a client can already have been
  told "checking on this…"; dropping it leaves that promise in permanent silence.

  **#31's remaining half is NOT an engineering blocker — it is a Legge-5 call for Zero.** An
  earlier version of this bullet claimed the WhatsApp path could not send on abstain because
  `abstain=True` might carry a full un-vetted answer. **That was wrong, and the repo says so in
  plain text.** `test_abstain_threshold_convergence.py` documents the exact case above its own
  fixture: _"KBLI query, score in (flat 0.15, kbli 0.20): generation gate PASSES, label gate
  ABSTAINS. **Generated answer carrying an abstain=True flag.**"_ It is the CONTRACT, not a
  divergence to repair: GENERATION decides whether to PRODUCE advice, LABEL only MARKS
  confidence, and reasoning.py treats 0.15-0.50 as moderate evidence and deliberately writes a
  cautious answer with a warning note. A fix built on the wrong premise was written, tested green
  and DISCARDED after an adversarial seat returned DO-NOT-SHIP 7/7 (it would have turned the
  label gate into a second generation gate on the sync path only, and — because the language
  detector covers 8+ languages while the stub covers 3 — would have answered a Spanish question
  with an English refusal).

  So on abstain the bot is discarding content that is legitimate either way (a localized stub
  below 0.15, a cautious answer above it). The open question is a product one:
  **should the bot send a LOW-CONFIDENCE answer with a caution note on immigration/tax/company
  questions, or keep today's silence?** Today's silence is not a decision — it is the `raise`,
  written when abstain was assumed to mean "no content". Measurement that sizes the stakes:
  abstain has fired ZERO times on WhatsApp in the entire recorded history.

  **Do not "fix" the gates to make this easier.** §Established truth #4 already says the abstain
  gates are the product; the divergence is panel-ruled (CLAUDE.md §9) and tidying it via the
  answer TEXT is the same violation as tidying it via the numbers.
  There is also NO
  human-notification path anywhere (grepped worker + generator for telegram/alert/notify/
  escalate/CRM-assign), and the `apology_sent_at`/`ack_sent_at` code from migration 260 is armed
  by `WA_OUTBOX_MANNERS_ENABLED`, default OFF, docstring "Ships dark: unset in prod today" — which
  is why those columns are 0-for-184 and, even armed, would write to the CLIENT, not a colleague.
  Fix specified in task #31: split ABSTAIN (a truthful, sendable result) from ERROR (retry/park).

  **The replacement-signal question is DECIDED (it was a schema choice, not a business one).**
  `wa_outbox` has no jsonb/metadata column, but it already carries the exact precedent: `ack_sent_at`
  and `apology_sent_at`, nullable timestamps that record _what kind of thing_ was sent. So: add
  `abstained_at timestamptz NULL` and leave `status='done'`, because the row WAS sent. Additive,
  nullable, no backfill, no reader touched — the safest migration class. Rejected alternative: a new
  terminal `status='abstained'`. `wa_outbox.status` is read only inside `wa_outbox_worker.py`
  (`whatsapp_chat.py:916` reads a DIFFERENT table via `_META_STATUS_RANK`), so it would be
  containable — but it is still a shared format changed from one side (superscar #9), for no gain
  over a nullable column. Still NOT decided, and still deliberately so: auto-setting `human_handling`
  would mark a thread as owned by someone who does not know they own it. And do NOT overload
  `meta_inbox_messages.error` — it means "gave up" today, and a successful abstain written there
  breaks every query that reads it.

  **Contract note for whoever implements it:** `generate_bot_reply` returns a plain `str` and the
  worker treats it as opaque. Return a small result object (`text` + `abstained` + `reason`), do NOT
  signal the refusal by raising a custom exception: an abstain is a SUCCESSFUL send, and putting it
  on the exception path invites any intervening `except Exception` to swallow it straight back into
  a park — re-creating this exact bug one refactor later. The refusal copy must be IMPORTED from the
  shared constant #3260 introduces, never re-typed here (two copies drift — superscars #1/#9).

- **⚙️ MERGED + LIVE — PR #3261**: `security.yml` cancels superseded PR runs, never on main (it
  owns 4 of the 25 required checks). Content-verified on main: line 28 is
  `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}`. Two honest limits recorded on the
  PR: `cancel-in-progress: false` protects only a run that has already STARTED (a QUEUED run is
  superseded regardless), and the PR's claim to be copying `tests.yml`'s current form was WRONG —
  `tests.yml` had already moved to `${{ github.event_name == 'schedule' || ... }}` plus a separate
  group for the scheduled run (#3206). Alignment tracked as task #30.

- **⚠️ COORDINATION: check main by CONTENT before building a bot-adjacent fix.** On 2026-07-27
  three separate lanes independently built the same `<Money>` mock fix, main ended up with TWO
  separate guards for one `chdir` bug (#3265 and #3270), and one branch was one push away from
  DELETING a sibling's already-merged guard. Root cause measured: the pre-push allowlist sends
  frontend-only diffs through the full backend suite, so the machine ran 6 concurrent pushes at
  load 33, peaking at **59** an hour later — see memory
  `discovery_the_prepush_allowlist_is_how_the_fleet_saturates_itself_2026_07_27`. Read files that
  carry a decision with `git show origin/main:<path>`, never from the M5 checkout, which is kept
  behind on purpose.

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
  - **C17 — CLOSED, and this entry was STALE for days (corrected 2026-08-10 by re-reading the
    file, not the corner).** It used to say `format_rich_text` has "ZERO non-test callers in the
    whole codebase — dead code", so `###`/`**bold**`/`[1, 5]` reach WhatsApp raw. **Both halves are
    now false.** `wa_inbox_bot.py:46` imports it and `:389` calls `format_rich_text(answer,
"whatsapp")`, right after `_strip_kg_workflow_scaffold`, each with its own empty-result raise.
    And `_BARE_CITATION_RE` (`channels/format.py:88`) is the CURED, anchored version — it only
    matches a citation marker in TRAILING position (`(?=[.!?]?\s*(?:\n|\Z))`), which is precisely
    the fix for the near-miss recorded two bullets below (`Perpres 10/2021 Pasal 6 [1] dan [3]`
    must survive). Somebody wired it and nobody updated this line.
    **The trap this cost, and it is the reusable part:** a 2026-08-10 probe battery fired 12
    questions at `POST /api/agentic-rag/query` and scored `md_leak 10/12`, `kg_scaffold 8/12` —
    then read those as client-facing. They are not. **That endpoint is upstream of the channel
    boundary**; the WhatsApp client sees the output of `generate_bot_reply`, which strips both.
    Measuring the ENDPOINT and reporting it as the CLIENT SURFACE is the same error as measuring a
    merge and reporting it as live. Any future battery must re-render through
    `_strip_kg_workflow_scaffold` + `format_rich_text(…, "whatsapp")` before scoring anything
    presentational — and must therefore keep the FULL answer text, not a truncated head.
    ⚠️ Still TRUE for OTHER consumers: `apps/mouth` (web chat) calls the same endpoint and has no
    strip (see C18 / task #25) — the leak is real there, just not on WhatsApp.
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
- **🎫 Collateral finding: orphan test tree — CLOSED 2026-08-21**: `apps/backend-rag/tests/` (top-level, false coverage, scar #2) deleted; its 4 CI-used files (`test_sentry_lazy_import.py`, `test_sentry_pii_redaction.py`, `kb/test_politics_hierarchical.py`, `integration/test_p3_sandbox_egress.py` — the last one was a live `p3-sandbox-gates.yml` enforcing-gate dependency the original finding missed) moved into `backend/tests/`.
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

- **🔴 PROBED LIVE 2026-07-27 (3 calls on the prod `ask_legal` surface) — two client-facing
  defects, one of them fabricating a legal deadline.**

  | probe                                 | `model`                   | `tools_called` | `abstain` | outcome                                                                          |
  | ------------------------------------- | ------------------------- | -------------- | --------- | -------------------------------------------------------------------------------- |
  | "KITAS respinto, posso fare ricorso?" | `multi-agent-coordinator` | 3              | **false** | confident answer inventing **"30 giorni per il ricorso"** + a 51-96 day timeline |
  | E33G requirements                     | `unknown`                 | 0              | true      | correct stub                                                                     |
  | same rejection question, rephrased    | `unknown`                 | 0              | true      | correct stub                                                                     |

  **All three returned `sources: []`, `context_length: 0`, `evidence_score: 0`.** So the gate is
  not broken — it is UNREACHABLE on one route: the `multi-agent-coordinator` path ran 3 tools,
  produced an answer, and reported `abstain: false` at evidence 0. Rephrasing the SAME question
  took the other route and abstained honestly. This is the nondeterminism §1 already records
  ("same code, different luck in the ReAct loop") — but now with the consequence measured: on
  the unlucky route a client is told a **specific appeal deadline that no source supports**, and
  a missed immigration deadline is not recoverable. Tracked in tasks #20/#23.

  **Second defect, 3/3 — the KG workflow scaffold reaches the client on this surface.** Every
  answer carried `## SUGGESTED WORKFLOW (from visa_subgraph, confidence: NN%)` plus the internal
  trailer. Twice it directly CONTRADICTED the refusal printed immediately above it: an
  "I couldn't find relevant information" was followed by an IMTA/TKA work-permit workflow for a
  question about remote work, and by a one-step "VITAS Processing" for a question about appeals.
  `wa_inbox_bot._strip_kg_workflow_scaffold` cures exactly this — but only on the WhatsApp path,
  which is the 1-of-N consumer problem in task #25, now confirmed live rather than inferred.

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
- Opus 5 sessions orchestrate + final-gate (RULED 2026-08-20 — Fable is out of the workflow, CLAUDE.md §5); edits/commits/pushes go to Sonnet implementers
  (hook-enforced). Adversarial review before merge on client-facing surfaces.
- Off-limits without a fresh mandate: `zantara_core.py` (+ prompt chain in place), `fly.toml`,
  `.env*`. The prompt v4 lane has Zero's mandate but is ADDITIVE ONLY (new file + flag).
