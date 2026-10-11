#!/bin/bash
# The CodeQL Analysis job's two action steps, as the localci sandbox runs them: `init <lang>` is github/codeql-action/init, `analyze <lang>`
# is github/codeql-action/analyze (merge_group shape, upload never). The command lines are the ones the hosted logs of 2026-10-10 show
# (codeql-action v4.38.2, CLI 2.27.2) and the action source builds (src/codeql.ts); BASE's copy of this file and of
# .github/codeql-config.yml is laid over the candidate tree (local.trusted_files), so a candidate cannot change what judges it.
#
# Exit codes are the CLI's own. A command that died of a signal (the shell reports 128+N: an OOM kill) re-raises that signal on this
# shell, so the driver sees a killed step (no verdict), never a failed one. Findings never change the exit code; a SARIF the hosted
# action would throw on or the API would reject is exit 1 (codeql_sarif_check.py, laid beside this file from BASE).
#
#   codeql_leg.sh init <python|javascript>      augmented config + `database init`
#   codeql_leg.sh analyze <python|javascript>   traceless extraction, finalize, run-queries, interpret-results
set -euo pipefail

MODE=${1:-}
LANG_=${2:-}
case "$MODE" in init | analyze) ;; *) echo "usage: codeql_leg.sh <init|analyze> <python|javascript>" >&2; exit 64 ;; esac
case "$LANG_" in python | javascript) ;; *) echo "codeql_leg.sh: language must be python or javascript, got '$LANG_'" >&2; exit 64 ;; esac

HERE=$(cd "$(dirname "$0")" && pwd)
CQ=${CODEQL_BIN:-/opt/codeql/codeql}
SRC=${CODEQL_SOURCE_ROOT:-/w}
WORK=${LOCALCI_CODEQL_WORK:-/tmp/cq}
BASE_CONFIG=${CODEQL_BASE_CONFIG:-$SRC/.github/codeql-config.yml}
QUERIES=${CODEQL_QUERIES:-security-extended,security-and-quality}   # the workflow's `queries:` input; the plan refuses a BASE job that says otherwise
THREADS=4
RAM=10240   # hosted passes 14575 on a 16 GB runner; the sandbox is capped at 12g, which the measured peak (8.6 GiB) fits
DB=$WORK/db
USER_CONFIG=$WORK/user-config.yaml
SARIF=$WORK/$LANG_.sarif
mkdir -p "$WORK"

step() {
  local rc=0
  echo "CMD $LANG_: $*"
  "$@" || rc=$?
  if [ "$rc" -gt 128 ] && [ "$rc" -le 192 ]; then
    echo "codeql_leg.sh: '$2 $3' died of signal $((rc - 128)): no verdict" >&2
    kill -s "$((rc - 128))" "$$" || true
    sleep 1
  fi
  return "$rc"
}

# No verdict on the candidate: this leg cannot say, so it dies of a signal and the driver reads a killed step (ERROR), never a red exit.
no_verdict() {
  echo "codeql_leg.sh: no verdict: $*" >&2
  kill -s KILL "$$" || true
  sleep 1
  exit 75
}

if [ "$MODE" = init ]; then
  # The action writes its "augmented user configuration": the config file with `queries` replaced by the input. Only that block is
  # rewritten, as text, so every other key (query-filters, paths-ignore) reaches the CLI exactly as BASE wrote it.
  python3 -I - "$BASE_CONFIG" "$QUERIES" "$USER_CONFIG" <<'PY' || no_verdict "BASE's .github/codeql-config.yml has a queries block this rewriter does not read as text (inline value, or a comment inside the block); the matrix follows BASE's shape before this leg runs"
import re
import sys

src, queries, dest = sys.argv[1:4]
lines = open(src, encoding="utf-8").read().splitlines()
block = ["queries:"] + [f"  - uses: {q.strip()}" for q in queries.split(",") if q.strip()]


def comment(x):
    return x.lstrip().startswith("#")


out, i, placed = [], 0, False
while i < len(lines):
    key = lines[i].split("#")[0].rstrip()
    if re.match(r"^queries\s*:\s*\S", key):   # `queries: [a, b]` or `queries: x`: not a block, and a second `queries:` key would be a duplicate
        sys.exit(3)
    if key == "queries:":
        i += 1
        while i < len(lines):   # the block ends at the first column-0 line that is not a list item: a blank or a comment before the next key stays
            if not lines[i].strip():
                nxt = next((x for x in lines[i + 1:] if x.strip()), "-")
                if nxt[0] not in " \t-":
                    break
            elif lines[i][0] not in " \t-":
                break
            i += 1
        rest = next((x for x in lines[i:] if x.strip() and not comment(x)), "k")
        if rest[0] in " \t-":   # a column-0 comment inside the block: its later items would attach to the block written here
            sys.exit(3)
        out += block
        placed = True
        continue
    out.append(lines[i])
    i += 1
open(dest, "w", encoding="utf-8").write("\n".join(out if placed else block + out) + "\n")
PY
  step "$CQ" version --format=terse >"$WORK/version.out"
  cat "$WORK/version.out"
  [ -n "${CODEQL_PIN:-}" ] || no_verdict "CODEQL_PIN (the matrix's pin) is not set: nothing says which CLI this leg must be"
  [ "$(tail -n 1 "$WORK/version.out")" = "$CODEQL_PIN" ] || no_verdict "the local CLI reports '$(tail -n 1 "$WORK/version.out")', the pin is '$CODEQL_PIN': not the CLI the matrix proved parity on"
  step "$CQ" database init --force-overwrite --db-cluster "$DB" --source-root="$SRC" --calculate-language-specific-baseline \
    --sublanguage-file-coverage --extractor-include-aliases --language="$LANG_" --codescanning-config="$USER_CONFIG"
  exit 0
fi

TRACE_OPTS=()
if [ "$LANG_" = javascript ]; then
  mkdir -p "$WORK/trap"
  TRACE_OPTS=("-O=javascript.trap.cache.dir=$WORK/trap" "-O=javascript.trap.cache.bound=1024" "-O=javascript.trap.cache.write=true")
fi
step "$CQ" database trace-command --index-traceless-dbs ${TRACE_OPTS[@]+"${TRACE_OPTS[@]}"} "$DB/$LANG_"   # empty-array safe on bash 3.2 too
step "$CQ" database finalize --finalize-dataset --threads="$THREADS" --ram="$RAM" "$DB/$LANG_"
step "$CQ" database run-queries --ram="$RAM" --threads="$THREADS" --expect-discarded-cache "$DB/$LANG_" --min-disk-free=1024 -v
# interpret-results is reconstructed from the action's src/codeql.ts: it adds metadata (baseline file info, query help, rule grouping)
# to the SARIF and cannot change which results exist
step "$CQ" database interpret-results --threads="$THREADS" --format=sarif-latest -v --output="$SARIF" --print-diagnostics-summary \
  --print-metrics-summary --sarif-add-baseline-file-info --sarif-codescanning-config="$USER_CONFIG" --sarif-group-rules-by-pack \
  --sarif-include-query-help=always --sublanguage-file-coverage --sarif-category "/language:$LANG_" --sarif-include-diagnostics "$DB/$LANG_"

# What the analyze action does with the SARIF even when it uploads nothing, and what the PR lane's upload then rejects: a file the action
# throws on, or one over the documented upload limits, is a red hosted job and a FAIL here. The findings stay data for the receipt.
python3 -I "$HERE/codeql_sarif_check.py" "$SARIF" "$LANG_"
