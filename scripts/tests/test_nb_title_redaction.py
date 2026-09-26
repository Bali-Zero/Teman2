"""Notebook titles are redacted before any report, alert or log line prints them.

Guilt: synthetic titles shaped like the four real leaks measured 2026-09-26 (a company
after "PT", a person after "Meet <date>", a party after "Tax Return for", and a listed
notebook id). Innocence: canon and legal-form titles pass through unchanged. Every name
here is invented; no real client, company or dossier appears in this file.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts._redact_pii import RedactionError, Redactor, load_config  # noqa: E402

REGISTRY_PY = REPO / "apps/mata-garuda/mata_garuda/scripts/nb_monitor/registry.py"
LISTED_ID = "afd7fc4e-2568-4fff-861f-67b661842ece"


@pytest.fixture(scope="module")
def r() -> Redactor:
    return Redactor.load_static()


@pytest.mark.parametrize(
    "title, expected",
    [
        (
            "Piano di Ristrutturazione e Conformità per PT Fakeco Nusantara",
            "Piano di Ristrutturazione e Conformità per [COMPANY-NAME-REDACTED]",
        ),
        (
            "Meet 2026-05-13 Jane Placeholder — Bali Real Estate",
            "Meet 2026-05-13 [CLIENT-NAME-REDACTED] — Bali Real Estate",
        ),
        (
            "August 2025 Income Tax Return for The Example Studio",
            "August 2025 Income Tax Return for [CLIENT-NAME-REDACTED]",
        ),
        ("Intake Rob Invented — KITAS", "Intake [CLIENT-NAME-REDACTED] — KITAS"),
        ("Brief for someone@example.org", "Brief for [CLIENT-EMAIL-REDACTED]"),
    ],
)
def test_guilt_client_shaped_titles_are_redacted(r: Redactor, title: str, expected: str) -> None:
    assert r.redact_notebook_title(title, "00000000-0000-0000-0000-000000000000") == expected


@pytest.mark.parametrize("nid", [LISTED_ID, LISTED_ID[:8], LISTED_ID.upper()])
def test_guilt_listed_notebook_loses_its_whole_title(r: Redactor, nid: str) -> None:
    assert r.redact_notebook_title("Harmless Looking Title", nid) == "[CLIENT-NOTEBOOK-REDACTED]"
    assert r.redact_notebook_title("", nid) == "[CLIENT-NOTEBOOK-REDACTED]"


@pytest.mark.parametrize(
    "title",
    [
        "NB-2: Immigration & Visa — Indonesia 2025",
        "NIB PMA Regulations 2025-2026 Research",
        "Setup PT PMA Research 2026",
        "AI Evolutionary Frontier quicktime 2026 — ALTK/DGM/PTB/SoM",
        "Bali Zero Setup Guide Mac+Mobile — Cinematic ID",
        "",
    ],
)
def test_innocence_canon_titles_unchanged(r: Redactor, title: str) -> None:
    assert r.redact_notebook_title(title, "11111111") == title


def test_short_id_never_matches_a_listed_notebook(r: Redactor) -> None:
    assert r.redact_notebook_title("Plain Title", LISTED_ID[:4]) == "Plain Title"


def test_idempotent(r: Redactor) -> None:
    once = r.redact_notebook_title("Meet 2026-01-02 Ana Madeup and PT Fakeco", None)
    assert r.redact_notebook_title(once, None) == once


def _write_rules_with(tmp_path: Path, nb_titles: dict) -> Path:
    text = (REPO / "agent-library/config/redaction-rules.yaml").read_text(encoding="utf-8")
    head = text.split("\nnb_titles:\n", 1)[0]
    tail = "\n# ─── Aggregate gate ───" + text.split("# ─── Aggregate gate ───", 1)[1]
    out = tmp_path / "redaction-rules.yaml"
    out.write_text(head + "\nnb_titles: " + json.dumps(nb_titles) + "\n" + tail, encoding="utf-8")
    return out


@pytest.mark.parametrize(
    "nb_titles",
    [
        {"sensitive_notebooks": [{"id": "afd7fc4e", "replace": "[X]"}]},
        {"sensitive_notebooks": [{"id": LISTED_ID}]},
        {"rules": [{"id": "a", "pattern": "x", "replace": "[X]"}, {"id": "a", "pattern": "y", "replace": "[Y]"}]},
        {"rules": [{"id": "a", "replace": "[X]"}]},
    ],
)
def test_guilt_unapplicable_nb_titles_entries_refused_at_load(tmp_path: Path, nb_titles: dict) -> None:
    with pytest.raises(RedactionError):
        load_config(_write_rules_with(tmp_path, nb_titles))


def _load_registry_module(name: str):
    spec = importlib.util.spec_from_file_location(name, REGISTRY_PY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _bootstrap(tmp_path: Path, *entries: tuple[str, str]) -> Path:
    notebooks = [
        {
            "uuid": uuid,
            "name": name,
            "family": "RESEARCH",
            "lifecycle_stage": "DM",
            "active_routing": False,
            "first_audited": "2026-05-07",
        }
        for uuid, name in entries
    ]
    path = tmp_path / "bootstrap.json"
    path.write_text(json.dumps({"schema_version": 1, "notebooks": notebooks}), encoding="utf-8")
    return path


def test_nb_monitor_registry_hands_out_redacted_names(tmp_path: Path) -> None:
    reg = _load_registry_module("nb_registry_under_test")
    path = _bootstrap(
        tmp_path,
        ("22222222-0000-0000-0000-000000000000", "Kontrak untuk PT Fakeco Nusantara"),
        (LISTED_ID, "Any Title"),
        ("33333333-0000-0000-0000-000000000000", "NB-3: Company Setup — Indonesia 2025"),
    )
    names = [e.name for e in reg.load_registry(path)]
    assert names == [
        "Kontrak untuk [COMPANY-NAME-REDACTED]",
        "[CLIENT-NOTEBOOK-REDACTED]",
        "NB-3: Company Setup — Indonesia 2025",
    ]


def test_nb_monitor_registry_withholds_when_redactor_cannot_load(tmp_path: Path) -> None:
    reg = _load_registry_module("nb_registry_broken")
    reg._REDACT_PII_PATH = tmp_path / "missing_redactor.py"
    path = _bootstrap(tmp_path, ("44444444-0000-0000-0000-000000000000", "Meet 2026-01-02 Ana Madeup"))
    assert [e.name for e in reg.load_registry(path)] == ["[NB-TITLE-WITHHELD:44444444]"]
