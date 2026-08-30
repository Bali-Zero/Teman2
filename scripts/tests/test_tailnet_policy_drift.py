from __future__ import annotations

import importlib.util
import json
import pytest
import re
import tempfile
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


def test_old_schema_Bits_is_authoritative_when_the_address_has_no_prefix() -> None:
    """`Bits` was validated and then DISCARDED, under a comment claiming the address
    string already carried the prefix. True for `Net` (a CIDR); false for the old
    schema's `IP`, a bare address whose prefix lives only in `Bits`.

    Measured before the fix: {"IP": "10.0.0.1", "Bits": 8} yielded 10.0.0.1/32 instead
    of 10.0.0.0/8 — silently NARROWER, and narrowing an enforced grant is the direction
    that can make a broad reality compare equal to a narrow declaration and read CLEAN.
    """
    module = load_module()
    shapes = module.netmap_shapes({"PacketFilter": [{
        "SrcIPs": ["192.0.2.1/32"],
        "DstPorts": [{"IP": "10.0.0.1", "Bits": 8, "Ports": {"First": 0, "Last": 65535}}],
        "IPProto": [6]}]})

    assert {shape.destination for shape in shapes} == {"10.0.0.0/8"}


def test_a_prefix_that_contradicts_Bits_is_BLIND_not_a_silent_pick() -> None:
    """Two sources of the same fact that disagree are a way to be wrong twice. When the
    CIDR says /24 and Bits says 8, refusing to choose is the only answer consistent with
    this tool's polarity: uncertainty costs visibility, never correctness."""
    module = load_module()
    with pytest.raises(module.BlindError):
        module.netmap_shapes({"PacketFilter": [{
            "Srcs": ["192.0.2.1/32"],
            "Dsts": [{"Net": "10.0.0.0/24", "Bits": 8, "Ports": {"First": 0, "Last": 65535}}],
            "IPProto": [6]}]})


def test_every_verdict_declares_what_it_did_NOT_compare() -> None:
    """The known limit must travel with the verdict, CLEAN most of all.

    Blind cross-family refutation (Kimi K3) showed the comparison is satisfied when
    EVERY source is swapped for a node that should hold no grant: policy.hujson grants
    by identity, the netmap has already resolved identities to addresses, and mapping
    one to the other would need the node<->identity table this tool must never hold.
    That limit is real and is not closable here — so it is declared on every result
    rather than left in a docstring. A reader who takes CLEAN to mean "the right nodes
    have the right access" would be wrong, and the output now says so itself.
    """
    for fixture in (ALLOW_ALL, POLICY_MATCH):
        _, payload = run_tool("--netmap-fixture", str(fixture))
        scope = payload.get("comparison_scope", "")
        assert "SOURCE IDENTITY IS NOT COMPARED" in scope, payload


def test_the_known_source_blindness_is_reproducible_and_documented() -> None:
    """Pins the limitation itself, so a future change that silently NARROWS the
    comparison (making this pass for the wrong reason) or one that finally closes it
    both show up here rather than passing unnoticed."""
    module = load_module()
    fixture = json.loads(POLICY_MATCH.read_text())
    for rule in fixture["PacketFilter"]:
        rule["Srcs"] = ["198.51.100.254/32"]   # a node with no such grant

    declared = module.policy_shapes(module.parse_hujson(POLICY.read_text()))
    enforced = module.netmap_shapes(fixture)

    assert declared == enforced, (
        "source identity is now being compared — good, but COMPARISON_SCOPE and this "
        "test must be updated together so the declared limit stops overstating itself"
    )


def test_redaction_covers_ipv6_magicdns_and_the_blind_reason() -> None:
    """The redactor was IPv4-and-email only. That is blind to HALF of every node's
    identity here — a Tailscale netmap carries addresses in fd7a:115c:a1e0::/48 — and
    to node NAMES entirely, which the spec forbids in output by name. `reason` was not
    sanitised at all, and the proprioception harness forwards it into its own report,
    so anything interpolated there would have travelled one hop further than the
    person adding it was looking. Found by blind cross-family refutation (Kimi K3).

    Declared limit, kept deliberately: a BARE hostname with no domain is not matched.
    Widening the pattern until it catches those would also eat `policy.hujson` and
    `0-65535` and turn every evidence line into "redacted".
    """
    module = load_module()

    for leak in ("node fd7a:115c:a1e0::1 replied",
                 "node nuzantara.tail461666.ts.net replied",
                 "contact owner@example.com at 203.0.113.7"):
        assert module.sanitize_evidence(leak) == "redacted-sensitive-evidence", leak

    # ...and the real evidence lines must survive, or the redactor has eaten its output.
    for keep in ("declared: 8 rule-shapes (specific-source -> specific-destination; "
                 "ports: 22,443,4317,6379,8990,11434; protocols: tcp)",
                 "enforced: 1 rule-shapes (any-source -> internet-any; ports: all)"):
        assert module.sanitize_evidence(keep) == keep, keep


def test_a_blind_reason_carrying_an_address_is_redacted() -> None:
    """`reason` travels into the proprioception report, so it needs the same treatment
    as evidence. Exercised through the real process, so it is the shipped path."""
    command = (
        "import importlib.util,sys; "
        f"spec=importlib.util.spec_from_file_location('drift',{str(SCRIPT)!r}); "
        "m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; "
        "spec.loader.exec_module(m); "
        "m.emit_result('BLIND','0123456789abcdef',[],'could not reach 100.107.22.111')"
    )
    completed = subprocess.run([sys.executable, "-c", command],
                               capture_output=True, check=False, text=True)

    assert "100.107.22.111" not in completed.stdout
    assert json.loads(completed.stdout)["reason"] == "redacted-sensitive-evidence"


def test_an_unexpected_crash_is_BLIND_not_DIVERGED() -> None:
    """`main` caught only BlindError, so any other exception exited 1 — and exit 1 IS
    DIVERGED. The harness then filed real, actionable drift for a probe that had
    determined nothing, with zero evidence to explain it. A crash is not a finding."""
    deep = '{"hosts":{"db":"10.0.0.1"},"acls":' + "[" * 400 + "]" * 400 + "}"
    policy = Path(tempfile.mkstemp(suffix=".hujson")[1])
    policy.write_text(deep, encoding="utf-8")
    try:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--policy", str(policy),
             "--netmap-fixture", str(ALLOW_ALL)],
            capture_output=True, check=False, text=True)
        assert completed.returncode == 2, completed.stderr[:400]
        assert json.loads(completed.stdout)["verdict"] == "BLIND"
        assert "Traceback" not in completed.stderr
    finally:
        policy.unlink(missing_ok=True)


def test_any_unexpected_exception_is_BLIND_and_leaks_no_message(capsys, monkeypatch) -> None:
    """The RecursionError case above exercises a NAMED clause. This one exercises the
    generic backstop, which is the whole point of it: every malformed policy I could
    craft is already caught as BlindError (the validation is thorough), so the only
    honest way to reach the backstop is to force an exception it was never told about.

    Also pins that `str(error)` is NOT emitted: an exception message is the likeliest
    place for an address or a filesystem path to appear, and this output lands in a
    public repo. The type name is enough to find the cause.
    """
    module = load_module()

    def explode(*_args, **_kwargs):
        raise RuntimeError("boom /Users/someone/secret-path 100.107.22.111")

    monkeypatch.setattr(module, "policy_shapes", explode)
    status = module.main(["--policy", str(POLICY), "--netmap-fixture", str(ALLOW_ALL)])
    payload = json.loads(capsys.readouterr().out)

    assert status == 2
    assert payload["verdict"] == "BLIND"
    assert payload["reason"] == "UNEXPECTED_RuntimeError"
    assert "boom" not in json.dumps(payload)
    assert "100.107.22.111" not in json.dumps(payload)


def test_coverage_canonicalisation_is_actually_WIRED_to_the_verdict(tmp_path: Path) -> None:
    """The unit test above proves canonical_coverage() computes the right thing; this
    one proves main() USES it. Reverting the call site to a raw set comparison left
    every other case green — a fix that is correct and unreachable is not a fix."""
    policy = tmp_path / "split.hujson"
    policy.write_text(
        '{"hosts":{"db":"10.1.0.0/24"},'
        '"acls":[{"action":"accept","proto":"tcp","src":["*"],"dst":["db:5432-5433"]}]}',
        encoding="utf-8")
    netmap = tmp_path / "split-netmap.json"
    netmap.write_text(json.dumps({"PacketFilter": [{
        "Srcs": ["0.0.0.0/0"], "SrcCaps": None, "Caps": [], "IPProto": [6],
        "Dsts": [{"Net": "10.1.0.0/24", "Ports": {"First": 5432, "Last": 5432}},
                 {"Net": "10.1.0.0/24", "Ports": {"First": 5433, "Last": 5433}}]}]}),
        encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--policy", str(policy),
         "--netmap-fixture", str(netmap)],
        capture_output=True, check=False, text=True)

    assert completed.returncode == 0, completed.stdout
    assert json.loads(completed.stdout)["verdict"] == "CLEAN"


def test_star_destination_resolves_instead_of_going_blind(tmp_path: Path) -> None:
    """`*:*` is the commonest ACL spelling and it is unambiguous. Treating it as an
    unknown host alias made the tool answer BLIND on a fully readable, VALID policy —
    and made the registry's fix_hint ("BLIND means the enforced state could not be
    read") false, because the cause was a tool-side gap, not lost visibility."""
    policy = tmp_path / "star.hujson"
    policy.write_text(
        '{"hosts":{"db":"10.1.0.0/24"},'
        '"acls":[{"action":"accept","proto":"tcp","src":["*"],"dst":["*:*"]}]}',
        encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--policy", str(policy),
         "--netmap-fixture", str(ALLOW_ALL)],
        capture_output=True, check=False, text=True)

    assert completed.returncode != 2, "a resolvable policy must not be BLIND"
    assert json.loads(completed.stdout)["verdict"] in ("CLEAN", "DIVERGED")


def test_a_broad_source_is_not_called_specific() -> None:
    """The comparison is source-blind by construction, but the one source signal it DOES
    carry must not point the wrong way: `autogroup:member` is every user device on the
    tailnet, and calling that "specific-source" let a tailnet-wide grant read like a
    single named host."""
    module = load_module()
    assert module._source_class(["autogroup:member"]) == "broad-source"
    assert module._source_class(["group:eng"]) == "broad-source"
    assert module._source_class(["100.64.0.1"]) == "specific-source"
    assert module._source_class(["*"]) == "any-source"


def test_a_comment_is_whitespace_not_nothing() -> None:
    """Deleting a comment outright concatenates the tokens on either side: `{"a": 1/**/2}`
    became `{"a": 12}`, which parses cleanly as a DIFFERENT document with a different
    value and a different fingerprint. Invalid input must cost visibility, never be
    silently reinterpreted into a valid document."""
    module = load_module()
    assert module.strip_hujson('{"a": 1/**/2}') == '{"a": 1 2}'
    with pytest.raises(module.BlindError):
        module.parse_hujson('{"a": 1/**/2}')


def test_identical_coverage_split_differently_is_CLEAN_not_DIVERGED() -> None:
    """Whether this receptor can EVER report CLEAN after an operator applies the policy
    must not depend on how tailscaled happens to split port ranges and protocol lists.
    A CLEAN signal unstable under the applicator's own normalisation is one nobody can
    trust; a receptor permanently stuck on DIVERGED is one people learn to ignore."""
    module = load_module()
    shape = module.RuleShape
    one_range = {shape("specific-source", "10.1.0.0/24", 5432, 5433, (6,))}
    split_range = {shape("specific-source", "10.1.0.0/24", 5432, 5432, (6,)),
                   shape("specific-source", "10.1.0.0/24", 5433, 5433, (6,))}
    one_proto = {shape("specific-source", "10.1.0.0/24", 22, 22, (6, 17))}
    split_proto = {shape("specific-source", "10.1.0.0/24", 22, 22, (6,)),
                   shape("specific-source", "10.1.0.0/24", 22, 22, (17,))}
    with_gap = {shape("specific-source", "10.1.0.0/24", 5432, 5432, (6,)),
                shape("specific-source", "10.1.0.0/24", 5435, 5435, (6,))}

    assert module.canonical_coverage(one_range) == module.canonical_coverage(split_range)
    assert module.canonical_coverage(one_proto) == module.canonical_coverage(split_proto)
    # ...and a real GAP must still differ, or the merge has erased a difference.
    assert module.canonical_coverage(one_range) != module.canonical_coverage(with_gap)


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
