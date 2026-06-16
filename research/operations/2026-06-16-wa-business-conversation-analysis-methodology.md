---
date: 2026-06-16
domain: operations
client_case: none
sources:
  - https://www.maestroqa.com/blog/how-to-build-a-qa-scorecard
  - https://www.zendesk.com/blog/quality-assurance/workforce-optimization/qa-scorecard/
  - https://www.calabrio.com/blog/quality-assurance-qa-scorecard/
  - https://www.balto.ai/blog/call-center-quality-assurance-metrics/
  - https://justcall.io/blog/customer-service-metrics-kpis.html
  - https://www.intercom.com/learning-center/customer-service-metrics
  - https://www.sqmgroup.com/resources/library/blog/fcr-metric-operating-philosophy
  - https://formbricks.com/blog/customer-effort-score
  - https://www.plecto.com/blog/customer-service/csat-vs-nps-vs-ces/
  - https://thelevel.ai/blog/conversation-analytics-software/
  - https://www.lorikeetcx.ai/articles/best-ai-qa-tools-support
  - https://authenticx.com/page/types-of-conversation-analysis/
  - https://edulearn.intelektual.org/index.php/EduLearn/article/view/21041
  - https://emcawiki.net/Adjacency_pair
  - https://secondnature.ai/meddpicc-spin-or-bant-the-right-sales-technique-for-your-organization/
  - https://www.claap.io/blog/bant-vs-spin
  - https://delvetool.com/blog/grounded-theory-vs-thematic-analysis
  - https://getthematic.com/insights/coding-qualitative-data
  - https://arxiv.org/pdf/2507.21017
  - https://blog.jetbrains.com/pycharm/2026/05/llm-evaluation-and-ai-observability-for-agent-monitoring/
  - https://www.gorgias.com/blog/whatsapp-for-customer-service
  - https://www.salesforce.com/service/contact-center/whatsapp-for-customer-service/
  - https://wolf.financial/blog/brand-voice-guide-financial-marketing-compliance
---

# Methodology: Analyzing Business / Customer-Service WhatsApp Conversations for Agent Evaluation

**Scope & purpose.** This is a public-methodology framework for evaluating individual customer-service agents at a regulated advisory firm (immigration / tax / company-setup) whose primary channel is asynchronous WhatsApp. It synthesizes contact-center QA literature, conversation-analytics vendor frameworks, academic Conversation Analysis (CA), sales-qualification models, qualitative-coding methods, and the current LLM-assisted auto-QA debate. It contains **no client data, no PII** — only the analytical scaffolding. The core principle throughout: combine **quantitative operational telemetry** (cheap, 100%-coverage, gameable) with **qualitative scorecard judgment** (expensive, sampled, meaningful), and never let one stand in for the other.

---

## 1. Operational / Quantitative Metrics

These are the channel-level "vital signs" — derivable from message timestamps and conversation metadata without reading content.

- **First Response Time (FRT):** elapsed time from a customer's inbound message to the agent's first *meaningful* reply. Formula: total first-reply times / number of conversations. Benchmarks vary by channel — chat <90s, email <24h, phone <3min — but messaging sits between live chat and email (JustCall; Intercom; Gorgias).
- **Average / Next Response Time (ART / NRT):** mean time to *subsequent* replies within an open thread. In async WhatsApp this matters more than FRT, because a single conversation can span days with many turns; NRT captures whether an agent keeps the thread warm or lets it stall (Gorgias).
- **Resolution Time:** total duration from conversation open to closure. Formula: total resolution time / conversations resolved (JustCall).
- **First-Contact Resolution (FCR):** % of issues fully resolved without a follow-up contact. Formula: (resolved on first contact / total) x 100; industry benchmark 60–80%. FCR is widely treated as the single highest-leverage operational metric because it correlates strongly with CSAT and inversely with repeat-contact rate (SQM Group; JustCall).
- **Message volume & inbound/outbound ratio:** interactions handled per agent per day/week, and the ratio of agent-sent to customer-sent messages. Volume must always be read *alongside* quality, never in isolation (JustCall).
- **Conversation length / turns:** number of message exchanges to resolution; an outlier-long thread can signal either complexity or poor handling.
- **After-hours coverage:** share of inbound arriving / answered outside business hours — load-bearing for a Bali-based firm serving European (Italian) and other time-zone clients.
- **SLA adherence:** % of first responses (and resolutions) inside the agreed target. Formula: responses within SLA / total responses (Freshworks/JustCall). Adjacent operational metrics: **occupancy** (75–85%), **schedule adherence** (90–95%), **repeat-contact rate**, **handover/escalation rate**, and **backlog/unread** (open threads awaiting an agent reply) (JustCall; Balto).

---

## 2. CX Outcome Metrics

Operational speed is a proxy; outcome metrics measure whether the customer was actually served well.

- **CSAT (Customer Satisfaction):** post-interaction "How satisfied were you?" on a 1–5 or 1–10 scale; CSAT = satisfied responses / total x 100; benchmark >85% (JustCall; Plecto).
- **NPS (Net Promoter Score):** relational loyalty, "How likely to recommend?" 0–10; NPS = %promoters(9–10) - %detractors(0–6); >50 excellent (Plecto).
- **CES (Customer Effort Score):** "How easy was it to get your issue resolved?" on a 5–7-point Likert; strong retention predictor; use after task-based interactions (Formbricks; Plecto).
- **Sentiment analysis:** automated polarity/emotion scoring across the thread — the *only* outcome signal available at 100% coverage when surveys are sparse. Track trajectory (did sentiment recover by the close?) not just average (thelevel.ai; Authenticx).
- **Churn / escalation signals:** explicit ("I'll go elsewhere", refund/complaint language), and implicit (rising effort, repeat contacts, ghosting after a quote). These are the leading indicators a regulated-advisory firm most needs to catch early.

---

## 3. Qualitative QA Scorecards

A QA scorecard is the rubric a reviewer uses to grade an interaction against the firm's standards, spanning **soft skills** (tone, empathy, listening) and **hard checks** (accuracy, compliance, resolution) (MaestroQA; Calabrio; Balto). Two widely-cited organizing frameworks: the **4C Framework** — Communication, Customer Connection, Compliance & Security, Correct & Complete Content (MaestroQA/Zendesk); and pillar models splitting Soft Skills / Issue Resolution / Procedure. Scoring mechanics: yes/no checkboxes, anchored linear scales (1–5 or 1–10), and **weighted** categories, plus an **auto-fail / critical-error** section that zeroes the whole interaction on a non-negotiable breach (e.g. wrong regulatory advice, data-protection violation) (MaestroQA).

**Recommended agent-scoring rubric (1–5 anchored).** Each dimension scored 1–5; weights tuned to a regulated advisory; any "Auto-fail" trigger overrides the total to 0.

| # | Dimension | What it measures | 1 (fail) | 3 (meets) | 5 (excellent) | Weight |
|---|-----------|------------------|----------|-----------|---------------|--------|
| 1 | Greeting & Identification | Opens, identifies self/firm, confirms who the client is | No greeting; ambiguous identity | Polite open, names self | Warm, branded, confirms client + context | 5% |
| 2 | Comprehension | Grasps the real question behind the question | Misreads the request | Answers the literal ask | Surfaces underlying need, asks clarifying Q | 10% |
| 3 | Accuracy / Correctness | Regulatory/factual correctness of advice | Wrong info given **(Auto-fail)** | Correct, slightly incomplete | Correct, precise, sourced/caveated | 25% |
| 4 | Resolution / Completeness | Issue actually resolved or clear next step | Left unresolved, no owner | Resolved or routed | Resolved + confirms understanding + next step | 20% |
| 5 | Empathy & Tone | Acknowledges emotion, on-brand register | Cold/curt/dismissive | Neutral-polite | Genuinely empathetic, reassuring | 10% |
| 6 | Personalization | Tailors to client's case, no blind macro | Generic copy-paste | Light tailoring | Fully contextual to the case | 5% |
| 7 | Proactivity | Anticipates next obstacle / upsell-with-integrity | Reactive only | Answers what's asked | Flags deadline/risk/next service | 10% |
| 8 | Closing | Confirms resolution, invites follow-up | Abrupt / no close | Clean close | Confirms + sets expectation + warm sign-off | 5% |
| 9 | Compliance & Data Handling | Disclaimers, PII discipline, no off-channel leakage | Breach **(Auto-fail)** | Compliant | Compliant + proactively protective | 10% |

---

## 4. Conversation Analysis (CA) Applied to Service Chats

CA is the academic discipline that treats talk as *structured social action*; its constructs map cleanly onto chat QA (Authenticx; EduLearn; emcawiki):

- **Turn-taking:** how parties manage who "speaks" — in async chat, who holds the floor, batching, overlap, and silence (a 6-hour gap *means* something).
- **Adjacency pairs:** first-pair-part -> expected second-pair-part (question->answer, greeting->greeting, request->grant/deny). A *missing* or *dispreferred* second-pair-part (question left unanswered) is a measurable defect.
- **Repair:** how breakdowns get fixed — self-initiated self-repair (the agent clarifies), other-initiated (client says "I don't understand"). Frequency and *type* of repair is a quality signal: lots of client-initiated repair = unclear agent communication.
- **Openings & closings:** institutional service openings ("How can I help?") and ritualized closings; CA shows closings are *negotiated*, not unilateral — an agent who closes before the client's concern is fully addressed produces a "dispreferred" close.

CA gives the *vocabulary* and *unit of analysis* (the sequence, not the isolated message) that elevates a scorecard from gut-feel to defensible structure.

---

## 5. Sales / Lead Frameworks for Chat

Bali Zero's inbound WhatsApp is half service, half sales (lead -> quote -> close), so the framework must score *conversion behavior* too (secondnature.ai; Claap):

- **SPIN (Rackham):** Situation, Problem, Implication, Need-payoff questions — built for consultative, multi-touch, >30-day cycles; ideal for visa/company-setup advisory. Measure whether the agent *diagnoses* before *prescribing*.
- **BANT:** Budget, Authority, Need, Timeline — fast transactional qualification; score whether the agent established these four before investing effort.
- **Objection handling:** acknowledge -> clarify -> reframe -> confirm; track which objections recur (price, timeline, trust) and how agents resolve them.
- **Funnel / conversion-in-chat:** measure inquiry -> qualified -> quote-sent -> closed within the thread; per-agent conversion rate and quote-to-close lag.
- **Follow-up cadence:** did the agent follow up after a quote went quiet? Ghosted-lead recovery is a high-value, easily-audited behavior.

---

## 6. Qualitative Coding Methods (Corpus-Level)

To learn *what* clients ask and *where* agents fail across thousands of threads, code the corpus (Delvetool; Getthematic; thelevel.ai):

- **Thematic analysis:** assign codes to phrases, cluster into themes; works **deductive/top-down** (start from a predefined codebook: "KITAS query", "tax deadline", "pricing objection") or **inductive/bottom-up** (let themes emerge).
- **Grounded theory:** open coding -> axial coding (relate codes) -> selective coding (build a core narrative) — for discovering *why* a failure pattern exists, not just that it does.
- **Intent classification:** map each inbound to an intent taxonomy (price, document-request, status-check, complaint, new-lead) — enables routing analytics and per-intent FCR.
- **Topic modeling:** unsupervised clustering (LDA/embeddings) to surface latent topics and seasonal spikes (e.g. visa-rule change -> query surge).

A practical pipeline: build a deductive codebook from domain knowledge, validate inductively on a sample, then let an LLM apply it at scale — with human-validated inter-coder agreement on a held-out sample.

---

## 7. Tone / Brand-Voice & Regulatory-Accuracy QA

For regulated advisory (visa/tax/legal), **wrong information is a liability**, not a style nit. QA in regulated industries treats compliance as a *non-negotiable, often auto-fail* category — were required disclaimers given, was statutory info correct, was data handled per regulation (Zendesk/4C; Calabrio; wolf.financial). Two distinct axes:

1. **Brand-voice compliance:** does the agent sound like one firm — approved vocabulary, register, no taboo phrases? A brand-voice guide that *maps approved language to compliance requirements* reduces review cycles (wolf.financial). This is checkable semi-automatically against a lexicon.
2. **Regulatory accuracy:** the highest-stakes check. Every factual claim about a visa type, tax rate, deadline, or KBLI code must be verifiable against ground truth. Recommended: a **claim-extraction + verification** step — pull every factual assertion from the thread and check against an authoritative source; any unverifiable or wrong claim is a critical error. This is exactly where automation must *flag for human review*, not auto-pass.

---

## 8. Modern LLM-Assisted Conversation Analytics

LLM/auto-QA platforms now score **100% of interactions** against custom scorecards (greeting, empathy, policy mention, resolution), versus the 1–2% a human team samples — auto-transcription, automated sentiment, summarization, and agent scorecards feeding coaching dashboards (thelevel.ai; Lorikeet; Balto). This is transformative for coverage and for catching the rare critical error in a long tail of conversations.

**But the pitfalls are real and documented:**
- **Hallucinated scoring:** LLMs produce confident-but-unsupported judgments; using an LLM to self-evaluate compounds the risk. Agent-trace hallucinations arise from multi-turn, evolving context and *cannot* be caught by conventional NLG checks (MIRAGE-Bench, arXiv 2507.21017).
- **Self-preference bias:** evaluator LLMs favor outputs from the same model family, inflating scores — a structural gaming vulnerability (MIRAGE-Bench; JetBrains).
- **Gaming & sensitivity:** scores drift with prompt design, transcript length, and contextual embeddings; agents (and models) learn to satisfy the rubric's letter, not spirit (JetBrains; arXiv 2412.05520).
- **Mitigations:** treat the LLM judge as a *first-pass triage*, calibrate it against human labels (TPR/TNR), reserve high-stakes regulatory-accuracy and auto-fail decisions for human reviewers, and **never** rank or discipline agents on an unvalidated automated score alone.

---

## 9. WhatsApp-Specific Considerations

WhatsApp breaks several assumptions baked into call-center metrics (Gorgias; Salesforce; Intercom):

- **Asynchronous cadence:** "response time" != live-chat. A 30-minute reply is fine async, terrible in live chat. Measure FRT *and* NRT, normalize by business hours, and weight after-hours separately. Conversation "open/closed" boundaries are fuzzy — define a reopen window (e.g. 24h).
- **Voice notes:** in SE Asia/LATAM a large share of clients communicate by voice note; these must be **transcribed** before any text analytics, and transcription quality caps every downstream metric.
- **Media / documents / OCR:** clients send passport photos, akta, NPWP, contracts. Handling quality (did the agent correctly read/route the document?) is part of resolution — and a PII-handling compliance surface.
- **Group vs direct chats:** group threads change turn-taking and accountability (who answered?); attribute per-agent metrics carefully.
- **Multilingual informal register:** Bahasa Indonesia / Italian / English **code-switching** within one thread. Sentiment, intent, and tone models must be multilingual and robust to informal/slang register, or they mis-score.
- **No native CSAT survey:** WhatsApp has no built-in post-chat survey. Substitutes: a sent CSAT/1-tap template message, **sentiment-trajectory as a CSAT proxy**, NPS via periodic broadcast, or inferred satisfaction from resolution + repeat-contact + thank-you-language signals.

---

## Recommended Metric Set for an Async WhatsApp Consultancy (Checklist)

Operational (100% coverage, automated):
- [ ] First Response Time (business-hours-normalized) + after-hours FRT split out
- [ ] Next Response Time (median, to catch stalled threads)
- [ ] Resolution Time + open-thread backlog/unread count per agent
- [ ] First-Contact Resolution proxy (no reopen within 7 days)
- [ ] SLA adherence %, message volume, inbound/outbound ratio, escalation/handover rate

Outcome (sampled or proxied):
- [ ] Sentiment trajectory per thread (proxy for CSAT, 100% coverage)
- [ ] CSAT via sent 1-tap template (transactional); periodic NPS broadcast; CES after task-completion
- [ ] Repeat-contact rate + churn/escalation language flags

Qualitative (sampled, human-validated, LLM-assisted triage):
- [ ] 9-dimension 1–5 scorecard on a stratified sample per agent per week (Section 3)
- [ ] **Auto-fail audit at 100% coverage** for regulatory-accuracy + PII/data-handling (LLM flags -> human confirms)
- [ ] Brand-voice lexicon compliance scan
- [ ] Conversion funnel + follow-up-cadence per agent (sales threads)
- [ ] Quarterly corpus-level thematic/intent coding to update the codebook + spot systemic gaps

Guardrails:
- [ ] LLM judges calibrated vs human labels; never discipline on unvalidated auto-score
- [ ] Voice notes transcribed before scoring; multilingual models verified on ID/IT/EN code-switch

---

## Sources (inline-cited)

1. [MaestroQA — How to Build Your First QA Scorecard](https://www.maestroqa.com/blog/how-to-build-a-qa-scorecard) — 4C framework, dimensions, scoring scales, auto-fail.
2. [Zendesk — How to build a QA scorecard](https://www.zendesk.com/blog/quality-assurance/workforce-optimization/qa-scorecard/) — categories, critical errors, 4C.
3. [Calabrio — Call Center QA Scorecards](https://www.calabrio.com/blog/quality-assurance-qa-scorecard/) — soft vs hard skills, coaching tie-in.
4. [Balto — 20 Call Center QA Metrics](https://www.balto.ai/blog/call-center-quality-assurance-metrics/) — QA metric inventory.
5. [JustCall — Customer Service KPIs](https://justcall.io/blog/customer-service-metrics-kpis.html) — FRT/ART/FCR/SLA/occupancy formulas + benchmarks.
6. [Intercom — Customer Service Metrics](https://www.intercom.com/learning-center/customer-service-metrics) — metric definitions.
7. [SQM Group — FCR](https://www.sqmgroup.com/resources/library/blog/fcr-metric-operating-philosophy) — FCR as operating philosophy.
8. [Formbricks — Customer Effort Score](https://formbricks.com/blog/customer-effort-score) — CES formula, Likert, benchmarks.
9. [Plecto — CSAT vs NPS vs CES](https://www.plecto.com/blog/customer-service/csat-vs-nps-vs-ces/) — formulas, transactional vs relational.
10. [thelevel.ai — Conversation Analytics Software](https://thelevel.ai/blog/conversation-analytics-software/) — 100% coverage auto-QA, sentiment.
11. [Lorikeet — Best AI QA Tools for Support](https://www.lorikeetcx.ai/articles/best-ai-qa-tools-support) — auto-QA coverage framing.
12. [Authenticx — Types of Conversation Analysis](https://authenticx.com/page/types-of-conversation-analysis/) — CA constructs applied to CX.
13. [EduLearn — Turn-taking, repair, adjacency pairs in online interaction](https://edulearn.intelektual.org/index.php/EduLearn/article/view/21041) — academic CA.
14. [emcawiki — Adjacency pair](https://emcawiki.net/Adjacency_pair) — CA reference.
15. [SecondNature — MEDDPICC, SPIN, or BANT](https://secondnature.ai/meddpicc-spin-or-bant-the-right-sales-technique-for-your-organization/) — methodology vs technique.
16. [Claap — BANT vs SPIN](https://www.claap.io/blog/bant-vs-spin) — when each framework fits.
17. [Delvetool — Grounded Theory vs Thematic Analysis](https://delvetool.com/blog/grounded-theory-vs-thematic-analysis) — coding distinctions.
18. [Getthematic — Coding Qualitative Data](https://getthematic.com/insights/coding-qualitative-data) — codebook, deductive/inductive.
19. [MIRAGE-Bench (arXiv 2507.21017)](https://arxiv.org/pdf/2507.21017) — LLM-agent hallucination, self-preference bias.
20. [JetBrains/PyCharm — LLM Evaluation & AI Observability](https://blog.jetbrains.com/pycharm/2026/05/llm-evaluation-and-ai-observability-for-agent-monitoring/) — eval pitfalls, calibration.
21. [Gorgias — WhatsApp for Customer Service](https://www.gorgias.com/blog/whatsapp-for-customer-service) — async FRT/NRT, voice notes, media.
22. [Salesforce — WhatsApp for Customer Service](https://www.salesforce.com/service/contact-center/whatsapp-for-customer-service/) — best practices, multilingual.
23. [Wolf Financial — Brand Voice & Compliance](https://wolf.financial/blog/brand-voice-guide-financial-marketing-compliance) — regulated brand-voice/compliance mapping.
