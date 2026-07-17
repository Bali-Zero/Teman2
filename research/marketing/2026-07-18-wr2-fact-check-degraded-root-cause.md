---
date: 2026-07-18
domain: marketing
client_case: false
adversarial_review: codex
sources:
  - scripts/wr2_fact_checker.py (verifiers; _extract_source_text:247; _find_law_citations:289; _aggregate_status:556 fail-closed cap; _process_one_draft source assembly:640-676; llm_enabled default:756)
  - scripts/wr2_fact_extractor.py (claim typing; prompt:141/158 semantic number/date, no digit required; passthrough:209-225 validates only the type enum)
  - scripts/wr2_grounding.py (grounding → brief_json.enrichment; duplicate _find_law_citations:83; ground_enrichment:239 graceful-degrade paths; KNOWN GAP:29)
  - .worktrees/wr2-factcheck-wordnumbers/scripts/wr2_fact_checker.py:360 (LIVE SIBLING — word-number normalization prototype, branch agent/air-m5/wr2/factcheck-wordnumbers)
  - infra/launchagents/com.balizero.wr2.fact-checker.plist + live Pro plist (no WR2_FACT_CHECKER_LLM)
  - prod war_room_drafts via scripts/pg.sh (nuzantara_readonly, Fly proxy): queries embedded in Appendix
---

# WR2 "fact_check_status degraded pipeline-wide" — root cause

**Verdict: `degraded` is not a checker bug — it is the fail-closed fact-checker correctly
refusing to bless claims it cannot corroborate. But the deeper cause is sharper than
"grounding is empty": the checker drinks from the same well as the composer. `brief_json`
is BOTH the corpus the draft was composed from AND the "external" source the checker
verifies against. There is no witness independent of the author.** This reframes the fix:
the naive "make grounding inject citations" is a closed citation-echo (inject a rail into
the brief → the composer writes it into the slides → the checker matches it → "verified"
with zero independent truth). The honest cures are (1) verify against a source the composer
did NOT see, and (2) label each verdict with its provenance instead of collapsing everything
to `verified`/`degraded`.

> This report was CADE'd by an adversarial Codex pass and rewritten. The original draft made
> two errors it now corrects: it called any check-against-the-article "necessarily dishonest"
> (a false dilemma — fidelity-to-source ≠ rubber-stamp-against-own-slides), and its own
> recommended fix ("inject citations into the brief") had the exact echo flaw it accused
> other fixes of. See `## Adversarial review`.

## The evidence (prod, `nuzantara_readonly` via Fly proxy, 2026-07-18)

| Fact | Value |
|---|---|
| Drafts with `fact_check_json` | 86 (79 `degraded`, 7 `pass`, 0 `fail`) |
| Unverifiable claims across degraded drafts | 438 (0 contradicted) |
| Degraded drafts with ANY law citation in `brief_json` | 22 / 79 (28%) |
| Degraded drafts with EMPTY `brief_json.enrichment` (`{}`/null) | 58 / 79 (73%) |
| LLM cross-check (Pass 2) armed in prod | **NO** (`WR2_FACT_CHECKER_LLM` unset → false) |

Unverifiable-claim note breakdown (all 438), with **honest** attribution:

| Note | n | Nature |
|---|---|---|
| `law claim has no matchable citation` | 186 | claim carries no citation token (183) + 3 STALE pre-2026-06-04-regex verdicts |
| `no extractable number in claim` | 105 | number expressed as a word ("Four", "double") — representation mismatch |
| `no extractable date in claim` | 32 | date expressed as a word — representation mismatch |
| `law citation X not found in external source` | ~38 | valid cite, absent from the (composer-shared) source |
| `quote not found verbatim in research_json` | 29 | quote not verbatim in source |
| `token overlap N/M <60%` | ~48 | genuine low corroboration |

Running the checker's **real** regexes against every claim text: 0 of the 105 word-number
and 0 of the 32 word-date claims contain a digit a digit-only regex could catch; only 3 of
186 law-no-citation would match the current regex (stale verdicts). So ~137 claims fail on a
**words-vs-digits representation mismatch** and ~183 on a genuinely-absent citation.

## The decisive query (why the headline can't move honestly by a checker/extractor tweak)

Of the 79 degraded drafts: **52 (66%)** carry ≥1 unverifiable that survives ANY
representation fix (cite-not-found / quote-not-verbatim / token-overlap<60%) — they cannot
reach `pass` without a source the checker doesn't currently have. **27 (34%)** are degraded
only on representation-mismatch claims; these *could* flip — but under today's code they
flip by matching against `source_text`, which **includes the draft's own slides**
(`_verify_claim` is handed slide-inclusive `source_text` at wr2_fact_checker.py:662; Pass 2's
`llm_source` is slide-inclusive too at :676). Flipping them that way is a rubber-stamp.

## Root cause — the layers (CADE-sharpened)

1. **No independent witness (the root).** `brief_json` is the corpus the draft is composed
   from (topic-selector → draft-generator) AND the source the checker verifies against
   (`_extract_source_text` threads `brief_json` into both `source_text` and the slides-
   excluded `external_text`). The checker can therefore only ever measure *fidelity to the
   author's own inputs*, never independent corroboration. `research_json` — the field the
   P-5 hardening (2026-06-04) designed the external leg around — is never populated in prod.
2. **Slide-inclusive verification (a live rubber-stamp hole).** Pass 1 hands number/date/
   quote/other verifiers `source_text` **with slides included** (:662); Pass 2 does the same
   (:676). Only law claims are checked against the slide-excluded `external_text` (via
   `source_laws`). So any non-law claim whose token appears in the draft's OWN slides
   self-verifies. It doesn't bite today only because most such claims have no digit to match
   at all — but it is a latent false-`verified` path.
3. **Grounding is wired but its output would echo, not corroborate.** `wr2_grounding.py`
   already injects verbatim citations into `brief_json.enrichment` — but into the SAME brief
   the composer consumes. Injecting more citations there would let the composer copy them
   into slides and the checker "match" them: a closed loop, not independent truth. (Also:
   grounding and checker each carry a *duplicate* `_find_law_citations` — :83 returns a list,
   :289 returns a set — so they can silently drift, scar #9.)
4. **Config amplifier.** LLM Pass 2 is OFF in prod, and cannot simply be armed as-is because
   its source is slide-inclusive (would rubber-stamp).

## Recommendation

**The honest fix is not "reduce degraded" — it is "make the fact-check measure independent
truth and say which kind of truth it measured."** Concretely, in priority order:

1. **Verify against a source the composer did not see** (the real cure, GO-gated backend
   follow-up): at CHECK time, re-query RAG/oracle keyed on each claim, rather than reusing
   the brief the composer already consumed. A match there is genuine corroboration; a match
   in the shared brief is an echo. Touches the RAG data plane (L2/L3).
2. **Verdict provenance labels** (honest, checker-side, cheap): replace the binary
   `verified`/`unverifiable`→`degraded` collapse with `independently_corroborated` /
   `supported_by_source_article` / `source_absent` / `claim_unparseable`. Then `degraded`
   becomes a *triageable* signal (58 source_absent vs a handful of actionable) instead of a
   pipeline-wide constant. This ADDS no verification power but stops the false dilemma of
   "loosen or stay dark".
3. **Verify against `external_text` (slides excluded) in BOTH passes** (honest, checker-side,
   cheap): closes the slide-inclusive rubber-stamp hole (:662, :676). Expect `degraded` to go
   *up*, correctly.
4. **Symmetric word/number normalization** for the ~137 representation-mismatch claims —
   normalize four→4 on claim AND on the source, yielding real `verified`/`contradicted`.
   **A live sibling is already shipping exactly this** in `.worktrees/wr2-factcheck-wordnumbers`
   (branch `agent/air-m5/wr2/factcheck-wordnumbers`, commit `3516d31039`, ~21 min before this
   capture). **⚠️ Honesty prerequisite — verified live in their current commit:** their
   `_normalize_number_words` is applied to the `source_text` handed to
   `_verify_number_or_date_claim`, and they did NOT change the `_verify_claim` call at :662 —
   so it still normalizes the **slide-inclusive** source. A word-number that also appears in
   the draft's own slides therefore self-verifies. As committed, the fix "kills false
   degraded" partly by matching against the draft itself. It is honest ONLY if step 3 lands
   first (verify against slides-excluded `external_text`). Their PR needs this exact check at
   its adversarial gate (blood-bought rule #7). Coordinate, do not duplicate (sibling-race #5).

**Anti-recommendations (banked scar):** do NOT (a) arm LLM Pass 2 unchanged, (b) reroute
mis-typed claims to token-overlap against slides, or (c) inject more citations into the
shared `brief_json` and call the resulting overlap a pass. All three reduce `degraded`
without adding one bit of independent truth — the P-5 rubber-stamp wound at a new address.

## Meta-pattern (the malattia-delle-malattie)

**"No witness independent of the author."** The fact-checker verifies the draft against the
same corpus the draft was written from, so the strongest verdict it can honestly earn is
"faithful to my own source", never "true". Every proposed shortcut — self-slides overlap,
LLM-against-slides, citation-injection into the shared brief — is a variant of the author
grading their own homework. The cure is not a better matcher; it is a *second, independent
reader* (a check-time query the composer never touched) plus honesty about which reader
signed off. This is superscar #2 "Esiste ≠ Armato" wearing a lab coat: the verification
organ exists and runs, but it has no independent evidence to verify against, so its green is
worth exactly what its source is worth — and its source is the author.

## Appendix — reproducible queries (run this turn via `scripts/pg.sh`)

```sql
-- status distribution
SELECT coalesce(fact_check_status,'(null)'), count(*) FROM war_room_drafts
 WHERE fact_check_json IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;   -- 79 degraded, 7 pass

-- all unverifiable claims + notes (438 rows; feeds the note table)
SELECT c->>'type', c->>'note', c->>'claim'
 FROM war_room_drafts d,
      jsonb_array_elements(coalesce(d.fact_check_json->'claims','[]'::jsonb)) c
 WHERE d.fact_check_status='degraded' AND c->>'verdict'='unverifiable';

-- citation presence + empty enrichment among degraded drafts
SELECT count(*) FILTER (WHERE brief_json::text ~ '(PP|PMK|UU|Perpres|Permen[a-z]*)[ -][0-9]'),
       count(*) FILTER (WHERE (brief_json->'enrichment') IS NULL OR brief_json->'enrichment'='{}'::jsonb)
 FROM war_room_drafts WHERE fact_check_status='degraded';        -- 22 with-cite, 58 empty-enrichment

-- 52 grounding-starved vs 27 representation-only (the decisive split)
WITH per_claim AS (
  SELECT d.id, CASE WHEN c->>'note' IN (
      'law claim has no matchable citation','no extractable number in claim',
      'no extractable date in claim') THEN 'repr' ELSE 'starvation' END AS bucket
  FROM war_room_drafts d,
       jsonb_array_elements(coalesce(d.fact_check_json->'claims','[]'::jsonb)) c
  WHERE d.fact_check_status='degraded' AND c->>'verdict' IN ('unverifiable','contradicted'))
SELECT count(DISTINCT id) FILTER (WHERE bucket='starvation'),
       count(DISTINCT id) FILTER (WHERE id NOT IN (SELECT id FROM per_claim WHERE bucket='starvation'))
 FROM per_claim;                                                 -- 52 starvation, 27 repr-only
```

## Adversarial review

Codex (`gpt-5.6-sol`, high effort, read-only) was asked to REFUTE the first draft. **Verdict:
CADE.** Every objection was independently re-verified on disk (W65 — the refuter also
hallucinates); all held. Resolutions folded into the rewrite above:

- **Strongest objection (CADE) — my own recommendation was a citation echo.** Injecting
  citations into `brief_json` feeds the composer and the checker from the same source; the
  resulting overlap reduces `degraded` without adding independent truth. **Conceded** — the
  recommendation is now "verify against a source the composer never saw" + provenance labels,
  and citation-injection-into-the-shared-brief is listed as an anti-recommendation.
- **False dilemma (obj 6).** I called any check-against-the-article dishonest. Fidelity-to-
  source ≠ rubber-stamp-against-own-slides. **Conceded** — provenance labels
  (`supported_by_source_article` vs `independently_corroborated`) replace the binary.
- **Slide-inclusive Pass 1 (obj 4).** Verified: `_verify_claim` gets slide-inclusive
  `source_text` (:662), and Pass 2 `llm_source` too (:676). The self-reference is not only
  Pass 2. **Folded in** as root-cause layer 2 + honest fix 3.
- **"323 mis-typing" over-classified (obj 5).** The extractor's contract asks for semantic
  numbers/dates without requiring digits; the checker's digit-only regex is the brittle side.
  **Conceded** — reframed as "representation mismatch", and the sibling word-number prototype
  is credited (obj also surfaced that live sibling — respected under #5).
- **Empty-enrichment ≠ proven backend failure (obj 7).** `ground_enrichment` also returns the
  brief unchanged on feature-disabled / already-cited / handled-error. **Conceded** —
  softened to "consistent with, most likely; per-draft telemetry needed to prove cause".
- **Reference errors + duplicate `_find_law_citations`.** `_extract_source_text` is :247 not
  :128; grounding/checker carry duplicate implementations that can drift. **Fixed** in
  sources + root-cause layer 3.
- **Prod numbers not independently reproducible (Codex couldn't reach Pro).** They were run
  this turn via the Fly proxy (`scripts/pg.sh`), not Pro. **Fixed** — the exact SQL is in the
  Appendix so any session can reproduce 79/438/52.
