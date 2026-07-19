# Task 6 Report — Pro Editorial Publisher and Automatic Cadence

## Outcome

Implemented the local, deterministic publisher used to turn sanitized collector
projections into closed Magazine publication packets and deliver them through the
dual-authenticated machine ingress. No collector, deployment, or remote endpoint
was mutated during implementation or verification.

## Delivered

- Frozen, extra-forbidden Pydantic mirrors for collector, story, edition, claim,
  evidence, placement, AssetUploadV2 metadata, and AssetUploadV2 canonical response
  handoff. The Python fixtures round-trip to the same JSON shape as TypeScript.
- Deny-by-default adapters for Intel Lake, MATA GARUDA, Regulatory Watcher, and
  NotebookLM health/insight projections, plus an explicit extension registry.
  Denied nested fields are stripped before validation and every emitted string is
  checked for Indonesian PII, including claim and evidence text.
- Deterministic lineage/syndication collapse, evidence scoring, five-domain-first
  selection, quiet/partial morning editions, and per-claim Breaking qualification.
  Legal-effect claims require an official resolved primary source even when two
  journalistic roots are independent.
- One persistent asynchronous `httpx.AsyncClient` with byte-exact body hashing and
  HMAC headers. Asset source bytes are uploaded first; only the returned canonical
  PNG digest is handed to the edition packet factory.
- Append-only, fsynced outcome and audit ledgers with process locks. An ambiguous
  side effect is marked `outcome_unknown` and reconciled before any retry; an
  unresolved outcome blocks automatic retry.
- RFC 8785 audit event verification and byte-exact Ed25519 anchor receipts using
  the specified domain tags, U32/U64 lengths, unpadded base64url signatures, and
  chained anchor hashes. Any rewrite, gap, malformed ledger row, or checkpoint
  conflict fails closed and blocks release.
- `magazine-publish morning` and `magazine-publish breaking` CLI commands.
  Network publication is explicit through `--publish`; `--dry-run` remains fully
  deterministic. Structured logs contain packet/story IDs, counts, and states,
  never payload bodies or credentials.

## TDD Evidence

- Initial RED: 5 collection errors because `zantara_media.magazine` did not exist.
- Contract cycle: 8 passed.
- Adapter cycle: 8/9, then 9/9 after handling the default Notebook Insight shape;
  later RED/GREEN cycles added collector-run projection and nested claim PII denial.
- Ranking/composer cycle: 6 passed.
- Transport/reconciliation cycle: 5 passed.
- Audit-anchor cycle: 4 passed.
- CLI cycle: collection failed because `magazine_publish` did not exist, then 2 passed.

## Final Gates

From `apps/zantara-media` with its Python 3.11 `.venv` activated:

```text
python -m pytest tests/magazine tests/test_dlp.py -q
50 passed in 0.42s

ruff check zantara_media/magazine zantara_media/cli/magazine_publish.py tests/magazine
All checks passed!

python -m compileall -q zantara_media/magazine zantara_media/cli/magazine_publish.py
exit 0
```

Focused Magazine-only rerun before finalization:

```text
python -m pytest tests/magazine -q
36 passed
```

## Baseline Limitation

The complete legacy `tests/` baseline was attempted and stopped during collection
with three identical environment errors:

```text
ModuleNotFoundError: No module named 'openai'
```

Affected collectors were `tests/test_atomic.py`, `tests/test_dedup.py`, and
`tests/test_e2e_integration.py`, all through the pre-existing
`zantara_media/indexer/embedder.py` import. The Air-M5 task venv was intentionally
kept lightweight; installing the app's heavyweight media/ML dependency set on the
thin client would violate machine routing policy. The directly relevant legacy DLP
baseline passed all 14 tests.

## Dependencies

- `rfc8785>=0.1.4` for RFC 8785 JSON canonicalization.
- `cryptography>=42.0` for exact Ed25519 signing and verification.

Both are pure task dependencies and require no paid API key or external service.
