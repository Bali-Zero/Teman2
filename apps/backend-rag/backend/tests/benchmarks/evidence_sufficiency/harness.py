"""B1.3 — the frozen evidence-sufficiency benchmark, reporting harness.

Pure functions over `manifest_mandatory.json` (and, in B2, the supplement)
plus a `main()` CLI that prints the report as JSON. This module makes NO
production, embedding, generation or paid call: it imports the REAL scorer
(`calculate_evidence_score`) and the REAL abstain policy
(`build_abstain_policy`) and runs them, in-process, against the manifest's
synthetic cases.

`decide()` reads ONLY `query`, `context` and the sources inside
`provenance_fixture` — never a label field (`stratum`, `expected_*_gate`,
`supporting_span`, ...). That is the whole point of the benchmark: labels
describe what SHOULD happen, `decide()` measures what the scorer ACTUALLY
does, and `report()` is the difference between the two.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from backend.core.score_provenance import SCORE_KINDS
from backend.services.rag.agentic._abstain_policy import build_abstain_policy
from backend.services.rag.agentic._support_signal import SupportVerdict
from backend.services.rag.agentic.reasoning_utils import calculate_evidence_score

_HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = _HERE / "manifest_mandatory.json"
DEFAULT_VALIDATION = _HERE / "validation_codex.json"
#: B2.1 §6 — the frozen CI-mode replay record. Empty mapping + a header until
#: the Dux fills it from a real seat run; `main()` only reads it when
#: `--support-record` is passed, so the baseline (no flag) run this module's
#: own verification depends on is untouched by this file's mere existence.
DEFAULT_SUPPORT_RECORD = _HERE / "support_verdicts_b2.json"

_STRATA = frozenset(
    {
        "sufficient",
        "relevant_insufficient",
        "irrelevant",
        "generic_overlap",
        "company_prefix_chunk",
    },
)
_NEGATIVE_STRATA = _STRATA - {"sufficient"}
_GATES = ("generation", "label")


def load(path: str | Path) -> dict[str, Any]:
    """Read a manifest JSON file from disk."""
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def source_sha256(path: str | Path) -> str:
    """The `source_sha256` pin for a benchmark evidence source (Set B/Set C/
    ... in `manifest_supplement_b2.json`'s `sets` block).

    ALWAYS hashes the FILE's raw bytes (`Path(path).read_bytes()`) — never
    an in-memory `json.dumps(data)` re-serialization of its parsed content.
    The two differ whenever the file's own bytes carry something a
    round-trip through `json.loads`/`json.dumps` does not reproduce
    byte-for-byte — a trailing newline being the concrete case found
    2026-09-13: Set C's recorded pin (`a55aed94...`) was
    `sha256(json.dumps(data, indent=2))`, i.e. the writer hashed the
    in-memory string it was about to write rather than the bytes the file
    ended up holding once the write appended a final `\n`. A pin computed
    this way verifies against nothing any `shasum -a 256 <file>` will ever
    produce. Use this helper for every future `source_sha256` this
    benchmark records, so that class of drift cannot recur."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def support_record_key(query: str, context: list[str]) -> str:
    """The B2.1 §6 replay key — `sha256` of a CANONICAL JSON serialization of
    `[query, context]`, NEVER `case_id`, so no label can be smuggled through
    the key itself.

    The serialization is JSON and not concatenation because concatenation is
    NOT INJECTIVE, and a non-injective replay key fails in the one way this
    record may never fail: silently, with the WRONG verdict rather than a
    missing one. Found by the adversarial seat (codex-gpt-5.6-sol, round 1)
    and reproduced before curing — the first version keyed on
    `query + "\\x00" + "\\n".join(context)`, under which

        ("a", ["b", "c"])   and   ("a", ["b\\nc"])

    hash IDENTICALLY: a two-chunk context and a one-chunk context carrying a
    newline are indistinguishable once joined. `decide()` raises on a MISSING
    key, which protects against an uncovered case; nothing protected against
    a COLLIDING one, and the colliding pair would have read a verdict
    measured on different text. JSON escapes the separators instead of
    trusting them to be absent."""
    payload = json.dumps([query, context], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_support_record(path: str | Path) -> dict[str, str]:
    """Read a frozen CI-mode support-verdict replay record.

    Shape: `{"_meta": {...}, "verdicts": {<key>: <SupportVerdict value>}}`.
    Returns the `verdicts` mapping only — `_meta` is documentation, never a
    lookup target. Raises (loudly, never silently) if the file is malformed:
    a record that cannot be read is not the same as an empty one."""
    with Path(path).open(encoding="utf-8") as f:
        raw = json.load(f)
    verdicts = raw.get("verdicts")
    if not isinstance(verdicts, dict):
        raise ValueError(
            f"{path}: support record must carry a 'verdicts' object, got {type(verdicts).__name__}",
        )
    return verdicts


def _cell(case: dict[str, Any]) -> str:
    return f"{case['query_lang']}>{case['context_lang']}"


def validate(manifest: dict[str, Any]) -> list[str]:
    """Structural + precedence-consistency checks. Returns a list of error
    strings; empty means the manifest is well-formed. Never raises."""
    errors: list[str] = []
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        return ["manifest['cases'] is not a list"]

    seen_ids: set[str] = set()
    pairs: dict[str, list[dict[str, Any]]] = {}

    for i, case in enumerate(cases):
        tag = case.get("case_id", f"<index {i}>")

        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{tag}: missing/invalid case_id")
        elif case_id in seen_ids:
            errors.append(f"{tag}: duplicate case_id")
        else:
            seen_ids.add(case_id)

        for field in (
            "query",
            "query_lang",
            "context",
            "context_lang",
            "provenance_fixture",
            "requested_fact",
            "stratum",
            "expected_generation_gate",
            "expected_label_gate",
            "synthetic",
            "origin",
        ):
            if field not in case:
                errors.append(f"{tag}: missing mandatory field {field!r}")

        # the three nuisance booleans are mandatory and must actually be bool
        # (a truthy/falsy non-bool, e.g. "true" or 1, silently passes a bare
        # `if not case.get(...)` check and was findable only by report()
        # mis-bucketing a case — Codex finding 7)
        for bool_field in ("generic_overlap", "company_prefix", "fee_policy"):
            if bool_field not in case:
                errors.append(f"{tag}: missing mandatory field {bool_field!r}")
            elif not isinstance(case[bool_field], bool):
                errors.append(
                    f"{tag}: {bool_field!r} must be a bool, got {type(case[bool_field]).__name__}",
                )

        if case.get("query_lang") not in ("EN", "ID"):
            errors.append(f"{tag}: query_lang must be EN or ID, got {case.get('query_lang')!r}")
        if case.get("context_lang") not in ("EN", "ID"):
            errors.append(
                f"{tag}: context_lang must be EN or ID, got {case.get('context_lang')!r}",
            )

        # `query` must be a str and `context` a list whose every element is
        # a str. A bare string `context` (e.g. "foo" instead of ["foo"])
        # still iterates and " ".join()s downstream (decide(), the
        # supporting_span substring check above) — it produces a legible
        # joined string from single characters instead of raising, so it
        # silently passed validate() before this check named the field
        # (Dux ruling K5).
        if "query" in case and not isinstance(case["query"], str):
            errors.append(f"{tag}: query must be a str, got {type(case['query']).__name__}")
        if "context" in case:
            context_val = case["context"]
            if not isinstance(context_val, list) or not all(
                isinstance(item, str) for item in context_val
            ):
                errors.append(f"{tag}: context must be a list of str")

        stratum = case.get("stratum")
        if stratum not in _STRATA:
            errors.append(f"{tag}: unknown stratum {stratum!r}")

        # span iff sufficient
        has_span = "supporting_span" in case
        has_missing = "missing_fact_explanation" in case
        if stratum == "sufficient":
            if not has_span:
                errors.append(f"{tag}: sufficient case missing supporting_span")
            if has_missing:
                errors.append(f"{tag}: sufficient case must not carry missing_fact_explanation")
        elif stratum in _NEGATIVE_STRATA:
            if not has_missing:
                errors.append(f"{tag}: non-sufficient case missing missing_fact_explanation")
            if has_span:
                errors.append(f"{tag}: non-sufficient case must not carry supporting_span")

        # a verbatim supporting_span really is a substring of the context
        if has_span:
            joined = " ".join(case.get("context") or [])
            if case["supporting_span"] not in joined:
                errors.append(f"{tag}: supporting_span is not a substring of context")

        # expected gates consistent with stratum
        expected_gate = "pass" if stratum == "sufficient" else "abstain"
        if case.get("expected_generation_gate") != expected_gate:
            errors.append(
                f"{tag}: expected_generation_gate {case.get('expected_generation_gate')!r} "
                f"inconsistent with stratum {stratum!r} (expected {expected_gate!r})",
            )
        if case.get("expected_label_gate") != expected_gate:
            errors.append(
                f"{tag}: expected_label_gate {case.get('expected_label_gate')!r} "
                f"inconsistent with stratum {stratum!r} (expected {expected_gate!r})",
            )

        # provenance_fixture: inventory_row must be an int, sources must carry
        # score/score_kind/score_raw, and score_kind must be in vocabulary
        # (Codex finding 7 — a provenance_fixture with a missing/malformed
        # inventory_row or an incomplete source silently passed validate()).
        prov = case.get("provenance_fixture") or {}
        inventory_row = prov.get("inventory_row")
        if not isinstance(inventory_row, int) or isinstance(inventory_row, bool):
            errors.append(
                f"{tag}: provenance_fixture.inventory_row must be an int, got {inventory_row!r}",
            )
        note = prov.get("note")
        if not isinstance(note, str) or not note:
            errors.append(f"{tag}: provenance_fixture.note must be a non-empty string")
        sources = prov.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{tag}: provenance_fixture.sources must be a non-empty list")
            sources = []
        for src in sources:
            if not isinstance(src, dict):
                errors.append(f"{tag}: provenance_fixture source must be an object, got {src!r}")
                continue
            for src_field in ("score", "score_kind", "score_raw"):
                if src_field not in src:
                    errors.append(
                        f"{tag}: provenance_fixture source missing {src_field!r}",
                    )
            kind = src.get("score_kind")
            if kind not in SCORE_KINDS:
                errors.append(
                    f"{tag}: provenance_fixture source score_kind {kind!r} not in vocabulary"
                )

        if not case.get("synthetic", False):
            errors.append(f"{tag}: synthetic must be true")

        pair_id = case.get("pair_id")
        if pair_id:
            pairs.setdefault(pair_id, []).append(case)

    for pair_id, members in pairs.items():
        if len(members) != 2:
            errors.append(f"pair {pair_id}: expected exactly 2 members, got {len(members)}")
            continue
        strata = sorted(m.get("stratum") for m in members)
        if strata != ["relevant_insufficient", "sufficient"]:
            errors.append(
                f"pair {pair_id}: expected one sufficient + one relevant_insufficient, got {strata}",
            )
        a, b = members
        for field in ("query", "query_lang", "context_lang"):
            if a.get(field) != b.get(field):
                errors.append(f"pair {pair_id}: members disagree on {field}")
        if json.dumps(a.get("provenance_fixture"), sort_keys=True) != json.dumps(
            b.get("provenance_fixture"),
            sort_keys=True,
        ):
            errors.append(f"pair {pair_id}: members disagree on provenance_fixture")

    return errors


def decide(
    case: dict[str, Any],
    support_record: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run the REAL scorer + abstain policy on one case's (query, context,
    sources) — never reads a label field.

    `support_record`, when given (CI mode, B2.1 §6), supplies the support
    verdict via the frozen replay key (`support_record_key`) — never
    `case_id`. A missing key is a loud `KeyError`, never a silent `None`:
    silently treating an unrecorded case as "not consulted" would let a
    manifest case the Dux's real run never covered pass CI unnoticed."""
    query = case["query"]
    context = case["context"]
    sources = (case.get("provenance_fixture") or {}).get("sources") or []

    support: SupportVerdict | None = None
    if support_record is not None:
        key = support_record_key(query, context)
        if key not in support_record:
            raise KeyError(
                f"support_verdicts record missing key {key!r} for case "
                f"{case.get('case_id')!r} — the Dux's seat run never covered this "
                "(query, context) pair, and a missing key must never silently "
                "read as 'not consulted'",
            )
        support = SupportVerdict(support_record[key])

    score = calculate_evidence_score(sources, context, query, support=support)
    policy = build_abstain_policy(query)
    generation = "abstain" if policy.generation_abstains(score) else "pass"
    label = "abstain" if policy.label_abstains(score) else "pass"

    return {
        "case_id": case.get("case_id"),
        "score": score,
        "query_domain": policy.query_domain,
        "generation": generation,
        "label": label,
    }


def _empty_metric() -> dict[str, int]:
    return {"count": 0, "denominator": 0}


def _new_gate_bucket() -> dict[str, Any]:
    return {
        "false_abstention": _empty_metric(),
        "false_acceptance": _empty_metric(),
        "by_stratum": {
            s: {"false_abstention": _empty_metric(), "false_acceptance": _empty_metric()}
            for s in sorted(_STRATA)
        },
    }


def _accumulate(bucket: dict[str, Any], stratum: str, expected: str, actual: str) -> None:
    metric_name = "false_abstention" if expected == "pass" else "false_acceptance"
    bucket[metric_name]["denominator"] += 1
    bucket["by_stratum"][stratum][metric_name]["denominator"] += 1
    if actual != expected:
        bucket[metric_name]["count"] += 1
        bucket["by_stratum"][stratum][metric_name]["count"] += 1


def _report_one(
    manifest: dict[str, Any],
    support_record: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run `decide()` on every case in ONE manifest and aggregate
    false-abstention / false-acceptance counts per cell, per gate, per
    stratum, plus a fee_policy column and a spec_pairs view."""
    cases = manifest.get("cases", [])

    by_cell: dict[str, dict[str, Any]] = {}
    by_fee_policy: dict[str, dict[str, Any]] = {
        "true": {g: _new_gate_bucket() for g in _GATES},
        "false": {g: _new_gate_bucket() for g in _GATES},
    }
    decisions: dict[str, dict[str, Any]] = {}

    for case in cases:
        decision = decide(case, support_record)
        decisions[case["case_id"]] = decision

        cell = _cell(case)
        cell_bucket = by_cell.setdefault(cell, {g: _new_gate_bucket() for g in _GATES})
        fee_bucket = by_fee_policy["true" if case.get("fee_policy") else "false"]

        stratum = case["stratum"]
        for gate in _GATES:
            expected = case[f"expected_{gate}_gate"]
            actual = decision[gate]
            _accumulate(cell_bucket[gate], stratum, expected, actual)
            _accumulate(fee_bucket[gate], stratum, expected, actual)

    # spec_pairs view
    pairs: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        pid = case.get("pair_id")
        if pid:
            pairs.setdefault(pid, []).append(case)

    spec_pairs: dict[str, Any] = {}
    distinguished_generation_count = 0
    distinguished_label_count = 0
    for pid, members in pairs.items():
        suff = next(m for m in members if m["stratum"] == "sufficient")
        insuff = next(m for m in members if m["stratum"] == "relevant_insufficient")
        d_suff = decisions[suff["case_id"]]
        d_insuff = decisions[insuff["case_id"]]
        distinguished_generation = (
            d_suff["generation"] == "pass" and d_insuff["generation"] == "abstain"
        )
        distinguished_label = d_suff["label"] == "pass" and d_insuff["label"] == "abstain"
        if distinguished_generation:
            distinguished_generation_count += 1
        if distinguished_label:
            distinguished_label_count += 1
        spec_pairs[pid] = {
            "topic": suff.get("spec_pair"),
            "cell": _cell(suff),
            "sufficient_case_id": suff["case_id"],
            "relevant_insufficient_case_id": insuff["case_id"],
            "sufficient_decision": d_suff,
            "relevant_insufficient_decision": d_insuff,
            "distinguished_generation": distinguished_generation,
            "distinguished_label": distinguished_label,
            "distinguished": distinguished_generation,
        }

    return {
        "frozen_for": manifest.get("frozen_for"),
        "base_sha": manifest.get("base_sha"),
        "case_count": len(cases),
        "by_cell": by_cell,
        "by_fee_policy": by_fee_policy,
        "spec_pairs": spec_pairs,
        "spec_pairs_summary": {
            "total": len(pairs),
            "distinguished_generation_count": distinguished_generation_count,
            "distinguished_label_count": distinguished_label_count,
        },
    }


def report(
    manifest: dict[str, Any],
    validation: dict[str, Any] | None = None,
    support_record: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Report on the MANDATORY manifest and, separately, on an optional
    VALIDATION manifest. The two sets are never pooled: each is scored by
    its own `_report_one()` call over only its own cases, so a validation
    case can never inflate or dilute a mandatory denominator (Codex finding
    5). A validation manifest with no cases (the frozen `cases: []` shape
    before the adversarial seat's draws are copied in) reports as `None`
    rather than an all-zero-denominator report.

    `support_record`, when given, is the SAME replay mapping applied to both
    sets (B2.1 §6 CI mode) — omit it (`None`) for the Dux-mode / baseline
    measurement, which reads neither record and is unaffected by this
    parameter's mere existence.

    Returns `{"mandatory": <report>, "validation": <report> | None}`.
    """
    mandatory_report = _report_one(manifest, support_record)

    validation_report: dict[str, Any] | None = None
    if validation is not None and validation.get("cases"):
        validation_report = _report_one(validation, support_record)

    return {"mandatory": mandatory_report, "validation": validation_report}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the B1.3 evidence-sufficiency benchmark and print its report.",
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help="path to the mandatory manifest JSON file (default: the frozen mandatory manifest)",
    )
    parser.add_argument(
        "--validation",
        default=str(DEFAULT_VALIDATION),
        help=(
            "path to the validation manifest JSON file (default: validation_codex.json "
            "beside the harness); an empty validation set (no cases) reports as null"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the full report as JSON (default: human-readable summary)",
    )
    parser.add_argument(
        "--support-record",
        default=None,
        help=(
            "path to a frozen support-verdict replay record (B2.1 §6 CI mode); omit for "
            "the Dux-mode / baseline measurement, which reads neither record and passes "
            "support=None (not consulted) for every case"
        ),
    )
    args = parser.parse_args(argv)

    support_record: dict[str, str] | None = None
    if args.support_record is not None:
        support_record = load_support_record(args.support_record)

    manifest = load(args.manifest)
    errors = validate(manifest)
    if errors:
        for e in errors:
            print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        return 1

    # The validation set is drawn by an adversarial seat and MAY carry a
    # mechanically-invalid case on purpose (the Dux decides whether to keep
    # it as drawn) — so its own validate() errors are reported but never
    # abort the run the way a mandatory-manifest error does.
    validation_manifest: dict[str, Any] | None = None
    validation_path = Path(args.validation)
    if validation_path.exists():
        validation_manifest = load(validation_path)
        for e in validate(validation_manifest):
            print(f"VALIDATION SET WARNING: {e}", file=sys.stderr)

    result = report(manifest, validation_manifest, support_record)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        mandatory = result["mandatory"]
        print(f"frozen_for={mandatory['frozen_for']} base_sha={mandatory['base_sha']}")
        print(f"mandatory cases={mandatory['case_count']}")
        for cell, gates in sorted(mandatory["by_cell"].items()):
            for gate in _GATES:
                fa = gates[gate]["false_abstention"]
                fac = gates[gate]["false_acceptance"]
                print(
                    f"  {cell} {gate}: false_abstention={fa['count']}/{fa['denominator']} "
                    f"false_acceptance={fac['count']}/{fac['denominator']}",
                )
        summary = mandatory["spec_pairs_summary"]
        print(
            f"spec_pairs: {summary['distinguished_generation_count']}/{summary['total']} "
            "distinguished (generation gate)",
        )
        if result["validation"] is None:
            print("validation cases=0 (empty validation set)")
        else:
            print(f"validation cases={result['validation']['case_count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
