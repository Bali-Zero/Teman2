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
ssh pro 'bash -lc "cd /Users/nuzantara/Desktop/nuzantara && INTAKE_QWEN_RUN_SECONDS=180 scripts/intake_qwen_autocatalog_worker.sh"'
```

From the Pro:

```sh
cd /Users/nuzantara/Desktop/nuzantara
INTAKE_QWEN_RUN_SECONDS=180 scripts/intake_qwen_autocatalog_worker.sh
```

For a long-lived tmux lane on the Pro:

```sh
tmux new -s wa-qwen-autocatalog 'cd /Users/nuzantara/Desktop/nuzantara && scripts/intake_qwen_autocatalog_worker.sh'
```

## Verify Aggregate Progress

Use aggregate counts only; do not print raw paths, phones, OCR, or client names.

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

Do not pass `--apply` until the CRM/Kita writer endpoint and production flags are
verified for the deployed commit.
