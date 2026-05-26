# WhatsApp Corpus Registry

Local-only utilities for the 2026-05-26 WhatsApp corpus archive.

## Privacy Contract

- Do not call cloud LLMs.
- Do not output raw message text.
- Do not output message snippets.
- Do not output phone numbers.
- Do not output raw source paths in shareable reports.
- Use `file_id` and `path_hash` for per-file references.

## Build Registry

Run from repo root with the repo virtualenv active:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_registry \
  --root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --output-dir research/personal/wa-corpus/registry \
  --target-total 105530
```

Outputs:

- `research/personal/wa-corpus/registry/registry.sqlite`
- `research/personal/wa-corpus/registry/registry_summary.md`

The SQLite registry stores metadata only: source bucket, hashed ZIP source tag,
parser type, file hash, path hash, line count, message-start count, timestamp
min/max, and parser warning codes. It intentionally avoids raw message bodies
and raw paths.

The registry keeps two export counts:

- `message_start_count`: baseline count that preserves the original 105k brief
  rule.
- `normalized_message_start_count`: diagnostic count that also accepts invisible
  Unicode-prefixed WhatsApp timestamp lines.

## Classify Chats

Run the privacy gate classifier after the registry exists:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.classify_chats \
  --registry-db research/personal/wa-corpus/registry/registry.sqlite \
  --output-dir research/personal/wa-corpus/classification
```

Outputs:

- `research/personal/wa-corpus/classification/chat_classification.sqlite`
- `research/personal/wa-corpus/classification/classification_summary.md`

The classifier is deterministic and metadata-only. It does not inspect message
bodies. It uses source buckets, hashed ZIP source tags, message counts, parser
warnings, and normalized count deltas to assign each file to a conservative
processing gate:

- `deny_content_mining_until_owner_allowlist`
- `local_only_team_analysis_after_owner_approval`
- `manual_review_before_content_mining`
- `manual_review_before_any_use`

All categories are pre-flight safety labels. They are not semantic claims about
the conversation contents.

## Resolve Review References Locally

Shareable reports intentionally expose only `file_id`, `path_hash`, and hashed
`source_tag`. To review a file on the Pro, resolve a specific reference in the
terminal:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.resolve_refs \
  --root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --file-id wa-file-0421
```

This command prints raw local paths, so do not redirect its output into tracked
repo files.

## Build Owner Review Manifest

Generate a private manifest for owner decisions before any content mining:

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

The `.local.tsv` file contains raw local paths and is ignored by git. Use its
blank `owner_decision` column to create the next allowlist/denylist:

- `allow_team_local`
- `allow_business_local`
- `deny_personal`
- `deny_sensitive`
- `unknown_hold`

## Compile Allow/Deny/Hold Decisions

Compile the private review manifest into local-only lists:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.compile_review_decisions \
  --review-manifest research/personal/wa-corpus/review/review_manifest.local.tsv \
  --output-dir research/personal/wa-corpus/decisions \
  --apply-safe-defaults
```

Outputs:

- `research/personal/wa-corpus/decisions/review_decisions.local.tsv`
- `research/personal/wa-corpus/decisions/content_allowlist.local.jsonl`
- `research/personal/wa-corpus/decisions/content_denylist.local.jsonl`
- `research/personal/wa-corpus/decisions/content_holdlist.local.jsonl`
- `research/personal/wa-corpus/decisions/review_decisions_summary.md`

Only `content_allowlist.local.jsonl` may feed the next local parser/indexer.
Never parse files from the denylist or holdlist.

## Parse Allowed Messages

Parse only the allowlist into an ignored local SQLite database:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.parse_allowed_messages \
  --allowlist research/personal/wa-corpus/decisions/content_allowlist.local.jsonl \
  --output-dir research/personal/wa-corpus/analysis
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_messages.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_messages_summary.md`

The SQLite file stores raw parsed message text and raw sender labels. It is
ignored by git and must stay on the Pro.

## Review Case Windows and Compile Local Actions

After domain events and case windows exist, build the owner review workbook for
the top operational windows:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_case_window_manual_review
```

Outputs:

- `research/personal/wa-corpus/review/case_window_review_workbook.local.tsv`
- `research/personal/wa-corpus/review/case_window_context.local.tsv`
- `research/personal/wa-corpus/review/case_window_manual_review_summary.md`

The workbook and context TSV are local-only and ignored by git. The context TSV
contains redacted previews for owner review; the tracked summary contains only
aggregate counts.

After setting `owner_decision=approve` on selected workbook rows, compile only
approved rows into a local CRM/ops queue:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.compile_case_window_actions
```

Outputs:

- `research/personal/wa-corpus/actions/case_window_actions.local.tsv`
- `research/personal/wa-corpus/actions/case_window_actions_summary.md`

Rows left blank, held, denied, duplicated, or marked `no_action` do not become
actions.

## Full Cleartext Local Corpus

When the owner explicitly authorizes full local processing, parse every readable
TXT chat into an ignored cleartext SQLite database:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.parse_full_corpus
```

Outputs:

- `research/personal/wa-corpus/full/full_messages.local.sqlite`
- `research/personal/wa-corpus/full/full_corpus_parse_summary.md`

The SQLite database contains raw message text and is ignored by git. It also
contains an FTS5 index for local cleartext search.

Set aside only explicit spicy/intimate conversation candidates:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.quarantine_spicy_conversations
```

Outputs:

- `research/personal/wa-corpus/full/spicy_quarantine.local.sqlite`
- `research/personal/wa-corpus/full/spicy_quarantine.local.tsv`
- `research/personal/wa-corpus/full/usable_after_spicy_quarantine.local.tsv`
- `research/personal/wa-corpus/full/spicy_quarantine_summary.md`

Mine business and memory value signals only from the usable file list:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.mine_full_gold_signals
```

Outputs:

- `research/personal/wa-corpus/full/full_gold_signals.local.sqlite`
- `research/personal/wa-corpus/full/full_gold_signals_summary.md`
- `research/personal/wa-corpus/full/full_corpus_gold_research.md`

## Analyze Allowed Temporal Metrics

Build aggregate temporal metrics from the ignored parsed-message DB:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.analyze_allowed_temporal \
  --input-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_temporal.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_temporal_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_temporal.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_temporal_summary.md`

The temporal analyzer reads only aggregate-safe columns and denies accidental
reads from `body_text`, `sender_raw`, and `local_path`.

## Analyze Allowed Signals

Run deterministic aggregate signal analysis over the ignored parsed-message DB:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.analyze_allowed_signals \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --output-dir research/personal/wa-corpus/analysis
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_signal_hits.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_signal_summary.md`

The signal report is aggregate-only. Signal codes are routing hints for the
next local extractor, not legal or client-level conclusions.

## Extract Allowed Candidates

Extract hashed structured candidates from the ignored parsed-message DB:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.extract_allowed_candidates \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --output-dir research/personal/wa-corpus/analysis
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_candidates.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_candidates_summary.md`

The candidate SQLite stores hashed body/value references only. It is still
ignored by git because hashes are local review aids, not publishable evidence.

## Extract Document Requirements

Extract aggregate document-requirement signals from the ignored parsed-message
DB and the ignored hashed-candidate DB:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.extract_document_requirements \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --candidates-db research/personal/wa-corpus/analysis/allowed_candidates.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_document_requirements.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_document_requirements_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_document_requirements.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_document_requirements_summary.md`

The tracked summary is aggregate-only. The ignored SQLite stores hashes,
message indexes, timestamps, category codes, evidence codes, and counters; it
does not store raw message text or raw extracted document values.

## Analyze Immigration Lifecycle

Build aggregate immigration lifecycle stages from the ignored local message,
candidate, and signal databases:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.analyze_immigration_lifecycle \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --candidates-db research/personal/wa-corpus/analysis/allowed_candidates.local.sqlite \
  --signal-db research/personal/wa-corpus/analysis/allowed_signal_hits.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_immigration_lifecycle.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_immigration_lifecycle_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_immigration_lifecycle.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_immigration_lifecycle_summary.md`

The lifecycle analyzer classifies aggregate message-level stages such as
`lead_intake`, `identity_passport`, `sponsor_company`,
`application_submission`, `appointment_biometric`, `approval_issuance`,
`extension_renewal_expiry`, and `problem_escalation`. The tracked summary
contains aggregate counts only.

## Extract Tax/Payment Signals

Extract aggregate tax, invoice, reporting, payment, and amount-reference
signals from ignored local databases:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.extract_tax_payment_signals \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --candidates-db research/personal/wa-corpus/analysis/allowed_candidates.local.sqlite \
  --signals-db research/personal/wa-corpus/analysis/allowed_signal_hits.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_tax_payment.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_tax_payment_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_tax_payment.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_tax_payment_summary.md`

The ignored SQLite stores only local identifiers, hashes, category codes,
timestamps, and counters. The tracked summary contains aggregate counts only.

## Build Follow-Up Risk Queue

Build aggregate local follow-up/risk queue signals:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_followup_risk_queue \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --signal-db research/personal/wa-corpus/analysis/allowed_signal_hits.local.sqlite \
  --temporal-db research/personal/wa-corpus/analysis/allowed_temporal.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_followup_risk.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_followup_risk_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_followup_risk.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_followup_risk_summary.md`

The queue is heuristic and local-only. Use it as an anonymous review queue, not
as a client-facing or legal conclusion.

## Build Domain Event Index

Normalize the derived domain extractor outputs into one ignored local event
table:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_domain_event_index \
  --document-db research/personal/wa-corpus/analysis/allowed_document_requirements.local.sqlite \
  --lifecycle-db research/personal/wa-corpus/analysis/allowed_immigration_lifecycle.local.sqlite \
  --tax-db research/personal/wa-corpus/analysis/allowed_tax_payment.local.sqlite \
  --followup-db research/personal/wa-corpus/analysis/allowed_followup_risk.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_domain_events.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_domain_events_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_domain_events.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_domain_events_summary.md`

The event index reads only derived extractor DBs. It does not read the raw
parsed-message DB and its tracked summary contains only aggregate event counts.

## Analyze Document/Lifecycle Gaps

Build aggregate coverage matrices between immigration lifecycle stages and
document requirement events:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.analyze_document_lifecycle_gaps \
  --events-db research/personal/wa-corpus/analysis/allowed_domain_events.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_document_lifecycle_gaps.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_document_lifecycle_gaps_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_document_lifecycle_gaps.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_document_lifecycle_gaps_summary.md`

This analyzer reads only the derived domain event index and reports aggregate
coverage/gap counts. A gap means no same-message document event was detected; it
does not prove a missing client document.

## Build Case Windows

Group the derived domain events into anonymous local case windows:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_case_windows \
  --events-db research/personal/wa-corpus/analysis/allowed_domain_events.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_case_windows.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_case_windows_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_case_windows.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_case_windows_summary.md`

The case windows are anonymous local review units. They are built from the
derived domain event index, not from the raw parsed-message DB.

## Build Case Window Review Queue

Build an anonymous local review queue from dense or high-risk case windows:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_case_window_review_queue \
  --input-db research/personal/wa-corpus/analysis/allowed_case_windows.local.sqlite \
  --output-tsv research/personal/wa-corpus/analysis/allowed_case_window_review.local.tsv \
  --summary research/personal/wa-corpus/analysis/allowed_case_window_review_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_case_window_review.local.tsv`
- `research/personal/wa-corpus/analysis/allowed_case_window_review_summary.md`

The TSV stays local-only and ignored by git. The tracked summary keeps only
aggregate counts and queue reason frequencies.

## Analyze Signal Matrix

Build aggregate matrices from signal hits:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.analyze_allowed_signal_matrix \
  --input research/personal/wa-corpus/analysis/allowed_signal_hits.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_signal_matrix.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_signal_matrix_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_signal_matrix.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_signal_matrix_summary.md`

The matrix reads only `signal_hits` fields, never raw message text.

## Build Analysis Inventory

Build a run checklist of local analysis artifacts:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_analysis_inventory \
  --analysis-dir research/personal/wa-corpus/analysis \
  --summary research/personal/wa-corpus/analysis/analysis_inventory_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/analysis_inventory_summary.md`

The inventory inspects only local SQLite table names, table row counts, summary
titles, and line counts. It does not select raw message text, sender labels, or
local paths.

## Privacy Audit

Run the report privacy audit before committing generated WhatsApp reports:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.audit_privacy_outputs
```

The audit scans tracked files under `research/personal/wa-corpus/`, skips local
and database artifacts, and prints only `repo/path<TAB>pattern_label` findings.

Use `--include-untracked` when you want to scan local scratch reports before
sharing them:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.audit_privacy_outputs --include-untracked
```
