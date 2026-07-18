"""Export the packaged JSON Schema 2020-12 contract files to a directory.

Pure I/O, no transformation: the files under ``schemas/`` are the single
source of truth for the wire contract; this just copies them byte-for-byte
so a caller (a future HTTP endpoint serving
``https://schemas.balizero.com/visa-engine/...``, or offline signing
tooling) can materialize them elsewhere without importing this package's
internals.
"""

from __future__ import annotations

import shutil
from pathlib import Path

_SCHEMAS_DIR = Path(__file__).parent / "schemas"

SCHEMA_FILENAMES: tuple[str, ...] = (
    "contract.schema.json",
    "rule-pack.schema.json",
    "rule.schema.json",
    "visa-product-version.schema.json",
    "applicant-facts.schema.json",
    "decision.schema.json",
    "price-quote.schema.json",
    "source-record.schema.json",
)


def export_schemas(output_dir: Path) -> None:
    """Copy every packaged schema file into ``output_dir`` (created if needed).

    Byte-for-byte copy: ``export_schemas(tmp)``'s output is identical to the
    packaged ``schemas/`` files.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in SCHEMA_FILENAMES:
        source = _SCHEMAS_DIR / filename
        shutil.copy2(source, output_dir / filename)
