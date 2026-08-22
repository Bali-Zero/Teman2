#!/usr/bin/env bash
# codex-spalla-trigger.sh — PostToolUse hook (telemetry-only, NO auto-spawn)
#
# Suggests `/codex-second-opinion` to the user when they touch high-risk paths,
# without actually dispatching Codex. Pure observability for week-1 learning.
#
# Configured via .claude/settings.json `hooks.PostToolUse`. The harness invokes
# this with a JSON event payload on stdin describing the tool call that just
# completed. We parse it, decide if the action is a strong spalla candidate,
# log to ~/logs/codex-spalla-trigger.jsonl, and emit a one-line stderr nudge.
#
# Hard rules (per docs/decisions/2026-05-03-codex-spalla-architecture.md):
#   - NEVER auto-spawn Codex. Suggestion only.
#   - Burn no quota. Stay cheap.
#   - Fail-open: any error or unexpected payload exits 0 silently.

set -u  # NOT -e: we want to fail open, not propagate errors.

# SECRET HYGIENE (added 2026-08-21 after a live leak; cicatrix superscar #4).
# This hook logs `tool_input.command` verbatim. A Bash tool call can carry a
# credential in argv, so this log is secret-bearing BY CONSTRUCTION -- and it
# was being created world-readable (0644) and never redacted.
#
# MAGNITUDE, stated as the STABLE conclusion rather than a count, because the
# counts here are NOT stable: 3 runs in the live log carry secret material --
# 1 whole token plus 2 truncation-clipped partials. Measured by END POSITION
# inside the 200-char logged field: the whole one ends at char 151, well short
# of the field; the other two end EXACTLY at char 200, the truncation boundary
# itself, which is what a value cut off mid-token looks like, not proof of two
# more complete secrets.
#
# The line counts this comment used to quote ("14 lines match the literal
# `sk-ant-oat`, 13 of them bare") were an INSTANT, not a fact. Re-measured on
# the same file at 2026-08-21T20:28Z: 24 matching lines, histogram 20x10,
# 5x13, 1x46, 1x87, 1x108 -- the bare-literal noise grew from 13 to 25 in four
# hours because THIS HOOK LOGS THE GREPS THAT MEASURE IT, so every measurement
# inflates the next one. The 3 secret-bearing runs did not move. Rule taken
# from that: anchor a volatile count to its measurement instant, or quote only
# the conclusion that survives the next measurement.
#
# CORRECTED 2026-08-21 by the Gear-3 gate, twice more, before the stale-count
# correction above: a first draft said "11 real values, 108 chars each" (a LINE
# count restated as a VALUE count, and the maximum restated as "each"); a later
# draft said "2 whole tokens" (a truncation artifact restated as two more
# complete secrets). The leak is real; the magnitude was inflated every time,
# in the very comment that preaches counting by run length.
#
# Two independent defenses, because either alone fails:
#   (1) umask 077 so the file can never be born readable by anyone else, plus
#       an explicit chmod for a file that already exists at the old mode --
#       `>>` does NOT change the mode of an existing file, so the umask alone
#       would leave every pre-existing log exposed forever;
#   (2) redaction of the value itself, so the log is safe even if the mode is
#       later widened by a rotation, a copy, or a backup that resets it.
umask 077

LOG_FILE="$HOME/logs/codex-spalla-trigger.jsonl"
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
chmod 0600 "$LOG_FILE" 2>/dev/null || true

# Read event payload from stdin (JSON). If unparseable, exit 0 quietly.
PAYLOAD="$(cat 2>/dev/null || true)"
[[ -z "$PAYLOAD" ]] && exit 0

# Extract fields with python (jq may not be available; python3 is).
TOOL_NAME="$(printf '%s' "$PAYLOAD" | python3 -c 'import sys,json
try:
    d = json.load(sys.stdin)
    print(d.get("tool_name") or d.get("toolName") or "")
except Exception:
    pass' 2>/dev/null || echo "")"

[[ -z "$TOOL_NAME" ]] && exit 0

TARGET="$(printf '%s' "$PAYLOAD" | python3 -c 'import sys,json
try:
    d = json.load(sys.stdin)
    inp = d.get("tool_input") or d.get("toolInput") or {}
    # Edit/Write: file_path. Bash: command. Read: file_path.
    print(inp.get("file_path") or inp.get("command") or "")
except Exception:
    pass' 2>/dev/null || echo "")"

# ─────────────────────────────────────────────────────────────────────────
# Trigger rules
# ─────────────────────────────────────────────────────────────────────────
SUGGEST="false"
REASON=""

# Rule 1: gh pr create (always)
if [[ "$TOOL_NAME" == "Bash" ]] && printf '%s' "$TARGET" | grep -qE 'gh pr create\b'; then
    SUGGEST="true"
    REASON="pr-create"
fi

# Rule 2: large git diff touching sensitive keywords
if [[ "$TOOL_NAME" == "Bash" ]] && printf '%s' "$TARGET" | grep -qE 'git diff\b'; then
    # We don't have the diff output here, only the command. As a heuristic,
    # flag if the command itself names a sensitive area.
    if printf '%s' "$TARGET" | grep -qiE 'auth|payment|migration|pricing|webhook|partner|commission|alembic'; then
        SUGGEST="true"
        REASON="sensitive-diff"
    fi
fi

# Rule 3: Edit/Write on sensitive paths
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" ]]; then
    if printf '%s' "$TARGET" | grep -qE 'apps/backend-rag/backend/services/(auth|pricing|partner|commission|payment)'; then
        SUGGEST="true"
        REASON="sensitive-service-edit"
    fi
    if printf '%s' "$TARGET" | grep -qE 'alembic/versions/[^/]+\.py$'; then
        SUGGEST="true"
        REASON="migration-file"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────
# Log + emit
# ─────────────────────────────────────────────────────────────────────────
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Always log even non-suggesting events (gives us denominator for tuning)
# Redact BEFORE truncating: a 200-char window can slice a token in half and
# leave a usable prefix, and it can also carry a whole short one.
#
# ORDERING CAVEAT, measured, because the obvious reading is wrong: redacting
# BEFORE truncating is not strictly protective. Redaction SHORTENS the string,
# which pulls bytes that the 200-char window used to cut off INTO the window.
# Proven on a 277-char command with a secret at char 253: truncate-only left it
# out; redact-then-truncate brought a following fragment in. The ordering is
# still right -- it is the only order that can redact a secret sitting inside
# the window at all -- but it does NOT eliminate exposure, and the direction of
# the trade is NOT always favourable. An earlier version of this paragraph said
# it "trades one exposure for a smaller one"; that was contradicted by
# measurement (Gear-3 gate, 2026-08-22) and is corrected here rather than
# quietly dropped. Counter-example, re-measured by the author on the shipped
# file: a 205-char command whose first 140 chars are a redactable
# CLIENT_SECRET= value and whose LAST 20 chars are a nameless secret starting
# at char 185. Truncate-only clips it to a 15-char partial; redact-first
# shortens the string and pulls the WHOLE 20-char value inside the window. So
# redaction can ENLARGE the exposure of an UNMATCHED secret while removing a
# MATCHED one. It is still the right order, on the grounds that a matched
# secret is the one this hook can do anything about -- not on the grounds that
# it is monotonically safer. Pinned in the other direction by the `straddle`
# guilt case: a 251-char command whose quoted secret starts at char 190, where
# truncate-first leaves 10 characters in cleartext and redact-first leaves none.
#
# WHAT THE VALUE BRANCH FIRES ON (three NAME shapes plus two non-name shapes --
# an earlier version of this comment said "only `NAME=value` or `NAME: value`",
# which was false as soon as the JSON and URL forms below were added):
#   a. ANY alphanumeric prefix followed by TOKEN / SECRET / PASSWORD / PASSWD /
#      CREDENTIAL, plus an optional plural `s` and an optional `_`/`-` suffix
#      chain. Covers the bare word (`TOKEN=`), the delimited compound
#      (`CLAUDE_CODE_OAUTH_TOKEN_5=`, matched from `TOKEN` onward -- the
#      lookbehind does the left-hand work, so no left wildcard is needed) and
#      the UNDELIMITED compound (`AUTHTOKEN=`, `mytoken=`, `PGPASSWORD=`).
#   b. `KEY`, and ONLY `KEY`, restricted to a bounded PREFIX VOCABULARY (or no
#      prefix at all): `KEY=`, `API_KEY=`, `APIKEY=`, `accesskey=`,
#      `SECRETKEY=`. The asymmetry with (a) is measured, not stylistic. `KEY`
#      is the one credential word that routinely ENDS an innocent identifier --
#      `monkey`, `pubkey`, `nkeys`, `topkey`, `dictkeys` -- so an open prefix on
#      it re-opens the exact over-match this hook was rejected for once already.
#      The five words in (a) practically never do, and a bounded vocabulary for
#      THEM is what leaked `PGPASSWORD=` 99 times in the live log, because
#      nobody puts `PG` in a prefix list.
#   c. a BARE GENERIC name: `pass=`, `pwd=`, `auth=`.
#   plus, on any of the above, an optional quote between name and separator, so
#   a JSON body (`-d {"api_key": "<v>"}`) is covered, not just shell/header;
#   d. URL USERINFO (`scheme://user:<secret>@host`) -- redacts the password
#      segment only, leaves scheme/user/host readable;
#   e. bare `Bearer <v>`, which carries no keyword in a NAME at all. The
#      dedicated `Authorization\s*:\s*Bearer` alternation that used to sit
#      beside it was MEASURED DEAD and deleted -- see ON RULE INTERACTION.
#
# SURVIVING UNDER-MATCH, measured against this exact matcher, not guessed. A
# redactor that claims a closed class is worse than one that names its holes:
#   - `<any-prefix>KEY=` where the prefix is outside the vocabulary in (b):
#     `PUBKEY=`, `M5KEY=`, `QKEY=`, `ORIGINALAPIKEY=`, `MACHINEHMACKEY=` leak
#     in full. Their DELIMITED twins (`PUB_KEY=`, `ORIGINAL_API_KEY=`) are
#     caught. This is the deliberate price of keeping `monkey=patch` innocent,
#     and it is the ONE class where this matcher is knowingly weaker than the
#     bare-substring version. Measured on the live log at 2026-08-21T21:08Z:
#     40 distinct names / 136 occurrences that the substring version redacted
#     and this one does not -- most (`KEYWORDS` 15, `KEYCHAIN` 12,
#     `StrictHostKeyChecking` 21, `MONKEYPATCH` 3, `ONKEYDOWN` 2) were that
#     version OVER-matching, but `QKEY` (19), `UKEY` (4), `M5KEY`, `PUBKEY`,
#     `ORIGINAL*KEY` (3) and `MACHINEHMACKEY` are real credential-shaped names
#     this hook does not cover.
#   - Credential words outside the six in (a)+(b): `--pin=`, `--otp=`,
#     `--salt=`, `--cookie=` all leak.
#   - `Authorization:` with anything other than `Bearer` (`Basic <b64>`, or an
#     opaque token with no scheme word) leaks; only the Bearer shape is caught.
#   - A secret NOT JOINED TO A CREDENTIAL-ISH NAME BY `=` OR `:`. This entry
#     used to be titled "a POSITIONAL secret with no name", which its own
#     example contradicted -- the class is far wider and INCLUDES every
#     `--flag <value>` form, because rule 2 requires the separator to sit
#     between the name and the value and a SPACE there defeats it outright.
#     Measured leaking through this hook: `gh auth login --token <v>`,
#     `mytool --api-key <v>`, `mysql --password <v>`,
#     `echo <v> | gh secret set FOO`, and the genuinely nameless
#     `mytool deploy <v>` / `mysql -p<v>`. Also here, for a different reason:
#     `curl -u admin:<v>` and `curl --user admin:<v>` DO carry a `:`, but they
#     hang it off a USERNAME, which is not a credential-ish name.
#   - SINGLE-SEGMENT ATTRIBUTE ASSIGNMENT. The lookbehind's `.` exclusion is
#     documented below as over-match PROTECTION (`jq .key = 1` stays innocent);
#     its OTHER half is an under-match and was never stated anywhere:
#     `python3 -c "c.token = \"<v>\""`, `c.secret = "<v>"` and
#     `jq ".password = \"<v>\"" cfg.json` all leak IN FULL. Same shape of
#     trade as the KEY vocabulary -- a named price, not a closed class.
#     Multi-segment names are still caught (`cfg.api_key = "<v>"` matches at
#     `key`, after the `_`).
#   - AN INDEX BETWEEN THE NAME AND THE SEPARATOR: `SECRETS[0]=<v>` and
#     `TOKEN[0]=<v>` leak, because `[0]` is neither the optional quote nor the
#     separator rule 2 permits between name and value.
#   - An UNQUOTED value containing a space: only the first word is redacted.
#
# OVER-MATCH residual risk (cicatrix superscar #3, the guard-over-match twin of
# the under-match list above). The keyword must end the NAME (as a delimited
# segment, a vocabulary compound, or a wide-word suffix) to fire, but it is
# still a NAME match with no notion of "is this actually a secret", and the
# damage is not limited to the value. MEASURED on the live log -- each figure
# carries its OWN instant, because this file grows while it is being measured
# and an earlier draft welded three different instants under one timestamp:
#   - THIS matcher (round 4, shipped): 2291 lines of 333,832 = 0.686%, at
#     2026-08-21T22:49:57Z. Replayed side by side with the round-3 matcher,
#     the two produce BYTE-IDENTICAL output on every line of that log -- the
#     ordering leak this round fixed has zero occurrences in this corpus.
#   - the segment-only version it replaces: 1253 = 0.376%, at 20:49Z;
#     the bare-substring version before that: 1874 = 0.562%, same instant.
# So it redacts MORE of the real corpus than the version that was rejected for
# over-matching, along different axes (297 URL-userinfo, ~210 bare-generic
# `auth`/`pwd`/`pass`, ~120 wide-suffix).
# That is the accepted trade, stated as a number rather than a hope:
#   - a legitimately-named non-secret (`FEATURE_FLAG_KEY=`, a cache-partition
#     name, `PWD=/tmp`, `redis-cli --pattern 'keys:*'`) redacts just as hard;
#   - the replacement SWALLOWS the rest of the unquoted value, so
#     `sed -i 's/key=old/key=new/'` loses its second half entirely;
#   - the replacement NORMALISES the separator to `=`, so a header or JSON
#     `name: value` is rewritten as `name=<REDACTED>`. The log stops being a
#     replayable command for those lines. Accepted: this is a telemetry log,
#     not a transcript.
# Two over-match shapes belong to the OTHER rules, not to the NAME rule, and
# went undisclosed until the Gear-3 gate drove them:
#   - rule 4's `Bearer` is a BARE WORD in prose, not a header. It eats the next
#     >=8-char `[A-Za-z0-9._-]` run in ANY text, with no name, no assignment and
#     no separator required: `gh pr create --title "Bearer authentication
#     rollout"` is logged as `Bearer <REDACTED> rollout`, and
#     `git commit -m "fix: bearer credentials refresh loop"` is mangled the same
#     way. `gh pr create` is TRIGGER RULE 1 of this very hook, so those are
#     precisely the lines it exists to record. Measured on the live log at
#     2026-08-21T22:50:35Z / 333,833 lines: 8 lines match, 10 matches total,
#     and 3 of the 10 carry no digit at all -- an 8-letter lowercase word, a
#     19-char lowercase hyphenated slug, and a 12-letter word that is the
#     MEASURING SESSION'S OWN PROBE STRING, which is this log's documented
#     self-inflation showing up inside the very measurement of it. Deliberately
#     NOT narrowed to require a digit or an uppercase letter: that would trade a
#     3-occurrence over-match for an under-match on an all-lowercase bearer
#     token, which inverts the preference this hook states two paragraphs above.
#   - rule 3 redacts a PORT when the port sits in the userinfo PASSWORD
#     position: `curl "https://example.com:8443@evil.test/"` is logged as
#     `example.com:<REDACTED>@`. Note what this is NOT: a genuine `host:port`
#     has no `@` after it, so this rule cannot fire on one -- verified,
#     `postgres://appuser@db.host.test:5432/x` and
#     `https://api.example.test:8443/health` are both left intact. An
#     all-digits carve-out was considered and REJECTED on measurement: 0 of 367
#     URL-userinfo matches in the live log have an all-digit password segment,
#     so it would fix nothing real while opening an under-match on any numeric
#     credential (a PIN, a numeric DB password). For scale on the same rule:
#     354 of those 367 matches are one test-fixture DSN
#     (`postgresql://test:<4 lowercase letters>@`), i.e. this rule too fires
#     overwhelmingly on non-secrets, which is the accepted direction.
# Given the choice between over-redacting a non-secret and under-redacting a
# real one, this hook accepts the former. The guilt/innocence corpus in
# scripts/tests/test_codex_spalla_trigger_redaction.sh proves the specific
# forms it enumerates; it is not a proof that no legitimately-named non-secret
# value anywhere can trip the match.
#
# On the WILDCARDS. The RIGHT-side one is load-bearing. A redactor written as
# `TOKEN=` matches CLAUDE_CODE_OAUTH_TOKEN= and misses CLAUDE_CODE_OAUTH_TOKEN_1=
# -- that exact off-by-one is how four tokens were printed by a probe that
# believed it was redacting. The first version of THIS fix then required at
# least one char BEFORE the keyword, so it caught CLAUDE_CODE_OAUTH_TOKEN_1=
# and missed a bare TOKEN= -- the same off-by-one, mirrored, found by the
# Gear-3 gate. The LEFT side needs no wildcard at all: the negative lookbehind
# does that work, and the replacement re-emits group(1) verbatim so whatever
# preceded the keyword survives untouched. MEASURED, not assumed: adding back
# `(?:[A-Za-z0-9]+[_-])*` on the left produced byte-identical output across the
# full 44-case corpus (guilt + innocence + 12 dash/prefix probes), so it was
# deleted. The optional leading `(?:--?)?` was the same kind of dead weight and
# is now deleted too: a leading `-`/`--` is neither alnum nor `.`, so the
# lookbehind already lets the match start right after it, and the unconsumed
# dashes stay in the string either way. MEASURED across 174 cases (the whole
# guilt+innocence corpus plus every vocabulary compound under six lead-in
# shapes: bare, `-`, `--`, `x--`, `a-b-`, `foo---`): byte-identical output with
# and without it. It was also the ONE mutant in this file's mutation set that
# nothing could kill -- which is what dead weight looks like from the test
# side. Flag forms (`--token=`, `-key=`) still redact, and have their own guilt
# cases. The lookbehind's `.` exclusion is narrower than it
# looks: it makes a SINGLE-SEGMENT attribute access innocent (`foo.key = x`,
# `jq '.key = 1'`), but `jq '.api_key = 1'` and `cfg.api_key = "x"` ARE
# redacted, because the match starts at `key` after the `_`, not at the `.`.
# That exclusion is TWO-SIDED and only one side was ever written down: it is
# over-match protection AND an under-match, because a single-segment attribute
# assignment to a real credential (`c.token = "<v>"`, `c.secret = "<v>"`,
# `jq '.password = "<v>"'`) leaks in full. Listed in the under-match block
# above; repeated here because this is the paragraph that sells the exclusion.
#
# ON RULE INTERACTION -- ORDER IS NECESSARY AND WAS NOT SUFFICIENT. Every rule
# REWRITES the span it matches, and a rewrite can destroy the marker another
# rule needs. The first fix for this was purely an ordering one: run the
# marker-anchored rules (1, 3, 4) before the generic NAME rule (2), on the
# stated principle that "rule 2 is the destructive one". THE PRINCIPLE WAS
# FALSE, and the Gear-3 gate falsified it ON the ordering fix itself:
#   - RULE 2 BEFORE RULE 4 LEAKED A TOKEN IN FULL. When a credential-ish NAME
#     carries an UNQUOTED value whose first word is `Bearer`, rule 2 replaced
#     exactly that word -- `-H 'X-Auth: Bearer <v>'` became
#     `X-Auth=<REDACTED> <v>` -- destroying the only marker rule 4 had.
#     `Authorization: Bearer <v>` was never affected, because `Authorization`
#     is not a NAME rule 2 matches, which is exactly why the bug hid behind a
#     passing control case.
#   - THE MIRROR, which the reorder alone CREATED: rule 4 eats an 8+ char
#     [A-Za-z0-9._-] run after `Bearer`, and a credential NAME is exactly such
#     a run. `Bearer refresh_token=<v>` became `Bearer <REDACTED>=<v>` -- the
#     marker replaced the NAME, the value survived in full, and the output
#     READS as if redaction fired. Rule 1 does the same thing whenever a real
#     token prefix starts a NAME: `echo ghp_MYTOKENS=<v>`.
#   - RULE 4 BEFORE RULE 3 LEAKS A URL PASSWORD. `Bearer postgresql://u:<v>@h`:
#     rule 4 eats the 10-char scheme name and leaves `<REDACTED>://u:<v>@h`,
#     which no longer matches rule 3's `[a-zA-Z][a-zA-Z0-9+.-]*://` anchor.
# So the cure is NOT an order. EVERY marker-anchored rule now carries
# ASSIGN_TAIL -- an optional `[=:]` plus a full VALUE (quoted or bare) -- so a
# rule that consumes a marker also consumes the assignment hanging off it, and
# cannot hand rule 2 a corpse. The order 1 -> 3 -> 4 -> 2 is KEPT because the
# third adjacency above is independent of the tail, and because a
# marker-anchored rule is more specific than the generic NAME rule; it is no
# longer load-bearing for the first two.
# WHAT THE ORDER MUTANTS ACTUALLY PROVE: all five non-current permutations of
# rules 2/3/4 fail the suite. That proves the suite CONSTRAINS the order. It
# does NOT prove the order is safe -- the mirror leak passed every one of those
# mutants and shipped anyway, because no case in the corpus had its shape. A
# mutation score is a statement about the corpus, never about the world.
# The mirror class has 7 guilt cases now (both quote styles included: a bare
# `[^\s"']*` tail, which is what was first proposed, would have left the
# quoted forms leaking).
# Rule 1's position is held by ARGUMENT, not measurement: it re-emits its own
# prefix and its character classes exclude `:` and `/`, so it cannot destroy
# rule 3's or rule 4's marker. That argument was ALWAYS about the marker of a
# LATER rule and never covered rule 2's NAME, which is the hole ASSIGN_TAIL now
# closes on it too.
# The `Authorization\s*:\s*Bearer|` alternation rule 4 used to carry was
# MEASURED DEAD and deleted, by the same test this PR applied twice before to
# `(?:--?)?` and the left wildcard: replayed over all 333,794 live-log target
# fields, keeping ONLY the bare alternation produced byte-identical output on
# every line (0 differences), while keeping only the `Authorization`-anchored
# one changed 2. An alternation nothing can fail on is dead weight.
TARGET_JSON="$(printf '%s' "$TARGET" | python3 -c '
import sys, re, json
s = sys.stdin.read()
# A VALUE is what sits on the right of a credential assignment: a
# double-quoted run, a single-quoted run, or a bare run up to whitespace.
# Defined FIRST because three different rules need it -- see ASSIGN_TAIL.
VALUE = r"(?:\"[^\"]*\"|\x27[^\x27]*\x27|[^\s\"\x27]+)"
# EVERY marker-anchored rule must be able to swallow an assignment that
# FOLLOWS its marker, or it destroys the NAME rule 2 needs and leaves the
# value in the clear (see ON RULE INTERACTION above -- this is the MIRROR of
# the bug the rule order fixes, found by the Gear-3 gate on the fix itself).
ASSIGN_TAIL = r"(?:[\"\x27]?\s*[=:]\s*" + VALUE + r")?"
# 1. Known credential shapes, by their own prefixes. Each carries ASSIGN_TAIL
#    because the prefix can itself be the NAME: echo ghp_MYTOKENS=<v> used
#    to log as gh_<REDACTED>=<v> -- marker consumed, value intact.
#    (No backticks anywhere inside this single-quoted python block: shellcheck
#    reads them as command substitution and raises SC2016.)
s = re.sub(r"sk-ant-[A-Za-z0-9_-]{8,}" + ASSIGN_TAIL, "sk-ant-<REDACTED>", s)
s = re.sub(r"gh[pousr]_[A-Za-z0-9]{8,}" + ASSIGN_TAIL, "gh_<REDACTED>", s)
s = re.sub(r"github_pat_[A-Za-z0-9_]{8,}" + ASSIGN_TAIL, "github_pat_<REDACTED>", s)
# 3. URL userinfo: scheme://user:<secret>@host -- password segment only.
#    Runs BEFORE rule 4: rule 4 would otherwise eat an 8+ char scheme name and
#    leave a bare ://user:<secret>@ with no scheme for this rule to anchor on.
s = re.sub(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^\s:/@]+:)[^\s/@]+@", r"\1<REDACTED>@", s)
# 4. Bearer, which carries no keyword in a NAME at all. Runs BEFORE rule 2:
#    rule 2 would otherwise rewrite a header X-Auth: Bearer <v> into
#    X-Auth=<REDACTED> <v> and leave the token in the clear (see ON RULE
#    INTERACTION above). The dedicated Authorization-anchored alternation
#    that used to sit here was MEASURED DEAD and deleted -- see the same block.
s = re.sub(
    r"(?i)\b(Bearer)\s+[A-Za-z0-9._-]{8,}" + ASSIGN_TAIL,
    r"\1 <REDACTED>",
    s,
)
# 2. Anything ASSIGNED to a credential-ish NAME (see the comment above for the
#    three name shapes, the KEY asymmetry, and what this does NOT catch). LAST
#    of the four, because it is the only DESTRUCTIVE rewrite: it consumes the
#    whole value and normalises the separator, so it destroys the markers the
#    other rules anchor on.
WIDE = r"(?:TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)"
PRE = (r"(?:API|AUTH|ACCESS|APP|CLIENT|PRIVATE|MASTER|ROOT|ADMIN|USER|SESSION"
       r"|REFRESH|OAUTH|BEARER|MY|ID|TOKEN|SECRET|PASSWORD|PASSWD"
       r"|CREDENTIAL)")
TAIL = r"S?(?:[_-][A-Za-z0-9]+)*"
NAME = (r"(?<![A-Za-z0-9.])(?:"
        + r"[A-Za-z0-9]*" + WIDE + TAIL   # a. ANY prefix + a wide credential word
        + r"|" + PRE + r"?KEY" + TAIL     # b. KEY: bounded prefix, or none at all
        + r"|(?:PASS|PWD|AUTH)"           # c. bare generic name
        + r")")
s = re.sub(
    r"(?i)(" + NAME + r")[\"\x27]?\s*[=:]\s*" + VALUE,
    lambda m: m.group(1) + "=<REDACTED>",
    s,
)
print(json.dumps(s[:200]))
' 2>/dev/null || echo '""')"
{
    printf '{"ts":"%s","tool":"%s","target":%s,"suggested":%s,"reason":"%s"}\n' \
        "$TS" "$TOOL_NAME" "$TARGET_JSON" "$SUGGEST" "$REASON"
} >> "$LOG_FILE" 2>/dev/null || true

if [[ "$SUGGEST" == "true" ]]; then
    echo "[spalla-suggest] consider /codex-second-opinion before commit (reason: $REASON)" >&2
fi

exit 0
