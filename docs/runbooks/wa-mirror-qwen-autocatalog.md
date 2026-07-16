# WA Mirror Qwen Autocatalog Runbook

This drains WA Mirror document backlog into review proposals without writing to
CRM/Kita. It is the safe test lane for local Qwen vision/text classification.

## Scope

- Run on the Pro only; the DB and WA Mirror blobs stay local to the Pro.
- Use Mini Ollama through an SSH tunnel by default.
- Keep `INTAKE_WRITER_ENABLED=0`, `INTAKE_AUTO_ATTACH_ENABLED=0`, and
  `INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED=0`.
- Produce `document_routing_proposal` rows for `/review`; auto-attach is a
  separate explicit step after aggregate counts are inspected.

## Start A Timed Test

From Air-M5:

```sh
ssh pro 'bash -lc "cd /Users/nuzantara/nuzantara && INTAKE_QWEN_RUN_SECONDS=180 scripts/intake_qwen_autocatalog_worker.sh"'
```

From the Pro:

```sh
cd /Users/nuzantara/nuzantara
INTAKE_QWEN_RUN_SECONDS=180 scripts/intake_qwen_autocatalog_worker.sh
```

For a long-lived tmux lane on the Pro:

```sh
tmux new -s wa-qwen-autocatalog 'cd /Users/nuzantara/nuzantara && scripts/intake_qwen_autocatalog_worker.sh'
```

## Verify Aggregate Progress

Use aggregate counts only; do not print raw paths, phones, OCR, or client names.

First classify the current review backlog into automation buckets:

```sh
PYTHONPATH=apps/backend-rag python scripts/intake_reprocess_backlog.py --review-backlog-report
```

Bucket meaning:

- `auto_attach_eligible`: strong-ID concordance already says it can be attached,
  still gated by `INTAKE_AUTO_ATTACH_ENABLED` and `INTAKE_WRITER_ENABLED`.
- `direct_phone_auto_catalog`: direct WhatsApp chat, existing CRM client resolved
  by sender-phone policy, doc type supported by Kita; still gated by
  `INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED` and `INTAKE_WRITER_ENABLED`.
- `direct_new_prospect_candidate`: direct WhatsApp chat with no CRM match yet and
  a supported doc type. This is the next safe automation target, but it needs a
  separate create-client/prospect gate before any document can be attached.
- `direct_unknown_reclassify`: direct WhatsApp unknown doc with enough saved OCR
  for local Qwen text reclassification.
- `group_human_review` / `missing_context_review` / `remaining_human_review`:
  keep gated until a stronger identity signal exists.

```sh
psql -X -qAt postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev <<'SQL'
SELECT pipeline_version || E'\t' || status || E'\t' || COALESCE(stage,'<null>') || E'\t' || COUNT(*)
FROM intake_queue
WHERE source='whatsapp' AND pipeline_version LIKE 'v2.2%qwen%'
GROUP BY pipeline_version, status, stage
ORDER BY pipeline_version, COUNT(*) DESC;

WITH wa_review AS (
  SELECT COALESCE(p.entity_resolution->>'decision', p.commit_gate->>'decision', 'proposal_only') AS decision
  FROM document_routing_proposal p JOIN intake_queue q ON q.id=p.queue_id
  WHERE p.status='review_pending' AND q.source='whatsapp'
)
SELECT decision || E'\t' || COUNT(*) FROM wa_review GROUP BY decision ORDER BY COUNT(*) DESC;
SQL
```

Dry-run the write candidates after a test batch:

```sh
PYTHONPATH=apps/backend-rag python scripts/intake_reprocess_backlog.py --auto-attach-eligible --auto-attach-limit 500
PYTHONPATH=apps/backend-rag python scripts/intake_reprocess_backlog.py --auto-attach-direct-phone --auto-attach-limit 500
```

## Promote Direct New Prospects

This is the safe bridge for the `direct_new_prospect_candidate` bucket. It
creates or resolves a local CRM lead from the direct-chat sender phone, supersedes
the stale `NO_MATCH` proposal, and resets the queue row to `validated` so the
normal worker runs only the route stage. It does not upload documents to Kita.

Dry-run first:

```sh
PYTHONPATH=apps/backend-rag python scripts/intake_reprocess_backlog.py \
  --promote-direct-new-prospects --auto-attach-limit 500
```

Apply the prospect promotion only after the aggregate count matches the reviewed
bucket:

```sh
PYTHONPATH=apps/backend-rag python scripts/intake_reprocess_backlog.py \
  --promote-direct-new-prospects --auto-attach-limit 500 --apply
```

Then run the intake worker against only the promoted rows. The launcher keeps
writer and auto-attach flags off by default:

```sh
INTAKE_PIPELINE_VERSION_FILTER=v2.3-direct-prospect-promote \
INTAKE_QWEN_RUN_SECONDS=300 \
scripts/intake_qwen_autocatalog_worker.sh
```

Finally re-check the direct-phone attach dry-run:

```sh
PYTHONPATH=apps/backend-rag python scripts/intake_reprocess_backlog.py \
  --auto-attach-direct-phone --auto-attach-limit 500
```

## Apply Auto-Attach To Kita

Do not pass `--apply` until the CRM/Kita writer endpoint and production flags are
verified for the deployed commit. The bulk script now runs this preflight
automatically before committing any auto-attach candidate:

```sh
PYTHONPATH=apps/backend-rag python scripts/intake_reprocess_backlog.py \
  --delivery-readiness-report
```

Expected readiness state before bulk apply:

- `crm_write_key_present=true`
- `intake_writer_enabled=true`
- `direct_phone_auto_attach_enabled=true` for the direct-phone bucket
- `preflight=accepted`

The worker runner imports only the scoped delivery allowlist from
`~/.wa-mirror.env` (`WA_MIRROR_CRM_WRITE_KEY`, optional
`INTAKE_CRM_PUSH_*`, optional `INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED`). It must
not source the whole file because that file is not shell-safe and contains
unrelated WA Mirror settings.

```sh
curl -sS -o /tmp/kita-preflight.json -w "%{http_code}\n" \
  -X POST https://nuzantara-rag.fly.dev/api/crm/internal/clients/1/documents/upload \
  -H "X-CRM-Write-Key: ${WA_MIRROR_CRM_WRITE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected safe result: `422` with a missing-field validation body. That means
HybridAuth let the request reach the service-write route and no file was written.

Blocked result: `401 {"detail":"Authentication required"}`. That means the
service-write upload route is not deployed/allowlisted yet, even if the same key
works for `/api/crm/clients/upsert-by-phone`. Do not apply auto-attach in that
state: it could commit locally without delivering the document to Kita.

Once the preflight returns `422`, start with a tiny applied batch:

```sh
INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED=1 \
INTAKE_WRITER_ENABLED=1 \
INTAKE_CRM_PUSH_ENABLED=1 \
PYTHONPATH=apps/backend-rag \
python scripts/intake_reprocess_backlog.py \
  --auto-attach-direct-phone --auto-attach-limit 5 --apply
```

Then verify aggregate delivery status from `intake_commit_audit` before scaling
the limit.
