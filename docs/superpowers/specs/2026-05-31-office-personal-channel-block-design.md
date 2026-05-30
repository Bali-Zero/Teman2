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
- **follows the device** (works even off the office WiFi — required because the office router is **ISP-locked**, see Constraints),
- is a **tamper-evident deterrent**, not a hard seal: employees are **local Admin** on the `balizero` profile, so they _can_ remove the DNS profile — but the contract forbids it and removal is **detected** (see Enforcement model). The technical layer raises the cost; the contractual + detection layers carry the enforcement.

## Enforcement model (the spine — employees are Admin)

The technical block alone is weak because employees are **local Admin** and can remove the DNS profile in seconds. The system is therefore a **three-layer deterrent**, where the technical layer is only the first:

1. **Technical (friction):** the per-device NextDNS profile blocks the web channels by default. Removing it is a deliberate, conscious act — not an accident.
2. **Contractual (accountability):** the **PKWTT contract / handbook** must contain an explicit clause: _the company DNS/security profile on the corporate device must not be removed, disabled, or bypassed; doing so is a disciplinary breach._ Without this clause, a removal cannot be contested. **This makes the contract clause a hard dependency of the design, not an HR afterthought.** The contracts were signed 2026-05-19 — if the clause is absent, an addendum is required before this system has teeth.
3. **Detection (the trigger):** removing the profile makes the device **stop appearing in the NextDNS logs**. A weekly check detects "device X has not reported to NextDNS in N days" → the operator is alerted → the contractual consequence applies. **This is what converts "removable" into "removable-but-tracked-and-sanctionable."** Without detection, layers 1–2 are toothless: a silent removal would never surface.

Consequence chain in plain terms: _block by default → contract says don't remove it → if you remove it, you drop off the radar → I notice you dropped off the radar → that's the breach, on the record._ The employee's choice is reframed from "open WA Web freely" to "open WA Web only by visibly breaching the contract."

## Constraints / decisions captured

- **Office router is ISP-managed** → network-level DNS block at the router is **not available**. This rules out the original NextDNS-on-router plan (Task 1 of the 2026-05-16 IT plan). Forces a **per-device** DNS profile.
- **All staff on the same office WiFi today**, but per-device coverage is chosen anyway because (a) the router is locked and (b) it survives a WiFi change.
- **Web channels only** (operator choice): blocks WhatsApp/Telegram **Web**, not the installed Desktop apps. Desktop-app blocking is a documented future extension, not in this scope.
- **Block, not detect** is the primary action. A private operator-only log digest ("who tried to open WA Web") is an **optional** secondary, additive later.
- **No device agents, no browsing capture beyond the messenger denylist, no team-visible surface** (UU PDP / UU Ketenagakerjaan — consistent with the 2026-05-14 rejection of the "Matrix dashboard").

## Verified facts (on disk 2026-05-31)

- `/usr/bin/profiles` present; macOS **26.5** → supports a NextDNS **DNSSettings `.mobileconfig`** (DoH) payload. Mac delivery path confirmed.
- `scripts/profile-monitor/mac-client/setup-balizero.sh` already provisions a macOS **`balizero` profile** (employees are Admin on it) and installs a LaunchAgent + immutable file. It is the natural carrier for the `.mobileconfig` install step. **This is the recovered value of the May work: the `balizero` profile is the consistent delivery surface for the DNS filter across all corporate Macs — even though, with Admin users, removal is detected rather than prevented.**

## Architecture

```
NextDNS profile "BaliZero-Office" (free tier)
  └─ Denylist: web.whatsapp.com, web.telegram.org, webk/webz.telegram.org (+ extensible)
  └─ Logs ON (30d retention)  ──required──► weekly private digest → Telegram chat 1125336968
        │                                     (tamper-detection: flags devices gone silent = profile removed)
        │  delivered PER-DEVICE as a DNS profile (Admin user → removable but DETECTED)
        ├─ macOS (Silicon + Intel): NextDNS .mobileconfig installed on the `balizero` profile
        └─ Windows (Adit): NextDNS desktop client / native DoH
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
- Logs ON, retention 30 days (feeds the required tamper-detection digest, C4).

### C2 — macOS delivery (`.mobileconfig`)

- Generate the NextDNS `.mobileconfig` (DNSSettings / DoH payload) from the NextDNS setup page for `BaliZero-Office`.
- **Extend `setup-balizero.sh`** with a step that installs it on the `balizero` profile via `profiles` (or double-click), so a **standard** user cannot remove it.
- Works on both Apple Silicon and Intel (it is a profile, not the arm64 Swift binary — so the Intel gap that blocked profile-monitor does **not** apply here).

### C3 — Windows delivery (Adit)

- Install the **NextDNS desktop client** (or configure native DoH) pointed at `BaliZero-Office`. Adit is Admin, so this is removable-but-detected (same model as macOS): the C4 digest flags the Windows box if it stops reporting.
- No custom code; vendor installer + config.

### C4 — Tamper-detection + private digest (**load-bearing**, not optional)

Because employees are Admin, C4 is **promoted from optional to required** — it is layer 3 of the Enforcement model. Weekly script (LaunchAgent on the Pro) pulls the NextDNS API and sends a private Telegram digest to **chat `1125336968` only**, covering two things:

- **Tamper-detection (primary):** per enrolled device, "last seen reporting to NextDNS = T". If a device has **gone silent** (no queries logged for N days while presumed in use), flag it: profile likely removed/disabled → contractual breach candidate. This is the trigger that makes the contract clause enforceable.
- **Attempt visibility (secondary):** "N blocked attempts to open `web.whatsapp.com` / `web.telegram.org` this week, by device X." Shows the block is biting and who keeps trying.

Discipline: Law 2 — the digest sends device labels, counts, and last-seen timestamps, never browsing content beyond the messenger denylist hits. Empty-week behavior: send "all devices reporting, 0 silent" so silence ≠ broken cron (cf. cicatrix W55).

Requires a small **device enrollment registry** (which device label belongs to which employee) so "device X went silent" maps to a person. Kept gitignored under `research/hr/` (sensitive), like the SIM/MDM registries in the 2026-05-16 plan.

## Honest limits (state them, don't hide them)

- **Web only.** WhatsApp/Telegram **Desktop apps** bypass the web-domain denylist. Mitigation (future): block the apps' API endpoints in NextDNS, or keep the apps off the `balizero` profile. Out of scope per operator choice.
- **Removable — employees ARE Admin.** This is the central design reality. A local-Admin employee can delete the DNS profile in seconds. The system does **not** pretend otherwise; it relies on the three-layer Enforcement model (technical friction + contract clause + tamper-detection). The seal is **social/contractual**, made real by the C4 detection layer. If the operator later wants a hard seal, the only path is demoting employees to Standard users (rejected for now) or a managed MDM with supervised mode.
- **Does not touch the personal phone on mobile data.** That channel (the actual Surya vector) is unreachable by any device/network control here — it is the separate investigative track.
- **DoH on the device could be undone by a savvy user** changing browser-level DNS or using a VPN. This is a deterrent against casual off-books use on the corporate machine, not a hard seal against a determined insider. Stated so expectations are calibrated.

## What this explicitly does NOT build

- ❌ No device agent on any OS (the May `profile-monitor` Swift daemon is untouched; presence is a separate concern).
- ❌ No client-theft data detector (R1–R4 from an earlier draft) — **wa-mirror already covers ghost-number / off-books detection**; that detector was redundant and was discarded.
- ❌ No NextDNS-on-router (router is ISP-locked).
- ❌ No browsing/productivity logging beyond the messenger denylist.

## Testing / verification

- After C2 install on a test Mac `balizero` profile: `web.whatsapp.com` and `web.telegram.org` fail to load; a non-listed site loads normally; the device appears in the NextDNS logs.
- After C3 on the Windows box: same two domains blocked; device appears in NextDNS logs.
- **Tamper-detection test (C4):** remove the profile on the test device → confirm it stops reporting to NextDNS → confirm the weekly digest flags it as "silent" within one cycle. This is the load-bearing test: it proves the contract clause is actually enforceable.
- NextDNS dashboard shows blocked queries (confirms enforcement + feeds C4).

## Sequencing (for the plan)

0. **Contract clause (prerequisite, HR):** confirm the PKWTT/handbook forbids removing/disabling the company DNS profile; if absent, draft an addendum. The technical work is wasted teeth without this — do it first or in parallel, but before relying on enforcement.
1. C1 NextDNS profile + denylist (config, ~30 min) — gives an immediately testable block on any device pointed at it.
2. C2 macOS `.mobileconfig` + `setup-balizero.sh` extension (the one code change, small).
3. C3 Windows client for Adit.
4. **C4 tamper-detection digest + enrollment registry (required, not optional)** — without it, Admin removal is silent and the whole model collapses.
