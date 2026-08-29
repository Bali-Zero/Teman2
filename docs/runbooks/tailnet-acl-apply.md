# Runbook — applying the tailnet ACL

Applies `infra/tailscale/policy.hujson` to the `balizero` tailnet (`tail461666.ts.net`), replacing
the factory allow-all default with the deny-by-default matrix.

**Owner: `operator[GUI]`.** The fleet holds no Tailscale API token — verified absent from
`~/.nuzantara-secrets.env`, `.env.master` and the keychain — and the CLI can neither read nor write
ACLs. The admin console is a genuine GUI-only surface, so a session cannot do this step; it can do
every verification step below.

## What you are fixing

Today the tailnet packet filter is one rule: every node to every port on every node. `tailscale
serve` on Pro publishes `https://nuzantara.tail461666.ts.net/term` -> `127.0.0.1:7681`, which is
`ttyd -W zsh` — writable, no credential flag. **Any device on this tailnet has an unauthenticated
writable shell on Pro as user `nuzantara`**, the host with the wa-mirror raw PII, the CRM runtime
and the secrets file.

This is not a live breach: all six nodes are Zero's own. It is a hard blocker on letting a
teammate's laptop join, and **the ordering is the whole point** — apply the policy first, enroll
second. Join-then-restrict leaves a window in which that laptop holds the shell.

## Before you start

- Have a **second device already on the tailnet** (an iPhone works) — step 5 needs it, and if you
  lock yourself out of Pro you will want another way in.
- Know that you are **not** locked out by a bad ACL: an admin can always edit the policy again from
  the console over the public internet, which no ACL governs.
- Read `infra/tailscale/policy.hujson` end to end, especially the `SHELL-ROUTE` block.

## 1. Repo-side pre-check (session can run this)

```bash
cd ~/nuzantara
python3 -m pytest scripts/tests/test_tailnet_acl_deny_by_default.py -q
```

### What green means — and the block it does not look at

Green means these properties hold **on the `acls` and `grants` blocks**, and nowhere else: no `*`
as a source; no `*` as a destination host or port; no destination spanning more than 64 ports;
every destination selector resolves to a named node or is refused outright
(`UNRESOLVABLE_DST_SELECTOR`); the shell port `pro:443` is reachable only from the two allowlisted
nodes, in every spelling of node and port the guard canonicalises; `"proto"` present on every
`acls` rule; and `tag:team-device` in no rule's `src`. Beyond the rules it also refuses any
top-level key it does not know, requires the `SHELL-ROUTE:` comment to still name `7681`, `/term`
and `ttyd`, and requires a deny-test covering the shell port for a team device.

**It does NOT check the `ssh` block, and you must read that block by eye before you save.** The
guard inspects exactly three things there — the literal string `"root"` in `users`, and
`tag:team-device` in `src` or `dst` — and applies none of the wildcard or selector checks above to
it. Measured on this branch: an `ssh` rule reading `"src": ["*"], "dst": ["*"], "users":
["autogroup:nonroot"]` yields **zero findings**, while the identical wildcard in an `acls` rule
yields `WILDCARD_SRC` + `WILDCARD_DST_HOST` + `UNRESOLVABLE_DST_SELECTOR`. And because the root
check is a denylist of that one literal, `"users": ["*"]` — strictly wider than `root` — is green
too. **So a green run is not evidence that this file grants no root over Tailscale SSH.** The only
thing that establishes that is your own reading of the block, which is one rule of six lines near
the end of `policy.hujson`; it must read `"users": ["autogroup:nonroot"]`.

Two further gaps, both relevant while you are looking at the file rather than after:

- **There is no `UNRESOLVABLE_SRC_SELECTOR`** to mirror the destination one. A source the guard
  cannot resolve — `tag:fleet`, a `group:`, any tag other than `tag:team-device` — is skipped
  silently, so a device enrolled under a different tag sits outside both the rules written to
  contain it and the guard written to check them. This is the same failure mode step 2 of
  `infra/tailscale/enroll-team-device.md` warns about from the other end: the auth key must carry
  `tag:team-device`, that exact string.
- **The shell anchor resolves through the `hosts` alias `"pro"`**, not through Pro's IP
  (`100.107.22.111` appears nowhere in the guard). Editing what `"pro"` points at moves the anchor
  with it. Measured: with `"pro"` re-pointed at Mini's IP and a second alias carrying Pro's real
  one, `mini -> <that alias>:443` produces **zero findings**, where `mini -> pro:443` against the
  correct map produces `SHELL_PORT_SRC_NOT_ALLOWLISTED`. It takes two coordinated edits rather than
  one, and re-pointing the alias alone is caught (as `UNRESOLVABLE_DST_SELECTOR`) — but it means
  **you must read the `hosts` map itself**, not only the rules that reference it. Confirm `"pro"`
  still reads `100.107.22.111`.

All four gaps are written up with their reproductions in `.claude/skills/modus/PENDING-ARMS.md`
(search `tailnet-acl guard`); closing them is a separate, specified PR and not a prerequisite for
applying this policy — the policy's own content was independently confirmed sound by three graders.

None of this means Tailscale accepts the file — only the console can say that.

## 2. Preview (dry run) in the console

1. Open <https://login.tailscale.com/admin/acls>.
2. **Copy the current policy out first** and save it to a scratch file outside the repo. This is
   your rollback, and it is the only copy — Tailscale keeps a version history in the console, but
   having the text in hand is faster under pressure.
3. Paste the contents of `infra/tailscale/policy.hujson` into the editor. **Do not save yet.**
4. The editor validates as you type: syntax errors, unknown tags, and invalid `dst` shapes surface
   inline. It also runs the `tests` block. Read every message.
   - If it rejects an `autogroup:*` used as an **ssh** `dst`, that is the known trap: an ssh
     destination is limited to `autogroup:self` (which is what the file uses). Note the
     distinction — an autogroup IS permitted as an ordinary ACL destination, so a blanket "no
     autogroups in dst" reading is wrong. Fix the file in the repo, re-run step 1, and re-paste
     — never patch only in the console, or the repo and the tailnet diverge (the HOME-fork
     disease, applied to network policy).
5. Use **Preview** on a couple of node pairs before saving. Preview answers "can A reach B:port"
   against the pasted draft. Check at minimum `m5` -> `pro:22` (must be allowed) and `mini` ->
   `pro:443` (must be denied).

## 3. Save

Click **Save**. The policy compiles and pushes to every node within seconds. The `tests` block runs
again at save time and a failing test blocks the save — that is the gate, and it is why the file
ships with deny-tests and not only accept-tests.

## 4. Verify the fleet still works (innocence)

From M5:

```bash
ssh pro   true && echo "m5->pro:22 OK"
ssh mini  true && echo "m5->mini:22 OK"
curl -sk -o /dev/null -w '%{http_code}\n' https://nuzantara.tail461666.ts.net/deck
```

From Pro:

```bash
ssh mini true && echo "pro->mini:22 OK"
nc -z -G 5 100.93.236.6 11434 && echo "pro->mini:11434 (ollama) OK"
nc -z -G 5 100.93.236.6 6379  && echo "pro->mini:6379 (redis) OK"
nc -z -G 5 100.93.236.6 8990  && echo "pro->mini:8990 (KG api) OK"
```

If one of these fails, the policy is missing a rule the fleet actually needs. **Add the rule with
its evidence** (which script, which file:line) and re-apply. Do not widen a `dst` to `:*` to make a
red go green — that is exactly the defect this policy replaced, and the CI guard will reject it.

Then let a full cron cycle pass and check `scripts/fleet_watch.py`'s output and the memory-sync
logs. A deny-by-default policy fails loudly on first use of an ungranted flow, which may be hours
after the save.

**Every rule carries `"proto": "tcp"`, so UDP and ICMP between nodes are no longer permitted.**
That is deliberate — without `proto` a rule granting "only SSH" also grants UDP/22 and ICMP for
the pair, which made the file's own comments false. Practical consequence: a plain
`ping 100.93.236.6` between fleet nodes will now fail. `scripts/fleet_watch.py` is unaffected, but
**not for the reason an earlier draft of this runbook gave** (corrected 2026-08-29): it has no ping
probe at all. `check_tailscale()` reads the local daemon (`tailscale status --json` — no tailnet
traffic) and `check_ssh()` uses OpenSSH on port 22, which the policy grants. If some service turns
out to need UDP, add `"proto": "udp"` as its own rule with its evidence — do not delete `proto` to
make a red go green.

## 5. Verify the denies actually deny (guilt) — the load-bearing step

An accept-only verification is not a verification: it can report success and can never report
failure. That is precisely how the 2026-05 laptop handoff "verified" retained access with
`ssh air 'tailscale status'` — a command that answers green from M5 no matter what, because both
`air` and `air-ts` resolve to M5 on Pro.

**Run the positive control FIRST, or the negative result proves nothing.** A failed `curl` to
`/term` has at least three causes — the ACL denied it, ttyd is down, or `tailscale serve` is not
mounted — and only the first is the one you are testing. So establish that the endpoint is alive
from a node the policy _allows_, then show it is dead from a node the policy _denies_, in the same
few minutes.

Step A — **from M5** (allowed: rule 4 grants `m5 -> pro:443`). This must SUCCEED:

```bash
curl -sk -m 8 -o /dev/null -w 'M5 -> /term : %{http_code}\n' https://nuzantara.tail461666.ts.net/term
```

Expect `200`. If this is not 200, the endpoint itself is down — stop, because step B cannot mean
anything yet.

Step B — **from Mini** (denied: rule 2 grants only `mini -> pro:22`). This must FAIL:

```bash
# GUILT TEST. Success here means the policy did NOT take effect.
curl -sk -m 8 -o /dev/null -w 'MINI -> /term : %{http_code}\n' https://nuzantara.tail461666.ts.net/term
echo "curl exit: $?"
```

- **Expected: a TIMEOUT — `curl: (28)`, exit 28.** A dropped packet gives no answer at all, so the
  connection hangs until the deadline. That is the signature of a packet filter.
- **Exit 7 (`Failed to connect`) is NOT a clean pass.** It means the connection was actively
  refused, which a dropped packet does not do — read it as "something else is wrong" and
  investigate, rather than banking it as proof.
- **`200`: the policy is NOT in effect.** Either it was not saved, or Mini matched a rule you did
  not intend. Stop and re-read the `acls` block before doing anything else.
- **`403` is a failure of this test too**: the connection was established and something above the
  network layer refused it. The ACL's job is that the TCP connection never completes.

Once a team laptop exists, the same test from the laptop is the real one, and its expected result
is identical. `infra/tailscale/enroll-team-device.md` step 5 covers it, together with
`bash scripts/verify_tailnet_node.sh <hostname>` — which exits 4, not 0, when the name you asked
about resolves to the machine you are asking from. That distinction is what hid the broken handoff
for three months.

## 6. Rollback

Two paths, in order of preference:

1. **Console version history.** The ACL editor keeps previous versions; select the one from before
   your save and restore it. Fastest, and exact.
2. **Paste back the copy you saved in step 2.2.** Save. The old policy recompiles and pushes within
   seconds.

Rollback restores allow-all, which restores the unauthenticated shell to every node. That is
acceptable only while every node is Zero's own — **if a team device has already joined, roll back
by removing that device from the tailnet first** (console -> Machines -> Remove), then roll the
policy back. Never leave a non-Zero device on an allow-all tailnet, even briefly.

## What this runbook does not cover

- **Enrolling a team device.** That is `infra/tailscale/enroll-team-device.md`, and it starts
  _after_ this runbook finishes: mint a single-use auth key tagged `tag:team-device` (that exact
  string — it is the tag `policy.hujson` fences, and a key minted with any other tag lands the
  device outside every rule that was written to contain it), non-reusable, non-ephemeral, then the
  holder runs one `tailscale up --auth-key=...`.
- **Hardening ttyd itself.** Putting `-c user:pass` on ttyd, or moving `/term` to its own port so
  the ACL can separate it from `/deck`, changes how Zero reaches his own machine from his own
  phone. It is a business call, filed in `.claude/skills/modus/PENDING-ARMS.md`, and the ACL
  contains the blast radius without it.
- **The `*:18789` all-interfaces bind** on Pro's OpenClaw Control, and the **public Funnel on
  8443**. Both are real and neither is fixed by this policy — Funnel traffic bypasses ACLs
  entirely, and a wide bind is a service-config issue, not a network-policy one. Tracked as
  follow-ups.
