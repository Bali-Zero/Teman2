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

`audit_policy()` is the whole rule. The real policy must produce zero findings; every fixture in
fixtures/tailnet_acl/ must produce the specific finding it is named for. Innocence and guilt, per
infra/guard-conformance/ — a guard censused without both halves is not a guard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY = REPO_ROOT / "infra" / "tailscale" / "policy.hujson"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tailnet_acl"

# The port that carries `tailscale serve` on Pro, and therefore /term.
SHELL_PORT = "443"
SHELL_HOST = "pro"


def strip_hujson(text: str) -> str:
    """Strip `//` line comments and trailing commas — string-aware.

    A naive `re.sub(r'//.*', '', ...)` would truncate any policy value containing `//` (a URL,
    a path). The parser must not be the thing that lies about the file it is checking.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and text[i : i + 2] == "//":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    # Trailing commas before a closing brace/bracket.
    cleaned = "".join(out)
    result: list[str] = []
    for idx, ch in enumerate(cleaned):
        if ch == ",":
            rest = cleaned[idx + 1 :].lstrip()
            if rest[:1] in ("}", "]"):
                continue
        result.append(ch)
    return "".join(result)


def load_policy(text: str) -> dict:
    return json.loads(strip_hujson(text))


def audit_policy(text: str) -> list[str]:
    """Return a list of finding codes. Empty list == the policy is deny-by-default and honest."""
    findings: list[str] = []
    policy = load_policy(text)
    hosts = set(policy.get("hosts", {}))
    acls = policy.get("acls", [])

    for rule in acls:
        srcs = rule.get("src", [])
        dsts = rule.get("dst", [])

        if "*" in srcs:
            findings.append("WILDCARD_SRC")

        for dst in dsts:
            host, _, port = dst.rpartition(":")
            if host == "*" or dst == "*":
                findings.append("WILDCARD_DST_HOST")
            # A wildcard port is the blanket that hides the shell port inside it. Reject it
            # regardless of how narrow the host side looks — `user:*` is exactly how the first
            # draft granted pro:443 to six devices while reading as a tidy one-liner.
            if port == "*":
                findings.append("WILDCARD_DST_PORT")

        # A team-class device is a destination for support, never a source. One rule with it in
        # `src` re-opens the shell, the Redis and every sshd to a non-Zero laptop.
        if any(s.startswith("tag:team") for s in srcs):
            findings.append("TEAM_TAG_AS_SOURCE")

    # Whoever may open the shell port must be named one host at a time. A user, a group or an
    # autogroup on that line silently grows as devices are added to it.
    for rule in acls:
        for dst in rule.get("dst", []):
            if dst == f"{SHELL_HOST}:{SHELL_PORT}":
                for src in rule.get("src", []):
                    if src not in hosts:
                        findings.append("SHELL_PORT_SRC_NOT_A_NAMED_HOST")

    # The exposure must stay documented in the file that contains it, or the next reader inherits
    # a tidy-looking ACL with no idea which port is load-bearing.
    if "SHELL-ROUTE:" not in text:
        findings.append("SHELL_ROUTE_BLOCK_MISSING")
    else:
        for token in ("7681", "/term", "ttyd"):
            if token not in text:
                findings.append("SHELL_ROUTE_BLOCK_INCOMPLETE")

    # Tailscale SSH must never hand out root, and never reach a team device.
    for rule in policy.get("ssh", []):
        if "root" in rule.get("users", []):
            findings.append("SSH_ROOT_GRANT")
        if any(s.startswith("tag:team") for s in rule.get("src", [])):
            findings.append("TEAM_TAG_AS_SOURCE")

    # A policy with only accept-tests can report success and never failure.
    tests = policy.get("tests", [])
    if not any("deny" in t for t in tests):
        findings.append("NO_DENY_TEST")
    else:
        denied_for_team = {
            d for t in tests if t.get("src", "").startswith("tag:team") for d in t.get("deny", [])
        }
        if f"{SHELL_HOST}:{SHELL_PORT}" not in denied_for_team:
            findings.append("SHELL_PORT_NOT_DENY_TESTED_FOR_TEAM")

    return findings


# --------------------------------------------------------------------------------------------
# Innocence: the real policy passes.
# --------------------------------------------------------------------------------------------


def test_policy_file_exists_and_parses() -> None:
    assert POLICY.is_file(), f"{POLICY} is missing — the policy IS the artifact"
    policy = load_policy(POLICY.read_text(encoding="utf-8"))
    assert policy["acls"], "a policy with no acls denies everything including the fleet"


def test_real_policy_is_deny_by_default_and_names_the_shell() -> None:
    assert audit_policy(POLICY.read_text(encoding="utf-8")) == []


# --------------------------------------------------------------------------------------------
# Guilt: each fixture reintroduces exactly one defect and must be caught.
# --------------------------------------------------------------------------------------------

GUILT_CASES = [
    ("allow_all.hujson", "WILDCARD_DST_HOST"),
    ("port_wildcard.hujson", "WILDCARD_DST_PORT"),
    ("team_as_source.hujson", "TEAM_TAG_AS_SOURCE"),
    ("shell_route_undocumented.hujson", "SHELL_ROUTE_BLOCK_MISSING"),
    ("ssh_root_grant.hujson", "SSH_ROOT_GRANT"),
    ("no_deny_test.hujson", "NO_DENY_TEST"),
]


@pytest.mark.parametrize("filename,expected", GUILT_CASES)
def test_guilty_fixture_is_rejected(filename: str, expected: str) -> None:
    fixture = FIXTURES / filename
    assert fixture.is_file(), f"missing guilt fixture {fixture}"
    assert expected in audit_policy(fixture.read_text(encoding="utf-8"))


def test_comment_stripper_does_not_truncate_a_value_containing_a_double_slash() -> None:
    """The parser must not be the thing that lies. `//` inside a string is data, not a comment."""
    parsed = load_policy('{"hosts": {"a": "https://example.invalid/x"}} // trailing comment')
    assert parsed["hosts"]["a"] == "https://example.invalid/x"
