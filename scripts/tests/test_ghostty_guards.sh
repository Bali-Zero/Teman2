#!/usr/bin/env bash
# test_ghostty_guards.sh — guilt AND innocence for the two guards in the Ghostty
# fleet profile (superscar #3: a guard is not shipped until it proves both).
#
# Guard 1 — the Application Support precedence check, in BOTH verify.sh and
# install.sh. macOS searches ~/Library/Application Support/com.mitchellh.ghostty/
# config.ghostty BEFORE any XDG location, so a file there silently outranks the
# whole installed profile. It has to be judged by CONTENT, not existence, because
# Ghostty.app creates that file empty by itself — a presence test would fail
# forever on every machine and train the reader to ignore the script.
#
# It shipped broken and was fixed on 2026-08-18: `grep -c` prints its count on
# stdout AND exits 1 when the count is zero, so `$(grep -c ... || echo 0)`
# appended a SECOND zero and the numeric test died on the two-line string "0\n0"
# with `integer expression expected`. This is the W104 class, already pinned for
# .claude/scripts/codex-spalla.sh by test_codex_spalla_grep_c.sh — the cure there
# was scoped to ONE FILE, so the class walked straight into a new one four days
# later. Section 1 is what stops it walking into the next.
#
# Guard 2 — the machine-profile check in verify.sh. It used to accept
# machine.ghostty if it matched ANY of the three host profiles, so M5's profile
# installed on Pro passed, working-directory and all.
#
# Nothing here touches the caller's real ~/.config/ghostty or the real
# ~/Library: every case runs against a fabricated HOME.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SRC="$REPO_ROOT/infra/ghostty"
VERIFY="$SRC/verify.sh"
INSTALL="$SRC/install.sh"
FAILURES=0
CASES=0

fail() {
    FAILURES=$((FAILURES + 1))
    echo "  ✗ FAIL: $1"
    [[ $# -gt 1 ]] && printf '    %s\n' "${@:2}"
}
pass() { echo "  ✓ $1"; }

for f in "$VERIFY" "$INSTALL"; do
    [[ -f "$f" ]] || {
        echo "FATAL: $f not found"
        exit 2
    }
done

# The verifier shells out to the real Ghostty binary. Without it every case would
# fail for the same irrelevant reason and the corpus would be measuring the
# machine, not the guard (W108: a fake world too poor to reach the code under
# test reports its own poverty).
GHOSTTY="/Applications/Ghostty.app/Contents/MacOS/ghostty"
if [[ ! -x "$GHOSTTY" ]]; then
    echo "SKIP: Ghostty is not installed on this machine — the guards cannot be exercised"
    exit 0
fi

this_machine() {
    case "$(hostname -s 2>/dev/null)" in
    Nuzantara) echo pro ;;
    Air-M5) echo m5 ;;
    Mini-Pro2 | mini-pro2) echo mini ;;
    *) echo "" ;;
    esac
}
MACHINE="$(this_machine)"
if [[ -z "$MACHINE" ]]; then
    echo "SKIP: hostname is not one of the three fleet machines — the host-aware guard has no expected answer here"
    exit 0
fi

# A HOME holding a correctly installed profile, so any failure a case produces is
# attributable to the thing that case varies and nothing else.
build_home() {
    local machine="$1" root
    root="$(mktemp -d)"
    mkdir -p "$root/.config/ghostty" "$root/Library/Application Support/com.mitchellh.ghostty"
    cp "$SRC/config" "$SRC/fleet.ghostty" "$SRC/keys.ghostty" "$SRC/verify-latest.sh" "$root/.config/ghostty/"
    cp "$SRC/machines/$machine.ghostty" "$root/.config/ghostty/machine.ghostty"
    printf '%s' "$root"
}

APPSUP_REL="Library/Application Support/com.mitchellh.ghostty/config.ghostty"

run_case() {
    local label="$1" home="$2" want_rc="$3" want_text="$4"
    CASES=$((CASES + 1))
    local out rc
    out="$(HOME="$home" bash "$VERIFY" 2>&1)"
    rc=$?
    if grep -q 'integer expression expected' <<<"$out"; then
        fail "$label: the guard could not evaluate its own count (W104 \"0\\n0\" regression)" "$out"
        return
    fi
    if [[ "$rc" != "$want_rc" ]]; then
        fail "$label: rc $rc, expected $want_rc" "$(grep -i 'application support' <<<"$out" | head -2)"
        return
    fi
    if ! grep -qi "$want_text" <<<"$out"; then
        fail "$label: verdict did not say \"$want_text\"" "$(grep -i 'application support' <<<"$out" | head -2)"
        return
    fi
    pass "$label"
}

# ══════════════════════════════════════ Guard 1 — Application Support precedence
# INNOCENCE first: the three states that must stay quiet. Two are the ones the
# broken arithmetic hit, and one of those — "exists but empty" — is the state the
# running app CREATES ON ITS OWN, i.e. the everyday case.
H="$(build_home "$MACHINE")"
run_case "innocence — no Application Support config at all" "$H" 0 "no higher-priority config"

: >"$H/$APPSUP_REL"
run_case "innocence — file exists but is EMPTY (what Ghostty.app itself creates)" "$H" 0 "present but empty"

printf '# a comment\n\n   \n' >"$H/$APPSUP_REL"
run_case "innocence — comments and blank lines only" "$H" 0 "present but empty"

# GUILT
printf 'font-size = 8\nbackground-opacity = 1\n' >"$H/$APPSUP_REL"
run_case "guilt — two real settings outranking the profile" "$H" 1 "takes PRECEDENCE"

# The count must be REPORTED, not just detected: "a file is in the way" without a
# number sends the reader to look at the wrong thing.
CASES=$((CASES + 1))
OUT="$(HOME="$H" bash "$VERIFY" 2>&1)"
if grep -q 'holds 2 setting' <<<"$OUT"; then
    pass "guilt — names how many settings are in the way"
else
    fail "guilt: the count was not in the message" "$(grep -i 'precedence' <<<"$OUT" | head -1)"
fi

# install.sh carries the same guard and must agree. A fix that covers only the
# half that bit you is half a fix.
CASES=$((CASES + 1))
IOUT="$(HOME="$H" bash "$INSTALL" 2>&1)"
if grep -q 'integer expression expected' <<<"$IOUT"; then
    fail "install.sh: same guard, still cannot evaluate its count"
elif ! grep -qi 'takes precedence' <<<"$IOUT"; then
    fail "install.sh: silent about a config that outranks what it just installed" "$(tail -3 <<<"$IOUT")"
else
    pass "guilt — install.sh warns about the same file the verifier fails on"
fi

# install.sh must stay silent on the innocent world, or its warning becomes noise.
CASES=$((CASES + 1))
: >"$H/$APPSUP_REL"
IOUT="$(HOME="$H" bash "$INSTALL" 2>&1)"
if grep -q 'integer expression expected' <<<"$IOUT"; then
    fail "install.sh innocence: the guard could not evaluate (W104 regression)"
elif grep -qi 'takes precedence' <<<"$IOUT"; then
    fail "install.sh innocence: warned about an EMPTY file — the state the app creates by itself"
else
    pass "innocence — install.sh stays quiet on the empty file the app creates"
fi
rm -rf "$H"

# ═══════════════════════════════════════════ Guard 2 — the machine profile check
# GUILT: another host's profile. It parses, it validates, every setting in it is
# legal — the only thing wrong is that it belongs to a different machine, which
# is exactly what a value-level check cannot see.
OTHER=pro
[[ "$MACHINE" == pro ]] && OTHER=m5
H2="$(build_home "$OTHER")"
CASES=$((CASES + 1))
OUT="$(HOME="$H2" bash "$VERIFY" 2>&1)"
RC=$?
# Assert the FAIL branch's own wording. An earlier version of this case grepped
# for "machine profile", which appears in BOTH verdicts — "machine profile
# installed: pro (matches this host)" and "wrong machine profile: ...". Mutation
# testing caught it: neutering the check to `cmp -s dest dest` left this case
# GREEN, because the wrong profile was still rejected, just by the
# working-directory check further down, and the passing verdict's own text
# satisfied the grep. Right answer, wrong reason (superscar #3, over-match).
if [[ "$RC" == "0" ]]; then
    fail "guilt: verify passed with ${OTHER}'s profile installed on a $MACHINE host" "$(grep -i 'machine profile' <<<"$OUT" | head -1)"
elif ! grep -q "wrong machine profile" <<<"$OUT"; then
    fail "guilt: rejected, but NOT by the profile check — something else caught it" "$(grep -iE 'FAIL' <<<"$OUT" | head -3)"
elif ! grep -q "machine.ghostty is '$OTHER'" <<<"$OUT"; then
    fail "guilt: the profile check fired but did not name which profile is installed" "$(grep -i 'wrong machine profile' <<<"$OUT" | head -1)"
else
    pass "guilt — ${OTHER}'s profile on a $MACHINE host is rejected BY THE PROFILE CHECK, which names it"
fi
rm -rf "$H2"

# INNOCENCE: this host's own profile must pass, or the guard is just noise.
H3="$(build_home "$MACHINE")"
CASES=$((CASES + 1))
OUT="$(HOME="$H3" bash "$VERIFY" 2>&1)"
RC=$?
if [[ "$RC" != "0" ]]; then
    fail "innocence: verify rejected this host's OWN profile" "$(grep -vE '^[[:space:]]*ok' <<<"$OUT" | head -4)"
else
    pass "innocence — the correct profile for $MACHINE passes clean"
fi
rm -rf "$H3"

# ═══════════════════════════════════════════════════ argument handling, install.sh
# `--machine` with no value used to consume nothing and fall through to hostname
# detection, so a typo installed a profile the caller did not ask for.
# rc != 0 is NOT enough here, and mutation testing proved it: with the guard
# deleted, `--machine` with no value still exits non-zero, because `case "$2"`
# under `set -u` dies on an unbound variable — and `--machine banana` still
# exits non-zero, because the install fails later looking for a profile file
# that does not exist. Both are the right verdict for the wrong reason, and both
# leave a caller staring at a message about something else. So assert the
# refusal's own words and its exact exit code.
H4="$(mktemp -d)"
CASES=$((CASES + 1))
OUT="$(HOME="$H4" bash "$INSTALL" --machine 2>&1)"
RC=$?
if [[ "$RC" == "0" ]]; then
    fail "guilt: --machine with no value was accepted and installed something"
elif ! grep -q -- "--machine needs a value" <<<"$OUT"; then
    fail "guilt: --machine with no value failed for some OTHER reason" "rc=$RC" "$(head -3 <<<"$OUT")"
elif [[ "$RC" != "2" ]]; then
    fail "guilt: refused with the right message but rc=$RC, expected 2"
else
    pass "guilt — --machine with no value is refused by its own guard, rc=2"
fi
CASES=$((CASES + 1))
OUT="$(HOME="$H4" bash "$INSTALL" --machine banana 2>&1)"
RC=$?
if [[ "$RC" == "0" ]]; then
    fail "guilt: --machine banana was accepted"
elif ! grep -q "unknown machine 'banana'" <<<"$OUT"; then
    fail "guilt: banana was rejected, but not by the name check — the caller is told the wrong thing" "rc=$RC" "$(head -3 <<<"$OUT")"
elif [[ "$RC" != "2" ]]; then
    fail "guilt: right message but rc=$RC, expected 2"
else
    pass "guilt — an unknown machine name is refused by name, rc=2"
fi
rm -rf "$H4"

# ═══════════════════════════════ Guard 3 — rollback, in BOTH of its two worlds
# Added after a cross-family reviewer proved the whole `restore()` body could be
# replaced with `return 0` and this corpus stayed green. A recovery path nothing
# exercises is a recovery path nobody knows is broken.
#
# A source tree with a deliberately invalid setting: the install completes the
# copies, then Ghostty rejects the result, then rollback runs. That is the ONLY
# path on which restore() exists.
broken_source() {
    local dir
    dir="$(mktemp -d)"
    cp "$SRC/config" "$SRC/fleet.ghostty" "$SRC/keys.ghostty" "$SRC/verify-latest.sh" "$SRC/install.sh" "$dir/"
    mkdir -p "$dir/machines"
    cp "$SRC"/machines/*.ghostty "$dir/machines/"
    printf '\nfont-size = not-a-number\n' >>"$dir/fleet.ghostty"
    printf '%s' "$dir"
}

# UPGRADE: something was already installed. It must come back byte-for-byte.
CASES=$((CASES + 1))
H5="$(mktemp -d)"
mkdir -p "$H5/.config/ghostty"
printf '# the config that was here before\nfont-size = 21\n' >"$H5/.config/ghostty/config"
BEFORE_SHA="$(shasum -a 256 "$H5/.config/ghostty/config" | cut -d' ' -f1)"
BS="$(broken_source)"
HOME="$H5" bash "$BS/install.sh" >/dev/null 2>&1
IRC=$?
AFTER_SHA="$(shasum -a 256 "$H5/.config/ghostty/config" 2>/dev/null | cut -d' ' -f1)"
if [[ "$IRC" == "0" ]]; then
    fail "rollback/upgrade: install REPORTED SUCCESS with an invalid source"
elif [[ "$BEFORE_SHA" != "$AFTER_SHA" ]]; then
    fail "rollback/upgrade: the previous config was NOT restored" "before=$BEFORE_SHA" "after=${AFTER_SHA:-<file gone>}"
else
    pass "guilt — a rejected config rolls back and the previous one returns byte-identical"
fi
rm -rf "$H5" "$BS"

# FRESH: nothing was installed. Rollback must remove what it placed, not leave a
# half-written config while reporting that nothing was lost.
CASES=$((CASES + 1))
H6="$(mktemp -d)"
BS="$(broken_source)"
HOME="$H6" bash "$BS/install.sh" >/dev/null 2>&1
IRC=$?
SURVIVORS="$(ls -A "$H6/.config/ghostty" 2>/dev/null | grep -vE '^\.backup-' | wc -l | tr -d ' ')"
if [[ "$IRC" == "0" ]]; then
    fail "rollback/fresh: install REPORTED SUCCESS with an invalid source"
elif [[ "$SURVIVORS" != "0" ]]; then
    fail "rollback/fresh: $SURVIVORS file(s) left behind after a failed install" "$(ls -A "$H6/.config/ghostty" 2>/dev/null | tr '\n' ' ')"
else
    pass "guilt — a failed FRESH install leaves nothing behind"
fi
rm -rf "$H6" "$BS"

# ══════════════════════════ Guard 4 — a tool that cannot answer is not a pass
# verify.sh shells out to the Ghostty binary for four separate questions. If the
# binary cannot answer one of them, that is a finding — not a silent skip and
# certainly not an "ok". `GHOSTTY_BIN` is overridable, so this is testable with a
# stand-in that answers some subcommands and fails others.
fake_ghostty() {
    local dir fail_on
    dir="$(mktemp -d)"
    fail_on="$1"
    cat >"$dir/ghostty" <<EOF
#!/usr/bin/env bash
case "\$1" in
  --version)         echo "Ghostty 1.3.1"; exit 0 ;;
  +validate-config)  exit 0 ;;
  $fail_on)          echo "stand-in: refusing $fail_on" >&2; exit 3 ;;
  +show-config)      echo "working-directory = \$HOME"; exit 0 ;;
  +show-face)        echo "found in face \"\$(sed -n 's/^--font-family=//p' <<<"\$2")\""; exit 0 ;;
  +ssh-cache)        echo "no hosts"; exit 0 ;;
  *)                 exit 0 ;;
esac
EOF
    chmod +x "$dir/ghostty"
    printf '%s' "$dir/ghostty"
}

for SUB in +ssh-cache +show-config +show-face; do
    CASES=$((CASES + 1))
    H7="$(build_home "$MACHINE")"
    FG="$(fake_ghostty "$SUB")"
    OUT="$(HOME="$H7" GHOSTTY_BIN="$FG" bash "$VERIFY" 2>&1)"
    RC=$?
    if [[ "$RC" == "0" ]]; then
        fail "guard4: verify PASSED while the binary could not answer $SUB" "$(tail -3 <<<"$OUT")"
    elif ! grep -q -- "$SUB" <<<"$OUT"; then
        fail "guard4: verify failed but never named $SUB as the reason" "$(grep -iE 'FAIL' <<<"$OUT" | head -2)"
    else
        pass "guilt — a binary that cannot answer $SUB is a failure that names itself (rc=$RC)"
    fi
    rm -rf "$H7" "$(dirname "$FG")"
done

# ═══════════════════ Guard 5 — unreadable is its own verdict, not "empty"
# The Application Support guard once set its count to 0 when the count FAILED,
# then fell through to the success branch, so the verifier printed both "cannot
# count" and "present but empty (no effect)" — the second contradicting the
# first. Unreadable and empty must never share an outcome.
CASES=$((CASES + 1))
H8="$(build_home "$MACHINE")"
printf 'font-size = 9\n' >"$H8/$APPSUP_REL"
chmod 000 "$H8/$APPSUP_REL"
OUT="$(HOME="$H8" bash "$VERIFY" 2>&1)"
RC=$?
if [[ "$RC" == "0" ]]; then
    fail "guard5: an UNREADABLE higher-priority config passed clean"
elif grep -qi 'present but empty' <<<"$OUT"; then
    fail "guard5: verify called an unreadable file empty — a claim it had just said it could not make" "$(grep -iE 'application support|cannot read' <<<"$OUT")"
elif ! grep -qi 'cannot read' <<<"$OUT"; then
    fail "guard5: failed, but not because the file is unreadable" "$(grep -iE 'FAIL' <<<"$OUT" | head -2)"
else
    pass "guilt — an unreadable Application Support config is its own verdict, never 'empty'"
fi
chmod 644 "$H8/$APPSUP_REL"
rm -rf "$H8"

echo
if ((FAILURES > 0)); then
    echo "FAIL: $FAILURES of $CASES ghostty-guard cases"
    exit 1
fi
echo "PASS: $CASES/$CASES ghostty-guard cases"
