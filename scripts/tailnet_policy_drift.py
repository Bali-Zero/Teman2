#!/usr/bin/env python3
"""Compare declared Tailscale ACL rule shapes with the local packet filter.

This is deliberately read-only.  The current fleet's recorded default allow-all
filter diverges from infra/tailscale/policy.hujson; that is expected until an
operator applies the policy in the Tailscale admin console.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


VERDICT_CLEAN = "CLEAN"
VERDICT_DIVERGED = "DIVERGED"
VERDICT_BLIND = "BLIND"

_EMAIL_RE = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_IP_RE = re.compile(
    r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?(?![\w.])"
)
# IPv6, and this is not a hypothetical here: a Tailscale netmap carries addresses in
# fd7a:115c:a1e0::/48, so an IPv4-only redactor is blind to HALF of every node's
# identity. Found by blind cross-family refutation (Kimi K3). Deliberately loose --
# any run of hex groups separated by colons, with or without a prefix -- because this
# is a redactor: over-matching costs a legible evidence line, under-matching publishes
# a node address in a public repo.
_IPV6_RE = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?:/\d{1,3})?(?![\w:])")
# MagicDNS names. The spec forbids a NODE NAME in output, and neither of the two
# patterns above sees one: `nuzantara.tail461666.ts.net` is not an address.
# Scoped to the ts.net suffix on purpose -- a general "anything dotted" rule would
# redact `policy.hujson` and `0-65535`, turning every evidence line into noise. That
# leaves a bare hostname with no domain unmatched, which is a declared LIMIT rather
# than an oversight: no code path here emits one, and the fix for that would be to
# stop building evidence from untrusted strings, not to widen this regex until it
# eats its own output.
_MAGICDNS_RE = re.compile(r"(?<![\w.])[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.ts\.net\b")
_PROTO_NAMES = {1: "icmp", 6: "tcp", 17: "udp"}


class BlindError(Exception):
    """An input was not safe enough to interpret as an enforced policy."""


@dataclass(frozen=True, order=True)
class RuleShape:
    """Comparable rule form; values never leave this process unredacted."""

    source_class: str
    destination: str
    first_port: int
    last_port: int
    protocols: tuple[int, ...]


def strip_hujson(source: str) -> str:
    """Remove HuJSON comments and trailing commas without touching string content."""

    without_comments: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(source):
        character = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if in_string:
            without_comments.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                # A SINGLE backslash. The original compared a one-character slice
                # against "\\\\", a TWO-character literal, so this branch could never
                # be taken: an escaped quote inside a string ended the string early and
                # everything after it was re-scanned as structure. Measured before the
                # fix: {"a": "he said \\" // x", "b": 1} truncated to
                # {"a": "he said \\" and raised JSONDecodeError. It fails toward BLIND
                # rather than CLEAN, so it was never a security hole -- but it would
                # make the receptor blind on a perfectly valid policy, which is the
                # same lost visibility by a slower route.
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
            without_comments.append(character)
            index += 1
        elif character == "/" and following == "/":
            index += 2
            while index < len(source) and source[index] not in "\r\n":
                index += 1
        elif character == "/" and following == "*":
            end = source.find("*/", index + 2)
            if end == -1:
                raise BlindError("POLICY_HUJSON_UNTERMINATED_COMMENT")
            index = end + 2
        else:
            without_comments.append(character)
            index += 1

    uncommented = "".join(without_comments)
    normalized: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(uncommented):
        character = uncommented[index]
        if in_string:
            normalized.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
            normalized.append(character)
        elif character == ",":
            cursor = index + 1
            while cursor < len(uncommented) and uncommented[cursor].isspace():
                cursor += 1
            if cursor >= len(uncommented) or uncommented[cursor] not in "}]":
                normalized.append(character)
        else:
            normalized.append(character)
        index += 1
    return "".join(normalized)


def parse_hujson(source: str) -> dict[str, Any]:
    """Parse the small HuJSON subset used by the checked-in ACL policy."""

    try:
        parsed = json.loads(strip_hujson(source))
    except json.JSONDecodeError as error:
        raise BlindError("POLICY_HUJSON_PARSE_FAILED") from error
    if not isinstance(parsed, dict):
        raise BlindError("POLICY_ROOT_NOT_OBJECT")
    return parsed


def policy_fingerprint(policy: dict[str, Any]) -> str:
    """Return a stable short hash of normalized, parsed policy content."""

    normalized = json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _parse_port_range(value: str) -> tuple[int, int]:
    if value == "*":
        return 0, 65535
    if value.isdecimal():
        port = int(value)
        if 0 <= port <= 65535:
            return port, port
    if value.count("-") == 1:
        first_text, last_text = value.split("-", 1)
        if first_text.isdecimal() and last_text.isdecimal():
            first, last = int(first_text), int(last_text)
            if 0 <= first <= last <= 65535:
                return first, last
    raise BlindError("POLICY_PORT_SHAPE_UNSUPPORTED")


def _policy_protocols(value: Any) -> tuple[int, ...]:
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or not values or not all(isinstance(item, str) for item in values):
        raise BlindError("POLICY_PROTOCOL_SHAPE_UNSUPPORTED")
    protocol_numbers = {name: number for number, name in _PROTO_NAMES.items()}
    try:
        return tuple(sorted({protocol_numbers[item.lower()] for item in values}))
    except KeyError as error:
        raise BlindError("POLICY_PROTOCOL_SHAPE_UNSUPPORTED") from error


def _source_class(sources: list[Any]) -> str:
    if not sources or not all(isinstance(source, str) for source in sources):
        raise BlindError("POLICY_SOURCE_SHAPE_UNSUPPORTED")
    if "*" in sources:
        if len(sources) != 1:
            raise BlindError("POLICY_SOURCE_SHAPE_UNSUPPORTED")
        return "any-source"
    return "specific-source"


def policy_shapes(policy: dict[str, Any]) -> set[RuleShape]:
    """Reduce static ACL grants to rule shapes, deliberately ignoring identities.

    Tailscale expands an unbound tag destination to no concrete packet-filter
    entry.  It therefore has no local IP/CIDR shape until a tagged device exists,
    and is excluded here rather than guessed at.
    """

    hosts = policy.get("hosts")
    rules = policy.get("acls")
    if not isinstance(hosts, dict) or not isinstance(rules, list):
        raise BlindError("POLICY_ACL_SHAPE_UNSUPPORTED")
    host_networks: dict[str, str] = {}
    for alias, address in hosts.items():
        if not isinstance(alias, str) or not isinstance(address, str):
            raise BlindError("POLICY_HOSTS_SHAPE_UNSUPPORTED")
        try:
            host_networks[alias] = str(ipaddress.ip_network(address, strict=False))
        except ValueError as error:
            raise BlindError("POLICY_HOSTS_SHAPE_UNSUPPORTED") from error

    shapes: set[RuleShape] = set()
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("action") != "accept":
            raise BlindError("POLICY_ACL_RULE_SHAPE_UNSUPPORTED")
        source = _source_class(rule.get("src"))
        protocols = _policy_protocols(rule.get("proto"))
        destinations = rule.get("dst")
        if not isinstance(destinations, list) or not destinations or not all(isinstance(item, str) for item in destinations):
            raise BlindError("POLICY_DESTINATION_SHAPE_UNSUPPORTED")
        for destination in destinations:
            if ":" not in destination:
                raise BlindError("POLICY_DESTINATION_SHAPE_UNSUPPORTED")
            target, port_text = destination.rsplit(":", 1)
            first_port, last_port = _parse_port_range(port_text)
            if target.startswith("tag:"):
                continue
            try:
                target_network = host_networks[target]
            except KeyError as error:
                raise BlindError("POLICY_DESTINATION_SHAPE_UNSUPPORTED") from error
            shapes.add(RuleShape(source, target_network, first_port, last_port, protocols))
    if not shapes:
        raise BlindError("POLICY_HAS_NO_CONCRETE_ACL_SHAPES")
    return shapes


def _netmap_source_class(value: Any) -> str:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise BlindError("NETMAP_SOURCE_SHAPE_UNSUPPORTED")
    if "*" in value:
        if len(value) != 1:
            raise BlindError("NETMAP_SOURCE_SHAPE_UNSUPPORTED")
        return "any-source"
    for source in value:
        try:
            ipaddress.ip_network(source, strict=False)
        except ValueError as error:
            raise BlindError("NETMAP_SOURCE_SHAPE_UNSUPPORTED") from error
    return "specific-source"


def _netmap_protocols(value: Any) -> tuple[int, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, int) and not isinstance(item, bool) for item in value):
        raise BlindError("NETMAP_PROTOCOL_SHAPE_UNSUPPORTED")
    if any(item < 0 or item > 255 for item in value):
        raise BlindError("NETMAP_PROTOCOL_SHAPE_UNSUPPORTED")
    return tuple(sorted(set(value)))


def _netmap_rule_fields(rule: dict) -> tuple[Any, Any]:
    """Return (sources, destinations) for either PacketFilter schema.

    MEASURED on this fleet 2026-08-31 with `tailscale debug netmap`: the live rule
    carries `Srcs` (a list of CIDR strings) and `Dsts` (a list of
    {"Net": "<cidr>", "Ports": {"First": n, "Last": n}}), alongside `IPProto`,
    `SrcCaps` and `Caps`.

    The first version of this file parsed only `SrcIPs`/`DstPorts` -- an older shape
    that this tailnet does not emit. It behaved CORRECTLY in the sense that mattered
    (it answered BLIND rather than guessing), but it was blind on every real node, and
    its fixtures encoded a schema that does not exist, so the corpus was proving the
    tool against a format it would never meet. Both schemas are accepted now; the newer
    one is what the fleet actually speaks.

    Unknown shape still raises BLIND. That polarity is the whole design: a schema guess
    that is wrong must cost visibility, never correctness.
    """
    if "Srcs" in rule or "Dsts" in rule:
        return rule.get("Srcs"), rule.get("Dsts")
    return rule.get("SrcIPs"), rule.get("DstPorts")


def _netmap_destination(destination: Any) -> tuple[str, int, int]:
    """One destination -> (network, first_port, last_port), for either schema.

    `Net` is the live key; `IP` is the older one.

    `Bits` IS AUTHORITATIVE when the address carries no prefix of its own, and an
    earlier version of this function got that exactly backwards: it validated `Bits`
    and then discarded it under a comment claiming "the CIDR string already carries
    the prefix length". That is true for `Net` (a CIDR string) and FALSE for the old
    schema's `IP`, which is a bare address whose prefix lives only in `Bits`.
    Measured: {"IP": "10.0.0.1", "Bits": 8} produced 10.0.0.1/32 instead of
    10.0.0.0/8 -- a silently NARROWER network, and narrowing an enforced grant is the
    direction that can make a broad reality compare equal to a narrow declaration and
    read CLEAN. Found by blind cross-family refutation (Kimi K3).

    When BOTH are present and they disagree, the answer is BLIND rather than a pick:
    two sources of the same fact that contradict each other are a way to be wrong
    twice, and this tool's whole polarity is that uncertainty costs visibility, never
    correctness.
    """
    if not isinstance(destination, dict):
        raise BlindError("NETMAP_DESTINATION_SHAPE_UNSUPPORTED")
    address = destination.get("Net", destination.get("IP"))
    ports = destination.get("Ports")
    if not isinstance(address, str) or not isinstance(ports, dict):
        raise BlindError("NETMAP_DESTINATION_SHAPE_UNSUPPORTED")
    bits = destination.get("Bits")
    if bits is not None and (not isinstance(bits, int) or isinstance(bits, bool) or bits < 0):
        raise BlindError("NETMAP_DESTINATION_SHAPE_UNSUPPORTED")
    first, last = ports.get("First"), ports.get("Last")
    if (
        not isinstance(first, int)
        or isinstance(first, bool)
        or not isinstance(last, int)
        or isinstance(last, bool)
        or not 0 <= first <= last <= 65535
    ):
        raise BlindError("NETMAP_DESTINATION_SHAPE_UNSUPPORTED")
    try:
        if "/" in address:
            network = ipaddress.ip_network(address, strict=False)
            if bits is not None and bits != network.prefixlen:
                # The two disagree. Refuse to choose.
                raise BlindError("NETMAP_DESTINATION_PREFIX_CONFLICT")
        elif bits is not None:
            network = ipaddress.ip_network(f"{address}/{bits}", strict=False)
        else:
            network = ipaddress.ip_network(address, strict=False)
    except BlindError:
        raise
    except ValueError as error:
        raise BlindError("NETMAP_DESTINATION_SHAPE_UNSUPPORTED") from error
    return str(network), first, last


def netmap_shapes(netmap: Any) -> set[RuleShape]:
    """Reduce an enforced PacketFilter to comparable rule SHAPES.

    Both the live schema (`Srcs`/`Dsts`) and the older one (`SrcIPs`/`DstPorts`) are
    accepted; anything else is BLIND. Losing visibility is always safer here than
    claiming a clean comparison from a guessed parse.
    """

    packet_filter = netmap if isinstance(netmap, list) else netmap.get("PacketFilter") if isinstance(netmap, dict) else None
    if not isinstance(packet_filter, list):
        raise BlindError("NETMAP_PACKET_FILTER_MISSING_OR_INVALID")
    shapes: set[RuleShape] = set()
    for rule in packet_filter:
        if not isinstance(rule, dict):
            raise BlindError("NETMAP_RULE_SHAPE_UNSUPPORTED")
        raw_sources, destinations = _netmap_rule_fields(rule)
        source = _netmap_source_class(raw_sources)
        protocols = _netmap_protocols(rule.get("IPProto"))
        if not isinstance(destinations, list) or not destinations:
            raise BlindError("NETMAP_DESTINATION_SHAPE_UNSUPPORTED")
        for destination in destinations:
            network, first, last = _netmap_destination(destination)
            shapes.add(RuleShape(source, network, first, last, protocols))
    if not shapes:
        raise BlindError("NETMAP_PACKET_FILTER_EMPTY")
    return shapes


def sanitize_evidence(value: str) -> str:
    """Reject sensitive-looking strings before they can enter public output.

    Whole-string rejection rather than substring replacement: a partially-scrubbed
    line invites the reader to trust the rest of it, and this output lands in a
    public repo.
    """

    if not isinstance(value, str):
        return "redacted-sensitive-evidence"
    for pattern in (_EMAIL_RE, _IP_RE, _IPV6_RE, _MAGICDNS_RE):
        if pattern.search(value):
            return "redacted-sensitive-evidence"
    return value


def _port_description(shapes: Iterable[RuleShape]) -> str:
    ranges = sorted({(shape.first_port, shape.last_port) for shape in shapes})
    rendered = ["all" if first == 0 and last == 65535 else str(first) if first == last else f"{first}-{last}" for first, last in ranges]
    return ",".join(rendered)


def _protocol_description(shapes: Iterable[RuleShape]) -> str:
    values = sorted({protocol for shape in shapes for protocol in shape.protocols})
    return ",".join(_PROTO_NAMES.get(value, f"protocol-{value}") for value in values)


def describe_shapes(label: str, shapes: set[RuleShape]) -> str:
    source_classes = "/".join(sorted({shape.source_class for shape in shapes}))
    destinations = {shape.destination for shape in shapes}
    destination_class = "internet-any" if destinations == {"0.0.0.0/0"} else "specific-destination"
    return sanitize_evidence(
        f"{label}: {len(shapes)} rule-shapes ({source_classes} -> {destination_class}; "
        f"ports: {_port_description(shapes)}; protocols: {_protocol_description(shapes)})"
    )


#: What a CLEAN verdict does and does NOT assert. Emitted with every result.
#
# The two sides speak different vocabularies and no amount of care closes that here:
# policy.hujson grants by IDENTITY (users, groups, tag:*), while the netmap has already
# RESOLVED those identities into node CIDRs. Mapping one to the other would require this
# tool to hold the node<->identity table -- exactly the data it is forbidden to touch or
# emit. So sources are compared only as any-vs-specific.
#
# Measured consequence, found by blind cross-family refutation (Kimi K3): take the
# matching fixture, replace EVERY source with a node that should hold no grant at all,
# and the comparison still reports equal. A reader who takes CLEAN to mean "the right
# nodes have the right access" would be wrong. So the scope travels with every verdict
# instead of living in a docstring nobody reads at 03:00.
COMPARISON_SCOPE = (
    "destination-network + port-range + protocol-set, and source only as "
    "any-vs-specific; SOURCE IDENTITY IS NOT COMPARED (policy grants by identity, "
    "the netmap has already resolved identities to addresses)"
)


def emit_result(
    verdict: str,
    fingerprint: str | None,
    evidence: Iterable[str] = (),
    reason: str | None = None,
) -> int:
    """Write the stable public result and return its prescribed process status."""

    payload: dict[str, Any] = {
        "verdict": verdict,
        "policy_fingerprint": fingerprint,
        "evidence": [sanitize_evidence(item) for item in evidence],
        # Travels with EVERY verdict, CLEAN included -- especially CLEAN. A limit a
        # reader has to go looking for is a limit that gets forgotten.
        "comparison_scope": COMPARISON_SCOPE,
    }
    if verdict == VERDICT_BLIND:
        # Sanitised like evidence. Every reason this tool emits today is a constant, so
        # nothing leaks right now -- but `reason` is the field a future contributor
        # reaches for when they want to say WHY, which is exactly when an address or a
        # hostname gets interpolated. The proprioception harness also forwards `reason`
        # into its own report, so an unsanitised value would travel one hop further
        # than the person adding it was looking.
        payload["reason"] = sanitize_evidence(reason or "UNKNOWN_BLIND_REASON")
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return {VERDICT_CLEAN: 0, VERDICT_DIVERGED: 1, VERDICT_BLIND: 2}[verdict]


def _read_fixture(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise BlindError("NETMAP_FIXTURE_UNREADABLE") from error
    except OSError as error:
        raise BlindError("NETMAP_FIXTURE_UNREADABLE") from error
    except UnicodeDecodeError as error:
        raise BlindError("NETMAP_FIXTURE_UNREADABLE") from error
    except json.JSONDecodeError as error:
        raise BlindError("NETMAP_FIXTURE_PARSE_FAILED") from error


def _read_live_netmap() -> Any:
    try:
        completed = subprocess.run(
            ["tailscale", "debug", "netmap"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError as error:
        raise BlindError("TAILSCALE_UNAVAILABLE") from error
    except (OSError, subprocess.SubprocessError) as error:
        raise BlindError("NETMAP_COMMAND_FAILED") from error
    try:
        return json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError) as error:
        raise BlindError("NETMAP_COMMAND_OUTPUT_INVALID") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Tailscale policy drift check.",
        epilog="The recorded live default allow-all fleet policy is expected to report DIVERGED until an operator applies the declared policy.",
    )
    parser.add_argument("--policy", required=True, type=Path, help="Declared HuJSON ACL policy")
    parser.add_argument("--netmap-fixture", type=Path, help="Recorded sanitized netmap; makes no subprocess call")
    parser.add_argument("--json", action="store_true", help="Retained for explicit machine-readable invocation")
    args = parser.parse_args(argv)

    fingerprint: str | None = None
    try:
        try:
            policy_source = args.policy.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise BlindError("POLICY_UNREADABLE") from error
        policy = parse_hujson(policy_source)
        fingerprint = policy_fingerprint(policy)
        declared = policy_shapes(policy)
        netmap = _read_fixture(args.netmap_fixture) if args.netmap_fixture else _read_live_netmap()
        enforced = netmap_shapes(netmap)
    except BlindError as error:
        return emit_result(VERDICT_BLIND, fingerprint, reason=str(error))

    evidence = [describe_shapes("declared", declared), describe_shapes("enforced", enforced)]
    verdict = VERDICT_CLEAN if declared == enforced else VERDICT_DIVERGED
    return emit_result(verdict, fingerprint, evidence)


if __name__ == "__main__":
    sys.exit(main())
