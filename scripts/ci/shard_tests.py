#!/usr/bin/env python3
"""shard_tests.py — deterministic partitioner for the `Backend Shard N` matrix.

WHY THIS EXISTS (S11, 2026-08-23)
---------------------------------
`Backend Tests (Python)` was a single job whose "Run unit tests" step measured
797s of a 1068s job on merge_group run 32626973483 (74.6%) and 726s of 975s on
schedule run 32624568684. Every code PR pays that twice (PR lane + merge-group
lane), which made it the largest fixed cost per queue transit. The cure is
cross-job sharding: three `Backend Shard N` jobs each run a third of the test
FILES, and a fan-in job keeps publishing the required status context.

This module is the ONE place that answers "which test files exist, and which
shard owns each one" — the shards and the fan-in guard both call it, so a shard
cannot silently disagree with the guard about what the full set was
(cicatrix-superscar #9, state-schema mutation drift: two copies of the same
derivation is how they drift).

THE PARTITION IS A GUARD, NOT A CONVENIENCE
-------------------------------------------
A sharded suite has one catastrophic failure mode that looks exactly like a
green run: the union of the chunks is a strict SUBSET of the test corpus, so
tests silently stop running while the required context stays green
(superscar #2, "esiste != armato" / W97 "a display cap read as the whole set").
`verify` exists to make that structurally impossible: it re-derives the full
enumeration and refuses unless the chunk lists the shards ACTUALLY consumed are
pairwise disjoint AND cover it exactly. It compares against the uploaded
artifacts, never against a recomputation of itself — a guard that only checks
its own arithmetic is a tautology, not a guard.

CONTRACT
--------
All paths are relative to the working directory the shards run pytest from
(`apps/backend-rag`), so the output can be handed straight to pytest.

Environment (mirrors the `changes` job's fail-open convention exactly — any
upstream failure leaves these unset and the unscoped default set is used, and
this module NEVER narrows the corpus on its own initiative):

  IMPACT_RUN_ALL          "false" only when the PR-lane static impact map ran
                          and trusted itself. Anything else (unset, "true",
                          malformed) => full corpus.
  IMPACT_SELECTED_TESTS   newline-separated, repo-root-relative test modules.

Subcommands:
  targets    print the resolved target list (what pytest would have been given)
  enumerate  print every test file in the corpus, canonically ordered
  chunk      print the files owned by --shard of --shards
  verify     assert the shards' uploaded chunk lists tile the corpus exactly
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# The unscoped target set. This is the SSOT for it — tests.yml's "Run unit
# tests" step no longer carries its own copy.
DEFAULT_TARGETS = (
    "backend/tests/",
    "../../scripts/bot/test_build_deid_corpus.py",
    "../../scripts/bot/test_wa_blind_bench.py",
)

# Mirrors pytest's own `--ignore=backend/tests/e2e` in tests.yml — an explicitly
# listed file is not reliably suppressed by --ignore, so the enumerator must not
# emit them in the first place. Deliberately NOT annotated with how many files
# that currently excludes: a count in a comment is a claim with no test behind
# it, and two sibling comments in this pair had already drifted to two different
# numbers (1423 vs 1425) by the time a refuter noticed, while the true figure had
# moved on to 1428.
#
# KNOWN AND NOT CLOSED BY THIS MODULE: because the exclusion is by PATH on the
# tree being enumerated, moving a live test file INTO backend/tests/e2e/ removes
# it from the corpus, and both guard passes stay green. That is the same class as
# deleting the file outright — no design that runs tests from the working tree
# catches it — and it predates sharding (the pre-split job carried the same
# --ignore). Named here so the next reader does not mistake the guard for a
# defence it never was.
EXCLUDED_DIRS = ("backend/tests/e2e",)

# IMPACT_SELECTED_TESTS is published repo-root-relative; the shards run from
# apps/backend-rag.
IMPACT_PREFIX = "apps/backend-rag/"


def resolve_targets(env=None):
    env = os.environ if env is None else env
    run_all = (env.get("IMPACT_RUN_ALL") or "true").strip()
    selected = [
        line.strip()
        for line in (env.get("IMPACT_SELECTED_TESTS") or "").splitlines()
        if line.strip()
    ]
    if run_all == "false" and selected:
        return [_to_pytest_cwd(s) for s in selected]
    return list(DEFAULT_TARGETS)


def _to_pytest_cwd(repo_relative):
    """Rewrite a repo-root-relative selection into the pytest cwd's frame.

    Everything here is relative to apps/backend-rag, because that is where the
    shards run pytest from. A path under that prefix loses it; ANY OTHER path
    gets `../../`, exactly like the two scripts/bot entries in DEFAULT_TARGETS.

    That second branch is not hypothetical tidiness — it was a refuter finding
    (Kimi K3): the first cut passed a non-prefixed path through untouched, so the
    first impact-map change that ever emitted one (a bot test, a packages/ test)
    would make `enumerate_tests` abort and turn every shard red. Worse, this
    module's own test suite ASSERTED the broken form, which is how a latent
    false-red gets blessed as intended behaviour.
    """
    if repo_relative.startswith(IMPACT_PREFIX):
        return repo_relative[len(IMPACT_PREFIX) :]
    return "../../" + repo_relative.lstrip("/")


def _is_test_file(path):
    name = path.name
    return path.suffix == ".py" and (
        name.startswith("test_") or name.endswith("_test.py")
    )


def _is_excluded(norm):
    for excluded in EXCLUDED_DIRS:
        excluded = excluded.rstrip("/")
        if norm == excluded or norm.startswith(excluded + "/"):
            return True
    return False


def enumerate_tests(targets, root, tolerate_missing=False):
    """Every test module reachable from `targets`, canonically ordered.

    Ordering is a plain codepoint sort of the normalised relative paths, so it
    is identical on every runner regardless of filesystem iteration order.

    `tolerate_missing` exists for exactly one caller: the fan-in's SECURITY pass,
    which runs the BASE ref's copy of this module against the HEAD tree. A PR
    that legitimately renames or removes a target directory would otherwise make
    that pass abort forever — the base ref's DEFAULT_TARGETS naming a path the
    head tree no longer has. Dropping it with a loud warning turns a permanent
    red into a declared, visible degradation. The default stays fail-loud,
    because for the shards a vanished target IS a defect.
    """
    found = set()
    for target in targets:
        candidate = root / target
        if candidate.is_file():
            matches = [candidate]
        elif candidate.is_dir():
            matches = [p for p in candidate.rglob("*.py") if _is_test_file(p)]
        elif tolerate_missing:
            print(
                "::warning::shard_tests: target %r does not exist in this tree — "
                "dropped from the trusted corpus (renamed or removed since the base "
                "ref); everything under it is UNVERIFIED by the security pass"
                % target,
                file=sys.stderr,
            )
            continue
        else:
            raise SystemExit("shard_tests: target does not exist: %s" % target)
        for match in matches:
            norm = os.path.normpath(os.path.relpath(match, root))
            if _is_excluded(norm):
                continue
            found.add(norm)
    return sorted(found)


def chunk_for(all_tests, shards, shard):
    """Round-robin over the canonical order.

    Round-robin (not contiguous blocks) because the canonical order is
    alphabetical by path: contiguous blocks would hand one shard a whole
    directory, and directories are exactly where slow tests cluster.
    """
    return [t for i, t in enumerate(all_tests) if i % shards == (shard - 1)]


def _read_chunk_file(path):
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def verify(all_tests, shards, chunk_dir, union_only=False):
    """Return a list of problems; empty means the partition is sound.

    Two modes, because two different questions are being asked and conflating
    them makes this guard block its own successor:

    ``full`` (default) — the DRIFT check. Every shard must have consumed exactly
    the files this module says it owns. Run with the HEAD copy, where "this
    module" and "what the shards ran" are the same code by construction.

    ``union_only`` — the SECURITY check, run with the BASE ref's copy. It asks
    only the question that can hide a regression: did every module in the
    trusted corpus run somewhere, exactly once? It deliberately does NOT check
    per-shard ownership (a PR is allowed to change the assignment algorithm) and
    deliberately does NOT flag modules the shards ran that the trusted corpus
    does not know about (a PR is allowed to ADD tests). The asymmetry is the
    point: running MORE than the trusted corpus is never a defect, running LESS
    always is. Without it, the v2 duration-aware splitter this file's own
    comments anticipate would be permanently unmergeable.
    """
    problems = []
    owner = {}

    valid_names = {str(s) for s in range(1, shards + 1)}
    stray = sorted(
        p.name
        for p in chunk_dir.glob("chunk-*.txt")
        if p.stem[len("chunk-") :] not in valid_names
    )
    if stray:
        problems.append(
            "unexpected chunk list(s) outside shards 1..%d: %s — the matrix and "
            "the declared shard count disagree" % (shards, ", ".join(stray))
        )

    for shard in range(1, shards + 1):
        path = chunk_dir / ("chunk-%d.txt" % shard)
        if not path.exists():
            problems.append(
                "shard %d published no chunk list (%s) — it did not run, or its "
                "artifact never arrived" % (shard, path)
            )
            continue
        consumed = _read_chunk_file(path)
        expected = chunk_for(all_tests, shards, shard)
        if not union_only and consumed != expected:
            only_consumed = sorted(set(consumed) - set(expected))
            only_expected = sorted(set(expected) - set(consumed))
            detail = []
            if only_consumed:
                detail.append("ran but not owned: %s" % only_consumed[:5])
            if only_expected:
                detail.append("owned but not run: %s" % only_expected[:5])
            if not detail:
                detail.append("same files, different order")
            problems.append(
                "shard %d consumed %d files, partition says %d — %s"
                % (shard, len(consumed), len(expected), "; ".join(detail))
            )
        for test in consumed:
            if test in owner:
                problems.append(
                    "overlap: %s ran on shard %d AND shard %d"
                    % (test, owner[test], shard)
                )
            owner[test] = shard

    missing = sorted(set(all_tests) - set(owner))
    if missing:
        problems.append(
            "%d test module(s) ran on NO shard, e.g. %s" % (len(missing), missing[:5])
        )
    if not union_only:
        extra = sorted(set(owner) - set(all_tests))
        if extra:
            problems.append(
                "%d module(s) ran that are not in the corpus, e.g. %s"
                % (len(extra), extra[:5])
            )
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("targets", "enumerate", "chunk", "verify"))
    parser.add_argument("--root", default=".", help="directory pytest runs from")
    parser.add_argument("--shards", type=int, default=3)
    parser.add_argument("--shard", type=int)
    parser.add_argument("--chunk-dir")
    parser.add_argument(
        "--union",
        action="store_true",
        help="security mode: assert only that the trusted corpus ran, disjointly",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    targets = resolve_targets()

    if args.command == "targets":
        print("\n".join(targets))
        return 0

    all_tests = enumerate_tests(targets, root, tolerate_missing=args.union)

    if args.command == "enumerate":
        print("\n".join(all_tests))
        return 0

    if args.command == "chunk":
        if args.shard is None:
            parser.error("--shard is required for `chunk`")
        if not 1 <= args.shard <= args.shards:
            parser.error("--shard must be in 1..%d" % args.shards)
        print("\n".join(chunk_for(all_tests, args.shards, args.shard)))
        return 0

    if not args.chunk_dir:
        parser.error("--chunk-dir is required for `verify`")
    problems = verify(
        all_tests, args.shards, Path(args.chunk_dir), union_only=args.union
    )
    mode = "union" if args.union else "full"
    if problems:
        print(
            "PARTITION GUARD FAILED (%s mode) — corpus is %d test modules across "
            "%d shards:" % (mode, len(all_tests), args.shards),
            file=sys.stderr,
        )
        for problem in problems:
            print("  - %s" % problem, file=sys.stderr)
        return 1
    print(
        "partition sound (%s mode): %d test modules, %d shards, disjoint and complete"
        % (mode, len(all_tests), args.shards)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
