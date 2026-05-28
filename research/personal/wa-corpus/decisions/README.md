# WhatsApp Corpus Decisions

This directory contains Step 4 of the local WhatsApp corpus workflow: compiled
allow/deny/hold decisions.

## Privacy Contract

- Tracked Markdown files must not contain raw message text.
- Tracked Markdown files must not contain message snippets.
- Tracked Markdown files must not contain phone numbers.
- Tracked Markdown files must not contain raw source paths.
- Tracked Markdown files must not contain raw contact names.
- Files ending in `.local.tsv`, `.local.csv`, `.local.jsonl`, or `.private.*`
  are ignored because they may contain raw local paths.

## Compile Decisions

Run from repo root with the repo virtualenv active:

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

Only the summary is tracked. The local files may contain raw paths and must stay
on the Pro.

## Safe Defaults

With `--apply-safe-defaults`:

- `team_operator_archive_candidate` rows gated as local team analysis become
  `allow_team_local`.
- private-drive rows become `deny_personal`.
- all other blank decisions become `unknown_hold`.

The next parser/indexer must read only `content_allowlist.local.jsonl`.
