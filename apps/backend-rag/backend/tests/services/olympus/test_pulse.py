"""Tests for Olympus v2 Pulse — outcome values match DB CHECK constraint."""
import pytest
from backend.services.olympus.models import PulseAction
from backend.services.olympus.pulse import Pulse

VALID_OUTCOMES = {"success", "failure", "skipped", "proposed"}


class TestPulseOutcomes:
    def test_no_ok_or_error_in_code(self):
        """BUG-1 fix: pulse must never emit 'ok' or 'error' as outcome."""
        import inspect
        source = inspect.getsource(Pulse)
        assert 'outcome="ok"' not in source, "Found 'ok' outcome — must be 'success'"
        assert 'outcome="error"' not in source, "Found 'error' outcome — must be 'failure'"

    def test_all_outcomes_in_valid_set(self):
        """Every outcome literal in pulse.py must match the DB CHECK constraint."""
        import inspect, re
        source = inspect.getsource(Pulse)
        outcomes = re.findall(r'outcome="(\w+)"', source)
        for o in outcomes:
            assert o in VALID_OUTCOMES, f"Invalid outcome '{o}' — must be one of {VALID_OUTCOMES}"
