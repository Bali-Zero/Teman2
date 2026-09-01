#!/bin/bash
# SPEC — the collision matrix for scripts/pro/pro-git-pull.sh.
#
# WHY THIS EXISTS. Three consecutive adversarial passes over the `--no-renames` change each
# found "the shape nobody asked about" on this one surface (PR #5492: a removed path the tree
# had already deleted; PR #5496 review: the same guard's removal test resolving a TREE and
# declining to fire). Each was cured by a one-token patch derived from that finding, and each
# patch was itself wrong about a neighbouring cell. That is the builder contract's definition
# of an UNDER-SPECIFIED surface, and its instruction is to write the spec instead of opening
# the third patch.
#
# WHAT A CELL IS. resolve_collisions() decides, per incoming path, between four outcomes. What
# it decides on is a triple, and the whole family of defects has been the same mistake: reading
# ONE coordinate and inferring the other two.
#
#   A  what the LOCAL worktree holds at that path
#   B  what the INCOMING change does to that path
#   C  whether the path is allowlisted Pro-authoritative runtime state
#
# THE DESIGN RULE THE MATRIX ENFORCES, stated once so no future patch has to re-derive it:
# classify B by the TYPE of the object at "$REMOTE:$f" -- blob, tree, or absent -- never by
# its EXISTENCE. `git cat-file -e` answers "is there any object here", so a directory created
# at a removed file's name answers YES and every existence-based guard silently declines.
#
# HOW TO READ A RUN. Every cell prints its measured outcome and is diffed against
# collision-matrix-baseline.tsv, which records the outcome AND a verdict: OK where the
# behaviour is correct, KNOWN_BAD where it is not, with the reason. A cell that MOVES in
# either direction is a failure -- including a KNOWN_BAD that silently becomes OK, because an
# undeclared improvement is an unreviewed behaviour change.
#
# Run:  bash scripts/pro/spec_collision_matrix.sh [--puller PATH] [--write-baseline]

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PULLER="$SCRIPT_DIR/pro-git-pull.sh"
BASELINE="$SCRIPT_DIR/collision-matrix-baseline.tsv"
WRITE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --puller) PULLER="$2"; shift 2 ;;
    --baseline) BASELINE="$2"; shift 2 ;;
    --write-baseline) WRITE=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[ -f "$PULLER" ] || { echo "FATAL: puller not found: $PULLER" >&2; exit 3; }

# The path every cell is built around, and a second path that keeps the parent dir alive.
# Root-level and capitalised: the case-only axis renames Subject.md -> subject.md, and on a
# case-insensitive filesystem the DIRECTION decides which spelling the resolver meets first.
# The body is deliberately long: git only PAIRS a rename above a similarity threshold, and a
# five-byte file is reported as delete+add, which is a different cell entirely.
P="Subject.md"
SIBLING="area/bystander.md"
BODY="body long enough for git to pair this as a rename rather than a delete plus an add"

fatal() { echo "FATAL fixture ($CELL): $1" >&2; exit 3; }

# ---- fixture construction ---------------------------------------------------------------
# build_origin_action: mutate a scratch clone of origin, push. Echoes UNCONSTRUCTIBLE and
# returns 1 for a combination git cannot express.
build_origin_action() {
  local action="$1" tmp; tmp="$(mktemp -d)" || fatal "mktemp origin"
  git clone -q "$ORIGIN" "$tmp/w" 2>/dev/null; [ -f "$tmp/w/.git/HEAD" ] || fatal "origin clone"
  git -C "$tmp/w" config user.email t@t; git -C "$tmp/w" config user.name t
  case "$action" in
    modify)       # doubles as ADD when the base never tracked P (the untracked row)
                  mkdir -p "$tmp/w/$(dirname "$P")"
                  printf 'ORIGIN-V2 %s\n' "$BODY" > "$tmp/w/$P"; git -C "$tmp/w" add "$P" ;;
    delete)       git -C "$tmp/w" rm -q "$P" ;;
    rename_away)  mkdir -p "$tmp/w/moved"; git -C "$tmp/w" mv "$P" "moved/subject.md" ;;
    tree_at_path) # the shape the existence-based guard cannot see: a DIRECTORY takes the name.
                  # `git rm` only when the base actually tracked P -- on the untracked row it
                  # never did, and an unguarded `git rm` there fails the fixture and would have
                  # recorded a cell that never ran.
                  git -C "$tmp/w" ls-files --error-unmatch -- "$P" >/dev/null 2>&1 \
                    && git -C "$tmp/w" rm -q "$P"
                  mkdir -p "$tmp/w/$P"; printf 'panel\n' > "$tmp/w/$P/panel.json"
                  git -C "$tmp/w" add "$P/panel.json" ;;
    rename_away_and_tree)
                  # THE CELL THAT CLOSED PR #5496. Content is moved BYTE-IDENTICAL so git pairs
                  # it as R100, and a directory then takes the vacated name. Rename detection
                  # hides the source; --no-renames reveals it; and an EXISTENCE-based removal
                  # test resolves the TREE and declines to fire. Three coordinates, one cell.
                  mkdir -p "$tmp/w/moved"; git -C "$tmp/w" mv "$P" "moved/subject.md"
                  mkdir -p "$tmp/w/$P"; printf 'panel\n' > "$tmp/w/$P/panel.json"
                  git -C "$tmp/w" add "$P/panel.json" ;;
    rename_case_only)
                  # THE SECOND REGRESSION, found 2026-09-01 while chasing the gap list. On a
                  # case-INSENSITIVE filesystem (APFS, and this repo lives on one) --no-renames
                  # puts BOTH spellings of a case-only rename into the same tick. The old
                  # spelling is not in the index, so it takes the untracked arm, where
                  # `[ -e "$REPO/$f" ]` is TRUE because it matches the file just restored under
                  # the NEW spelling -- and `mv -n` into $BACKUP_ROOT then declines, because the
                  # backup directory inherits the same case-insensitivity and the destination
                  # already exists. Not hypothetical: qwen.md -> QWEN.md landed on main in #5371.
                  git -C "$tmp/w" mv -f "$P" "subject.md" ;;
    typechange)   git -C "$tmp/w" rm -q "$P"
                  ln -s "bystander.md" "$tmp/w/$P"; git -C "$tmp/w" add "$P" ;;
    *) rm -rf "$tmp"; echo "UNCONSTRUCTIBLE"; return 1 ;;
  esac
  git -C "$tmp/w" commit -qm "origin: $action" >/dev/null || fatal "origin commit $action"
  assert_origin_action "$tmp/w" "$action" \
    || fatal "incoming action '$action' did not produce what its label claims at $P"
  git -C "$tmp/w" push -q origin HEAD:main || fatal "origin push $action"
  rm -rf "$tmp"; return 0
}

# assert_local_state: the POST-CONDITION. A fixture arm that fails silently does not skip the
# cell -- it records a row LABELLED one state while MEASURING another, and `del_staged` degrades
# into exactly `del_unstaged`, whose cells carry the opposite verdict. So every arm is checked
# against the disk before the puller is allowed to run, and a mismatch aborts the whole run
# rather than publishing a mislabelled row.
assert_local_state() {
  local tracked=no exists=no
  git -C "$LOCAL" ls-files --error-unmatch -- "$P" >/dev/null 2>&1 && tracked=yes
  { [ -e "$LOCAL/$P" ] || [ -L "$LOCAL/$P" ]; } && exists=yes
  case "$1" in
    clean)            [ "$tracked" = yes ] && [ "$exists" = yes ] && git -C "$LOCAL" diff --quiet HEAD -- "$P" ;;
    # `modified` must say REGULAR FILE, not merely "tracked and different". An empirical 8x8
    # confusion matrix over these predicates found this one arm matching three OTHER states'
    # real on-disk shapes: dir_at_path, dangling_symlink and symlink all leave `tracked` yes
    # (their arms run no git add/rm), satisfy `-e`/`-L`, and are never `diff --quiet` because
    # the TYPE changed. Unreachable today — run_cell always passes the same $A to apply and
    # assert — so this masked nothing; a post-condition that cannot tell four states apart is
    # still not a post-condition, and the next refactor of the dispatch is what it would cost.
    modified)         [ "$tracked" = yes ] && [ -f "$LOCAL/$P" ] && [ ! -L "$LOCAL/$P" ] \
                        && ! git -C "$LOCAL" diff --quiet HEAD -- "$P" ;;
    del_unstaged)     [ "$tracked" = yes ] && [ "$exists" = no ] ;;
    del_staged)       [ "$tracked" = no ]  && [ "$exists" = no ] ;;
    dir_at_path)      [ -d "$LOCAL/$P" ] && [ ! -L "$LOCAL/$P" ] ;;
    dangling_symlink) [ -L "$LOCAL/$P" ] && [ ! -e "$LOCAL/$P" ] ;;
    symlink)          [ -L "$LOCAL/$P" ] && [ -e "$LOCAL/$P" ] ;;
    untracked)        [ "$tracked" = no ] && [ -f "$LOCAL/$P" ] && [ ! -L "$LOCAL/$P" ] ;;
    *) return 1 ;;
  esac
}

# assert_origin_action: the POST-CONDITION for the B axis, symmetric with assert_local_state.
# `build_origin_action`'s only safety net was its trailing `git commit || fatal`, which catches
# "nothing changed" but NOT a partial or wrong change that still leaves something to commit --
# the same masking class as the `del_staged` arm, on the other axis. So read back what actually
# stands at $P in the pushed origin, by MODE and TYPE, and refuse to measure a cell whose
# incoming side is not what its label says. Note git's object store is case-SENSITIVE even when
# the filesystem is not, which is what makes the case-only assertion meaningful.
assert_origin_action() {
  local wt ent
  wt="$1"
  ent="$(git -C "$wt" ls-tree HEAD -- "$P" 2>/dev/null | awk '{print $1" "$2}')"
  case "$2" in
    modify)                              [ "$ent" = "100644 blob" ] ;;
    delete|rename_away|rename_case_only) [ -z "$ent" ] ;;
    rename_away_and_tree|tree_at_path)   [ "$ent" = "040000 tree" ] ;;
    typechange)                          [ "$ent" = "120000 blob" ] ;;
    *) return 1 ;;
  esac
}

# apply_local_state: put the local worktree into state A at $P.
apply_local_state() {
  case "$1" in
    clean)            : ;;                                   # tracked, untouched
    modified)         printf 'PRO-LOCAL-EDIT %s\n' "$BODY" > "$LOCAL/$P" ;;
    del_unstaged)     rm "$LOCAL/$P" ;;                       # index still holds it
    del_staged)       git -C "$LOCAL" rm -q --cached "$P" >/dev/null 2>&1 && rm -f "$LOCAL/$P" ;;
    dir_at_path)      rm "$LOCAL/$P" && mkdir -p "$LOCAL/$P" && printf 'x\n' > "$LOCAL/$P/inner" ;;
    dangling_symlink) rm "$LOCAL/$P" && ln -s "/nonexistent/target" "$LOCAL/$P" ;;
    symlink)          # a VALID symlink, distinct from the dangling one: it does not wedge, but
                      # `cp -p` DEREFERENCES it into the backup, so recovery hands back another
                      # file's bytes under this name with no record it was ever a link.
                      rm "$LOCAL/$P" && ln -s "area/bystander.md" "$LOCAL/$P" ;;
    untracked)        printf 'UNTRACKED-LOCAL\n' > "$LOCAL/$P" ;;   # base never tracked it
    *) return 1 ;;
  esac
}

# ---- one cell ----------------------------------------------------------------------------
run_cell() {
  local A="$1" B="$2" C="$3"
  CELL="$A|$B|$C"
  # constructibility: an untracked local file only meets an incoming CREATE.
  if [ "$A" = untracked ] && [ "$B" != modify ] && [ "$B" != tree_at_path ]; then return 0; fi
  SANDBOX="$(mktemp -d "/tmp/pgp-matrix-XXXXXX")" || fatal "mktemp sandbox"
  ORIGIN="$SANDBOX/origin.git"; LOCAL="$SANDBOX/local"
  git init -q --bare "$ORIGIN" || fatal "init bare"
  git -C "$ORIGIN" symbolic-ref HEAD refs/heads/main || fatal "symref"
  git clone -q "$ORIGIN" "$LOCAL" 2>/dev/null; [ -f "$LOCAL/.git/HEAD" ] || fatal "clone"
  git -C "$LOCAL" config user.email t@t; git -C "$LOCAL" config user.name t
  mkdir -p "$LOCAL/area"
  # An UNTRACKED local file can only collide with a path the incoming change CREATES, so for
  # that row the base must not contain P at all. Pairing it with delete/rename/typechange of a
  # path that never existed is not a cell git can express -- the first run of this matrix
  # reported rc=1 for all ten of them, which was the fixture committing a local removal and
  # diverging HEAD, not the puller refusing anything. A row that is uniformly red is a claim
  # about the fixture until proven otherwise.
  if [ "$1" != untracked ]; then printf '%s\n' "$BODY" > "$LOCAL/$P"; fi
  printf 'bystander\n' > "$LOCAL/$SIBLING"
  echo base > "$LOCAL/README.md"
  git -C "$LOCAL" add -A && git -C "$LOCAL" commit -qm base >/dev/null || fatal "base commit"
  git -C "$LOCAL" push -q origin HEAD:main || fatal "base push"

  if ! build_origin_action "$B" >/dev/null; then rm -rf "$SANDBOX"; return 0; fi
  apply_local_state "$A" || fatal "local-state arm '$A' failed"
  assert_local_state "$A" || fatal "local state '$A' is NOT what is on disk — the row would be mislabelled"

  local allow="$SANDBOX/allow.json"
  if [ "$C" = keeplocal ]; then
    printf '{"entries":[{"path":"%s","machines":["pro"]}]}\n' "$P" > "$allow"
  else
    printf '{"entries":[]}\n' > "$allow"
  fi

  git -C "$LOCAL" fetch -q origin main 2>/dev/null
  local before; before="$(git -C "$LOCAL" rev-parse HEAD)"
  PRO_GIT_PULL_REPO="$LOCAL" PRO_GIT_PULL_LOG="$SANDBOX/pull.log" \
  PRO_GIT_PULL_LOCK="$SANDBOX/lock.d" PRO_GIT_PULL_BACKUP_ROOT="$SANDBOX/backup" \
  PRO_GIT_PULL_ALLOWLIST="$allow" PRO_GIT_PULL_NO_ALERT=1 \
    bash "$PULLER" >/dev/null 2>&1
  local rc=$?
  local after moved outcome
  after="$(git -C "$LOCAL" rev-parse HEAD)"
  [ "$before" != "$after" ] && moved=ff || moved=stuck
  # what survived where the local machine's content was
  local present
  present="$(ls -1 "$LOCAL/$(dirname "$P")" 2>/dev/null | grep -Fx "$(basename "$P")" || true)"
  if   [ -z "$present" ];                  then outcome=absent
  elif [ -d "$LOCAL/$P" ];                 then outcome=dir
  elif [ -L "$LOCAL/$P" ];                 then outcome=symlink
  else                                          outcome="file:$(head -c 14 "$LOCAL/$P" | tr -d '\n' | tr ' ' '_')"
  fi
  # `backup=` used to mean "the directory exists", which `mkdir -p` guarantees even when the
  # `cp` that follows fails -- so it read as "recoverable" on cells where nothing was saved.
  # Measure a FILE, and distinguish an empty backup dir from an absent one.
  local backed=no
  if [ -d "$SANDBOX/backup" ]; then
    if [ -n "$(find "$SANDBOX/backup" \( -type f -o -type l \) 2>/dev/null | head -1)" ]
      then backed=file; else backed=empty; fi
  fi
  printf '%s\t%s\t%s\trc=%s\t%s\t%s\tbackup=%s\n' "$A" "$B" "$C" "$rc" "$moved" "$outcome" "$backed" >> "$MEASURED"
  rm -rf "$SANDBOX"
}

LOCAL_STATES="clean modified del_unstaged del_staged dir_at_path dangling_symlink symlink untracked"
ORIGIN_ACTIONS="modify delete rename_away rename_away_and_tree rename_case_only tree_at_path typechange"
ALLOWLIST="ordinary keeplocal"

MEASURED="$(mktemp)"
for a in $LOCAL_STATES; do for b in $ORIGIN_ACTIONS; do for c in $ALLOWLIST; do
  run_cell "$a" "$b" "$c"
done; done; done
sort -o "$MEASURED" "$MEASURED"

if [ "$WRITE" = 1 ]; then
  # NEVER blind-copy. $MEASURED holds seven MEASURED fields; the eighth is a human VERDICT the
  # machine cannot produce. A `cp` here destroys every judgement in the file, and because the
  # comparator only diffs fields 1-7 it then reports STABLE forever against a baseline nobody
  # has ever reviewed -- the exact guarantee this instrument exists to give, with a hole in it.
  # So: carry each cell's verdict forward by its coordinate key when its MEASUREMENT is
  # unchanged, and stamp anything new or moved UNREVIEWED, which the comparator refuses.
  if [ -f "$BASELINE" ]; then
    awk -F'\t' -v OFS='\t' '
      NR==FNR { if (NF>7) { k=$1 FS $2 FS $3; m[k]=$4 FS $5 FS $6 FS $7; v[k]=substr($0, index($0,$8)) } ; next }
      { k=$1 FS $2 FS $3
        if (k in v && m[k]==($4 FS $5 FS $6 FS $7)) print $0, v[k]
        else print $0, "UNREVIEWED", "measurement is new or has MOVED — a human must judge this cell before the matrix can pass" }
    ' "$BASELINE" "$MEASURED" > "$BASELINE.new"
  else
    awk -F'\t' -v OFS='\t' '{print $0, "UNREVIEWED", "no prior baseline — every cell needs a first judgement"}' "$MEASURED" > "$BASELINE.new"
  fi
  mv "$BASELINE.new" "$BASELINE"
  carried=$(awk -F'\t' '$8!="UNREVIEWED"' "$BASELINE" | wc -l | tr -d ' ')
  todo=$(awk -F'\t' '$8=="UNREVIEWED"' "$BASELINE" | wc -l | tr -d ' ')
  echo "baseline written: $BASELINE ($(wc -l < "$BASELINE" | tr -d ' ') cells; $carried verdicts carried, $todo UNREVIEWED)"
  [ "$todo" -gt 0 ] && echo "REVIEW REQUIRED: $todo cell(s) marked UNREVIEWED — the matrix will FAIL until each is judged."
  rm -f "$MEASURED"; exit 0
fi
if [ ! -f "$BASELINE" ]; then
  echo "FATAL: no baseline at $BASELINE — run with --write-baseline once, then REVIEW every row." >&2
  cat "$MEASURED" >&2; rm -f "$MEASURED"; exit 3
fi
echo "cells measured: $(wc -l < "$MEASURED" | tr -d ' ')  baseline: $(wc -l < "$BASELINE" | tr -d ' ')"
# The baseline carries an 8th, human-written column: the VERDICT for that cell (OK, or
# KNOWN_BAD with a reason). The machine measures 7 fields and must never overwrite the
# judgement, so the comparison is on fields 1-7 only. A cell whose verdict is wrong is a
# review defect; a cell whose MEASUREMENT moved is what this script exists to catch.
# An unjudged baseline is not a baseline. Before comparing anything, require that every row
# carries a verdict a human wrote. The first version of this check asked whether column 8 was
# PRESENT — non-empty and not the literal UNREVIEWED — which is not the same question and let
# four shapes straight through, measured: whitespace-only, `MAYBE`, a lone `-`, and a stray
# comment. That is the original defect one layer up: "no verdict" was closed and "not a
# verdict" was left open. So the test is now an ALLOW-LIST of the two strings that mean
# something, which also subsumes empty and UNREVIEWED without naming them.
unjudged=$(awk -F'\t' 'NF<8 || ($8!="OK" && $8!="KNOWN_BAD")' "$BASELINE" | wc -l | tr -d ' ')
if [ "$unjudged" -gt 0 ]; then
  echo "BASELINE NOT REVIEWED — $unjudged of $(wc -l < "$BASELINE" | tr -d ' ') cells carry no usable verdict." >&2
  echo "  Column 8 must be exactly OK or KNOWN_BAD (the reason goes in column 9). A verdict this" >&2
  echo "  script wrote, an empty field, or anything else is not a judgement. Offending cells:" >&2
  awk -F'\t' 'NF<8 || ($8!="OK" && $8!="KNOWN_BAD") {print "    " $1 "|" $2 "|" $3 "   verdict=[" $8 "]"}' "$BASELINE" >&2
  rm -f "$MEASURED"; exit 2
fi
# Coordinate keys must be unique. Nothing enforced this, and the carry-forward awk keys on
# fields 1-3 — so two rows sharing a key would both inherit ONE verdict, and the second would
# be judged by a decision made about the first.
dupes=$(cut -f1-3 "$BASELINE" | sort | uniq -d)
if [ -n "$dupes" ]; then
  echo "BASELINE HAS DUPLICATE COORDINATE KEYS — a cell judged twice, or one verdict standing in for two:" >&2
  printf '    %s\n' "$dupes" | tr '\t' '|' >&2
  rm -f "$MEASURED"; exit 2
fi
cut -f1-7 "$BASELINE" > "$BASELINE.cmp"
if diff -u "$BASELINE.cmp" "$MEASURED" > "$MEASURED.diff"; then
  rm -f "$BASELINE.cmp"
  echo "MATRIX STABLE — every cell matches the reviewed baseline."
  rm -f "$MEASURED" "$MEASURED.diff"; exit 0
fi
rm -f "$BASELINE.cmp"
echo "MATRIX MOVED — a cell changed behaviour. Both directions are failures:"
echo "  a KNOWN_BAD that became OK is an unreviewed improvement; review it and rewrite the baseline."
sed -n '3,200p' "$MEASURED.diff"
rm -f "$MEASURED" "$MEASURED.diff"; exit 1
