"""GARUDA VOA -- the delivered artifact (W3A phase 2).

One immutable file, at most one live per practice: the deliverable Bali
Zero hands the customer at the end of a VOA practice (spec SS2,
`docs/plans/2026-09-11-garuda-voa-artifact-delivery-spec.md`).

Modules (S2a — the store ships first; the service, the repository and the
routers follow in their own PRs):
  - `models`       -- wire-independent dataclasses (`ArtifactRecord`).
  - `ports`        -- `Protocol`s a service will depend on (object store,
                      repository) and `MAX_ARTIFACT_BYTES`, so the concrete
                      adapters are swappable for `fakes.py` in tests without
                      any consumer importing a concrete module.
  - `tigris_store` -- the private, own-credentialed Tigris object store.
  - `fakes`        -- the in-memory object-store double. TEST-ONLY: never
                      imported by production wiring (`service_initializer.py`).
"""

from __future__ import annotations
