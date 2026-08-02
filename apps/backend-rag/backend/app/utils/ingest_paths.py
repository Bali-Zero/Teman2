"""Root confinement for the three ingestion HTTP entry points.

`POST /api/ingest/file`, `POST /api/ingest/batch` and `POST /api/legal/ingest` take a
filesystem path straight out of the request body — that is their documented purpose
("Ingest a book from local file path"), and `_require_ingest_admin` is today their only
defense. Two measured facts make that insufficient:

* **The principal set is wider than the three admin emails.** `is_crm_admin` also accepts
  the practices-full-view allowlist and *any* user whose `role` is one of
  admin / board member / ceo / founder.
* **The bytes do not stay with the caller.** They are embedded into the shared Qdrant
  knowledge base — queryable in chat by any authenticated user — and, on the legal path,
  uploaded to the team Drive folder ``BALI ZERO/PERATURAN``. So an unconfined path is a
  privilege *escalation*, not a read: ``/proc/self/environ`` would put every Fly secret
  into a chat-queryable corpus.

Scope is deliberately the three HTTP handlers and nothing below them. The library layer
(`backend/core/parsers.py`, `backend/services/ingestion/*`) is called with arbitrary
operator-chosen paths by `backend/cli/ingestion_cli.py`, `scripts/ingest_*.py` and
`infra/eventbus/regulatory_ingest_runner.py` — those are not remote input, and confining
them would break real ingestion.

**Why this returns the path instead of just asserting.** A validator that merely raises
leaves the raw value in scope, so a later edit can validate one variable and use another;
and CodeQL's taint tracking does not model a function that raises elsewhere as a barrier
(measured on #3524: nine guards live-proven inside the running containers, every alert
still open on the merge commit). Callers must use the returned value.
"""

from __future__ import annotations

import os
from pathlib import Path

# Defaults mirror the ingestion data directories: `raw_books_dir` / `processed_dir` from
# settings, plus the hardcoded `data/temp` that `upload_and_ingest` writes to before
# handing the file to the very same service.
_DEFAULT_ROOTS: tuple[str, ...] = ("./data/raw_books", "./data/processed", "./data/temp")

#: Operator escape hatch. When set, it REPLACES the defaults (os.pathsep-separated), so it
#: can both widen the allow-list for a deployment whose data lives elsewhere and tighten it.
ALLOWED_ROOTS_ENV = "INGEST_ALLOWED_ROOTS"


def _settings_roots() -> list[str]:
    """Roots declared in settings, best-effort.

    Imported lazily and type-checked: under `backend/tests/unit/routers/` a conftest
    installs a fake `backend.app.core.config` whose `settings` is a MagicMock, so these
    attributes can be Mock objects rather than strings. A non-str value is a
    misconfiguration either way — fall back to the defaults rather than crash the request.
    """
    try:
        from backend.app.core.config import settings
    except Exception:  # pragma: no cover - config import failure is fatal elsewhere
        return []
    roots: list[str] = []
    for attr in ("raw_books_dir", "processed_dir"):
        value = getattr(settings, attr, None)
        if isinstance(value, str) and value.strip():
            roots.append(value)
    return roots


def allowed_ingest_roots() -> tuple[Path, ...]:
    """Resolved, de-duplicated roots an ingestion request may name."""
    override = os.environ.get(ALLOWED_ROOTS_ENV, "").strip()
    if override:
        raw = [part for part in override.split(os.pathsep) if part.strip()]
    else:
        raw = [*_settings_roots(), *_DEFAULT_ROOTS]

    roots: list[Path] = []
    for entry in raw:
        # `strict=False` (the default): a root that does not exist yet still resolves, and
        # confinement must not depend on the directory having been created.
        resolved = Path(entry).expanduser().resolve()
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def resolve_within_root(base: Path, raw_name: str) -> Path:
    """Resolve `raw_name` under `base`, or raise `ValueError` if it lands outside.

    For the upload route, where the directory is chosen by the SERVER and only the name
    comes from the caller — so it is confined to that one directory rather than to the
    ingest allow-list, which is a different question and a different env var.

    `Path(base) / raw_name` is not safe on its own in two ways, both of which survive an
    extension check because both still end in `.pdf`: a relative name walks up
    (``../../x.pdf``), and pathlib REPLACES the whole path when the operand is absolute
    (``Path("data/temp") / "/etc/x.pdf"`` is ``/etc/x.pdf``). Containment is judged on the
    resolved result, so both are refused, as is a symlink whose target leaves `base`.
    """
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise ValueError("Upload filename must be a non-empty string")

    resolved_base = Path(base).expanduser().resolve()
    candidate = (resolved_base / raw_name).expanduser().resolve()
    if candidate == resolved_base or not candidate.is_relative_to(resolved_base):
        # `== base` is refused too: a name resolving to the directory itself is not a file
        # to write, it is `.` or `..`-style traversal that happened to land on the root.
        raise ValueError("Upload filename must resolve to a file inside the upload directory")
    return candidate


def resolve_ingest_path(raw_path: str) -> Path:
    """Return `raw_path` resolved, or raise `ValueError` if it escapes the allowed roots.

    `Path.resolve()` follows symlinks, so a symlink planted inside an allowed root that
    points outside it is rejected on the *target* — the entity — rather than accepted on
    the name. Containment is tested with `is_relative_to`, never a string prefix: as a
    prefix, ``/data/raw_books_elsewhere`` "starts with" ``/data/raw_books`` while being a
    different directory (superscar #3 — the form lying about the entity).

    The message never echoes `raw_path`: it reaches logs and HTTP responses, and it is the
    tainted value.
    """
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("Ingestion path must be a non-empty string")

    roots = allowed_ingest_roots()
    if not roots:
        # Fail closed. An empty allow-list means "confine to nothing", never "allow all" —
        # an over-tightened INGEST_ALLOWED_ROOTS must break ingestion loudly, not silently
        # remove the guard.
        raise ValueError("No ingestion roots are configured; ingestion by path is disabled")

    resolved = Path(raw_path).expanduser().resolve()
    if any(resolved == root or resolved.is_relative_to(root) for root in roots):
        return resolved

    allowed = ", ".join(str(root) for root in roots)
    raise ValueError(f"Ingestion path must be inside an allowed root ({allowed})")
