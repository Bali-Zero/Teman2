"""B25-prime P1: the ledger-rule mutants of docs/specs/localci-sovereign-2026-10-07.md 2b.4 (their spec names), then the writer's, the
verifier's and the wrapper mode's own. `m-gate-not-failure` is accepted as equivalent there (the closed verdict schema makes it one predicate)."""
GL, GT = "scripts/localci/gate_ledger.py", ("scripts/localci/tests/test_gate_ledger.py",)
WR = "scripts/localci/localci_merger_tick.sh"
NEWEST = '    if mine[-1][1]["verdict"] != "success":'
HEX = 'HEX40 = re.compile(r"[0-9a-f]{40}")'
MINE = 'e["repo"] == repo and e["head_sha"] == head]'
REPLACED = "        if (st.st_dev, st.st_ino) != (on_disk.st_dev, on_disk.st_ino):"

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    # --- 2b.4 ledger rule
    "b25-gate-of-any-state": (GL, NEWEST, "    if False:", GT),
    "b25-gate-absent-is-fine": (GL, '    except LedgerMissing:\n        return False, "ledger missing"', '    except LedgerMissing:\n        return True, "ledger missing"', GT),
    "b25-gate-other-sha": (GL, MINE, 'e["repo"] == repo]', GT),
    "b25-gate-read-error-is-true": (GL, "    except LedgerFile as exc:\n        return False, str(exc)\n", "    except LedgerFile as exc:\n        return True, str(exc)\n", GT),
    "g-gate-any-success": (GL, NEWEST, '    if not any(e["verdict"] == "success" for _, e in mine):', GT),
    "g-gate-sha-unchecked": (GL, HEX, 'HEX40 = re.compile(r"[0-9a-f]+")', GT),
    "g-failed-read-is-success": (GL, "    except LedgerLine as exc:\n        return False, str(exc)\n", "    except LedgerLine as exc:\n        return True, str(exc)\n", GT),
    "m-gate-prefix": (GL, MINE, 'e["repo"] == repo and e["head_sha"].startswith(head[:12])]', GT),
    "m-gate-casefold": (GL, HEX, 'HEX40 = re.compile(r"[0-9a-f]{40}", re.I)', GT),
    "m-gate-first-wins": (GL, NEWEST, '    if mine[0][1]["verdict"] != "success":', GT),
    "m-gate-last-wins": (GL, "    for i, (d, e) in enumerate(mine[:-1]):", "    for i, (d, e) in enumerate([]):", GT),
    "symlink-followed": (GL, "        st = os.lstat(path)\n        _check_state(st)\n        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)\n",
                        "        st = os.stat(path)\n        _check_state(st)\n        fd = os.open(path, os.O_RDONLY)\n", GT),
    "mode-or-owner-unchecked": (GL, "    if st.st_mode & 0o077 or st.st_uid != os.geteuid():", "    if False:", GT),
    "torn-line-skipped": (GL, '            raise LedgerLine(n, f"does not parse ({str(exc)[:60]})")', "            continue", GT),
    "junk-skipped": (GL, "        if (why := validate(e)) is not None:\n            raise LedgerLine(n, why)\n", "        if (why := validate(e)) is not None:\n            continue\n", GT),
    "supersede-any-digest": (GL, 'and not any(l["supersedes"] == d for _, l in mine[i + 1:]):\n            return False, f"entry',
                             'and not any(l["supersedes"] is not None for _, l in mine[i + 1:]):\n            return False, f"entry', GT),
    # --- the reader's remaining terms
    "own-forward-supersede-counts": (GL, 'any(l["supersedes"] == d for _, l in mine[i + 1:]):\n            return False', 'any(l["supersedes"] == d for _, l in mine):\n            return False', GT),
    "own-other-head-supersede-counts": (GL, 'any(l["supersedes"] == d for _, l in mine[i + 1:]):\n            return False', 'any(l["supersedes"] == d for _, l in entries):\n            return False', GT),
    "own-not-regular-accepted": (GL, "    if not stat.S_ISREG(st.st_mode):\n        raise LedgerFile(\"ledger is not a regular file\")", "    if False:\n        raise LedgerFile(\"ledger is not a regular file\")", GT),
    "b25p1-quarantine-completes-the-torn-tail": (GL, "            rest = rest[:-1]", "            pass", GT),
    "b25p1-pr-must-be-int": (GL, 'and (e["pr"] is None or (_is_int(e["pr"]) and e["pr"] > 0))', 'and (_is_int(e["pr"]) and e["pr"] > 0)', GT),
    "b25p1-torn-tail-accepted": (GL, "        if torn_tail and n == len(lines):", "        if False:", GT),
    # --- the writer
    "b25p1-twin-at-any-position": (GL, "            newest = mine[-1] if mine else None", "            newest = next((x for x in mine if _same(x[1], entry)), mine[-1] if mine else None)", GT),
    "b25p1-no-idempotency": (GL, "            if newest is not None and (_same(", "            if False and (_same(", GT),
    "b25p1-tail-newline-unchecked": (GL, '        if data and not data.endswith(b"\\n"):', "        if False:", GT),
    "b25p1-via-always-local": (GL, "    return parts[0]", '    return "local"', GT),
    "b25p1-malformed-ssh-connection-guessed": (GL, "    if len(parts) != 4 or not VIA_RE.fullmatch(parts[0]):", "    if False:", GT),
    "b25p1-short-write-unchecked": (GL, '                if os.write(fd, line + b"\\n") != len(line) + 1:', "                if False:", GT),
    "b25p1-short-write-not-truncated": (GL, "                os.ftruncate(fd, size)\n                raise\n", "                raise\n", GT),
    "b25p1-replaced-inode-unchecked": (GL, REPLACED, "        if False:", GT),
    "b25p1-supersede-oldest-first": (GL, "for d in reversed(_unsuperseded(mine))]", "for d in _unsuperseded(mine)]", GT),
    "b25p1-supersede-names-one": (GL, "for d in reversed(_unsuperseded(mine))]", "for d in reversed(_unsuperseded(mine))][:1]", GT),
    "b25p1-supersede-on-a-failure": (GL, '        if supersede and client["verdict"] == "success":', "        if supersede:", GT),
    "b25p1-supersede-other-head": (GL, 'mine = [(d, e) for d, e in have if e["repo"] == full["repo"] and e["head_sha"] == full["head_sha"]]',
                                   'mine = [(d, e) for d, e in have if e["repo"] == full["repo"]]', GT),
    "b25p1-unsuperseded-ignores-names": (GL, 'and not any(l["supersedes"] == d for _, l in mine[i + 1:])]', 'and not any(l["supersedes"] is not None for _, l in mine[i + 1:])]', GT),
    "b25p1-directory-0755": (GL, "mode=0o700, exist_ok=True", "mode=0o755, exist_ok=True", GT),
    "b25p1-file-0644": (GL, "os.O_NOFOLLOW, 0o600)\n    try:\n        fcntl.flock(fd, fcntl.LOCK_EX)\n        st, on_disk", "os.O_NOFOLLOW, 0o644)\n    try:\n        fcntl.flock(fd, fcntl.LOCK_EX)\n        st, on_disk", GT),
    # --- verify and quarantine
    "b25p1-verify-ignores-directory-mode": (GL, "    if dmode & 0o077:", "    if False:", GT),
    "b25p1-quarantine-moves-a-valid-line": (GL, "        if valid:", "        if False:", GT),
    "b25p1-quarantine-unjournalled": (GL, '            os.write(qfd, rec.encode("ascii") + b"\\n")', "            pass", GT),
    # --- the tick wrapper's gate-append mode
    "b25p1-wrapper-reads-base": (WR, 'rev-parse --verify --quiet "refs/merger/wrapper^{commit}"', 'rev-parse --verify --quiet "refs/merger/base^{commit}"', GT),
    "b25p1-wrapper-failure-swallowed": (WR, 'append "$@"\n  exit $?', 'append "$@" || true\n  exit 0', GT),
    "b25p1-wrapper-missing-code-unchecked": (WR, 'if ! git -C "$GA_STATE/repo.git" show "$GA_SHA:scripts/localci/gate_ledger.py" > "$GA_CODE/gate_ledger.py" || [ ! -s "$GA_CODE/gate_ledger.py" ]; then',
                                             "if false; then", GT),
}
