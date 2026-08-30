---
date: 2026-08-28
domain: operations
part: B8 content-intel-pipeline
scope: Intel scraper → article composer → magazine, WR2 carousels, WR3 video, zantara-media curator, NAGA research, councils/critics/fact-gates, publishers — anatomy, SOTA benchmark, gap table, recommendations
sources:
  - https://mediacopilot.ai/newsroom-ai-strategies/
  - https://www.niemanlab.org/2026/07/how-three-newsrooms-are-charting-different-paths-for-ai-use/
  - https://talkingbiznews.com/media-news/how-reuters-is-using-artificial-intelligence-3/
  - https://www.niemanlab.org/2023/10/the-ap-announces-five-ai-tools-to-help-local-newsrooms-with-tasks-like-transcription-and-sorting-pitches/
  - https://techcrunch.com/2014/07/01/the-ap-is-using-robots-to-write-earnings-reports
  - https://rsf.org/en/rsf-and-16-partners-unveil-paris-charter-ai-and-journalism
  - https://tvnewscheck.com/tech/article/content-authentication-initiative-c2pa-hits-some-bumps-in-the-road/
  - https://show.ibc.org/accelerator-project-stamping-content-c2pa-provenance
  - https://www.futuremediahubs.com/future-media-hubs/cases/c2pa-content-credentials-verification
  - https://pipeline.zoominfo.com/sales/crayon-vs-klue
  - https://unkover.com/blog/ai-competitive-intelligence/
  - https://arxiv.org/pdf/1809.08193
  - https://arxiv.org/pdf/2407.02351
  - https://www.emergentmind.com/topics/agentic-fact-checking-system-architecture
  - https://signal-ai.com/signal-ai-vs-meltwater-media-intelligence-platform-comparison/
  - https://www.meltwater.com/en/ai
  - https://www.frontify.com/en/blog/the-future-of-brand-governance-is-machine-readable
  - https://www.forbes.com/sites/enriquedans/2019/02/06/meet-bertie-heliograf-and-cyborg-the-new-journalists-on-the-block/
status: DONE 2026-08-29
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# B8 — Content & Intel Pipeline: Beyond-SOTA Report

## Anatomy (as measured)

The content-intel organism is five coupled machines: an **intel ingestion pipeline**, an **editorial brain** (multi-LLM councils + agent fan-out), a **render/publish layer**, a **feedback/learning loop**, and a **native operator surface**. All measurements below are against the worktree pinned at `origin/main 11a3c89a2e`.

### 1. Intel ingestion (bali-intel-scraper → Intel Lake)

The daily pipeline driver is `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` (2,753 lines). Its step list at `run_intel_pipeline.py:47-60` defines 12 stages: scraping → validation → LLM filter (`gemma4:26b`, threshold `quality_score >= 30`) → 4-dimension quality gate → T1-source cross-verification → semantic clustering into dossiers → NotebookLM legal context → Claude deep enrichment (1,400-2,000-word articles) → Gemini SEO → Telegram approval → cover images (Fireworks Flux.1, Pollinations fallback) → publishing. It runs **locally on Pro at 03:00 WITA** (per `apps/bali-intel-scraper/CLAUDE.md` §Deployment), never on Fly.

The quality gate (`apps/bali-intel-scraper/scripts/quality_gate.py:41-50`) scores four weighted dimensions — relevance 0.35, urgency 0.20, reliability 0.20, business impact 0.25 — with three-way routing: composite ≥0.70 auto-publish, ≥0.40 review, below archive. Reliability uses a source-tier table (T1=1.0 / T2=0.70 / T3=0.40, `quality_gate.py:61-64`); business impact maps topics to CRM service categories (`quality_gate.py:66-69`) — a genuinely rare feature (scoring news by *client-book overlap*, not just topicality).

Upstream classification is primitive by contrast: `services/intel/intel_classification_service.py:49-62` routes visa-vs-news by category string match plus bare keyword counting. The canonical store is **Intel Lake** (`services/intel/intel_lake_service.py:1-14`): UPSERT into `intel_items` + append-only `intel_observations`, with immutability invariants (title/summary/content_hash frozen post-first-write; content drift → new row, never silent mutation) — an event-sourced provenance design. `TrendHunterOrchestrator` (`services/intel/trend_hunter/__init__.py:1-13`) is the sensory layer on a 2h cadence — but only RSS is implemented; Bali Post scraping, Reddit PRAW, and Google Trends are marked "deferred" in the module docstring. `DossierCompiler` (`services/intel/dossier_compiler.py:1-15`) clusters unconsumed trend signals into research dossiers via Claude CLI with strict JSON schema.

### 2. Editorial brain (WR2 orchestration + councils)

WR2's carousel brain is 8 agent definitions in repo `.claude/agents/wr2-*.md` with an explicit CANON marker (`wr2-design-architect.md:12`: "vendored 2026-07-16, shadows ~/.claude/agents copy"). The orchestrator contract is unusually hard-edged: **Contract A** mandatory fan-out to 4 specialists with a self-check that counts Agent invocations and aborts `STATUS: fanout_violated` if <4; **Contract B** NB ground-truth with `nb_sources_consulted` ≥1 and a verbatim `nb_query_log`, else abort `ground_truth_missing`; **Contract C** no silent hero-image placeholder reuse, enforced by sha256 anchor comparison. Cost discipline is codified from a measured incident (test-5: $10.07/29min/165 tool calls) down to exactly 4 audit Bash calls per run.

Register selection is a real multi-agent debate: `services/council/tone_council.py:1-12` runs 3 isolated proponents → a structured challenge round (each scores non-own proposals and criticizes the worst — "forces structural dissent") → a judge with veto, plus hard anti-repetition rules (`tone_council.py:38-40`: max 3 same-register/7d, groupthink concordance threshold 0.90). The **Consiglio** (`services/research/consiglio_orchestrator.py:1-20`) does 4-LLM playbook synthesis with a Gate-6 invariant (every final claim ≥3/4 LLM agreement; disputed claims kept but flagged ⚠️) and honest degradation accounting (`meta["active_llms"]`).

### 3. Runtime orchestration (event-driven supervisor + fact gate)

`scripts/wr2_supervisor.py` replaced five chained fixed-time launchd plists with a Postgres `NOTIFY wr2_status_change` listener plus a state machine (`wr2_supervisor.py:93-103`): `briefed → drafts → drafts_imaged → drafts_imaged_facted → drafts_imaged_checked → html-apply`, terminal states `rendered`/`fact_check_failed`/`rejected`/`parked` alert-only. It carries the SOTA properties: per-draft locking, stale-payload re-read, dedup, startup + periodic reconciliation sweeps for lost NOTIFYs, SIGTERM drain.

The **fact gate** is the crown jewel. `scripts/wr2_fact_checker.py:1-50`: claims extracted by `wr2_fact_extractor.py` are verified deterministically (regex law citations `PP \d+/\d{4}`, number/date token match) with LLM cross-check only for paraphrase, and every pass/degraded verdict carries a **provenance class** (`supported_by_source_article` / `independently_corroborated` — defined but never yet emitted / `source_absent` / `claim_unparseable`). The 2026-08-03 change closed a fail-open hole: `source_absent` and `claim_unparseable` now route to `fact_check_failed` for manual review instead of silently reaching render. Canva-apply is locked to `status='drafts_imaged_checked'` only.

Image QA is dual-voice (`services/visual/qa_judge.py:1-10`): local `qwen2.5vl:7b` produces structured flags, Claude Haiku issues pass/retry/hard-reject, deterministic fallback if the judge is down.

### 4. Publish layer (fail-closed by construction)

`services/publisher/orchestrator.py:40-71`: the WR2 publisher kill switch reads `system_settings.wr2_publisher_enabled` and **fails closed** on any DB error. Platform publishers (blog, IG, LinkedIn, X — `services/publisher/`) fan out in isolation with per-publisher retries and idempotency on `(draft_id, platform)`. The IG server-side path (`app/routers/wr2_publish.py:1-40`) is operator-gated (Legge 5): `confirm=False` returns a dry-run of exactly what would be posted; the real publish is guarded by a `wr2_publish_attempts` ledger with idempotency key `<carousel_id>:<platform>:<content_hash[:16]>`, HTTP 409 + prior permalink on re-attempt, fail-closed on DB unreachable. Human publish confirmation even has a WhatsApp-native path: `scripts/wr2_damar_publish_consumer.py:1-30` parses `PUBBLICATO WR2-XXXX <ig_url>` messages from the designer's mirrored WhatsApp channel with exact ref-code match and an unmatched-JSONL dead letter (never silently dropped).

Review is Telegram-native (`services/review/review_handler.py:1-13`): cover + caption + inline keyboard to Zero's chat, owner-only authorization (`review_handler.py:47`), idempotent callbacks against Telegram webhook retries, plus an SLA worker (`services/review/sla_worker.py`).

The **magazine** (`apps/bali-zero-magazine`) is a separate Cloudflare/OpenAI-Sites (vinext) property with D1 + R2 bindings and machine-HMAC ingress (`worker/index.ts:13-21`), publishing a morning edition + breaking updates. Its publish wrapper is Pro-host-gated (`infra/launchagents/wrappers/bali-zero-magazine-publish.sh:26-29`: exit 78 if hostname ≠ Nuzantara).

### 5. Feedback & learning loop

The loop closes on paper: `services/learner/__init__.py:1-13` — composite score per post at T+72h; >p70 → skill in Genome, <p20 or rejected-by-Zero → scar in cicatrix; `memoria_episodica` (≤2,000 chars) injected into the next Consiglio. Cron support: `com.balizero.wr2.learner-nightly`, `ig-metrics-scrape.daily` + `ig-metrics-analyst.weekly`, `external-bench.monthly` (12 reference brands + 3 competitors), `wr3.reflexion.weekly` — 36 WR2/WR3/magazine/intel plists among 156 total in `infra/launchagents/`.

### 6. Adjacent organs

**NAGA** (`services/naga/orchestrator.py:1-40`, 28 files/4,075 lines) is a sequential deep-research loop with a Pointer State Pattern (evidence map on disk, URI in state), CRAG-light quality evaluation, source scoring, convergence checks, and budget tracking; registered `_RAG` (`router_manifest.py:317`). **zantara-media** (`apps/zantara-media`) is the GARUDA Drive curator: indexer, per-channel composers, and a DLP PII guard (NIK/KITAS/NPWP detection) before anything leaves. **wr2-control-app** is a native SwiftUI macOS operator app (`Sources/ClaudeRunner.swift`, `CarouselIO.swift`, `InstagramCaption.swift`). Routers registered per manifest: `article_composer` (:135), `blog_ask` (:138), `intel*` (:279-287), `media` (:311), `naga` (:317), `news` (:321), `war_room_dashboard` (:397), `wr2_publish` (:403). Test breadth: 88 test files across war_room/publisher/council/intel/naga/review paths.

## Honest state vs. SOTA

**Genuinely good — rare even among professional newsrooms:**

1. **Adversarial, generator≠grader editorial gates.** A separate critic agent with binary per-slide verdicts, a deterministic fact-checker with a provenance taxonomy that *names its epistemic basis* per claim, and a fail-closed evolution history (the 2026-08-03 hole-closing) — most commercial content-ops platforms have nothing comparable.
2. **Fail-closed publishing.** Kill switch, idempotency ledger, dry-run-by-default confirm gate, dead-letter for unmatched human confirmations. Financial-systems discipline applied to social publishing.
3. **Business-impact-weighted triage.** Scoring news by CRM client-book overlap (`quality_gate.py:66-69`) is a competitive-intel feature Crayon/Klue sell as premium.
4. **A closing learning loop** (T+72h engagement → genome/scar → next council injection) plus monthly external benchmarking — structurally a Reflexion/Voyager architecture, which published newsroom systems do not have.
5. **Anti-groupthink councils** with concordance thresholds and forced-dissent rounds.

**Theater or drift:**

1. **DeepSeek is still load-bearing in code, retired in doctrine.** `consiglio_orchestrator.py:10` names "DeepSeek V4 Pro Think Max ($0.01/query)" as a voter (roster tuple at `:70`); the `article_composer` router imports `DeepSeekError`/`DeepSeekAuthError` and advertises "DeepSeek enrichment (~100x cheaper than Claude Sonnet)" (`app/routers/article_composer.py:16,39`). The seat was retired 2026-07-19 (HTTP-402 dead, pre-auth revoked). The Consiglio silently degrades to 3 voters; the composer's enrichment path is dead weight (runtime behavior unverified, but the credential is documented dead).
2. **WR3's brain is a HOME-fork.** All 13 `wr3-*` agent definitions exist ONLY in `~/.claude/agents/` — not in the repo — with `.bak-drift-20260616` files proving past divergence. The repo holds only `wr3_*.py` scripts, one plist (`com.balizero.wr3.reflexion.weekly`) and a spend-gate workflow; `apps/war-room/output/episode/` referenced by the WR3 agents does not exist in the tree. The WR2 vendoring (2026-07-16) fixed exactly this class and stopped short of WR3. Superscar family #1 in its purest form.
3. **Empty organs.** `services/social/` is one file, one line. Trend-hunter's Reddit/Google-Trends/Bali-Post adapters are docstring-deferred. `independently_corroborated` provenance is defined but never emitted — the fact-checker verifies against *its own research inputs*, not independent retrieval.
4. **Head-of-pipeline classification is 2015-era.** Keyword counting (`intel_classification_service.py:53-58`) feeds everything downstream; the sophisticated gates guard a coarse intake.
5. **No provenance or AI-disclosure on outputs.** Zero grep hits for C2PA/content-credentials/disclosure across `services/publisher/` and the magazine. A pipeline internally obsessive about claim provenance publishes externally with none.
6. **Cron sprawl as fragility.** 36 content plists on one Mac, WR2 ones invoked through `/Users/nuzantara/.openclaw/bin/wr2/wr2-script-wrapper.sh` (HOME-path bridge, per plist ProgramArguments) — the supervisor absorbed 5 stages but the constellation still depends on launchd + one host + one wrapper path.

## Deep research: the world's best

**Reuters — speed lanes with governance checkpoints.** Reuters runs [Lynx Insight](https://talkingbiznews.com/media-news/how-reuters-is-using-artificial-intelligence-3/) (real-time financial data analysis) and Fact Genie (press-release processing) to publish breaking financial alerts in **6-8 seconds**, while requiring journalists to verify every AI-generated claim before publication — editor-in-chief Galloni describes "governance checkpoints built in at each stage" ([MediaCopilot summary of the AP/Nieman piece](https://mediacopilot.ai/newsroom-ai-strategies/), [Nieman Lab 2026-07](https://www.niemanlab.org/2026/07/how-three-newsrooms-are-charting-different-paths-for-ai-use/)). The engineering pattern: **automation buys speed only inside a template + verification envelope**; the human gate is placed where the marginal risk is, not everywhere.

**BBC — disclosure as a product feature.** BBC's Style Assist reformats agency copy into house style (replacing a 30-minute manual task) and At a Glance summarizes articles — both behind **mandatory editor sign-off, no exceptions**. After its October 2025 research found AI assistants misrepresented news content 45% of the time, the BBC introduced **AI disclosure labels at the top of stories** ([MediaCopilot](https://mediacopilot.ai/newsroom-ai-strategies/)). The Guardian's variant: senior-editor approval of *task categories* (alt text, parliamentary document analysis, transcription) rather than per-item review — approval granularity as a scaling lever.

**AP / Heliograf / Cyborg — structured-data-first automation.** AP has generated earnings stories straight from structured data feeds since [2014](https://techcrunch.com/2014/07/01/the-ap-is-using-robots-to-write-earnings-reports), expanding coverage from ~300 to ~4,400 companies/quarter; the Washington Post's Heliograf produced ~850 templated articles in year one (elections, Olympics); Bloomberg's Cyborg automates roughly a third of published output ([Forbes](https://www.forbes.com/sites/enriquedans/2019/02/06/meet-bertie-heliograf-and-cyborg-the-new-journalists-on-the-block/)). AP's [five local-newsroom AI tools](https://www.niemanlab.org/2023/10/the-ap-announces-five-ai-tools-to-help-local-newsrooms-with-tasks-like-transcription-and-sorting-pitches/) target the same shape: automate the structured/repetitive (transcription, pitch sorting), keep judgment human. Pattern: **the highest-ROI automation is where the input is already structured** — earnings tables, gazette entries, regulation numbers — because verification becomes string comparison, not epistemology.

**Norms: the Paris Charter.** [RSF + 16 partners' Paris Charter on AI and Journalism](https://rsf.org/en/rsf-and-16-partners-unveil-paris-charter-ai-and-journalism) (Ressa commission, 10 principles) sets the two rules the industry is converging on: responsibilities for AI systems must be **assigned to named humans**, and any AI use with significant impact on content production must be **disclosed to the audience alongside the content**.

**Provenance: C2PA / Content Credentials.** The BBC, EBU and IPTC are driving newsroom adoption of C2PA signing — an [IBC Accelerator built a stamping tool that signs and verifies video at the point of publication](https://show.ibc.org/accelerator-project-stamping-content-c2pa-provenance); trials showed **83% of users reporting increased trust** after seeing Content Credentials ([Future Media Hubs](https://www.futuremediahubs.com/future-media-hubs/cases/c2pa-content-credentials-verification)). Adoption is genuinely hard — platform strippage and the spec making editorial-provenance display optional are live problems ([TVNewsCheck](https://tvnewscheck.com/tech/article/content-authentication-initiative-c2pa-hits-some-bumps-in-the-road/)) — but the engineering unit is simple: **sign at render, verify at publish, carry org identity**.

**Fact-checking as an engineering discipline.** Full Fact's claim-detection work ([Konstantinovskiy et al.](https://arxiv.org/pdf/1809.08193)) established sentence-level claim detection with an objective annotation schema (7 claim types), outperforming ClaimBuster; the current research consensus ([LLM fact-checking survey](https://arxiv.org/pdf/2407.02351), [agentic fact-checking architectures](https://www.emergentmind.com/topics/agentic-fact-checking-system-architecture)) decomposes the pipeline as claim detection → **independent evidence retrieval** → verdict prediction → justification generation, with the retrieval step being what separates verification from self-confirmation. Nuzantara's fact-checker already has the verdict taxonomy; what SOTA adds is the independent-retrieval leg it explicitly deferred.

**Competitive intelligence platforms.** [Crayon](https://pipeline.zoominfo.com/sales/crayon-vs-klue) is coverage-first (monitoring 300M+ pages across 7.6M domains — site diffs, pricing pages, job postings, reviews — with "Sparks" compressing raw signals into battlecards); [Klue](https://unkover.com/blog/ai-competitive-intelligence/) is distribution-first (battlecards pushed into Salesforce/Slack; its Compete Agent generates *deal-specific* competitive insight at the moment a rep needs it). The transferable pattern: **intelligence is valued at the point of use** — the delivery surface (inside the seller's tool, scoped to the live deal) matters more than the analysis.

**Media monitoring.** [Signal AI's AIQ](https://signal-ai.com/signal-ai-vs-meltwater-media-intelligence-platform-comparison/) combines discriminative entity-based retrieval ("apple" fruit vs "Apple" company) with RAG generation and *measures citation accuracy* (claims 95% vs a 75% industry benchmark); [Meltwater's Mira](https://www.meltwater.com/en/ai) does entity-level five-point sentiment with webhook-triggered real-time enrichment. Pattern: **entity resolution, not keywords, at intake — and citation accuracy as a tracked KPI**, not an aspiration.

**Brand governance.** The frontier ([Frontify: machine-readable brand governance](https://www.frontify.com/en/blog/the-future-of-brand-governance-is-machine-readable)) is encoding brand constraints as structured, machine-readable rules enforced *inside* the generation workflow rather than checked after. Nuzantara's `bali-zero-brand` constitution with numbered articles enforced by a critic agent (Article 6.2 bilingual assist, 6.3 bullet-promise, 5.10 sha-verified no-reuse) is **already this** — arguably ahead of the commercial products, which either apply brand kits without evaluating compliance (Canva) or hold guidelines without inspecting output (Frontify).

**Multi-agent editorial research.** Published 2025 practice (LangGraph-style Analyzer→Writer→…→Critic→Refiner chains with score-gated rerouting; committee-of-reviewers blueprints like [APIGen-MT](https://openreview.net/forum?id=qk6ORqQ4Cu)) matches — and does not exceed — WR2's fan-out + binary critic gate + Reflexion synthesis. The academic frontier's one addition worth stealing: **cheap-model pre-pass / expensive-model escalation inside the critic** (WR3's Haiku-VLM-then-Opus design has this; WR2's critic runs single-tier).

## Gap table

| Dimension | Nuzantara today (measured) | Sector SOTA | Verdict |
|---|---|---|---|
| Ingestion breadth | RSS-only live; Reddit/Trends/Bali-Post deferred (`trend_hunter/__init__.py:5-9`) | Crayon: 300M pages, site-diff/pricing/job-posting signals | **Behind** |
| Intake classification | Keyword counting (`intel_classification_service.py:53-58`) | Entity-based retrieval + resolution (Signal AIQ) | **Behind** |
| Quality triage | 4-dim weighted gate incl. CRM overlap (`quality_gate.py:41-69`) | Topical relevance scoring; client-overlap is premium CI territory | **At/ahead** |
| Fact verification | Deterministic + LLM cross-check, provenance taxonomy, fail-closed (`wr2_fact_checker.py`) | Claim detection + **independent** evidence retrieval (Full Fact, agentic FC) | **Split**: taxonomy ahead, independent retrieval missing |
| Editorial multi-agent | Contract-enforced fan-out, adversarial critic, tone council with anti-groupthink | Critic-gated agent chains (research-grade) | **At/ahead** |
| Human-in-the-loop | Telegram review gate, owner-authz, idempotent, SLA worker | BBC mandatory sign-off; Guardian task-category approval | **At** |
| Speed lane (breaking) | Daily 03:00 batch; magazine "breaking" mode exists | Reuters 6-8s templated alerts inside verification envelope | **Behind** |
| Output provenance/disclosure | None (zero C2PA/disclosure hits in publisher + magazine) | BBC AI labels; C2PA sign-at-publish; Paris Charter disclosure | **Missing** |
| Brand governance | Machine-readable constitution + critic enforcement + sha anchors | Frontify "machine-readable governance" (checked, not enforced) | **Ahead** |
| Learning loop | T+72h score → genome/scar → council injection; monthly external bench | Not present in published newsroom systems | **Ahead** |
| Delivery at point of use | Telegram digest to owner; designer WhatsApp loop | Klue: deal-scoped battlecards inside seller's tools | **Behind** |
| Ops substrate | 36 plists, one Mac, HOME-path wrapper; supervisor event-driven core | Managed queues/workflows, multi-tenant | **Behind** (fragile) |
| Doctrine↔code coherence | DeepSeek retired in doctrine, live in Consiglio/composer code | n/a (internal) | **Drifted** |

## Recommendations — reach SOTA

1. **P0 — Purge the DeepSeek ghost seat.** Replace the DeepSeek voter in `consiglio_orchestrator.py` with the Kimi K3 seat (already doctrine) and remove/replace the DeepSeek enrichment path in `app/routers/article_composer.py`. *Acceptance (falsifiable): `grep -ri deepseek` over `services/research/ services/article_composer/ app/routers/article_composer.py` returns only historical comments; a new test asserts the Consiglio voter roster matches `FLEET_TOPOLOGY.json`; Consiglio smoke run reports `active_llms=4`.*
2. **P0 — Vendor WR3's brain into the repo.** Copy the 13 `~/.claude/agents/wr3-*.md` into `.claude/agents/` with the same CANON marker WR2 got on 2026-07-16, and register the pairs in `scripts/lint_home_fork.py`. *Acceptance: `ls .claude/agents/wr3-*.md | wc -l` = 13; `lint_home_fork.py` covers them and exits 0; a deliberate 1-byte HOME edit makes it exit non-zero.*
3. **P0 — AI-involvement disclosure on every published surface.** Add a machine-readable `ai_involvement` field to `DraftPayload`/staging payloads and render a visible label on blog/magazine articles and IG captions (BBC pattern; Paris Charter principle). *Acceptance: publisher unit test fails if a payload lacks the field; 10 consecutive published artifacts carry the visible label; the label text is ratified by Zero (see §Solo-operatore).*
4. **P1 — Arm `independently_corroborated`.** Give the fact-checker its missing independent-retrieval leg: at check time, re-query NotebookLM/Intel Lake (not the draft's own `research_json`) for each law/number claim. *Acceptance: the provenance distribution over 20 consecutive drafts shows >0% `independently_corroborated`; the fail-closed routing for `source_absent` stays intact (existing tests green).*
5. **P1 — Entity-based intake classification.** Replace keyword counting with local embedding classification (bge-m3 is already in the Ollama arsenal) or LLM structured output, keeping the keyword path as fallback. *Acceptance: blind A/B on 200 historical Intel Lake items; misroute rate of the new path ≤ half the keyword baseline, measured against hand-labeled ground truth.*
6. **P1 — A breaking-news speed lane.** Heliograf/Reuters pattern scoped to structured regulatory events: T1 trend-hunter signal matching a gazette/regulation pattern → templated alert draft → Telegram confirm → publish, bypassing the 03:00 batch. *Acceptance: measured wall-time signal→approved-alert < 30 minutes on 3 live events (vs current next-morning latency); zero alerts published without the confirm callback.*
7. **P2 — C2PA Content Credentials at render.** Sign carousel PNGs and magazine covers with `c2patool` in the render step, org identity Bali Zero. *Acceptance: `c2patool <published-tigris-url>` reads back a valid manifest for a live post; strippage on IG documented as known-limitation, blog/magazine verified end-to-end.*
8. **P2 — Fold residual fixed-time plists into the supervisor.** Extend the TRANSITIONS state machine to absorb the remaining chained stages. *Acceptance: WR2 plist count reduced ≥40% from 33; the daily e2e probe stays green for 14 consecutive days.*

## Recommendations — beyond SOTA

1. **P1 — Client-scoped intel delivery ("battlecards for immigration").** The Klue Compete-Agent pattern applied to an agency: when a T1 intel item's `service_category_map` intersects a team member's assigned client segment, push a one-paragraph advisory draft to that member (S7-derogation delivery shape: name+initial, client_id, deadline — no new PII surface). No newsroom does this; only premium CI platforms approximate it. *Acceptance: ≥50% of T1 published items generate an advisory within 24h; conversions (advisory → client consultation) tracked in CRM for 30 days.*
2. **P1 — End-to-end provenance ledger.** Intel Lake already freezes content hashes at intake; the fact-checker already binds claims to sources; C2PA (rec 7 above) signs the output. Join them: one queryable lineage `source_url → intel_item hash → claim_id → slide → published permalink`. That chain — intake-to-post cryptographic provenance — is beyond what BBC/IPTC have shipped. *Acceptance: for any of 10 spot-audited published posts, a single CLI query returns the full lineage with no manual joins.*
3. **P2 — Self-tuning quality gate.** Close the loop the learner already half-built: propose `quality_gate.yaml` weight amendments from T+72h engagement + advisory-conversion data, as `_proposed-amendments/` files a human ratifies (never auto-applied; tripwire test pins the ratified values). *Acceptance: after one ratified amendment cycle, auto-publish precision (published items not later rejected/parked) improves measurably vs the frozen baseline on a 30-day window.*
4. **P2 — Counterfactual register measurement.** The tone council picks a register; nobody measures whether the debate adds value. Shadow-render the runner-up register for 1-in-5 carousels and A/B alternate them. *Acceptance: N=20 pairs; council-chosen register wins engagement >60% of pairs, else the council is simplified to a single judge (cost saving is itself a win — the test is falsifiable in both directions).*

## §Meta-pattern

**Cathedral gates on a dirt road.** The pipeline's *middle* — fact gates, critic contracts, fail-closed publishing, idempotency ledgers — is stronger than anything the commercial sector ships. Both *ends* are weak: intake is keyword-matching over an RSS trickle, and the public-facing output carries none of the internal epistemic rigor (no disclosure, no provenance). The organism is rigorous exactly where nobody outside can see it, and permissive where the world touches it.

Second pattern, familiar from the superscar families: **ruling-code drift**. Doctrine retired DeepSeek on 2026-07-19; five weeks later it is still a named voter in the Consiglio and an advertised enrichment path in a live router. The WR3 HOME-only brain is the same disease (family #1) at the agent-definition layer. Rulings propagate to CLAUDE.md instantly and to code only when someone happens to touch the file — there is no lint that walks the roster.

## §Solo-operatore

Decisions only Zero can take (business, spend, risk — Legge 5):

1. **Public AI-disclosure wording and stance.** Labeling content "AI-assisted, human-reviewed" is a positioning choice for a paid advisory brand — it can read as transparency-differentiator or as discount signal. The engineering (rec SOTA-3) is trivial; the stance is not.
2. **Fund or archive WR3.** The video pipeline's brain lives outside the repo, its output tree doesn't exist, and one weekly cron survives. Either it gets the vendoring + a production mandate, or it is formally archived — half-alive is the worst state (it consumes benchmark/reflexion cron cycles for a product that doesn't ship).
3. **Ingestion spend.** Widening beyond RSS (Exa/Brave quotas via NAGA's existing budget tracker, or scraping infrastructure) has a monthly cost; the free tier ceiling is where CI-platform-grade coverage starts costing real money.
4. **Client-scoped advisory delivery** (beyond-SOTA rec 1) extends the S7 WhatsApp derogation from yield digests to intel advisories — same payload shape, new trigger. That extension of a named Legge-2 derogation is exactly what CLAUDE.md §14 says must not be re-derived by a session; it needs an explicit ruling.
5. **C2PA signing identity** — the org certificate is a legal-identity artifact only the owner can commission.
6. **IG publish automation level.** Damar's manual publish (Law 5) is currently load-bearing in the feedback loop; automating past it changes a person's role, not just a pipeline.

## Sources

1. https://mediacopilot.ai/newsroom-ai-strategies/ — Reuters/BBC/Guardian AI paths (fetched; carrier of the AP/Nieman reporting)
2. https://www.niemanlab.org/2026/07/how-three-newsrooms-are-charting-different-paths-for-ai-use/ — original Nieman Lab piece
3. https://talkingbiznews.com/media-news/how-reuters-is-using-artificial-intelligence-3/ — Lynx Insight / Fact Genie, 6-8s alerts
4. https://www.niemanlab.org/2023/10/the-ap-announces-five-ai-tools-to-help-local-newsrooms-with-tasks-like-transcription-and-sorting-pitches/ — AP local-newsroom AI tools
5. https://techcrunch.com/2014/07/01/the-ap-is-using-robots-to-write-earnings-reports — AP structured-data earnings automation
6. https://www.forbes.com/sites/enriquedans/2019/02/06/meet-bertie-heliograf-and-cyborg-the-new-journalists-on-the-block/ — Heliograf / Cyborg
7. https://rsf.org/en/rsf-and-16-partners-unveil-paris-charter-ai-and-journalism — Paris Charter (10 principles, disclosure + assigned human responsibility)
8. https://show.ibc.org/accelerator-project-stamping-content-c2pa-provenance — IBC C2PA stamping-at-publication tool
9. https://www.futuremediahubs.com/future-media-hubs/cases/c2pa-content-credentials-verification — BBC/EBU Content Credentials trials (83% trust uplift)
10. https://tvnewscheck.com/tech/article/content-authentication-initiative-c2pa-hits-some-bumps-in-the-road/ — C2PA adoption obstacles
11. https://arxiv.org/pdf/1809.08193 — Full Fact claim-detection annotation schema (Konstantinovskiy et al.)
12. https://arxiv.org/pdf/2407.02351 — survey: LLMs in automated fact-checking
13. https://www.emergentmind.com/topics/agentic-fact-checking-system-architecture — agentic fact-checking decomposition (independent evidence retrieval)
14. https://pipeline.zoominfo.com/sales/crayon-vs-klue — Crayon coverage model / Klue distribution model
15. https://unkover.com/blog/ai-competitive-intelligence/ — Klue Compete Agent, deal-scoped insight
16. https://signal-ai.com/signal-ai-vs-meltwater-media-intelligence-platform-comparison/ — Signal AIQ entity-based retrieval, 95% citation accuracy
17. https://www.meltwater.com/en/ai — Meltwater Mira, entity-level enrichment
18. https://www.frontify.com/en/blog/the-future-of-brand-governance-is-machine-readable — machine-readable brand governance
19. https://openreview.net/forum?id=qk6ORqQ4Cu — APIGen-MT reviewer-committee pipeline pattern
