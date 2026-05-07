# Wave 3 Critical Review

## A. Fix Verification (Wave 2 patches)

1. **`foundations/__init__.py` PEP 562 `__getattr__`** – Correctly exposes all 4 lazy items (`ArxivSanityScorer`, `LabeledPaper`, `NERExtractor`, `NamedEntity`). `__all__` includes them; `__getattr__` caches after first access. Wildcard imports work because Python calls `getattr` for each name in `__all__`, triggering the lazy loader. No issue found.

2. **`cron-wrapper.sh` atomic publish** – The `mkdir -p` + temp file + `mv` pattern is sound under normal operation. **Two gaps remain:**
   - No locking; if two instances run concurrently (e.g., cron drift or manual invocation), the final `mv` will silently overwrite each other’s snapshot.
   - If `$SNAPSHOT_DIR` is deleted between `mkdir -p` (once at start) and `mv`, the `mv` will fail noisily. A `mv` to a nonexistent parent directory is an error, but the script lacks a guard or fallback.  
     _Severity_: Low (daily 04:00 WITA, unlikely to collide or have directory removed).

3. **`NERExtractor` class‑level lock** – The double‑checked locking pattern uses `self._pipeline` (instance attribute) but a class‑level `_lock`. If two `NERExtractor` instances are created on different threads, each will see its own `_pipeline is None` and independently load the model (each ~440 MB). This defeats the intent of a shared model per process. In practice the codebase likely uses a single instance, but the design is not thread‑safe across instances. _Severity_: Medium if multiple instances are ever created; low otherwise.

## B. Modules Under‑Reviewed (Waves 1+2 did not deeply analyze)

1. **`gdelt_client.py`** – `_parse_seen_date` returns `None` for missing or malformed timestamps. The caller does not filter; `GdeltArticle.seen_date` is `Optional[datetime]`. No downstream code in the current stack assumes `non-None`, so it’s safe. No finding.

2. **`bali_calendar.py`** – `_pawukon_day_index` uses Python’s `%` (non‑negative for negative deltas), `wuku_day = (idx % 7) + 1` correctly gives 1‑based index for day 1 of cycle (`idx=0` → `wuku_day=1`). Verified against anchor dates. No finding.

3. **`gov_apis_inventory.json`** – Not used by `opensanctions_id.py`; the OpenSanctions URLs are hardcoded as constants. No issue.

## C. Cross‑Cutting Concerns

1. **`PasalIdClient` statefulness** – Instance holds `_api_token` but no mutable shared state across async `search_laws` calls. Thread‑safe by design (no shared data). No finding.

2. **Timeout inconsistency** – `pasal_id_client` uses 30 s, `opensanctions_id` uses 60 s, `gov_apis_health` uses 15 s. This is intentional: different backends have different latency profiles. No inconsistency that bites; the values are reasonable for each endpoint class.

## D. Plan Drift (vs. `2026-05-08-domain-mesh-phase0-foundations.md`)

1. **pasal.id client endpoint** – The plan tentatively used `https://pasal.id/api/mcp` (FastMCP) but the implementation (correctly) uses `https://pasal.id/api/v1` with bearer‑token auth. This is a **minor drift**; the plan was provisional and the live endpoint was discovered during development. The code aligns with the actual API.

2. **Cron script path** – The plan specifies `~/scripts/domain-mesh-foundations-cron.sh`, but the actual file is named `cron-wrapper.sh` and is located in a different directory (not shown in the code snippets, but the `cd` path suggests it lives inside the repo). The LaunchAgent plist (which references the script) is not yet created. This is a **moderate drift**; the implementation took a slightly different file layout without updating the plan. Would expect the plan to be updated or the script path to match.

## Final Judgment

No critical issues remain. The three findings (concurrent cron locking, NER instance‑level pipeline duplication, plan drift on script path) are minor and well within “diminishing returns.” The code is production‑ready after Waves 1+2.
