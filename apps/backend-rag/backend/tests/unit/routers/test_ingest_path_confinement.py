"""Corpus for the ingestion root-confinement guard (py/path-injection, ingestion half).

Guilt AND innocence for every guarded entry point, plus the two traps the previous
path-injection PR walked into:

* **Vacuous guilt.** An assertion that "nothing escaped" passes trivially when the escape
  it names is not the escape the code would perform. Every guilt case here first proves
  the escape is REAL — the glob genuinely matches the outside file, the symlink genuinely
  resolves outside — and only then asserts it is refused.
* **Dual-world settings.** `backend/tests/unit/routers/conftest.py` installs a fake
  `backend.app.core.config` only when the real one is not imported yet, so `settings` is a
  MagicMock when this file runs alone and a real `Settings` when it runs under
  `pytest backend/tests/`. These tests therefore drive the allow-list through the
  `INGEST_ALLOWED_ROOTS` env var, which behaves identically in both worlds.
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import backend.app.routers.ingest as ingest_mod
import backend.app.routers.legal_ingest as legal_mod
from backend.app.utils.ingest_paths import (
    ALLOWED_ROOTS_ENV,
    allowed_ingest_roots,
    resolve_ingest_path,
)

ADMIN = {"email": "zero@balizero.com", "role": "admin"}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """An allowed root with a legit file, and a secret sitting OUTSIDE it."""
    root = tmp_path / "allowed"
    root.mkdir()
    (root / "book.pdf").write_bytes(b"%PDF-legit")
    (tmp_path / "secret.pdf").write_bytes(b"%PDF-secret")
    monkeypatch.setenv(ALLOWED_ROOTS_ENV, str(root))
    return root


# --------------------------------------------------------------------------- wiring


def test_both_routers_bind_the_same_validator():
    """A guard imported under a different name in each module is two guards."""
    assert ingest_mod.resolve_ingest_path is resolve_ingest_path
    assert legal_mod.resolve_ingest_path is resolve_ingest_path


def test_env_override_replaces_the_defaults(sandbox):
    assert allowed_ingest_roots() == (sandbox.resolve(),)


def test_defaults_hold_with_no_override_in_either_settings_world(monkeypatch):
    """Without the env var the allow-list must still be usable.

    This is the only case that exercises `_settings_roots()`, and it has to pass whether
    `settings` is the conftest MagicMock (attributes are Mocks, skipped by the isinstance
    check) or a real `Settings` (attributes are strings, added to the list). In both
    worlds the hardcoded data dirs must survive, or ingestion breaks on a deployment that
    never set INGEST_ALLOWED_ROOTS.
    """
    monkeypatch.delenv(ALLOWED_ROOTS_ENV, raising=False)
    roots = allowed_ingest_roots()
    assert Path("./data/raw_books").resolve() in roots
    assert Path("./data/temp").resolve() in roots
    assert all(isinstance(root, Path) and root.is_absolute() for root in roots)


# ------------------------------------------------------------------- helper: guilt


def test_traversal_is_refused(sandbox):
    escape = "../secret.pdf"
    # non-vacuity: this really would have reached the secret
    assert (sandbox / escape).resolve() == (sandbox.parent / "secret.pdf").resolve()
    with pytest.raises(ValueError):
        resolve_ingest_path(str(sandbox / escape))


def test_absolute_path_outside_the_root_is_refused(sandbox):
    with pytest.raises(ValueError):
        resolve_ingest_path("/etc/passwd")


def test_symlink_planted_inside_the_root_is_judged_on_its_target(sandbox):
    link = sandbox / "innocent.pdf"
    link.symlink_to(sandbox.parent / "secret.pdf")
    # non-vacuity: the name is inside the root, only the TARGET is outside
    assert str(link).startswith(str(sandbox))
    assert link.resolve() == (sandbox.parent / "secret.pdf").resolve()
    with pytest.raises(ValueError):
        resolve_ingest_path(str(link))


def test_sibling_directory_sharing_the_root_prefix_is_refused(sandbox):
    """`<root>_elsewhere` string-prefixes `<root>` while being a different directory."""
    sibling = Path(f"{sandbox}_elsewhere")
    sibling.mkdir()
    (sibling / "book.pdf").write_bytes(b"%PDF-other")
    assert str(sibling).startswith(str(sandbox))  # the form lies
    with pytest.raises(ValueError):
        resolve_ingest_path(str(sibling / "book.pdf"))


@pytest.mark.parametrize("bad", ["", "   ", None, 42])
def test_non_path_values_are_refused(sandbox, bad):
    with pytest.raises(ValueError):
        resolve_ingest_path(bad)


def test_refusal_never_echoes_the_offending_path(sandbox):
    marker = "zz-do-not-echo-me"
    with pytest.raises(ValueError) as excinfo:
        resolve_ingest_path(f"/tmp/{marker}.pdf")
    assert marker not in str(excinfo.value)


def test_empty_allow_list_fails_closed(monkeypatch):
    """An over-tightened override must disable ingestion, never remove the guard."""
    monkeypatch.setenv(ALLOWED_ROOTS_ENV, os.pathsep)
    assert allowed_ingest_roots() == ()
    with pytest.raises(ValueError):
        resolve_ingest_path("/etc/passwd")


# --------------------------------------------------------------- helper: innocence


def test_a_file_inside_the_root_resolves(sandbox):
    assert resolve_ingest_path(str(sandbox / "book.pdf")) == (sandbox / "book.pdf").resolve()


def test_a_nested_file_inside_the_root_resolves(sandbox):
    nested = sandbox / "sub" / "deep"
    nested.mkdir(parents=True)
    (nested / "b.pdf").write_bytes(b"%PDF")
    assert resolve_ingest_path(str(nested / "b.pdf")) == (nested / "b.pdf").resolve()


def test_the_root_itself_is_allowed(sandbox):
    assert resolve_ingest_path(str(sandbox)) == sandbox.resolve()


def test_a_relative_path_landing_inside_the_root_resolves(sandbox, monkeypatch):
    monkeypatch.chdir(sandbox)
    assert resolve_ingest_path("./book.pdf") == (sandbox / "book.pdf").resolve()


# ------------------------------------------------------ POST /api/ingest/file


async def test_ingest_file_refuses_a_traversal_and_never_reaches_the_service(sandbox):
    request = MagicMock(file_path=str(sandbox / "../secret.pdf"))
    with patch.object(ingest_mod, "IngestionService") as service_cls:
        with pytest.raises(HTTPException) as excinfo:
            await ingest_mod.ingest_local_file(request=request, current_user=ADMIN)
    assert excinfo.value.status_code == 400
    service_cls.assert_not_called()


async def test_ingest_file_accepts_a_file_inside_the_root(sandbox):
    request = MagicMock(
        file_path=str(sandbox / "book.pdf"),
        title=None,
        author=None,
        language="en",
        tier_override=None,
    )
    service = MagicMock()
    service.ingest_book = AsyncMock(
        return_value={
            "success": True,
            "book_title": "t",
            "book_author": "a",
            "tier": "A",
            "chunks_created": 1,
            "message": "ok",
        },
    )
    with patch.object(ingest_mod, "IngestionService", return_value=service):
        await ingest_mod.ingest_local_file(request=request, current_user=ADMIN)
    # the service must receive the RESOLVED value, not the raw request field
    assert service.ingest_book.await_args.kwargs["file_path"] == str(
        (sandbox / "book.pdf").resolve(),
    )


# ----------------------------------------------------- POST /api/ingest/batch


async def test_batch_refuses_a_traversal_directory(sandbox):
    request = MagicMock(
        directory_path=str(sandbox / ".."),
        file_patterns=["*.pdf"],
        skip_existing=True,
    )
    with patch.object(ingest_mod, "IngestionService") as service_cls:
        with pytest.raises(HTTPException) as excinfo:
            await ingest_mod.batch_ingest(
                request=request,
                _background_tasks=MagicMock(),
                current_user=ADMIN,
            )
    assert excinfo.value.status_code == 400
    service_cls.assert_not_called()


async def test_batch_refuses_a_glob_pattern_that_escapes_the_root(sandbox):
    """The alerts name `directory_path`; `file_patterns` is a second way out."""
    pattern = "../*.pdf"
    # non-vacuity: the glob really does reach the secret outside the root
    matched = [p.resolve() for p in sandbox.glob(pattern)]
    assert (sandbox.parent / "secret.pdf").resolve() in matched

    request = MagicMock(
        directory_path=str(sandbox),
        file_patterns=[pattern],
        skip_existing=True,
    )
    with patch.object(ingest_mod, "IngestionService") as service_cls:
        with pytest.raises(HTTPException) as excinfo:
            await ingest_mod.batch_ingest(
                request=request,
                _background_tasks=MagicMock(),
                current_user=ADMIN,
            )
    assert excinfo.value.status_code == 400
    service_cls.assert_not_called()


async def test_batch_accepts_patterns_that_stay_inside_the_root(sandbox):
    service = MagicMock()
    service.ingest_book = AsyncMock(
        return_value={
            "success": True,
            "book_title": "t",
            "book_author": "a",
            "tier": "A",
            "chunks_created": 1,
            "message": "ok",
        },
    )
    request = MagicMock(
        directory_path=str(sandbox),
        file_patterns=["*.pdf"],
        skip_existing=True,
    )
    with patch.object(ingest_mod, "IngestionService", return_value=service):
        response = await ingest_mod.batch_ingest(
            request=request,
            _background_tasks=MagicMock(),
            current_user=ADMIN,
        )
    assert response.total_books == 1
    assert service.ingest_book.await_args.args[0] == str((sandbox / "book.pdf").resolve())


# ----------------------------------------------------- POST /api/legal/ingest


async def test_legal_ingest_refuses_a_traversal_and_never_reaches_the_service(sandbox):
    request = MagicMock(
        file_path=str(sandbox / "../secret.pdf"),
        title=None,
        tier=None,
        collection_name=None,
    )
    with patch.object(legal_mod, "get_legal_service") as get_service:
        with pytest.raises(HTTPException) as excinfo:
            await legal_mod.ingest_legal_document(request=request, current_user=ADMIN)
    assert excinfo.value.status_code == 400
    get_service.assert_not_called()


async def test_legal_ingest_accepts_a_file_inside_the_root(sandbox):
    request = MagicMock(
        file_path=str(sandbox / "book.pdf"),
        title=None,
        tier=None,
        collection_name=None,
    )
    service = MagicMock()
    service.ingest_legal_document = AsyncMock(
        return_value={
            "success": True,
            "book_title": "t",
            "chunks_created": 1,
            "message": "ok",
        },
    )
    with patch.object(legal_mod, "get_legal_service", return_value=service):
        await legal_mod.ingest_legal_document(request=request, current_user=ADMIN)
    assert service.ingest_legal_document.await_args.kwargs["file_path"] == str(
        (sandbox / "book.pdf").resolve(),
    )


# ---------------------------------------------------- POST /api/ingest/upload
#
# No CodeQL alert names this route. It is nonetheless the worst of the four: the caller
# controls the path AND the bytes, starlette does not sanitise `UploadFile.filename`
# (measured on starlette 1.3.1 — it decodes the Content-Disposition value and hands it
# over), and the `.pdf`/`.epub` extension check stops neither escape because both still
# end in `.pdf`.


@pytest.mark.parametrize(
    "hostile",
    [
        "../../../tmp/pwned.pdf",  # walks out of data/temp
        "/tmp/pwned.pdf",  # pathlib REPLACES the path on an absolute operand
        "..",  # resolves to the parent, not a file
    ],
)
def test_upload_filename_escapes_are_refused(tmp_path, hostile):
    from backend.app.utils.ingest_paths import resolve_within_root

    base = tmp_path / "temp"
    base.mkdir()
    # non-vacuity: the naive join really would land outside `base`
    naive = (base / hostile).resolve()
    assert naive == base or not naive.is_relative_to(base)
    with pytest.raises(ValueError):
        resolve_within_root(base, hostile)


def test_upload_filename_symlink_is_judged_on_its_target(tmp_path):
    from backend.app.utils.ingest_paths import resolve_within_root

    base = tmp_path / "temp"
    base.mkdir()
    (tmp_path / "outside").mkdir()
    (base / "link").symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError):
        resolve_within_root(base, "link/x.pdf")


def test_upload_ordinary_filenames_still_work(tmp_path):
    from backend.app.utils.ingest_paths import resolve_within_root

    base = tmp_path / "temp"
    base.mkdir()
    for good in ("book.pdf", "Peraturan 2026 (final).pdf", "sub/deep.epub"):
        assert resolve_within_root(base, good) == (base / good).resolve()


async def test_upload_route_refuses_a_traversal_filename_and_writes_nothing(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)  # `temp_dir` is the relative Path("data/temp")
    escape = tmp_path / "pwned.pdf"
    upload = MagicMock()
    upload.filename = "../../pwned.pdf"
    upload.read = AsyncMock(return_value=b"payload")

    with patch.object(ingest_mod, "IngestionService") as service_cls:
        with pytest.raises(HTTPException) as excinfo:
            await ingest_mod.upload_and_ingest(file=upload, current_user=ADMIN)

    assert excinfo.value.status_code == 400
    service_cls.assert_not_called()
    # the point of the guard: the bytes never landed
    assert not escape.exists()


# --------------------------------------------------------------------- scope pin


def test_the_library_layer_is_deliberately_left_unconfined():
    """The cure is scoped to the HTTP handlers on purpose.

    `core/parsers.py` and `services/ingestion/*` are called with arbitrary operator-chosen
    paths by the CLI, `scripts/ingest_*.py` and `infra/eventbus/regulatory_ingest_runner.py`.
    Confining them would break real ingestion, so their CodeQL alerts stay open by
    decision, not by oversight. This pin fails if someone "completes" the fix downstream
    without revisiting those callers.
    """
    from backend.core import parsers

    source = Path(parsers.__file__).read_text(encoding="utf-8")
    assert "resolve_ingest_path" not in source
