"""Unit tests for kbli_inspect_cache_bust.py.

The load-bearing invariant is NOT the eviction loop — it is that this script's
key format matches the one `inspect_kbli` actually writes. If those drift, the
script reports "no cache entry (nothing to evict)" for every code, a cure
declares itself proven-live, and WhatsApp/webchat keep serving the pre-cure
payload for up to 30 days. That is the exact failure this tool exists to
prevent, so it is pinned against the router's own source rather than restated.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.scripts.kbli_inspect_cache_bust import cache_key, parse_codes

ROUTER = Path(__file__).resolve().parents[3] / "app" / "routers" / "kbli_notebook.py"


def test_key_format_matches_the_router_that_writes_it():
    """Anti-drift: read the key literal out of `kbli_notebook.py` and confirm
    this script builds the same string. A rename on either side fails here
    instead of silently evicting nothing in production."""
    src = ROUTER.read_text(encoding="utf-8")
    m = re.search(r'cache_key\s*=\s*f"([^"]*\{code\}[^"]*)"', src)
    assert m, f"could not find the inspect cache key literal in {ROUTER}"
    router_key = m.group(1).replace("{code}", "82920")
    assert cache_key("82920") == router_key


def test_cache_key_is_per_code():
    assert cache_key("82920") != cache_key("82921")
    assert "82920" in cache_key("82920")


def test_parse_codes_preserves_order_and_drops_blanks():
    assert parse_codes("26120, 60111 ,82920,,85598") == ["26120", "60111", "82920", "85598"]


def test_parse_codes_empty_input_yields_empty_list():
    """Feeds the caller's exit-2 refusal — an empty scope must never be read as
    "nothing needed evicting"."""
    assert parse_codes("") == []
    assert parse_codes(" , , ") == []
