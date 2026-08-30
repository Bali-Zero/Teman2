#!/usr/bin/env bash
# Offline contract tests for seat_build.sh's derive_effort_from_floor() (mandate
# L09-PR3: bind dispatch effort to compute_floor). Complements test_seat_build.sh
# (pre-existing contract) and test_seat_build_tiers.sh (--tier/effort-cap/ctx-check
# surface). Uses --dry-run + --out throughout: these are policy/report-shape
# checks, never a real seat invocation.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEAT_BUILD="$REPO_ROOT/scripts/seat_build.sh"
FIXTURE="$(mktemp -d)"
MAIN_REPO="$FIXTURE/main"
LINKED_WT="$FIXTURE/linked"
TASK_FILE="$FIXTURE/task.txt"
FAKE_BIN="$FIXTURE/bin"
MUTATED_SCRIPTS_DIR="$FIXTURE/mutated-scripts"
MUTATED_LOW_SEAT_BUILD="$MUTATED_SCRIPTS_DIR/seat_build.sh"
PASS_COUNT=0
FAIL_COUNT=0

cleanup() {
    rm -rf "$FIXTURE"
}
trap cleanup EXIT

mkdir -p "$FAKE_BIN"
git init -q "$MAIN_REPO"
git -C "$MAIN_REPO" config user.email test@example.invalid
git -C "$MAIN_REPO" config user.name "Seat Build Effort Test"
printf 'fixture\n' > "$MAIN_REPO/tracked.txt"
git -C "$MAIN_REPO" add tracked.txt
git -C "$MAIN_REPO" commit -qm "test fixture"
git -C "$MAIN_REPO" worktree add -qb linked-effort-fixture "$LINKED_WT"
printf 'Effort test task, small.\n' > "$TASK_FILE"

# codex/luna is capped at medium (R2) — a real seat/tier we can point a
# derived-xhigh dispatch at to prove the cap still bites (case 6).
for stub in codex qwen; do
    printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "$FAKE_BIN/$stub"
    chmod +x "$FAKE_BIN/$stub"
done

# A copy of seat_build.sh with the hardcoded EFFORT="medium" initializer in
# main() mutated to EFFORT="low". Used by cases 1 and 4 to prove the reported
# value came from derive_effort_from_floor's OWN assignment, not from the
# pre-existing hardcoded default landing on the same string by coincidence.
# (medium is both the hardcoded default AND floor-1's derived value, so a
# naive assertion of effort=="medium" alone would pass vacuously even if
# derive_effort_from_floor did nothing at all.)
# Mirrors scripts/'s own layout (lib/, seat_build_tp1.sh, seat_ctx.json)
# because seat_build.sh sources those relative to its own SCRIPT_DIR — a bare
# copy dropped straight into $FIXTURE would fail to source them and never
# reach derive_effort_from_floor at all.
cat > "$FIXTURE/mutate_low.py" <<'MUTATE_LOW_PY'
import sys

src_path, dst_path = sys.argv[1:3]
with open(src_path) as f:
    text = f.read()
needle = '    EFFORT="medium"\n    EFFORT_EXPLICIT=false\n'
assert text.count(needle) == 1, (
    "main() init anchor not found exactly once: %d" % text.count(needle)
)
mutated = text.replace(needle, '    EFFORT="low"\n    EFFORT_EXPLICIT=false\n', 1)
with open(dst_path, "w") as f:
    f.write(mutated)
MUTATE_LOW_PY

mkdir -p "$MUTATED_SCRIPTS_DIR"
cp -R "$REPO_ROOT/scripts/lib" "$MUTATED_SCRIPTS_DIR/lib"
cp "$REPO_ROOT/scripts/seat_build_tp1.sh" "$MUTATED_SCRIPTS_DIR/seat_build_tp1.sh"
cp "$REPO_ROOT/scripts/seat_ctx.json" "$MUTATED_SCRIPTS_DIR/seat_ctx.json"
# Targets main()'s init block SPECIFICALLY, not derive_effort_from_floor's own
# gear-1 branch (which also assigns EFFORT="medium" a few dozen lines away,
# under 12-space case-arm indentation followed by a different next line) — a
# plain `sed s/EFFORT="medium"/EFFORT="low"/` with no address restriction
# rewrites BOTH occurrences (sed replaces the first match on every matching
# line, and these are two different lines), silently mutating the very
# derivation this fixture exists to isolate.
python3 "$FIXTURE/mutate_low.py" "$SEAT_BUILD" "$MUTATED_LOW_SEAT_BUILD"
chmod +x "$MUTATED_LOW_SEAT_BUILD"
# Sanity: exactly ONE occurrence changed (main()'s init) — the floor-1 branch
# inside derive_effort_from_floor must remain untouched ("medium"), or case 1
# ("still resolves to medium") would be trivially true for the wrong reason
# (both would read the mutated value).
if [ "$(grep -c 'EFFORT="low"' "$MUTATED_LOW_SEAT_BUILD")" -ne 1 ]; then
    printf 'FIXTURE SETUP FAILED: expected exactly 1 EFFORT="low" (main() init), got %s\n' \
        "$(grep -c 'EFFORT="low"' "$MUTATED_LOW_SEAT_BUILD")" >&2
    exit 1
fi
if [ "$(grep -c 'EFFORT="medium"' "$MUTATED_LOW_SEAT_BUILD")" -ne 1 ]; then
    printf 'FIXTURE SETUP FAILED: expected exactly 1 EFFORT="medium" left (derive_effort_from_floor gear-1 branch, untouched), got %s\n' \
        "$(grep -c 'EFFORT="medium"' "$MUTATED_LOW_SEAT_BUILD")" >&2
    exit 1
fi

run_case() {
    local name="$1"
    local fn="$2"
    if "$fn"; then
        printf 'PASS %s\n' "$name"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        printf 'FAIL %s\n' "$name"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

seat_env() {
    env PATH="$FAKE_BIN:$PATH" "$@"
}

report_of() {
    # $1 = script to run, remaining args = seat_build.sh argv (minus --out)
    local script="$1"
    shift
    local out="$FIXTURE/report-$$-$RANDOM.json"
    seat_env "$script" "$@" --out "$out" >/dev/null 2>"$FIXTURE/stderr-$$-$RANDOM.log" || true
    cat "$out"
}

# ── case 1 (GUILT): floor-1, no --effort, is floor-driven not the pre-existing
# hardcoded default ─────────────────────────────────────────────────────────
case_floor1_resolves_via_derivation_not_hardcoded_default() {
    local out
    out="$(report_of "$MUTATED_LOW_SEAT_BUILD" --seat qwen --gear 1 \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run)"
    # On the mutated copy, main()'s hardcoded init is EFFORT="low". If the
    # report still says "medium", the value MUST have come from
    # derive_effort_from_floor's own gear-1 assignment — the hardcoded
    # default was proven to read "low" in this exact copy.
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["effort"] == "medium", d
assert d["effort_source"] == "derived-from-floor", d' <<< "$out"
}

# ── case 2 (INNOCENCE): floor-3, no --effort, derives xhigh ─────────────────
case_floor3_derives_xhigh() {
    local out
    out="$(report_of "$SEAT_BUILD" --seat qwen --gear 3 \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run)"
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["effort"] == "xhigh", d
assert d["effort_source"] == "derived-from-floor", d' <<< "$out"
}

# ── case 3 (INNOCENCE): explicit --effort always overrides the derived
# default ────────────────────────────────────────────────────────────────────
case_explicit_effort_overrides_floor3_derivation() {
    local out
    out="$(report_of "$SEAT_BUILD" --seat qwen --gear 3 --effort low \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run)"
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["effort"] == "low", d
assert d["effort_source"] == "explicit", d' <<< "$out"
}

# ── case 4: floor-2 is advisory, NOT enforced — EFFORT is left untouched ────
case_floor2_is_advisory_not_enforced() {
    local out
    # First half: on the UNMODIFIED script, floor-2 leaves EFFORT at the
    # hardcoded init value ("medium") while logging the proposal.
    out="$(report_of "$SEAT_BUILD" --seat qwen --gear 2 \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run)"
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["effort"] == "medium", d
assert d["effort_source"] == "advisory-floor-2", d
assert d["effort_advisory"] == "high", d' <<< "$out" || return 1

    # Second half: on the MUTATED copy (hardcoded init = "low"), floor-2 must
    # STILL leave EFFORT alone — i.e. it reports "low", proving the advisory
    # branch never overwrote EFFORT. If it had derived a value the way
    # floor-1/floor-3 do, this would read "medium" or something else, not the
    # mutated copy's own untouched initializer value.
    out="$(report_of "$MUTATED_LOW_SEAT_BUILD" --seat qwen --gear 2 \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run)"
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["effort"] == "low", d
assert d["effort_source"] == "advisory-floor-2", d
assert d["effort_advisory"] == "high", d' <<< "$out"
}

# ── case 5: no --gear at all keeps the historical default ───────────────────
case_no_gear_keeps_historical_default() {
    local out
    out="$(report_of "$SEAT_BUILD" --seat qwen \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run)"
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["effort"] == "medium", d
assert d["effort_source"] == "default", d' <<< "$out"
}

# ── case 6: a derived xhigh is STILL subject to the existing per-tier cap
# (R2: codex/luna capped at medium) ─────────────────────────────────────────
case_derived_xhigh_still_capped() {
    local rc=0
    seat_env "$SEAT_BUILD" --seat codex --tier luna --gear 3 \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run \
        >/dev/null 2>/dev/null || rc=$?
    # Same exit code enforce_effort_cap uses for an explicit cap violation
    # (see test_seat_build_tiers.sh's case_codex_luna_xhigh_capped).
    [ "$rc" -eq 65 ]
}

# ── case 7: effort_advisory is JSON null (not "") when no advisory applies ──
case_effort_advisory_is_null_not_empty_string() {
    local out
    out="$(report_of "$SEAT_BUILD" --seat qwen --gear 3 \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run)"
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["effort_advisory"] is None, d
assert d["effort_advisory"] != "", d' <<< "$out"
}

# ── case 8: syntax check ─────────────────────────────────────────────────────
case_seat_build_syntax_ok() {
    bash -n "$SEAT_BUILD"
}

# Found by a blind codex-sol refutation: several refusal paths (invalid
# --effort / --gear / --seat / --tier) emit the JSON report BEFORE
# derive_effort_from_floor runs. effort_source was "" there — a fifth,
# undocumented state a consumer cannot tell apart from "resolved to nothing".
# It must be the named "unresolved" instead.
case_pre_derivation_refusal_names_its_state() {
    local out="$FIXTURE/pre-derive.json" src
    rm -f "$out"
    bash "$SEAT_BUILD" --seat nosuchseat --gear 3 --task-file "$TASK_FILE" \
        --worktree "$FIXTURE" --out "$out" --dry-run >/dev/null 2>&1 || true
    [ -f "$out" ] || return 1
    src="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['effort_source'])" "$out")"
    [ "$src" = "unresolved" ]
}

# Found by a blind codex-sol refutation: the floor-2 stderr NOTICE is the only
# user-visible signal that the advisory hold exists at all, and nothing asserted
# it — deleting the printf left the whole suite green. A needs-ruling hold whose
# announcement can vanish silently is a hold nobody will notice was dropped.
case_floor2_notice_is_actually_printed() {
    local errlog="$FIXTURE/floor2-notice.log" out="$FIXTURE/floor2-notice.json"
    rm -f "$errlog" "$out"
    seat_env "$SEAT_BUILD" --seat qwen --gear 2 --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --out "$out" --dry-run >/dev/null 2>"$errlog" || true
    grep -q 'gear 2' "$errlog" || return 1
    grep -qi 'advisory' "$errlog" || return 1
    # and the notice must NOT appear for the floors that ARE ruled
    rm -f "$errlog"
    seat_env "$SEAT_BUILD" --seat qwen --gear 3 --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --out "$out" --dry-run >/dev/null 2>"$errlog" || true
    ! grep -qi 'advisory' "$errlog"
}

run_case "GUILT: floor-1 resolves to medium via derivation, not the pre-existing hardcoded default" \
    case_floor1_resolves_via_derivation_not_hardcoded_default
run_case "INNOCENCE: floor-3, no --effort, derives xhigh" case_floor3_derives_xhigh
run_case "INNOCENCE: explicit --effort=low overrides floor-3's derived xhigh" \
    case_explicit_effort_overrides_floor3_derivation
run_case "floor-2 is advisory only, never overwrites EFFORT" case_floor2_is_advisory_not_enforced
run_case "no --gear at all keeps the historical hardcoded default" case_no_gear_keeps_historical_default
run_case "a derived xhigh (floor-3) is still subject to the existing per-tier cap" \
    case_derived_xhigh_still_capped
run_case "effort_advisory is JSON null, not empty string, when unset" \
    case_effort_advisory_is_null_not_empty_string
run_case "seat_build.sh passes bash -n" case_seat_build_syntax_ok
run_case "a refusal before derivation names its state, never empty-string" case_pre_derivation_refusal_names_its_state
run_case "floor-2 actually prints its advisory notice (and floor-3 does not)" case_floor2_notice_is_actually_printed

printf 'SUMMARY %d passed, %d failed\n' "$PASS_COUNT" "$FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ]
