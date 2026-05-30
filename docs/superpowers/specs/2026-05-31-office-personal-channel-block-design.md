# Office Personal-Channel Block — Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to turn this design into a task-by-task implementation plan.

**Date:** 2026-05-31
**Owner:** Antonello (Zero)
**Status:** Design approved by operator — pending spec review → implementation plan
**Origin:** Started on "corporate Mac config" (`scripts/profile-monitor/`). Refocused twice through brainstorming. Final target, in operator's words: _"arginare nelle ore di ufficio computer e un potenziale numero personale"_ — block, on the corporate computer, the personal WhatsApp/Telegram **web** channels an employee would use to run business off-books.

---

## Problem statement (final)

While on the **corporate computer in the office**, an employee can open **WhatsApp Web / Telegram Web** in the browser with their **personal number** and run clients off-books. wa-mirror only sees the **company** numbers, so this personal-web channel is invisible to it. The operator wants to **block** (not merely detect) these personal web channels on the corporate machine.

This is the structural/preventive complement to the open Surya case (`case-surya-black-tide-vanguard-2026-05-14`). The Surya investigation (personal phone, GetContact on Receh, etc.) is a **separate manual track** and out of scope here.

## Goal

Make `web.whatsapp.com`, `web.telegram.org` (and a short extensible denylist of personal messenger web apps) **unreachable from the corporate computer**, in a way that:

- is **cross-OS** (Mac Apple Silicon, Mac Intel, Windows) without per-OS agent code,
- **cannot be removed** by the employee (standard user on a `balizero`-owned profile),
- **follows the device** (works even off the office WiFi — required because the office router is **ISP-locked**, see Constraints).

## Constraints / decisions captured

- **Office router is ISP-managed** → network-level DNS block at the router is **not available**. This rules out the original NextDNS-on-router plan (Task 1 of the 2026-05-16 IT plan). Forces a **per-device** DNS profile.
- **All staff on the same office WiFi today**, but per-device coverage is chosen anyway because (a) the router is locked and (b) it survives a WiFi change.
- **Web channels only** (operator choice): blocks WhatsApp/Telegram **Web**, not the installed Desktop apps. Desktop-app blocking is a documented future extension, not in this scope.
- **Block, not detect** is the primary action. A private operator-only log digest ("who tried to open WA Web") is an **optional** secondary, additive later.
- **No device agents, no browsing capture beyond the messenger denylist, no team-visible surface** (UU PDP / UU Ketenagakerjaan — consistent with the 2026-05-14 rejection of the "Matrix dashboard").

## Verified facts (on disk 2026-05-31)

- `/usr/bin/profiles` present; macOS **26.5** → supports a NextDNS **DNSSettings `.mobileconfig`** (DoH) payload. Mac delivery path confirmed.
- `scripts/profile-monitor/mac-client/setup-balizero.sh` already provisions a macOS **`balizero` Standard-user profile** and installs a LaunchAgent + immutable file. It is the natural carrier for the `.mobileconfig` install step. **This is the recovered value of the May work: the `balizero` profile exists to make the DNS filter non-removable by a standard user — not for presence tracking.**

## Architecture

```
NextDNS profile "BaliZero-Office" (free tier)
  └─ Denylist: web.whatsapp.com, web.telegram.org, webk/webz.telegram.org (+ extensible)
  └─ Logs ON (30d retention)  ── optional ──► weekly private digest → Telegram chat 1125336968
        │
        │  delivered PER-DEVICE as a locked DNS profile
        ├─ macOS (Silicon + Intel): NextDNS .mobileconfig installed on the `balizero` profile
        │     (standard user cannot remove a profile installed by admin)
        └─ Windows (Adit): NextDNS desktop client / native DoH, admin-locked
```

## Components

### C1 — NextDNS profile (config, no code)

- Account `zero@balizero.com`, profile `BaliZero-Office`, free tier (300k queries/month).
- Denylist initial set:
  | Channel | Domains |
  |---|---|
  | WhatsApp Web | `web.whatsapp.com` |
  | Telegram Web | `web.telegram.org`, `webk.telegram.org`, `webz.telegram.org` |
  | (extensible) | add a line per channel as needed (Signal web, Messenger, etc.) |
- Logs ON, retention 30 days (feeds the optional digest).

### C2 — macOS delivery (`.mobileconfig`)

- Generate the NextDNS `.mobileconfig` (DNSSettings / DoH payload) from the NextDNS setup page for `BaliZero-Office`.
- **Extend `setup-balizero.sh`** with a step that installs it on the `balizero` profile via `profiles` (or double-click), so a **standard** user cannot remove it.
- Works on both Apple Silicon and Intel (it is a profile, not the arm64 Swift binary — so the Intel gap that blocked profile-monitor does **not** apply here).

### C3 — Windows delivery (Adit)

- Install the **NextDNS desktop client** (or configure native DoH) pointed at `BaliZero-Office`, under an admin-locked account so Adit (standard user) cannot disable it.
- No custom code; vendor installer + config.

### C4 — Optional private digest (additive, later)

- Weekly script pulls NextDNS blocked-query log via API → Telegram **chat `1125336968` only** → "N attempts to open web.whatsapp.com this week, by device X". Confirms the block is biting and surfaces who keeps trying. Built only if the operator wants the visibility; the block works without it.

## Honest limits (state them, don't hide them)

- **Web only.** WhatsApp/Telegram **Desktop apps** bypass the web-domain denylist. Mitigation (future): block the apps' API endpoints in NextDNS, or keep the apps off the `balizero` profile. Out of scope per operator choice.
- **Removable if the employee has admin.** The non-removability depends entirely on the employee being a **Standard** user on a profile owned by the operator. If they are local admin, they can delete the profile. The `balizero` Standard-profile model is therefore load-bearing.
- **Does not touch the personal phone on mobile data.** That channel (the actual Surya vector) is unreachable by any device/network control here — it is the separate investigative track.
- **DoH on the device could be undone by a savvy user** changing browser-level DNS or using a VPN. This is a deterrent against casual off-books use on the corporate machine, not a hard seal against a determined insider. Stated so expectations are calibrated.

## What this explicitly does NOT build

- ❌ No device agent on any OS (the May `profile-monitor` Swift daemon is untouched; presence is a separate concern).
- ❌ No client-theft data detector (R1–R4 from an earlier draft) — **wa-mirror already covers ghost-number / off-books detection**; that detector was redundant and was discarded.
- ❌ No NextDNS-on-router (router is ISP-locked).
- ❌ No browsing/productivity logging beyond the messenger denylist.

## Testing / verification

- After C2 install on a test Mac `balizero` profile: `web.whatsapp.com` and `web.telegram.org` fail to load; a non-listed site loads normally; the standard user **cannot** remove the profile (verify via System Settings → Profiles, no "−" available).
- After C3 on the Windows box: same two domains blocked, standard user cannot disable the NextDNS client.
- NextDNS dashboard shows the blocked queries in the logs (confirms enforcement + feeds optional C4).

## Sequencing (for the plan)

1. C1 NextDNS profile + denylist (config, ~30 min) — gives an immediately testable block on any device pointed at it.
2. C2 macOS `.mobileconfig` + `setup-balizero.sh` extension (the one code change, small).
3. C3 Windows client for Adit.
4. C4 optional digest (only if operator wants it).
