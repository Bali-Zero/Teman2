# Visa Catalogue rebuild from authoritative seed

**Date:** 2026-04-21
**Author:** Claude (Opus 4.7, 1M ctx) — brainstormed with Antonello (Zero)
**Scope:** `apps/backend-rag/backend/services/visa_check/{catalogue,match_tree,pricing_bridge}.py`
**Branch target:** `refactor/visa-catalogue-from-seed`

---

## Why

The current `catalogue.py` (shipped in PR #137, Visa Check app) lists 12 visa types chosen from Claude's generic memory, not from the Bali Zero knowledge base. Concretely:

- `B211A` is included, but B211A is **pre-2023-reform nomenclature** — immigrasi.go.id no longer recognises it. It is absent from both authoritative sources (seed + pricing JSON). The match tree recommends it in two branches (`WORK_REMOTE` low-budget, `LONG_TOURISM` 3–6mo); `pricing_bridge` therefore returns `None` for those paths, and the UI fallback ("confirm on WhatsApp") hides a real bug.
- Remaining 11 codes are correct but incomplete: no coverage for multi-entry business travellers, short business/internship visits, pre-PMA investors, freelance residents, or 5-year golden-visa retirees.

Goal: rebuild the three files so **every code is justified by an authoritative source**, the recommender returns a **ranked list** (not a single pick), and the pricing bridge maps correctly to the real JSON keys.

## Authoritative sources (ranked)

| #   | Source                                                                    | What it gives                                                                                      | What it does NOT give                                                             |
| --- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| 1   | `backend/migrations/scripts/seed_visa_types_complete_2026.py` (114 codes) | `code`, `name` (EN), `name_id` (Bahasa), `category`                                                | `duration` is `"See details"`, `cost_visa` is `"Contact for Quote"` for every row |
| 2   | `backend/data/bali_zero_official_prices_2025.json` (67 entries)           | Real IDR prices under **name-based keys** (e.g. `"C1 Tourism"`, `"E33G Remote Worker (Offshore)"`) | No systematic `code` field — most entries have `code: ""`                         |
| 3   | MEMORY.md `reference_visa_c_duration_rules.md`                            | C1/C2/C6/C7 = 60d + 2×60d = 180max; C7A/B = 30d non-extendable                                     | Only C-series                                                                     |
| 4   | NB-2 NotebookLM (Immigration notebook)                                    | Consulted for any duration/policy question NOT answered by #3                                      | —                                                                                 |

If a field cannot be sourced from #1–#4, we fail loud (write it in the code comment: `# duration: UNVERIFIED — confirm via NB-2 before merge`).

## Scope: 18 VisaType values

**Keep (11 — present in seed, current enum values unchanged):**
`C1`, `C2`, `C7`, `C7A`, `C7B`, `E33G`, `E28A`, `E23`, `E33F`, `E31`, `E30A`

**Add (7):**

| Code            | Purpose branch           | Rationale                                                      |
| --------------- | ------------------------ | -------------------------------------------------------------- |
| `C6`            | `LONG_TOURISM` alt       | Social visit — used when reason is family/NGO not pure leisure |
| `C22A`          | `WORK_EMPLOYEE` short    | Internship 60d — pre-KITAS sampling                            |
| `C18`           | `WORK_EMPLOYEE` short    | Work trial 90d — pre-E23 probation                             |
| `D2`            | `WORK_REMOTE` alt        | Multi-entry business — digital workers who travel in/out       |
| `D12`           | `INVESTOR` pre-PMA       | Business investigation 1–2yr — scouting before E28A            |
| `E33E`          | `RETIREMENT` high-budget | Golden Second Home elder 5yr — premium retirement tier         |
| `E23_FREELANCE` | `WORK_REMOTE` alt        | Freelance KITAS — for users invoicing Indonesian clients       |

**Drop (1):** `B211A` — not in seed, confirmed by parsing 114 codes.

**Total: 18 codes.**

### E23_FREELANCE enum handling

Python enum name is `E23_FREELANCE`, value is `"E23-FREELANCE"` (trattino matches the seed exactly). Column `visa_type VARCHAR(16)` — fits (13 chars). Serialisation: `.value` always returns `"E23-FREELANCE"`; existing rows unaffected.

## File-by-file deltas

### `catalogue.py` (rewrite)

Single source of truth: `VISA_META: dict[VisaType, VisaMeta]`.

```python
@dataclass(frozen=True)
class VisaMeta:
    name_en: str                   # from seed.name
    name_id: str                   # from seed.metadata.name_id
    category: str                  # from seed.category
    purposes: frozenset[Purpose]   # which match_tree branches surface this
    duration_days: int             # base validity (source #3 or #4)
    extensions: tuple[int, int]    # (count, days_each); (0, 0) = non-extendable
    min_budget_idr: int | None     # None = no budget gate
    notes: str                     # 1-line human hint for UI/reason
    seed_source: str               # "seed" | "seed+NB2" — audit trail
    duration_source: str           # "reference_visa_c_duration_rules.md" | "NB-2" | …
```

**Retro-compat:** `DEFAULT_DURATION_DAYS` and `EXTENSION_POLICY` become **derived** dict comprehensions over `VISA_META`, so `clock.py` imports stay unchanged:

```python
DEFAULT_DURATION_DAYS = {vt: meta.duration_days for vt, meta in VISA_META.items()}
EXTENSION_POLICY = {vt: meta.extensions for vt, meta in VISA_META.items()}
```

### `match_tree.py` (rewrite core)

**New result shape (ranked, backwards-compatible):**

```python
@dataclass(frozen=True)
class RankedVisa:
    visa: VisaType
    score: float              # 0.0–1.0
    reason: str               # why this rank
    fit_tags: list[str]       # ["budget_match", "duration_exact", "foreign_employer_salary", …]

@dataclass(frozen=True)
class MatchResult:
    ranking: list[RankedVisa]        # ordered best → worst, len 1–4
    pre_arrival_steps: list[str]     # steps for ranking[0]
    referral_mode: bool              # True when ranking empty → WA CTA
```

**Ranking sizes per purpose (domain-driven, not budget-driven):**

| Purpose         | Size | Codes considered                                                                   |
| --------------- | ---- | ---------------------------------------------------------------------------------- |
| `WORK_EMPLOYEE` | 1    | `E23` (+ `C18`/`C22A` only if duration_months ≤ 3)                                 |
| `STUDENT`       | 1    | `E30A`                                                                             |
| `FAMILY`        | 1    | `E31`                                                                              |
| `RETIREMENT`    | 2    | `E33F`; `E33E` if budget > 500M                                                    |
| `INVESTOR`      | 2–3  | `E28A`; `D12`; `E33G` (bridge)                                                     |
| `WORK_REMOTE`   | 2–3  | `E33G`; `E23_FREELANCE` (tag: `invoices_indonesian_clients`); `C1`/`C2` short-term |
| `LONG_TOURISM`  | 2–3  | `C1`; `C2` mixed; `C6` social                                                      |
| `OTHER`         | 0    | → `referral_mode=True`                                                             |

**Key behaviour:** no hardcoded `VisaType.X` in the branch logic. Each branch filters `VISA_META` by `(purpose in meta.purposes) and (budget_ok) and (duration_ok)`, scores each candidate, sorts, returns top-N.

**Scoring (simple, deterministic):**

```
score = 0.5                            # base
      + 0.3 if budget_band matches meta.min_budget_idr bracket
      + 0.2 if duration_months fits within meta total duration+extensions
      - 0.2 if fit_tag conflicts with input (e.g. user said foreign employer but visa is local)
clamp [0.0, 1.0]
```

### `pricing_bridge.py` (update hints)

Replace `_SEARCH_HINTS` with name-based hints reflecting the JSON reality:

```python
_SEARCH_HINTS: dict[VisaType, tuple[str, ...]] = {
    VisaType.C1:             ("C1 Tourism",),
    VisaType.C2:             ("C2 Business",),
    VisaType.C6:             ("C6", "Social"),                     # likely None — acceptable
    VisaType.C7:             ("C7", "Internship"),                 # best-effort
    VisaType.C7A:            ("C7A&B Music/Art", "C7A"),
    VisaType.C7B:            ("C7A&B Music/Art", "C7B"),
    VisaType.C18:            ("C18 Work Trial",),
    VisaType.C22A:           ("C22A&B Internship (60 Days)",),
    VisaType.D2:             ("D12 Business Investigation (1 Year)",),  # closest multi-entry
    VisaType.D12:            ("D12 Business Investigation (1 Year)", "D12 Business Investigation (2 Years)"),
    VisaType.E23:            ("Working KITAS (Offshore)", "Working KITAS"),
    VisaType.E23_FREELANCE:  ("Freelance E23 (Offshore)", "Freelance E23"),
    VisaType.E28A:           ("Investor KITAS 2 Years (Offshore)", "Investor KITAS"),
    VisaType.E30A:           ("Education", "Student"),              # known None — seed lacks pricing
    VisaType.E31:            ("Dependent 1 Year (Offshore)", "Spouse 1 Year (Offshore)", "Family"),
    VisaType.E33E:           ("Retirement KITAP + MERP", "Retirement"),  # 5yr premium
    VisaType.E33F:           ("Retirement (Offshore)", "Retirement"),
    VisaType.E33G:           ("E33G Remote Worker (Offshore)", "E33G Remote Worker"),
}
```

**Offshore preferred** over Altus/Onshore in every KITAS lookup (user-friendly default: cheaper, standard path for fresh applicants).

**Known legitimate None returns:** `C6`, `E30A` — UI already shows "confirm on WhatsApp" for these.

## Test matrix

### Unit (new file `test_catalogue_vs_seed.py`)

Parses the seed at test time and asserts:

1. Every `VisaType.value` exists in seed (guard against drift).
2. Every `VisaMeta.name_en` matches `seed[code].name` (guard against rename).
3. Every `VisaMeta.category` matches `seed[code].category`.

### Unit (match_tree)

4. Every `Purpose` except `OTHER` yields a non-empty `ranking` for at least one `(budget, duration)` combo.
5. `ranking` is sorted by `score` descending.
6. `ranking[0].visa` is always in `VISA_META` keys (no dangling code).
7. `OTHER` returns `referral_mode=True` with empty `ranking`.

### Unit (pricing_bridge)

8. For every `VisaType` except `{C6, E30A}`, `estimate_match_cost` returns `cost_idr != None`.
9. `C6` and `E30A` return `(None, None)` — explicit, not a crash.

### Contract (clock.py compat)

10. `DEFAULT_DURATION_DAYS` and `EXTENSION_POLICY` keys include the original 11 codes → existing clock.py tests pass unchanged.

### Integration (live backend)

11. `POST /api/visa/match` × 7 purposes × 3 budget bands = 21 calls.
12. Every response has `ranking` non-empty OR `referral_mode=true`.
13. Backwards-compat fields present: `recommended_visa = ranking[0].visa`, `alternatives = [r.visa for r in ranking[1:]]`.
14. `estimated_cost_idr` non-null for at least 17 of the 21 calls.

## API backwards-compat contract

The HTTP response shape `/api/visa/match` keeps `recommended_visa`, `alternatives`, `reason`, `estimated_cost_idr` fields (read by current frontend). **Adds** a new optional `ranking: list[{visa, score, reason, fit_tags}]` field. Frontend migration to `ranking` happens in a separate PR.

## Non-goals

- No changes to `repository.py`, `clock.py`, routers, frontend.
- No Alembic migration — `visa_type VARCHAR(16)` already fits the longest code (`E23-FREELANCE` = 13).
- No new purpose path (no `WORK_REMOTE_LOCAL` split — deferred to a UX design round).
- No pricing JSON edits — it's the source of truth, we adapt to it.

## Deliverable

1. This spec at `docs/superpowers/specs/2026-04-21-visa-catalogue-rebuild.md` (committed).
2. Branch `refactor/visa-catalogue-from-seed` with:
   - 3 modified files (`catalogue.py`, `match_tree.py`, `pricing_bridge.py`).
   - 1 new test file (`test_catalogue_vs_seed.py`).
   - Updates to existing match_tree / pricing_bridge tests for the new ranking shape + backwards-compat assertions.
3. Federation orchestrator red-team dispatch before merge:
   `./scripts/ai-dispatch.sh redteam "visa catalogue rebuild — verify every code against seed + price map + NB-2 duration rules"`

## Fail-loud contract

If during implementation:

- any `VisaType.value` cannot be found in the seed → **STOP**, message user;
- NB-2 is consulted and returns an answer that contradicts source #3 → **STOP**, message user, do not guess;
- a pricing hint resolves to `None` for a code NOT in `{C6, E30A}` → **STOP**, message user, fix hints or widen search.

This is the bug we're fixing — we will not re-introduce it.
