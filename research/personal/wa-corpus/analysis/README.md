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
