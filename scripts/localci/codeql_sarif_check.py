#!/usr/bin/env python3
"""The SARIF the CodeQL CLI wrote, judged the way the hosted job's analyze action judges it: `codeql_sarif_check.py SARIF LANGUAGE`.

Exit 0 = hosted would accept it; exit 1 = the hosted job would turn red on it, and the line says which rule (`LOCALCI_CODEQL_SARIF_REJECTED`);
exit 70 = this checker itself crashed (a RecursionError, MemoryError or UnicodeEncodeError on the document): NO verdict, which the leg turns into
its no-verdict signal, never into a red exit. Findings never change the verdict: the results count is receipt data (`LOCALCI_CODEQL_RESULTS`).

What hosted can fail on here is code-determined, from codeql-action v4.38.2 (src/upload-lib.ts) and the GitHub docs
(docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning):
  - the action reads the file with JSON.parse and counts results: a file that is not JSON, has no `runs` array, or holds a run without a
    `results` array throws InvalidSarifUploadError (readSarifFileOrThrow, countResultsInSarif);
  - the PR lane uploads (upload: always) and the API rejects a file over its documented limits. The maxima are REJECTION limits, not display
    truncation: the docs say "If any of these objects exceeds its maximum value the SARIF file is rejected"; "only the top 5,000 ..." is a
    display truncation BELOW the maximum. So the result and rule maxima fail here (a Kimi round-2 reading of them as truncation is rebutted).
The schema is NOT validated: the action skips validateSarifFileSchema when every run is produced by CodeQL, and a stricter check here would
be a FALSE_RED. A GitHub-side processing error outside these limits is infrastructure, a parity gap the matrix names.
"""
from __future__ import annotations

import json
import sys
import zlib

GZIP_MAX_BYTES = 10_000_000   # "10 MB" per gzip-compressed file, read as decimal megabytes: the SMALLER reading of the unit, so a doubt can only turn a leg red, never green (FALSE_GREEN 0)
GZIP_LEVEL = 6                # zlib.gzipSync's default, which the action compresses with
FINGERPRINT_BOUND = 32        # bytes the action may add per result it fingerprints (`"primaryLocationLineHash":"<16 hex>:1"` rides in compressed form well under this)
AUTOMATION_BOUND = 256        # bytes the action may add per run lacking `automationDetails` (`{"id":"<category>/"}`)
NO_VERDICT_RC = 70            # the checker's own crash: not 0 (accepted) and not 1 (rejected)
MAX_RUNS, MAX_RESULTS, MAX_RULES, MAX_EXTENSIONS = 20, 25_000, 25_000, 100
MAX_THREAD_FLOW_LOCATIONS, MAX_LOCATIONS, MAX_TAGS = 10_000, 1_000, 20


def _reject_constant(name: str):
    raise ValueError(f"{name} is not JSON")   # JSON.parse refuses NaN and Infinity; Python's json would take them


def load(path: str) -> tuple[object, str | None]:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.loads(fh.read(), parse_constant=_reject_constant), None
    except UnicodeEncodeError:
        raise   # not a verdict on the file: main() reads it as the checker's own crash
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


def action_adds(doc: dict) -> int:
    """A conservative bound of what the analyze action adds to the SARIF before it sends it (codeql-action v4.38.2): a `primaryLocationLineHash`
    to every result that lacks one and has a primary location with `physicalLocation.artifactLocation` and `region.startLine` (fingerprints.ts
    addFingerprints), and `automationDetails` to every run that has none (upload-lib.ts populateRunAutomationDetails). The CLI's own SARIF
    carries both on every result and run today, so this is 0 on a real document; it only grows if the CLI stops writing them."""
    total = 0
    for run in doc["runs"]:
        if not isinstance(run, dict):
            continue
        if "automationDetails" not in run:
            total += AUTOMATION_BOUND
        for res in (r for r in _list(run.get("results")) if isinstance(r, dict)):
            pf = res.get("partialFingerprints")
            if isinstance(pf, dict) and pf.get("primaryLocationLineHash"):
                continue
            loc = (_list(res.get("locations")) or [None])[0]
            phys = loc.get("physicalLocation") if isinstance(loc, dict) else None
            region = phys.get("region") if isinstance(phys, dict) else None
            if isinstance(phys, dict) and phys.get("artifactLocation") is not None and isinstance(region, dict) and region.get("startLine") is not None:
                total += FINGERPRINT_BOUND
    return total


def gzip_size(doc: object) -> int:
    """Bytes of the document as the action sends it: JSON.stringify text (compact), gzip-compressed at zlib's default level, plus the bound of
    what the action adds first (action_adds). The input's own whitespace never matters: the document is re-serialised compact."""
    text = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8", "surrogatepass")
    co = zlib.compressobj(GZIP_LEVEL, zlib.DEFLATED, 31)
    return len(co.compress(text)) + len(co.flush()) + (action_adds(doc) if isinstance(doc, dict) and isinstance(doc.get("runs"), list) else 0)


def limit_problems(doc: dict, gzip_bytes: int) -> list[str]:
    """Every documented upload limit the document exceeds, each named with the limit (a well-shaped document: shape_problem is None)."""
    out = []
    runs = doc["runs"]
    if len(runs) > MAX_RUNS:
        out.append(f"runs per file: {len(runs)} > {MAX_RUNS}")
    if gzip_bytes > GZIP_MAX_BYTES:
        out.append(f"gzip size: {gzip_bytes} bytes > {GZIP_MAX_BYTES} (10 MB per gzip-compressed file, read as 10,000,000)")
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


def judge(path: str, lang: str) -> int:
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


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: codeql_sarif_check.py SARIF LANGUAGE", file=sys.stderr)
        return 64
    path, lang = args
    try:
        return judge(path, lang)
    except (RecursionError, MemoryError, UnicodeEncodeError) as e:   # this checker failed, the document was not judged: exit 1 would say "hosted rejects it"
        print(f"LOCALCI_CODEQL_SARIF_CHECK_CRASHED language={lang} {type(e).__name__}: no verdict on this SARIF", file=sys.stderr)
        return NO_VERDICT_RC


if __name__ == "__main__":
    sys.exit(main())
