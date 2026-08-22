#!/usr/bin/env bash
# Guilt + innocence + mode for .claude/hooks/codex-spalla-trigger.sh's secret
# hygiene (cicatrix superscar #4 — secret in the clear).
#
# The defect this pins: the hook logs `tool_input.command` verbatim to
# ~/logs/codex-spalla-trigger.jsonl. Measured on the live file before the fix,
# mode 0644 (world-readable), never redacted.
#
# MAGNITUDE is stated as the STABLE conclusion, not as a count, because the
# counts are not stable: 3 runs carry secret material — 1 whole token (ends at
# char 151 inside the 200-char logged field) plus 2 truncation-clipped partials
# (both ending EXACTLY at char 200, the truncation boundary itself, which is
# what a value cut off mid-token looks like). Earlier drafts of this header
# said "11 values, 108 chars each" (a LINE count read as a VALUE count) and
# then "2 whole tokens" (a truncation artifact read as two more complete
# secrets); both corrected by the Gear-3 gate. The literal line counts that
# used to be quoted here ("14 matching lines, 13 bare") were an INSTANT, not a
# fact — re-measured at 2026-08-21T20:28Z the same file gave 24 matching lines,
# because this hook logs the very greps that measure it. The 3 secret-bearing
# runs did not move.
#
# The fix: (a) `umask 077` + an explicit `chmod 0600` for a log that already
# existed at the old mode (`>>` does NOT change an existing file's mode), and
# (b) redaction of the secret VALUE before truncation.
#
# ── HOW THE MATCHER IS PINNED ────────────────────────────────────────────────
# The value branch fires on four NAME shapes plus two non-name shapes, and each
# gets its own case(s) here, because two rounds of history show the failure mode
# is always an off-by-one at one end of the name:
#   a. DELIMITED SEGMENT — keyword bounded by `_`/`-`/string-start-or-end, with
#      an optional plural `s`. v1 of this fix matched `TOKEN=` and missed
#      `TOKEN_5=` (missing wildcard AFTER — that exact off-by-one is how a probe
#      printed four real tokens while believing it redacted). v2 required >=1
#      char BEFORE the keyword and missed a bare `TOKEN=` (the same off-by-one,
#      mirrored). Both directions have cases below.
#   b. UNDELIMITED COMPOUND — a bounded PREFIX VOCABULARY immediately followed
#      by a credential word (`APIKEY=`, `authtoken=`, `accesskey=`, `mytoken=`),
#      including keyword-then-keyword (`SECRETKEY=`). v2 narrowed so hard that
#      TWELVE forms leaked in full; the vocabulary is what re-closes them
#      without re-opening `monkey=patch` (`mon` is not in the vocabulary). Every
#      vocabulary entry and every credential word has its own case, in the two
#      loops below — an alternation nothing can fail on is not pinned.
#   c. ANY alphanumeric prefix + TOKEN/SECRET/PASSWORD/PASSWD/CREDENTIAL, but
#      NOT `KEY`. Measured, not stylistic: a bounded vocabulary still leaked
#      `PGPASSWORD=` — 99 occurrences in the live log — because nobody lists
#      `PG`. The five wide words practically never END an innocent identifier;
#      `KEY` does (`monkey`, `pubkey`, `nkeys`, `topkey`), so `KEY` stays
#      bounded and `<any-prefix>KEY=` is a NAMED, measured hole, not a claim of
#      closure. One case per wide word below.
#   d. BARE GENERIC — `pass=`, `pwd=`, `auth=`.
#   plus OPTIONAL QUOTE between name and separator, so a JSON body
#      (`-d {"api_key": "<v>"}`) is covered, not just shell/header shapes.
#   e. URL USERINFO — `scheme://user:<secret>@host`.
#   f. bare `Bearer <v>` — no keyword in a NAME. (The `Authorization: Bearer`
#      alternation that used to sit beside it was measured byte-for-byte dead
#      over the whole live log and deleted; only the bare one remains.)
#   g. RULE ORDER, which is itself a rule and had no case at all until the
#      Gear-3 gate found a LEAK caused purely by it. Rule 2 rewrites NAME +
#      separator + the whole value, so it destroys markers the other rules
#      anchor on and must run LAST. Two adjacencies are pinned below:
#      rule-2-before-rule-4 leaked a token in full (`X-Auth: Bearer <v>` became
#      `X-Auth=<REDACTED> <v>`), and rule-4-before-rule-3 leaks a URL password
#      (`Bearer postgresql://u:<v>@h` — rule 4 eats the scheme name).
# Plus three properties whose mutants used to SURVIVE (the gate deleted each and
# the suite still passed; two of them leaked a secret in full): the QUOTED-value
# alternations, the explicit `chmod` on a PRE-EXISTING log, and the
# REDACT-BEFORE-TRUNCATE ordering. Each now has a case that fails without it.
#
# ── INNOCENCE ────────────────────────────────────────────────────────────────
# The gate's other central finding: the suite once shipped 10 guilt cases and
# ONE innocence case for a matcher that had just been widened. Guilt coverage
# without a matching innocence corpus is not proof the widening is safe
# (cicatrix #3, guard-over-match). Each innocence case is a form that LOOKS like
# it should trip the keyword but must NOT be redacted. The corpus deliberately
# spans more than KEY-substrings: PASSWORD (`PasswordAuthentication=no`), TOKEN
# (`TOKENIZER=fast`) and SECRET (`-k 'secret_scanning'`) forms are here because
# an earlier version of this header claimed "TOKEN/KEY/SECRET/etc substrings"
# while all 30 keyword occurrences in it were `key`/`Key`/`KEY`. Added
# 2026-08-22 for the same reason one step further out: rules 3 and 4 had ZERO
# innocence cases, so no over-match or boundary mutant in EITHER of them was
# killable — the URL rule's userinfo class, the Bearer rule's `\b` and its
# length floor could each be widened with the suite still green. One case each,
# below.
#
# Method: run the REAL hook (not a reimplementation) with a temporary HOME per
# case, feed it a PostToolUse-shaped JSON payload on stdin via python3 (so a
# secret-looking string never has to survive bash quoting), and inspect the
# resulting log file's content + mode. Every secret-shaped string below is
# SYNTHETIC.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOOK="$REPO_ROOT/.claude/hooks/codex-spalla-trigger.sh"
fails=0
total=0
guilt_n=0
innocence_n=0
mode_n=0

[ -f "$HOOK" ] || { echo "FAIL: hook missing at $HOOK"; exit 1; }

# run_hook <home_dir> <tool_name> <command_string>
# Feeds a minimal PostToolUse payload to the hook with HOME pointed at a
# scratch dir, so the hook's own $HOME/logs/... path lands there instead of
# the real ~/logs/.
run_hook() {
    local home="$1" tool="$2" cmd="$3"
    local payload
    payload="$(python3 -c '
import json, sys
tool, cmd = sys.argv[1], sys.argv[2]
print(json.dumps({"tool_name": tool, "tool_input": {"command": cmd}}))
' "$tool" "$cmd")"
    HOME="$home" bash "$HOOK" <<<"$payload" >/dev/null 2>&1
}

log_line() {  # log_line <home_dir> — last line of that HOME's log, if any
    local home="$1"
    tail -n1 "$home/logs/codex-spalla-trigger.jsonl" 2>/dev/null
}

file_mode() {  # file_mode <path>
    python3 -c 'import os,sys;print(oct(os.stat(sys.argv[1]).st_mode & 0o777)[2:])' "$1" 2>/dev/null \
        || stat -c '%a' "$1" 2>/dev/null
}

case_result() {  # case_result <label> <0=pass|1=fail> <category: guilt|innocence|mode>
    local label="$1" ok="$2" category="${3:?category required}"
    total=$((total + 1))
    case "$category" in
        guilt) guilt_n=$((guilt_n + 1)) ;;
        innocence) innocence_n=$((innocence_n + 1)) ;;
        mode) mode_n=$((mode_n + 1)) ;;
        *) echo "FAIL: unknown case_result category '$category' for [$label]"; fails=$((fails + 1)); return ;;
    esac
    if [ "$ok" -eq 0 ]; then
        echo "PASS[$label]"
    else
        echo "FAIL[$label]"
        fails=$((fails + 1))
    fi
}

cleanup_dirs=()
# shellcheck disable=SC2329  # invoked indirectly via `trap cleanup EXIT` below
cleanup() {
    local d
    for d in "${cleanup_dirs[@]:-}"; do
        [ -n "$d" ] && rm -rf "$d"
    done
}
trap cleanup EXIT

# assert_redacted <label> <command> <needle that must NOT survive>
assert_redacted() {
    local label="$1" cmd="$2" needle="$3" tmp line ok
    tmp="$(mktemp -d)"; cleanup_dirs+=("$tmp")
    run_hook "$tmp" "Bash" "$cmd"
    line="$(log_line "$tmp")"
    ok=1
    [ -n "$line" ] && ! printf '%s' "$line" | grep -qF -- "$needle" && ok=0
    case_result "$label" "$ok" guilt
}

# ───────────────────────────────────────────────────────────── GUILT ──

# 1. A live-shaped Anthropic OAuth token inside a Bash command — the exact
#    historical leak shape (one 108-char run in the live log, cleartext).
#    Deliberately assigned to a NON-credential name (`X=`), so ONLY the
#    `sk-ant-` prefix rule can catch it.
TOKEN1="sk-ant-oat01-$(python3 -c 'import secrets; print(secrets.token_hex(48))')"
assert_redacted "guilt-sk-ant-oat-token-not-in-log" \
    "echo hello && export X=$TOKEN1" "$TOKEN1"

# 2. SUFFIXED variable name — CLAUDE_CODE_OAUTH_TOKEN_5=, not the bare TOKEN=
#    a naive redactor would only catch. Pins the RIGHT-side wildcard, the one
#    measured to be load-bearing (see the hook's comment).
assert_redacted "guilt-suffixed-oauth-token-var-value-not-in-log" \
    "export CLAUDE_CODE_OAUTH_TOKEN_5=somesecretvalue123" "somesecretvalue123"

# 3. A GitHub PAT (ghp_...). NOT placed in a URL: the URL-userinfo rule added
#    2026-08-22 would also catch it there, which would leave the `gh[pousr]_`
#    prefix rule unpinned (a mutant deleting it would survive).
GHTOKEN="ghp_$(python3 -c 'import secrets; print(secrets.token_hex(18))')"
assert_redacted "guilt-github-pat-ghp-not-in-log" \
    "echo $GHTOKEN | gh auth login --with-token" "$GHTOKEN"

# 3-bis. The OTHER FOUR members of the `gh[pousr]_` class. A mutant narrowing
#     that class to a bare `ghp_` SURVIVED the mutation run of 2026-08-22: only
#     `ghp_` had a case, so `gho_`/`ghu_`/`ghs_`/`ghr_` were carried by an
#     alternation nothing could fail on. One case for the class, not five: the
#     mutant that survived collapses the whole class, and any single non-`p`
#     member kills it.
GHOTOKEN="gho_$(python3 -c 'import secrets; print(secrets.token_hex(18))')"
assert_redacted "guilt-github-oauth-app-token-gho-not-in-log" \
    "echo $GHOTOKEN | gh auth login --with-token" "$GHOTOKEN"

# 3a. The fine-grained PAT prefix (github_pat_) — a SEPARATE rule, because
#     `gh[pousr]_` cannot match it (`gh` followed by `i`). It had no guilt case
#     at all until 2026-08-22: the rule was unfalsifiable, so deleting it was a
#     silently surviving mutant.
GHPAT="github_pat_11ABCDEFG0$(python3 -c 'import secrets; print(secrets.token_hex(12))')"
assert_redacted "guilt-github-fine-grained-pat-not-in-log" \
    "echo $GHPAT | gh auth login --with-token" "$GHPAT"

# 3b. PREFIX off-by-one — the twin of case 2. v2 of the regex required at least
#     one char BEFORE the keyword, so it caught CLAUDE_CODE_OAUTH_TOKEN_1= and
#     MISSED a bare TOKEN=. Each credential word gets its own bare-segment case
#     (they are alternations of one shared list — an unpinned entry can be
#     deleted without any test failing), plus a lowercase and a --flag= form.
for _form in \
    'export TOKEN=barePrefixSecret001' \
    'export KEY=barePrefixSecret002' \
    'SECRET=barePrefixSecret003' \
    'export PASSWORD=barePrefixSecret004' \
    'export PASSWD=barePrefixSecret005' \
    'export CREDENTIAL=barePrefixSecret006' \
    'export my_token=lowercaseNameSecret007' \
    'curl --token=flagFormSecret008'
do
    assert_redacted "guilt-prefix-and-form-variant [${_form##* }]" \
        "$_form" "$(printf '%s' "$_form" | sed 's/.*=//')"
done

# 3c. Header form: a secret after a colon inside a quoted -H argument. Not a
#     shell assignment at all, which is why the assignment-only branch of an
#     earlier regex missed it.
assert_redacted "guilt-header-form-secret-not-in-log" \
    'curl -H "X-API-Key: headerFormSecret009" https://example.test' \
    "headerFormSecret009"

# 3d. THE GATE'S TWELVE LEAKING FORMS, verbatim. Every one of these was logged
#     COMPLETE AND UNREDACTED by the segment-only regex, because it demanded a
#     `_`/`-` delimiter these names do not have. This block is the regression
#     list; the loops after it are what PIN each alternation.
assert_redacted "guilt-gate-leak-form [APIKEY=]"    "export APIKEY=gateLeak001"    "gateLeak001"
assert_redacted "guilt-gate-leak-form [apikey=]"    "export apikey=gateLeak002"    "gateLeak002"
assert_redacted "guilt-gate-leak-form [apiKey=]"    "export apiKey=gateLeak003"    "gateLeak003"
assert_redacted "guilt-gate-leak-form [AUTHTOKEN=]" "export AUTHTOKEN=gateLeak004" "gateLeak004"
assert_redacted "guilt-gate-leak-form [SECRETKEY=]" "export SECRETKEY=gateLeak005" "gateLeak005"
assert_redacted "guilt-gate-leak-form [accesskey=]" "export accesskey=gateLeak006" "gateLeak006"
assert_redacted "guilt-gate-leak-form [mytoken=]"   "export mytoken=gateLeak007"   "gateLeak007"
assert_redacted "guilt-gate-leak-form [TOKENS=]"    "export TOKENS=gateLeak008"    "gateLeak008"
assert_redacted "guilt-gate-leak-form [--pass=]"    "mysql --pass=gateLeak009"     "gateLeak009"
assert_redacted "guilt-gate-leak-form [--auth=]"    "curl --auth=gateLeak010"      "gateLeak010"
assert_redacted "guilt-gate-leak-form [json api_key]" \
    'curl -d '"'"'{"api_key": "gateLeak011"}'"'"' https://example.test' "gateLeak011"
# The DSN below is a FIXTURE, not a credential. scripts/lint_pg_dsn_credentials.py judges a
# DSN password by SHAPE, not by role, and it is right to flag a real-looking one anywhere in
# the tree -- but this suite needs a real-looking one to prove rule 3 fires at all. The marker
# on the next line is that guard's deliberate author-assertion escape, and it must sit on the
# same line as the DSN or the line directly above it: synthetic-pg-password
_dsn_gate_leak="psql postgres://appuser:gateLeak012@db.example.test/mydb"
assert_redacted "guilt-gate-leak-form [url userinfo]" "$_dsn_gate_leak" "gateLeak012"

# 3d-bis. ONE CASE PER PREFIX-VOCABULARY ENTRY. The vocabulary now exists for
#     exactly one word — `KEY` — because `KEY` is the one credential word that
#     routinely ends an INNOCENT identifier (`monkey`, `pubkey`, `nkeys`,
#     `topkey`, `dictkeys`), so it cannot take an open prefix without re-opening
#     `monkey=patch`. Each entry therefore gets a `<prefix>key=` case: with a
#     `<prefix>token=` case instead, deleting any vocabulary entry would leave
#     the suite GREEN, because the wide-word branch would cover for it — that is
#     exactly what the mutation run found and this loop fixes.
_i=0
for _pre in api auth access app client private master root admin user session \
            refresh oauth bearer my id token secret password passwd credential
do
    _i=$((_i + 1))
    _val="vocabSecret$(printf '%03d' "$_i")"
    assert_redacted "guilt-vocabulary-prefix-with-KEY [${_pre}key=]" \
        "export ${_pre}key=${_val}" "$_val"
done

# 3e. ANY-PREFIX + WIDE WORD. The bounded vocabulary above cannot save a prefix
#     nobody thought to list: `PGPASSWORD=` — the standard Postgres password env
#     var — occurs 99 times in the live 333k-line log and the vocabulary-only
#     design leaked EVERY one of them. TOKEN/SECRET/PASSWORD/PASSWD/CREDENTIAL
#     therefore take ANY alphanumeric prefix; `KEY` deliberately does not.
#     `zzq`-prefixed so no vocabulary entry can cover for a deleted wide word.
assert_redacted "guilt-any-prefix-wide-word [PGPASSWORD=]" \
    "PGPASSWORD=pgRealWorldSecret001 psql -h db -c 'select 1'" "pgRealWorldSecret001"
_i=0
for _wide in token secret password passwd credential
do
    _i=$((_i + 1))
    _val="widePrefixSecret$(printf '%03d' "$_i")"
    assert_redacted "guilt-any-prefix-wide-word [zzq${_wide}=]" \
        "export zzq${_wide}=${_val}" "$_val"
done

# 3f. PLURAL — `TOKENS=` leaked in full under the segment-only regex. Pins the
#     optional `s` on both the segment and the compound branch.
assert_redacted "guilt-plural-segment [TOKENS=]" \
    "export TOKENS=pluralSecret001" "pluralSecret001"
assert_redacted "guilt-plural-compound [apikeys=]" \
    "export apikeys=pluralSecret002" "pluralSecret002"

# 3g. BARE GENERIC names. Over-redaction is the direction this hook explicitly
#     accepts (see the hook comment): `PWD=/tmp` is a real over-match this buys.
assert_redacted "guilt-bare-generic [--pass=]" \
    "mysql --pass=genericSecret001" "genericSecret001"
assert_redacted "guilt-bare-generic [--pwd=]" \
    "sqlcmd --pwd=genericSecret002" "genericSecret002"
assert_redacted "guilt-bare-generic [--auth=]" \
    "curl --auth=genericSecret003" "genericSecret003"

# 3h. JSON body: the name is QUOTED, so a quote sits between the name and the
#     `:` separator. Leaked in full until the optional quote was added.
assert_redacted "guilt-json-quoted-name [\"api_key\": \"<v>\"]" \
    'curl -d '"'"'{"api_key": "jsonSecret001"}'"'"' https://example.test' \
    "jsonSecret001"

# 3i. QUOTED VALUES. Until 2026-08-22 NO guilt case used one, so deleting the
#     quoted alternations `(?:"[^"]*"|\x27[^\x27]*\x27)` was a SURVIVING mutant
#     — and with them gone the value branch cannot match a quoted value at all
#     (the unquoted alternative excludes `"` and `\x27`), so these two commands
#     logged COMPLETE AND UNREDACTED. One case per quote style.
assert_redacted "guilt-double-quoted-value" \
    'export CLAUDE_CODE_OAUTH_TOKEN="dquotedSecret001"' "dquotedSecret001"
assert_redacted "guilt-single-quoted-value" \
    "export API_TOKEN='squotedSecret002'" "squotedSecret002"

# 3j. URL USERINFO — `scheme://user:<secret>@host`. No credential-ish NAME
#     anywhere, so only the dedicated rule can catch it. Uses a generic
#     password (no known prefix) so the prefix rules cannot cover for it.
# The DSN below is a FIXTURE, not a credential. scripts/lint_pg_dsn_credentials.py judges a
# DSN password by SHAPE, not by role, and it is right to flag a real-looking one anywhere in
# the tree -- but this suite needs a real-looking one to prove rule 3 fires at all. The marker
# on the next line is that guard's deliberate author-assertion escape, and it must sit on the
# same line as the DSN or the line directly above it: synthetic-pg-password
_dsn_userinfo="psql postgres://appuser:urlUserinfoSecret001@db.example.test/mydb"
assert_redacted "guilt-url-userinfo-password" "$_dsn_userinfo" "urlUserinfoSecret001"

# 3j-bis. A URL PASSWORD CONTAINING A COLON. The password class is `[^\s/@]+`,
#     which allows `:` on purpose — the split between user and password is the
#     FIRST colon, not the last. Narrowing it to `[^\s/@:]+` SURVIVED the
#     mutation run of 2026-08-22 and leaks the first half of such a password in
#     full, because no case had one.
assert_redacted "guilt-url-userinfo-password-containing-a-colon" \
    "psql 'redis://appuser:urlColonSecret001:more@db.example.test/x'" \
    "urlColonSecret001"

# 3k. REDACT-BEFORE-TRUNCATE ordering. Reordering the hook to
#     `sys.stdin.read()[:200]` used to be a SURVIVING mutant that leaked ~10
#     characters of cleartext, because no guilt case had a command longer than
#     the 200-char window. This one is 251 chars with a quoted secret starting
#     at char 190: truncate-first leaves chars 190..199 — the marker below — in
#     the log; redact-first leaves none of it.
_pad="$(python3 -c 'print("x"*167)')"
_straddle="ZZSTRADDLE$(python3 -c 'import secrets; print(secrets.token_hex(25))')"
assert_redacted "guilt-secret-straddling-the-200-char-truncation-boundary" \
    "echo ${_pad} && export TOKEN=\"${_straddle}\"" "ZZSTRADDLE"

# 4. Bearer/Authorization — carries no keyword in a variable NAME at all, so
#    the assignment-shaped rule above cannot see it. Only the dedicated
#    Bearer/Authorization rule catches this.
assert_redacted "guilt-bearer-token-not-in-log" \
    'curl -H "Authorization: Bearer abcdefgh12345678" https://x' \
    "abcdefgh12345678"

# 4a. THE ORDERING LEAK (Gear-3 gate, round 4). Rule 2 running BEFORE rule 4
#     did not merely fail to help — it made the output LESS SAFE than no match
#     at all. A credential-ish NAME whose UNQUOTED value begins with the word
#     `Bearer` made rule 2 replace exactly that word, destroying the only
#     marker rule 4 had, so rule 4 could no longer fire and the token was
#     logged in full. All three shapes were driven through the real hook and
#     all three leaked. The control above (`Authorization: Bearer`) stayed safe
#     throughout, because `Authorization` is not a NAME rule 2 matches — which
#     is exactly why this hid behind a green suite. Moving rule 4 above rule 2
#     is the fix; putting it back below fails these three.
assert_redacted "guilt-order-rule2-must-not-disarm-rule4 [header X-Auth]" \
    "curl -H 'X-Auth: Bearer ordSecretAAA1111' https://x" "ordSecretAAA1111"
assert_redacted "guilt-order-rule2-must-not-disarm-rule4 [--auth=Bearer]" \
    "mytool --auth=Bearer ordSecretBBB2222" "ordSecretBBB2222"
assert_redacted "guilt-order-rule2-must-not-disarm-rule4 [lowercase auth: bearer]" \
    "svc auth: bearer ordSecretCCC3333" "ordSecretCCC3333"

# 4b. The OTHER ordering adjacency, in the opposite direction: rule 3 must run
#     BEFORE rule 4. Rule 4 consumes an 8+ char run, and a URL scheme name is
#     one — so with rule 4 first, `Bearer postgresql://u:<v>@h` becomes
#     `Bearer <REDACTED>://u:<v>@h`, which no longer matches rule 3's
#     `[a-zA-Z][a-zA-Z0-9+.-]*://` anchor, and the URL password leaks.
# The DSN below is a FIXTURE, not a credential. scripts/lint_pg_dsn_credentials.py judges a
# DSN password by SHAPE, not by role, and it is right to flag a real-looking one anywhere in
# the tree -- but this suite needs a real-looking one to prove rule 3 fires at all. The marker
# on the next line is that guard's deliberate author-assertion escape, and it must sit on the
# same line as the DSN or the line directly above it: synthetic-pg-password
_dsn_order="Bearer postgresql://appuser:ordSecretDDD4444@db.example.test/x"
assert_redacted "guilt-order-rule3-must-run-before-rule4 [scheme eaten by Bearer]" \
    "$_dsn_order" "ordSecretDDD4444"

# 4c. THE MIRROR of 4a/4b, and the reason rule order alone was NOT the fix.
#     Found by the Gear-3 gate ON the ordering fix itself: putting the
#     marker-anchored rules FIRST does not make them safe, it just moves the
#     destruction. Rule 4 eats an 8+ char [A-Za-z0-9._-] run after Bearer --
#     and a credential NAME is exactly such a run. So `Bearer refresh_token=<v>`
#     logged as `Bearer <REDACTED>=<v>`: the marker replaced the NAME, the value
#     survived in full, and the output READS as if redaction fired. Strictly
#     less safe than not matching at all -- the same property the reorder was
#     introduced to remove, mirrored. Rule 1 does it too, because a real token
#     prefix can itself be the start of a NAME.
#     The cure is not an order: EVERY marker-anchored rule now carries
#     ASSIGN_TAIL and swallows the assignment that follows its own marker.
#     One case per shape the gate demonstrated, including BOTH quote styles --
#     the gate's proposed regex used a bare `[^\s"']*` tail and would have left
#     the quoted forms leaking.
MIRROR_V="mirrorLeak$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
MIRROR_DQ='Bearer ACCESS_TOKEN="'"$MIRROR_V"'"'
MIRROR_SQ="Bearer client_secret='$MIRROR_V'"
assert_redacted "guilt-mirror-rule4-eats-name [bare]" \
    "curl -d 'Bearer refresh_token=$MIRROR_V' https://auth.test/token" "$MIRROR_V"
assert_redacted "guilt-mirror-rule4-eats-name [double-quoted value]" \
    "curl -H $MIRROR_DQ https://auth.test" "$MIRROR_V"
assert_redacted "guilt-mirror-rule4-eats-name [single-quoted value]" \
    "export H=$MIRROR_SQ" "$MIRROR_V"
assert_redacted "guilt-mirror-rule4-eats-name [dotted attribute name]" \
    "log 'Bearer cfg.api_key=$MIRROR_V'" "$MIRROR_V"
assert_redacted "guilt-mirror-rule4-eats-name [hyphenated header name]" \
    "log 'Bearer x-api-key=$MIRROR_V'" "$MIRROR_V"
assert_redacted "guilt-mirror-rule4-eats-name [colon separator, rule 2 cannot match this name]" \
    "log 'Bearer PASSWORDX: $MIRROR_V'" "$MIRROR_V"
assert_redacted "guilt-mirror-rule1-prefix-eats-name" \
    "echo ghp_MYTOKENS=$MIRROR_V" "$MIRROR_V"

# 4d. THE THIRD DIRECTION, found by the Gear-3 gate on the cure for 4c. The tail
#     that closed the mirror could itself CROSS a later rule's marker: its bare
#     branch runs to the next whitespace, so `github_pat_<8+>=bearer <v>` had
#     rule 1 -- which runs FIRST -- eat the word `bearer` as its own value,
#     leaving rule 4 nothing to anchor on and the token in the clear beside a
#     `<REDACTED>` that fired for something else. Same misleading shape, third
#     round, third layer down. A differential fuzz against the pre-tail version
#     found 258 such inputs.
#     The cure is TEMPERED_VALUE: the bare branch may not cross a position where
#     any later marker STARTS. These cases pin it -- each has a value that
#     CONTAINS a later rule's marker rather than merely following one, which is
#     the shape none of 4c's cases had.
THIRD_V="thirdDir$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_redacted "guilt-third-rule1-tail-eats-rule4-marker [github_pat]" \
    "github_pat_CCCCCCCC=bearer $THIRD_V" "$THIRD_V"
assert_redacted "guilt-third-rule1-tail-eats-rule4-marker [ghp colon]" \
    "ghp_BBBBBBBB: Bearer $THIRD_V" "$THIRD_V"
assert_redacted "guilt-third-rule1-tail-eats-rule4-marker [sk-ant]" \
    "sk-ant-AAAAAAAA=bearer $THIRD_V" "$THIRD_V"
assert_redacted "guilt-third-rule4-tail-eats-its-own-next-marker" \
    "Bearer AAAAAAAAAA: Bearer $THIRD_V" "$THIRD_V"
assert_redacted "guilt-third-marker-inside-the-value-not-at-its-start" \
    "ghp_BBBBBBBB:x/Bearer $THIRD_V" "$THIRD_V"
assert_redacted "guilt-third-shaped-command-not-fuzz-noise" \
    "curl -H 'X-Pat: github_pat_CCCCCCCC:bearer $THIRD_V'" "$THIRD_V"
assert_redacted "guilt-third-greedy-prefix-kills-two-markers-in-one-bite" \
    "ghp_BBBBBBBBhttps://u:xx:Bearer $THIRD_V" "$THIRD_V"

# 4e. THE FOURTH DIRECTION, found by the gate on the cure for 4d. MARKER guarded
#     the anchors of rules 1, 3 and 4 -- and omitted rule 2's NAME, the anchor of
#     the rule that does the most work. So the tempered tail could still cross
#     `TOKEN:` / `PASSWORD=` / `API_KEY =` and swallow the anchor whose value it
#     then left behind: `github_pat_<8+>:TOKEN: <v>` logged as
#     `github_pat_<REDACTED> <v>`. The shape needs a separator followed by
#     WHITESPACE -- the bare run stops at the space, so it consumes
#     prefix + sep + NAME + sep and drops the value outside its own match.
#     Cured by making MARKER mean what its own comment always said: EVERY anchor
#     a later rule needs, rule 2's NAME included.
#     WHY THE FUZZ MISSED IT, which is the more useful lesson: the class needs at
#     least four fragments (prefix, separator, NAME, separator-with-space,
#     secret), so a generator whose deterministic core emits three-fragment
#     triples STRUCTURALLY cannot produce it, and the rest rode on a single
#     random seed. A fuzz score is a statement about the GENERATOR, exactly as a
#     mutation score is a statement about the corpus.
FOURTH_V="fourthDir$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_redacted "guilt-fourth-tail-eats-rule2-NAME [github_pat + TOKEN:]" \
    "github_pat_CCCCCCCC:TOKEN: $FOURTH_V" "$FOURTH_V"
assert_redacted "guilt-fourth-tail-eats-rule2-NAME [ghp + PASSWORD:]" \
    "ghp_BBBBBBBB=PASSWORD: $FOURTH_V" "$FOURTH_V"
assert_redacted "guilt-fourth-tail-eats-rule2-NAME [sk-ant + spaced separator]" \
    "sk-ant-AAAAAAAA:API_KEY = $FOURTH_V" "$FOURTH_V"
assert_redacted "guilt-fourth-tail-eats-rule2-NAME [rule 4 tail]" \
    "Bearer AAAAAAAAAA:TOKEN: $FOURTH_V" "$FOURTH_V"
assert_redacted "guilt-fourth-tail-eats-rule2-NAME [shaped command]" \
    "deploy --pat=ghp_BBBBBBBB:PASSWORD: $FOURTH_V" "$FOURTH_V"

# 4f. THE FIFTH DIRECTION, found by the gate on the cure for 4e -- and the one
#     that ended the cascade architecture instead of extending it. TEMPERED_VALUE
#     tempered only its BARE branch; a comment asserted the two QUOTED branches
#     needed no tempering because they consume a COMPLETE delimited value, so
#     "whatever marker they swallow they also redact". That reasoning was wrong
#     in one specific way: the marker is swallowed INSIDE the quotes, and the
#     value it introduces sits BEHIND the closing quote, untouched. It reproduced
#     on all four marker rules at once, single- and double-quoted alike:
#         ghp_<8+>="junk TOKEN=" <secret>  ->  gh_<REDACTED> <secret>
#     Five directions of one defect was the signal that the defect was the
#     ARCHITECTURE: a consume-and-rewrite cascade in which any rule can blind a
#     later one, patched by a tempering list that must enumerate every anchor.
#     The cure is structural (see the hook comment): every anchor is searched
#     against the ORIGINAL string, nothing is consumed, and the cut runs from the
#     EARLIEST anchor to end-of-string. These five cases are kept as the
#     regression witness for the direction that forced it.
FIFTH_V="fifthDir$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_redacted "guilt-fifth-quoted-tail-strands-value [ghp + double quotes]" \
    "ghp_BBBBBBBB=\"junk TOKEN=\" $FIFTH_V" "$FIFTH_V"
assert_redacted "guilt-fifth-quoted-tail-strands-value [ghp + single quotes]" \
    "ghp_BBBBBBBB='junk TOKEN=' $FIFTH_V" "$FIFTH_V"
assert_redacted "guilt-fifth-quoted-tail-strands-value [sk-ant + PASSWORD]" \
    "sk-ant-AAAAAAAA=\"x PASSWORD=\" $FIFTH_V" "$FIFTH_V"
assert_redacted "guilt-fifth-quoted-tail-strands-value [github_pat + API_KEY]" \
    "github_pat_CCCCCCCC=\"x API_KEY=\" $FIFTH_V" "$FIFTH_V"
assert_redacted "guilt-fifth-quoted-tail-strands-value [rule 4 tail]" \
    "Bearer AAAAAAAAAA=\"x AUTH_TOKEN=\" $FIFTH_V" "$FIFTH_V"

# 4g. THE BACKSLASH-ESCAPED QUOTE, found by the same gate as 4f and DEFERRED at
#     the time as its own class: VALUE quoted branches are [^"]* / [^\x27]*,
#     which stop at an escaped quote instead of stepping over it, so
#     TOKEN="abc\" <secret>" logged the secret beside a <REDACTED> that had
#     fired for its NAME. It needed no separate cure in the end. Under the
#     earliest-anchor cut, VALUE no longer has to find where a value ENDS -- it
#     only has to prove an assignment BEGINS -- so where its quoted branch stops
#     stopped mattering. Kept as cases because "cured as a side effect" is a
#     claim about behaviour and behaviour is what regresses.
ESCQ_V="escQuote$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_redacted "guilt-backslash-escaped-quote [double, TOKEN]" \
    "TOKEN=\"abc\\\" $ESCQ_V\"" "$ESCQ_V"
assert_redacted "guilt-backslash-escaped-quote [single, PASSWORD]" \
    "PASSWORD='abc\\' $ESCQ_V'" "$ESCQ_V"
assert_redacted "guilt-backslash-escaped-quote [double, API_KEY, trailing text]" \
    "API_KEY=\"x\\\" $ESCQ_V y\"" "$ESCQ_V"
assert_redacted "guilt-backslash-escaped-quote [prefix rule tail]" \
    "ghp_BBBBBBBB=\"a\\\" TOKEN=\" $ESCQ_V" "$ESCQ_V"

# 4h. ANCHOR RECALL, not tail containment — a DIFFERENT disease from 4a-4f and the
#     one case the earliest-anchor cut could not fix on its own. A JSON body written
#     inside a double-quoted shell arg reaches the hook as {\"api_key\": <v>}: the
#     separator is preceded by a BACKSLASH-escaped quote, the NAME+separator anchor
#     therefore never matches, and NOTHING fires — the line was logged unchanged,
#     byte for byte. 4a-4f all leaked a value BEHIND a recognised anchor; a cut that
#     runs to end-of-string is no defence where nothing anchors at all. Cured by
#     allowing an optional backslash before the separator quote. The lesson is worth
#     more than the regex: soundness of the CUT and recall of the ANCHOR are separate
#     obligations, and proving the first says nothing about the second.
JSONQ_V="jsonQuote$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_redacted "guilt-anchor-recall-json-in-double-quoted-arg [api_key]" \
    "curl -d \"{\\\"api_key\\\": \\\"$JSONQ_V\\\"}\"" "$JSONQ_V"
assert_redacted "guilt-anchor-recall-json-in-double-quoted-arg [access_token]" \
    "curl -d \"{\\\"access_token\\\": \\\"$JSONQ_V\\\"}\"" "$JSONQ_V"
assert_redacted "guilt-anchor-recall-escaped-separator-no-quote" \
    "run api_key\\:$JSONQ_V" "$JSONQ_V"

# 4i. ESCAPING DEPTH. The 4h cure allowed exactly ONE backslash before the
#     separator quote. A refuter on a fresh context broke it within the hour by
#     adding a nesting level: a remote dispatch nests its quoting, so
#     ssh host "bash -c \"curl -d ...\"" reaches this hook with TWO or THREE
#     literal backslashes and nothing anchors again. The point-patch had
#     reproduced the exact enumeration trap the redesign renounced -- one more
#     special case bolted onto the anchor. Cured by quantifying the depth (\\*)
#     instead of enumerating it. These cases exist so the NEXT depth cannot
#     regress silently.
DEPTH_V="depthEsc$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_redacted "guilt-escaping-depth [two backslashes]" \
    "curl -d \"{\\\\\"api_key\\\\\": \\\\\"$DEPTH_V\\\\\"}\"" "$DEPTH_V"
assert_redacted "guilt-escaping-depth [three backslashes]" \
    "curl -d \"{\\\\\\\"api_key\\\\\\\": \\\\\\\"$DEPTH_V\\\\\\\"}\"" "$DEPTH_V"

# 4j. PEM PRIVATE KEY, which anchored on NOTHING: PRE?KEY needs KEY glued to its
#     prefix and "PRIVATE KEY" has a SPACE, so the single most unambiguous
#     credential shape in existence was invisible to every rule, before and after
#     the redesign. Found by a refuter, not by the corpus -- worth recording as a
#     property of the CORPUS: 105 cases had been built by attacking the regex that
#     existed, so they could only ever find shapes that regex nearly caught.
PEM_V="pemBody$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_redacted "guilt-pem-private-key [RSA]" \
    "printf -- '-----BEGIN RSA PRIVATE KEY-----\\nMIIEow$PEM_V\\n-----END RSA PRIVATE KEY-----'" "$PEM_V"
assert_redacted "guilt-pem-private-key [no algorithm]" \
    "printf -- '-----BEGIN PRIVATE KEY-----\\nMIIEow$PEM_V'" "$PEM_V"
assert_redacted "guilt-pem-private-key [EC]" \
    "printf -- '-----BEGIN EC PRIVATE KEY-----\\nMHc$PEM_V'" "$PEM_V"

# 4k. THE URL SCHEME BOUND, pinned by the LONGEST real schemes rather than by a
#     round number. The userinfo anchor was unbounded ([a-zA-Z][a-zA-Z0-9+.-]*),
#     which retries from every position of a long alphanumeric run and rescans to
#     the end: on a 50KB command carrying NO credential at all -- a big
#     git commit -m, a heredoc -- that one anchor cost 2278 ms against 2.53 ms
#     bounded, in a hook that runs on EVERY tool call. Bounded to sixteen, the
#     figure the old MARKER comment had already argued for and that the rule
#     itself never carried. These cases exist so a future tightening cannot
#     silently drop a scheme that is actually used: mongodb+srv is 11 characters
#     and is the longest one here.
SCHEME_V="urlScheme$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_redacted "guilt-url-userinfo-scheme-length [postgresql, 10]" \
    "psql postgresql://u:$SCHEME_V@h/db" "$SCHEME_V"
assert_redacted "guilt-url-userinfo-scheme-length [mongodb+srv, 11]" \
    "mongo mongodb+srv://u:$SCHEME_V@c.net" "$SCHEME_V"
assert_redacted "guilt-url-userinfo-scheme-length [redis, 5]" \
    "redis-cli -u redis://u:$SCHEME_V@h" "$SCHEME_V"

# 4l. THE SCHEME BOUND WAS ITSELF A COVERAGE REGRESSION, and this is the case
#     that proves the rule no longer has a boundary to fall off. Bounding the
#     scheme to sixteen characters (4k) fixed a 2462 ms scan and silently stopped
#     anchoring a SEVENTEEN-character scheme: a17chars://u:<secret>@h leaked where
#     the unbounded rule had redacted it. Found by a CROSS-FAMILY seat on a
#     differential old-vs-new hunt, after two fuzzers written by this design's
#     author -- a fragment product and a 300,000-input character-level run -- had
#     both reported zero regressions. Neither could reach a well-formed userinfo
#     URL carrying an over-long scheme; that is what "a fuzz score is a statement
#     about the GENERATOR" costs when the generator and the design share an
#     author. Cured by anchoring on the literal :// with no scheme pattern at all,
#     which no length can escape and which is FASTER than the bound (0.52 ms).
LONGSCHEME_V="longScheme$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_redacted "guilt-url-userinfo-any-scheme-length [17, the old boundary+1]" \
    "run a0123456789012345://u:$LONGSCHEME_V@h" "$LONGSCHEME_V"
assert_redacted "guilt-url-userinfo-any-scheme-length [40]" \
    "run aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa://u:$LONGSCHEME_V@h" "$LONGSCHEME_V"

# 4m. A URL PASSWORD MAY CONTAIN A SLASH, and forbidding one meant the whole
#     credential anchored on nothing: postgres://u:pa/ss@h leaked in full, on the
#     old design as well as the new. A cross-family seat surfaced it in a
#     contrived form -- the old cascade consumed a token containing the slash,
#     which conjured a userinfo URL that had not been in the input, so the old
#     redacted where the new did not -- and the plain form is the same gap
#     without the theatre. Only the PASSWORD class was loosened; the USER class
#     still forbids the slash, which is what keeps https://host/a:b@c innocent
#     (the user run stops at the slash before it can reach a colon).
URLSLASH_V="urlSlash$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_redacted "guilt-url-userinfo-password-with-slash" \
    "psql postgres://u:pa/$URLSLASH_V@h" "$URLSLASH_V"
assert_redacted "guilt-url-userinfo-password-with-slash [cascade-conjured form]" \
    "run a://u:${URLSLASH_V}ghp_12345678=\"/\"@h" "$URLSLASH_V"
# The value is GENERATED, not written, and that is a lint requirement rather
# than a style choice: a literal all-digit password inside a literal
# postgres:// DSN is indistinguishable from a real credential to
# scripts/lint_pg_dsn_credentials.py, which failed this file on exactly this
# line. The same fragment discipline that linter applies to its own fixtures
# applies here. Only the SHAPE is load-bearing (all digits, immediately before
# the @), never the digits themselves.
ALLDIGIT_V="$(python3 -c 'import secrets; print("".join(secrets.choice("0123456789") for _ in range(10)))')"
assert_redacted "guilt-url-userinfo-all-digit-password-still-anchors" \
    "psql postgres://u:$ALLDIGIT_V@h" "$ALLDIGIT_V"
assert_redacted "guilt-url-userinfo-password-starting-with-digits-and-a-query-char" \
    "curl 'https://alice:123?x$URLSLASH_V@db.test/query'" "$URLSLASH_V"
assert_redacted "guilt-slack-token-in-a-bare-authorization-header" \
    "curl -H 'Authorization: xoxb-123456789012-$URLSLASH_V' https://api.example.test" "$URLSLASH_V"
assert_redacted "guilt-pem-private-key [PGP block delimiter]" \
    "printf -- '-----BEGIN PGP PRIVATE KEY BLOCK-----\\n$URLSLASH_V'" "$URLSLASH_V"
assert_redacted "guilt-pem-private-key [OPENSSH]" \
    "printf -- '-----BEGIN OPENSSH PRIVATE KEY-----\\n$URLSLASH_V'" "$URLSLASH_V"

# 4n. Authorization: Basic <base64>. Rule 4 only ever covered Bearer, and this was
#     a NAMED residual risk rather than an oversight -- which is precisely why it
#     is worth promoting: a named hole that nothing executes is indistinguishable
#     from an unknown one. A wholly ordinary `curl -H "Authorization: Basic ..."`
#     passed through untouched. The 16-character floor and the base64 alphabet are
#     what keep the ordinary English word innocent.
BASIC_V="QmFzaWNBdXRo$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_redacted "guilt-authorization-basic-base64" \
    "curl -H 'Authorization: Basic $BASIC_V' https://example.invalid/ping" "$BASIC_V"
assert_redacted "guilt-authorization-basic-base64 [proxy variant]" \
    "curl -H 'Proxy-Authorization: Basic $BASIC_V' https://example.invalid/ping" "$BASIC_V"
assert_redacted "guilt-bearer-standard-base64-alphabet" \
    "curl -H 'Authorization: Bearer ab+cd/ef=$BASIC_V' https://example.invalid/" "$BASIC_V"

# ───────────────────────────────────────────────────────── INNOCENCE ──

# An ordinary command must survive INTACT — no redaction marker anywhere near
# it. This is the guard-over-match twin (cicatrix #3): a redactor broad enough
# to catch every guilt case above must not also eat innocent command text.

assert_intact() {  # assert_intact <label> <command> <expected substring>
    local label="$1" cmd="$2" needle="$3" tmp line ok
    tmp="$(mktemp -d)"; cleanup_dirs+=("$tmp")
    run_hook "$tmp" "Bash" "$cmd"
    line="$(log_line "$tmp")"
    ok=1
    if printf '%s' "$line" | grep -qF -- "$needle" \
        && ! printf '%s' "$line" | grep -q "REDACTED"; then
        ok=0
    fi
    case_result "$label" "$ok" innocence
}

# The eight measured v1 casualties: v1 matched the keyword as a bare substring
# and mangled these ordinary commands.
assert_intact "innocence-monkey-patch-key-substring-prefix-not-in-vocabulary" \
    'gh pr create --title "monkey=patch"' 'monkey=patch'
assert_intact "innocence-keyfile-flag-key-not-delimited-on-right" \
    'openssl x509 --keyfile=/etc/x.pem' 'openssl x509 --keyfile=/etc/x.pem'
assert_intact "innocence-jq-dot-key-single-segment-attribute" \
    "jq '.key = 1' data.json" "jq '.key = 1' data.json"
assert_intact "innocence-stricthostkeychecking-camelcase-no-delimiter" \
    'ssh -o StrictHostKeyChecking=no pro' 'ssh -o StrictHostKeyChecking=no pro'
assert_intact "innocence-sed-keyword-key-not-delimited-on-right" \
    'sed -i "s/keyword=old/keyword=new/" f.txt' 's/keyword=old/keyword=new/'
assert_intact "innocence-keyspace-env-name-key-not-delimited-on-right" \
    'docker run -e KEYSPACE=prod myimg' 'docker run -e KEYSPACE=prod myimg'
assert_intact "innocence-publickeypath-camelcase-no-delimiter" \
    'npm run build -- --publicKeyPath=./pub.pem' 'npm run build -- --publicKeyPath=./pub.pem'
assert_intact "innocence-redis-keys-command-name-no-assignment" \
    "redis-cli KEYS '*'" "redis-cli KEYS '*'"

# NON-KEY keyword substrings. Added 2026-08-22: this corpus was described as
# spanning "TOKEN/KEY/SECRET/etc substrings" while every occurrence in it was
# `key`. These three carry PASSWORD, TOKEN and SECRET substrings instead.
assert_intact "innocence-password-authentication-camelcase-no-delimiter" \
    'ssh -o PasswordAuthentication=no pro' 'ssh -o PasswordAuthentication=no pro'
assert_intact "innocence-tokenizer-token-not-delimited-on-right" \
    'make TOKENIZER=fast build' 'make TOKENIZER=fast build'
assert_intact "innocence-secret-scanning-test-selector" \
    "pytest -k 'secret_scanning' --maxfail=1" "pytest -k 'secret_scanning' --maxfail=1"

# RULE 3 and RULE 4 innocence. Added 2026-08-22: until then neither rule had a
# single innocence case — no case in the corpus contained `Bearer` or `://` at
# all — so every over-match and boundary mutant in them survived a green suite.
# One case per boundary, each verified to be a real over-match when the boundary
# is removed.

# Rule 3, USERINFO BOUNDARY. The user segment is `[^\s:/@]+` — it may not span
# a `/` or a `:`. Widen it to `[^\s@]+` and this ordinary query string, whose
# `role:email@host` value has nothing to do with a URL password, gets its
# `admin` redacted.
assert_intact "innocence-url-query-string-role-and-email-not-userinfo" \
    "curl 'https://api.test/send?to=ops:admin@example.test'" \
    "to=ops:admin@example.test"

# Rule 4, WORD BOUNDARY. `\bBearer` must not match inside a longer word.
# `flagbearer`, `pallbearer`, `torchbearer` are ordinary English; drop the `\b`
# and the next 8+ char run after one of them is eaten.
assert_intact "innocence-flagbearer-word-boundary-not-a-bearer-header" \
    'git commit -m "flagbearer handoff20260822 done"' \
    "flagbearer handoff20260822 done"

# Rule 4, LENGTH FLOOR. `{8,}` is what keeps short prose after the word
# `Bearer` intact; relax it to `{1,}` and this PR title loses its `v2`.
# Innocence for the two anchors added on 2026-08-22, because a guard added
# without an innocence case is exactly the pattern this corpus exists to refuse
# (cicatrix #3). The English word "Basic" is common in commit messages and help
# text; a URL with a path is common in every command that touches a repo.
assert_intact "innocence-basic-long-english-word-past-the-length-floor" \
    "printf '%s' 'Basic telecommunications'" "Basic telecommunications"
assert_intact "innocence-basic-long-english-phrase" \
    "printf '%s' 'Basic understanding of internationalization'" "internationalization"
assert_intact "innocence-basic-the-ordinary-english-word" \
    'git commit -m "Basic auth support for the gateway"' "Basic auth support"
assert_intact "innocence-basic-below-the-base64-length-floor" \
    'echo "Basic ZGVtbw=="' "Basic ZGVtbw"
assert_intact "innocence-basic-long-word-in-a-real-header-no-digit" \
    "printf '%s' 'Authorization: Basic documentationonly'" "documentationonly"
assert_intact "innocence-basic-long-word-in-a-real-header-multiple-of-four" \
    "printf '%s' 'Authorization: Basic internationalization'" "internationalization"
assert_intact "innocence-url-host-port-path-with-at-sign [registry digest]" \
    "curl 'https://reg.test:5000/v2/img@sha256'" "reg.test:5000"
assert_intact "innocence-url-host-port-path-with-at-sign [release path]" \
    "curl 'https://example.test:8443/releases/app@2'" "releases/app@2"
assert_intact "innocence-pem-certificate-is-public-not-a-key" \
    "printf -- '-----BEGIN CERTIFICATE-----'" "BEGIN CERTIFICATE"
assert_intact "innocence-pem-public-key-block" \
    "printf -- '-----BEGIN PGP PUBLIC KEY BLOCK-----'" "PUBLIC KEY BLOCK"
assert_intact "innocence-url-path-colon-at-not-userinfo" \
    'curl "https://cdn.test/a/b:c@d/e"' "cdn.test"
assert_intact "innocence-bearer-followed-by-short-token-length-floor" \
    'gh pr create --title "Bearer v2 rollout"' \
    "Bearer v2 rollout"

assert_intact "innocence-ordinary-command-intact-no-redacted-marker" \
    "gh pr create --title fix --body ok" "gh pr create --title fix --body ok"

# ──────────────────────────────────────────────────────────────── MODE ──

# A freshly created log must be born 0600 (umask 077), never 0644.
tmp5="$(mktemp -d)"; cleanup_dirs+=("$tmp5")
run_hook "$tmp5" "Bash" "echo fresh"
mode="$(file_mode "$tmp5/logs/codex-spalla-trigger.jsonl")"
ok=1
[ "$mode" = "600" ] && ok=0
case_result "mode-fresh-log-is-0600-not-0644 (got: ${mode:-<unreadable>})" "$ok" mode

# A PRE-EXISTING log at the old 0644 must be repaired to 0600. This is the
# case the explicit `chmod 0600 "$LOG_FILE"` line exists for, and the ONLY one
# that can fail if it is deleted: `umask 077` governs CREATION only, and `>>`
# never changes an existing file's mode — so with only the fresh-log case
# above, deleting that chmod was a SURVIVING mutant that left every
# already-exposed log (including the real 83 MB one) world-readable forever.
tmp6="$(mktemp -d)"; cleanup_dirs+=("$tmp6")
mkdir -p "$tmp6/logs"
: > "$tmp6/logs/codex-spalla-trigger.jsonl"
chmod 0644 "$tmp6/logs/codex-spalla-trigger.jsonl"
premode="$(file_mode "$tmp6/logs/codex-spalla-trigger.jsonl")"
run_hook "$tmp6" "Bash" "echo preexisting"
mode6="$(file_mode "$tmp6/logs/codex-spalla-trigger.jsonl")"
ok=1
[ "$premode" = "644" ] && [ "$mode6" = "600" ] && ok=0
case_result "mode-preexisting-0644-log-repaired-to-0600 (before: ${premode:-?}, after: ${mode6:-<unreadable>})" "$ok" mode

# ── PATH THAT STARTS WITH AN AT-SIGN ────────────────────────────────────────
#
# Found by a PEER SESSION, not by this corpus: it drove 197 invented inputs and
# reported 87 false positives, of which this was the one that falsified a claim
# rather than merely widening a declared class. The pack used to assert rule 3
# "cannot fire on a genuine host:port, which has no @ after it (verified)". The
# verification was VACUOUS -- both examples it cited had no at-sign after the
# port at all, so neither could test the claim they were offered as proof of.
# A self-hosted Mastodon-style API on a non-default port has exactly the shape
# the claim ruled out, and it was truncated in full, taking the SCHEME with it.
#
# The guilt case below rides along on purpose: it is the shape that made the
# obvious cure (reject any digits-then-slash) the WRONG one -- a real password
# that begins with digits and contains a slash. Both pins are needed, or the
# next session tightens this rule back into the leak.
ATPATH_V="atPath$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_intact "innocence-url-port-then-path-starting-with-at [mastodon-style]" \
    'curl "https://staging.example.test:8443/@mentions/feed"' \
    "staging.example.test:8443/@mentions/feed"
assert_intact "innocence-url-port-then-path-starting-with-at [user handle]" \
    'curl "https://social.example.test:9443/@alice/posts/123"' \
    "social.example.test:9443/@alice/posts/123"
assert_redacted "guilt-url-password-starting-with-digits-and-containing-a-slash" \
    "psql postgres://u:123/$ATPATH_V@h" "$ATPATH_V"

# ── NUMERIC SUFFIX ON THE CREDENTIAL NAME ───────────────────────────────────
#
# Found by an independent gate that drove 383 inputs through the real hook, not
# by this corpus: TOKEN_2= was caught and TOKEN2= was not, because a suffix could
# only arrive as a _- or --delimited segment. That split the commonest real names
# in half. PGPASSWORD is not hypothetical -- this repo already measured the
# undelimited form leaking 99 times in its own live log.
#
# The pins below run in BOTH directions on purpose, because the fix is a
# widening and a widening is only safe if its narrowness is asserted too. TAIL
# admits digits and NOT bare letters: a bare alphanumeric suffix would swallow
# TOKENIZER=fast. Branch (c) gets only the numeric half, never the delimited one:
# the full TAIL was measured admitting AUTH_MODE=, AUTH_URL=, PWD_FILE= and
# PASS_THROUGH=, four ordinary config idioms that the generic branch -- unlike
# (a) and (b) -- has no credential WORD to tell apart from a real name.
SUF_V="sufTest$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
assert_redacted "guilt-numeric-suffix-wide-word [TOKEN1]" \
    "export TOKEN1=$SUF_V" "$SUF_V"
assert_redacted "guilt-numeric-suffix-wide-word [SECRET3]" \
    "export SECRET3=$SUF_V" "$SUF_V"
assert_redacted "guilt-numeric-suffix-wide-word [PGPASSWORD1, the live-log shape]" \
    "PGPASSWORD1=$SUF_V psql -h db.internal" "$SUF_V"
assert_redacted "guilt-numeric-suffix-after-the-plural-S [TOKENS1]" \
    "export TOKENS1=$SUF_V" "$SUF_V"
assert_redacted "guilt-numeric-suffix-key-branch [APIKEY2]" \
    "export APIKEY2=$SUF_V" "$SUF_V"
assert_redacted "guilt-numeric-suffix-in-a-header [X-Auth-Token2]" \
    "curl -H \"X-Auth-Token2: $SUF_V\" https://api.example.test" "$SUF_V"
assert_redacted "guilt-numeric-suffix-generic-branch [AUTH1]" \
    "export AUTH1=$SUF_V" "$SUF_V"
assert_redacted "guilt-numeric-suffix-generic-branch [PWD9]" \
    "export PWD9=$SUF_V" "$SUF_V"
assert_intact "innocence-letter-suffix-is-not-a-numeric-one [TOKENIZER]" \
    "export TOKENIZER=fast" "TOKENIZER=fast"
assert_intact "innocence-generic-branch-rejects-the-delimited-tail [AUTH_MODE]" \
    "export AUTH_MODE=oidc" "AUTH_MODE=oidc"
assert_intact "innocence-generic-branch-rejects-the-delimited-tail [AUTH_URL]" \
    "export AUTH_URL=https://idp.example.test" "AUTH_URL=https://idp.example.test"
assert_intact "innocence-generic-branch-rejects-the-delimited-tail [PASS_THROUGH]" \
    "export PASS_THROUGH=true" "PASS_THROUGH=true"
assert_intact "innocence-generic-branch-rejects-the-delimited-tail [PWD_FILE]" \
    "export PWD_FILE=/etc/app/pwd" "PWD_FILE=/etc/app/pwd"
assert_intact "innocence-generic-word-with-a-bare-letter-suffix [AUTHOR]" \
    "AUTHOR=alice git commit --amend --no-edit" "AUTHOR=alice"

# ── WALL CLOCK ──────────────────────────────────────────────────────────────
#
# This exists because the SAME defect shipped TWICE, four commits apart, in two
# different rules: an unbounded character class in front of a literal makes the
# regex engine retry from every position of a long run. The URL scheme cost
# 2462 ms; the [A-Za-z-]* admitting Proxy-Authorization cost EIGHTEEN SECONDS on
# a 50KB command containing no credential at all -- and 346 SECONDS at 200KB --
# in a hook that fires on every PostToolUse event. A comment saying "do not do
# this" was already in the file when the second one landed, written by the same
# session that then wrote the second one. So the rule is executable now.
#
# The budget is deliberately loose (10s for a 200KB input, against ~0.1s
# measured): it is a CATASTROPHE detector, not a benchmark. A pattern that
# regresses this way does not get 3x slower, it gets four orders of magnitude
# slower, so a loose budget catches the real thing without going red on a
# loaded CI runner. Wall clock in CI is noisy; a tight budget here would be a
# flaky test, and a flaky guard gets disabled, which is how guards die.
tmp7="$(mktemp -d)"; cleanup_dirs+=("$tmp7")
big_cmd="git commit -m $(python3 -c 'print("a"*200000)')"
t_start=$(python3 -c 'import time; print(time.time())')
run_hook "$tmp7" "Bash" "$big_cmd"
t_end=$(python3 -c 'import time; print(time.time())')
elapsed=$(python3 -c "import sys; print(round(float(sys.argv[2])-float(sys.argv[1]),2))" "$t_start" "$t_end")
ok=1
python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) < 10.0 else 1)" "$elapsed" && ok=0
case_result "wallclock-200kb-no-credential-under-10s (took ${elapsed}s)" "$ok" mode

# The 200KB payload above is a single run of one letter, and it exercises almost
# nothing: it anchors on no rule and every class rejects it on the first
# character. The URL userinfo rule was QUADRATIC underneath it and this suite was
# blind to that for exactly that reason -- a credential-free 200KB run of "a"
# costs milliseconds while ("://u" + 30 chars) repeated, no @ anywhere, cost
# 5545 ms at 200KB and 23015 ms at 400KB, i.e. past the budget on the line above.
# That shape is not exotic: it is a minified JSON config or a lockfile line. So
# the catastrophe detector gets a second payload whose shape actually reaches the
# rule that failed, and the lesson is general -- a perf guard only guards the code
# path its payload happens to walk.
#
# IT IS 400KB, NOT 200KB, AND THAT IS NOT ARBITRARY. The unbounded rule cost
# 5545 ms at 200KB -- UNDER this budget. A 200KB version of this case passes on
# the very hook it was written to catch, which would have made it a guard that
# tests nothing while reading as coverage. The size was chosen by RUNNING the
# case against the pre-fix hook until it failed, not by picking a round number:
# 400KB costs 23015 ms unbounded and ~0.8s bounded, so it bites on the defect
# and keeps an order of magnitude of headroom against a loaded CI runner.
tmp8="$(mktemp -d)"; cleanup_dirs+=("$tmp8")
url_cmd="curl $(python3 -c 'print(("://u"+"A"*30)*11764, end="")')"
t_start=$(python3 -c 'import time; print(time.time())')
run_hook "$tmp8" "Bash" "$url_cmd"
t_end=$(python3 -c 'import time; print(time.time())')
elapsed=$(python3 -c "import sys; print(round(float(sys.argv[2])-float(sys.argv[1]),2))" "$t_start" "$t_end")
ok=1
python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) < 10.0 else 1)" "$elapsed" && ok=0
case_result "wallclock-400kb-url-run-no-at-under-10s (took ${elapsed}s)" "$ok" mode

# The bound that buys that linearity is 2048 characters per run, and a bound is
# only honest if something asserts where it sits. A 2048-character password must
# still redact; the documented residual above 2048 is deliberately NOT asserted
# here, so that a future rule which covers MORE does not fail this suite.
long_pw="$(python3 -c 'print("P"*2048, end="")')"
assert_redacted "userinfo-password-at-the-2048-bound" \
    "psql postgres://svc:${long_pw}@db.internal:5432/app" "$long_pw"

echo "---"
if [ "$fails" -eq 0 ]; then
    echo "PASS ($total cases: $guilt_n guilt, $innocence_n innocence, $mode_n mode)"
    exit 0
fi
echo "FAILED: $fails/$total"
exit 1
