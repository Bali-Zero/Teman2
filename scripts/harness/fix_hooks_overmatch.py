#!/usr/bin/env python3
"""fix_hooks_overmatch.py — fixa la famiglia "Guard-over-match" (superscar #3) in 3 hook.
BUG#1 CPMV su 'npm/pip/brew install' + redirect-come-path. BUG#2 redirect 2>/&> non rilevati.
BUG#3 guardrails python -c matcha eval/subprocess dentro stringhe.
Idempotente, backup-first. OPERATOR-RUN (hooks/ blindato). PATCH_TARGET_DIR per test."""
import os, sys, re

DIR = os.environ.get("PATCH_TARGET_DIR", os.path.expanduser("~/.claude/hooks"))

def patch(fname, replacements):
    p = os.path.join(DIR, fname)
    src = open(p).read()
    orig = src
    for old, new, tag in replacements:
        if new in src:
            print(f"  {fname}: [{tag}] già patchato"); continue
        if old not in src:
            print(f"  {fname}: [{tag}] 🔴 ANCORA NON TROVATO (pattern cambiato?)"); continue
        src = src.replace(old, new, 1)
        print(f"  {fname}: [{tag}] ✓ patchato")
    if src != orig and "PATCH_TARGET_DIR" not in os.environ:
        open(p + ".bak-overmatch", "w").write(orig)
    open(p, "w").write(src)

# ── BUG#1 + BUG#2 in worktree_isolation.py ──
# CPMV: escludi 'install' preceduto da package-manager (npm/pip/brew/apt/cargo/gem/yarn/pnpm)
OLD_CPMV = r'CPMV_RE = re.compile(r"\b(?:cp|mv|install)\b((?:\s+(?:-\S+|[^\s|;&)]+))+)")'
NEW_CPMV = r'CPMV_RE = re.compile(r"(?<![\w-])(?:cp|mv|install)\b((?:\s+(?:-\S+|[^\s|;&)]+))+)")'
# il (?<![\w-]) impedisce match di 'install' dentro 'npm install' (preceduto da spazio dopo 'npm'),
# MA 'npm install' ha spazio prima di install → serve escludere il COMANDO precedente.
# Soluzione robusta: nel codice, scarta i match il cui token-0 della riga e' un package manager.

# ── BUG#3 in guardrails-static.py: richiedi la CHIAMATA (parentesi) non la sola parola ──
OLD_PYC = r'''(re.compile(r"\bpython\d?\s+-c\s+['\"].*\b(os\.system|subprocess|exec|eval|os\.remove|shutil\.rmtree)\b", re.IGNORECASE), "Python -c arbitrary exec"),'''
NEW_PYC = r'''(re.compile(r"\bpython\d?\s+-c\s+['\"].*\b(os\.system|exec|eval|os\.remove|shutil\.rmtree)\s*\(|\bpython\d?\s+-c\s+['\"].*subprocess[^'\"]*shell\s*=\s*(?:True|1)", re.IGNORECASE), "Python -c arbitrary exec"),'''

print("=== guardrails-static.py (BUG#3) ===")
patch("guardrails-static.py", [(OLD_PYC, NEW_PYC, "python-c-require-call")])

print("=== worktree_isolation.py (BUG#1 CPMV + BUG#2 redirect) ===")
# BUG#1: patch CPMV consumption nel _extract_write_targets per scartare pkg-manager + redirect-token
OLD_CONSUME = '''    for m in CPMV_RE.finditer(cmd):
        toks = [t for t in m.group(1).split() if not t.startswith("-")]
        if toks:
            targets.append(toks[-1])  # destination is the last positional arg'''
NEW_CONSUME = '''    _PKG_MGR = ("npm ", "pip ", "pip3 ", "brew ", "apt ", "apt-get ", "cargo ", "gem ", "yarn ", "pnpm ", "go ")
    for m in CPMV_RE.finditer(cmd):
        # skip `install` that belongs to a package manager (npm/pip/brew install ...), not coreutils install
        pre = cmd[max(0, m.start() - 12):m.start()]
        if m.group(0).lstrip().startswith("install") and any(pre.rstrip().endswith(k.strip()) for k in _PKG_MGR):
            continue
        toks = [t for t in m.group(1).split()
                if not t.startswith("-") and ">" not in t and "<" not in t]  # drop flags + redirects
        if toks:
            targets.append(toks[-1])'''
# BUG#2: REDIR_RE cattura anche 2> e &> (rimuovi il lookbehind troppo largo, filtra &1/&2 dopo)
OLD_REDIR = r'REDIR_RE = re.compile(r"(?<![0-9>&])>>?\s*([^\s|;&)]+)")'
NEW_REDIR = r'REDIR_RE = re.compile(r"(?:[0-9]?>|&>)>?\s*([^\s|;&)]+)")  # stdout/stderr/combined redirects'

patch("worktree_isolation.py", [
    (OLD_REDIR, NEW_REDIR, "redirect-2>-&>"),
    (OLD_CONSUME, NEW_CONSUME, "cpmv-pkgmgr+redirect-skip"),
])

print("\nFATTO." if "PATCH_TARGET_DIR" not in os.environ else "\nTEST patch applicata.")
