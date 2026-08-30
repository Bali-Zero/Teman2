from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "tailnet_policy_drift.py"
POLICY = REPO_ROOT / "infra" / "tailscale" / "policy.hujson"
FIXTURES = Path(__file__).parent / "fixtures"
ALLOW_ALL = FIXTURES / "tailnet_netmap_allow_all_2026_08_11.json"
POLICY_MATCH = FIXTURES / "tailnet_netmap_policy_match.json"


def run_tool(*arguments: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--policy", str(POLICY), *arguments],
        capture_output=True,
        check=False,
        text=True,
    )
    return completed, json.loads(completed.stdout)


def load_module() -> object:
    spec = importlib.util.spec_from_file_location("tailnet_policy_drift", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_guilt_allow_all_diverges_from_declared_policy() -> None:
    completed, output = run_tool("--netmap-fixture", str(ALLOW_ALL))

    assert completed.returncode == 1
    assert output["verdict"] == "DIVERGED"


def test_innocence_matching_filter_is_clean() -> None:
    completed, output = run_tool("--netmap-fixture", str(POLICY_MATCH), "--json")

    assert completed.returncode == 0
    assert output["verdict"] == "CLEAN"


def test_blind_for_unreadable_fixture_never_claims_clean(tmp_path: Path) -> None:
    completed, output = run_tool("--netmap-fixture", str(tmp_path / "missing-netmap.json"))

    assert completed.returncode == 2
    assert output["verdict"] == "BLIND"
    assert output["verdict"] != "CLEAN"


def test_blind_for_valid_json_with_wrong_netmap_schema(tmp_path: Path) -> None:
    fixture = tmp_path / "wrong-schema.json"
    fixture.write_text('{"PacketFilter": {}}', encoding="utf-8")

    completed, output = run_tool("--netmap-fixture", str(fixture))

    assert completed.returncode == 2
    assert output["verdict"] == "BLIND"


def test_blind_for_non_json_netmap(tmp_path: Path) -> None:
    fixture = tmp_path / "not-json.json"
    fixture.write_text("not JSON", encoding="utf-8")

    completed, output = run_tool("--netmap-fixture", str(fixture))

    assert completed.returncode == 2
    assert output["verdict"] == "BLIND"


def test_hujson_parser_preserves_double_slash_inside_string() -> None:
    module = load_module()
    parsed = module.parse_hujson('{"url":"https://example.test/a//b", // a comment\n "items":[1,],}')

    assert parsed["url"] == "https://example.test/a//b"
    assert parsed["items"] == [1]


def test_hujson_stripper_handles_an_ESCAPED_quote_inside_a_string() -> None:
    """The escape branch was unreachable: it compared a one-character slice against
    "\\\\", a TWO-character literal, so `escaped` was never set. An escaped quote then
    ended the string early and the remainder was re-scanned as structure — the `//`
    inside this string was eaten as a comment and the document truncated.

    Measured before the fix, this exact input raised
    JSONDecodeError("Unterminated string"). It fails toward BLIND rather than CLEAN, so
    it was never a security hole, but a receptor that goes blind on a valid policy has
    lost the same visibility by a slower route.

    The sibling test below covers an UNESCAPED `//` inside a string and passed
    throughout — which is why this one is separate: the two look like the same case and
    only one of them was ever broken.
    """
    module = load_module()
    parsed = module.parse_hujson('{"a": "he said \\" // not a comment", "b": 1}')

    assert parsed["a"] == 'he said " // not a comment'
    assert parsed["b"] == 1


def test_output_redacts_ip_and_email_from_evidence() -> None:
    command = (
        "import importlib.util,sys; "
        f"spec=importlib.util.spec_from_file_location('drift',{str(SCRIPT)!r}); "
        "module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); "
        "module.emit_result('CLEAN','0123456789abcdef',['contact owner@example.com at 203.0.113.7'])"
    )
    completed = subprocess.run([sys.executable, "-c", command], capture_output=True, check=False, text=True)

    assert completed.returncode == 0
    assert "owner@example.com" not in completed.stdout
    assert "203.0.113.7" not in completed.stdout
    assert json.loads(completed.stdout)["evidence"] == ["redacted-sensitive-evidence"]


def test_both_packet_filter_schemas_parse_to_the_same_shapes(tmp_path: Path) -> None:
    """The LIVE schema is Srcs/Dsts (measured on this fleet 2026-08-31); the older one is
    SrcIPs/DstPorts. The first version of this tool understood only the older one, so it
    answered BLIND on every real node while its fixtures encoded a format the netmap
    never emits — a corpus proving the tool against a world that does not exist.

    Both must reduce to identical rule shapes, or the two paths are not the same probe.
    """
    module = load_module()
    live = {"PacketFilter": [{"Srcs": ["192.0.2.1/32"], "SrcCaps": None,
                              "Dsts": [{"Net": "0.0.0.0/0",
                                        "Ports": {"First": 0, "Last": 65535}}],
                              "Caps": [], "IPProto": [6, 17]}]}
    legacy = {"PacketFilter": [{"SrcIPs": ["192.0.2.1/32"],
                                "DstPorts": [{"IP": "0.0.0.0/0", "Bits": None,
                                              "Ports": {"First": 0, "Last": 65535}}],
                                "IPProto": [6, 17]}]}

    assert module.netmap_shapes(live) == module.netmap_shapes(legacy)


def test_the_guilt_fixture_uses_the_LIVE_schema(tmp_path: Path) -> None:
    """Pins the fixture to the format the fleet actually speaks. Without this the fixture
    can silently drift back to a shape no real netmap produces, and every other case here
    would stay green while proving nothing about a live node."""
    fixture = json.loads(ALLOW_ALL.read_text())
    rule = fixture["PacketFilter"][0]

    assert "Srcs" in rule and "Dsts" in rule, "guilt fixture must use the live schema"
    assert "Net" in rule["Dsts"][0]


def test_no_tailnet_node_address_appears_in_any_tool_output() -> None:
    """The tool's evidence describes rule SHAPE, never identity. The fixtures necessarily
    contain the fleet's own host addresses (they are already published in policy.hujson
    and are what makes the CLEAN comparison meaningful) — so the property that matters is
    that none of them reach the OUTPUT."""
    for fixture in (ALLOW_ALL, POLICY_MATCH):
        completed, _ = run_tool("--netmap-fixture", str(fixture))
        combined = completed.stdout + completed.stderr
        assert not re.search(r"\b100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+", combined), \
            f"a tailnet-range address reached the output for {fixture.name}"


def test_policy_fingerprint_is_stable_and_changes_with_policy_content(tmp_path: Path) -> None:
    first, first_output = run_tool("--netmap-fixture", str(POLICY_MATCH))
    second, second_output = run_tool("--netmap-fixture", str(POLICY_MATCH))
    changed_policy = tmp_path / "changed-policy.hujson"
    changed_policy.write_text(POLICY.read_text(encoding="utf-8").replace('"proto":  "tcp"', '"proto":  "udp"', 1), encoding="utf-8")
    changed = subprocess.run(
        [sys.executable, str(SCRIPT), "--policy", str(changed_policy), "--netmap-fixture", str(POLICY_MATCH)],
        capture_output=True,
        check=False,
        text=True,
    )
    changed_output = json.loads(changed.stdout)

    assert first.returncode == 0
    assert second.returncode == 0
    assert first_output["policy_fingerprint"] == second_output["policy_fingerprint"]
    assert changed_output["policy_fingerprint"] != first_output["policy_fingerprint"]
