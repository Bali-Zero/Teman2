# Enrolling a team member's laptop into the tailnet

For a company-owned laptop that a team member uses day to day, where Bali Zero keeps remote
support access to the machine. This restores the network half of the 2026-05-02 laptop-handoff
decision ("the machine goes to the team member, Bali Zero retains remote access if needed"),
which was never armed: as of 2026-08-11 no such machine is in the tailnet at all.

Person-neutral by design. This repo is **public**, so which teammate holds which node is recorded
in private fleet memory, not here. Substitute the real hostname where this file says
`team-laptop-01`.

**Read `README.md` in this directory first.** It carries the measurement this runbook depends on,
including the one fact that dictates the order of the steps below.

## The constraint that fixes the order

Any device that joins this tailnet as a plain member device currently gets an unauthenticated,
writable zsh shell on Pro as user `nuzantara`, via `https://nuzantara.tail461666.ts.net/term`
(`ttyd … -W zsh`, no credential flag, measured 200 from another node). Pro holds the wa-mirror raw
PII, the CRM runtime, and `~/.nuzantara-secrets.env`.

So: **the policy goes in before the laptop does.** Enrolling first and restricting afterwards
leaves a window in which the laptop holds that shell, and "we'll tag it in a minute" is exactly
the shape of a window nobody closes.

This is not a judgement about any person. It is that the CRM's own RBAC gives team members only
their `assigned_to` rows, and raw network reach to Pro would route around it at the network layer;
UU PDP / SYMBIOSIS Law 2 have no convenience exception.

## What each step needs, and who can do it

| Step                               | Surface                     | Owner                                              |
| ---------------------------------- | --------------------------- | -------------------------------------------------- |
| 1. Apply the ACL                   | Tailscale admin console     | `operator[GUI]` — no API token exists on the fleet |
| 2. Mint a tagged auth key          | Tailscale admin console     | `operator[GUI]`                                    |
| 3. Run one command on the laptop   | a machine outside the fleet | `operator[physical]` — its holder                  |
| 4. Verify                          | any fleet machine           | the session                                        |
| 5. Pin the support path in the ACL | console + repo              | `operator[GUI]` + the session                      |
| 6. Add a **distinct** ssh alias    | Pro / M5                    | the session                                        |

Steps 4 and 6 are the session's and are done the moment step 3 lands. Steps 1–3 are the two
categories that are genuinely not a diff: a GUI-only surface, and a machine that is not in the
fleet.

---

## Step 0 — look at the console's device list first · `operator[GUI]`

Admin console → **Machines**. If a stale device from this machine is still listed (the laptop in
question was previously a fleet machine and may have an old, key-expired entry), **delete it before
minting the key.**

Two reasons, both measured rather than assumed:

- Re-enrolling while an old entry survives does not reconnect it — Tailscale mints a fresh node and
  **appends `-1` to the hostname on collision**. That is exactly how this tailnet ended up with
  `iphone-14-pro-max-1` next to a dead `iphone-14-pro-max`, and how M5 answers to DNSName
  `air-m5-2` while calling itself `Air-M5`. A `-1` suffix would defeat the whole point of pinning
  the name in step 3.
- **The CLI cannot check this for you.** `tailscale status` reports _this node's peers_, and there
  is no device-listing subcommand at all (`tailscale devices` → `unknown subcommand`, verified
  2026-08-11 on v1.98.5). So the console list is the only authoritative device inventory, and a
  clean `tailscale status` from a fleet machine is not evidence that the console is clean.

## Step 1 — apply the ACL · `operator[GUI]`

Admin console → **Access Controls** → replace the policy with `infra/tailscale/policy.hujson`
→ **Save**. The console validates the `tests` block on save; if a test fails it refuses, which is
why the tests ship with the policy.

Expected (REWRITTEN 2026-08-29 — the policy no longer reproduces flat reachability, so the old
text here was describing a draft that no longer exists): the six existing nodes keep only the
flows the repo has a cited consumer for — `pro -> mini` 22/6379/11434/8990, `mini -> pro` 22,
`pro -> m5` 22, `m5 -> pro` 22/443, `m5 -> mini` 22/4317, and the three iOS devices -> `pro:443`.
Anything else between Zero's own machines is now denied, including UDP and ICMP (every rule
carries `"proto": "tcp"`), so a plain `ping` between nodes stops working while `tailscale ping`
keeps working. Two intended differences beyond that: Tailscale SSH loses its root grant (latent
today, since no node runs the Tailscale SSH server), and `mini` no longer reaches `pro:443`.
Verification, including the positive/negative control pair, is `docs/runbooks/tailnet-acl-apply.md`.

If the console refuses the policy, the message is the ground truth, not this file: nothing in the
fleet can validate a Tailscale policy offline (no API token, no local validator), so the grammar
here was checked against the published ACL syntax reference and by a cross-family review, and no
further. One construct is worth knowing because a draft of this policy had it wrong:
`autogroup:member` is fine in `src`, and is also permitted as an ordinary ACL `dst` — but NOT as
an `ssh` `dst`, where the value must be a user, a tag, or `autogroup:self`. (An earlier version of
this paragraph called it invalid as any `dst`; that was overbroad.)

### Known casualty of this policy — decide it BEFORE you enrol · `operator[business]`

`scripts/profile-monitor/` expects an employee's Mac to POST checkout events to
`http://100.107.22.111:9099/checkout` (`mac-client/profile-monitor.swift:12`; the wrapper listens
on 9099, `wrapper.py:44`), and `mac-client/setup-balizero.sh` is the documented procedure for
joining such a Mac to this tailnet. **Under `policy.hujson` a `tag:team-device` Mac cannot reach
that port.**

CORRECTED 2026-08-29: this used to say the failure is "silent" and the POST "fire-and-forget".
Both are false. `profile-monitor.swift` sets `timeoutInterval = 5` (`:65`), waits on a semaphore
up to 6s (`:78`), and logs `POST_FAIL` with the error inside `if let error` (`:70`) or `POST_OK`
with the HTTP status otherwise (`:73`). A POST the packet filter drops is a transport error, so it
**is** recorded — to `~/Library/Logs/balizero-profile-events.log` (`:13`), **on the employee's own
Mac**. So the checkout evidence exists; it is on the far side of the fence this policy raises. The
accurate word is **invisible to us**, not silent — and that changes the remedy: recovering a
missed checkout means reading a log on someone else's laptop, which is a consent question, not an
unprovable negative.

This is deliberate, not an oversight — but state the cost precisely, because it is the owner's
decision and an inflated cost biases it. What fences the shell is the **absence of any grant to
`pro:443`**; ACL rules are independent allow entries, so a rule granting `tag:team-device -> pro:9099`
would leave `pro:443` exactly as fenced. The real cost is narrower and lives in the guard, not in
Tailscale: "a team device is never a SOURCE" is the bright line this repo mechanically enforces
(`TEAM_TAG_AS_SOURCE`), and port-scoping it would mean teaching that check an exemption — turning
a rule anyone can check by eye into one that needs reading. That is a genuine cost, and it is a
smaller one than "the single property keeping the laptop off the shell".
The choice is the owner's: grant `tag:team-device -> pro:9099` as one named exception (with its own
deny-tests for every other port), or move that client off the tailnet. Decide it before enrolling,
because after enrolment the wrong answer is invisible.

## Step 2 — mint a tagged, single-use auth key · `operator[GUI]`

Admin console → **Settings → Keys → Generate auth key**:

- **Tags**: `tag:team-device` ← the entire mechanism, and it must be this exact string, because
  it is the tag every containing rule in `policy.hujson` names. Without it the laptop joins as a
  member device, lands outside every rule written to fence it, and inherits `autogroup:member` —
  which is what the Tailscale SSH rule grants.
- **Reusable**: off.
- **Ephemeral**: off (an ephemeral node disappears when it goes offline; a laptop is not that).
- **Expiration**: the shortest that fits the handover window. This is the _key's_ lifetime, not
  the device's — a tagged device's node key does not expire, so the laptop will not silently drop
  off the tailnet months later.

Because the key carries the tag, the device is owned by the **tailnet**, not by a person. The
holder never signs into a Tailscale account, and no credential of Zero's is shared. That is a
better outcome than the original runbook's "keep Tailscale on the antonellosiano profile", which
would have left Zero's session signed in on a machine he no longer holds.

The key is a secret: send it over the holder's business WhatsApp line, delete it after use, and
never paste it into a commit, a transcript, or a shared doc. Generate it immediately before step 3
so its window is short.

## Step 3 — one command on the laptop · `operator[physical]`

After installing Tailscale from the App Store:

```bash
sudo tailscale up --auth-key=tskey-auth-XXXX --hostname=team-laptop-01
```

- `--hostname=` fixes the MagicDNS name, which is the identity everything downstream keys on.
  Do not let it default to the machine's own hostname: at handoff the machine called itself
  `Nuzantara-9` (per the handoff record — not re-verified since, because nothing in the fleet can
  reach it), and a node named after the fleet's own scheme is the exact collision this runbook
  already suffered once (see README, "Identity is `DNSName`").
- Do **not** pass `--ssh` (it would arm the Tailscale SSH server on the laptop).
- Do **not** pass `--shields-up` (it blocks inbound connections and would defeat the support path
  this whole exercise exists for).

## Step 4 — verify, in a way that cannot answer from the wrong machine

From Pro or M5:

```bash
bash scripts/verify_tailnet_node.sh team-laptop-01
```

Expect `OK: … is a live peer of this tailnet — team-laptop-01.tail461666.ts.net  100.x.y.z …`.

Before step 3 the same command exits **3** (`is NOT in this tailnet`) — that is its output today,
and it is the honest baseline. It never exits 0 for a name that resolves to the machine asking:
that case is exit **4**, with its own message. The old runbook's check (`ssh air 'tailscale
status'`) is precisely the thing that cannot distinguish those, which is how it certified M5 for
three months.

Then assert the support path end to end, rather than assuming the ACL did what it says:

```bash
bash scripts/verify_tailnet_node.sh team-laptop-01 --ssh <local-user>   # we can reach it
```

And confirm the reverse is closed — ask the holder to run this on the laptop; it must **fail**:

```bash
curl -m 8 -o /dev/null -w '%{http_code}\n' https://nuzantara.tail461666.ts.net/term
```

A timeout or connection refused is the pass. A `200` means the device is not tagged, or the policy
was not applied, or it was applied after the join — check `tag:team-device` on the device in the
console before anything else.

## Step 5 — pin the support path in the ACL

CORRECTED 2026-08-29: this step used to say the accept direction toward the laptop could not be
tested until the node existed, "because ACL tests need a concrete destination host". That was
false — a test destination may be a TAG — so `policy.hujson` now ships the tag form already, and
the support path is asserted before any laptop joins:

```hujson
{ "src": "m5", "accept": ["tag:team-device:22", "tag:team-device:5900"] }
```

Once a real node exists, add the concrete-host form alongside it. Note the source is `m5` (and
`pro`), not the whole owner identity — those are the only two sources the support rule grants:

```hujson
"hosts": { …, "team-laptop-01": "100.x.y.z" },
"tests": [
  { "src": "m5", "accept": ["team-laptop-01:22", "team-laptop-01:5900"] },
  …
]
```

Save in the console, commit the same edit here, and the property is enforced from then on instead
of remembered.

**Adding that `hosts` entry does NOT require editing the guard, and that is deliberate.**
`scripts/tests/test_tailnet_acl_deny_by_default.py` pins `hosts` — because it is the table the
guard resolves all of its other anchors through, and an unpinned one let a re-pointed alias hand
a foreign machine the shell while every check stayed green — but it pins it in an
**additive-tolerant** way: the six fleet aliases may not be re-pointed or deleted, and every
value must be a bare IPv4 literal, while new entries are allowed. Adding
`"team-laptop-01": "100.x.y.z"` satisfies both clauses and the guard stays green. This is
asserted, not merely intended: `test_enrolling_a_team_laptop_keeps_the_guard_green` performs
exactly this edit and requires zero findings, so a future tightening of the pin cannot silently
break this step — it would have to delete that test.

Two things that WILL turn it red, both correctly: giving the new entry anything other than a bare
dotted-quad IPv4 (a CIDR, a v6 address, a DNS name), and adding the `acls` grant without the
matching accept-test — the guard requires every grant to be asserted by an accept-test from its
own source, so add the accept-test above in the same commit.

## Step 6 — a distinct alias, never `air` or `air-ts`

Both of those already point at M5 on Pro, and `air` is _correctly_ M5's per
`infra/fleet/nodes.json`. The laptop gets a name that cannot be confused with a fleet node:

```
Host team-laptop-01
    HostName 100.x.y.z
    User <local-user>
```

Do not add it to `infra/fleet/nodes.json`. That file is the roster of nodes that can **host an
implementation lane**; a support destination is not a compute node, and listing it there would
offer it to `scripts/fleet_dispatch.py`.

## Step 7 — audit what of OURS is still running on that machine

Only reachable once steps 1–4 land, and it is the first thing worth doing with the access, not an
afterthought. If the laptop is a former fleet machine, the handoff procedure's own steps were
recorded but never confirmed executed — so none of the following is known to have happened:

- Bali Zero LaunchAgents unloaded (e.g. a daily indexing-sweep cron). **A company cron still firing
  on a teammate's personal-use laptop, monitored by nothing, is its own problem** — it is not
  covered by any of the fleet's cron sensors, which only know the three fleet machines.
- `postgresql@17` and `redis` (installed for those crons) stopped.
- Ollama models removed (~4.4 GB of disk that is no use to the holder).
- Whether a local admin account was created for the holder at all, and — if it was created with the
  password that the handoff runbook carried in cleartext until 2026-08-11 — **that password
  changed.** The literal has been redacted from the runbook and the file tightened to `0600`, but
  redacting a record does not rotate a credential.

Record the outcome in private fleet memory, not here.

## What the holder is told, and what we do not do

Carried forward from the original handoff decision, unchanged: the machine belongs to Bali Zero
and is lent for work; admin access is retained for emergencies; there is no silent monitoring.
Screen Sharing shows the user a "screen is being shared" indicator and that is deliberate — do not
look for a way around it. Send this in the holder's own language.

With this policy the retained access is also _smaller_ than the original runbook's: we can reach
the laptop on 22 and 5900, and the laptop can reach nothing of ours.
