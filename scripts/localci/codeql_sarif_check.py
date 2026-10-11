#!/usr/bin/env python3
"""The SARIF the CodeQL CLI wrote, judged the way the hosted job's analyze action judges it: `codeql_sarif_check.py SARIF LANGUAGE`.

Exit 0 = hosted would accept it; exit 1 = the hosted job would turn red on it, and the line says which rule (`LOCALCI_CODEQL_SARIF_REJECTED`).
Findings never change the verdict: the results count is receipt data (`LOCALCI_CODEQL_RESULTS`).

What hosted can fail on here is code-determined, from codeql-action v4.38.2 (src/upload-lib.ts) and the GitHub docs
(docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning):
  - the action reads the file with JSON.parse and counts results: a file that is not JSON, has no `runs` array, or holds a run without a
    `results` array throws InvalidSarifUploadError (readSarifFileOrThrow, countResultsInSarif);
  - the PR lane uploads (upload: always) and the API rejects a file over its documented limits.
The schema is NOT validated: the action skips validateSarifFileSchema when every run is produced by CodeQL, and a stricter check here would
be a FALSE_RED. A GitHub-side processing error outside these limits is infrastructure, a parity gap the matrix names.
"""
from __future__ import annotations

import json
import sys
import zlib

GZIP_MAX_BYTES = 10 * 1024 * 1024   # "10 MB" per gzip-compressed file; the larger reading of the unit, so a doubt never turns a leg red
GZIP_LEVEL = 6                      # zlib.gzipSync's default, which the action compresses with
MAX_RUNS, MAX_RESULTS, MAX_RULES, MAX_EXTENSIONS = 20, 25_000, 25_000, 100
MAX_THREAD_FLOW_LOCATIONS, MAX_LOCATIONS, MAX_TAGS = 10_000, 1_000, 20


def _reject_constant(name: str):
    raise ValueError(f"{name} is not JSON")   # JSON.parse refuses NaN and Infinity; Python's json would take them


def load(path: str) -> tuple[object, str | None]:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.loads(fh.read(), parse_constant=_reject_constant), None
    except (OSError, ValueError) as e:   # UnicodeDecodeError and JSONDecodeError are ValueErrors
        return None, f"Invalid SARIF. JSON syntax error or unreadable file: {type(e).__name__}: {str(e)[:120]}"


def shape_problem(doc: object) -> str | None:
    """The throws of countResultsInSarif: no `runs` array, or a run with no `results` array."""
    if not isinstance(doc, dict) or not isinstance(doc.get("runs"), list):
        return "Invalid SARIF. Missing 'runs' array."
    for i, run in enumerate(doc["runs"]):
        if not isinstance(run, dict) or not isinstance(run.get("results"), list):
            return f"Invalid SARIF. Missing 'results' array in run {i}."
    return None


def _list(v: object) -> list:
    return v if isinstance(v, list) else []


def _rules_of(run: dict) -> list:
    tool = run.get("tool") if isinstance(run.get("tool"), dict) else {}
    driver = tool.get("driver") if isinstance(tool.get("driver"), dict) else {}
    rules = [r for r in _list(driver.get("rules")) if isinstance(r, dict)]
    for ext in _list(tool.get("extensions")):
        rules += [r for r in _list(ext.get("rules") if isinstance(ext, dict) else None) if isinstance(r, dict)]
    return rules


def gzip_size(doc: object) -> int:
    """Bytes of the document as the action sends it: JSON.stringify text, gzip-compressed at zlib's default level."""
    text = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8", "surrogatepass")
    co = zlib.compressobj(GZIP_LEVEL, zlib.DEFLATED, 31)
    return len(co.compress(text)) + len(co.flush())


def limit_problems(doc: dict, gzip_bytes: int) -> list[str]:
    """Every documented upload limit the document exceeds, each named with the limit (a well-shaped document: shape_problem is None)."""
    out = []
    runs = doc["runs"]
    if len(runs) > MAX_RUNS:
        out.append(f"runs per file: {len(runs)} > {MAX_RUNS}")
    if gzip_bytes > GZIP_MAX_BYTES:
        out.append(f"gzip size: {gzip_bytes} bytes > {GZIP_MAX_BYTES} (10 MB per gzip-compressed file)")
    for i, run in enumerate(runs):
        tool = run.get("tool") if isinstance(run.get("tool"), dict) else {}
        rules = _rules_of(run)
        for what, n, cap in (("results per run", len(run["results"]), MAX_RESULTS), ("rules per run", len(rules), MAX_RULES),
                             ("tool extensions per run", len(_list(tool.get("extensions"))), MAX_EXTENSIONS)):
            if n > cap:
                out.append(f"{what}: {n} > {cap} (run {i})")
        tags = max((len(_list((r.get("properties") or {}).get("tags") if isinstance(r.get("properties"), dict) else None)) for r in rules), default=0)
        if tags > MAX_TAGS:
            out.append(f"tags per rule: {tags} > {MAX_TAGS} (run {i})")
        most_loc = most_flow = 0
        for res in (r for r in run["results"] if isinstance(r, dict)):
            most_loc = max(most_loc, len(_list(res.get("locations"))))
            flow = sum(len(_list(tf.get("locations"))) for cf in _list(res.get("codeFlows")) if isinstance(cf, dict)
                       for tf in _list(cf.get("threadFlows")) if isinstance(tf, dict))
            most_flow = max(most_flow, flow)
        if most_loc > MAX_LOCATIONS:
            out.append(f"locations per result: {most_loc} > {MAX_LOCATIONS} (run {i})")
        if most_flow > MAX_THREAD_FLOW_LOCATIONS:
            out.append(f"thread flow locations per result: {most_flow} > {MAX_THREAD_FLOW_LOCATIONS} (run {i})")
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: codeql_sarif_check.py SARIF LANGUAGE", file=sys.stderr)
        return 64
    path, lang = args
    doc, why = load(path)
    why = why or shape_problem(doc)
    if why:
        print(f"LOCALCI_CODEQL_SARIF_REJECTED language={lang} {why}")
        return 1
    runs = doc["runs"]
    results = sum(len(r["results"]) for r in runs)
    ids = {r["id"] for run in runs for r in _rules_of(run) if "id" in r}
    print(f"LOCALCI_CODEQL_RESULTS language={lang} results={results} rules={len(ids)}")   # data for the receipt, never part of the verdict
    if (problems := limit_problems(doc, gzip_size(doc))):
        print(f"LOCALCI_CODEQL_SARIF_REJECTED language={lang} " + "; ".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
