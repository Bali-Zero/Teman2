#!/bin/bash
# cc_headless_shape_bench.sh — re-measure what one headless `claude -p` costs under each
# invocation shape, on THIS machine, now. Same prompt for every shape; usage read from the
# JSON envelope. Numbers are environment-dependent (hooks, pending fleet mail, plugins), which
# is exactly why this script exists instead of a frozen table. Usage: bench.sh [outdir] ;
# SHAPES='label:flag1|flag2;label:flag1|flag2' (pipe-separated flags, so a
# genuinely EMPTY flag value round-trips — no eval, no word-splitting) to
# override the default set.
P='Reply with exactly the word PONG and nothing else.'
OUTDIR="${1:-/tmp/cc-shape-bench}"; mkdir -p "$OUTDIR"
run() {
  local label="$1"; shift
  local t0=$(date +%s)
  # context-diet: exempt — bench harness measures the unflagged baseline on purpose
  claude -p "$P" --model haiku --output-format json --max-turns 1 "$@" </dev/null >"$OUTDIR/$label.json" 2>"$OUTDIR/$label.err"
  local rc=$?; local t1=$(date +%s)
  python3 - "$label" "$rc" "$((t1-t0))" "$OUTDIR/$label.json" <<'PY'
import json,sys
label,rc,secs,path=sys.argv[1:5]
raw=open(path).read().strip()
try:
    d=json.loads(raw); u=d.get('usage',{})
    cr=u.get('cache_read_input_tokens',0); cc=u.get('cache_creation_input_tokens',0); i=u.get('input_tokens',0)
    print(f"{label:28s} rc={rc} {secs:>3}s result={str(d.get('result',''))[:8]!r:10s} TOTAL_IN={i+cc+cr} (in={i} cache_create={cc} cache_read={cr}) turns={d.get('num_turns')} err={d.get('is_error')}")
except Exception:
    print(f"{label:28s} rc={rc} {secs:>3}s NOJSON {raw[:160]!r}")
PY
}
if [ -n "${SHAPES:-}" ]; then
  IFS=';' read -ra L <<< "$SHAPES"
  for s in "${L[@]}"; do
    label="${s%%:*}"; flags="${s#*:}"; [ "$flags" = "$label" ] && flags=""
    # '|'-separated (not space-separated + eval): a genuinely empty flag
    # value (e.g. label:--setting-sources|) must survive as its own empty
    # array element, not vanish under word-splitting or eval re-quoting.
    # `read -ra` on its own drops a TRAILING empty field (bash quirk, same
    # class of bug this fix exists for) — append a sentinel token, split,
    # then slice it back off, so a trailing empty field is preserved.
    flagarr=()
    if [ -n "$flags" ]; then
      IFS='|' read -ra flagarr <<< "${flags}|__CDBENCH_END__"
      flagarr=("${flagarr[@]:0:$((${#flagarr[@]}-1))}")
    fi
    run "$label" "${flagarr[@]}"
  done
else
  run default
  run restricted --restricted
  run restricted_strictmcp --restricted --strict-mcp-config
  run setting_sources_empty --setting-sources ""
  run safe_mode --safe-mode
fi
