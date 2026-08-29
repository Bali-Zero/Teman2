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

Green means, clause by clause and each one actually enforced by `audit_policy()`: no wildcard or
unresolvable source or destination anywhere; every node spelling collapsed to its IP before
judging, with Pro's own IP pinned so the anchor cannot be moved by renaming an alias; the shell
port reachable only from an explicit allowlist of named devices; `tag:team-device` in no rule's
`src`; the `ssh` block allowlisted on all three axes, so no root and no wildcard user; deny-tests
present including team → `pro:443`; and the `SHELL-ROUTE` block still naming `/term`.

It does **not** mean Tailscale accepts the file — only the console can say that — and it is not a
Tailscale evaluator: it does not expand `group:` membership and takes no position on selectors it
has never seen beyond refusing them.

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

> **If Save is REFUSED, look here first — one assertion is `(unverified)`.** The `tests` block
> asserts reachability to `tag:team-device:22` and `tag:team-device:5900` from `m5` and `pro`. No
> device currently carries that tag. Whether the console resolves an ACL test whose destination is
> a tag with **no members** cannot be determined from this repo: the fleet holds no Tailscale API
> token and there is no offline validator, so the repo-side guard cannot answer it and does not
> claim to. It is asserted deliberately — a test destination may be a tag, which is what lets the
> support direction be proven before any laptop enrols — but it is the one line in the file whose
> acceptance is genuinely unknown until this Save, and the failure lands on you, here.
>
> If Save fails naming those tests: delete the two `tag:team-device` **accept**-test entries, save
> again, and record the outcome in `infra/tailscale/enroll-team-device.md` step 5. **Expect the
> repo guard to go red when you do — measured: four occurrences of `ACL_RULE_NOT_ACCEPT_TESTED`.**
> Every ACL rule must be covered by an accept-test from its own source, so removing those two
> entries leaves the `tag:team-device` grants untested. That red is the correct and temporary
> consequence of this workaround, not a second fault to chase, and it clears when you reinstate
> the accept form after enrolment using the concrete host (`team-laptop-01:22`), which is
> unambiguous. Do NOT delete the `tag:team-device` **deny**-tests — those are the load-bearing
> half, and they reference the tag as a SOURCE, which is a different question.

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

> **One red here is intended, and will look like a guard bug if you do not know it.** If the
> missing flow needs a machine to be a **source** — a new node that must reach `mini:11434`, say,
> rather than merely be reached — the CI guard fails that rule with `UNPINNED_ALIAS_AS_SOURCE`
> until that machine's alias is added to `EXPECTED_HOSTS` in
> `scripts/tests/test_tailnet_acl_deny_by_default.py`. Only the six pinned fleet aliases may
> appear in a `src`; any other alias may be a destination only. **The fix is to add the constant,
> never to relax the clause**, and adding it is the point: a new machine acquiring reach _into_
> the fleet then shows up as a reviewed line in a diff instead of widening the tailnet silently.
> Enrolling a team device does **not** hit this — that path only ever adds a destination, which
> is why `test_enrolling_a_team_laptop_keeps_the_guard_green` still passes.

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
