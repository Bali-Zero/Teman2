#!/usr/bin/env bash
# install_skill_symlinks.sh — cable the repo skill SOURCE as the loaded skill,
# per-file, leaving runtime/artifact files physical in HOME (superscar #1 cure).
#
# WHY per-file (not a full-dir symlink): the live skill READS/WRITES runtime data
# that is intentionally NOT in the repo — past/ (45M carousels), _observations/,
# _carousels-by-session/, _reflexion-state.json, _proposed-amendments/. A full-dir
# symlink HOME->repo would make those vanish and break the running pipeline. So we
# symlink ONLY the git-tracked source files; everything else stays a real HOME file.
#
# SOURCE OF TRUTH = `git ls-files skills/<name>/`. A file tracked in git IS source.
# Anything present only in HOME (artifacts, runtime state) is left untouched.
#
# IDEMPOTENT: re-running reconciles — adds symlinks for newly-tracked files, fixes
# wrong targets, leaves correct ones. Safe to run after every `git pull`.
#
# PATH-AWARE: repo root from `git rev-parse`, HOME from $HOME (M5=balizero,
# Pro/Mini=nuzantara — never hardcode the user).
#
# Default is DRY-RUN. Pass --apply to act. Pass --skill <name> to target one skill
# (default: bali-zero-brand).
#
# Reverse: --restore copies the repo content back to physical HOME files (undo).

set -euo pipefail

SKILL="bali-zero-brand"
APPLY=0
RESTORE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --restore) RESTORE=1; shift ;;
    --skill) SKILL="$2"; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
REPO_SKILL_DIR="$REPO_ROOT/skills/$SKILL"
HOME_SKILL_DIR="$HOME/.claude/skills/$SKILL"

if [[ ! -d "$REPO_SKILL_DIR" ]]; then
  echo "ERROR: repo skill dir not found: $REPO_SKILL_DIR" >&2
  exit 1
fi

# The git-tracked file list = the source manifest (paths relative to REPO_SKILL_DIR).
# (while-read loop, not `mapfile` — macOS ships bash 3.2 which lacks mapfile.)
SRC_FILES=()
while IFS= read -r _f; do
  [[ -n "$_f" ]] && SRC_FILES+=("$_f")
done < <(git -C "$REPO_ROOT" ls-files "skills/$SKILL/" | sed "s#^skills/$SKILL/##")

if [[ ${#SRC_FILES[@]} -eq 0 ]]; then
  echo "ERROR: no git-tracked files under skills/$SKILL/ — nothing to link" >&2
  exit 1
fi

echo "repo source : $REPO_SKILL_DIR"
echo "home target : $HOME_SKILL_DIR"
echo "source files: ${#SRC_FILES[@]} (git-tracked)"
echo "mode        : $([[ $RESTORE -eq 1 ]] && echo RESTORE || echo SYMLINK) / $([[ $APPLY -eq 1 ]] && echo APPLY || echo DRY-RUN)"
echo "------------------------------------------------------------"

linked=0 fixed=0 skipped=0 backed_up=0 restored=0

mkact() { [[ $APPLY -eq 1 ]] && eval "$1" || true; }

for rel in "${SRC_FILES[@]}"; do
  src="$REPO_SKILL_DIR/$rel"
  dst="$HOME_SKILL_DIR/$rel"
  dst_dir="$(dirname "$dst")"

  if [[ $RESTORE -eq 1 ]]; then
    # Undo: replace symlink (or absent) with a physical copy from the repo.
    if [[ -L "$dst" ]]; then
      echo "RESTORE  $rel  (symlink -> physical copy)"
      mkact "mkdir -p '$dst_dir'"
      mkact "rm -f '$dst' && cp '$src' '$dst'"
      restored=$((restored+1))
    fi
    continue
  fi

  # SYMLINK mode
  mkact "mkdir -p '$dst_dir'"

  if [[ -L "$dst" ]]; then
    cur="$(readlink "$dst")"
    if [[ "$cur" == "$src" ]]; then
      skipped=$((skipped+1)); continue
    fi
    echo "FIX      $rel  (wrong target: $cur)"
    mkact "ln -sf '$src' '$dst'"
    fixed=$((fixed+1))
  elif [[ -e "$dst" ]]; then
    # A physical HOME file (old copy) shadows the source -> back up, then link.
    echo "REPLACE  $rel  (physical HOME file -> backup + symlink)"
    mkact "mv '$dst' '$dst.pre-symlink-bak'"
    mkact "ln -s '$src' '$dst'"
    backed_up=$((backed_up+1)); linked=$((linked+1))
  else
    echo "LINK     $rel"
    mkact "ln -s '$src' '$dst'"
    linked=$((linked+1))
  fi
done

echo "------------------------------------------------------------"
if [[ $RESTORE -eq 1 ]]; then
  echo "restored=$restored"
else
  echo "linked=$linked fixed=$fixed replaced(backup)=$backed_up already-ok=$skipped"
fi
[[ $APPLY -eq 0 ]] && echo "(dry-run — re-run with --apply to act)"
echo "runtime data left untouched (past/ _observations/ _carousels-by-session/ _reflexion-state.json + any non-tracked file)"
