---
date: 2026-05-12
wave: 4
producers: regulatory_watcher, peraturan_ingestion_trigger
status: implemented
---

# Wave 4 — regulatory-watcher + peraturan_ingestion_trigger → Intel Lake

## Scope

2 producers focused on legal/regulatory documents:

- `regulatory-watcher` (`~/scripts/regulatory-watcher-run.sh`, daily 07:00 WITA): multi-LLM cascade scans JDIH / Hukumonline / Ortax / MUC, emits `~/Desktop/nuzantara/research/regulatory/<date>-delta.json` + Telegram + EventBus (`regulatory.delta.detected`).
- `peraturan_ingestion_trigger` (`apps/evaluator/nlm_deep_research/peraturan_ingestion_trigger.py`, scheduled): Google Sheet driven PDF download → backend `/api/legal/upload` (RAG + KG) → Drive PERATURAN folder → NB-6 NotebookLM → Sheet status.

Both are CRITICAL producers (legal exposure for Bali Zero if data drifts) — Wave 4 plan calls for **dual-write retained for first 30 days post-cut-over** as defensive measure.

## Patches applied

### regulatory-watcher-run.sh

Inside the inline Python block that publishes to EventBus, after each delta is emitted, also enqueue to Intel Lake outbox:

```python
import hashlib
from intel_lake_outbox import enqueue as _lake_enqueue
for delta in deltas:
    ...
    _lake_enqueue('regulatory_watcher', {
        'producer_name': 'regulatory_watcher',
        'canonical_url': delta.source or f'regulatory-watcher://delta/{citation}',
        'content_hash': sha256(citation + title)[:32],
        'title': citation + ' — ' + title,
        'summary': delta.summary,
        'source_domain': delta.source_domain or 'regulatory-watcher',
        'language': 'id',
        'jurisdiction': 'ID-national',
        'topic_tags': ['regulation', regulation_type] + service_lines,
        'published_at': first_seen_at,
        'raw_payload': {
            'citation': citation,
            'urgency': urgency,
            'verbatim_excerpt': verbatim_excerpt[:2000],
        },
    })
```

Failure to import or enqueue is logged and swallowed — must NOT block the watcher daily cron.

### peraturan_ingestion_trigger.py

Inside `_ingest_to_backend()`, after successful POST to `/api/legal/upload`, enqueue observation with `source_domain=peraturan.go.id`, `topic_tags=['regulation','legal', row.tipo]`. The raw_payload preserves `tipo`, `anno`, `tier`, and `backend_response_chunks` for downstream auditability.

## Verification

- `bash -n` clean on regulatory-watcher-run.sh
- Inline Python block parsed via ast: OK (3003 chars)
- `ast.parse` clean on peraturan_ingestion_trigger.py

## Volume estimate (24h)

- `regulatory_watcher`: daily 07:00, typical 1-5 new deltas/day, peaks at 10-20 during Permenkumham/PMK release weeks
- `peraturan_ingestion_trigger`: scheduled (~daily), ~1-3 new PDFs/day driven by Google Sheet PENDING rows

Combined: ~5-25 observations/day. Trivial drain volume.

## Out of scope this PR

This PR contains ONLY the design doc. The patches live in:

- `~/scripts/regulatory-watcher-run.sh` (NOT in repo — operator-managed script on Pro)
- `apps/evaluator/nlm_deep_research/peraturan_ingestion_trigger.py` (IN repo — separate commit on this branch)

## Stop-loss

Same as Wave 1/3: `~/.intel-lake-wave2-blocked` file pauses Wave 5 if shadow-validate detects divergence >15%.
