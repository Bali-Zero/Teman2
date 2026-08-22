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
#   - A BACKSLASH-ESCAPED QUOTE around the value defeats VALUE in EVERY rule.
#     Named 2026-08-22 by the Gear-3 gate; PRE-EXISTING, not introduced by any
#     commit on this branch, and NOT fixed here -- naming it is the fix this
#     round owes, and a change to VALUE's quoting is its own diff. VALUE's two
#     quoted branches need a literal quote next, a `\` fails them, and the bare
#     branch stops dead at the `"`. Re-measured on THIS matcher:
#       export API_KEY=\"<v>\"          -> API_KEY=<REDACTED>"<v>\"   value survives
#       curl -d "TOKEN=\"<v>\""         -> TOKEN=<REDACTED>"<v>\""    value survives
#       curl -d "{\"api_key\": \"<v>\"}" -> UNCHANGED, byte for byte
#     The third is the ordinary way to write a JSON body inside a double-quoted
#     shell string, and the corpus's JSON guilt case uses the single-quoted-outer
#     form, which works -- so the corpus proves the shape it enumerates and this
#     one hides behind it. That is a lesson about corpora, not just about quotes.
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
#   - THE THIRD DIRECTION, which the CURE for the mirror created: a tail whose
#     bare branch runs to the next whitespace can CROSS a later rule's marker.
#     `github_pat_<8+>=bearer <v>` had rule 1 -- which runs FIRST -- eat the
#     word `bearer` as its own value, so rule 4 had nothing to anchor on and the
#     token stood in the clear beside a `<REDACTED>` that had fired for
#     something else. 258 inputs in a differential fuzz against the pre-tail
#     version. Rule 1's greedy alnum class makes it worse:
#     `ghp_<8+>https://u:xx:Bearer <v>` kills rule 3's AND rule 4's marker in
#     one bite.
# So the cure is NOT an order, and it is not a tail either. EVERY
# marker-anchored rule carries ASSIGN_TAIL -- an optional `[=:]` plus a value --
# so a rule that consumes a marker also consumes the assignment hanging off it
# and cannot hand rule 2 a corpse; and that tail's bare branch is TEMPERED, so
# it may not cross a position where any later marker starts. The two properties
# are both needed: the tail alone opened the third direction, and tempering
# alone would not have closed the mirror. The order 1 -> 3 -> 4 -> 2 is KEPT because the
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
# RULE 1'S POSITION USED TO BE HELD BY AN ARGUMENT THAT ASSIGN_TAIL ITSELF
# INVALIDATED, and the sentence survived one commit past its truth: "it
# re-emits its own prefix and its character classes exclude `:` and `/`, so it
# cannot destroy rule 3's or rule 4's marker". True of the OLD rule 1. False the
# moment a tail was bolted on, because the tail consumes `[=:]` and its value
# class contains both `:` and `/` -- so rule 1, which runs FIRST, could reach
# forward past its own credential into rule 3's and rule 4's territory.
# Measured, not argued: `github_pat_<8+>=bearer <v>` logged as
# `github_pat_<REDACTED> <v>`, value intact. Six reproducers, and a differential
# fuzz against the pre-tail version found 258 inputs that leaked only with the
# untempered tail. That is what TEMPERED_VALUE exists for. Rule 1's position is
# now held by CONSTRUCTION -- but the construction is only as wide as MARKER, and
# saying it any other way is how the FOURTH direction shipped: the first MARKER
# listed rules 1, 3 and 4 and omitted rule 2's NAME, so "no tail can cross a
# later rule's marker" was true and still left `<prefix>:TOKEN: <v>` leaking.
# MARKER now covers all four rules. The honest form of the claim is therefore:
# no tail can cross an anchor THAT MARKER LISTS, and MARKER is the thing that
# has to be kept complete.
# The `Authorization\s*:\s*Bearer|` alternation rule 4 used to carry was
# MEASURED DEAD and deleted, by the same test this PR applied twice before to
# `(?:--?)?` and the left wildcard: replayed over all 333,794 live-log target
# fields, keeping ONLY the bare alternation produced byte-identical output on
# every line (0 differences), while keeping only the `Authorization`-anchored
# one changed 2. An alternation nothing can fail on is dead weight.
TARGET_JSON="$(printf '%s' "$TARGET" | python3 -c '
import sys, re, json
s = sys.stdin.read()
# WHY THIS IS A SINGLE EARLIEST-ANCHOR CUT AND NOT A CASCADE OF REWRITES.
# The four credential shapes below used to be four sequential re.sub calls, each
# consuming its match. That architecture leaked FIVE times, and every leak was
# the same defect wearing a different hat: one rule consumed text containing a
# LATER rule anchor, so the later rule never saw its own trigger and the value
# behind it stayed in the clear. Five cures were attempted -- reordering the
# rules, adding an assignment tail, tempering that tail against a marker list,
# widening the marker list to include rule 2 NAME -- and each cure was followed
# by a gate finding the next direction of the same defect. The fifth direction
# killed the approach: the tail two QUOTED branches consume a COMPLETE delimited
# value, and a comment here asserted that this made them safe because whatever
# marker they swallow they also redact. That was false. The marker is inside the
# quotes; its VALUE is behind the closing quote. Measured, all four rules:
#     ghp_<8+>="junk TOKEN=" <secret>   ->   gh_<REDACTED> <secret>
# The lesson is not that the sixth patch was missing. It is that a blacklist
# which must enumerate every structure a secret can hide in cannot be argued
# sound, and every added rule adds a surface for the next one to swallow.
#
# So: nothing is rewritten in place and nothing is consumed. Each anchor is
# searched independently against the ORIGINAL string, and everything from the
# EARLIEST anchor to the end of the string is replaced by one <REDACTED>. No
# text after a credential anchor ever reaches disk, so the class dies by
# construction rather than by enumeration -- there is no "behind" left for a
# value to survive in. The tempering apparatus this replaced (MARKER,
# TEMPERED_VALUE, ASSIGN_TAIL and the load-bearing rule ORDER) is gone with it.
#
# The COST is real and deliberate: a command whose credential sits early loses
# the diagnostic tail that follows it. This is affordable here and nowhere else
# in the repo -- the target field has NO programmatic consumer (the hook own
# routing at the top of this file reads TARGET in memory and never the log),
# so the field is diagnostic-only, and the prefix that survives is the part
# that says WHICH command ran.
#
# The anchors are the rules OWN patterns, at their own boundaries and length
# floors -- deliberately NOT the old wide MARKER list, which existed to be
# conservative as a lookahead and is too wide as a trigger: its bearer
# alternative carried no left word-boundary, so it would fire on flagbearer and
# on a Bearer below the 8-char floor, both of which are innocence cases in
# scripts/tests/test_codex_spalla_trigger_redaction.sh. A rule that does not
# fire today contributes no anchor and therefore changes no innocent line.
# (No apostrophes and no backticks anywhere in this single-quoted python block:
# an apostrophe would terminate the shell string, and shellcheck reads a
# backtick as command substitution and raises SC2016. Use \x27.)
WIDE = r"(?:TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)"
PRE = (r"(?:API|AUTH|ACCESS|APP|CLIENT|PRIVATE|MASTER|ROOT|ADMIN|USER|SESSION"
       r"|REFRESH|OAUTH|BEARER|MY|ID|TOKEN|SECRET|PASSWORD|PASSWD"
       r"|CREDENTIAL)")
# The [0-9]* is a RECALL fix with a deliberately narrow shape, added 2026-08-22
# after an independent gate drove 383 inputs through the real hook: TOKEN_2= was
# caught and TOKEN2= was not, because the suffix could only arrive as a _- or
# --delimited segment. That split the commonest real names in half -- TOKEN1,
# SECRET3, PGPASSWORD1, AUTH1 all leaked in FULL, and PGPASSWORD is the exact
# name this repo already measured leaking 99 times in the live log. DIGITS ONLY,
# never [A-Za-z0-9]*: a bare alphanumeric suffix would swallow TOKENIZER=fast,
# which is an innocence case here, and the whole reason KEY carries a bounded
# prefix vocabulary is that credential words routinely END innocent identifiers.
# Digits do not appear in that role. DECLARED RESIDUAL: a bare LETTER suffix
# (TOKENA=, TOKENV2=) still leaks -- it is not separable from TOKENIZER by any
# rule this shape can express, so it is priced, not closed.
TAIL = r"S?[0-9]*(?:[_-][A-Za-z0-9]+)*"
# TAIL_ND is TAIL WITHOUT the bare-digit suffix, and it exists because a second
# gate falsified the sentence above. "Digits do not appear in that role" is FALSE
# for a BARE credential word: key1, key2, key3 are the canonical placeholder
# identifiers in form encodings, dict literals, configmaps and annotations, and
# a form-encoded curl body of key1=v1 and key2=v2, --from-literal=key1=hello,
# UPDATE t SET key1=1, and a sed rewriting key1=old to key1=new were all
# truncated in full -- 180 of 276
# digit-suffixed identifiers newly damaged, on inputs the previous hook left
# intact. The distinction is the same one that gave KEY a bounded prefix
# vocabulary in the first place, applied one level deeper: WITH a prefix from that
# vocabulary the name is a credential (APIKEY2, SESSIONKEY8) and digits are safe;
# BARE, it is a placeholder and they are not. Branch (a) keeps the digits because
# TOKEN/SECRET/PASSWORD/PASSWD/CREDENTIAL are not words anything uses as a
# placeholder key.
TAIL_ND = r"S?(?:[_-][A-Za-z0-9]+)*"
NAME = (r"(?<![A-Za-z0-9.])(?:"
        + r"[A-Za-z0-9]*" + WIDE + TAIL   # a. ANY prefix + a wide credential word
        # b. KEY, split by whether a vocabulary PREFIX is present: with one, the
        #    name is a credential and a bare digit suffix is safe; without one it
        #    is a placeholder identifier and a bare digit suffix is not (see
        #    TAIL_ND above). Both forms still take the delimited suffix chain.
        + r"|" + PRE + r"KEY" + TAIL
        + r"|KEY" + TAIL_ND
        # c. generic name, BARE -- no plural, no digits, no delimited chain.
        #    The numeric half was added here on 2026-08-22 and REMOVED the same
        #    day, on measurement, when a second gate showed the rationale written
        #    for it ("the digits close a hole that has no innocent counterpart")
        #    was simply false: AUTH2=off is a protocol version, PASS1/PASS2 are
        #    compiler and report passes, PWD2=/srv/build2 is a path -- all newly
        #    truncated, all intact before. This branch has NO credential word to
        #    lean on, which is exactly why it cannot afford an ambiguous suffix.
        #    The S? that rode in with it (AUTHS=, PASSS=, PWDS=, none of them
        #    described in any artifact and none pinned by any case) goes with it.
        #    COST, declared: AUTH1= and PASS2= leak again. A real delimited
        #    credential is AUTH_TOKEN, and branch (a) already has it.
        + r"|(?:PASS|PWD|AUTH)"
        + r")")
# A VALUE is what sits on the right of a credential assignment: a double-quoted
# run, a single-quoted run, or a bare run up to whitespace. It no longer has to
# be tempered against anything -- it only has to prove an assignment EXISTS, so
# that rule 2 fires on a real assignment and stays silent on jq .key or
# --keyfile. Where the value ENDS is now irrelevant: the cut runs to end-of-string.
VALUE = r"(?:\"[^\"]*\"|\x27[^\x27]*\x27|[^\s\"\x27]+)"
ANCHORS = (
    # 1. Known credential shapes, by their own prefixes.
    r"sk-ant-[A-Za-z0-9_-]{8,}",
    r"gh[pousr]_[A-Za-z0-9]{8,}",
    r"github_pat_[A-Za-z0-9_]{8,}",
    #     Slack, whose tokens travel in an Authorization header with NO Bearer and no
    #     credential-ish name, so nothing else here would ever see one.
    r"xox[baprs]-[A-Za-z0-9-]{10,}",
    # 1b. A PEM private-key block anchors on NOTHING above: PRE?KEY needs KEY glued
    #     to its prefix, and PRIVATE KEY has a SPACE, so the single most
    #     unambiguous credential shape there is was invisible. Found by a refuter,
    #     not by the corpus. No over-match risk worth weighing: the delimiter line
    #     is not something an innocent command says by accident.
    #     The trailing [A-Z ]* matters: PGP writes
    #     -----BEGIN PGP PRIVATE KEY BLOCK-----, so a form requiring PRIVATE KEY to be
    #     followed immediately by the dashes missed one of the commonest private-key
    #     formats there is. A CERTIFICATE, a PUBLIC KEY and a CERTIFICATE REQUEST are
    #     all still innocent -- none of them contains the words PRIVATE KEY.
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY[A-Z ]*-----",
    # 3. URL userinfo: scheme://user:<secret>@host. The whole userinfo form is
    #    the anchor, so a bare scheme:// in an innocent URL does not fire.
    #     ANCHORED ON :// ITSELF, with no scheme pattern at all -- and the two
    #     rejected alternatives are why. UNBOUNDED [a-zA-Z][a-zA-Z0-9+.-]* retries
    #     from every position of a long alphanumeric run and rescans to the end:
    #     2462 ms on a 50KB command containing no credential, in a hook that fires
    #     on EVERY tool call. Bounding it to sixteen fixed the time and introduced a
    #     COVERAGE REGRESSION at the boundary -- a 17-character scheme stopped
    #     anchoring, so a17chars://u:<secret>@h leaked where the unbounded rule had
    #     redacted it. Found by a cross-family seat on a differential old-vs-new
    #     hunt, AFTER two fuzzers written by this design author (a fragment product
    #     and a 300k character-level run) had both reported zero: neither could
    #     reach a valid userinfo URL carrying an over-long scheme, which is exactly
    #     what "a fuzz score describes the GENERATOR" means in practice.
    #     Anchoring on the literal :// is strictly better than both: no scheme
    #     length can escape it, and the literal prefix keeps it linear (0.52 ms on
    #     the same 50KB input). The scheme is not lost from the log either -- the
    #     cut starts AT the ://, so what precedes it survives.
    #     The PASSWORD class is [^\s@]+ and NOT [^\s/@]+: a URL password may contain
    #     a slash, and forbidding one meant postgres://u:pa/ss@h anchored on nothing
    #     and leaked in full. The USER class still forbids the slash, and that is
    #     what keeps the shape pinned to real userinfo -- https://host/a:b@c does not
    #     match, because the user run stops at the slash before it can reach a colon.
    #     A cross-family seat surfaced this as a coverage REGRESSION in a contrived
    #     form (the old cascade consumed a token containing the slash, which made a
    #     userinfo URL appear that had not been there); the plain form above is the
    #     same gap without the theatre, and it leaked on the old design too.
    #     The (?!\\d+[/?#]) is a PORT DISCRIMINATOR and it is the price of letting a
    #     password contain a slash. Without it, host:port/path@segment reads exactly
    #     like user:password@host, and three entirely ordinary commands were
    #     truncated in full: a registry URL with a digest
    #     (https://reg.test:5000/v2/img@sha256), a release path
    #     (https://example.test:8443/releases/app@2), and any :8080 URL with an at-sign
    #     later in the path. A port is digits followed by / ? or #; a password is not,
    #     and an ALL-DIGIT password immediately before the @ still anchors because the
    #     lookahead needs one of those three characters after the digits. Scored
    #     against both alternatives: this form is 6/6 guilt and 0 false positives,
    #     the slash-permitting one without the lookahead was 6/6 and 3, and the
    #     original slash-forbidding one was 4/6 and 0.
    #     PATH-AWARE, and the refinement is the whole point: the earlier form rejected
    #     ANY digits-then-delimiter, which threw away a real password beginning with
    #     digits (https://alice:123?x@db.test/query redacted before, leaked after).
    #     What actually separates the two shapes is WHERE the at-sign sits: in
    #     host:port/path@segment there is a SLASH between the colon and the at-sign;
    #     in user:password@host there is not. Requiring that slash in the rejection
    #     scores 6/6 guilt and 0 false positives, where the digits-only form scored
    #     5/6 and 0.
    #     EVERY RUN HERE IS LENGTH-BOUNDED, and the bound is the whole point.
    #     Unbounded, this rule is QUADRATIC in the input: the engine restarts at
    #     every :// in the string, and each attempt scans [^\s@]+ to the end of the
    #     whitespace-free run before failing for want of an @. Measured on a
    #     minified-JSON shape -- ("://u" + 30 chars) repeated, no @ anywhere, which
    #     is an ordinary lockfile or config one-liner, not a crafted attack:
    #     5545 ms at 200KB and 23015 ms at 400KB, i.e. PAST the 10s wall-clock
    #     guard below. Three further shapes aimed at the port lookahead rather than
    #     the password cost 3716 / 4250 / 5023 ms. Bounding all three runs to 2048
    #     makes the per-position cost constant and the whole rule linear: the same
    #     four shapes cost 92-123 ms at 200KB and 245 ms at 400KB (2x input, 2x
    #     time -- linear, as intended). This is the FOURTH appearance of one family
    #     in this file (unbounded scheme, unbounded Basic prefix, and now both the
    #     userinfo password and its lookahead): an unbounded run that has to be
    #     re-scanned from many start positions. It is bounded here in EVERY run at
    #     once rather than in the one that was measured slowest, because patching
    #     the measured instance is what let it come back three times.
    #     WHY NOT A CHEAP `"@" in s` PRE-CHECK, which would cost nothing and lose no
    #     coverage: it is defeated by a single leading @. With "@" + the payload
    #     above, the pre-check passes and every later attempt still scans to the end.
    #     DECLARED RESIDUAL, deliberately accepted: a URL password longer than 2048
    #     characters no longer anchors. Verified at the boundary -- 2047 and 2048
    #     redact, 2049 and 5000 do not. The scar this rule already carries (a
    #     16-character scheme bound that regressed coverage at 17) says bounds bite
    #     at PLAUSIBLE values; 2048 is not one. A long JWT, the longest credential
    #     that realistically travels in userinfo, runs a few hundred characters.
    #     A differential run of 60000 inputs against the unbounded form found ZERO
    #     divergences below the bound, and by construction a bound can only make the
    #     match START LATER or vanish -- it can never invent a false positive.
    #     THE `/@` ALTERNATIVE, added 2026-08-22 after a peer session drove 197
    #     invented inputs through the hook: a path that STARTS with an at-sign --
    #     https://staging.example.test:8443/@mentions/feed, the ordinary shape of a
    #     self-hosted Mastodon-style API on a non-default port -- was truncated in
    #     full, and it ate the SCHEME with it (logged as `https` + the marker). The
    #     path-aware discriminator could not see it: it demands a SLASH after the
    #     port delimiter, and here the at-sign arrives before any second slash.
    #     Rejecting a bare `\d+/` was tried first and is WORSE: it also discards
    #     a real userinfo password that BEGINS WITH DIGITS and then contains a
    #     slash (spelled out here as a full DSN in an earlier draft, which made
    #     scripts/lint_pg_dsn_credentials.py fail this file -- a literal DSN in a
    #     COMMENT is still a literal DSN in the tree), scoring 6/7 guilt and
    #     1/7 false positives. Requiring the at-sign
    #     to follow the slash IMMEDIATELY scores 7/7 and 1/7, against 7/7 and 3/7
    #     for the form it replaces -- strictly better in both directions.
    #     AND IT FALSIFIES A CLAIM THIS FILE USED TO MAKE. The pack asserted rule 3
    #     "cannot fire on a genuine host:port, which has no @ after it (verified)".
    #     The verification was vacuous: both examples cited had NO at-sign after the
    #     port at all, so they could not test the claim they were offered as proof
    #     of. A genuine host:port followed by an at-sign later in the path is
    #     exactly what broke it.
    r"://[^\s:/@]{1,2048}:(?!\d+(?:/@|[/?#][^\s@]{0,2048}/))[^\s@]{1,2048}@",
    # 4b. Authorization: Basic <base64>. Rule 4 covers Bearer only, and this was a
    #     NAMED residual risk rather than an oversight -- promoted to an anchor when
    #     the same cross-family seat pointed out that a wholly ordinary curl -H
    #     header carrying base64 credentials passed through untouched. The 16-char
    #     floor and the base64 alphabet keep the ordinary English word innocent:
    #     "Basic usage", "Basic auth support", "Basic Income Study 2026" all stay.
    #     ANCHORED ON THE HEADER, not on the bare word, and this is a CORRECTION of
    #     the first version of this rule, which fired on prose: "Basic
    #     telecommunications" is eighteen characters of the base64 alphabet and
    #     tripped a bare \\bBasic\\s+[A-Za-z0-9+/=]{16,}. My own innocence cases missed
    #     it because I had used SHORT words (Basic auth support), so the length floor
    #     hid the defect from the very corpus written to catch it -- found by a
    #     cross-family seat one commit later. Requiring the Authorization: header
    #     scores 3/3 on guilt with 0 false positives on the prose set, where the bare
    #     form scored 3/3 and 1. The [A-Za-z-]* prefix admits Proxy-Authorization.
    #     NOTE THE ASYMMETRY WITH BEARER, which IS bare: rule 4 mangling prose that
    #     contains the word bearer is a pre-existing, measured and DECLARED residual
    #     (8 lines in the live log). Inheriting a known defect into a rule added today
    #     would be a choice, not an accident, so this one is tighter than its sibling.
    #     The payload must contain at least ONE digit or + / = -- a length floor alone
    #     is not enough, because a long English word IS valid base64 alphabet:
    #     Authorization: Basic documentationonly and ... internationalization both
    #     cleared a 16-character floor and were truncated in full. A base64 encoding
    #     of any real credential essentially always carries a digit; prose does not.
    #     Declared residual: an all-letter base64 payload (roughly 0.4% of 24-char
    #     encodings) is missed. A multiple-of-four rule was tried FIRST and rejected
    #     on measurement -- it scored 1/3 on guilt, because padding is not counted by
    #     the group, and it still let internationalization through at 20 characters.
    #     NO [A-Za-z-]* PREFIX. It was there to admit Proxy-Authorization, and it
    #     cost EIGHTEEN SECONDS on a 50KB command with no credential in it -- an
    #     unbounded character class in front of a literal makes the engine retry
    #     from every position of a long run, which is the SAME trap already cured
    #     once in this file on the URL scheme, reintroduced four commits later in a
    #     different rule. The prefix is unnecessary: Proxy-Authorization: CONTAINS
    #     Authorization:, so the bare literal matches it anyway, and the cut starts
    #     at the match so Proxy- survives in the log. 18027 ms -> 1.36 ms, same 3/3
    #     guilt and same 0 false positives. Measured, not reasoned: the corpus now
    #     carries a WALL-CLOCK case, because two occurrences of one trap means
    #     comments do not hold it.
    r"(?i)Authorization:\s*Basic\s+(?=[A-Za-z0-9+/=]{16,})[A-Za-z0-9+/=]*[0-9+/=][A-Za-z0-9+/=]*",
    # 4. Bearer, which carries no keyword in a NAME at all. The left \b and the
    #    8-char floor are what keep flagbearer and Bearer abc innocent.
    #     The class carries the FULL base64 alphabet (+ / = ~), not just base64url:
    #     a standard-base64 token containing a plus stopped the match dead, so
    #     Bearer ab+cdefgh went through in the clear. Widening costs no innocence --
    #     prose does not contain + or / mid-word -- and closes a real recall gap.
    r"(?i)\b(?:Bearer)\s+[A-Za-z0-9._~+/=-]{8,}",
    # 2. Anything ASSIGNED to a credential-ish NAME.
    # The \\* before the optional quote is NOT decoration: a JSON body written
    # inside a double-quoted shell arg reaches this hook as api_key\": <v>, so the
    # separator is preceded by a BACKSLASH-escaped quote. Without it NO anchor fires
    # at all and the line is logged unchanged, byte for byte -- measured. That is a
    # DIFFERENT disease from the five tail directions above: those leaked a value
    # BEHIND a recognised anchor, this one fails to RECOGNISE the anchor. The
    # earliest-anchor cut cannot help where nothing anchors, so anchor RECALL is its
    # own obligation and does not follow from the cut being sound.
    # It is \\* and NOT \\?, and the difference is a finding not a preference: a
    # remote dispatch nests its quoting, so ssh host "bash -c \\"curl -d ...\\"" reaches
    # this hook with TWO or THREE literal backslashes before the quote. A refuter on a
    # fresh context broke the \\? version within the hour by adding one nesting level --
    # the point-patch reproducing the very enumeration trap the block above renounces.
    # \\* answers the depth, not one more enumerated depth.
    r"(?i)" + NAME + r"\\*[\"\x27]?\s*[=:]\s*" + VALUE,
)
_starts = [m.start() for m in (re.search(p, s) for p in ANCHORS) if m]
if _starts:
    s = s[:min(_starts)] + "<REDACTED>"
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
