"""Shared PII source-allowlist check (Phase-0 safety rail, FATAL 5 —
research/operations/2026-07-17-full-domain-cache-design.md §8) for
`scripts/curated_qa_convert_e33.py` and `scripts/curated_qa_harvest.py`.

Structural check, not an assumption: input files are accepted only from the
committed `data/curated_qa/` corpus root, or from an explicit
`--source-attestation` naming the reviewed dossier for a one-off path
outside it. Any path referencing a raw-log-derived source
(`meta_inbox_messages` — customer message text, PII-bearing) is hard-refused
regardless of attestation; the PII boundary is structural, not
policy-by-instruction.
"""

from __future__ import annotations

from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
ALLOWED_SOURCE_ROOT = (_SCRIPT_DIR.parent / "data" / "curated_qa").resolve()

# Raw-log-derived sources are ALWAYS refused, even with an attestation — the
# PII boundary here is structural (UU PDP Art. 67-68), not a reviewer's call
# to waive. Matched as a case-insensitive substring against the resolved
# absolute path.
FORBIDDEN_SOURCE_MARKERS: tuple[str, ...] = ("meta_inbox_messages",)


class SourceAllowlistViolation(ValueError):
    """Raised when an input path fails the PII source allowlist check."""


def check_source_allowlist(
    paths: list[Path],
    *,
    source_attestation: str | None = None,
) -> None:
    """Raise SourceAllowlistViolation if any of `paths` is not an
    allowlisted curated_qa source.

    Args:
        paths: candidate input paths (files or directories) about to be
            read by the converter or harvester.
        source_attestation: operator-supplied name/path of the reviewed
            dossier authorizing a path outside `data/curated_qa/`. Ignored
            for paths already inside the allowlisted root.
    """
    for p in paths:
        resolved = p.resolve()
        lowered = str(resolved).lower()
        if any(marker in lowered for marker in FORBIDDEN_SOURCE_MARKERS):
            raise SourceAllowlistViolation(
                f"REFUSED (FATAL 5, PII boundary): input path references a "
                f"forbidden raw-log-derived source: {p}. curated_qa content "
                "must come from NB collections or reviewed markdown "
                "dossiers only, never raw meta_inbox_messages.",
            )

        try:
            resolved.relative_to(ALLOWED_SOURCE_ROOT)
            continue  # inside data/curated_qa/ — always OK
        except ValueError:
            pass

        if not source_attestation:
            raise SourceAllowlistViolation(
                f"REFUSED (FATAL 5, PII boundary): input path {p} is "
                f"outside the allowlisted {ALLOWED_SOURCE_ROOT} corpus root "
                "and no --source-attestation was given naming the reviewed "
                "dossier that authorizes it.",
            )
