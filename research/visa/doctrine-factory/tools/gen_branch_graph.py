#!/usr/bin/env python3
"""Generate the E4 interview branch graph FROM THE LIVE SOURCE, not from memory.

Throwaway tool (per E4 task briefing: "tools are fine, prod code is not").
Reads `tree.ts` (question registry) and `flow.ts` (state machine: entry
sequence, `computeNextNode`, `FIXED_CATEGORY_QUESTIONS`) via regex extraction
— good enough for a documentation artifact, NOT a substitute for the
TypeScript compiler. Re-run after any tree.ts/flow.ts edit; do not hand-edit
the generated files.

Usage:
    python3 gen_branch_graph.py

Writes, next to this script's ../e4/:
    branch-graph.json   -- structured graph (nodes, edges, dead nodes, categories)
    branch-graph.mmd    -- mermaid flowchart source
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
LIB = REPO_ROOT / "apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib"
TREE_TS = LIB / "tree.ts"
FLOW_TS = LIB / "flow.ts"
OUT_DIR = Path(__file__).resolve().parent.parent / "e4"


def extract_questions(tree_text: str):
    """One entry per QUESTIONS[...] object: id, group, decisionMapping kind."""
    blocks = re.split(r"(?=^\s{4}id: \")", tree_text, flags=re.M)
    out = []
    for b in blocks:
        m = re.search(r'id: "([^"]+)"', b)
        if not m:
            continue
        qid = m.group(1)
        g = re.search(r'group: "([^"]+)"', b)
        group = g.group(1) if g else None
        kind = None
        km = re.search(r'kind: "(FACT|HUMAN_CONTEXT)"', b)
        if km:
            kind = km.group(1)
        fact_paths = re.findall(r'"([a-z_]+\.[a-z_]+)"', b.split("decisionMapping", 1)[-1][:300]) if "decisionMapping" in b else []
        out.append({"id": qid, "group": group, "decision_kind": kind})
    return out


def extract_category_keys(tree_text: str):
    m = re.search(r"export const CATEGORY_KEYS = \[(.*?)\] as const;", tree_text, re.S)
    if not m:
        return []
    return re.findall(r'"([a-z]+)"', m.group(1))


def extract_fixed_category_questions(flow_text: str):
    m = re.search(
        r"const FIXED_CATEGORY_QUESTIONS[^=]*=\s*\{(.*?)\n\};", flow_text, re.S
    )
    if not m:
        return {}
    body = m.group(1)
    out = {}
    for cat_match in re.finditer(r"(\w+):\s*\[(.*?)\]", body, re.S):
        cat, items = cat_match.groups()
        ids = re.findall(r'"([a-z_]+)"', items)
        out[cat] = ids
    return out


def extract_dead_nodes(flow_text: str):
    """computeNextNode's explicit legacy-bucket comment names the dead ids."""
    m = re.search(
        r"// Legacy fixture snapshots.*?never feeds the API mapper\.\n((?:\s*case \"[a-z_]+\":\n)+)",
        flow_text,
        re.S,
    )
    if not m:
        return []
    return re.findall(r'case "([a-z_]+)":', m.group(1))


def extract_entry_switch_edges(flow_text: str):
    """Static edges out of the `switch (current.questionId)` body in
    computeNextNode — everything up to the shared `category` -> `trip_scope`
    dispatch into per-category sequences. Best-effort regex, human-verified
    against the source at authoring time (see branch-graph.md)."""
    body_m = re.search(r"switch \(current\.questionId\) \{(.*?)\n  \}\n\}", flow_text, re.S)
    edges = []
    if not body_m:
        return edges
    body = body_m.group(1)
    for case_m in re.finditer(r'case "([a-z_]+)":(.*?)(?=case "|\Z)', body, re.S):
        src, rest = case_m.groups()
        targets = set(re.findall(r'questionId: "([a-z_]+)"', rest))
        for t in sorted(targets):
            edges.append({"from": src, "to": t, "kind": "conditional" if rest.count("questionId") > 1 else "fixed"})
    return edges


def main():
    tree_text = TREE_TS.read_text()
    flow_text = FLOW_TS.read_text()

    questions = extract_questions(tree_text)
    category_keys = extract_category_keys(tree_text)
    fixed_category_questions = extract_fixed_category_questions(flow_text)
    dead_nodes = extract_dead_nodes(flow_text)
    entry_edges = extract_entry_switch_edges(flow_text)

    human_context_ids = [q["id"] for q in questions if q["decision_kind"] == "HUMAN_CONTEXT"]
    fact_ids = [q["id"] for q in questions if q["decision_kind"] == "FACT"]
    no_decision_ids = [
        q["id"] for q in questions if q["decision_kind"] is None
    ]  # navigation-only or review-gate

    graph = {
        "source": {
            "tree_ts": str(TREE_TS.relative_to(REPO_ROOT)),
            "flow_ts": str(FLOW_TS.relative_to(REPO_ROOT)),
        },
        "node_count_total": len(questions),
        "category_keys": category_keys,
        "category_count": len(category_keys),
        "human_context_lanes": human_context_ids,
        "human_context_count": len(human_context_ids),
        "fact_backed_nodes": fact_ids,
        "unclassified_decision_nodes": no_decision_ids,
        "dead_nodes": dead_nodes,
        "fixed_category_questions": fixed_category_questions,
        "entry_switch_edges": entry_edges,
        "questions": questions,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "branch-graph.json").write_text(json.dumps(graph, indent=2) + "\n")

    # Mermaid rendering: entry spine (shared prelude) + one subgraph per
    # category branch from FIXED_CATEGORY_QUESTIONS (family/invest/retirement
    # are dynamic — rendered as a single conditional node, see branch-graph.md
    # prose for the real per-branch detail).
    lines = ["flowchart TD"]
    lines.append('  framing["framing"] --> in_indonesia')
    for e in entry_edges:
        style = "-. cond .->" if e["kind"] == "conditional" else "-->"
        lines.append(f'  {e["from"]} {style} {e["to"]}')
    lines.append('  trip_scope --> category_dispatch{{"per-category branch"}}')
    for cat in category_keys:
        node = f"cat_{cat}"
        lines.append(f'  category_dispatch -->|{cat}| {node}["{cat}"]')
        seq = fixed_category_questions.get(cat)
        if seq:
            chain = " --> ".join([node] + seq)
            lines.append(f"  {chain}")
        else:
            lines.append(f'  {node} -.-> {node}_dynamic["dynamic branch (facts-dependent)"]')
    lines.append("  review_gate --> confirmation --> verdict")
    for d in dead_nodes:
        lines.append(f'  {d}["{d} (DEAD — unreachable, legacy fixtures only)"]')
        lines.append(f"  style {d} fill:#444,color:#fff,stroke:#f66,stroke-dasharray: 5 5")

    (OUT_DIR / "branch-graph.mmd").write_text("\n".join(lines) + "\n")

    print(f"nodes={len(questions)} categories={len(category_keys)} "
          f"human_context={len(human_context_ids)} dead={dead_nodes}")


if __name__ == "__main__":
    main()
