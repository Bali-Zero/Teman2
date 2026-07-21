# @nuzantara/design-system — DEPRECATED

**DEPRECATED 2026-07-21 — tokens merged into `packages/core/tokens/operative.css` (WS1). Do not consume; `brand-api/` subdir remains active.**

The former `tokens/bz-tokens.css` now lives in `@balizero/core` as the single
token SSOT, imported from `packages/core/tokens/index.css` after
`semantic.css` and before the theme files. All `--bz-*` names and values were
preserved unchanged. New work must import tokens from `@balizero/core`, never
from this package.
