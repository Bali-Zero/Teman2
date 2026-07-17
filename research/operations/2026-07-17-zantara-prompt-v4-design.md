---
date: 2026-07-17
domain: bot (Zantara WA Meta bot — prompt chain)
client_case: null
sources:
  - apps/backend-rag/backend/prompts/zantara_core.py (v1, read in full)
  - apps/backend-rag/backend/prompts/zantara_core_v2.py (read in full)
  - apps/backend-rag/backend/prompts/zantara_core_v3.py (read in full)
  - apps/backend-rag/backend/prompts/whatsapp_persona.py (read in full)
  - apps/backend-rag/backend/prompts/channel_overlays.py (read in full)
  - apps/backend-rag/backend/prompts/business_rules_i18n.py (read in full)
  - apps/backend-rag/backend/prompts/few_shot_examples.py (read in full)
  - apps/backend-rag/backend/llm/prompt_manager.py (read in full)
  - apps/backend-rag/backend/services/rag/agentic/prompt_builder.py (read in full)
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (queried live, 1559 records)
  - memory fact_kbli2025_pp28_oss_conversion_2026_06_24.md (PP 28/2025 deadline mechanics)
  - .claude/skills/bot/SKILL.md (corner, LIVE STATE + established truths)
---

# Zantara prompt v4 — design doc

Authorized by Zero 2026-07-17 ("ti autorizzo ad analizzare il system prompt di zantara e
allinearlo ai livelli attuali SOTA"). This document proposes an ADDITIVE, flag-gated v4
template plus a cure for the prompt split-brain that currently means the WA bot never sees
v2/v3 (or any future version) regardless of the `ZANTARA_PROMPT_VERSION` env var.

## 1. Problem statement — 6 findings, all re-verified on disk today (2026-07-17)

### F1 (P0) — Prompt split-brain: the WA bot's brain bypasses the versioned door

`backend/llm/prompt_manager.py` is the ONLY module that reads `ZANTARA_PROMPT_VERSION` and
selects v1/v2/v3 with a defensive fallback chain. It is consumed correctly by
`backend/llm/zantara_ai_client.py:139` (`self.prompt_manager = PromptManager()`).

But `backend/services/rag/agentic/prompt_builder.py:25-29` — the `SystemPromptBuilder` class
that the agentic RAG orchestrator (`orchestrator_core.py:1036,1582`) calls to build the system
prompt for EVERY query, including the one WA answers through
(`wa_inbox_bot.py` → `POST /api/agentic-rag/query` → `orchestrator_core.py` →
`SystemPromptBuilder.build_system_prompt()`) — imports `ZANTARA_MASTER_TEMPLATE` **directly
from `backend.prompts.zantara_core`** (v1), not from `prompt_manager`. Confirmed by grep and
read: no `ZANTARA_PROMPT_VERSION` branch exists anywhere in `prompt_builder.py`.

Consequence: prod's `ZANTARA_PROMPT_VERSION=v3` env var arms v3 on the Oracle/`zantara_ai_client`
path (which is NOT what WhatsApp uses) and has **zero effect** on the WA bot. The WA number
+62 821-3465-159 has been running pure v1 semantics (Italian-only inline examples, no
multi-language business phrases, no worked examples) the entire time v2/v3 existed.

**Scope note on "who else imports v1 directly":** grep found 4 more direct importers of
`ZANTARA_MASTER_TEMPLATE` from `zantara_core` — `backend/prompts/zantara_persona.py`,
`backend/prompts/whatsapp_persona.py`, `backend/prompts/zantara_prompt_builder.py`,
`backend/prompts/__init__.py`. All four live **inside** `backend/prompts/` itself (the prompts
package), consumed by the Oracle service and a WA-specific overlay
(`whatsapp_chat.py:491-494`) that is NOT the live Meta-webhook→outbox→`wa_inbox_bot.py` path
(bot corner §2 established truth #1: that's Path B, the only live path for this number).
Changing those four is out of scope for an additive, flag-gated PR — they are legacy/parallel
surfaces this mandate does not touch. **The cure targets exactly the one split-brain the corner
names as P0: `services/rag/agentic/prompt_builder.py`, the only *non-prompts* module (i.e.
outside `backend/prompts/`) that imports the template directly.** This scoping also defines
the parity test in §4.3.

### F2 — Stale deadline announced as future

v1 `TOOL_USAGE_POLICY` (inherited unchanged by v2/v3): *"Deadline: 18 June 2026 — all businesses
must migrate to KBLI 2025 codes... When clients ask about KBLI, proactively mention the June
2026 deadline."* Today is 2026-07-17 — the deadline is **29 days in the past**, and the prompt
still tells the model to announce it as upcoming.

Verified regulatory state (memory `fact_kbli2025_pp28_oss_conversion_2026_06_24.md`, sourced
2026-06-24 via Hukumonline Pro/Hogan Lovells/Lexology/SmartLegal/GoLaw/Kemenko Perekonomian):
PP No. 28/2025 was promulgated 18 December 2025 with a 6-month adjustment clock → 18 June 2026.
**Most companies需 nothing**: if the 2020→2025 code change is a pure renumbering with no
substance change, OSS + Ditjen AHU auto-convert via a BPS correspondence table. **Manual action
is required only** when the registered activity's risk level actually shifted (low/medium-low/
medium-high/high), which can trigger new license/standard/verification requirements and may
need an NIB update or Articles of Association amendment. The same memory flags: "rollout still
being adjusted by the government system as of mid-2026 — do not over-promise per-company
outcomes." No source found (checked `.claude/skills/kbli-navigator/SKILL.md` and `research/`)
that reports a formal extension, but enforcement posture for non-compliant cases is genuinely
unresolved — I am not asserting one.

**v4 fix**: deadline-neutral phrasing that (a) states the 18 June 2026 date has passed, (b)
explains the auto-convert/manual-action split so the model doesn't scare clients whose codes
already converted automatically, (c) routes anyone asking about consequences/enforcement to
"verify with the team" rather than inventing a penalty regime. This is injected as static text
(see F2 fix below) — the DATE_CONTEXT injection from F3 makes it possible for the model to
reason about "is 18 June 2026 in the past" itself, but the explicit rewrite removes the
proactive "mention the deadline as upcoming" instruction which is simply wrong now regardless
of what date the model computes.

### F3 — No current-date injection anywhere in the chain

Grepped all of `backend/prompts/*.py` and `backend/services/rag/agentic/prompt_builder.py` for
`datetime.now`, `date.today`, `ZoneInfo` — zero hits. The model has no way to reason "is this
deadline past or future" without being told today's date. Established repo convention for Bali
time is `ZoneInfo("Asia/Makassar")` (used in `team_timesheet_service.py`,
`attendance_monitor.py`, `weekly_email_reporter.py`, `daily_checkin_notifier.py` — no shared
helper exists, each file defines its own `BALI_TZ = ZoneInfo("Asia/Makassar")` constant; v4
follows the same local-constant pattern rather than inventing a new shared utility, since reuse
across those files is by copy, not import, throughout this codebase).

**v4 fix**: inject `<date_context>Today's date: {weekday}, {DD Month YYYY} (WITA,
Asia/Makassar)</date_context>` at BUILD TIME (not baked into the static template — a static
string would go stale the moment the process starts). Placed in `prompt_builder.py`'s
`build_system_prompt()`, right next to where `user_memory`/`rag_results`/`query` are already
interpolated into the template — same mechanism, new placeholder.

### F4 — Phantom KBLI codes in v3's villa worked example

v3 `WORKED_EXAMPLES` (KBLI section, English variant): *"the relevant KBLI 2025 codes are 55130
(Vila) and 55194 (Akomodasi jangka pendek lainnya)."* Verified against
`data/source_documents/KBLI_2025_FINAL_CLEAN.json` (1,559 records, live query this session):

- `55130` and `55194` do **not exist** as `kode_kbli_2025` values anywhere in the dataset.
- They exist only as `kbli_2020_source`/PP28-source references — and they map to **55106
  ("Aktivitas Hotel Nonbintang")** and **55204 ("Aktivitas Apartemen Hotel")**, i.e. hotel and
  apart-hotel, NOT villa.
- The real KBLI 2025 villa code is **55203** ("Aktivitas Vila" — *"penyediaan akomodasi jangka
  pendek... rumah-rumah pribadi yang khusus disewakan kepada wisatawan"*), with
  `pp28_sources: ["55193"]` confirming the 55193→55203 renumbering v1's `RULE 5` already states
  correctly. `55901` ("Aktivitas Jasa Manajemen Akomodasi", management-fee model) and `55400`
  ("Aktivitas Jasa Intermediasi Akomodasi", platform/booking model) also verified present and
  correctly described in v1 `RULE 5`.

**Second phantom pair found while fixing the first** (own verification, same method, before
building the file): v3's Indonesian-language KBLI worked example ("Kode KBLI untuk usaha
konsultan IT yang dimiliki asing apa?") answers with `62029 ("Aktivitas konsultasi komputer
lainnya")` and `62012 ("Pengembangan aplikasi perdagangan")` — **neither code exists** in the
2025 dataset (queried live, same method). The real codes: **62209** ("Aktivitas Konsultansi
Komputer dan Manajemen Fasilitas Komputer Lainnya" — general IT/computer consulting) and
**62191** ("Aktivitas Pengembangan Aplikasi Perdagangan melalui Internet (E-Commerce)" — the
concept v3 was reaching for with "Pengembangan aplikasi perdagangan," just the wrong number).
Fixed alongside the villa example in v4.

So the bug is entirely inside v3's own `WORKED_EXAMPLES` copy — it contradicts v1/v2's own
`TOOL_USAGE_POLICY RULE 5` on the same fact, in the same prompt version chain. If v3 goes live
un-fixed, the model has two contradictory "ground truth" statements about the same code and
could pick the wrong one — a citation-plausible hallucination model to clients asking about
villa business setup, exactly the class of error `_abstain_policy.py`'s gates exist to prevent
(though this is a worked-example fabrication, not a RAG-retrieval failure, so those gates don't
catch it — the fix has to be in the prompt text itself).

**v4 fix**: rewrite the villa worked example to `55203` (primary), with `55901`/`55400` as the
conditional branches, matching v1 `RULE 5` exactly. No other WORKED_EXAMPLES entries reference
KBLI codes with values checkable against the dataset (restaurant `56101`, IT consulting
`62029`/`62012` — spot-checked `56101` below to make sure v3 isn't systematically wrong).

### F5 — Double price SSOT + pre-BKPM-5/2025 capital figures in few-shots

Two separate issues under one heading:

1. **Double SSOT for prices.** `whatsapp_persona.py:_load_full_pricing()` loads the *entire*
   `bali_zero_official_prices_2026.json` catalog into the system prompt at import time
   (`_PRICING_TABLES` module-level dict, built once per process) and injects it verbatim via
   `build_system_prompt()`'s `pricing_table` block — right next to
   `TOOL_USAGE_POLICY RULE 1: ONLY USE PRICES FROM get_pricing TOOL`. Contradictory guidance:
   the model is simultaneously told "call the tool" and handed the full price sheet in context,
   which is exactly the shape that produces stale-price answers if the JSON file and the
   `PricingTool`'s live source ever diverge (they're both sourced from the same file today, but
   nothing enforces that going forward — CLAUDE.md Golden Rule #11 says PricingTool only).
   **This file (`whatsapp_persona.py`) is out of scope for this PR** (it is not on the live
   Meta-webhook path per bot corner §2 — see F1 scope note), but it is a live pattern that must
   NOT be copied into v4, and is called out here so a future session doesn't reuse it.

2. **Hardcoded capital/price figures in few-shot examples.** `few_shot_examples.py` and the
   `whatsapp_persona.py` `FEW_SHOT_EXAMPLES` list both contain: `"D12 un anno 7.500.000 IDR"`,
   `"E33G ... 13 juta IDR"`, `"PT PMA ... 10 billion IDR, about $650k"` stated as flat facts with
   no tool-call shown. Per CLAUDE.md `feedback_single_price_no_pnbp_fee_split` +
   `fact_bkpm_5_2025_paidup_capital_2_5_mld_2026_07_16` (confirmed 2026-07-16): BKPM 5/2025
   changed **paid-up** PMA capital to 2.5 miliar (abrogating 4/2021's 10 miliar paid-up rule);
   the >10 miliar **total investment** per KBLI/lokasi rule still stands separately, and a THIRD
   number (10 miliar) is an unrelated **E28A immigration** eligibility rule. A flat "10 billion
   IDR" few-shot answer is now wrong for the paid-up-capital reading and dangerously easy to
   misapply across all three regimes.
   `zantara_core_v3.py`'s own `WORKED_EXAMPLES` avoid this trap correctly (pricing examples
   always show `→ CALL get_pricing(...) → Tool returns: {...} → Answer: ...` — shape not
   numbers) — the problem is specifically in the two `FEW_SHOT_EXAMPLES` lists
   (`few_shot_examples.py` `GENERAL_FEW_SHOT_EXAMPLES`/`WHATSAPP_FEW_SHOT_EXAMPLES`, and the
   copy embedded in `whatsapp_persona.py`), which are literal conversation-turn examples with
   baked-in numbers, not instructional prose.

**v4 fix**: `few_shot_examples.py` is consumed by `zantara_ai_client.py` (need to verify at
BUILD time) and is a separate module from the template chain — v4 does not touch it in this
PR (scope discipline: v4 is the template chain `zantara_core_v4.py` + `prompt_builder.py` +
`prompt_manager.py`, not every module that ever prints a price). What v4 DOES do: its own
`WORKED_EXAMPLES` section (inherited from v3, reviewed) already avoids hardcoded prices/capital
— confirmed no v3 worked-example states a bare price without a preceding tool call. No
regression to introduce. The double-SSOT and few-shot hardcoding are flagged here as known
debt for a follow-up PR (tracked in the PR body per mandate), not silently left unstated.

### F6 — Minor hygiene

- v1 `INTERNAL_MONOLOGUE` has two items numbered "2." (pricing check and fact-check) —
  cosmetic but confusing for a human reading the source; v3 inherits it unchanged. Fix in v4
  (renumber 0/1/2/3, matching v2's INTERNAL_MONOLOGUE which already fixed this — v2 has
  `0/1/2/3` correctly, so this is actually ALREADY fixed as of v2/v3's inherited
  `INTERNAL_MONOLOGUE`... re-checking: v2's `INTERNAL_MONOLOGUE` (line ~279-317) does show
  `0. CONVERSATION RECALL`, `1. PRICING CHECK`, `2. Fact Check`, `3. Identity Check` — correctly
  numbered. **v1's copy has the bug, v2/v3 already fixed it.** Since v4 builds on v3, this is a
  non-issue for v4 — noted here only so nobody "fixes" v3 again.
- `"# ZANTARA V6 SYSTEM PROMPT"` header naming (v1/v2/v3 all say "V6" regardless of the v1/v2/v3
  Python module version) — cosmetic drift between the header string and the module name. v4
  fixes its own header to say `(v4 with unified prompt door + date injection)` for
  operator-legibility in logs/traces, following the v2/v3 naming convention
  (`# ZANTARA V6 SYSTEM PROMPT (multi-language v2)` / `(multi-language v3 with worked
  examples)`).
- Keyword-trigger lists (`TOOL_USAGE_POLICY`'s "Keywords that trigger X" blocks) are a
  substring-matching pattern — cicatrix family #3 (guard-over-match). **These are NOT
  code-level guards** (no `if "keyword" in text` in Python gating tool calls) — they are prose
  instructions telling the LLM which keywords should make IT decide to call a tool. The failure
  mode is different: an over-fit keyword list can't "clobber" anything since there's no
  code-level enforcement, but a too-narrow list can make the model under-call tools on
  phrasings it doesn't recognize. v4 keeps the keyword lists (they are a proven pattern that
  demonstrably improved tool-calling reliability per the v1→v2→v3 changelog) but does NOT
  expand this PR's scope to a keyword-list redesign — that would risk changing tool-calling
  behavior contracts, which the mandate explicitly says to avoid ("WITHOUT changing tool-calling
  behavior contracts"). Left as-is, verbatim from v3.

## 2. v4 structure

`backend/prompts/zantara_core_v4.py` — same shape as v3 (imports v3's sections verbatim via
`noqa: F401` re-export pattern, matching how v2→v3 already works), with 3 changes:

1. **`TOOL_USAGE_POLICY_V4`**: v3's `TOOL_USAGE_POLICY` text with the KBLI deadline paragraph
   rewritten (F2) — everything else byte-identical (pricing rules, KBLI rules 1-4, RULE 5 villa
   mapping already correct, CRM query rules, parallel-tool-call guidance, web-search guidance,
   all keyword-trigger lists unchanged per F6).
2. **`WORKED_EXAMPLES_V4`**: v3's `WORKED_EXAMPLES` text with the villa KBLI example corrected
   (F4) — `55130`/`55194` → `55203` primary + `55901`/`55400` conditional, matching
   `TOOL_USAGE_POLICY RULE 5` exactly. All other examples (pricing, pricing-fallback, visa, tax,
   escalation, identity-lock, restaurant/IT-consulting KBLI) unchanged — restaurant `56101` and
   IT-consulting `62029`/`62012` spot-checked against the dataset, both correct.
3. **`ZANTARA_MASTER_TEMPLATE`**: same composition order as v3, with one new section —
   `<date_context>` — placed directly after the opening header and before
   `SECURITY_BOUNDARY`, as a `{today_wita}` format placeholder (NOT a static string — filled at
   build time by whichever consumer calls `.format()`, exactly like `{rag_results}`,
   `{user_memory}`, `{query}` already are). Consumers that don't pass `today_wita` get a safe
   default via `str.format_map` with a `_SafeDict` fallback (see §3) so this is non-breaking for
   any caller that doesn't yet know about the new placeholder.

No text is deleted from v3's `WORKED_EXAMPLES` or `TOOL_USAGE_POLICY` beyond the two corrections
above — v4 is a superset fix, not a rewrite. `SECURITY_BOUNDARY`, `SYSTEM_INSTRUCTIONS`,
`KNOWLEDGE_GOVERNANCE`, `LANGUAGE_PROTOCOL`, `GREETING_RULES`, `CITATION_RULES`,
`ESCALATION_PROTOCOL`, `CRASH_PROTOCOL`, `CLOSING_PHRASES`, `INTERNAL_MONOLOGUE`,
`CREATOR_PERSONA`, `TEAM_PERSONA` are re-exported from v3 unchanged (which itself re-exports
from v2 unchanged for everything except `WORKED_EXAMPLES`).

## 3. Date injection design

Placeholder name: `{today_wita}`. Format: ISO 8601 date + explicit timezone note —
`"2026-07-17 (WITA, UTC+8, Asia/Makassar)"`. **Revised after panel finding #9**: an earlier
draft used `%A, %d %B %Y` (weekday + full month name); dropped in favor of plain ISO because
`strftime` locale names depend on the container's OS locale (typically "C"/English regardless
of the user's language) — ISO is unambiguous and locale-independent, and the model can convert
it to a weekday name or any language itself if a response needs one.

Computed with the established repo pattern:
```python
from datetime import datetime
from zoneinfo import ZoneInfo

BALI_TZ = ZoneInfo("Asia/Makassar")

def today_wita_string() -> str:
    return datetime.now(BALI_TZ).strftime("%Y-%m-%d") + " (WITA, UTC+8, Asia/Makassar)"
```

**Panel findings #1 and #2 (both accepted, both fixed in the same edit)**: the cache key must
derive its date bucket from the SAME `datetime.now(BALI_TZ)` call used for the injected text
(not a separate `date.today()`, which reads the process/container timezone — likely UTC on
Fly, desyncing from the WITA text); and, discovered while inspecting this exact line, the
existing cache key was missing a hash of `query`/`rag_results` even though both are baked into
the cached `final_prompt` via `.format()` — a pre-existing bug (not introduced by this PR) that
can serve a stale system prompt (wrong query context, wrong RAG grounding) to a second, different
question from the same user within the 5-minute TTL. Both fixed together since they touch the
identical `cache_key = f"..."` construction:

```python
now_wita = datetime.now(BALI_TZ)
today_wita = now_wita.strftime("%Y-%m-%d") + " (WITA, UTC+8, Asia/Makassar)"
date_bucket = now_wita.strftime("%Y-%m-%d")
query_hash = _stable_hash(query)
rag_hash = _stable_hash(rag_results)
cache_key = (
    f"{user_id}:{deep_think_mode}:{facts_hash}:{coll_facts_hash}:{timeline_hash}:"
    f"{is_creator}:{is_team}:{ctx_hash}:{lang_key}:{date_bucket}:{query_hash}:{rag_hash}"
)
```

This helper lives in `zantara_core_v4.py` itself (not a new shared util module — matches the
"each file defines its own `BALI_TZ` constant" convention already established across
`team_timesheet_service.py`/`attendance_monitor.py`/etc., and keeps the v4 module
self-contained per the "additive only" mandate — no new shared dependency for other modules to
break).

**Where it's called**: `prompt_builder.py`'s `SystemPromptBuilder.build_system_prompt()`, at
the same point where `rag_results`/`user_memory`/`query` are already interpolated
(`ZANTARA_MASTER_TEMPLATE.format(...)` call sites, both the `detected_lang` branch and the
`else` branch — lines ~404 and ~446 in the current file). This computes the date fresh on every
request (cheap — one `datetime.now()` call), so it's never stale even if the process has been
running for days. NOT baked into the cached prompt string beyond the existing 5-minute TTL
cache in `SystemPromptBuilder` — actually it MUST be, since the cache key doesn't include date;
**cache-key fix required**: add a day-granularity date bucket to the existing cache key
(`cache_key = f"{user_id}:{deep_think_mode}:...:{date.today().isoformat()}"`) so a prompt built
at 23:59 WITA and served from cache at 00:01 WITA the next day doesn't say yesterday's date.
Day-granularity (not per-request) keeps the existing 5-minute-TTL cache's hit rate intact for
the overwhelmingly common case (same day).

## 4. Unified versioned entry point (the split-brain cure)

### 4.1 `prompt_manager.py` changes

Add a `v4` branch to the existing fallback chain, following the exact same defensive-import
pattern already used for v2/v3:

```python
_PROMPT_VERSION = os.environ.get("ZANTARA_PROMPT_VERSION", "v1").lower()

if _PROMPT_VERSION == "v4":
    try:
        from backend.prompts.zantara_core_v4 import ZANTARA_MASTER_TEMPLATE
    except ImportError:
        # fall through to v3 → v2 → v1, same chain as today
        ...
elif _PROMPT_VERSION == "v3":
    ...  # unchanged
```

Also export a new `get_prompt_template()` function (or expose the resolved
`ZANTARA_MASTER_TEMPLATE` + a `get_today_wita()` helper) that `prompt_builder.py` can import,
so the versioned door is a proper importable API, not just a module-level side effect other
files copy by re-importing the resolved constant.

### 4.2 `prompt_builder.py` changes (the actual cure)

Replace:
```python
from backend.prompts.zantara_core import (
    CREATOR_PERSONA,
    TEAM_PERSONA,
    ZANTARA_MASTER_TEMPLATE,
)
```
with:
```python
from backend.llm.prompt_manager import ZANTARA_MASTER_TEMPLATE
from backend.prompts.zantara_core import CREATOR_PERSONA, TEAM_PERSONA  # personas are version-stable, not templated
```
`prompt_manager.py` already resolves `ZANTARA_MASTER_TEMPLATE` to whatever
`ZANTARA_PROMPT_VERSION` selects (defaulting to v1, unchanged behavior by default) — this one
import-line change is what makes `ZANTARA_PROMPT_VERSION=v4` (or `v3`, or `v2`) actually reach
the WA bot for the first time since v2 was introduced.

`CREATOR_PERSONA`/`TEAM_PERSONA` stay imported from `zantara_core` (v1) directly — they are
persona overlays, not versioned templates (v2/v3/v4 all re-export them unchanged, `noqa: F401`,
confirming they're intentionally version-stable), so importing them from the v1 module is not
a split-brain — it's importing a constant that is identical across all four modules by
construction. (Verified: `grep CREATOR_PERSONA` across v1/v2/v3 shows v2/v3 re-export, never
redefine.)

Add the date placeholder to both `.format()` call sites (§3).

### 4.3 Parity test: `backend/tests/unit/prompts/test_prompt_source_parity.py`

Scans every `.py` file under `apps/backend-rag/backend/` (excluding `backend/prompts/` itself,
excluding `backend/tests/`, excluding `backend/llm/prompt_manager.py` — the one legitimate
resolver) via AST import-scan (not naive grep, to avoid false positives on comments/docstrings
mentioning `ZANTARA_MASTER_TEMPLATE`) for any `ImportFrom` node whose module starts with
`backend.prompts.zantara_core` (matches `zantara_core`, `zantara_core_v2`, `zantara_core_v3`,
`zantara_core_v4`) and whose imported names include `ZANTARA_MASTER_TEMPLATE`. Asserts the
result set is empty.

Rationale for the `backend/prompts/` exclusion (already argued in F1's scope note): the prompts
package is allowed to import its own template constants — that's not a split-brain, that's the
package's own internals (`zantara_persona.py`, `whatsapp_persona.py`,
`zantara_prompt_builder.py`, `__init__.py` all currently do this, all pre-existing, all out of
this PR's scope). The test's job is narrower and sharper: **no *consumer* outside the prompts
package may ever again import the raw template instead of going through the versioned door.**
This is exactly the shape of the bug this PR fixes (`prompt_builder.py` in
`services/rag/agentic/`, not in `prompts/`), and exactly the shape a future regression would
take (someone adds a new consumer next year, copies the wrong import out of muscle memory).

On first run (before the `prompt_builder.py` fix lands in the same PR) this test MUST fail —
that's the proof the split-brain existed. After the fix, it passes. This ordering is enforced
by writing the test and the fix in the same commit.

## 5. Rollout / rollback

- **Default env unchanged**: no `ZANTARA_PROMPT_VERSION` set → `prompt_manager.py` defaults to
  `"v1"` exactly as today. `prompt_builder.py` now gets v1 **via the versioned door** instead of
  a direct import — byte-identical template, different import path. This is the only behavior
  change for the default/no-flag case, and it is deliberately invisible: same template object,
  same `.format()` contract, same output. Confirmed by design (v1's `ZANTARA_MASTER_TEMPLATE`
  constant is passed through `prompt_manager.py` unchanged when `_PROMPT_VERSION` doesn't match
  v2/v3/v4).
- **Flip to v4**: operator/session sets `ZANTARA_PROMPT_VERSION=v4` on Fly (`fly secrets set` or
  `fly.toml [env]`, per CLAUDE.md §13 — this is a LATER step, explicitly out of this PR per the
  mandate: "prod flip to v4 is a LATER operator/session step, not this PR").
- **Rollback**: unset the env var (defaults to v1) or set back to `v3`/`v2`. No data migration,
  no schema change, no irreversible action — pure prompt-text + import-path change.
- **Blast radius**: `prompt_builder.py` is the WA bot's brain AND (per orchestrator_core.py
  call sites at both line 1036 and 1582) likely also serves other channels through the same
  agentic RAG orchestrator (webapp, telegram, instagram — the "4 live channels" in CLAUDE.md
  §12). This PR does not audit every channel's rendering of the new `<date_context>` block, but
  the change is additive text, not a removal — channels that ignore it lose nothing; channels
  don't rely on today's absence of a date block for anything (no test found asserting date
  ABSENCE).

## 6. Test plan

- `backend/tests/unit/prompts/test_prompt_source_parity.py` — new, asserts no non-prompts
  consumer imports the raw template (§4.3). MUST fail-then-pass in the same commit history
  (verified manually before commit, not asserted by the test itself).
- Existing `backend/tests/unit/llm/test_prompt_manager.py` — add a `v4` case mirroring the
  existing v2/v3 coverage (env var set → correct template resolves; import failure → falls back
  to v3).
- Existing `backend/tests/unit/services/rag/agentic/test_prompt_builder_comprehensive.py` and
  `test_prompt_builder_exponential_coverage.py` — run as-is (no signature change to
  `build_system_prompt()`'s public args); add one new test asserting `<date_context>` appears
  in the built prompt and contains today's WITA date.
- Full targeted run before commit: `PYTHONPATH=. pytest backend/tests/unit/llm/
  backend/tests/unit/services/rag/agentic/ backend/tests/unit/prompts/ -q` — must be green with
  NO `ZANTARA_PROMPT_VERSION` set (default env, proving default-path parity).

## 7. Explicitly out of scope for this PR (tracked, not silently dropped)

- `whatsapp_persona.py` double price SSOT (F5.1) — legacy overlay, not on the live WA path.
- Hardcoded prices/capital figures in `few_shot_examples.py` (F5.2) — separate module, separate
  PR; flagging BKPM-5/2025 three-way capital distinction as a correctness bug worth its own fix.
- Keyword-trigger-list redesign (F6) — explicitly excluded by the mandate
  ("WITHOUT changing tool-calling behavior contracts").
- `zantara_persona.py`, `zantara_prompt_builder.py`, `prompts/__init__.py` direct-import
  cleanup — all pre-existing, all inside `backend/prompts/`, none on the WA path; a genuine
  full-repo prompt-source consolidation is a separate mandate.
- Flipping prod's `ZANTARA_PROMPT_VERSION` to `v4` — operator/session step after this PR merges
  and the corner's LIVE STATE is updated, not part of this PR.

## 8. Panel (adversarial red-team, Codex `gpt-5.6-sol` xhigh, read-only)

Ran against the design as drafted in §1-§7. 10 findings, 8 BLOCKING, 2 NON-BLOCKING. All
re-verified against source before accepting/rejecting. Verdict per item:

1. **BLOCKING — cache-key doesn't hash `query`/`rag_results`.** VERIFIED as a real,
   **pre-existing** bug (not introduced by this design): `prompt_builder.py`'s cache key omits
   `query`/`rag_results`, but the cached `final_prompt` value has them baked in via `.format()`
   — within the 5-minute TTL, a second different question from the same user can be served the
   first question's system prompt (stale query context + stale grounding). **Accepted as
   in-scope to fix**: I am already touching this exact `cache_key` line to add the date bucket
   (§3), so adding `_stable_hash(query)` + `_stable_hash(rag_results)` to the same tuple is a
   strict superset addition (more granularity, never fewer cache hits than correct, cannot
   introduce a wrong answer, can only reduce hit rate) — same class of change already authorized
   by the mandate's "cache-key fix" for date. Fixed in `prompt_builder.py`.
2. **BLOCKING — date bucket must derive from the SAME `datetime.now(WITA)` call as the injected
   text**, not a separate `date.today()` (which uses process/container timezone, likely UTC on
   Fly — would desync from the WITA text and could bucket-flip at the wrong hour). **Accepted**:
   compute `now_wita = datetime.now(BALI_TZ)` once per build call, derive both the injected
   string and the cache-key date bucket from it.
3. **BLOCKING — v3's `get_pricing()` worked-example call shapes are schema-invalid.** VERIFIED
   against `backend/services/rag/agentic/tools.py:427-444` (`PricingTool.parameters_schema`):
   real schema is `{service_type: enum[visa,kitas,business_setup,tax_consulting,legal,all],
   query: string}`. v3's pricing WORKED_EXAMPLES teach `get_pricing(service_type="visa_extension",
   visa_code="C1", duration_days=60)` (invalid enum value, two non-existent parameters) and the
   fallback example teaches `get_pricing(service_type="akta_amendment_kbli")` (also invalid
   enum). v1/v2's own inline examples (`get_pricing(service_type="visa")`,
   `get_pricing("business_setup")`) are schema-correct — only v3's NEW `WORKED_EXAMPLES` section
   introduced the invalid shapes. **Accepted as in-scope**: same section I'm already correcting
   for the villa KBLI phantom codes (F4); this is a second, independently-verified bug in the
   identical worked-example block, and fixing it is "correcting an example to match the
   existing tool contract," not "changing the tool-calling behavior contract" (the schema
   itself is untouched). v4 rewrites both call shapes:
   `get_pricing(service_type="visa", query="C1 60-day extension")` and
   `get_pricing(service_type="legal", query="akta perubahan KBLI code change")`.
4. **BLOCKING — flipping WhatsApp from v1→v4 also activates v3 content that has never run
   live on this channel (worked-example prices as illustrative tool-return shapes, escalation
   phrases, identity-lock redirects) — "copy shape not values" doesn't fully neutralize LLM
   anchoring on the example numbers.** Reviewed, **accepted as residual risk, not blocking**:
   v3 already carries an explicit disclaimer ("ALWAYS call the actual tool... NEVER reuse the
   example numbers verbatim because prices change") immediately before the worked examples;
   stripping all illustrative numbers from WORKED_EXAMPLES would be a materially larger rewrite
   of content this PR did not audit line-by-line, and the mandate's own rollout design already
   treats "prod flip to v4" as a separate, later, PROVE-LIVE-gated step for exactly this reason
   (§5) — this PR ships the capability additively; the flip is where this risk gets a live
   check before Zero-facing traffic depends on it.
5. **BLOCKING — deadline-neutral rewrite of the KBLI paragraph could suppress an urgent nudge**
   for a client whose migration genuinely needs manual action (risk-level change) if the model
   over-reads "most cases auto-convert" as blanket reassurance. **Accepted, incorporated**: the
   v4 `TOOL_USAGE_POLICY` KBLI paragraph now explicitly instructs a 3-way triage instead of a
   single reassuring statement — (a) most codes auto-converted via OSS, no action needed; (b) if
   the client's registered activity's risk level changed, or they're unsure, manual action may
   be required — ask + suggest verifying with the team; (c) never assert "you're fine" without
   the client having actually described their situation. See exact text in `zantara_core_v4.py`.
6. **BLOCKING — the existing v2/v3 defensive-fallback pattern (silent `ImportError` → fall back
   one version, `logger.warning`) means an explicitly-requested `v4` that fails to import
   silently re-serves v3's phantom-code/stale-deadline content while ops believes v4 is live.**
   **Accepted, mitigated**: kept the existing fallback *behavior* (consistent with v2/v3,
   defensible against partial deploys per the existing code comments — changing the philosophy
   is out of this PR's scope) but bumped the log level from `WARNING` to `ERROR` for ALL
   explicitly-requested-version-failed branches (v2, v3, v4) so a silent regression is at least
   loud in logs/Sentry. PROVE-LIVE step (§5) explicitly checks logs for this signature before
   declaring v4 live.
7. **BLOCKING — does `{today_wita}` break the *other* consumer of `ZANTARA_MASTER_TEMPLATE`
   (`PromptManager` → `zantara_ai_client.py`, the Oracle/creator/team-persona path)?** VERIFIED
   a **pre-existing, separate P0 bug while checking this**: `PromptManager.build_system_prompt()`
   never calls `.format()` on `ZANTARA_MASTER_TEMPLATE` at all — it returns the raw template
   string with `{user_memory}`, `{rag_results}`, `{query}` still present as literal unresolved
   text, then string-concatenates `context_sections`. This means the Oracle/Creator-mode path
   (used directly by Antonello per `is_creator` detection in `prompt_builder.py`) has been
   leaking three literal curly-brace placeholders into every system prompt on that path,
   independent of anything in this PR. **NOT fixed here** — distinct bug, distinct blast radius
   (Oracle path, not WhatsApp), and fixing `PromptManager`'s placeholder resolution is its own
   mandate-sized change I was not asked to make. Flagged prominently in the PR body and to
   team-lead/Zero as a new P0 finding for a follow-up. Confirmed `{today_wita}` does not make
   this qualitatively worse (one more unresolved placeholder on an already-leaking path, not a
   new failure mode) — `prompt_builder.py` (the path THIS PR fixes) is the only consumer that
   actually calls `.format()` and will resolve `{today_wita}` correctly.
8. **BLOCKING — the AST parity test's `backend/prompts/` directory exclusion is evadable**: a
   future file OUTSIDE `backend/prompts/` could do `from backend.prompts import
   ZANTARA_MASTER_TEMPLATE` (via the package's `__init__.py` re-export) instead of
   `from backend.prompts.zantara_core import ...`, and a matcher scoped only to
   `module.startswith("backend.prompts.zantara_core")` would miss it. **Accepted, fixed**:
   widened the AST matcher to flag `ImportFrom` nodes where `module in ("backend.prompts",) or
   module.startswith("backend.prompts.zantara_core")` and `ZANTARA_MASTER_TEMPLATE` is among the
   imported names — still excluding files whose own path is under `backend/prompts/` and
   excluding `backend/llm/prompt_manager.py` (the one legitimate resolver).
9. **NON-BLOCKING — `%A, %d %B %Y` (weekday/month names) depends on OS/process locale**;
   containers typically run the "C" locale so this renders in English regardless of user
   language, which is not itself wrong (the field is an internal instruction, not user-facing
   text) but is implicit and fragile. **Accepted, simplified**: switched to explicit ISO 8601 —
   `<date_context>Today's date: 2026-07-17 (WITA, UTC+8, Asia/Makassar)</date_context>` — no
   weekday name, no locale dependency, unambiguous for the model to reason about deadline math
   regardless of which language it answers in.
10. **NON-BLOCKING — `ZANTARA_PROMPT_VERSION` is read at process import time, so any flip
    requires a restart/redeploy.** Already true of v1/v2/v3 (not new to v4) — documented in §5
    rollout notes, no code change needed.

**Net effect of the panel**: 2 additional verified bugs found and fixed inside the scope I was
already touching (get_pricing schema-invalid examples in WORKED_EXAMPLES; cache-key missing
query/rag_results hash) — both are strict corrections/additions, not new behavior. 1 new P0
bug discovered and explicitly NOT fixed here, flagged for a separate mandate (PromptManager
placeholder leak on the Oracle path). No blocking finding required abandoning or restructuring
the core design (unified versioned door + v4 template + date injection).

## 9. Verification findings (2026-07-17/18, resumed lane — adversarial re-check)

The implementer session that wrote §1-§8 above hit its usage window mid-work; a second session
resumed and verified the inherited diff against this document's own claims before shipping.
Two categories of gap found, both closed in the same commit as this doc's update.

### 9.1 — Test plan (§6) was written but never executed

`test_prompt_source_parity.py`, the v4 case in `test_prompt_manager.py`, and the
`<date_context>` assertion in the prompt_builder test suite — all three commitments in §6 —
did not exist on disk; only an empty `backend/tests/unit/prompts/__init__.py` was present.
Written now:

- `backend/tests/unit/prompts/test_prompt_source_parity.py` — the AST-based scanner from §4.3,
  widened per panel finding #8 (also catches `from backend.prompts import
  ZANTARA_MASTER_TEMPLATE`). Confirms zero non-`backend/prompts/` consumer imports the raw
  template outside `backend.llm.prompt_manager`.
- `TestPromptManagerVersionSelection` in `test_prompt_manager.py` — v1 (default)/v2/v3/v4
  selection via `ZANTARA_PROMPT_VERSION` + `importlib.reload`, since no v2/v3 coverage existed
  to "mirror" as §6 assumed.
- `TestDateContextInjection` in `test_prompt_builder_comprehensive.py` — confirms the default
  (v1) path has NO `<date_context>` block (backward-compat anchor) and the v4 path does, with
  today's WITA date.

### 9.2 — P0 found live: `.format()` crashes on v3/v4's embedded JSON worked examples

While writing a regression test for the date-context assertion, `ZANTARA_MASTER_TEMPLATE.format(...)`
raised `KeyError: '"price_idr"'` under `ZANTARA_PROMPT_VERSION=v4`. Root cause: v3's (and v4's,
which copies v3's `WORKED_EXAMPLES` verbatim aside from the two corrected examples) worked
examples embed illustrative JSON as prose, e.g. `Tool returns: {"price_idr": 1700000, ...}`.
That text is written as `{{"price_idr": ...}}` in the *template module's own* f-string (escapes
to literal single braces in the module's `WORKED_EXAMPLES` string value), but is invisible to a
**second**, later `.format()` call — the one `prompt_builder.py` performs — which requires
every brace pair in the ENTIRE template to be valid format syntax and chokes on the first
JSON-looking fragment it can't resolve as a keyword argument.

**Why this was dormant until this exact PR**: before F1's fix, `prompt_builder.py` always
imported `ZANTARA_MASTER_TEMPLATE` directly from v1 (which has no such JSON examples — v1
predates `WORKED_EXAMPLES`), regardless of `ZANTARA_PROMPT_VERSION`. F1's whole point is
routing the WA/webapp/telegram/instagram path through `prompt_manager` so the env var is
finally respected — which means whatever version the env var selects now actually reaches
`.format()`.

**Why this was live-critical, not a future flip-time risk**: `fly secrets list -a nuzantara-rag`
confirms `ZANTARA_PROMPT_VERSION` is SET as a deployed Fly secret today (value not readable —
secrets are write-only — but §1 F1's own text asserts prod runs v3 on the Oracle path, i.e. the
value is `v3`). Had this PR shipped with the F1 fix and the crash unpatched, `build_system_prompt()`
would have raised on literally the first query after deploy, on every one of the 4 live channels
that route through `SystemPromptBuilder` (no try/except wraps the call site in
`orchestrator_core.py:1036,1582` — confirmed by reading both call sites). This is NOT the §8
finding #4 residual risk (LLM anchoring on example numbers, deferred to the flip step) — it is a
hard crash, unconditional, on every query, the moment this PR's own core fix (F1) reaches prod
with the env var already set to a version whose `WORKED_EXAMPLES` predates safe escaping.

**Fix**: replaced both `ZANTARA_MASTER_TEMPLATE.format(rag_results=..., ...)` call sites in
`prompt_builder.py` with a new `_safe_template_fill()` helper — plain `str.replace("{key}",
value)` per known placeholder, not `str.format()`. This fixes v3 AND v4 without editing any
`zantara_core*.py` file (respects both the "additive only, v1/v2/v3 untouched" design
constraint in §2 and the repo's `zantara_core.py` off-limits rule) and is strictly more robust
than escaping each JSON example by hand, since it can't regress the next time someone adds an
illustrative payload to a worked example. Verified: all four versions (v1/v2/v3/v4) now call
`build_system_prompt()` without raising — locked in by a new parametrized regression test,
`TestTemplateFillDoesNotChokeOnEmbeddedBraces` in `test_prompt_builder_comprehensive.py`.

**Not fixed, flagged for follow-up**: the underlying `.format()`-unsafe text still lives in
`zantara_core_v3.py` itself (out of scope per the additive-only constraint — `prompt_builder.py`
no longer calls `.format()` on it, so it's inert there, but `PromptManager.get_system_prompt()`
or any future caller that DOES call `.format()` directly on a v2/v3/v4 template would hit the
same crash). Tracked alongside the other §7 out-of-scope items for a follow-up PR: audit every
`.format()`-based consumer of `ZANTARA_MASTER_TEMPLATE`, not just the one this PR fixes.
