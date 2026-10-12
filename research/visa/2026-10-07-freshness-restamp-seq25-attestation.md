---
date: 2026-10-07
domain: visa
client_case: none — production incident (second occurrence) and source-ledger attestation
sources:
  - research/visa/2026-10-07-freshness-restamp-seq25/ (read ledger: receipts, judgements, disposition, saved visible text)
  - apps/backend-rag/backend/scripts/visa_engine/portal_read_receipt.py
  - apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq25.py
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-025.{source,signed}.json
  - research/visa/2026-08-30-freshness-restamp-seq17-attestation.md (the rule this fold implements)
  - production catalog, read-only role (visa_ruleset_activations / visa_rule_packs), via scripts/pg.sh
adversarial_review: codex
---

# seq-25 re-stamp — the ledger IS the attestation this time

## What happened

The 18 `OFFICIAL_PORTAL` records of the active pack (seq-23) carried
`verified_at = 2026-08-30T13:18:00Z` under the 32-day window seq-18 set. They went
STALE at **2026-10-01T13:18:00Z**. From the next evaluation every Visa Oracle product
answered `HUMAN_REVIEW_REQUIRED` with an empty candidate list — the public page says
"This needs a human, not an algorithm", the reason code is `DECISIVE_SOURCE_STALE`.
Six days, every product, no error anywhere. Second occurrence of the 2026-08-30 incident.

Why nobody re-stamped: the weekly re-attestation lane is still a human mandate, not an
organ; seq-18's docstring said so and it is still true. Why nobody was told: the
sentinel on Pro fired APPROACHING on 2026-09-29 and STALE on 2026-10-01, but the
Telegram bot token was 401-dead from 2026-09-22 to 2026-10-06, so neither first send
reached anyone; once the token came back the key `visa-freshness:stale:23` was already
on the dedup ladder (streak 4, 168h mute) and every later run logged `deduped`.

## What seq-17 asked for, and what seq-25 does about it

The 2026-08-30 attestation named its own defect — `verified_at` was a constant in a
Python file, and nothing on disk proved anyone had looked — and wrote the rule: *write
the ledger during the reading; take the earliest reader's instant.*

seq-25 does not type a stamp. It derives one:

| artifact | written by | when | what it proves |
| --- | --- | --- | --- |
| `*-receipts.jsonl` (21 lines) | `portal_read_receipt.py` | at the instant of each request | URL, HTTP status, `fetched_at`, key phrase found, visible-text fingerprint, path of the saved text |
| `text/<id>.txt` (18 files) | same tool | same instant | the visible text that was actually served (scripts, styles, CSRF token stripped) |
| `*-judgements.jsonl` (18 lines) | three readers (Sonnet 5, parallel) + two orchestrator spot-checks (E31B, VoA list) | after reading the saved text | a verbatim `checked_sentence`, what the page states, what the pack assumes, a verdict |
| `disposition.json` | the orchestrator | before the fold | every `changed` verdict accepted by id with a reason |

The fold refuses unless every portal record has a 200 with the key phrase found, a
non-`unsure` judgement, a dispositioned `changed` if any, and a quote that is a
substring of the saved text. `verified_at` is then the earliest successful
`fetched_at` in the ledger: **2026-10-07T13:32:18Z**. The next boundary under the
32-day window is 2026-11-08T13:32:18Z.

## What the readers found

- 18/18 pages HTTP 200, final URL = canonical URL, key phrase present.
- D1, D2, D12, E30A, E30B, E31A: page and pack agree (stay, sponsor, purpose).
- E31B, E31C, E31D, E31E, E31F, E31G, E31H, E31J: the page offers a 1-year OR 2-year
  ITAS (2-year PNBP Rp 8.500.000); the pack models the 1-year option only
  (`FIXED_DAYS 365/365`). The pack has modelled 1 year only since at least seq-17 (30 August), so the
  rules' assumption is still supported today; whether the 2-year option was already on
  the page in August is NOT provable (no earlier snapshot) — a product modelling gap,
  dispositioned by id and tracked in `PENDING-ARMS.md`, not a stamp blocker.
- Calling Visa list: 6 countries (Afganistan, Israel, Korea Utara, Liberia, Nigeria,
  Somalia). VoA list: 97 lines. Press release 2024-04-24 and the Alih Status ITK→ITAS
  service page: unchanged in substance.

## Adversarial review

Two seats, read-only on the staged patch and the ledger (2026-10-07, 13:54Z–14:04Z;
`evidence/2026-10/agent-air-m5-backend-rag-visa-freshness-restamp-e1af826a/council-journal.jsonl`).

**Codex GPT-5.6 (red-team): BLOCK, 8 findings, 3 cured on this head, none surviving as a
blocker.** (1) BLOCK — only the earliest `fetched_at` was validated: one page's receipts moved
to 2099 still produced seq-25. Cured: every successful receipt is validated (URL, not in the
future, after the previous stamp), guilt test. (2) MEDIUM — a receipt for a foreign URL and a
judgement older than its fetch were accepted. Cured by the same gates, guilt tests. (3) MEDIUM
— "not page drift" was unproven without an August snapshot. Cured by rewording: the 1-year
assumption is still supported; the August state is not provable. (4)–(8) re-derived PASS by
the refuter: the other gates refuse every mutation, fingerprint tie 18/18, rules/products/
`content_sha256` identical, exactly 18 records moved, both signatures verify, chain equals
the signed seq-24, census 39 passed, observer executable, no secret or PII.

**Gemini 3.1 Pro (constructive): GO-WITH-CONDITIONS, 7 findings, 1 cured, 2 surviving as
notes.** HIGH 1 — saved text not tied to the receipt's fingerprint: cured
(`_saved_text_matches_a_receipt`, guilt test). Surviving: MEDIUM 2 — one text file per record
is overwritten by a later fetch (mitigated by the fingerprint tie; per-fetch suffix next
time); HIGH 7 — the next re-stamp must be a scheduled organ, not a session act (PENDING-ARMS).
MEDIUM 3 / LOW 4–6 accepted as design (lane identifier in `verified_by`, readers read the
saved text, global-earliest instant, disposition tracked).

## Two residual risks, still named

**`content_sha256` was deliberately not moved** — same reasoning as seq-13/seq-17: it
is a quotation fingerprint, and the pages embed a per-request CSRF token, so a fetch
hash can never match. The receipts now carry a *visible-text* fingerprint per read, so
the NEXT re-stamp can compare text-to-text; this one has nothing to compare against.

**The lane is still not an organ.** This fold makes a re-stamp auditable and
mechanical (tool → readers → fold → sign → activate), but nothing schedules it. Until
it is scheduled, the sentinel's alert is the only guard, and a muted alert is the
failure mode that just happened twice.
