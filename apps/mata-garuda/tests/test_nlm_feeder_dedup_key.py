"""Regression tests for the nlm_feeder dedup-key collapse (W89 #2).

Bug: dedup_key was the bare URL, so distinct intel items sharing one landing-page
URL (every LHKPN official carries url='https://elhkpn.kpk.go.id/'; one peraturan
harmon URL covers many regulations) collapsed — after the first was fed, the rest
matched 'already fed' and were silently skip+ACKed, never reaching NLM. The audit
saw 130 distinct LHKPN entries on that one URL with 0 markers → 129 would drop.

Fix: _dedup_key(title, url) keys on item identity (hash of title+url) so distinct
titles on a shared URL dedup independently, while true duplicates still collapse.
"""
from __future__ import annotations

from mata_garuda.workers.nlm_feeder import _dedup_key


LHKPN_URL = "https://elhkpn.kpk.go.id/"


class TestDedupKey:
    # ── GUILT: the bug must be fixed ──────────────────────────────────────
    def test_distinct_officials_same_url_get_distinct_keys(self):
        """The W89 #2 core: two officials on the same portal URL must NOT collapse."""
        k1 = _dedup_key("LHKPN GEDE DUDY DUWITA", LHKPN_URL)
        k2 = _dedup_key("LHKPN RAJA ULUL AZMI", LHKPN_URL)
        assert k1 != k2, "distinct titles on a shared URL must dedup independently"

    def test_many_distinct_regs_one_harmon_url_all_distinct(self):
        url = "https://peraturan.go.id/harmon/abc123"
        keys = {_dedup_key(f"Peraturan {i} tahun 2026", url) for i in range(50)}
        assert len(keys) == 50, "50 distinct regs on one harmon URL → 50 keys"

    # ── INNOCENCE: true duplicates must STILL collapse ────────────────────
    def test_identical_title_and_url_is_stable(self):
        """Same item seen twice → same key (real dedup still works)."""
        a = _dedup_key("Perpres baru kementerian", "https://x.go.id/p")
        b = _dedup_key("Perpres baru kementerian", "https://x.go.id/p")
        assert a == b

    def test_url_only_item_keys_on_url(self):
        """No title (e.g. arxiv feed) → bare-URL dedup preserved (back-compat)."""
        u = "http://arxiv.org/abs/2604.07345v1"
        assert _dedup_key("", u) == u
        assert _dedup_key("  ", u) == u  # whitespace-only title is empty

    def test_title_only_item_keys_on_title(self):
        assert _dedup_key("Some headline", "") == "title:Some headline"

    def test_empty_empty_is_constant(self):
        assert _dedup_key("", "") == "empty"

    def test_key_is_short_and_stable_string(self):
        k = _dedup_key("a title", "http://u")
        assert isinstance(k, str) and k.startswith("h:") and len(k) <= 30
        assert k == _dedup_key("a title", "http://u")  # deterministic
