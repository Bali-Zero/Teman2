"""schema_export.export_schemas round-trip: exported files == packaged files."""

from __future__ import annotations

import filecmp
from pathlib import Path

from backend.services.visa_engine.schema_export import SCHEMA_FILENAMES, export_schemas


def test_export_schemas_creates_output_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "exported" / "nested"
    assert not output_dir.exists()
    export_schemas(output_dir)
    assert output_dir.is_dir()


def test_export_schemas_writes_every_packaged_schema(tmp_path: Path, schemas_dir: Path) -> None:
    output_dir = tmp_path / "exported"
    export_schemas(output_dir)

    for filename in SCHEMA_FILENAMES:
        exported_file = output_dir / filename
        packaged_file = schemas_dir / filename
        assert exported_file.is_file(), f"{filename} was not exported"
        assert filecmp.cmp(exported_file, packaged_file, shallow=False), (
            f"{filename}: exported content differs from packaged content"
        )


def test_export_schemas_covers_all_eight_entrypoints_plus_contract(schemas_dir: Path) -> None:
    packaged = {p.name for p in schemas_dir.glob("*.schema.json")}
    assert packaged == set(SCHEMA_FILENAMES)
    assert len(SCHEMA_FILENAMES) == 8


def test_export_schemas_is_idempotent(tmp_path: Path) -> None:
    output_dir = tmp_path / "exported"
    export_schemas(output_dir)
    export_schemas(output_dir)  # must not raise on re-export into the same dir
    assert len(list(output_dir.glob("*.schema.json"))) == len(SCHEMA_FILENAMES)
