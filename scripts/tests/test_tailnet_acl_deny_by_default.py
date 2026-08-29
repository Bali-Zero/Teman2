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

HARDENED A THIRD TIME 2026-08-29 by the round-4 gate, which asked the question the first three
rounds had not: where does this guard get its own anchors from? From `hosts` — which is part of
the file under audit. Rounds 1-3 hardened what the guard CHECKS; round 4 found that what it
checks WITH was still whatever the policy said. SIX spellings walked through, every one measured
green against the real policy before this fix: the four the adjudication named — a re-pointed
alias, an IPv6 alias, a CIDR alias used as a source, and a `/32` alias for the shell host's own
address — plus two invented at review time to test whether the cure was structural or just a
longer list: a decimal-integer spelling of Pro's address, and an IPv4-mapped IPv6 one that
contains Pro's own dotted quad as a substring. All six close under the two clauses below, and not
one of them needed a branch of its own.

So `hosts` is now pinned — but NOT as a closed set, which is the subtle half. The six fleet
aliases may not be re-pointed or deleted, AND every entry must be a bare IPv4 literal; entries
may still be ADDED, because this repo's own enrolment procedure adds one, and a guard that goes
red when an operator follows the runbook is worse than the gap it closes. Two conjoined clauses,
one assertion, no per-spelling branches — see EXPECTED_HOSTS.

The pattern across all four rounds, worth more than any one finding: every round found the guard
blind on the axis nobody had swept yet, and every fix that enumerated bad spellings was defeated
by the next spelling. The ones that held are the ones that fail closed on a whole class —
unknown top-level key, unresolvable selector, and now a `hosts` value of the wrong shape.

HARDENED A FOURTH TIME 2026-08-29 by the round-5 gate, which closed two things the round-4 PR
declared but did not fix. Both are recorded because the SHAPE of each mistake outlives it.

  C1 — the SHELL-ROUTE span was inferred from a decorative `// ====` fence, and with that fence
  deleted it ran to end-of-file: the block could be gutted and the required tokens parked in the
  JSON body, and the guard returned `[]`. A FALSE GREEN, in the check written to stop one. What
  makes it worth remembering is how it was found: the round-4 PR correctly named this the weakest
  surface in the diff and then PREDICTED its failure mode in prose — a cosmetic reflow causing a
  false RED — instead of mutating it. The prediction was wrong in the worst direction. A guard's
  weak point is found by mutating it; naming it and guessing is not evidence. It now terminates on
  a structural boundary (the comment run, which the JSON body ends) and an UNTERMINATED block is
  itself a finding.

  C2 — additive tolerance had an unpriced cost. An alias ADDED to `hosts` with a perfectly
  well-formed FOREIGN IPv4 satisfies both clauses above, and could then originate traffic. The
  round-4 PR declared this residual honestly but illustrated it with `mini:6379`, which
  understated it: probed port by port, `pro:443` was correctly refused and `pro:22`, `mini:22`,
  `mini:6379`, `mini:11434`, `mini:8990` and `m5:22` were ALL green — OpenSSH on the host holding
  the secrets file among them. No `hosts`-SHAPE rule can catch it, because the value is
  legitimately shaped; the cure is about the alias's ROLE instead. See UNPINNED_ALIAS_AS_SOURCE.

It is not, and cannot be, a Tailscale evaluator: it does not know what a `group:` expands to, and

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
SHELL_PORT = 443

# THE `hosts` TABLE, PINNED (round-4 gate, 2026-08-29). Round 3 pinned one CELL of this table —
# Pro's IP — and believed everything else the policy said. But `hosts` is INPUT to this guard:
# canonicalisation resolves every node spelling THROUGH it, and the shell-port allowlist resolves
# through it too, so whoever writes `hosts` decides what the guard's own anchors mean. Six
# spellings exploited exactly that and all six were green: re-pointing `m5` at a foreign IP
# (which inherits pro:443 while the guard stays quiet), an IPv6 alias for Pro, a CIDR alias used
# as a source, a `/32` alias for Pro's own address, a decimal-integer spelling of that address,
# and an IPv4-mapped IPv6 one. One defect, not six, so this is one assertion and not six patches.
#
# IT IS NOT A CLOSED SET, AND THAT IS THE LOAD-BEARING PART. The obvious spelling of "pin the
# table" — `hosts == EXPECTED_HOSTS` — would go RED the first time an operator follows this
# repo's OWN enrolment procedure, which adds a seventh entry (`enroll-team-device.md` step 5,
# and the worked example at the foot of policy.hujson). A guard that fails when someone does
# exactly what the runbook tells them to is worse than the gap it closes, and it would fire at
# enrolment time — the worst possible moment. So the assertion is TWO CONJOINED CLAUSES:
#
#   1. the six fleet aliases below keep these exact values — they may not be re-pointed, and
#      they may not be deleted; and
#   2. EVERY entry in `hosts`, including ones added long after this comment, is a bare IPv4
#      literal (see `_is_bare_ipv4`).
#
# Additive-tolerant, and still closed: enrolling `team-laptop-01` with a real magic IP passes,
# while a re-pointed alias fails clause 1 and every non-IPv4 spelling — v6, CIDR, `/32`, a DNS
# name, a decimal-integer address — fails clause 2 whether it is an existing entry or a new one.
# The two clauses are genuinely independent: clause 1 does not look at added entries, clause 2 is
# the ONLY thing standing over them.
EXPECTED_HOSTS = {
    "pro": "100.107.22.111",
    "mini": "100.93.236.6",
    "m5": "100.110.186.116",
    "iphone-14": "100.113.83.92",
    "iphone175": "100.77.16.7",
    "apple-vision-pro": "100.97.28.18",
}

# Derived, never re-typed: two literals for one fact are two chances to disagree.
SHELL_HOST_IP = EXPECTED_HOSTS[SHELL_HOST]

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

# `proto` was presence-checked and never value-checked, so `"proto": "udp"` under a comment
# reading "Only SSH" was green — a rule that names a TCP service while granting a different
# protocol between the same pair. Every service this policy grants is TCP, so the allowlist is
# one entry; a rule that genuinely needs UDP takes an edit here, which is the point.
ALLOWED_PROTOS = {"tcp"}

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


def _is_bare_ipv4(value: str) -> bool:
    """Is this a bare dotted-quad IPv4 literal and nothing else?

    An ALLOWLIST of one shape, not a denylist of the shapes that bit us. Tailscale's `hosts`
    accepts more than an address — a CIDR is legal there, which is what let `100.64.0.0/10` and
    `100.107.22.111/32` be laundered into "a node". A v6 literal, a DNS name, a decimal-integer
    address and a trailing space are all equally not-a-dotted-quad, and none of them needs to be
    enumerated here to be refused. Leading zeros are refused too: `010` is 8 in some parsers and
    10 in others, and a value this file disagrees with Tailscale about is worse than no value.
    """
    parts = value.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not (part.isascii() and part.isdigit()):
            return False
        if len(part) > 1 and part[0] == "0":
            return False
        if not 0 <= int(part) <= 255:
            return False
    return True


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


def _enumerate_ports(spec: str) -> set:
    """The concrete ports a spec admits, or an empty set if it is too wide to enumerate.

    Only used by the accept-test coverage check. A spec too wide to enumerate is already a
    WILDCARD_DST_PORT or OVERBROAD_DST_PORT_RANGE finding, so returning nothing here cannot hide
    anything: the rule is condemned on another axis before it reaches this one.
    """
    spec = spec.strip()
    if spec == "*" or _port_count(spec) > MAX_PORTS_PER_DST:
        return set()
    ports: set = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, _, hi = part.partition("-")
            try:
                ports.update(range(int(lo), int(hi) + 1))
            except ValueError:
                continue
        elif part:
            try:
                ports.add(int(part))
            except ValueError:
                continue
    return ports


def _is_fence(line: str) -> bool:
    """A `// =====` rule line. The SHELL-ROUTE banner is wrapped in these."""
    stripped = line.strip()
    return stripped.startswith("//") and set(stripped.strip("/ \t")) == {"="}


def _is_comment(line: str) -> bool:
    """A `//` comment line — the only thing a well-formed SHELL-ROUTE block is made of."""
    return line.strip().startswith("//")


def _shell_route_block(text: str) -> tuple[str, bool]:
    """The SHELL-ROUTE banner's span, and whether that span is properly TERMINATED.

    Returns `(block_text, terminated)`. `terminated` is the load-bearing half.

    The marker sits BETWEEN two fences (a banner), so the fence immediately following it opens the
    body rather than closing it. A fence only terminates the block once real content has been seen;
    that off-by-one made the first version of this fire on the shipped policy.

    HARDENED 2026-08-29 (gate condition C1) after the previous version was measured to produce a
    false GREEN — the failure mode this file exists to prevent, in the check written to prevent it.
    That version scanned for the closing fence and, finding none, silently returned everything to
    EOF: delete the `// ====` at policy.hujson:42 and the span grew from 32 lines to 374, so the
    required tokens could be parked ANYWHERE below — inside the JSON body — and the guard returned
    `[]`. Measured, not theorised.
    The cure is to stop treating a decorative fence as the only boundary and to fail closed when
    the block is not properly closed:
      * the block is a run of `//` COMMENT lines — the first non-comment line (i.e. the JSON body)
        ends it, so tokens parked in the policy proper can never count as "inside the block";
      * a span that reaches that boundary, or EOF, without a closing fence is UNTERMINATED, and an
        unterminated block is malformed rather than permissive.
    Structural, not decorative: reformatting the banner cannot silently widen what the check sees,
    and deleting its fence is now a finding instead of a licence.
    """
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if "SHELL-ROUTE:" in ln)
    collected: list[str] = [lines[start]]
    seen_content = False
    terminated = False
    for line in lines[start + 1 :]:
        if not _is_comment(line):
            # The comment run ended (blank line or the JSON body). The block cannot extend past it.
            break
        if _is_fence(line):
            if seen_content:
                terminated = True
                break
            continue
        if line.strip().strip("/ \t"):
            seen_content = True
        collected.append(line)
    return "\n".join(collected), terminated


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

    # `hosts` is trusted input to every other check in this function, so it is judged before any
    # of them runs. Two conjoined clauses, neither of which subsumes the other — see the comment
    # on EXPECTED_HOSTS for why this is deliberately NOT a closed set.
    #
    # Clause 2 first, and over EVERY entry: this is the only assertion that stands over an alias
    # added after today, which is exactly what clause 1 is designed to permit.
    for value in hosts.values():
        if not _is_bare_ipv4(str(value)):
            findings.append("HOST_VALUE_NOT_BARE_IPV4")
    # Clause 1: the six fleet aliases are immovable. `.get()` rather than `in` so that DELETING a
    # pinned alias fails here too — a removed anchor is a moved anchor with extra steps.
    if any(hosts.get(alias) != ip for alias, ip in EXPECTED_HOSTS.items()):
        findings.append("PINNED_HOST_ALIAS_MOVED")
    # Kept as its own finding although clause 1 covers it: "the shell anchor moved" is a louder
    # message to the next reader than "a pinned alias moved", and it is the one cell whose
    # movement silently unguards Pro's 443.
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
            # AN UNPINNED ALIAS MAY BE A DESTINATION, NEVER A SOURCE (gate condition C2,
            # 2026-08-29). The `hosts` pin is additive-tolerant on purpose — the enrolment runbook
            # adds a seventh entry, and a guard that reddens when the operator follows the
            # documented procedure is worse than the gap it closes. But that tolerance had a price
            # nobody had priced: an added alias holding a perfectly well-formed FOREIGN IPv4 became
            # "a node", and could then be granted anything. Probed port by port: `pro:443` was
            # correctly refused by the shell allowlist, and `pro:22`, `mini:22`, `mini:6379`,
            # `mini:11434`, `mini:8990` and `m5:22` were ALL green — OpenSSH on the host that holds
            # the secrets file among them.
            #
            # No `hosts`-SHAPE rule can catch that: the value is legitimately shaped. So the rule
            # is about the ROLE instead, and it mirrors the bright line this file already draws for
            # team devices — we reach the new machine, the new machine reaches nothing. That is
            # exactly what enrolment needs (`m5`/`pro -> team-laptop-01:22,5900` keeps the alias on
            # the destination side), so the cure costs the documented path nothing;
            # `test_enrolling_a_team_laptop_keeps_the_guard_green` is what proves that, not this
            # comment.
            elif src not in EXPECTED_HOSTS and _canon_node(src, hosts) not in EXPECTED_HOSTS.values():
                findings.append("UNPINNED_ALIAS_AS_SOURCE")
        if require_proto:
            proto = str(rule.get("proto", "")).strip()
            if not proto:
                # Without `proto`, a rule grants UDP alongside the TCP service it names, plus
                # ICMP between the pair — so "only SSH" would be false as written.
                findings.append("MISSING_PROTO")
            elif proto not in ALLOWED_PROTOS:
                findings.append("PROTO_NOT_ALLOWLISTED")
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
    #
    # SCOPED TO THE BLOCK, 2026-08-29. This used to ask `if token not in text` — of the WHOLE FILE.
    # Measured: delete the block's body and leave `7681`, `/term` and `ttyd` surviving anywhere at
    # all — including inside the very paragraph warning that they must not be deleted — and the
    # guard stayed green. Same disease as the `hosts` defect this commit exists to close: a check
    # asking "does this string appear somewhere" where it means "is this structure intact".
    #
    # AND THE SPAN ITSELF MUST BE WELL-FORMED (C1, 2026-08-29). Scoping alone was not enough: the
    # first version inferred the span from a decorative `// ====` fence and, when that fence was
    # deleted, ran to EOF — so the block could be gutted, the tokens parked in the JSON body, and
    # the guard returned green. An unterminated block is now a finding in its own right.
    if "SHELL-ROUTE:" not in text:
        findings.append("SHELL_ROUTE_BLOCK_MISSING")
    else:
        block, terminated = _shell_route_block(text)
        if not terminated:
            findings.append("SHELL_ROUTE_BLOCK_UNTERMINATED")
        for token in ("7681", "/term", "ttyd"):
            if token not in block:
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

    # ...and the INNOCENCE half, which was unenforced: every accept-test in the block could be
    # deleted and this guard stayed green, which is the same half-guard mistake as shipping only
    # accept-tests, taken from the other end. The console runs the `tests` block at save time, so
    # an untested grant is a grant nobody ever proved still works — and deny-by-default's whole
    # failure mode is a flow that silently stops. Every (src, dst) an acl rule grants must
    # therefore be asserted by an accept-test from that same source.
    accepts: dict = {}
    for t in tests:
        if "accept" in t:
            key = _canon_node(str(t.get("src", "")), hosts)
            accepts.setdefault(key, []).extend(t.get("accept", []))
    for rule in policy.get("acls", []):
        srcs = list(rule.get("src", [])) + list(rule.get("users", []))
        dsts = list(rule.get("dst", [])) + list(rule.get("ports", []))
        for dst in dsts:
            host, port = _split_dst(dst)
            wanted = _enumerate_ports(port)
            if not wanted:
                continue
            for src in srcs:
                proven = set()
                for entry in accepts.get(_canon_node(src, hosts), []):
                    e_host, e_port = _split_dst(entry)
                    if _canon_node(e_host, hosts) == _canon_node(host, hosts):
                        proven.update(p for p in wanted if _port_spec_covers(e_port, p))
                if proven != wanted:
                    findings.append("ACL_RULE_NOT_ACCEPT_TESTED")

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


def test_enrolling_a_team_laptop_keeps_the_guard_green() -> None:
    """The documented enrolment path must PASS. This test is the point of the additive tolerance.

    `enroll-team-device.md` step 5 adds a seventh `hosts` entry and the support rule that reaches
    it. A closed-set pin (`hosts == EXPECTED_HOSTS`) would go red exactly here — when an operator
    does what the runbook says, at enrolment time. This asserts the opposite, so that a future
    tightening of the pin cannot quietly reintroduce that failure: it would have to delete this
    test, which is a visible act rather than an invisible consequence.
    """
    policy = POLICY.read_text(encoding="utf-8")
    enrolled = policy.replace(
        '"apple-vision-pro": "100.97.28.18"',
        '"apple-vision-pro": "100.97.28.18",\n    "team-laptop-01":   "100.99.44.21"',
    ).replace(
        '"dst":    ["tag:team-device:22", "tag:team-device:5900"]',
        '"dst":    ["tag:team-device:22", "tag:team-device:5900",\n'
        '                 "team-laptop-01:22", "team-laptop-01:5900"]',
    ).replace(
        '"accept": ["tag:team-device:22", "tag:team-device:5900"]',
        '"accept": ["tag:team-device:22", "tag:team-device:5900",\n'
        '                 "team-laptop-01:22", "team-laptop-01:5900"]',
    )
    assert enrolled != policy, "the enrolment edit did not apply — this test would be vacuous"
    assert audit_policy(enrolled) == []


# ---------------------------------------------------------------------------------------------
# Guilt: each fixture reintroduces a defect and must be caught by the finding it is named for.
#
# Stated precisely rather than tidily (2026-08-29): most of these fixtures are MINIMAL — a few
# lines of policy carrying one defect — so since `hosts` became pinned they also emit
# PINNED_HOST_ALIAS_MOVED, because a three-line `hosts` block is missing five of the six pinned
# aliases and a missing anchor is a moved anchor. That is expected and does not weaken anything:
# the assertion below demands the SPECIFIC named code, so a fixture cannot pass on the strength of
# the pin alone. The four `hosts_*` fixtures added in round 4 carry the full pinned table on
# purpose, so that each isolates the exact spelling it is named for — verified: they emit that
# one code and nothing else.
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
    # Round-4 gate: `hosts` was trusted input and round 3 had pinned one cell of it. All four of
    # these were green against the REAL policy. They are four spellings of one defect, and they
    # are closed by one assertion — which is the whole claim this block has to survive.
    ("hosts_alias_repointed.hujson", "PINNED_HOST_ALIAS_MOVED"),
    ("hosts_v6_alias.hujson", "HOST_VALUE_NOT_BARE_IPV4"),
    ("hosts_cidr_alias_as_src.hujson", "HOST_VALUE_NOT_BARE_IPV4"),
    ("hosts_slash32_alias.hujson", "HOST_VALUE_NOT_BARE_IPV4"),
    # The two minors the round-3 and round-4 adjudicators both declared, carried in with them.
    ("shell_route_tokens_outside_block.hujson", "SHELL_ROUTE_BLOCK_INCOMPLETE"),
    # Gate condition C1: the previous span inference produced a FALSE GREEN when its fence
    # was deleted — the failure mode this whole file exists to prevent.
    ("shell_route_fence_deleted.hujson", "SHELL_ROUTE_BLOCK_UNTERMINATED"),
    # Gate condition C2: additive tolerance let a new foreign alias originate traffic.
    ("unpinned_alias_as_source.hujson", "UNPINNED_ALIAS_AS_SOURCE"),
    ("proto_not_tcp.hujson", "PROTO_NOT_ALLOWLISTED"),
    ("accept_tests_deleted.hujson", "ACL_RULE_NOT_ACCEPT_TESTED"),
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


def test_only_a_bare_dotted_quad_counts_as_a_host_value() -> None:
    """The value-shape half of the `hosts` pin, asserted directly rather than through a fixture.

    An allowlist of one shape: a spelling absent from this test is refused because it is not a
    dotted quad, not because someone remembered to enumerate it.
    """
    for good in ("100.107.22.111", "10.0.0.1", "0.0.0.0", "255.255.255.255"):
        assert _is_bare_ipv4(good), good
    for bad in (
        "fd7a:115c:a1ce:1::1",  # v6
        "100.64.0.0/10",  # CIDR range
        "100.107.22.111/32",  # CIDR host
        "100.107.22.111 ",  # trailing space
        "pro.tail461666.ts.net",  # DNS name
        "100.107.22",  # short
        "100.107.22.111.5",  # long
        "100.107.22.256",  # out of range
        "100.107.022.111",  # leading zero: 022 is 18 to some parsers and 22 to others
        "",
    ):
        assert not _is_bare_ipv4(bad), bad


def test_the_expected_hosts_table_is_itself_well_formed() -> None:
    """The constant the whole pin rests on must satisfy the shape rule it enforces."""
    assert all(_is_bare_ipv4(v) for v in EXPECTED_HOSTS.values())
    assert len(set(EXPECTED_HOSTS.values())) == len(EXPECTED_HOSTS), "two aliases, one IP"
    assert SHELL_HOST in EXPECTED_HOSTS
    assert SHELL_PORT_ALLOWED_SOURCES <= set(EXPECTED_HOSTS), "allowlists an alias that is not a node"


def test_port_enumeration_declines_specs_too_wide_to_enumerate() -> None:
    """Wide specs return nothing — they are condemned by the wildcard/overbroad checks instead."""
    assert _enumerate_ports("22") == {22}
    assert _enumerate_ports("22,443") == {22, 443}
    assert _enumerate_ports("80-82") == {80, 81, 82}
    assert _enumerate_ports("*") == set()
    assert _enumerate_ports("1-65535") == set()
