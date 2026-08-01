"""Find logger calls that interpolate PII into the message, across the backend.

CodeQL saw 3 of 7 in the ReDoS family, so its count is a floor here too. This walks the
AST instead of grepping text, and is control-tested on known-guilty and known-innocent
shapes BEFORE it is allowed to report a number (W107: the probe that measures a disease
can have it).

`client_id` is deliberately NOT PII here: CLAUDE.md 14 names it as the SAFE replacement
to use in logs. Sentry's own list redacts it, because there the scope is a user record —
different surface, different rule. Conflating the two would flag every correct fix.
"""

import ast
import pathlib
import sys

PII_TOKENS = (
    "passport", "npwp", "nib", "ktp", "nik", "tax_id",
    "email", "phone", "whatsapp", "wa_number", "msisdn",
    "full_name", "first_name", "last_name", "surname", "client_name", "contact_name",
    "address", "birth", "dob", "akta", "kitas", "visa_number",
    "password", "secret", "token", "api_key",
)
SAFE_TOKENS = ("client_id", "user_id", "practice_id", "token_count", "tokens_used")

LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical"}


def _is_logger_call(node: ast.Call) -> bool:
    f = node.func
    if not isinstance(f, ast.Attribute) or f.attr not in LOG_METHODS:
        return False
    base = f.value
    while isinstance(base, ast.Attribute):
        base = base.value
    return isinstance(base, ast.Name) and "log" in base.id.lower()


def _hits(src: str) -> list[str]:
    low = src.lower()
    for safe in SAFE_TOKENS:                      # strip safe names before matching
        low = low.replace(safe, "")
    return sorted({t for t in PII_TOKENS if t in low})


def scan_source(text: str, label: str) -> list[tuple[str, int, str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines = text.splitlines()
    out: list[tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_logger_call(node):
            continue
        # only the INTERPOLATED parts can carry a value; a constant message cannot.
        risky: list[str] = []
        for arg in node.args[1:]:                 # %-style extra args
            risky.append(ast.unparse(arg))
        for arg in node.args[:1]:
            if isinstance(arg, ast.JoinedStr):    # f-string: only its expressions
                risky += [ast.unparse(v.value) for v in arg.values
                          if isinstance(v, ast.FormattedValue)]
            elif not isinstance(arg, ast.Constant):
                risky.append(ast.unparse(arg))
        for kw in node.keywords:                  # extra={...}
            if kw.arg in ("extra", "exc_info"):
                risky.append(ast.unparse(kw.value))
        found = _hits(" ".join(risky))
        if found:
            line = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
            out.append((label, node.lineno, ",".join(found) + " :: " + line[:90]))
    return out


GUILTY = [
    'logger.info(f"OCR done for {client_id}: {extracted.get(\'passport_number\')}")',
    'logger.info("payload %s", {"phone": phone})',
    'log.debug("x", extra={"email": addr})',
    'logger.warning(f"failed for {api_key[:8]}")',
]
INNOCENT = [
    'logger.info("Auto OCR completed")',
    'logger.info(f"done for client {client_id}")',
    'logger.info("rows=%d", len(rows))',
    'logger.error(f"db error: {exc.__class__.__name__}")',
    'logger.info(f"tokens_used={token_count}")',
    'passport = row["passport_number"]',          # not a log call at all
]

if __name__ == "__main__":
    bad = 0
    for i, s in enumerate(GUILTY):
        if not scan_source(s, "g"):
            print(f"CONTROL FAIL: guilty #{i} not flagged: {s}")
            bad += 1
    for i, s in enumerate(INNOCENT):
        if scan_source(s, "i"):
            print(f"CONTROL FAIL: innocent #{i} flagged: {s}")
            bad += 1
    print(f"CONTROL: {len(GUILTY)} guilty / {len(INNOCENT)} innocent, {bad} failure(s)")
    if bad:
        sys.exit(2)

    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <root>   (e.g. apps/backend-rag/backend)")
        print("  Reports logger calls that interpolate PII-named values. Report-only.")
        sys.exit(64)  # EX_USAGE — a missing argument is not a clean scan
    root = pathlib.Path(sys.argv[1])
    if not root.is_dir():
        print(f"not a directory: {root}")
        sys.exit(64)
    findings = []
    scanned = 0
    for p in sorted(root.rglob("*.py")):
        if any(x in p.parts for x in (".venv", "node_modules", "__pycache__")):
            continue
        scanned += 1
        findings += scan_source(p.read_text(encoding="utf-8", errors="replace"),
                                str(p.relative_to(root)))
    if scanned == 0:
        print("BLIND SCAN: 0 files traversed — 0 findings means nothing")
        sys.exit(3)
    print(f"scanned {scanned} files, {len(findings)} logger calls interpolate PII-named values\n")
    for label, line, what in findings:
        print(f"{label}:{line}\t{what}")
