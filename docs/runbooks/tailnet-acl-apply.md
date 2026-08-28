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

Green means the file is structurally deny-by-default, names the shell route, keeps
`tag:team-device` out of every `src`, grants no root over Tailscale SSH, and carries deny-tests. It
does **not** mean Tailscale accepts it — only the console can say that.

## 2. Preview (dry run) in the console

1. Open <https://login.tailscale.com/admin/acls>.
2. **Copy the current policy out first** and save it to a scratch file outside the repo. This is
   your rollback, and it is the only copy — Tailscale keeps a version history in the console, but
   having the text in hand is faster under pressure.
3. Paste the contents of `infra/tailscale/policy.hujson` into the editor. **Do not save yet.**
4. The editor validates as you type: syntax errors, unknown tags, and invalid `dst` shapes surface
   inline. It also runs the `tests` block. Read every message.
   - If it rejects `autogroup:*` in a `dst`, that is the known trap: an autogroup as a destination
     is limited to `autogroup:internet` / `autogroup:self`. Fix the file in the repo, re-run step
     1, and re-paste — never patch only in the console, or the repo and the tailnet diverge (the
     HOME-fork disease, applied to network policy).
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

## 5. Verify the denies actually deny (guilt) — the load-bearing step

An accept-only verification is not a verification: it can report success and can never report
failure. That is precisely how the 2026-05 laptop handoff "verified" retained access with
`ssh air 'tailscale status'` — a command that answers green from M5 no matter what, because both
`air` and `air-ts` resolve to M5 on Pro.

Run this **from Mini**, a node the policy denies `pro:443`:

```bash
# GUILT TEST. Success here means the policy did NOT take effect.
curl -sk -m 8 -o /dev/null -w '%{http_code}\n' https://nuzantara.tail461666.ts.net/term
```

- **Expected (policy applied): the command times out** — `curl: (28)`, or exit 7 / `000`. The
  packet filter drops the connection, so there is no HTTP status at all.
- **`200`: the policy is NOT in effect.** Either it was not saved, or Mini matched a rule you did
  not intend. Stop and re-read the `acls` block before doing anything else.

An HTTP `403` would also be a failure of this test, not a pass: 403 means the connection was
established and something above the network layer refused it. The ACL's job is that the TCP
connection never completes.

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
