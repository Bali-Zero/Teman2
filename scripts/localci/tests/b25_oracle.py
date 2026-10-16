"""Normative B25-prime oracle and MC/DC condition registry (docs/specs/localci-sovereign-2026-10-07.md §2b.1, §2b.3).
Imports nothing from merger.py or runner.py."""
from __future__ import annotations

import ast
import inspect
import textwrap

HOST_KINDS = {"host_disk_full", "host_disk_below_floor", "host_disk_unmeasured", "host_disk_floor_invalid"}
PR_TERMS = ("head_unchanged", "not_draft", "base_main", "open", "review_not_blocking", "not_in_queue", "first_enqueue", "label_privileged")
G1_STATES = ("S", "N", "F", "U", "O", "Gh")
G2_STATES = ("S", "N", "F", "U", "O", "Gh", "SF")
H_STATES = ("g", "p", "x")
MOVED_STATES = ("none", "head", "base")

REPS: dict[str, dict] = {
    "OK": {"mapping": "executed", "verdict": "OK", "coverage": "full"},
    "OKp": {"mapping": "executed", "verdict": "OK", "coverage": "partial"},
    "NE": {"mapping": "blocked", "verdict": "BLOCKED", "coverage": "full"},
    "HB": {"mapping": "executed", "verdict": "BLOCKED", "no_verdict": "host_disk_full", "coverage": "full"},
    "HE": {"mapping": "executed", "verdict": "ERROR", "no_verdict": "host_disk_unmeasured", "coverage": "full"},
    "RS": {"mapping": "executed", "verdict": "BLOCKED", "no_verdict": "judge_rewritten_base_ok", "coverage": "full"},
    "JR": {"mapping": "executed", "verdict": "BLOCKED", "no_verdict": "judge_rewritten", "coverage": "full"},
    "BL": {"mapping": "executed", "verdict": "BLOCKED", "coverage": "full"},
    "GP": {"mapping": "executed", "verdict": "BLOCKED", "no_verdict": "gate_pending", "coverage": "full"},
    "FA": {"mapping": "executed", "verdict": "FAIL", "coverage": "full"},
    "RF": {"mapping": "executed", "verdict": "FAIL", "no_verdict": "judge_rewritten_base_ok", "coverage": "full"},
    "RE": {"mapping": "executed", "verdict": "ERROR", "no_verdict": "judge_rewritten_base_ok", "coverage": "full"},
    "UC": {"mapping": "executed", "verdict": "UNCOVERED", "coverage": "full"},
}


def cls(r) -> str:
    """Normative per-context classifier (§2b.1)."""
    v = r.get("verdict") if isinstance(r, dict) else None
    nv = r.get("no_verdict") if isinstance(r, dict) and isinstance(r.get("no_verdict"), str) else ""
    if isinstance(r, dict) and r.get("mapping") in ("blocked", "not_implemented") and v == "BLOCKED":
        return "NE"
    if v in ("ERROR", "BLOCKED") and nv.split(" ")[0] in HOST_KINDS:
        return "HOST"
    if v == "BLOCKED" and nv == "judge_rewritten_base_ok":
        return "RESCUE"
    if v == "OK":
        return "OK"
    return "RED"


def local_oracle(status: dict) -> dict:
    """Normative local_side oracle for T1 (§2b.1, §2b.3)."""
    ctx = status.get("contexts") if isinstance(status.get("contexts"), dict) else {}
    results = ctx.get("results") if isinstance(ctx.get("results"), dict) else {}
    required = ctx.get("required") if isinstance(ctx.get("required"), list) else []
    ne, host, rescue, red, partial = {}, {}, [], {}, {}
    for c in required:
        r = results.get(c) if isinstance(c, str) and isinstance(results.get(c), dict) else {}
        k = cls(r)
        if k == "NE":
            ne[c] = r["mapping"]
        elif k == "HOST":
            host[str(c)] = r["no_verdict"]
        elif k == "RESCUE":
            rescue.append(str(c))
        elif k == "RED":
            red[str(c)] = f"{r.get('verdict')} ({r.get('mapping')})"
        elif r.get("coverage") != "full":
            partial[str(c)] = r["coverage"] if r.get("coverage") in ("full", "partial") else "unrecorded"
    base = ctx.get("status") == "ok" and len(required) > 0
    x = bool(host or red)
    e_ok = base and not x
    return {
        "executed_contexts_ok": e_ok,
        "non_executed": ne,
        "host_no_verdict": host,
        "not_ok": red,
        "partial": partial,
        "judge_rewritten_base_ok": rescue,
        "judge_gate_only": base and not x and bool(rescue),
        "contexts_status": ctx.get("status"),
        "required_n": len(required),
    }


def _ctx_classes(row: dict) -> list[str]:
    results = row["results"]
    return [cls(results.get(c) if isinstance(c, str) else None) for c in row["required"]]


CONDS: dict[str, object] = {
    "contexts_status_ok": lambda r: r["contexts_status"] == "ok",
    "required_nonempty": lambda r: len(r["required"]) > 0,
    "has_host": lambda r: "HOST" in _ctx_classes(r),
    "has_red": lambda r: "RED" in _ctx_classes(r),
    "has_rescue": lambda r: "RESCUE" in _ctx_classes(r),
    "gate1": lambda r: r["G1"] == "S",
    "gate2": lambda r: r["G2"] == "S",
    "hosted1": lambda r: r["H1"] == "g",
    "hosted2": lambda r: r["H2"] == "g",
    "local_checks_clean": lambda r: bool(r["local_checks_clean"]),
    "review_independent": lambda r: bool(r["review_independent"]),
    "same_repo1": lambda r: bool(r["same_repo1"]),
    "same_repo2": lambda r: bool(r["same_repo2"]),
    **{f"pr1_{t}": (lambda r, t=t: bool(r["pr_terms1"][t])) for t in PR_TERMS},
    **{f"pr2_{t}": (lambda r, t=t: bool(r["pr_terms2"][t])) for t in PR_TERMS},
    "overall_conflict": lambda r: r["overall"] == "CONFLICT",
    "overall_error": lambda r: r["overall"] == "ERROR",
    "overall_fail": lambda r: r["overall"] == "FAIL",
    "gate_pending": lambda r: bool(r["gate_pending"]),
    "moved_head": lambda r: r["moved"] == "head",
    "moved_base": lambda r: r["moved"] == "base",
}


def derived(c: dict[str, bool]) -> tuple:
    """Derived terms (§2b.1, §2b.3): reads atomic conditions ONLY through ``c[k]`` for ``k in CONDS``."""
    base = c["contexts_status_ok"] and c["required_nonempty"]
    X = c["has_host"] or c["has_red"]
    R = c["has_rescue"]
    E1 = base and not X and (not R or c["gate1"])
    only1 = base and not X and R
    gated = c["gate1"] and base and not X
    hosted1 = c["hosted1"]
    L = c["local_checks_clean"] and c["review_independent"] and c["same_repo1"]
    pr1_all = (c["pr1_head_unchanged"] and c["pr1_not_draft"] and c["pr1_base_main"] and c["pr1_open"]
               and c["pr1_review_not_blocking"] and c["pr1_not_in_queue"] and c["pr1_first_enqueue"] and c["pr1_label_privileged"])
    pr2_all = (c["pr2_head_unchanged"] and c["pr2_not_draft"] and c["pr2_base_main"] and c["pr2_open"]
               and c["pr2_review_not_blocking"] and c["pr2_not_in_queue"] and c["pr2_first_enqueue"] and c["pr2_label_privileged"])
    bad_overall = c["overall_conflict"] or c["overall_error"] or c["overall_fail"]
    ok1 = L and E1 and hosted1 and pr1_all
    pending1 = not ok1 and not bad_overall and not c["gate_pending"] and L and (E1 or only1)
    retried = pending1 and not c["moved_head"] and not c["moved_base"]
    ok2 = (retried and c["local_checks_clean"] and c["review_independent"] and c["same_repo2"]
           and (not R or c["gate2"]) and c["hosted2"] and pr2_all)
    merged2 = ok2
    return (ok1, E1, hosted1, only1, gated, pending1, retried, ok2, merged2)


def check_derived_ast() -> None:
    """§2b.3 AST check: fails if any comparison or boolean leaf of ``derived`` is not a ``CONDS`` entry."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(derived)))
    fn = tree.body[0]
    assert isinstance(fn, ast.FunctionDef)
    assert [a.arg for a in fn.args.args] == ["c"] and not fn.args.kwonlyargs and not fn.args.vararg and not fn.args.kwarg and not fn.args.defaults
    compares = [ast.dump(n) for n in ast.walk(fn) if isinstance(n, ast.Compare)]
    assert not compares, f"derived() must not contain comparisons outside CONDS: {compares}"
    locals_seen: set[str] = set()
    conds_used: set[str] = set()

    def check_expr(node: ast.AST) -> None:
        if isinstance(node, ast.BoolOp):
            for v in node.values:
                check_expr(v)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            check_expr(node.operand)
        elif isinstance(node, ast.Name) and node.id in locals_seen:
            return
        elif (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "c"
              and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str) and node.slice.value in CONDS):
            conds_used.add(node.slice.value)
        else:
            raise AssertionError(f"boolean leaf in derived() is not a CONDS entry or prior derived local: {ast.dump(node)}")

    for stmt in fn.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            continue
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            name = stmt.targets[0].id
            check_expr(stmt.value)
            locals_seen.add(name)
        elif isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Tuple):
            for elt in stmt.value.elts:
                assert isinstance(elt, ast.Name) and elt.id in locals_seen
        else:
            raise AssertionError(f"unexpected statement in derived(): {ast.dump(stmt)}")
    missing = set(CONDS) - conds_used
    assert not missing, f"CONDS entries unused in derived(): {sorted(missing)}"


def cond_vector(row: dict) -> dict[str, bool]:
    return {k: bool(fn(row)) for k, fn in CONDS.items()}


def oracle_row(row: dict) -> tuple:
    results = row["results"]
    rescued = tuple(c for c in row["required"] if cls(results.get(c) if isinstance(c, str) else None) == "RESCUE")
    ok1, E1, hosted1, only1, gated, pending1, retried, ok2, merged2 = derived(cond_vector(row))
    return (ok1, E1, hosted1, only1, dict.fromkeys(rescued, gated), pending1, retried, ok2, merged2)


def make_row(
    row_id: str,
    reps: tuple[str, ...],
    G1: str = "S",
    H1: str = "g",
    G2: str = "S",
    H2: str = "g",
    moved: str = "none",
    *,
    contexts_status: str = "ok",
    required: list[str] | None = None,
    local_checks_clean: bool = True,
    review_independent: bool = True,
    same_repo1: bool = True,
    same_repo2: bool = True,
    pr_terms1: dict[str, bool] | None = None,
    pr_terms2: dict[str, bool] | None = None,
    overall: str = "BLOCKED",
    gate_pending: bool = False,
) -> dict:
    req = [f"ctx-{i}" for i in range(len(reps))] if required is None else list(required)
    res = {f"ctx-{i}": dict(REPS[r]) for i, r in enumerate(reps)}
    p1 = {t: True for t in PR_TERMS}
    if pr_terms1:
        p1.update(pr_terms1)
    p2 = {t: True for t in PR_TERMS}
    if pr_terms2:
        p2.update(pr_terms2)
    return {
        "id": row_id,
        "reps": reps,
        "contexts_status": contexts_status,
        "required": req,
        "results": res,
        "G1": G1,
        "H1": H1,
        "G2": G2,
        "H2": H2,
        "moved": moved,
        "local_checks_clean": local_checks_clean,
        "review_independent": review_independent,
        "same_repo1": same_repo1,
        "same_repo2": same_repo2,
        "pr_terms1": p1,
        "pr_terms2": p2,
        "overall": overall,
        "gate_pending": gate_pending,
    }


def t2_configs() -> list[tuple[str, ...]]:
    """208 context configs in fixed order: 13 singles, 169 ordered pairs, 26 triples (RS+RS+x, x+RS+RS)."""
    names = tuple(REPS)
    singles = [(a,) for a in names]
    pairs = [(a, b) for a in names for b in names]
    triples = [t for a in names for t in (("RS", "RS", a), (a, "RS", "RS"))]
    return singles + pairs + triples


def t2_decision_specs() -> list[tuple[tuple[str, ...], str, str, list[tuple[str, str, str]]]]:
    """3,744 decisions; each oracle-pending decision expands over 7 G2 × 3 H2 × 3 moved = 63 retries, else [('S', 'g', 'none')]."""
    out = []
    for cfg in t2_configs():
        for g1 in G1_STATES:
            for h1 in H_STATES:
                probe = make_row("probe", cfg, g1, h1)
                pending1 = oracle_row(probe)[5]
                retries = [(g2, h2, mv) for g2 in G2_STATES for h2 in H_STATES for mv in MOVED_STATES] if pending1 else [("S", "g", "none")]
                out.append((cfg, g1, h1, retries))
    return out


def t2_rows() -> list[dict]:
    rows = []
    for cfg, g1, h1, retries in t2_decision_specs():
        label = "+".join(cfg)
        for g2, h2, mv in retries:
            rows.append(make_row(f"{label} | {g1},{h1} -> {g2},{h2},{mv}", cfg, g1, h1, g2, h2, mv))
    return rows


def t2b_rows() -> list[dict]:
    """T2b MC/DC rows on the AND terms from the two baselines (§2b.3)."""
    rows = [
        make_row("T2b:base_D", ("OK",), "S", "g", "S", "g", "none"),
        make_row("T2b:contexts_status", ("OK",), "S", "g", "S", "g", "none", contexts_status="error"),
        make_row("T2b:required_empty", (), "S", "g", "S", "g", "none", required=[]),
        make_row("T2b:local_checks_clean", ("OK",), "S", "g", "S", "g", "none", local_checks_clean=False),
        make_row("T2b:review_independent", ("OK",), "S", "g", "S", "g", "none", review_independent=False),
        make_row("T2b:same_repo1", ("OK",), "S", "g", "S", "g", "none", same_repo1=False),
    ]
    for t in PR_TERMS:
        rows.append(make_row(f"T2b:pr1_{t}", ("OK",), "S", "g", "S", "g", "none", pr_terms1={t: False}))
    rows.append(make_row("T2b:base_R", ("RS",), "N", "g", "S", "g", "none"))
    rows.append(make_row("T2b:same_repo2", ("RS",), "N", "g", "S", "g", "none", same_repo2=False))
    for t in PR_TERMS:
        rows.append(make_row(f"T2b:pr2_{t}", ("RS",), "N", "g", "S", "g", "none", pr_terms2={t: False}))
    for ov in ("CONFLICT", "ERROR", "FAIL"):
        rows.append(make_row(f"T2b:overall_{ov}", ("RS",), "N", "g", "S", "g", "none", overall=ov))
    rows.append(make_row("T2b:gate_pending", ("RS",), "N", "g", "S", "g", "none", gate_pending=True))
    return rows


def mcdc_pairs(rows: list[dict]) -> dict[str, tuple[str, str]]:
    """For every condition in CONDS, find an independence pair (r1, r2) in ``rows`` differing ONLY in that condition with different oracle outputs."""
    keys = list(CONDS)
    by_vec: dict[tuple[bool, ...], tuple[str, tuple]] = {}
    for r in rows:
        cv = cond_vector(r)
        vec = tuple(cv[k] for k in keys)
        if vec not in by_vec:
            by_vec[vec] = (r["id"], oracle_row(r))
    pairs: dict[str, tuple[str, str]] = {}
    for idx, k in enumerate(keys):
        for vec, (id1, out1) in by_vec.items():
            flipped = vec[:idx] + (not vec[idx],) + vec[idx + 1:]
            if flipped in by_vec:
                id2, out2 = by_vec[flipped]
                if out1 != out2:
                    pairs[k] = (id1, id2)
                    break
    return pairs
