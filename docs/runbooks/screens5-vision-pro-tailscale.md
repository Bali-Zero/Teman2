# Runbook — Screens 5 on Apple Vision Pro over the tailnet

Drive the three fleet Macs (M5, Pro, Mini) from the Apple Vision Pro with Screens 5 (Edovia),
using the tailnet as the transport and Screens 5's built-in Tailscale device list instead of
Screens Connect or port forwarding.

- **Status**: fleet side verified 2026-09-27 (this file, part A); visor side is `operator[GUI]`
  (part B) and cannot be done by a session.
- **ACL**: rule 6b in `infra/tailscale/policy.hujson` (added 2026-09-27). The live tailnet still
  runs the factory allow-all filter, so Screens works today regardless; the rule exists so it
  KEEPS working the day `docs/runbooks/tailnet-acl-apply.md` is executed.
- **Source study**: P3 of `research/operations/2026-08-11-apple-vision-pro-tailnet-leverage.md`.
  Sibling: `docs/runbooks/vision-deck.md` (browser surfaces on `pro:443`; this runbook is the
  full-desktop path).
- **Vendor guide**: <https://help.edovia.com/it/screens-5/connecting-anywhere/tailscale>.

## The fleet, as Screens 5 will see it

| Node               | Tailnet name (MagicDNS)              | Tailnet IP        | Screen Sharing flavour                            | Tailscale flavour              |
| ------------------ | ------------------------------------ | ----------------- | ------------------------------------------------- | ------------------------------ |
| M5 (`Air-M5`)      | `air-m5-2.tail461666.ts.net`         | `100.110.186.116` | Screen Sharing (on-demand launch)                 | App Store app, user session    |
| Pro (`Nuzantara`)  | `nuzantara.tail461666.ts.net`        | `100.107.22.111`  | Remote Management (`ARDAgent` + `screensharingd`) | App Store app, user session    |
| Mini (`Mini-Pro2`) | `mini-pro2.tail461666.ts.net`        | `100.93.236.6`    | Remote Management (`ARDAgent`)                    | App Store app, user session    |
| Vision Pro         | `apple-vision-pro.tail461666.ts.net` | `100.97.28.18`    | client                                            | visionOS app, already enrolled |

All four are enrolled under the tailnet admin account; the Vision Pro was online at verification
time. Port is the RFB default, **5900**, on every node.

## A. Fleet side — what a session verified (2026-09-27, from M5)

```bash
# RFB banner from each node over the tailnet — proves Screen Sharing answers, not just a socket
for ip in 127.0.0.1 100.107.22.111 100.93.236.6; do echo | nc -w3 $ip 5900 | head -c 12; echo; done
# -> RFB 003.889  (x3)

# Who runs Tailscale on each Mac (user process = App Store flavour, launches after login)
ps -axo user,comm | grep -i Tailscale.app | grep -v grep
# -> balizero  /Applications/Tailscale.app/Contents/MacOS/Tailscale        (M5)
# -> nuzantara /Applications/Tailscale.app/Contents/MacOS/Tailscale        (Pro, Mini via ssh)

# Guard on the ACL amendment (rule 6b + its accept/deny tests)
python3 -m pytest scripts/tests/test_tailnet_acl_deny_by_default.py -q
```

Re-run the `nc` line before any Screens session that fails: a `CLOSED` node means Screen Sharing
is off or Tailscale is not up on that Mac (see caveats), not a Screens 5 problem.

## B. Visor side — `operator[GUI]`, Zero only

Screens 5 links to the tailnet through a **read-only OAuth client**, not through the Tailscale
app on the visor. Do these once per client device (the Vision Pro; repeat on an iPhone or Mac if
Screens 5 is used from there too — links are per device, they do not sync).

1. **Tailnet ID** — <https://login.tailscale.com/admin/settings/general>, copy the _Tailnet ID_
   (a short token like `TcfXSop1q66VBYTZ`, not the `tail461666.ts.net` DNS name).
2. **OAuth client** — <https://login.tailscale.com/admin/settings/trust-credentials> → _Generate
   credentials_ → type **OAuth** → description `Screens 5 – Vision Pro` → scope **Devices → Core →
   Read** only. No write scope, no other scope. Generate, copy the **Client Secret**
   (`tskey-client-…`). It is shown once.
3. **Screens 5 on the Vision Pro** → Settings → **Tailscale** → **Link Account…** → paste the
   Tailnet ID, then the Client Secret. The device list populates from the tailnet: `air-m5-2`,
   `nuzantara`, `mini-pro2` appear with their MagicDNS names.
4. **Connect** to a node from that list. Protocol VNC / Screen Sharing, port 5900 (default).
   Authenticate with the Mac's **login user and password** (M5: `balizero`; Pro and Mini:
   `nuzantara`) — that is Screens 5's default "macOS authentication", the one Remote Management
   and Screen Sharing both honour.
5. Optional: save the three as Screens 5 _Saved Screens_ so the tailnet lookup is cached; Screens
   keeps credentials in the Keychain, the choice to store them is the owner's.

Preview before saving on apply day (`tailnet-acl-apply.md` step 2): `apple-vision-pro` →
`pro:5900` **allowed**, `apple-vision-pro` → `pro:22` **denied**.

## Secret handling

- The OAuth client secret is a credential. Scope is read-only device list, but it still names every
  node and IP on the tailnet. It lives in Screens 5's Keychain and nowhere else: not in the repo,
  not in `~/.nuzantara-secrets.env`, not in a chat, not in a memory.
- Leaked or lost → revoke it in the same _Trust credentials_ page and re-link (step 2–3). Revoking
  breaks only the device list in Screens; manual connections by MagicDNS name keep working.
- The fleet itself holds no Tailscale API token by design (`tailnet-acl-apply.md`); this client
  does not change that — it exists on the visor only.

## Caveats the fleet carries into this

- **Tailscale starts after login on all three Macs.** They run the App Store app as a user process,
  not the `tailscaled` system daemon. After a remote restart the node is off the tailnet until
  someone logs in locally — Edovia documents the same trap. Restart from Screens only when you are
  next to the Mac, or accept the blind window. Moving to the system daemon (Homebrew
  `tailscaled`, or the app's "Run as system extension" install) is an owner decision, not part
  of this runbook.
- **Mini has a legacy VNC password set** (`/Library/Preferences/com.apple.VNCSettings.txt`, dated
  2026-06-25). Screens 5 does not need it — it authenticates as the macOS user — and the legacy
  scheme is weak (8-char DES). Recommended: on Mini, System Settings → General → Sharing → Remote
  Management → ⓘ → uncheck _VNC viewers may control screen with password_. Owner call; GUI or
  `sudo`, so not done here.
- **Screen Sharing on M5 shows `state = not running`** in `launchctl` and still answers on 5900:
  launchd starts `screensharingd` on the first connection. Not a fault.
- **Apple's Mac Virtual Display does not ride the tailnet** (same Wi-Fi + same Apple ID only).
  Screens over Tailscale is the remote path; Virtual Display is the in-room one.

## Ownership

| Step                                                          | Owner                                       |
| ------------------------------------------------------------- | ------------------------------------------- |
| A. fleet verification, ACL rule + guard, this runbook         | session                                     |
| B. Tailnet ID, OAuth client, Screens 5 linking, saved screens | `operator[GUI]` (Zero)                      |
| Apply `policy.hujson` in the admin console                    | `operator[GUI]`, per `tailnet-acl-apply.md` |
| Mini legacy VNC password, Tailscale daemon flavour            | owner decision                              |
