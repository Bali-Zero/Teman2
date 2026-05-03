"""Regression: AHU must be in run_full_pipeline scraper_map."""
from __future__ import annotations

import inspect

from osint_nexus import pipeline


def test_ahu_in_scraper_map() -> None:
    source = inspect.getsource(pipeline.run_full_pipeline)
    assert '"ahu"' in source
    assert "AHUScraper" in source


def test_all_known_sources_dispatchable() -> None:
    source = inspect.getsource(pipeline.run_full_pipeline)
    expected = {"lhkpn", "lpse", "putusan", "ahu"}
    missing = {s for s in expected if f'"{s}"' not in source}
    assert not missing, f"Missing from scraper_map: {missing}"
