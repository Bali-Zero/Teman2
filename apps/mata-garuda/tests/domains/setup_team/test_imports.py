"""Lightweight-import contract: setup_team must NOT pull ML deps."""
from __future__ import annotations

import sys


def test_setup_team_importable_without_ml_deps():
    """Importing the package and the obligation_engine module must NOT
    transitively load transformers/torch/sklearn. Same Wave 2 lesson as
    foundations/__init__.py — heavy deps go behind explicit access only.
    """
    # Snapshot state before the import to avoid false negatives if a
    # previous test in the same pytest run already pulled the heavy deps.
    pre_loaded = {
        mod for mod in ("transformers", "torch", "sklearn") if mod in sys.modules
    }

    # Importing the package itself — eager exports must be stdlib only.
    import mata_garuda.domains.setup_team as st_pkg  # noqa: F401

    # Touch the dataclasses (eager surface).
    from mata_garuda.domains.setup_team import Regulation  # noqa: F401
    from mata_garuda.domains.setup_team.types import Obligation  # noqa: F401

    # Importing the obligation_engine submodule directly is also allowed
    # to be lightweight — sqlite3 + stdlib only at module load.
    from mata_garuda.domains.setup_team import obligation_engine  # noqa: F401

    newly_loaded = {
        mod for mod in ("transformers", "torch", "sklearn") if mod in sys.modules
    } - pre_loaded
    assert newly_loaded == set(), (
        f"setup_team eager import pulled ML deps: {newly_loaded}. "
        "These must stay behind PEP 562 lazy access."
    )


def test_setup_team_lazy_attributes_resolve():
    """PEP 562 __getattr__ should resolve named exports on demand."""
    import mata_garuda.domains.setup_team as st_pkg

    # Resolution path goes through __getattr__ → import submodule → cache.
    assert callable(st_pkg.should_skip_today)


def test_setup_team_unknown_attribute_raises_attribute_error():
    import mata_garuda.domains.setup_team as st_pkg

    try:
        _ = st_pkg.totally_made_up_name_that_should_not_exist
    except AttributeError as exc:
        assert "totally_made_up_name_that_should_not_exist" in str(exc)
    else:
        raise AssertionError("Expected AttributeError for unknown attribute")


def test_types_dataclasses_minimal_smoke():
    """Frozen dataclasses construct + equality contract."""
    from datetime import date

    from mata_garuda.domains.setup_team.types import (
        Client,
        Obligation,
        Regulation,
    )

    reg = Regulation(
        source_id="pasal-id:uu-2022-27",
        domain="regulation",
        tier=1,
        title="UU 27/2022 PDP",
        url="https://peraturan.bpk.go.id/...",
        published_at=date(2022, 9, 27),
        body_excerpt="...",
        tags=("regex_match:UU 27",),
    )
    assert reg.tier == 1

    obl = Obligation(
        text="Wajib lapor pelanggaran data dalam 3x24 jam",
        obligation_type="reporting",
        article_ref="Pasal 46",
        deadline_pattern="3x24 jam",
        sanction_if_missed="denda administratif",
        effective_date=date(2024, 10, 17),
        kbli_codes_affected=("63122",),
        regulation_source_id=reg.source_id,
    )
    assert obl.id is None
    assert obl.human_validated is False

    cli = Client(id=1, name="PT Pulau Dewata Desain", kbli_codes=("63122",))
    assert cli.active is True
