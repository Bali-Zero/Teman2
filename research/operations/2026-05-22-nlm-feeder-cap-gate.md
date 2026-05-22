---
date: 2026-05-22
domain: operations
client_case: NB automations hardening — W15 nlm_feeder NB source-count cap gate
sources: 4
---

# nlm_feeder W15: NB source-cap gate + stderr-surface

## Context

Loop iteration 15. W14 deferred-list item §2: "NLM-INTEL-AIResearch
source cap: 600/1000 reached, every `nlm source add` returns 'Could
not add url source' in 3s but worker logs only 'case_not_resolved'
with no actionable context."

W15 survey confirms the cap is real:

| NB                   | Sources | At cap |
| -------------------- | ------- | ------ |
| NB-INTEL-AIResearch  | 600     | YES    |
| NB-INTEL-Press       | 216     | no     |
| NB-INTEL-Immigration | 80      | no     |
| NB-INTEL-Regulation  | 41      | no     |
| NB-INTEL-Tax         | 17      | no     |

Empirical live test against AIResearch returns 3-second rejection. The
worker has been wasting cycles + generating noise on every cron firing.

## Fix shipped

`apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` changes:

### New: cap helper

```python
NLM_NOTEBOOK_SOURCE_CAP = 500          # conservative midpoint between
                                        # observed accept (216) and reject (600)
_NB_COUNT_CACHE: dict[str, (int, ts)]   # 1h TTL cache

def _nlm_notebook_source_count(nb_id) -> int | None:
    """Cached source_count probe via `nlm notebook list`.
    On error → None (graceful degrade: let CLI try)."""

def _nlm_at_cap(nb_id) -> bool:
    """True if count >= 500; False if below or probe failed."""
```

### Modified: `_nlm_add_url`

```python
def _nlm_add_url(notebook_id: str, url: str) -> bool:
    if not notebook_id:
        return False
    if _nlm_at_cap(notebook_id):
        logger.warning("[nlm_feeder] skip add (NB at cap): nb=%s url=%s",
                       notebook_id, url)
        return False
    try:
        result = subprocess.run([...], timeout=60)
        if result.returncode == 0:
            return True
        # W15: surface stderr so operator sees why
        stderr_blob = (result.stderr or "") + (result.stdout or "")
        snippet = stderr_blob.replace("\n", " ").strip()[:200]
        logger.warning("[nlm_feeder] add_url rejected: nb=%s url=%s rc=%d reason=%s",
                       notebook_id, url, result.returncode, snippet or "(empty)")
        return False
    except Exception as e:
        logger.warning(f"[nlm_feeder] Failed to add {url}: {e}")
        return False
```

### Modified: `_nlm_add_text`

Same cap gate + stderr-surface on non-auth rejection paths. Auth-retry
path unchanged (still attempts ONE headless refresh).

## Tests

`apps/mata-garuda/tests/test_nlm_feeder_cap_gate.py` (9 tests):

| Test                                                 | Coverage                                |
| ---------------------------------------------------- | --------------------------------------- |
| `test_nlm_at_cap_true_when_count_above_threshold`    | gate fires at ≥500                      |
| `test_nlm_at_cap_false_when_count_below_threshold`   | gate inactive at 216                    |
| `test_nlm_at_cap_false_on_probe_failure`             | graceful degrade on probe error         |
| `test_add_url_skips_when_at_cap`                     | no subprocess spawn when at cap         |
| `test_add_url_surfaces_stderr_on_rejection`          | log contains "Could not add url source" |
| `test_add_url_success_still_returns_true`            | happy path preserved                    |
| `test_source_count_cache_hits_within_ttl`            | second call within 1h doesn't re-spawn  |
| `test_source_count_returns_none_on_subprocess_error` | error path                              |
| `test_source_cap_constant_matches_design`            | constants locked                        |

**9/9 PASS** in 0.20s.

Full mata-garuda suite (excluding flaky concurrent-test): **938 passed
(+9 W15), 21 skipped, 1 pre-existing UUID-drift failure** (unrelated).

## Empirical live verification

```python
from mata_garuda.workers.nlm_feeder import _nlm_at_cap, _nlm_notebook_source_count
# AIResearch (id dc5d01cd-...): count=600, at_cap=True   ← gate FIRES
# Press (id 9d262101-...):      count=216, at_cap=False  ← gate INACTIVE
```

Next nlm-feeder cron will:

- Skip every ai_research item destined for AIResearch (log "skip add (NB at cap)")
- Continue normal add for press/immigration/regulation/tax items
- Save ~30-60s wasted subprocess time per fire

## Cross-tree gotcha (W14 lesson recurrence — DOUBLE OCCURRENCE this session)

Initial Edit calls reported "updated successfully" but inspection showed
**no changes landed** — likely a Edit-tool ghost-success or linter revert
between my Edit and the next tool call. Re-running the same Edit
(unchanged old_string / new_string) succeeded. Lesson: when Edit reports
success but downstream tests/greps show no change, IMMEDIATELY re-grep
to confirm + re-Edit if needed before continuing. Don't assume the tool
result is authoritative.

This is the second W9-cross-tree pattern hit in 2 iterations (W14 hit
it via wrong absolute path; W15 via ghost Edit revert). Either way, the
fix discipline is the same: verify with grep after every Edit on
critical files.

## Operator runbook impact

Future cap-rejection diagnoses:

```bash
# OLD: had to manually test `nlm source add <X>` and parse stderr
$ nlm source add dc5d01cd-... --url https://example.com
Error: Could not add url source.
# (no automatic alert; operator had to notice the symptom)

# NEW: greppable WARNING in worker log
$ grep "skip add (NB at cap)" ~/logs/matagaruda-nlm-feeder-stream.log
[nlm_feeder] skip add (NB at cap): nb=dc5d01cd-... url=https://arxiv.org/abs/2604.07350

# Also greppable: rejection reasons (auth issue, URL issue, etc.)
$ grep "add_url rejected" ~/logs/matagaruda-nlm-feeder-stream.log
[nlm_feeder] add_url rejected: nb=dc5d01cd-... url=https://x rc=1 reason=Error: Could not add url source
```

Operator no longer needs to manually dive into NLM CLI to diagnose
"why isn't NB-INTEL-AIResearch getting fed?". The warning log answers
it directly: NB at cap. Action: either delete old sources from NB,
upgrade Google tier, or add overflow NB.

## Open questions (deferred)

- **W16 candidate: overflow NB routing**: when AIResearch hits cap,
  ai_research items get silently dropped (logged but no fallback NB).
  Could add `NLM_DOMAIN_ROUTING_FALLBACK` map: `ai_research →
ai_research_overflow_q2_2026`. Operator manually creates new NB +
  registers ID + worker auto-routes when primary is full. Defer until
  Antonello decides whether to upgrade Google tier vs overflow strategy.
- **Cap value tuning**: 500 is conservative. If Workspace cap is
  empirically 1000, half the capacity goes unused. Worth running a
  one-shot binary search probe (add to a fresh NB until reject) to
  establish the real number. Defer.
- **Cache invalidation when operator manually deletes sources**: 1h
  TTL means stale-cache for up to an hour after manual delete. Could
  add file-watcher on a `.nlm-cap-invalidate` flag file. Defer (low
  value — manual deletes are rare).
- **Per-worker startup PEL drainage** (W13 deferred): unchanged.
- **wr2-canva-renderer plist resurrection** (W14 deferred): unchanged
  (out of NB scope).
- **nexus-bridge legacy decision** (W11/W12/W13/W14 deferred):
  unchanged.

## Sources

1. W14 cicatrix open question — open-questions §2
2. Empirical `nlm notebook list` 2026-05-22 10:50 WITA: 5 NB counts
3. Empirical `nlm source add dc5d01cd-... --url <X>`: returns
   "Could not add url source" in ~3s
4. `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` lines 53-217
   (W15 edits)
