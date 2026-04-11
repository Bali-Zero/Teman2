"""Topological execution of visa sub-questions."""

from __future__ import annotations

import structlog

from nuzantara_graph.subgraphs.visa.types import SubQuestion

logger = structlog.get_logger()


def topo_sort(
    sub_questions: list[SubQuestion],
    max_depth: int = 3,
) -> tuple[list[SubQuestion], list[tuple[int, int]]]:
    """Topologically sort sub-questions.

    - Breaks cycles by dropping back-edges (from higher idx to lower).
    - Clamps chain depth to ``max_depth`` by collapsing deep dependencies
      onto the shallowest ancestor within the depth budget.

    Returns:
        (ordered_list, broken_edges) where broken_edges is a list of
        (from_idx, to_idx) pairs that were removed to eliminate cycles
        or clamp depth.
    """
    broken_edges: list[tuple[int, int]] = []

    # Normalize depends_on: each dep must be strictly smaller than idx to
    # guarantee acyclicity. Any edge (a -> b) with b >= a is a cycle.
    cleaned: list[SubQuestion] = []
    for sq in sub_questions:
        kept_deps: list[int] = []
        for dep in sq.depends_on:
            if dep < sq.idx and 0 <= dep < len(sub_questions):
                kept_deps.append(dep)
            else:
                broken_edges.append((sq.idx, dep))
        cleaned.append(
            SubQuestion(
                idx=sq.idx,
                text=sq.text,
                needs_kb=sq.needs_kb,
                depends_on=kept_deps,
            )
        )

    # Clamp depth. max_depth=3 allows depth levels {0, 1, 2}.
    max_allowed_depth = max_depth - 1
    depths: dict[int, int] = {}
    result: list[SubQuestion] = []
    for sq in cleaned:
        if not sq.depends_on:
            depths[sq.idx] = 0
            result.append(sq)
            continue

        parent_depth = max(depths.get(p, 0) for p in sq.depends_on)
        new_depth = parent_depth + 1

        if new_depth > max_allowed_depth:
            # Collapse to shallowest ancestor; if that still overflows,
            # drop all deps and re-root.
            shallowest = min(sq.depends_on, key=lambda p: depths.get(p, 0))
            shallowest_parent_depth = depths.get(shallowest, 0)
            candidate_depth = shallowest_parent_depth + 1

            dropped = [d for d in sq.depends_on if d != shallowest]

            if candidate_depth <= max_allowed_depth:
                collapsed_deps = [shallowest]
                new_depth = candidate_depth
            else:
                # Even the shallowest path is too deep — collapse to root
                collapsed_deps = []
                new_depth = 0
                dropped = list(sq.depends_on)

            for d in dropped:
                broken_edges.append((sq.idx, d))

            sq = SubQuestion(
                idx=sq.idx,
                text=sq.text,
                needs_kb=sq.needs_kb,
                depends_on=collapsed_deps,
            )

        depths[sq.idx] = new_depth
        result.append(sq)

    if broken_edges:
        logger.warning(
            "topo_sort_broken_edges",
            count=len(broken_edges),
            edges=broken_edges,
        )

    return result, broken_edges
