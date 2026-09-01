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
# BYTE SEMANTICS, NOT LOCALE SEMANTICS. The verdict guard below asks awk whether a field is
# the literal string "OK". Under a UTF-8 locale, BWK awk compares by COLLATION, and a
# zero-width character (U+200B, U+FEFF) collates EQUAL to nothing -- so "OK"+U+200B passes a
# guard written as $8!="OK" while a human reading the baseline sees an ordinary OK. An
# invisible character must never be able to forge a review verdict, so every comparison in
# this script is made byte-exact.
export LC_ALL=C

# THE FILESYSTEM IS A COORDINATE, not an environment detail -- learned the hard way, in CI.
# The rename_case_only axis measures a defect that EXISTS ONLY where the filesystem folds
# case: on a case-SENSITIVE volume, Subject.md -> subject.md is an ordinary rename between two
# distinct paths, so those cells measure a different phenomenon and their reviewed verdicts do
# not describe it. Pro, Mini and M5 are all APFS (folding); GitHub's runners are not. The
# first CI run of this instrument therefore went red on 14 cells while the same command was
# green on every machine in the fleet -- the baseline was right, and so was the runner. The
# cure is to record which filesystem a run measured on and compare only what that filesystem
# can express, never to bake one volume's answers into a file the other must match.
# Probed in mktemp's directory because that is where the fixtures are actually built.
# Probed with the SAME construction run_cell uses for $SANDBOX -- an explicit /tmp template,
# never a bare `mktemp -d`. A refuter measured that on stock macOS the bare form lands in
# /var/folders while the sandbox lands in /tmp, that the two are the same device TODAY, and
# that nothing anywhere checked it: the congruence was coincidental. The failure it hides is
# the bad direction -- probe reports case-sensitive, fixtures build case-folding, and the axis
# is silently dropped where it would in fact have worked. Same construction, same filesystem,
# by construction rather than by luck.
#
# Three outcomes, not two: a probe that could not RUN is not a case-sensitive filesystem.
# Collapsing them made an unwritable /tmp print "filesystem: case-SENSITIVE" with total
# confidence and drop the axis for a reason that was never measured.
#   0 = folds case   1 = does not fold   2 = could not measure
fs_folds_case() {
  local d
  d="$(mktemp -d /tmp/pgp-casefold-XXXXXX)" || return 2
  : > "$d/CaseFoldProbe" 2>/dev/null || { rm -rf "$d"; return 2; }
  [ -e "$d/CaseFoldProbe" ] || { rm -rf "$d"; return 2; }
  if [ -e "$d/casefoldprobe" ]; then rm -rf "$d"; return 0; fi
  rm -rf "$d"; return 1
}
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

# The path every cell is built around, and the target the `symlink` local state points at.
# ($SIBLING was described here as "a second path that keeps the parent dir alive" -- true when
# $P sat in a subdirectory, and stale since it moved to the repo root.) Read the role precisely:
# the `symlink` arm does NOT reference $SIBLING by name, it hardcodes the same literal string,
# so grepping for the identifier under-reports how load-bearing this path is. Its existence IS
# asserted -- delete it and the symlink state goes dangling and trips assert_local_state -- but
# its CONTENT is not, and for `ordinary` cells nothing downstream would notice wrong bytes here.
# Root-level and capitalised: the case-only axis renames Subject.md -> subject.md, and on a
# case-insensitive filesystem the DIRECTION decides which spelling the resolver meets first.
# The body is deliberately long: git only PAIRS a rename above a similarity threshold, and a
# five-byte file is reported as delete+add, which is a different cell entirely.
P="Subject.md"
SIBLING="area/bystander.md"
BODY="body long enough for git to pair this as a rename rather than a delete plus an add"

fatal() { echo "FATAL fixture ($CELL): $1" >&2; exit 3; }

# EXPECTED CONTENT, as blob hashes derived from the fixture's own constants -- because two
# independent reviewers, working separately, found the same hole one level below the last fix:
# the assertions verified an object's SHAPE (mode and type) and never its CONTENT.
#   * `modify` with wrong bytes that merely share the real 14-byte prefix reproduced a full
#     MATRIX STABLE across all 16 of its cells -- and "ORIGIN-V2 body" IS that prefix, so
#     preserving it costs a saboteur nothing. `outcome` samples head -c 14 and sees nothing.
#   * `rename_away`'s destination could hold entirely unrelated content, never moved at all,
#     and no probe fired -- while that arm's whole point, stated in its own comment, is that
#     the content is BYTE-IDENTICAL so git pairs it as R100. The one property that makes the
#     cell a rename was the one property nothing checked.
#   * a tree at the removed path could hold the wrong file, or an extra one beside it.
# One cure closes all of them, and it is this spec's own design rule applied a level deeper:
# assert the OBJECT, not its silhouette.
H_BASE="$(printf '%s\n' "$BODY" | git hash-object --stdin)"          # the base blob at $P
H_V2="$(printf 'ORIGIN-V2 %s\n' "$BODY" | git hash-object --stdin)"  # what `modify` writes
H_PANEL="$(printf 'panel\n' | git hash-object --stdin)"              # the file inside a tree
H_LINK="$(printf 'bystander.md' | git hash-object --stdin)"           # a symlink blob IS its target

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
  local wt src dst low inner nsub
  wt="$1"
  # THREE probes, not one. The first version asked a single question -- what stands at $P --
  # and `delete`, `rename_away` and `rename_case_only` all answer it identically ("nothing"),
  # while `tree_at_path` and `rename_away_and_tree` both answer "a tree". Two independent
  # reviewers found the same consequence: an arm that DEGENERATES into its neighbour passes.
  # One of them carried it further and showed the whole instrument can go silent -- sabotage
  # `rename_away` into a plain delete, then align the baseline to the values a human would
  # plausibly re-measure, and the run reports MATRIX STABLE, exit 0. Assertion blind AND
  # comparator blind. The cure is the same one the A axis needed: give every action a UNIQUE
  # signature, so no arm can wear another's clothes. Source, destination, and the lowercase
  # spelling are read separately and all three are asserted, including their ABSENCE.
  src="$(git -C "$wt" ls-tree HEAD -- "$P"                | awk '{print $1" "$2" "$3}')"
  dst="$(git -C "$wt" ls-tree HEAD -- "moved/subject.md"  | awk '{print $1" "$2" "$3}')"
  low="$(git -C "$wt" ls-tree HEAD -- "subject.md"        | awk '{print $1" "$2" "$3}')"
  # A FOURTH probe, for the one blind spot a reviewer found that BOTH the assertion and all
  # seven measured fields missed completely: the two tree-building arms are asserted to leave
  # "a tree at $P", and a tree holding the WRONG file satisfies that. Nothing downstream
  # notices -- the resolver's outcome for a directory does not depend on what is inside it --
  # so a fixture silently building an empty or misnamed tree would keep measuring, keep
  # matching the baseline, and keep certifying a cell that no longer exercises its own shape.
  inner="$(git -C "$wt" ls-tree HEAD -- "$P/panel.json"   | awk '{print $1" "$2" "$3}')"
  # ...and how many blobs live under $P in total, so a tree carrying an EXTRA file beside the
  # expected one cannot pass a probe that only asks about the expected one.
  nsub="$(git -C "$wt" ls-tree -r HEAD -- "$P" | wc -l | tr -d ' ')"
  # Why the two tree arms below compare only `${src% *}` and drop the tree's OWN sha: a tree
  # object's hash is a pure function of its sorted (mode, name, blob) entry list, and `inner`
  # (exact path, exact mode+type+hash) plus `nsub` (exactly one blob anywhere beneath) admit
  # exactly one such list. Checking both IS checking the tree hash. THE CAVEAT, because it is
  # not general: this holds only while the arms build a FLAT single-file tree. Nest content a
  # level deeper and `nsub` no longer pins WHERE the blob sits relative to `inner`'s one
  # checked path, and the equivalence has to be re-derived or the tree sha pinned directly.
  case "$2" in
    modify)               [ "$src" = "100644 blob $H_V2" ] && [ -z "$dst" ] && [ -z "$low" ] \
                          && [ -z "$inner" ] && [ "$nsub" = 1 ] ;;
    delete)               [ -z "$src" ] && [ -z "$dst" ] && [ -z "$low" ] \
                          && [ -z "$inner" ] && [ "$nsub" = 0 ] ;;
    rename_away)          [ -z "$src" ] && [ "$dst" = "100644 blob $H_BASE" ] && [ -z "$low" ] \
                          && [ -z "$inner" ] && [ "$nsub" = 0 ] ;;
    rename_away_and_tree) [ "${src% *}" = "040000 tree" ] && [ "$dst" = "100644 blob $H_BASE" ] \
                          && [ -z "$low" ] && [ "$inner" = "100644 blob $H_PANEL" ] && [ "$nsub" = 1 ] ;;
    rename_case_only)     [ -z "$src" ] && [ -z "$dst" ] && [ "$low" = "100644 blob $H_BASE" ] \
                          && [ -z "$inner" ] && [ "$nsub" = 0 ] ;;
    tree_at_path)         [ "${src% *}" = "040000 tree" ] && [ -z "$dst" ] && [ -z "$low" ] \
                          && [ "$inner" = "100644 blob $H_PANEL" ] && [ "$nsub" = 1 ] ;;
    typechange)           [ "$src" = "120000 blob $H_LINK" ] && [ -z "$dst" ] && [ -z "$low" ] \
                          && [ -z "$inner" ] && [ "$nsub" = 1 ] ;;
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

# Drop the axis this filesystem cannot express, and say so loudly enough that a red run is
# never mistaken for one, nor a green one read as covering more than it did.
SKIP_ACTIONS=""
fs_folds_case; FS_RC=$?
case "$FS_RC" in
  0) echo "filesystem: case-FOLDING — all $(set -- $ORIGIN_ACTIONS; echo $#) origin actions in scope" ;;
  1) SKIP_ACTIONS="rename_case_only"
     ORIGIN_ACTIONS="$(echo "$ORIGIN_ACTIONS" | tr ' ' '\n' | grep -vx "rename_case_only" | tr '\n' ' ')"
     echo "filesystem: case-SENSITIVE — SKIPPING the rename_case_only axis (it measures a"
     echo "  case-folding defect that cannot occur here; its baseline verdicts do not apply)." ;;
  *) echo "FATAL: the case-folding probe could not run (mktemp or /tmp unwritable)." >&2
     echo "  Refusing to guess: an unmeasurable filesystem is not a case-sensitive one, and" >&2
     echo "  guessing drops the one axis that pins a regression already on record." >&2
     exit 3 ;;
esac

MEASURED="$(mktemp)"
for a in $LOCAL_STATES; do for b in $ORIGIN_ACTIONS; do for c in $ALLOWLIST; do
  run_cell "$a" "$b" "$c"
done; done; done
sort -o "$MEASURED" "$MEASURED"

if [ "$WRITE" = 1 ]; then
  # A baseline written where an axis is out of scope would silently DELETE those reviewed rows
  # -- fourteen human verdicts, gone, with the file still looking complete. Refuse: the
  # baseline is only ever authored where the whole matrix is constructible.
  if [ -n "$SKIP_ACTIONS" ]; then
    echo "REFUSING to write the baseline on a case-SENSITIVE filesystem: the $SKIP_ACTIONS" >&2
    echo "  axis is out of scope here, and writing would drop its reviewed rows. Author the" >&2
    echo "  baseline on a case-folding volume (any Mac in this fleet)." >&2
    rm -f "$MEASURED"; exit 3
  fi
  # NEVER blind-copy. $MEASURED holds seven MEASURED fields; the eighth is a human VERDICT the
  # machine cannot produce. A `cp` here destroys every judgement in the file, and because the
  # comparator only diffs fields 1-7 it then reports STABLE forever against a baseline nobody
  # has ever reviewed -- the exact guarantee this instrument exists to give, with a hole in it.
  # So: carry each cell's verdict forward by its coordinate key when its MEASUREMENT is
  # unchanged, and stamp anything new or moved UNREVIEWED, which the comparator refuses.
  prior_rows=0
  [ -f "$BASELINE" ] && prior_rows=$(wc -l < "$BASELINE" | tr -d ' ')
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
  if [ "$prior_rows" -gt 0 ] && [ "$(wc -l < "$BASELINE" | tr -d ' ')" -lt "$prior_rows" ]; then
    echo "NOTE: the baseline SHRANK ($prior_rows -> $(wc -l < "$BASELINE" | tr -d ' ') cells)."
    echo "  Cells that stopped being enumerated took their reviewed verdicts with them."
  fi
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
# The count is printed AFTER the comparison set is built, and carries the held-out figure on
# the SAME line: it used to print "88 vs 102" several lines above its own explanation, so
# anything reading one line -- a summary bot, a skim -- saw an unexplained gap.
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
# KNOWN_BAD without a reason is not a judgement, it is a silencer: it tells a future reader
# that someone looked and decided nothing. The reason column is what makes a declared defect
# auditable, so require it wherever the verdict claims one.
#
# AND THE SAME DEMAND ON THE OTHER SIDE, which is where this guard was originally wrong. A
# KNOWN_BAD nobody argued is merely pessimistic; an OK nobody argued is a defect blessed in
# writing, and the instrument then certifies it forever. Measured 2026-09-01: an independent
# audit of the human half found 46 of 102 rows carried an unargued OK, and TWO of them were
# false — `modified x tree_at_path x keeplocal` was reproduced against the real puller losing
# Pro-authoritative content into a nested path while the log said `restored kept-local`.
# So an OK must also be argued wherever it is a CLAIM rather than an observation: content was
# set aside (`backup=file`) AND the tracked path did not come back a regular file. In that
# shape "this is fine" asserts that Pro's content is somewhere recoverable and that a consumer
# reading the path can cope with what it found — neither of which any measured field shows.
unjudged=$(awk -F'\t' '
  NF<8 || ($8!="OK" && $8!="KNOWN_BAD") ||
  ($8=="KNOWN_BAD" && (NF<9 || $9 ~ /^[ \t]*$/)) ||
  ($8=="OK" && $7=="backup=file" && $6 !~ /^file:/ && (NF<9 || $9 ~ /^[ \t]*$/))' "$BASELINE" | wc -l | tr -d ' ')
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
# Compare like with like: on a filesystem that skipped an axis, the baseline's rows for that
# axis describe behaviour this run never measured and are held out rather than counted absent.
if [ -n "$SKIP_ACTIONS" ]; then
  awk -F'\t' -v OFS='\t' -v skip="$SKIP_ACTIONS" \
    '$2!=skip {print $1,$2,$3,$4,$5,$6,$7}' "$BASELINE" > "$BASELINE.cmp"
  held=$(awk -F'\t' -v s="$SKIP_ACTIONS" '$2==s' "$BASELINE" | wc -l | tr -d ' ')
  echo "cells measured: $(wc -l < "$MEASURED" | tr -d ' ')  baseline: $(wc -l < "$BASELINE" | tr -d ' ') minus $held held out on the $SKIP_ACTIONS axis (this filesystem cannot express it)"
else
  cut -f1-7 "$BASELINE" > "$BASELINE.cmp"
  echo "cells measured: $(wc -l < "$MEASURED" | tr -d ' ')  baseline: $(wc -l < "$BASELINE" | tr -d ' ')"
fi
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
