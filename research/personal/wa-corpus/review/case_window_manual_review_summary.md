# WhatsApp Case Window Manual Review

Generated UTC: `2026-05-26T17:36:21+00:00`
Private workbook: `research/personal/wa-corpus/review/case_window_review_workbook.local.tsv`
Private context TSV: `research/personal/wa-corpus/review/case_window_context.local.tsv`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers or emails.
- This tracked summary contains no raw source paths or extracted values.
- The private `.local.tsv` workbook and context files are ignored by git.
- Context previews mask direct identifiers and still stay local-only.

## Counts

| Metric                   | Value |
| ------------------------ | ----: |
| Review windows           |   100 |
| Window messages          |  6850 |
| Window events            | 30022 |
| High-severity event refs |  2732 |
| Context rows             | 11433 |
| Preserved owner rows     |     0 |

## Context Scopes

| Scope  |  Rows |
| ------ | ----: |
| window | 11053 |
| after  |   194 |
| before |   186 |

## Dominant Domains

| Domain                | Windows |
| --------------------- | ------: |
| immigration_lifecycle |      76 |
| followup_risk         |      23 |
| document_requirement  |       1 |

## Owner Decision Values

| Value     | Meaning                         |
| --------- | ------------------------------- |
| approve   | Queue a local CRM/ops action.   |
| hold      | Keep for later review.          |
| deny      | Exclude from action generation. |
| duplicate | Exclude as duplicated context.  |
| no_action | Reviewed, no action required.   |

## Action Types

| Type                     | Use                                         |
| ------------------------ | ------------------------------------------- |
| crm_followup             | Follow-up or status check.                  |
| document_chase           | Missing or pending document chase.          |
| deadline_check           | Date or deadline validation.                |
| immigration_status_check | Visa or immigration status check.           |
| payment_reconcile        | Invoice, transfer, or proof reconciliation. |
| case_note                | Add an internal case note only.             |
| kb_extract               | Extract reusable internal knowledge.        |
| team_escalation          | Internal escalation for owner/team review.  |

## Next Command

After filling `owner_decision=approve` on selected rows, run:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.compile_case_window_actions
```
