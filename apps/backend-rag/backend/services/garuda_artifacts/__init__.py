"""GARUDA VOA -- the delivered artifact (W3A phase 2).

One immutable file, at most one live per practice: the deliverable Bali
Zero hands the customer at the end of a VOA practice (spec SS2,
`docs/plans/2026-09-11-garuda-voa-artifact-delivery-spec.md`).

Modules:
  - `models`      -- wire-independent dataclasses (`ArtifactRecord`).
  - `ports`       -- `Protocol`s the service depends on (object store,
                     repository), so `postgres_repository.py` /
                     `tigris_store.py` are swappable for `fakes.py` in tests
                     without the service importing either concrete module.
  - `service`     -- `GarudaArtifactService`: put/get/resolve-for-delivery.
  - `postgres_repository` -- the one real `garuda_practice_artifacts` writer/reader.
  - `tigris_store`        -- the private, own-credentialed Tigris object store.
  - `fakes`               -- in-memory test doubles. TEST-ONLY: never imported
                             by production wiring (`service_initializer.py`).
"""

from __future__ import annotations
