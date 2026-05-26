# WhatsApp Corpus Analysis

This directory contains allowlist-only local parsing and aggregate analysis.

## Privacy Contract

- Tracked Markdown files must not contain raw message text.
- Tracked Markdown files must not contain message snippets.
- Tracked Markdown files must not contain phone numbers.
- Tracked Markdown files must not contain raw source paths.
- Tracked Markdown files must not contain raw contact names.
- Files ending in `.local.sqlite`, `.local.db`, `.local.jsonl`, or `.private.*`
  are ignored because they may contain raw parsed messages or raw local paths.

## Parse Allowlist

Run from repo root with the repo virtualenv active:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.parse_allowed_messages \
  --allowlist research/personal/wa-corpus/decisions/content_allowlist.local.jsonl \
  --output-dir research/personal/wa-corpus/analysis
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_messages.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_messages_summary.md`

Only the summary is tracked. The local SQLite stores raw parsed message text and
raw sender labels, so it must stay on the Pro.

## Analyze Temporal Metrics

Build aggregate temporal metrics from the ignored parsed-message SQLite:

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

The temporal analyzer reads only safe aggregate columns and blocks accidental
reads from raw body, sender, and local path columns.

## Analyze Aggregate Signals

Run deterministic signal analysis over the ignored parsed-message SQLite:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.analyze_allowed_signals \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --output-dir research/personal/wa-corpus/analysis
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_signal_hits.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_signal_summary.md`

The signal SQLite stores no raw body text, but it is still ignored by git. Treat
signal codes as routing hints, not legal or client-level conclusions.

## Extract Structured Candidates

Run hashed candidate extraction over the ignored parsed-message SQLite:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.extract_allowed_candidates \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --output-dir research/personal/wa-corpus/analysis
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_candidates.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_candidates_summary.md`

The candidate SQLite stores only category codes, evidence codes, body hashes,
and extracted value hashes. Do not treat hashed candidates as client-level facts
until a local owner review resolves them.

## Analyze Signal Matrix

Build aggregate signal matrices from the ignored signal-hit SQLite:

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

The matrix uses only `file_id`, hashed `source_tag`, `message_index`,
`timestamp`, and `signal_code`.
