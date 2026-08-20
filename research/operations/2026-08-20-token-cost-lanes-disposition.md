---
date: 2026-08-20
adversarial_review: kimi-k3
---

# Token-cost build lanes 1-2: both closed VERIFY-NOT-BUILD, with the numbers

> Disposition record for the first two build lanes of the 2026-08-19 near-free-tools panel
> (`research/operations/2026-08-19-near-free-tools-token-cost-panel.md`, §consolidated levers).
> Both lanes closed the same way: the mechanism the lane wanted to build ALREADY EXISTS, is
> armed, and fires in production — measured, not argued. Nothing was built, deliberately.

## Lane 1 — WA-bot call-avoidance (semantic cache + local intent tier): CLOSED, verdict in the bot corner

Full verdict shipped to the bot corner §1 (PR #4391, merged 2026-08-20 02:59Z,
`.agents/skills/bot/SKILL.md`, bullet "IMPLICIT PREFIX-CACHE: VERIFIED HEALTHY"). One-paragraph
summary, pointers only — do not re-derive from here, read the corner:

- The Gemini request shape is already cache-correct (static ~8.2k-token prefix, byte-identical
  retries, append-only contents); `system_instruction` participation in the implicit prefix match
  was settled BY CONSTRUCTION (hits of 8,166/8,167 tokens on calls whose contents were ~2.5k).
- July's 0% cache readings were the gateway ledger's blindness (#2845 recorded without
  extracting `cached_content_token_count`; #3914 cured it on 2026-08-09 17:47Z).
- Explicit caching and the semantic-cache lane: SKIPPED with numbers (background traffic 3-17
  calls/DAY ≈ $0.05/day vs a ~3.6-4.8 calls/HOUR break-even; semantic cache deferred to
  go-public — cache hits bypass the abstain gate, bot corner §2 truth #4).
- Side-finding for Zero (open): the live answering model has been `gemini-2.5-flash` since
  2026-08-10 — #3939 wired the pre-existing `PRIMARY_MODEL_NAME` Fly secret, silently undoing
  the #2611 promotion to 3.5-flash. Deliberate mechanism, un-ratified steady state.

## Lane 2 — "Docling-first document cascade" in intake: CLOSED, the cascade already exists and fires

The panel's lane premise was "try local text extraction before vision OCR" with metric
"qwen2.5vl page calls per 100 intake pages". Measured on 2026-08-20:

1. **The cascade is already built at the exact choke point.** All three intake sources
   (whatsapp/drive/zoho) pass through `backend/services/intake/preprocess.py::preprocess_blob()`,
   whose `TEXTLAYER_FASTPATH` (env `INTAKE_TEXTLAYER_FASTPATH`, default true; pypdfium2 text
   extraction, ≥100-char threshold) hands `classify.ocr_pages()` a text layer that makes it
   SKIP vision entirely for that page (`classify.py` logs `via="textlayer"`). DOCX/TXT/CSV have
   their own non-vision extractors.
2. **It is armed and firing in production** (Esiste≠Armato checked, not presumed): the intake
   worker is live on Pro (`python -m backend.services.intake.worker`), the queue is active
   (last enqueue 2026-08-20 11:41 WITA; 14-day status: 2,203 done / 3 pending), and the freshest
   classify output carries `via="textlayer"` with vision skipped.
3. **The 30-day page split** (10,689 pages, `intake_queue.stage_output->'classify'->
   'ocr_text_per_page'`, Pro local `nuzantara_dev`): `textlayer` 3,994 (37%, vision skipped) ·
   vision-answered `response` 4,861 (45%) · `fallback` 145 (1%) · `empty` 1,689 (16%).
   **`empty` is not "no call"** — read from `classify.py::ocr_pages` (origin/main): `via="empty"`
   survives only after vision was attempted TWICE (primary + deliberate same-model retry) and
   returned nothing usable. So vision-CALLED pages are 6,695 (63%) and vision calls ≈ 8,529
   (`empty`/`fallback` pages cost two each). By source: drive is textlayer-heavy (2,444 text vs
   2,355 vision-answered), whatsapp is vision-heavy (2,506 vs 1,550).
4. **What Docling would and would not change — token-cost frame only.** The metered cost of ALL
   of this is $0: every vision call is local qwen2.5vl on Pro (unmetered compute), and cloud
   vision fails closed (`cloud_vision_gate.cloud_vision_allowed()`, default
   `ocr_allow_cloud_vision=False`). Docling could displace qwen2.5vl calls on the panel's
   LITERAL call-count metric only by substituting its own bundled OCR
   (RapidOCR/EasyOCR/Tesseract) — the same local-$0 class, so no token-cost win, with unmeasured
   quality on Indonesian legal scans. The cheap-extraction headroom (skip vision when a text
   layer exists) is already captured by the fastpath. Left open, unmeasured: how many of drive's
   2,355 vision-answered pages are digital PDFs whose text layer pypdfium2 under-extracted
   (<100 chars) — the pages Docling's layout models could reclaim. **Headroom as a token-cost
   lane: ~zero. Headroom on the literal call-count metric: not established — and irrelevant to
   spend.**
5. **Docling's real slot is QUALITY, and that was already ruled — with one live trigger to
   watch.** The June research (`research/operations/doc-intake-unified/`, 2026-06-04;
   `2026-06-27-39k-drive-ocr-backlog-sovereign-pipeline.md`) had already scoped Docling as
   "Option C — forward investment, not required": structure-aware extraction (tables in
   akta/NIB) over pypdfium2's flat text. Re-open only with a MEASURED extraction-quality gap, as
   a quality lane — never as a token-cost lane. **The one open measurement this arc leaves
   behind: the `empty` 16% is an unclassified zero-extraction class** (1,689 pages/30d where two
   vision attempts produced nothing). If PII-safe sampling on Pro shows failed extractions
   rather than blank/separator pages, the re-open condition is already met; if mostly blanks,
   the cheap fix is a blank-page detector (saves ~3,400 wasted local calls/month — compute, not
   tokens). If Docling is ever adopted, it must not land in the shared backend requirements
   (the Fly image does not need its model weights; the intake worker runs on Pro).

## Remaining panel lanes — disposition

- Local hero-image lane (mflux/Draw Things), deterministic reel pipeline, Qwen3-Coder grunt
  lane, mlx-whisper, MCP/tool-context audit, approved-asset retrieval: NOT started in this arc;
  each needs its own GROUND. Ranked next by measured spend: none of them touches a metered
  seat — the metered burn was measured in lane 1 (probe batteries ≈ $13, background $0.05/day).
- Coordination note: the `/intake` corner was deliberately NOT updated in this arc — a sibling
  lane (`ops-intake-company-projection`, Fable final gate) was in flight on Pro at measurement
  time. The next intake session should fold §Lane 2 points 2-3 into the intake skill when that
  lane lands.

## Method notes (scars touched, honestly)

- **W97, mine, live**: the first 30-day aggregate was piped through `tail -12` and silently
  dropped its TOP row (`response` 4,861, the largest value, DESC-ordered). Caught because the
  by-source breakdown did not reconcile. The published split is the reconciled one.
- **W104**: Codex refuter seat returned usage-limit ERRORs on stdout with exit 0 (quota-dead
  until 2026-08-22); judged by the reply, cascaded to Kimi K3.
- Sibling discipline: live Fable gate + rclone intake copy observed on Pro; this arc stayed
  measurement-only on intake surfaces.
- PII: one sampled `stage_output` row contained a real person's CV text; used only for its
  structural fields, not transcribed into any artifact.

## Adversarial review

Lane 1 claims were refuted by Kimi K3 (kimi-code/k3) against a claims+evidence pack: 2 claims
tightened ("proven" → settled-by-construction with a new discriminating query; TTL/shape
attribution rewritten as "TTL/routing plus prefix fragmentation, not apportioned"), 1 claim
REFUTED and re-cured with new queries (the verifier "can never cache" was contradicted by its
own 2.5-flash 9.5% row — root-caused to self-correction re-verifications sharing the
query+context prefix). Codex gpt-5.6-sol was dispatched first and was quota-dead (declared,
not silent).

Lane 2's draft got its own Kimi K3 pass, which landed three hits, all applied above:
"the 45% are scans/photos with no text layer" was REFUTED as unmeasured for drive (rewritten as
an open measurement); "headroom ~zero" was OVERCLAIMED on the literal call-count metric (Docling
bundles its own OCR) and now stands on the token-cost frame alone; and the `empty` 16% class was
flagged as an undisclosed dependency of the closure — settled the same turn by reading
`classify.py::ocr_pages` on origin/main (`empty` = two vision attempts, nothing usable), which
corrected the vision-called share from 45% to 63% and turned `empty` into the note's one
declared open measurement.
