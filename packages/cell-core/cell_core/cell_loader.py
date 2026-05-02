"""Cell definition loader — Sprint 1.

Reads YAML cell definitions from ``packages/cell-core/cells/*.yaml`` and
returns plain dicts ready to feed into ``AdmissionTest().run_all()``.

The YAML schema mirrors the dict shape documented in
``docs/cell-core/admission-test-rubric.md`` § "YAML template".

Why YAML and not Python literals: cell definitions are ops artifacts that
non-developers (Antonello) must be able to edit; YAML is the lingua franca
already used for ``apps/organism/organism/genome.yaml``.

Why not Pydantic: the admission test takes plain dicts. Adding pydantic
just for parsing duplicates schema validation that admission_test already
does at runtime, with clearer error messages.

Usage::

    from cell_core.cell_loader import load_cell_definition, load_all_cells

    cell = load_cell_definition(Path("packages/cell-core/cells/intel_scraper_cell.yaml"))
    result = AdmissionTest().run_all(cell)
    assert result.passed

    # Or load all cells in a directory:
    cells = load_all_cells(Path("packages/cell-core/cells"))
"""

from __future__ import annotations

import pathlib
from typing import Any

import yaml


def load_cell_definition(path: pathlib.Path) -> dict[str, Any]:
    """Load a single cell YAML definition.

    Returns a plain dict that ``AdmissionTest.run_all`` can consume directly.
    Missing optional keys are NOT injected — admission_test handles defaults
    via ``cd.get(key, default)``.

    Raises:
        FileNotFoundError: if the path does not exist.
        yaml.YAMLError: if the file is not valid YAML.
        ValueError: if the top-level structure is not a mapping.
    """
    if not path.exists():
        raise FileNotFoundError(f"cell definition not found: {path}")
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(
            f"cell definition root must be a YAML mapping, got "
            f"{type(data).__name__} at {path}"
        )
    return data


def load_all_cells(cells_dir: pathlib.Path) -> dict[str, dict[str, Any]]:
    """Load every ``*.yaml`` cell definition under ``cells_dir``.

    Returns a dict mapping ``cell["name"]`` → cell definition. Cells that
    have no ``name`` field, or whose name collides with an earlier load,
    raise ``ValueError`` — fail-loud rather than silently shadowing.
    """
    if not cells_dir.exists():
        return {}
    cells: dict[str, dict[str, Any]] = {}
    for yaml_path in sorted(cells_dir.glob("*.yaml")):
        cell = load_cell_definition(yaml_path)
        name = cell.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(
                f"cell definition at {yaml_path} is missing a 'name' field"
            )
        if name in cells:
            raise ValueError(
                f"duplicate cell name {name!r}: previously loaded from "
                f"{cells[name].get('_source_path')}, now from {yaml_path}"
            )
        # Attach source path for diagnostics; not a Symbiosis-checked field.
        cell["_source_path"] = str(yaml_path)
        cells[name] = cell
    return cells


__all__ = ["load_cell_definition", "load_all_cells"]
