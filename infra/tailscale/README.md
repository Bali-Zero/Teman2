# `infra/tailscale/` — the tailnet, as measured

The tailnet had no representation in this repo before 2026-08-11: its shape lived only in a
memory file, and its access-control policy lived only in the Tailscale admin console at its
factory default. This directory is the repo-side record and the policy as code.

| File | What it is |
|---|---|
| `policy.hujson` | The ACL, **proposed, not yet applied**. Applying it is `operator[GUI]`. |
| `enroll-team-device.md` | Runbook to bring a team member's company laptop into the tailnet. |
| `../../docs/runbooks/tailnet-acl-apply.md` | How to apply the ACL, verify it (both directions), roll it back. |
| `../../scripts/tests/test_tailnet_acl_deny_by_default.py` | CI guard: the ACL stays deny-by-default and keeps naming `/term`. |
| `../../scripts/verify_tailnet_node.sh` | Proves a node is present **and is not the machine asking**. |

`policy.hujson` was rewritten 2026-08-29. The first draft granted
`antonellosiano@gmail.com -> antonellosiano@gmail.com:*` — every port on every owned device, which
reproduced the flat default among the fleet and left `pro:443` (the shell port) open to all six
nodes. It now carries a per-direction, per-port matrix derived from what the repo actually
connects to, with the evidence cited on each rule.

This repo is **public**, so nothing here names which teammate holds which device, or carries
anyone's contact details or performance data. That mapping lives in private fleet memory. The
mechanism is person-neutral on purpose — `tag:team-device` is reusable for the next one.

## Measured state — 2026-08-11, from M5

Six nodes, all owned by `antonellosiano@gmail.com`. Read with `tailscale status --json` and
`tailscale debug netmap`.

| MagicDNS name | Magic IP | OS | Note |
|---|---|---|---|
| `air-m5-2` | 100.110.186.116 | macOS | M5. Reports `HostName: "Air-M5"` — the names differ. |
| `nuzantara` | 100.107.22.111 | macOS | Pro. Runs `serve` + `funnel`, see below. |
| `mini-pro2` | 100.93.236.6 | macOS | Control-plane reachable, **no usable inbound path** — see below. |
| `iphone-14` | 100.113.83.92 | iOS | `HostName: "Iphone 14"`. |
| `iphone175` | 100.77.16.7 | iOS | `HostName: "localhost"`. |
| `apple-vision-pro` | 100.97.28.18 | iOS | `HostName: "localhost"`. |

**No team member's laptop is in this tailnet.** The 2026-05-02 decision to hand a company MacBook
Air M4 to a team member while retaining remote access was never armed on the network side: the
physical handoff happened, the access did not.

### Identity is `DNSName`, never `HostName`, never an ssh alias

Two of six nodes report `HostName: "localhost"`, and M5 reports `Air-M5` against a DNSName of
`air-m5-2` (a collision suffix). So `HostName` both fails to name real nodes and can name the
wrong one. `StableID`/`ID` and the first label of `DNSName` are the identity.

An ssh alias is weaker still. On Pro, **both `air` and `air-ts`** resolve to M5
(`Air-M5.local` / `100.110.186.116`) — and `air` is *correct* there, because
`infra/fleet/nodes.json` declares `ssh_alias: "air"` for the m5 node. The problem is that the
2026-05 laptop-handoff runbook used those names to mean the *handed-over* machine and verified
retained access with `ssh air 'tailscale status'`. That command cannot fail: it answers green from
M5. Use
`scripts/verify_tailnet_node.sh`, which returns a distinct exit code (4) for "that name is the
machine you are asking from".

### What a plain member device inherits today

The packet filter is a single rule: every node → `0.0.0.0/0`, ports `0-65535`, TCP+UDP+ICMP.
Probed from M5, on Pro:

| Port | State | What it is |
|---|---|---|
| 22 | open | OpenSSH, key-gated |
| 443 | open | `tailscale serve`, **tailnet-only**, no authentication (below) |
| 6379 | open | Redis — replies `-NOAUTH Authentication required.`, so gated |
| 18789 | open | OpenClaw Control (also behind `serve /`) |
| 5432 | closed | Postgres not on the tailnet interface |

`tailscale serve status --json` on Pro, port 443, **tailnet-wide and unauthenticated**:

```
/        → 127.0.0.1:18789   OpenClaw Control
/term    → 127.0.0.1:7681    ttyd -p 7681 --interface 127.0.0.1 -W zsh
/deck    → 127.0.0.1:18890
/cinema  → 127.0.0.1:18891
```

`-W` is *writable* and there is no `-c` credential flag; `GET /term` answered **200** from
another node. **Any device in this tailnet has an unauthenticated, writable zsh shell on Pro as
user `nuzantara`** — the host with the wa-mirror raw PII, the CRM runtime and
`~/.nuzantara-secrets.env`. This is why a teammate's laptop must join **tagged**, and why
`policy.hujson` must be applied *before* it joins.

That shell is fine while every node is Zero's own, which is the case today. Hardening ttyd
itself (`-c user:pass`, or dropping `/term` from `serve`) changes how Zero reaches his own
machine from his own phone, so it is his call, filed in the ledger rather than done here.

### Public vs tailnet-only

Only **`:8443`** is public. `AllowFunnel` is `{"nuzantara.tail461666.ts.net:8443": true}` and it
proxies `127.0.0.1:8789` = `uvicorn openclaw_whatsapp_bridge:app` — the WhatsApp webhook, public
by design because Meta must reach it. `GET /` on the public path returns 404. Public DNS
resolves the name (`dig @1.1.1.1` → 103.84.155.153/217), which is expected when Funnel is on.

`:443`, the one carrying `/term`, is **not** funnelled. The web shell is not on the internet.

### Tailscale SSH: maximal grant, currently latent

`SSHPolicy` in the netmap is one rule: `action: accept`, agent + local + remote port forwarding,
principals = all 12 node addresses, `sshUsers {"*": "=", "0": "", "root": "root"}` — i.e. any
user **including root**, with no re-authentication.

It is latent: no node runs the Tailscale SSH server. `RunSSH: false` on M5; Pro advertises no
SSH host key (`tailscale ssh nuzantara@nuzantara` → "No ED25519 host key is known"); Mini could not
be measured either way, for the reason in the next section. One `tailscale up --ssh` anywhere arms it. `policy.hujson` drops the root
grant while it still costs nothing.

### Mini: not powered off, not a broken sshd — a very poor network path

Two readings were considered and the first was wrong, so the reasoning is recorded rather than just
the conclusion. (An earlier draft of this file also claimed a ledger row had recorded Mini as
*powered off*. There is no such row — that was this session's own recollection, and grepping for it
matched only `off` inside unrelated words. Removed rather than kept as colour.)

The first reading was **sshd broken**: `ssh nuzantara@100.93.236.6` returns
`kex_exchange_identification: read: Connection reset by peer`, reproducibly 3 of 3, from M5 *and*
from Pro. But sshd is not the organ. Measured:

| Probe | Mini | Pro (control) |
|---|---|---|
| `tailscale ping` | pong, **1.32 s**, 1 of 3 replies | pong, **7 ms** |
| Endpoint | `180.254.227.76` | `192.168.0.15` / `59.153.130.164` |
| tailscaled's own peerapi | no response (`http=000`) | `http=200` |
| Ports 22 / 5900 / 6379 / 11434 / 443 | TCP accepted, **no banner**; on a later sweep all read closed | serves normally |

Two unrelated services (sshd and Screen Sharing) failing identically, tailscaled's *own* peerapi
failing while Pro's answers, a 190× RTT gap, and per-port readings that do not reproduce between
sweeps: that is a **network path**, not a service. Mini sits on a different public address from
both other machines, and a 1.3 s RTT with loss is enough on its own to time out a TCP banner
exchange. This is cicatrix family #8 (network flap), not #2 (exists ≠ armed).

Two consequences worth stating:

- Any per-port reading for Mini in this document is **not evidence a service is or is not there**.
  An earlier draft of this file listed Mini's 6379/11434 as open; that was a transient accept, and
  the later sweep read the same ports closed.
- Mini's **outbound** path works: the healer-tick ledger row dated today landed from Mini via
  PR #4028 at 02:54. Reachability is asymmetric — it reaches out, nothing reaches in — which is the
  signature of a NAT/relay path, not of a dead machine or a dead daemon.
- A ledger row that waits on "restore Mini's SSH" is therefore aimed at the wrong organ. `ssh mini`
  succeeding is still the right proof; no amount of sshd work will produce it.

### No API token on the fleet

There is no Tailscale API token in `~/.nuzantara-secrets.env`, in `.env.master`, or in the
keychain, and the CLI cannot read or write ACLs, create auth keys, or rename devices. Every
change in this directory therefore lands through the admin console — a genuine GUI-only surface,
declared as `operator[GUI]` in the ledger rather than left implicit.
