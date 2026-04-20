"""Unit tests for the lead_intent matcher cron logic.

We test the pure functions (`normalise_phone`, `_pick_match`) against
crafted inputs. The DB-touching `run()` is not covered here — it has
an integration-test owner in `backend/tests/integration/`.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Import the script file directly (it lives in /scripts/ at the root, not in a package).
# File is at: apps/backend-rag/backend/tests/services/lead_capture/test_matcher.py
# parents[0..5]: lead_capture, services, tests, backend, backend-rag, apps, [root]
_SCRIPT_PATH = Path(__file__).resolve().parents[6] / "scripts" / "lead_intent_matcher.py"
sys.path.insert(0, str(_SCRIPT_PATH.parent))
import lead_intent_matcher as m  # noqa: E402


class TestPhoneNormalise:
    def test_strips_plus_and_spaces(self):
        assert m.normalise_phone("+62 812 345 678") == "812345678"

    def test_strips_leading_zero(self):
        assert m.normalise_phone("0812 345") == "812345"

    def test_collapses_equivalent_forms(self):
        assert m.normalise_phone("+62812345") == m.normalise_phone("0812345")

    def test_empty(self):
        assert m.normalise_phone("") is None
        assert m.normalise_phone(None) is None


class TestPickMatch:
    def _intent(self, *, phone: str | None = None, minutes_ago: int = 2):
        created = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        context = {}
        if phone:
            context["phone"] = phone
        return {
            "id": "li_abc",
            "source": "visa_clock",
            "context": context,
            "utm": None,
            "fingerprint": None,
            "created_at": created,
        }

    def _msg(self, *, phone_norm: str, minutes_ago: int = 1):
        return {
            "id": "c_123",
            "phone_norm": phone_norm,
            "touched_at": datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
            "lead_source": None,
            "lead_metadata": None,
        }

    def test_phone_match_in_window(self):
        intent = self._intent(phone="+62 812 345", minutes_ago=2)
        msg = self._msg(phone_norm="812345", minutes_ago=1)
        assert m._pick_match(intent, [msg]) is msg

    def test_phone_match_outside_window_skipped(self):
        intent = self._intent(phone="+62 812 345", minutes_ago=2)
        msg = self._msg(phone_norm="812345", minutes_ago=40)  # > 30 min AFTER intent
        assert m._pick_match(intent, [msg]) is None

    def test_single_candidate_no_phone_accepted(self):
        intent = self._intent(phone=None, minutes_ago=2)
        msg = self._msg(phone_norm="999999", minutes_ago=1)
        assert m._pick_match(intent, [msg]) is msg

    def test_multiple_candidates_no_phone_ambiguous(self):
        intent = self._intent(phone=None, minutes_ago=2)
        msgs = [
            self._msg(phone_norm="111", minutes_ago=1),
            self._msg(phone_norm="222", minutes_ago=1),
        ]
        assert m._pick_match(intent, msgs) is None

    def test_no_messages_no_match(self):
        assert m._pick_match(self._intent(), []) is None
