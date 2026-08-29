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

HARDENED AGAIN 2026-08-29 by the independent Gear-3 gate, which ran the same lens down the
DESTINATION column that round 1 had run down the source column, and found three more live
bypasses: a second `hosts` alias for Pro's IP, `antonellosiano@gmail.com:443` (the historical
defect with one character class changed), and `autogroup:member:443`. All three were green.

So this guard canonicalises every spelling of a node to its IP before judging, and FAILS CLOSED
twice over: on any top-level key it cannot audit, and on any destination selector it cannot
resolve to a node. That second one is the general answer to the whole family — a destination the
guard cannot resolve is treated as possibly being the shell host, rather than skipped.

It is not, and cannot be, a Tailscale evaluator: it does not know what a `group:` expands to, and
it takes no position on selectors it has never seen beyond refusing them. `audit_policy()` is the
whole rule: the real policy must produce zero findings, and every fixture in fixtures/tailnet_acl/
must produce the specific finding it is named for. Innocence and guilt, per
infra/guard-conformance/.
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
SHELL_HOST_IP = "100.107.22.111"
SHELL_PORT = 443

# Exactly which nodes may open the shell port. This is an ALLOWLIST, not a shape rule, and it is
# deliberately duplicated here rather than derived from the policy: widening the shell exposure
# for a KNOWN NODE then takes two edits in two files instead of one tidy-looking line in the
# policy. (Scoped honestly, round-2 gate: this is not a general two-key lock — a destination the
# guard cannot resolve is refused outright by UNRESOLVABLE_DST_SELECTOR, which is what actually
# covers the non-node spellings.) Caught by mutation 2026-08-29 — an earlier version required
# only that the source be
# *some* named node, so re-pointing `mini` at `pro:1-65535` stayed green while handing the
# least-attended machine on the fleet a writable shell.
SHELL_PORT_ALLOWED_SOURCES = {"m5", "iphone-14", "iphone175", "apple-vision-pro"}

# A port spec wider than this is a wildcard wearing a range's clothes (`1-65535`).
MAX_PORTS_PER_DST = 64

# The only destination selectors that are allowed NOT to resolve to a node in `hosts`. A team
# device has no magic IP until it enrols, so the tag is the only way to express the support
# direction — and it is safe precisely because a tagged device is the thing being fenced.
# Everything else (a user, a `group:`, an `autogroup:`, a CIDR, an unknown tag) is rejected:
# see UNRESOLVABLE_DST_SELECTOR below for why.
ALLOWED_NON_NODE_DSTS = {"tag:team-device"}

# The mirror of the above on the SOURCE axis. This policy's design has no user or group sources
# at all — every acl src is a fleet node — so anything else is a finding. A `group:` or a bare
# user as a src was green before this existed: `group:team -> mini:22,6379,11434` handed Redis,
# Ollama and sshd on Mini to a non-tagged teammate identity.
ALLOWED_NON_NODE_SRCS: set = set()

# The ssh block is allowlisted on all three axes (see audit_policy). These are exactly the values
# the shipped policy uses and Tailscale's own default policy documents.
SSH_ALLOWED_SRCS = {"autogroup:member"}
SSH_ALLOWED_DSTS = {"autogroup:self"}
SSH_ALLOWED_USERS = {"autogroup:nonroot"}

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
    """Collapse every spelling of a machine to its IP — the one identity that cannot be aliased.

    Canonicalising to the ALIAS was the round-2 gate's finding A: `hosts` could simply grow a
    second name for the same IP (`"pro-deck": "100.107.22.111"`), and an alias-keyed comparison
    treats it as a different machine. The IP is the node; the alias is a label for it.
    """
    if token in hosts:
        return hosts[token]
    if token in set(hosts.values()):
        return token
    return token


def _is_node(token: str, hosts: dict) -> bool:
    return _canon_node(token, hosts) in set(hosts.values())


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


def _allowed_shell_ips(hosts: dict) -> set:
    """The allowlist, resolved to IPs — so a renamed or duplicated alias cannot smuggle a node in."""
    return {hosts[a] for a in SHELL_PORT_ALLOWED_SOURCES if a in hosts}


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

    # The shell anchor is an IP, not a name. Pinning it here closes the last spelling: re-pointing
    # the `pro` alias at a decoy address moved the anchor, and the real Pro's 443 became
    # unguarded while every other check stayed green.
    if hosts.get(SHELL_HOST) != SHELL_HOST_IP:
        findings.append("SHELL_HOST_IP_MOVED")

    def audit_rule(srcs: list, dsts: list, port_spec_of, *, require_proto: bool, rule: dict):
        for src in srcs:
            if src == "*":
                findings.append("WILDCARD_SRC")
            if _is_team_reaching(src):
                findings.append("TEAM_TAG_AS_SOURCE")
            # Mirror of UNRESOLVABLE_DST_SELECTOR on the source axis.
            elif not _is_node(src, hosts) and src not in ALLOWED_NON_NODE_SRCS:
                findings.append("UNRESOLVABLE_SRC_SELECTOR")
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
            # FAIL CLOSED ON THE DESTINATION AXIS (round-2 gate, findings B/C/E). The shell
            # check below can only fire on a destination it can RESOLVE to a node. A user, a
            # `group:`, an `autogroup:`, a CIDR or an unknown tag resolves to nothing — and the
            # first version simply skipped them, so `antonellosiano@gmail.com:443` (the
            # historical defect, merely de-wildcarded) and `autogroup:member:443` both handed
            # every node the shell while the guard reported green. An unresolvable destination
            # is therefore treated as possibly covering the shell host, exactly as an unknown
            # top-level key is treated as possibly granting access.
            if not _is_node(host, hosts) and host not in ALLOWED_NON_NODE_DSTS:
                findings.append("UNRESOLVABLE_DST_SELECTOR")
            # Whoever may open the shell port must be a NAMED NODE (never a user, group or
            # autogroup, each of which silently grows as devices are added to it) AND must be on
            # the allowlist above.
            if _canon_node(host, hosts) == hosts.get(SHELL_HOST) and _port_spec_covers(
                port, SHELL_PORT
            ):
                for src in srcs:
                    if not _is_node(src, hosts):
                        findings.append("SHELL_PORT_SRC_NOT_A_NAMED_HOST")
                    elif _canon_node(src, hosts) not in _allowed_shell_ips(hosts):
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

    # The ssh block gets ALLOWLISTS on all three axes, not a denylist on one of them. Two
    # independent gates converged on this: the block never passed through audit_rule at all, so
    # `src: ["*"]` / `dst: ["*"]` returned clean — and `users: ["root"]` was caught only because
    # "root" is the one literal that was ever spelled out, while `users: ["*"]` (strictly wider,
    # and a superset of `autogroup:tagged`) sailed through. A denylist on the axis that hands out
    # shells is the same mistake this whole file exists to stop.
    for rule in policy.get("ssh", []):
        for src in rule.get("src", []):
            if src not in SSH_ALLOWED_SRCS:
                findings.append("SSH_SRC_NOT_ALLOWLISTED")
            if _is_team_reaching(src):
                findings.append("TEAM_TAG_AS_SOURCE")
        for dst in rule.get("dst", []):
            if dst not in SSH_ALLOWED_DSTS:
                findings.append("SSH_DST_NOT_ALLOWLISTED")
            if _is_team_reaching(dst):
                findings.append("TEAM_TAG_AS_SSH_DESTINATION")
        for user in rule.get("users", []):
            if user == "root":
                findings.append("SSH_ROOT_GRANT")
            elif user not in SSH_ALLOWED_USERS:
                findings.append("SSH_USERS_NOT_ALLOWLISTED")

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
            _canon_node(_split_dst(d)[0], hosts) == hosts.get(SHELL_HOST)
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
    # Destination-axis bypasses executed by the round-2 independent gate. Round 1 hunted SOURCE
    # spellings and they were fixed; nobody had run the same lens down the destination column.
    ("shell_via_duplicate_alias.hujson", "SHELL_PORT_SRC_NOT_ALLOWLISTED"),
    ("shell_via_user_dst.hujson", "UNRESOLVABLE_DST_SELECTOR"),
    ("shell_via_autogroup_member_dst.hujson", "UNRESOLVABLE_DST_SELECTOR"),
    ("shell_via_cidr_dst.hujson", "UNRESOLVABLE_DST_SELECTOR"),
    # Third axis — the `ssh` block and the source column. Found independently by BOTH round-3
    # gates, which is why they are here rather than in the ledger: two seats converging on the
    # same hole is not a taste difference.
    ("ssh_wildcard_src.hujson", "SSH_SRC_NOT_ALLOWLISTED"),
    ("ssh_users_wildcard.hujson", "SSH_USERS_NOT_ALLOWLISTED"),
    ("acl_group_src.hujson", "UNRESOLVABLE_SRC_SELECTOR"),
    ("shell_host_ip_moved.hujson", "SHELL_HOST_IP_MOVED"),
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


def test_canonicalisation_collapses_every_spelling_of_a_node() -> None:
    """Alias, duplicate alias and bare IP must all resolve to the same node identity."""
    hosts = {"pro": "100.107.22.111", "pro-deck": "100.107.22.111"}
    assert _canon_node("pro", hosts) == _canon_node("pro-deck", hosts) == "100.107.22.111"
    assert _canon_node("100.107.22.111", hosts) == "100.107.22.111"
    assert not _is_node("autogroup:member", hosts)
    assert not _is_node("100.107.22.111/32", hosts)
    assert _port_spec_covers("22,443", SHELL_PORT)
    assert _port_spec_covers("1-65535", SHELL_PORT)
    assert not _port_spec_covers("22,5900", SHELL_PORT)
