"""parse_ts guilt+innocence (superscar #3): both live sidecar ts dialects.

Born from the healer-pro FIRST tick (2026-07-06): the Pro fleet heartbeat lib
writes ts as numeric epoch seconds, the G2 gene writes ISO-8601 — parse_ts
read only ISO, so 14 healthy Pro organs classified false-"dead" (the healer's
FP rule refused the kickstarts; family #9 state-schema drift on the reader).
"""

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[1] / "healer_receptor_registry.py"
_spec = importlib.util.spec_from_file_location("healer_receptor_registry", _MOD_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["healer_receptor_registry"] = _mod
_spec.loader.exec_module(_mod)

parse_ts = _mod.parse_ts


def test_guilt_epoch_float_parses():
    # the Pro dialect that produced 14 false-dead: float epoch seconds
    dt = parse_ts(1783102855.0)
    assert dt is not None
    assert dt == datetime.fromtimestamp(1783102855.0, tz=timezone.utc)


def test_guilt_epoch_int_parses():
    dt = parse_ts(1783102855)
    assert dt is not None
    assert dt.tzinfo is not None


def test_innocence_iso_z_still_parses():
    # the G2 gene dialect must keep working exactly as before
    dt = parse_ts("2026-07-06T13:15:58Z")
    assert dt == datetime(2026, 7, 6, 13, 15, 58, tzinfo=timezone.utc)


def test_innocence_iso_offset_still_parses():
    assert parse_ts("2026-07-06T13:15:58+00:00") is not None


def test_garbage_is_none_not_crash():
    assert parse_ts("not-a-date") is None
    assert parse_ts(None) is None
    assert parse_ts(float("inf")) is None


def test_bool_is_not_a_timestamp():
    # bool is an int subclass — True must NOT become epoch-second 1
    assert parse_ts(True) is None
