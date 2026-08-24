"""Loads the shared defect-class catalogue (``defect_classes.yaml``) as
typed data.

Both bots' golden conversation suites are meant to index INTO this file by
``id`` rather than maintain their own parallel enumeration — see this
package's ``__init__.py`` docstring and the B6a mandate's deliverable #3.
B6b (client-bot golden fixtures, building after B1 freezes its contracts)
is data entry against this catalogue, not a second list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CATALOGUE_PATH = Path(__file__).parent / "defect_classes.yaml"

VALID_BOTS = frozenset({"client", "team", "transport"})


@dataclass(frozen=True)
class DefectClass:
    """One row of the catalogue."""

    id: str
    bot: str
    title: str
    description: str
    source: str
    variants: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.bot not in VALID_BOTS:
            raise ValueError(
                f"{self.id}: bot must be one of {sorted(VALID_BOTS)}, got {self.bot!r}"
            )
        if not self.id or not self.id[0].isalpha():
            raise ValueError(
                f"defect class id {self.id!r} must be a non-empty slug starting with a letter"
            )
        if not self.title.strip():
            raise ValueError(f"{self.id}: title must not be blank")
        if not self.description.strip():
            raise ValueError(f"{self.id}: description must not be blank")
        if not self.source.strip():
            raise ValueError(f"{self.id}: source must not be blank")


def _coerce_entry(entry: dict[str, Any]) -> DefectClass:
    variants_raw = entry.get("variants", ())
    # YAML may hand back a list of str OR (for the "401"/"403"/... row) a
    # list that PyYAML would otherwise coerce ints for unquoted digits —
    # the source file quotes them, but coerce defensively here too so a
    # future edit that forgets the quotes fails loudly at load time
    # instead of producing a catalogue with a non-str variant.
    variants = tuple(str(v) for v in variants_raw)
    return DefectClass(
        id=str(entry["id"]),
        bot=str(entry["bot"]),
        title=str(entry["title"]),
        description=str(entry["description"]),
        source=str(entry["source"]),
        variants=variants,
    )


def load_defect_catalogue(path: Path | None = None) -> list[DefectClass]:
    """Parse ``defect_classes.yaml`` (or ``path``) into ``DefectClass``
    records, in file order.

    Raises:
        ValueError: if any ``id`` repeats. The catalogue's entire reason
            to exist is to give golden fixtures ONE stable id per defect
            class — a silently-tolerated duplicate id would let two
            fixtures claim to cover the same class while actually testing
            different things (or the reverse), so this is a hard error
            rather than a warning.
    """
    src = path or CATALOGUE_PATH
    raw = yaml.safe_load(src.read_text(encoding="utf-8"))
    entries = raw["defect_classes"]

    seen: set[str] = set()
    catalogue: list[DefectClass] = []
    for entry in entries:
        dc = _coerce_entry(entry)
        if dc.id in seen:
            raise ValueError(f"duplicate defect class id in {src}: {dc.id!r}")
        seen.add(dc.id)
        catalogue.append(dc)
    return catalogue


def by_bot(catalogue: list[DefectClass], bot: str) -> list[DefectClass]:
    """Filter a loaded catalogue to one ``bot`` category
    (``"client"`` / ``"team"`` / ``"transport"``)."""
    return [dc for dc in catalogue if dc.bot == bot]


def index_by_id(catalogue: list[DefectClass]) -> dict[str, DefectClass]:
    """``{id: DefectClass}`` — the lookup shape a golden-fixture loader
    wants (``fixture.defect_class_id -> catalogue lookup -> assert it
    exists``), rather than a linear scan per fixture.
    """
    return {dc.id: dc for dc in catalogue}
