"""Replayable mutation sweep for the matrix's extra_services stand-ins and the values made up per leg (runner.py, prune.py) against
test_extra_services.py (and test_prune.py for the never-list) — the same harness, rules and verdicts as merger_mutants.py (one textual
rule on a temporary copy; KILLED only on a pytest failure; STALE when the rule's text no longer occurs exactly once).

    python3 scripts/localci/tests/mutants/extra_services_mutants.py [--only NAME ...] [--list]
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from merger_mutants import ROOT, copy_tree, run_tests, verdict

RN, PR = "scripts/localci/runner.py", "scripts/localci/prune.py"
T_RN, T_PR = ("scripts/localci/tests/test_extra_services.py",), ("scripts/localci/tests/test_prune.py",)

# name: (file, text that must occur once, replacement) — every rule must turn its test file red
MUTANTS = {
    "es-tag-accepted": (RN, 'DIGEST_IMAGE = re.compile(r"[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}")', 'DIGEST_IMAGE = re.compile(r"[a-z0-9][a-z0-9._/:-]*(@sha256:[0-9a-f]{64})?")'),
    "es-image-presence-unchecked": (RN, 'if not iid.startswith("sha256:"):\n            return None, f"service {name}: image {ref} is not present',
                                    'if False:\n            return None, f"service {name}: image {ref} is not present'),
    "es-name-collision-allowed": (RN, 'or name in taken:', 'or False:'),
    "es-health-optional": (RN, 'if not isinstance(h, dict) or set(h) != {"cmd", "interval", "timeout", "retries"} or not h["cmd"]:', 'if False:'),
    "es-unknown-key-ignored": (RN, 'or (bad := sorted(set(svc) - EXTRA_SERVICE_KEYS))', 'or (bad := [])'),
    "es-expression-env-allowed": (RN, 'if (expr := sorted(k for k, v in env.items() if "${{" in v)):\n            return None, f"service {name}: env', 'if False:\n            return None, f"service {name}: env'),
    "gen-constant": (RN, 'store.setdefault(m.group(1), os.urandom(24).hex())', 'store.setdefault(m.group(1), "0" * 48)'),
    "gen-per-use": (RN, 'store.setdefault(m.group(1), os.urandom(24).hex())', 'os.urandom(24).hex()'),
    "gen-short": (RN, "os.urandom(24).hex()", "os.urandom(2).hex()"),
    "gen-not-substituted": (RN, 'return {k: GEN_RE.sub(lambda m: store.setdefault(m.group(1), os.urandom(24).hex()), str(v)) for k, v in env.items()}', 'return {k: str(v) for k, v in env.items()}'),
    "es-not-added-to-job": (RN, 'svcs = svcs + extra_svcs if extra_svcs is not None else None', 'svcs = svcs if extra_svcs is not None else None'),
    "es-service-env-unfilled": (RN, '[{**sv, "env": fill_generated(sv["env"], gen)} for sv in job["services"]]', 'job["services"]'),
    "es-step-env-unfilled": (RN, '        if st.get("env"):\n            st["env"] = fill_generated(st["env"], gen)\n', ''),
    "seed-not-run": (RN, 'if (sd := s.get("seed")):', 'if False:'),
    "seed-failure-ignored": (RN, 'if not r or "seeded" not in r:\n                return names', 'if False:\n                return names'),
    "seed-name-unchecked": (RN, 'not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name) or', ''),
    "seed-bool-size-accepted": (RN, 'type(size) is not int or not 0 < size <= 65536', 'not isinstance(size, int) or not 0 < size <= 65536'),
    "seed-distance-unchecked": (RN, 'if seed["distance"] not in ("Cosine", "Dot", "Euclid") or not re.fullmatch(r"[A-Z0-9_]+", str(seed["api_key_env"])):', 'if False:'),
    "seed-key-env-unchecked": (RN, 'if why or seed["api_key_env"] not in env:', 'if why:'),
    "seed-not-read-from-base": (RN, 'lambda rel: _extract_base_file(wt, base, safe_tree_path(rel)))', 'lambda rel: _extract_base_file(wt, cand, safe_tree_path(rel)))'),
    "net-standin-on-bridge": (RN, '"--network", f"container:{owner}" if owner else "none", "--health-cmd"', '"--network", "bridge", "--health-cmd"'),
    "gen-shared-across-legs": (RN, '    steps, gen = [], {}\n', '    steps, gen = [], globals().setdefault("_SHARED_GEN", {})\n'),
    "reached-not-checked": (RN, "    if want == 0 and unreached:", "    if False:"),
    "reached-zero-accepted": (RN, 'if seen is None or seen < sv["reached"]["min"]:', 'if seen is not None and seen < 0:'),
    "reached-counts-every-status": (RN, 'if str(k).startswith("2"))', "if True)"),
    "skip-gate-off": (RN, 'if want == 0 and (pw := job.get("playwright_skips")):', "if False:"),
    "skip-gate-off-by-one": (RN, 'sm["skipped"] > pw["max"]:', 'sm["skipped"] > pw["max"] + 1:'),
    "skip-no-summary-passes": (RN, 'if sm is None or sm["skipped"] > pw["max"]:', 'if sm is not None and sm["skipped"] > pw["max"]:'),
    "summary-first-not-last": (RN, "int(skipped[-1]) if skipped else 0", "int(skipped[0]) if skipped else 0"),
    "es-never-list-drops-extra": (PR, 'if isinstance(node.get("extra_services"), list):', 'if False:'),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mutation sweep for extra_services against its tests.")
    ap.add_argument("--only", nargs="+", metavar="NAME")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    names = a.only or list(MUTANTS)
    if unknown := [n for n in names if n not in MUTANTS]:
        print(f"unknown mutant(s): {unknown}", file=sys.stderr)
        return 2
    if a.list:
        print("\n".join(names))
        return 0
    with tempfile.TemporaryDirectory(prefix="extra-services-mutants-") as tmp:
        tree = Path(tmp)
        copy_tree(tree)
        (tree / ".github/workflows").mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ".github/workflows/tests.yml", tree / ".github/workflows/tests.yml")   # the real-context test reads BASE's job
        (tree / "apps/backend-rag/backend/app/core").mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "apps/backend-rag/backend/app/core/config.py", tree / "apps/backend-rag/backend/app/core/config.py")   # and the seed's source
        originals = {f: (tree / f).read_text() for f in (RN, PR)}
        if (rc := run_tests(tree, T_RN + T_PR)) != 0:
            print(f"baseline: the unmutated copy gives pytest exit {rc} — nothing to measure", file=sys.stderr)
            return 2
        survived, stale, errors = [], [], []
        for n in names:
            f, old, new = MUTANTS[n]
            original = originals[f]
            if original.count(old) != 1 or old == new:
                stale.append(n)
                print(f"{n:30} STALE (the rule's text occurs {original.count(old)} times)", flush=True)
                continue
            (tree / f).write_text(original.replace(old, new))
            v = verdict(run_tests(tree, T_PR if f == PR else T_RN))
            (tree / f).write_text(original)
            if v == "SURVIVED":
                survived.append(n)
            elif v != "KILLED":
                errors.append(n)
            print(f"{n:30} {v}", flush=True)
    killed = len(names) - len(survived) - len(stale) - len(errors)
    print(f"{killed}/{len(names)} killed; survivors: {survived or 'none'}; errors: {errors or 'none'}; stale: {stale or 'none'}")
    return 1 if survived or stale or errors else 0


if __name__ == "__main__":
    sys.exit(main())
