#!/usr/bin/env python3
"""PreToolUse hook (Bash) — block dangerous git ops AND shell file-writes in main checkout.

L5.1 SOTA wave 2026-05-25. Closes Gap G1 (adoption enforcement) from
research/operations/2026-05-25-sota-workflow-gap-analysis-and-l5-spec.md.

Post-4-LLM-panel amendments (research/operations/specs/L5.1-panel-synthesis-2026-05-25.md):
- A1: Path canonicalization via os.path.realpath() + Path.is_relative_to()
- A3: Parse `git -C <path>` and `cd <path> && git` for effective target
- A4: Removed transcript marker bypass (env-only escape)
- A5: Probe-mode logging for empirical sub-agent inheritance test
- A6: Cached alive-agent count (zero subprocess on hot path)

W79 (§9-B of research/operations/specs/phase-aware-guardrails.md, 4-LLM panel
2026-06-13 Gemini 3.1 Pro + DeepSeek, verified on disk):
- B1: ALSO block shell file-WRITES into the main checkout via Bash (`> file`,
  `>> file`, `tee file`, `sed -i ... file`, `cp/mv ... dest`, `dd of=`). Closes the
  pre-existing hole: worktree_file_write_check covered only Edit/Write/MultiEdit tools,
  worktree_isolation covered only `git` — so `echo "x" > $REPO_ROOT/f.py` via Bash
  used to write the main checkout with NO hook stopping it.

W83 (over-match fix, 2026-06-16, superscar #3 guard-over-match): the BLOCKED_SUBCMD_RE
matched `git ... pull` ANYWHERE in the command string — including inside a quoted
literal (`grep "git pull"`) and inside a REMOTE `ssh host '... git pull ...'` payload
(a git op on ANOTHER machine, which never touches this checkout). The `cd <path> && git`
target-resolver also failed on the nested-quoting of an ssh payload, so the effective
target fell back to the LOCAL cwd → false BLOCK. Three live false-positives in one
session (remote `git pull` on the Pro x3). Fix, in order:
  1. Strip noise (heredocs + quoted strings) BEFORE the git scan too — a `git pull`
     inside quotes is text, not a command (reuses the W79 _strip_noise recipe).
  2. If the (noise-stripped) command is a REMOTE dispatch (`ssh`/`scp`/`rsync ... host:`),
     the git op runs off-box → ALLOW (this checkout is untouched). Innocence-tested:
     a LOCAL `git pull` must still block; only the ssh-wrapped one is exempt.

Blocked (only when effective target resolves INTO main checkout, NOT a worktree):
- git checkout / switch / stash / reset / merge / rebase / pull / commit -a / add -A / add .
- shell writes: `> file`, `>> file`, `tee file`, `sed -i ... file`, `cp/mv ... dest`, `dd of=`

Allow (defense conservative — a global L1 hook on 3 machines must NOT false-positive):
- git read-only; git -C <worktree>; git add <file>; git commit -m; git push
- ANY write whose target is a worktree, /tmp, $HOME outside the repo, or unclassifiable
- a git op carried by a remote ssh/scp/rsync dispatch (runs on another host) [W83]
- a git verb appearing only inside a quoted string / heredoc body (not a real command) [W83]

Escape: AGENT_WORKTREE_ENFORCEMENT=false (env var set in session, NOT inline cmd prefix).

Exit code 2 + stderr = block tool call.
Exit code 0 + no stderr = allow.

Reference cicatrix: 2026-04-29 #1+#2, W50/W51/W52, 32+ sibling-orphan-2026-05-25, W79, W83 (this).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

import subprocess as _sp


def _is_nuzantara_root(root: str) -> bool:
    """Repo signature: only the nuzantara checkout carries scripts/agent_start.py."""
    return os.path.isfile(os.path.join(root, "scripts", "agent_start.py"))


def _derive_repo_root() -> str:
    """Machine-agnostic main-checkout root (Pro /Users/nuzantara, M5 /Users/balizero).

    git-common-dir derivation is correct ONLY when cwd is inside the nuzantara
    repo. When the session cwd sits in a DIFFERENT git repo (e.g. ~/.claude),
    it would silently resolve there and disarm the brake. The signature guard
    rejects any derived root that lacks scripts/agent_start.py.
    """
    home_default = f"{os.path.expanduser('~')}/Desktop/nuzantara"
    # 1) honor explicit override
    _env = os.environ.get("NUZ_REPO_ROOT")
    if _env:
        return _env.rstrip("/")
    # 2) main checkout = parent of git common dir (only if it is the nuzantara repo)
    try:
        cd = _sp.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=os.getcwd(), capture_output=True, text=True, timeout=3,
        )
        if cd.returncode == 0 and cd.stdout.strip():
            common = cd.stdout.strip()
            root = common[:-5] if common.endswith("/.git") else os.path.dirname(common)
            if _is_nuzantara_root(root):
                return root
    except Exception:
        pass
    # 3) fallback to home-based guess (works on both machines)
    return home_default


REPO_ROOT = _derive_repo_root()

# Blocked git subcommands.
BLOCKED_SUBCMD_RE = re.compile(
    r"\bgit\s+(?:-c\s+\S+\s+)*"  # optional -c key=val flags
    r"(?:-C\s+\S+\s+)?"  # optional -C path
    r"(checkout|switch|stash|reset|merge|rebase|pull)\b"
    r"|\bgit\s+commit\s+(?:[^\s]+\s+)*(?:-[A-Za-z]*a|--all\b)"  # commit -a / -am / -a -m / --all
    r"|\bgit\s+add\s+(?:-A|-a|--all|\.)"  # add -A / add -a / add --all / add .
)

# Extract `git -C <path>` target.
GIT_C_RE = re.compile(r"\bgit\s+(?:-c\s+\S+\s+)*-C\s+(\S+)")

# Extract `cd <path> && git ...` target.
CD_GIT_RE = re.compile(r"\bcd\s+(\S+)\s*(?:&&|;)\s*git\b")

# W83: a remote dispatch carries the git op to ANOTHER host — this checkout is
# never touched. The dispatcher must be the FIRST real token of a command
# SEGMENT (start of line, or right after a segment separator && || ; |). This is
# deliberately strict: `echo ssh ... && git reset` must NOT be exempted just
# because the word "ssh" appears as an echo argument — only a segment that
# actually STARTS with ssh/scp/rsync carries work off-box. Anchoring to a
# segment boundary (not a bare word anywhere) is itself the superscar-#3
# antidote: match the command's intent, not a substring.
REMOTE_DISPATCH_RE = re.compile(r"(?:^|(?:&&|\|\||;|\|)\s*)\s*(?:ssh|scp|rsync)\b")

# --- W79 B1: shell file-WRITE detection ----------------------------------------
# Quick gate: does the command contain anything that could write a file?
WRITE_HINT_RE = re.compile(r"(>>?|\btee\b|\bsed\b[^|]*-i|\bdd\b[^|]*\bof=|\b(?:cp|mv|install)\b)")
# Extractors for write TARGETS. Each yields candidate destination path(s).
# Redirect:  ... > path   or  ... >> path   (NOT >&, NOT >/dev/null handled by classifier)
REDIR_RE = re.compile(r"(?:[0-9]?>|&>)>?\s*([^\s|;&)]+)")  # stdout/stderr/combined redirects
# tee [-a] path...   (path before next pipe/redirect)
TEE_RE = re.compile(r"\btee\s+(?:-a\s+)?([^\s|;&)]+)")
# sed -i ... LAST-non-flag-token is the file (best-effort: take tokens after the script)
SEDI_RE = re.compile(r"\bsed\b[^|;&]*?-i\S*\s+(?:-e\s+\S+\s+|'[^']*'\s+|\"[^\"]*\"\s+|\S+\s+)([^\s|;&)]+)")
# dd of=path
DDOF_RE = re.compile(r"\bdd\b[^|;&]*?\bof=([^\s|;&)]+)")
# cp/mv/install SRC... DEST  → DEST is the last non-flag token before pipe/sep
CPMV_RE = re.compile(r"\b(?:cp|mv|install)\b((?:\s+(?:-\S+|[^\s|;&)]+))+)")


def _strip_noise(cmd: str) -> str:
    """Neutralize regions where a `>` or a path-like token is NOT a real write target.

    Removes (in order):
      1. heredoc BODIES — everything from `<<[-]?WORD` (or quoted 'WORD') up to a line
         that is exactly WORD. The body is free text (commit messages, file content)
         and routinely contains `>` and bare words that look like relative paths.
      2. single-quoted strings  '...'   → emptied
      3. double-quoted strings  "..."   → emptied
    What remains is shell *structure*, where a `>` is far more likely a real redirect.
    This is the load-bearing false-positive killer (DeepSeek recipe, W79 follow-up):
    `git commit -m "...> x..."` and `cat > /tmp/f <<'EOF' ...body... EOF` no longer
    leak their text into the redirect scan.
    """
    # 1) heredoc bodies
    def _drop_heredocs(s: str) -> str:
        lines = s.split("\n")
        out = []
        i = 0
        hd_re = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
        while i < len(lines):
            line = lines[i]
            m = hd_re.search(line)
            out.append(line)
            if m:
                word = m.group(2)
                i += 1
                # consume body until a line == word (allow leading tabs for <<-)
                while i < len(lines) and lines[i].strip() != word:
                    i += 1
                # drop the terminator line too (it's not a command)
                i += 1
                continue
            i += 1
        return "\n".join(out)

    s = _drop_heredocs(cmd)
    # 2/3) empty quoted strings (single then double; simple state-free pass is enough
    #      because we only need to remove their CONTENT, not parse nesting perfectly).
    #      W84: the char-class MUST exclude newline — `[^']*`/`[^"]*` otherwise span
    #      across lines, so a stray quote on line A (an apostrophe in a comment, or the
    #      opening quote of an `ssh '...'` payload) pairs with a quote on line C,
    #      collapsing several commands into one mangled string and leaking grep
    #      patterns (`grep "a\|b" 2>&1`) into the redirect scan → a phantom
    #      write-target like `warm_models_extra\`. A shell quote never legitimately
    #      spans a newline here, so confining the match to one line is correct + the
    #      false-positive killer (lived 3x in the 2026-06-16 session, sibling of W83).
    s = re.sub(r"'[^'\n]*'", "''", s)
    s = re.sub(r'"[^"\n]*"', '""', s)
    return s


def _is_remote_dispatch(cmd_stripped: str) -> bool:
    """True if the (noise-stripped) command runs the work on ANOTHER host.

    W83: a git op inside `ssh host '...'` / `scp ... host:` / `rsync ... host:`
    executes off-box, so it can never touch THIS checkout — the worktree brake
    must not apply. We test the noise-stripped command so a literal `ssh` inside
    a quoted string does not falsely exempt a real local git op. Word-boundary
    match (not bare substring) to avoid matching e.g. `gosship`.
    """
    return bool(REMOTE_DISPATCH_RE.search(cmd_stripped))


def _extract_write_targets(cmd: str) -> list[str]:
    """Best-effort list of file-write destination paths in a shell command.

    Conservative by design: a target we cannot resolve is simply not returned
    (→ command is ALLOWED). We only want HIGH-CONFIDENCE writes into the repo.
    Runs on the NOISE-STRIPPED command (heredoc bodies + quoted strings removed).
    """
    cmd = _strip_noise(cmd)
    targets: list[str] = []
    for m in REDIR_RE.finditer(cmd):
        targets.append(m.group(1))
    for m in TEE_RE.finditer(cmd):
        targets.append(m.group(1))
    for m in SEDI_RE.finditer(cmd):
        targets.append(m.group(1))
    for m in DDOF_RE.finditer(cmd):
        targets.append(m.group(1))
    _PKG_MGR = ("npm ", "pip ", "pip3 ", "brew ", "apt ", "apt-get ", "cargo ", "gem ", "yarn ", "pnpm ", "go ")
    for m in CPMV_RE.finditer(cmd):
        # skip `install` that belongs to a package manager (npm/pip/brew install ...), not coreutils install
        pre = cmd[max(0, m.start() - 12):m.start()]
        if m.group(0).lstrip().startswith("install") and any(pre.rstrip().endswith(k.strip()) for k in _PKG_MGR):
            continue
        toks = [t for t in m.group(1).split()
                if not t.startswith("-") and ">" not in t and "<" not in t]  # drop flags + redirects
        if toks:
            targets.append(toks[-1])  # destination is the last positional arg
    # strip quotes; drop obvious non-file sinks
    cleaned = []
    for t in targets:
        t = t.strip().strip("'\"")
        if not t or t.startswith("/dev/") or t in {"&1", "&2"} or t.startswith("$("):
            continue
        # W84 defense-in-depth: a real write target never carries a backslash
        # (line-continuation / escape residue) nor a grep-alternation pipe; such a
        # token is noise that survived quote-stripping, not a path.
        if "\\" in t or "|" in t:
            continue
        cleaned.append(t)
    return cleaned


def _resolve_target(path_str: str, cwd: str) -> pathlib.Path | None:
    """Resolve a possibly-relative write target against cwd. None on failure."""
    try:
        p = pathlib.Path(os.path.expanduser(path_str))
        if not p.is_absolute() and cwd:
            p = pathlib.Path(cwd) / p
        return p.resolve()
    except Exception:
        return None


def _write_hits_main(cmd: str, cwd: str) -> pathlib.Path | None:
    """Return the offending path if a shell write lands INSIDE main checkout
    (and NOT inside an allowed worktree). None = no main-write detected → allow."""
    if not WRITE_HINT_RE.search(cmd):
        return None
    repo_real = pathlib.Path(REPO_ROOT).resolve()
    for raw in _extract_write_targets(cmd):
        # allowed-worktree check reuses the git path logic (same resolver)
        if _is_path_in_allowed_worktree(raw):
            continue
        resolved = _resolve_target(raw, cwd)
        if resolved is None:
            continue  # unclassifiable → conservative allow
        try:
            inside_main = resolved == repo_real or resolved.is_relative_to(repo_real)
        except AttributeError:
            try:
                resolved.relative_to(repo_real)
                inside_main = True
            except ValueError:
                inside_main = False
        if inside_main and not _is_path_in_allowed_worktree(str(resolved)):
            return resolved
    return None

ALIVE_COUNT_CACHE = "/tmp/nuz_alive_count"
BLOCK_COUNT_FILE = "/tmp/nuz_l5_1_blocks"
PROBE_LOG = pathlib.Path.home() / ".claude" / "l5_1_hook_probe.jsonl"


def _kill_switch_active() -> bool:
    val = os.environ.get("AGENT_WORKTREE_ENFORCEMENT", "true").strip().lower()
    return val in {"false", "0", "no", "off", "disabled"}


def _git_worktree_list() -> list[pathlib.Path]:
    """Parse `git worktree list --porcelain` for current worktree paths.

    Best-effort: empty list on error (defaults to only main).
    """
    try:
        result = subprocess.run(
            ["git", "-C", REPO_ROOT, "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode != 0:
            return []
        worktrees = []
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                p = line.removeprefix("worktree ").strip()
                try:
                    worktrees.append(pathlib.Path(p).resolve())
                except Exception:
                    pass
        return worktrees
    except Exception:
        return []


def _is_path_in_allowed_worktree(path_str: str) -> bool:
    """True if path resolves under an allowed worktree (NOT main checkout)."""
    if not path_str:
        return False
    try:
        path_real = pathlib.Path(path_str).resolve()
    except Exception:
        return False

    repo_real = pathlib.Path(REPO_ROOT).resolve()

    # Exactly main checkout → NOT allowed
    if path_real == repo_real:
        return False

    # Get all worktrees from git
    worktrees = _git_worktree_list()
    # Filter out main checkout itself
    allowed = [w for w in worktrees if w != repo_real]

    # W79: any path under REPO_ROOT/.worktrees/<anything> is the convention scratch
    # area — allowed even if not (yet) a git-registered worktree. Without this, a
    # write into a freshly-created or unregistered worktree dir is mis-classified
    # as a main-checkout write and blocked (false positive that breaks normal work).
    _repo_esc = re.escape(str(repo_real))
    worktrees_dir_re = re.compile(r"^" + _repo_esc + r"/\.worktrees/[^/]+(?:/|$)")
    if worktrees_dir_re.match(str(path_real)):
        return True

    # Also accept external worktree convention paths
    _base = re.escape(os.path.dirname(REPO_ROOT))
    external_patterns = [
        re.compile(r"^" + _base + r"/nuzantara-deploy$"),
        re.compile(r"^" + _base + r"/nuzantara-wa-dashboard-[a-z0-9-]+$"),
        re.compile(r"^" + _base + r"/nuzantara-[a-z0-9-]+-2026-\d{2}-\d{2}$"),
    ]

    path_str_real = str(path_real)
    for pattern in external_patterns:
        # Check if path_real OR any parent matches
        for parent in [path_real, *path_real.parents]:
            if pattern.match(str(parent)):
                return True

    # is_relative_to check against discovered worktrees
    for allowed_wt in allowed:
        try:
            if path_real == allowed_wt or path_real.is_relative_to(allowed_wt):
                return True
        except AttributeError:
            # Python <3.9 fallback
            try:
                path_real.relative_to(allowed_wt)
                return True
            except ValueError:
                pass

    return False


def _effective_git_target(cmd: str, default_cwd: str) -> str:
    """Determine the effective working dir for git command.

    Priority: `git -C <path>` > `cd <path> && git` > default cwd.
    """
    m = GIT_C_RE.search(cmd)
    if m:
        return m.group(1)
    m = CD_GIT_RE.search(cmd)
    if m:
        return m.group(1)
    return default_cwd


def _n_alive_cached() -> int:
    try:
        return int(pathlib.Path(ALIVE_COUNT_CACHE).read_text().strip())
    except Exception:
        return -1


def _increment_block_counter():
    try:
        bc = pathlib.Path(BLOCK_COUNT_FILE)
        n = int(bc.read_text().strip()) if bc.exists() else 0
        bc.write_text(str(n + 1))
    except Exception:
        pass


def _probe_log(payload: dict, decision: str):
    """A5: probe-mode logging for empirical sub-agent inheritance test."""
    try:
        PROBE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with PROBE_LOG.open("a") as f:
            json.dump({
                "tool_name": payload.get("tool_name", ""),
                "cwd": payload.get("cwd", ""),
                "cmd": payload.get("tool_input", {}).get("command", "")[:200],
                "decision": decision,
                "pid": os.getpid(),
                "ppid": os.getppid(),
            }, f)
            f.write("\n")
    except Exception:
        pass


def main():
    if _kill_switch_active():
        sys.exit(0)

    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if payload.get("tool_name") != "Bash":
        sys.exit(0)

    cmd = payload.get("tool_input", {}).get("command", "")
    cwd = payload.get("cwd", "")

    # --- W79 B1: shell file-WRITE into main checkout (independent of git) ---
    offending = _write_hits_main(cmd, cwd)
    if offending is not None:
        _increment_block_counter()
        _probe_log(payload, "block_shell_write_main")
        sys.stderr.write(
            f"WORKTREE ISOLATION VIOLATION (Bash file-write into main checkout)\n"
            f"  cwd: {cwd}\n"
            f"  write target: {offending}\n"
            f"  command: {cmd[:200]}\n\n"
            f"Reason: writing a file into the MAIN checkout via shell would race with\n"
            f"other agents and bypass the worktree discipline (W79 / phase-aware-guardrails §9-B).\n\n"
            f"Resolution: write into your worktree instead, or use\n"
            f"  python scripts/agent_start.py --lane <lane> --task-id <task-id>\n\n"
            f"Emergency escape: AGENT_WORKTREE_ENFORCEMENT=false (env var set in shell)\n"
        )
        sys.exit(2)

    # Quick exit: cmd doesn't look git-mutating
    if "git" not in cmd:
        sys.exit(0)

    # W83: strip heredoc bodies + quoted strings BEFORE the git scan, so a git verb
    # that lives only inside a quoted literal (e.g. grep "git pull") is not seen as a
    # real command. The git scan + target resolution all run on the stripped form.
    cmd_scan = _strip_noise(cmd)

    if not BLOCKED_SUBCMD_RE.search(cmd_scan):
        sys.exit(0)

    # W83: a git op carried by a remote ssh/scp/rsync dispatch runs on ANOTHER
    # host and can never touch this checkout → allow. (Innocence: a LOCAL git op
    # has no ssh/scp/rsync dispatcher token, so it still falls through to block.)
    if _is_remote_dispatch(cmd_scan):
        _probe_log(payload, "allow_remote_dispatch")
        sys.exit(0)

    # Compute effective target (on the stripped command, for the same reason).
    target = _effective_git_target(cmd_scan, cwd)

    # If effective target is in an allowed worktree → permit
    if _is_path_in_allowed_worktree(target):
        _probe_log(payload, "allow_worktree")
        sys.exit(0)

    # If target is NOT REPO_ROOT and we can't classify → permit (defense conservative)
    target_real = pathlib.Path(target).resolve() if target else pathlib.Path(REPO_ROOT)
    repo_real = pathlib.Path(REPO_ROOT).resolve()
    if target_real != repo_real:
        _probe_log(payload, "allow_external")
        sys.exit(0)

    # Block.
    _increment_block_counter()
    _probe_log(payload, "block")

    n_alive = _n_alive_cached()
    n_alive_str = f"{n_alive}" if n_alive >= 0 else "?"

    sys.stderr.write(
        f"WORKTREE ISOLATION VIOLATION (Bash git op in main)\n"
        f"  cwd: {cwd}\n"
        f"  effective target: {target_real}\n"
        f"  command: {cmd[:200]}\n"
        f"  alive AI processes: {n_alive_str}\n\n"
        f"Reason: this git op in main checkout would race with other agents.\n\n"
        f"Resolution:\n"
        f"  1. Create dedicated worktree:\n"
        f"     python scripts/agent_start.py --lane <lane> --task-id <task-id>\n"
        f"     cd <output-path>\n"
        f"  2. Then retry the git op there (use 'git -C <path> ...' since Bash resets cwd).\n\n"
        f"Emergency escape: AGENT_WORKTREE_ENFORCEMENT=false (env var set in shell)\n\n"
        f"See: docs/runbooks/agent-worktree-broker.md\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
