"""infra/tailscale/policy.hujson must stay deny-by-default, and must keep naming the shell.

Why this guard exists. The tailnet's live policy is the factory default: one packet-filter rule,
every node -> 0.0.0.0/0, all ports. On top of it `tailscale serve` on Pro publishes
`/term` -> 127.0.0.1:7681 (`ttyd -W zsh`, writable, no credential flag) to the whole tailnet. Not
a live breach — every node is Zero's own — but a hard blocker on the team expansion, and the kind
of exposure that comes back the moment someone "temporarily" widens a rule.

The first draft of the policy widened it by accident, not by malice: it granted
`antonellosiano@gmail.com -> antonellosiano@gmail.com:*`, which reads as "the fleet keeps talking
to itself" and means "every port on every owned device, including the shell port, forever, plus
any port anyone adds later". That is the failure this file makes loud.

HARDENED 2026-08-29 after a cross-family adversarial review (codex gpt-5.6-sol, xhigh) REJECTED
the first version of this guard with executed bypasses. Every one of those bypasses is now a
fixture below. The lesson driving the redesign: the first version matched on LEXICAL SHAPE — the
literal string `pro:443`, a src literally starting `tag:team` — so any equivalent spelling walked
straight past it. Tailscale offers many spellings of the same access:

  * the same node as an alias (`pro`) or as its magic IP (`100.107.22.111`);
  * the same port as `443`, as a list `22,443`, or inside a range `1-65535`;
  * the same team laptop as `tag:team-device` or as `autogroup:tagged`;
  * the same grant expressed in `acls`, in the newer `grants` block, or via the legacy
    `users`/`ports` fields — all three are valid and ADDITIVE.

So this guard now canonicalises before it judges, audits every access-granting surface, and
fails closed on any top-level key it does not know how to audit. `audit_policy()` is the whole
rule: the real policy must produce zero findings, and every fixture in fixtures/tailnet_acl/ must
produce the specific finding it is named for. Innocence and guilt, per infra/guard-conformance/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY = REPO_ROOT / "infra" / "tailscale" / "policy.hujson"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tailnet_acl"

# The node and port that carry `tailscale serve` on Pro, and therefore /term.
SHELL_HOST = "pro"
SHELL_PORT = 443

# Exactly which nodes may open the shell port. This is an ALLOWLIST, not a shape rule, and it is
# deliberately duplicated here rather than derived from the policy: widening the shell exposure
# then takes two edits in two files by two different intents, instead of one tidy-looking line in
# the policy. Caught by mutation 2026-08-29 — an earlier version only required the source to be
# *some* named node, so re-pointing `mini` at `pro:1-65535` stayed green while handing the
# least-attended machine on the fleet a writable shell.
SHELL_PORT_ALLOWED_SOURCES = {"m5", "iphone-14", "iphone175", "apple-vision-pro"}

# A port spec wider than this is a wildcard wearing a range's clothes (`1-65535`).
MAX_PORTS_PER_DST = 64

# Selectors that include a team-class device. `autogroup:tagged` is the one that bit us: it
# contains every tagged node, so it contains the team laptop, while looking nothing like
# `tag:team-device`. `autogroup:member` deliberately does NOT appear here — a tagged device is
# owned by the tailnet, not by a user, so it falls outside `member`. That exclusion is the
# mechanism the policy relies on, and it is why `member` is safe where `tagged` is not.
TEAM_REACHING_SOURCES = ("autogroup:tagged",)

# Top-level keys this guard knows how to audit, or that cannot grant network access. Anything
# else fails closed: a policy that grows a new access surface must grow an auditor for it in the
# same commit. This is the structural answer to "the auditor only looked at `acls`".
KNOWN_TOP_LEVEL_KEYS = {"hosts", "tagOwners", "groups", "acls", "ssh", "tests", "grants"}


# ---------------------------------------------------------------------------------------------
# HuJSON
# ---------------------------------------------------------------------------------------------


def _skip_ws_and_comments(text: str, i: int) -> int:
    while i < len(text):
        if text[i] in " \t\r\n":
            i += 1
        elif text[i : i + 2] == "//":
            while i < len(text) and text[i] != "\n":
                i += 1
        elif text[i : i + 2] == "/*":
            end = text.find("*/", i + 2)
            i = len(text) if end == -1 else end + 2
        else:
            break
    return i


def strip_hujson(text: str) -> str:
    """Strip `//` and `/* */` comments and trailing commas — string-aware throughout.

    The parser must not be the thing that lies about the file it checks. A naive regex would
    truncate any value containing `//`, and a non-string-aware trailing-comma pass would corrupt
    a value containing `,}` — both were real defects in the first version of this file.
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            j, escaped = i + 1, False
            while j < n:
                c = text[j]
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    break
                j += 1
            out.append(text[i : j + 1])
            i = j + 1
            continue
        if text[i : i + 2] == "//":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text[i : i + 2] == "/*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        if ch == ",":
            nxt = _skip_ws_and_comments(text, i + 1)
            if nxt < n and text[nxt] in "}]":
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def load_policy(text: str) -> dict:
    return json.loads(strip_hujson(text))


# ---------------------------------------------------------------------------------------------
# Canonicalisation — judge the access, not its spelling
# ---------------------------------------------------------------------------------------------


def _canon_node(token: str, hosts: dict) -> str:
    """`pro` and `100.107.22.111` are the same machine. Collapse them before comparing."""
    if token in hosts:
        return token
    for alias, ip in hosts.items():
        if token == ip:
            return alias
    return token


def _split_dst(dst: str) -> tuple[str, str]:
    host, sep, port = dst.rpartition(":")
    return (host, port) if sep else (dst, "")


def _port_spec_covers(spec: str, wanted: int) -> bool:
    """Does this port spec admit `wanted`? Handles `*`, lists and ranges, not just a bare int."""
    spec = spec.strip()
    if spec == "*":
        return True
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, _, hi = part.partition("-")
            try:
                if int(lo) <= wanted <= int(hi):
                    return True
            except ValueError:
                continue
        else:
            try:
                if int(part) == wanted:
                    return True
            except ValueError:
                continue
    return False


def _port_count(spec: str) -> int:
    """How many distinct ports does this spec admit? `*` and huge ranges are the same disease."""
    spec = spec.strip()
    if spec == "*":
        return 65535
    total = 0
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, _, hi = part.partition("-")
            try:
                total += max(0, int(hi) - int(lo) + 1)
            except ValueError:
                continue
        elif part:
            total += 1
    return total


def _is_team_reaching(src: str) -> bool:
    return src.startswith("tag:team") or src in TEAM_REACHING_SOURCES


def _grant_port_spec(entry: dict) -> str:
    """A `grants` entry carries its ports in `ip:` (e.g. `["tcp:443"]`), not in the dst."""
    specs = []
    for item in entry.get("ip", []):
        specs.append(item.split(":", 1)[1] if ":" in item else item)
    return ",".join(specs) if specs else "*"


def audit_policy(text: str) -> list[str]:
    """Return a list of finding codes. Empty list == deny-by-default and honest."""
    findings: list[str] = []
    policy = load_policy(text)
    hosts = policy.get("hosts", {})

    for key in policy:
        if key not in KNOWN_TOP_LEVEL_KEYS:
            findings.append("UNKNOWN_TOP_LEVEL_KEY")

    def audit_rule(srcs: list, dsts: list, port_spec_of, *, require_proto: bool, rule: dict):
        for src in srcs:
            if src == "*":
                findings.append("WILDCARD_SRC")
            if _is_team_reaching(src):
                findings.append("TEAM_TAG_AS_SOURCE")
        if require_proto and not str(rule.get("proto", "")).strip():
            # Without `proto`, a rule grants UDP alongside the TCP service it names, plus ICMP
            # between the pair — so "only SSH" would be false as written.
            findings.append("MISSING_PROTO")
        for dst in dsts:
            host, port = port_spec_of(dst)
            if host == "*" or dst == "*":
                findings.append("WILDCARD_DST_HOST")
            if port.strip() == "*":
                findings.append("WILDCARD_DST_PORT")
            if _port_count(port) > MAX_PORTS_PER_DST:
                findings.append("OVERBROAD_DST_PORT_RANGE")
            # Whoever may open the shell port must be a NAMED NODE (never a user, group or
            # autogroup, each of which silently grows as devices are added to it) AND must be on
            # the allowlist above.
            if _canon_node(host, hosts) == SHELL_HOST and _port_spec_covers(port, SHELL_PORT):
                for src in srcs:
                    canon = _canon_node(src, hosts)
                    if canon not in hosts:
                        findings.append("SHELL_PORT_SRC_NOT_A_NAMED_HOST")
                    elif canon not in SHELL_PORT_ALLOWED_SOURCES:
                        findings.append("SHELL_PORT_SRC_NOT_ALLOWLISTED")

    for rule in policy.get("acls", []):
        # `users`/`ports` are the legacy spelling of `src`/`dst` and are still honoured.
        srcs = list(rule.get("src", [])) + list(rule.get("users", []))
        dsts = list(rule.get("dst", [])) + list(rule.get("ports", []))
        audit_rule(srcs, dsts, _split_dst, require_proto=True, rule=rule)

    for grant in policy.get("grants", []):
        spec = _grant_port_spec(grant)
        audit_rule(
            list(grant.get("src", [])),
            list(grant.get("dst", [])),
            lambda d, _s=spec: (d, _s),
            require_proto=False,
            rule=grant,
        )

    for rule in policy.get("ssh", []):
        if "root" in rule.get("users", []):
            findings.append("SSH_ROOT_GRANT")
        if any(_is_team_reaching(s) for s in rule.get("src", [])):
            findings.append("TEAM_TAG_AS_SOURCE")
        if any(_is_team_reaching(d) for d in rule.get("dst", [])):
            findings.append("TEAM_TAG_AS_SSH_DESTINATION")

    # The exposure must stay documented in the file that contains it, or the next reader inherits
    # a tidy-looking ACL with no idea which port is load-bearing.
    if "SHELL-ROUTE:" not in text:
        findings.append("SHELL_ROUTE_BLOCK_MISSING")
    else:
        for token in ("7681", "/term", "ttyd"):
            if token not in text:
                findings.append("SHELL_ROUTE_BLOCK_INCOMPLETE")

    # A policy with only accept-tests can report success and never failure.
    tests = policy.get("tests", [])
    if not any("deny" in t for t in tests):
        findings.append("NO_DENY_TEST")
    else:
        denied = {
            d
            for t in tests
            if _is_team_reaching(str(t.get("src", "")))
            for d in t.get("deny", [])
        }
        if not any(
            _canon_node(_split_dst(d)[0], hosts) == SHELL_HOST
            and _port_spec_covers(_split_dst(d)[1], SHELL_PORT)
            for d in denied
        ):
            findings.append("SHELL_PORT_NOT_DENY_TESTED_FOR_TEAM")

    return findings


# ---------------------------------------------------------------------------------------------
# Innocence: the real policy passes.
# ---------------------------------------------------------------------------------------------


def test_policy_file_exists_and_parses() -> None:
    assert POLICY.is_file(), f"{POLICY} is missing — the policy IS the artifact"
    policy = load_policy(POLICY.read_text(encoding="utf-8"))
    assert policy["acls"], "a policy with no acls denies everything including the fleet"


def test_real_policy_is_deny_by_default_and_names_the_shell() -> None:
    assert audit_policy(POLICY.read_text(encoding="utf-8")) == []


# ---------------------------------------------------------------------------------------------
# Guilt: each fixture reintroduces exactly one defect and must be caught.
# ---------------------------------------------------------------------------------------------

GUILT_CASES = [
    ("allow_all.hujson", "WILDCARD_DST_HOST"),
    ("port_wildcard.hujson", "WILDCARD_DST_PORT"),
    ("team_as_source.hujson", "TEAM_TAG_AS_SOURCE"),
    ("shell_route_undocumented.hujson", "SHELL_ROUTE_BLOCK_MISSING"),
    ("ssh_root_grant.hujson", "SSH_ROOT_GRANT"),
    ("no_deny_test.hujson", "NO_DENY_TEST"),
    # Bypasses executed by the round-1 cross-family grader against the first version.
    ("grants_block_bypass.hujson", "TEAM_TAG_AS_SOURCE"),
    ("autogroup_tagged_source.hujson", "TEAM_TAG_AS_SOURCE"),
    ("shell_via_ip_literal.hujson", "SHELL_PORT_SRC_NOT_A_NAMED_HOST"),
    ("shell_via_port_range.hujson", "SHELL_PORT_SRC_NOT_A_NAMED_HOST"),
    ("legacy_users_ports.hujson", "TEAM_TAG_AS_SOURCE"),
    ("ssh_to_team_device.hujson", "TEAM_TAG_AS_SSH_DESTINATION"),
    ("missing_proto.hujson", "MISSING_PROTO"),
    ("unknown_top_level_key.hujson", "UNKNOWN_TOP_LEVEL_KEY"),
]


@pytest.mark.parametrize("filename,expected", GUILT_CASES)
def test_guilty_fixture_is_rejected(filename: str, expected: str) -> None:
    fixture = FIXTURES / filename
    assert fixture.is_file(), f"missing guilt fixture {fixture}"
    assert expected in audit_policy(fixture.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------
# The parser itself
# ---------------------------------------------------------------------------------------------


def test_stripper_keeps_a_double_slash_inside_a_string() -> None:
    parsed = load_policy('{"hosts": {"a": "https://example.invalid/x"}} // trailing comment')
    assert parsed["hosts"]["a"] == "https://example.invalid/x"


def test_stripper_handles_block_comments_and_commas_inside_strings() -> None:
    """Both were real defects: `/* */` failed to parse, and `,}` inside a string was corrupted."""
    parsed = load_policy('{/* block */ "hosts": {"a": "x,}y"}, }')
    assert parsed["hosts"]["a"] == "x,}y"


def test_canonicalisation_collapses_alias_and_ip() -> None:
    hosts = {"pro": "100.107.22.111"}
    assert _canon_node("100.107.22.111", hosts) == "pro"
    assert _port_spec_covers("22,443", SHELL_PORT)
    assert _port_spec_covers("1-65535", SHELL_PORT)
    assert not _port_spec_covers("22,5900", SHELL_PORT)
