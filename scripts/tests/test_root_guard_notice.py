"""root_guard: the Apache-2.0 NOTICE file (#8241) is allowed at root; junk is not."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "root_guard", Path(__file__).resolve().parents[1] / "root_guard.py"
)
root_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(root_guard)


def test_notice_is_whitelisted():
    assert root_guard.is_whitelisted("NOTICE")


def test_junk_root_file_still_rejected():
    assert not root_guard.is_whitelisted("scratch_dump_notes.txt")
    assert not root_guard.is_whitelisted("NOTICE.bak")
