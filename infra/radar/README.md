# iQOO RADAR node

The iQOO 15 is a **reactive pager and receipt console**, not a third log host and
not a merge/deploy machine. Pro and Mini retain raw logs, credentials, client
data, detection and repair capability. The phone receives only closed-schema
Incident Capsules.

## Data boundary

The relay reads the existing `tg_notify.py` P0 spool locally and emits a finite
vocabulary:

- node: `pro`, `mini`, `other`;
- category/source class: allow-listed enums;
- timestamp, repeat count, transport state;
- deterministic IDs derived from enum labels, timestamp and byte offset;
- the response route and approval policy.

It never serializes or hashes `text`, `key`, a raw producer name, a phone,
email, client/company name, credential, command line or log tail. The Termux
receiver rejects unknown fields, free text, remote commands and payloads over
8 KiB. It keeps at most 250 capsules with mode `0600`.

## Response route

1. Existing deterministic detectors and the Telegram gateway establish the P0.
2. Existing bounded healers on Pro/Mini remain the only repairers
   (`claude-sonnet-5`, allow-listed and reversible actions).
3. A separate medium reviewer reviews small/medium changes.
4. High-risk security, data-integrity and billing incidents route to Opus.
5. Irreversible production, security, payment, authentication and data actions
   remain owner-gated.

RADAR does not merge, deploy or perform a repair. It makes incident state
visible and preserves a safe receipt while the source node handles the case.

## Phone install

Stage `infra/radar/iqoo/` on the phone and run `./install.sh`. The runtime files
are installed below `~/.local/`; the boot hook is staged at
`~/.termux/boot/10-nuzantara-radar`.

Termux:Boot must be installed from the same signing source as Termux and opened
once. Until then the hook is harmlessly staged and `sshd` continues to work in
the current Termux session. Termux:API is optional; without it, capsules still
arrive and are visible through:

```sh
radar status
radar list 10
radar show <incident-id>
radar health
```

## Restricted relay identity

Generate one dedicated Ed25519 identity per source node. Append only its public
key to the phone's `~/.ssh/authorized_keys` with this forced command (replace
the placeholder key):

```text
restrict,command="/data/data/com.termux/files/home/.local/libexec/nuzantara-radar-receive" ssh-ed25519 AAAA... nuzantara-radar-pro
```

Before arming, audit every existing line in `authorized_keys`. Every relay key
must carry both `restrict` and the exact forced command above. Inventory any
separate unrestricted administrator key explicitly; never point a relay wrapper
at that key. Pro and Mini use distinct restricted keys, so either source can be
revoked without affecting the other.

The private key never leaves its Mac. Pin the phone host key in
`~/.ssh/known_hosts_iqoo_radar`; the production relay uses
`StrictHostKeyChecking=yes`, disables the global host-key file and never uses
`accept-new`. It invokes OpenSSH with `-F /dev/null`, so user-level SSH config
cannot inject a proxy, alternate identity or another host-key policy. A source
node can therefore reach only the explicitly pinned iQOO receiver through this
path.

## Relay behavior

`scripts/iqoo_radar_relay.py` consumes only:

- sent P0 records from `archive-p0.jsonl`;
- unsent/budget-held P0 records from `pending.jsonl`.

`archive-p0.jsonl` is the append-only primary source. `pending.jsonl` is a
best-effort secondary view that the Telegram gateway may replace by atomic
rename; a relay holding the previous inode can finish that snapshot and sees
the replacement on its next run. A pending-only item can therefore be delayed
one interval, never treated as durable evidence in place of the archive.

The first run places each cursor at EOF, preventing a historic alert flood.
Afterward, a cursor advances only after a valid receiver receipt. Delivery
retries use the same incident ID, and the phone treats duplicates idempotently.
An unfinished final JSONL line is left for the next pass instead of being lost.

The relay distinguishes two failure classes:

- exit `75`: the mobile receiver is busy, sleeping or temporarily unreachable;
  the cursor stays in place and the source heartbeat records healthy deferred
  delivery, so the healer does not restart a healthy relay in a loop;
- exit `70`: receiver rejection or a local software/state/security/configuration
  fault; the source heartbeat is an error and remains eligible for
  investigation.

The receiver accepts exactly one JSON document per SSH stream, reads across
fragmented SSH packets up to the 8 KiB ceiling and recovers a lock left behind
when Android kills Termux, even if Android later recycles its PID. SSH receipts
are captured in temporary files and at most 4 KiB per stream is read into relay
memory. Missing runtime dependencies fail closed. `radar health` reports the
local Termux/SSHD/wake-lock/dependency state only; end-to-end Mac-to-phone
reachability is proven by the source relay receipt, not by that local command.
