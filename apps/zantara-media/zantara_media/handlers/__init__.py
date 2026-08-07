"""Media extraction helpers shared across zantara-media.

`image_handler` lived under `indexer/handlers/` until the GARUDA indexer was
decommissioned (2026-08-07). It is kept here because the magazine's
`media_resolver` uses `extract_image` as its default describer — it never
depended on the indexer, only on stdlib and httpx.
"""
