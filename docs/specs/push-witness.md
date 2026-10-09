# Push witness

## Runtime witness

### Threat model

Shell text cannot prove which hook Git will execute. A pusher may override
`core.hooksPath`, use `--no-verify`, wrap Git in another shell or function, or
construct an override dynamically. Static inspection therefore remains useful
only for known shapes; it is not the trust decision.

After every blocking check succeeds, `.husky/pre-push` appends one JSONL marker
per ref from Git's pre-push stdin. The marker records the exact tip SHA, remote
ref, remote URL (the `user:token@` of a URL with a scheme is dropped; the ssh
user of an scp-form remote is kept), host, time, cwd, trust root, and SHA-256 of
the hook file that ran (`$0`). Journal failure warns but never blocks a push.

The reconciler evaluates the `agent/<host>/...` tips this checkout has observed
(the proprioception runner fetches first) whose time falls inside `--since`. A
tip's time is the later of its committer date and the moment the reflog of
`refs/remotes/origin/<branch>` moved to it, so a backdated commit pushed today
is judged; a tip with no such reflog line is counted as `unobserved` (its
committer date is then the only clock). A tip requires an exact SHA marker for its own remote ref whose URL
equals the checkout's `origin` push URL after the same userinfo drop; an
ancestor, a SHA prefix or a push of the same SHA to another remote is not
evidence. The journal is per host and `$HOME`, so markers are not filtered by
the hostname they recorded. It reports:

- `NO-WITNESS`: no exact marker exists.
- `STALE-WITNESS`: every matching marker predates the tip's committer date.
- `FOREIGN-ROOT`: every matching marker names neither the checkout or one of its
  linked worktrees (registered, or `<checkout>/.worktrees/<lane>`) nor the
  pinned bundle layout `codex-autofix-trusted-prepush/<40-hex-commit>/tree`.
- `RECONCILE-ERROR`: the run itself failed (for example a tip object missing
  locally); `--json` still exits 0 and `--check` exits 1.

The witness epoch is the oldest marker in the journal: the witness covers
pushes after the epoch only. An unmarked tip whose time is before it, or whose own
tree has no witness code in `.husky/pre-push` (a branch forked before the
hook carried it) while its time is within seven days of the epoch, is counted
as `uncovered`, never judged. After those seven days such a tip is judged: its
own hook is stale. An absent or empty
journal reports `checked: 0` and `note: no witness epoch yet`. Epoch and
coverage use the tip's time above.

### Claim and limits

A marker proves that a hook reached its successful end before Git attempted to
land those refs. It does not prove the later push succeeded: a push rejected
after the hook leaves a marker with no tip, harmless for the verdicts because
only tips are judged; the reuse it allows is declared below. A forced push that
replaces a witnessed tip with an unmarked, covered one reads `NO-WITNESS`. A
marker does not, by itself, prove the checks were the reviewed versions:
`trust_root` is a declared root classified by its path, not an attestation of
the bundle's content, while `hook_sha256` preserves the exact hook identity for
audit and comparison. The trusted bundle
carries the hook itself, so both normal and unattended pushes execute the same
marker code.

Declared remainders:

- A host owner can forge a marker by writing the journal directly; host-owner
  integrity is the trust boundary.
- The same owner can delete or replace the journal: an empty journal reads
  `no witness epoch yet` and a replaced one starts a new epoch, so both silence
  the probe instead of raising it. Host-owner integrity covers this too.
- A failed witnessed attempt followed by a bypassed retry of the same ref and
  SHA can reuse the earlier marker; the journal is not a remote push receipt.
- A marker binds a SHA and a ref, not one push: re-pointing a branch around the
  hook to a SHA that went through it earlier reads witnessed; that content
  passed the hook.
- A `<checkout>/.worktrees/<lane>` root stays trusted after the worktree is
  pruned, so a finished lane does not turn into `FOREIGN-ROOT`; planting a
  directory there needs the host owner's write access.
- A journal the hook could not write, or a commit dated after its own marker by
  clock skew, reads `NO-WITNESS` or `STALE-WITNESS`: a finding to read, not
  proof that the hook was skipped. A tip written on the server side (a GitHub
  update-branch merge) has no local marker and reads `NO-WITNESS`.
- A worktree push runs the branch's own `.husky/pre-push`; a branch that
  removes the witness code leaves coverage, visibly, in its diff of that file.
- Pushes from another host are judged from that host's journal.
- A malformed journal line is counted and ignored; it cannot stop the probe.
- The legacy static lint's `TRUSTED` verdict means only “canonical line with no
  known override shape.” It is not runtime evidence.
