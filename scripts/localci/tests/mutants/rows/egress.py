"""Egress step: the network exemption judges pip-audit's finding, never its clean line (#8613) — against test_egress_finding.py."""
PY = "scripts/localci/runner.py"
EF = ("scripts/localci/tests/test_egress_finding.py",)
OLD = 're.search(r"^Found [1-9][0-9]* known vulnerabilit|^Name +Version +ID", full, re.M)'

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "egress-finding-is-a-substring": (PY, OLD, 're.search(r"known vulnerabilit|^Name +Version +ID", full, re.I | re.M)', EF),
    "egress-finding-drops-table-header": (PY, OLD, 're.search(r"^Found [1-9][0-9]* known vulnerabilit", full, re.M)', EF),
    "egress-finding-drops-found-line": (PY, OLD, 're.search(r"^Name +Version +ID", full, re.M)', EF),
    "egress-finding-accepts-zero": (PY, OLD, 're.search(r"^Found [0-9]* known vulnerabilit|^Name +Version +ID", full, re.M)', EF),
}
