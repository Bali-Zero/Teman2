"""`GarudaArtifactService` unit tests, over the in-memory fakes -- no
Postgres, no Tigris. The migration's own constraints (partial unique index,
digest CHECK, guard trigger) are exercised separately against a real
Postgres in `tests/db/test_migration_312_garuda_practice_artifacts.py`;
this file is the service ORCHESTRATION layer (spec SS5's put/serve/resolve
logic) in isolation.
"""

from __future__ import annotations

import hashlib
import logging
import re

import pytest

from backend.services.garuda_artifacts.fakes import (
    InMemoryArtifactObjectStore,
    InMemoryArtifactRepository,
)
from backend.services.garuda_artifacts.service import (
    MAX_ARTIFACT_BYTES,
    ArtifactDeliveryRejected,
    ArtifactTooLarge,
    GarudaArtifactService,
    InvalidArtifactContent,
)

_ARTIFACT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
#: Contract's DeliverPracticeTransition.artifact_digest pattern (spec fact 17
#: / SS5) -- lowercase-hex sha256, 64 chars.
_ARTIFACT_DIGEST_PATTERN = re.compile(r"^[a-f0-9]{64}$")

_SYNTHETIC_PDF = b"%PDF-1.4\n%synthetic-test-fixture-no-real-document\n%%EOF"


def _service() -> tuple[GarudaArtifactService, InMemoryArtifactRepository, InMemoryArtifactObjectStore]:
    repo = InMemoryArtifactRepository()
    store = InMemoryArtifactObjectStore()
    service = GarudaArtifactService(repository=repo, object_store=store, environment="TEST")
    return service, repo, store


class TestPutPracticeArtifact:
    @pytest.mark.asyncio
    async def test_happy_path_generates_id_and_digest_matching_contract_shapes(self) -> None:
        service, _repo, store = _service()
        record = await service.put_practice_artifact(
            conn=None, practice_id="prc_test0000000000001", body=_SYNTHETIC_PDF, produced_by="staff@balizero.com"
        )
        assert _ARTIFACT_ID_PATTERN.match(record.artifact_id)
        assert _ARTIFACT_DIGEST_PATTERN.match(record.artifact_digest)
        assert record.artifact_digest == hashlib.sha256(_SYNTHETIC_PDF).hexdigest()
        assert record.byte_length == len(_SYNTHETIC_PDF)
        assert record.content_type == "application/pdf"
        assert record.is_live
        # Object THEN row (spec SS3): the bytes must already be in the
        # store under the row's own storage_key.
        stored = await store.fetch_and_verify(
            key=record.storage_key, expected_digest=record.artifact_digest
        )
        assert stored == _SYNTHETIC_PDF

    @pytest.mark.asyncio
    async def test_non_pdf_body_is_rejected_before_any_write(self) -> None:
        service, _repo, store = _service()
        with pytest.raises(InvalidArtifactContent):
            await service.put_practice_artifact(
                conn=None, practice_id="prc_test0000000000002", body=b"not a pdf at all", produced_by="staff@balizero.com"
            )
        assert store._objects == {}  # nothing was ever uploaded

    @pytest.mark.asyncio
    async def test_over_ceiling_body_is_rejected(self) -> None:
        service, _repo, store = _service()
        oversized = b"%PDF-1.4\n" + b"\x00" * MAX_ARTIFACT_BYTES
        with pytest.raises(ArtifactTooLarge):
            await service.put_practice_artifact(
                conn=None, practice_id="prc_test0000000000003", body=oversized, produced_by="staff@balizero.com"
            )
        assert store._objects == {}

    @pytest.mark.asyncio
    async def test_second_put_while_a_live_artifact_exists_supersedes_it(self) -> None:
        """Decision #13-revision ("always supersede, never 409, made
        observable"): a second put no longer raises `ArtifactAlreadyExists`
        -- it replaces the live artifact and leaves the old row marked."""
        service, repo, _store = _service()
        practice_id = "prc_test0000000000004"
        first = await service.put_practice_artifact(
            conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff@balizero.com"
        )
        second = await service.put_practice_artifact(
            conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff2@balizero.com"
        )
        assert second.artifact_id != first.artifact_id
        assert second.is_live
        old = repo._by_id[first.artifact_id]
        assert not old.is_live
        assert old.superseded_by == second.artifact_id
        live = await repo.get_live_for_practice(None, practice_id=practice_id)
        assert live is not None
        assert live.artifact_id == second.artifact_id

    @pytest.mark.asyncio
    async def test_put_after_supersession_succeeds(self) -> None:
        """The partial unique index is scoped to LIVE rows -- once the only
        row is superseded, a fresh put is not blocked by history."""
        service, repo, _store = _service()
        practice_id = "prc_test0000000000005"
        first = await service.put_practice_artifact(
            conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff@balizero.com"
        )
        repo.supersede_for_test(first.artifact_id)
        second = await service.put_practice_artifact(
            conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff2@balizero.com"
        )
        assert second.artifact_id != first.artifact_id
        assert second.storage_key != first.storage_key

    @pytest.mark.asyncio
    async def test_non_conflict_insert_failure_leaves_an_orphan_object_and_logs_a_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Object-then-row (spec SS3): a row-insert failure that is NOT
        `ArtifactAlreadyExists` (a generic DB error here) must still
        propagate to the caller, but the service should log a warning
        naming the orphaned key's existence -- practice_id/artifact_id
        only, never the body, an email, or a credential."""

        class _FailingRepository(InMemoryArtifactRepository):
            async def insert(self, conn, **kwargs):
                raise RuntimeError("simulated connection drop")

        repo = _FailingRepository()
        store = InMemoryArtifactObjectStore()
        service = GarudaArtifactService(repository=repo, object_store=store, environment="TEST")
        practice_id = "prc_test0000000000014"
        with caplog.at_level(logging.WARNING, logger="backend.services.garuda_artifacts.service"):
            with pytest.raises(RuntimeError):
                await service.put_practice_artifact(
                    conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff@balizero.com"
                )
        # The object was already written before the failed insert -- an
        # orphan, exactly as this phase accepts (no delete member).
        assert len(store._objects) == 1
        [record] = caplog.records
        assert record.levelno == logging.WARNING
        assert practice_id in record.practice_id
        assert "staff@balizero.com" not in caplog.text
        assert "%PDF" not in caplog.text


class TestGetStaffPracticeArtifact:
    @pytest.mark.asyncio
    async def test_fetch_verify_emit_returns_verified_bytes(self) -> None:
        service, _repo, _store = _service()
        practice_id = "prc_test0000000000006"
        put_record = await service.put_practice_artifact(
            conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff@balizero.com"
        )
        record, body = await service.get_staff_practice_artifact(conn=None, practice_id=practice_id)
        assert record.artifact_id == put_record.artifact_id
        assert body == _SYNTHETIC_PDF

    @pytest.mark.asyncio
    async def test_no_live_artifact_raises_lookup_error(self) -> None:
        service, _repo, _store = _service()
        with pytest.raises(LookupError):
            await service.get_staff_practice_artifact(conn=None, practice_id="prc_nosuchpractice00001")

    @pytest.mark.asyncio
    async def test_digest_mismatch_raises_before_returning_any_bytes(self) -> None:
        """The digest-mismatch case must never leak partial/unverified
        bytes to the caller (spec SS5's fetch-verify-emit ordering) --
        asserted here at the service layer; the router-level test asserts
        the same at the HTTP layer (zero body bytes on the wire)."""
        service, _repo, store = _service()
        practice_id = "prc_test0000000000007"
        record = await service.put_practice_artifact(
            conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff@balizero.com"
        )
        store.corrupt(record.storage_key)
        from backend.services.garuda_artifacts.ports import ArtifactDigestMismatch

        with pytest.raises(ArtifactDigestMismatch):
            await service.get_staff_practice_artifact(conn=None, practice_id=practice_id)

    @pytest.mark.asyncio
    async def test_missing_object_raises_before_returning_any_bytes(self) -> None:
        service, _repo, store = _service()
        practice_id = "prc_test0000000000008"
        record = await service.put_practice_artifact(
            conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff@balizero.com"
        )
        store.delete_for_test(record.storage_key)
        from backend.services.garuda_artifacts.ports import ArtifactObjectMissing

        with pytest.raises(ArtifactObjectMissing):
            await service.get_staff_practice_artifact(conn=None, practice_id=practice_id)


class TestResolveForDelivery:
    @pytest.mark.asyncio
    async def test_matching_pair_resolves(self) -> None:
        service, _repo, _store = _service()
        practice_id = "prc_test0000000000009"
        put_record = await service.put_practice_artifact(
            conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff@balizero.com"
        )
        resolved = await service.resolve_for_delivery(
            conn=None,
            practice_id=practice_id,
            artifact_id=put_record.artifact_id,
            artifact_digest=put_record.artifact_digest,
        )
        assert resolved.artifact_id == put_record.artifact_id

    @pytest.mark.asyncio
    async def test_fabricated_artifact_id_is_rejected(self) -> None:
        """The exact PENDING-ARMS row 1847 case: a fabricated
        (artifact_id, artifact_digest) pair must never resolve."""
        service, _repo, _store = _service()
        practice_id = "prc_test0000000000010"
        await service.put_practice_artifact(
            conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff@balizero.com"
        )
        with pytest.raises(ArtifactDeliveryRejected):
            await service.resolve_for_delivery(
                conn=None,
                practice_id=practice_id,
                artifact_id="artifact_id_0000000000001",
                artifact_digest="a" * 64,
            )

    @pytest.mark.asyncio
    async def test_digest_matching_row_but_wrong_id_is_rejected(self) -> None:
        service, _repo, _store = _service()
        practice_id = "prc_test0000000000011"
        put_record = await service.put_practice_artifact(
            conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff@balizero.com"
        )
        with pytest.raises(ArtifactDeliveryRejected):
            await service.resolve_for_delivery(
                conn=None,
                practice_id=practice_id,
                artifact_id="a_completely_different_id_00001",
                artifact_digest=put_record.artifact_digest,
            )

    @pytest.mark.asyncio
    async def test_no_live_artifact_at_all_is_rejected(self) -> None:
        service, _repo, _store = _service()
        with pytest.raises(ArtifactDeliveryRejected):
            await service.resolve_for_delivery(
                conn=None,
                practice_id="prc_nosuchpractice00002",
                artifact_id="artifact_id_0000000000001",
                artifact_digest="a" * 64,
            )

    @pytest.mark.asyncio
    async def test_superseded_artifact_is_rejected_even_with_the_right_pair(self) -> None:
        service, repo, _store = _service()
        practice_id = "prc_test0000000000012"
        put_record = await service.put_practice_artifact(
            conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff@balizero.com"
        )
        repo.supersede_for_test(put_record.artifact_id)
        with pytest.raises(ArtifactDeliveryRejected):
            await service.resolve_for_delivery(
                conn=None,
                practice_id=practice_id,
                artifact_id=put_record.artifact_id,
                artifact_digest=put_record.artifact_digest,
            )

    @pytest.mark.asyncio
    async def test_object_missing_at_resolve_time_is_rejected(self) -> None:
        """The row says one thing, the bucket says another -- spec SS5 step
        3 ("confirms the stored object exists and its digest matches the
        row") catches this even though the (artifact_id, artifact_digest)
        pair itself is genuine."""
        service, _repo, store = _service()
        practice_id = "prc_test0000000000013"
        put_record = await service.put_practice_artifact(
            conn=None, practice_id=practice_id, body=_SYNTHETIC_PDF, produced_by="staff@balizero.com"
        )
        store.delete_for_test(put_record.storage_key)
        with pytest.raises(ArtifactDeliveryRejected):
            await service.resolve_for_delivery(
                conn=None,
                practice_id=practice_id,
                artifact_id=put_record.artifact_id,
                artifact_digest=put_record.artifact_digest,
            )
