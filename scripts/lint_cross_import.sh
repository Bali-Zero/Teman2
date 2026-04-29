#!/usr/bin/env bash
# scripts/lint_cross_import.sh
#
# NB-D guard: detect cross-workspace import violations in the Vercel monorepo
# BEFORE Vercel build cascades a single-package break across all 21 apps.
#
# Subcommands:
#   validate-json   — every package.json under apps/, packages/, root must parse
#   circular        — DFS over @nuzantara/* and @balizero/* workspace deps
#   undeclared      — TS/JS source imports of @nuzantara/* / @balizero/* must be
#                     either declared in the nearest package.json deps OR aliased
#                     in the nearest tsconfig*.json compilerOptions.paths
#                     (tsconfig path aliases ARE the canonical resolution path
#                     in this repo — see apps/mouth/tsconfig.json)
#   all             — run all three (default)
#
# Exits non-zero on first failing subcommand. Emits GitHub Actions
# `::error file=...::msg` annotations so violations surface inline in PRs.
#
# Cited by: docs/audits/2026-04-29-zero-crash-audit/09_intervention_plan.md NB-D
set -euo pipefail

cmd="${1:-all}"

run_validate_json() {
  python3 <<'PYEOF'
import glob, json, sys
fail = 0
roots = ["package.json"] + sorted(
    glob.glob("apps/*/package.json") + glob.glob("packages/*/package.json")
)
for pj in roots:
    try:
        with open(pj) as fh:
            json.load(fh)
    except FileNotFoundError:
        continue
    except Exception as e:
        print(f"::error file={pj}::invalid JSON: {e}")
        fail = 1
sys.exit(fail)
PYEOF
}

run_circular() {
  python3 <<'PYEOF'
import glob, json, sys

# Build a graph restricted to workspace-scoped deps (@nuzantara/*, @balizero/*).
graph = {}
for pj in sorted(glob.glob("apps/*/package.json") + glob.glob("packages/*/package.json")):
    with open(pj) as fh:
        d = json.load(fh)
    name = d.get("name")
    if not name:
        continue
    deps = set()
    for key in ("dependencies", "devDependencies"):
        for k in (d.get(key) or {}):
            if k.startswith("@nuzantara/") or k.startswith("@balizero/"):
                deps.add(k)
    graph[name] = deps

# White-grey-black DFS cycle detection.
WHITE, GREY, BLACK = 0, 1, 2
color = {n: WHITE for n in graph}

def dfs(node, path):
    color[node] = GREY
    for nxt in graph.get(node, ()):
        c = color.get(nxt)
        if c == GREY:
            cycle = path[path.index(nxt):] + [nxt] if nxt in path else path + [nxt]
            print(f"::error::circular workspace import: {' -> '.join(cycle)}")
            sys.exit(1)
        if c == WHITE:
            dfs(nxt, path + [nxt])
        # nxt unknown (= not a workspace package) is fine — npm will resolve it.
    color[node] = BLACK

for n in list(graph.keys()):
    if color[n] == WHITE:
        dfs(n, [n])

print("no circular workspace imports")
PYEOF
}

run_undeclared() {
  python3 <<'PYEOF'
import glob, json, os, re, subprocess, sys

# JSONC-aware loader: strip /* */ and // comments + trailing commas. Used for
# tsconfig*.json which uses JSONC. Naive regex stripping is wrong because it
# would consume `/*` and `//` that appear inside string literals (e.g. the
# tsconfig path `"@/*": ["./src/*"]`). We do a hand-rolled state-machine pass
# that knows about strings.
TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")

def _strip_jsonc_comments(raw):
    out = []
    i = 0
    n = len(raw)
    in_str = False
    quote = ""
    while i < n:
        ch = raw[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(raw[i + 1])
                i += 2
                continue
            if ch == quote:
                in_str = False
            i += 1
            continue
        if ch == '"' or ch == "'":
            in_str = True
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n:
            nxt = raw[i + 1]
            if nxt == "/":
                # line comment
                j = raw.find("\n", i + 2)
                i = n if j < 0 else j
                continue
            if nxt == "*":
                # block comment
                j = raw.find("*/", i + 2)
                i = n if j < 0 else j + 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)

def load_jsonc(path):
    raw = open(path).read()
    raw = _strip_jsonc_comments(raw)
    raw = TRAILING_COMMA_RE.sub(r"\1", raw)
    return json.loads(raw)

def collect_alias_prefixes(pkg_dir):
    """Return the set of @scope/name aliases declared in any tsconfig*.json
    under pkg_dir. e.g. {'@balizero/core'}."""
    prefixes = set()
    for tsc in sorted(glob.glob(os.path.join(pkg_dir, "tsconfig*.json"))):
        try:
            d = load_jsonc(tsc)
        except Exception:
            continue
        paths = (d.get("compilerOptions") or {}).get("paths") or {}
        for key in paths:
            # 'foo/*' -> 'foo' ; '@scope/name/*' -> '@scope/name'
            base = key.split("/*", 1)[0]
            if base.startswith("@nuzantara/") or base.startswith("@balizero/"):
                prefixes.add(base)
    return prefixes

IMPORT_RE = re.compile(
    r"""(?:from|import)\s*\(?\s*['"](@(?:nuzantara|balizero)/[^'"]+)['"]"""
)

fail = 0
for pj in sorted(glob.glob("apps/*/package.json") + glob.glob("packages/*/package.json")):
    pkg_dir = os.path.dirname(pj)
    with open(pj) as fh:
        meta = json.load(fh)
    declared = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        declared.update((meta.get(key) or {}).keys())
    own = meta.get("name", "")
    if own:
        declared.add(own)  # a package can self-import via its own scope name
    declared.update(collect_alias_prefixes(pkg_dir))

    # Scan TS/JS source. Use find to avoid pulling in node_modules / .next /
    # build outputs. Limit to text files we actually own.
    try:
        files_out = subprocess.run(
            [
                "find", pkg_dir,
                "-type", "f",
                "(",
                "-name", "*.ts", "-o",
                "-name", "*.tsx", "-o",
                "-name", "*.js", "-o",
                "-name", "*.jsx", "-o",
                "-name", "*.mjs", "-o",
                "-name", "*.cjs",
                ")",
                "-not", "-path", "*/node_modules/*",
                "-not", "-path", "*/.next/*",
                "-not", "-path", "*/dist/*",
                "-not", "-path", "*/build/*",
                "-not", "-path", "*/coverage/*",
            ],
            capture_output=True, text=True, check=False,
        ).stdout.splitlines()
    except Exception as e:
        print(f"::warning::find failed in {pkg_dir}: {e}", file=sys.stderr)
        continue

    for f in files_out:
        try:
            content = open(f, "r", encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for line_no, line in enumerate(content.splitlines(), 1):
            for m in IMPORT_RE.finditer(line):
                spec = m.group(1)  # e.g. '@balizero/core/components/X'
                # strip subpath: '@balizero/core/components/X' -> '@balizero/core'
                parts = spec.split("/")
                base = "/".join(parts[:2]) if len(parts) >= 2 else spec
                # also accept exact-match alias (key may be '@balizero/core/*')
                if base in declared:
                    continue
                # accept any longer prefix that's declared
                if any(spec.startswith(d + "/") or spec == d for d in declared):
                    continue
                print(
                    f"::error file={f},line={line_no}::"
                    f"undeclared workspace import '{spec}' in {own or pkg_dir} "
                    f"(not in package.json deps and not aliased in tsconfig)"
                )
                fail = 1

if fail == 0:
    print("no undeclared workspace imports")
sys.exit(fail)
PYEOF
}

case "$cmd" in
  validate-json) run_validate_json ;;
  circular)      run_circular ;;
  undeclared)    run_undeclared ;;
  all)
    echo "=== validate-json ==="
    run_validate_json
    echo "=== circular ==="
    run_circular
    echo "=== undeclared ==="
    run_undeclared
    ;;
  *)
    echo "usage: $0 {validate-json|circular|undeclared|all}" >&2
    exit 2
    ;;
esac
