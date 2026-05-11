"""DEPRECATED 2026-05-08 (IG-3), removal scheduled 2026-06-08.

Re-exports `organism.tools.validate_organs_registry` for backward compat
with cron jobs / scripts / CI workflows that still reference the old name.

Use `organism.tools.validate_organs_registry` directly. See `organs_registry.yaml`
for the file. The "Innervation Genoma" stays as a SYSTEM CONCEPT name in
SYMBIOSIS.md — only the file + tool were renamed for disambiguation against
the `cell-core/Genome` Python class (skill DB per-agent).
"""
from __future__ import annotations

import sys
import warnings

from organism.tools.validate_organs_registry import *  # noqa: F401, F403
from organism.tools.validate_organs_registry import (  # noqa: F401  re-export
    _RECOVERY_ACTIONS,
    _REQUIRED_FIELDS,
    _RUNTIMES,
    _SEVERITIES,
    _TYPES,
    compute_checksum,
    main,
    update_checksum,
    validate_data,
    validate_file,
)

warnings.warn(
    "organism.tools.validate_genome is deprecated, "
    "use organism.tools.validate_organs_registry. Removal 2026-06-08.",
    DeprecationWarning,
    stacklevel=2,
)


if __name__ == "__main__":
    print(
        "[deprecated] use 'python -m organism.tools.validate_organs_registry' "
        "(alias removal 2026-06-08)",
        file=sys.stderr,
    )
    sys.exit(main())
