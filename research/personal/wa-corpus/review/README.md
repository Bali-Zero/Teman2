# WhatsApp Corpus Review

This directory contains Step 3 of the local WhatsApp corpus workflow: owner
review manifests.

## Privacy Contract

- Tracked Markdown files must not contain raw message text.
- Tracked Markdown files must not contain message snippets.
- Tracked Markdown files must not contain phone numbers.
- Tracked Markdown files must not contain raw source paths.
- Tracked Markdown files must not contain raw contact names.
- Files ending in `.local.tsv`, `.local.csv`, `.local.jsonl`, or `.private.*`
  are ignored because they may contain raw local paths.

## Generate Review Manifest

Run from repo root with the repo virtualenv active:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_review_manifest \
  --root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --classification-db research/personal/wa-corpus/classification/chat_classification.sqlite \
  --output-dir research/personal/wa-corpus/review \
  --limit 80
```

Outputs:

- `research/personal/wa-corpus/review/review_manifest.local.tsv`
- `research/personal/wa-corpus/review/review_manifest_summary.md`

The `.local.tsv` file is for private owner review on the Pro. It contains local
paths and blank decision columns. Do not copy it into prompts, reports, commits,
tickets, cloud docs, or chats.

## Decision Values

Use these values in the private manifest `owner_decision` column:

- `allow_team_local`
- `allow_business_local`
- `deny_personal`
- `deny_sensitive`
- `unknown_hold`

## Compile Decisions

After review, compile decisions into allow/deny/hold lists:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.compile_review_decisions \
  --review-manifest research/personal/wa-corpus/review/review_manifest.local.tsv \
  --output-dir research/personal/wa-corpus/decisions \
  --apply-safe-defaults
```

With safe defaults, only team-gated rows are allowed. Private-drive rows are
denied, and all remaining blank manual-review rows stay on hold.

## Case Window Manual Review

The case-window queue is a second-stage review over already allowlisted local
messages. It is for operational triage only: dense windows may become local
CRM/ops actions after owner approval.

Generate the editable workbook and redacted local context:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_case_window_manual_review
```

Outputs:

- `research/personal/wa-corpus/review/case_window_review_workbook.local.tsv`
- `research/personal/wa-corpus/review/case_window_context.local.tsv`
- `research/personal/wa-corpus/review/case_window_manual_review_summary.md`

The workbook is private and ignored by git. Fill `owner_decision` only after
checking the local context. Supported values:

- `approve`
- `hold`
- `deny`
- `duplicate`
- `no_action`

When `owner_decision=approve`, set `action_type` if the inferred default is not
good enough:

- `crm_followup`
- `document_chase`
- `deadline_check`
- `immigration_status_check`
- `payment_reconcile`
- `case_note`
- `kb_extract`
- `team_escalation`

Compile only approved rows into the local ops queue:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.compile_case_window_actions
```

Outputs:

- `research/personal/wa-corpus/actions/case_window_actions.local.tsv`
- `research/personal/wa-corpus/actions/case_window_actions_summary.md`

The action queue is still local-only. Validate each row before copying anything
into CRM or team workflows.
