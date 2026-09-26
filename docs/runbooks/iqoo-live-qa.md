# iQOO physical client QA

Status: **Wireless, USB-free display-off QA verified on Pro, 2026-09-26; client-flow QA remains per-flow**.
Owner mandates: `IQOO-LIVE-QA-20260926`, `IQOO-WIRELESS-20260926`,
`IQOO-SHARED-CAPABILITY-20260927` (BLUE). This runbook is a shared capability
for Claude, Codex, Gemini and Qwen; it does not grant release authority.

## Purpose and current availability

Use the owner's iQOO for physical Android client-journey checks: navigation,
touch, keyboard, responsive layout, message indicators and approved live flows.
**This is a priority shared QA resource for all Bali Zero/Nuzantara mobile
surfaces: portal, public sites, product funnels and authorized application flows.**
For changes to a client-facing mobile journey, include a physical iQOO check
when the device is available and the flow is authorized. Record the tested
scope or the concrete availability blocker in the normal QA evidence.
Check current connectivity before claiming availability. A reachable Tailscale
peer alone does not mean ADB or browser control is available.

The vivo iQOO I2508 has an authenticated **wireless ADB TLS connection through
Tailscale**, driven by **Pro**. **USB is optional.** The full wireless test passed
with the phone on an AC wall charger, USB absent, and the physical display off
while Chrome remained interactive. Android platform-tools 37.0.1 and scrcpy 4.1
are installed on Pro. Wireless availability requires connectivity, authorization,
AC power and an initial local unlock by the owner. It is a supervised, bounded
session; reboot, host crash, SIGKILL and unattended unlock recovery are not proved.

M5/Mini agents use `ssh pro`; they do not assume the phone is attached locally.
Keep heavy browser builds/test runners on Pro. The
RADAR Termux identity is restricted to incident receipts and is not a QA shell.

On Pro, include `/opt/homebrew/bin` and `$HOME/.local/bin` in the SSH command's
PATH. ADB is provided by Homebrew's `android-platform-tools` cask. Scrcpy uses
the upstream macOS ARM64 v4.1 archive in
`$HOME/.local/share/nuzantara/iqoo/scrcpy-macos-aarch64-v4.1/`, with a symlink at
`$HOME/.local/bin/scrcpy`. The archive SHA-256 was checked against upstream:
`20fd47c9014dd5e0fa77091f3cb7adbda8445a360c4584aeaa0150b5b3988ff3`.
This installation does not require upgrading Pro's existing FFmpeg libraries.

The [physical verification receipt](iqoo-live-qa-evidence-20260926.md) records a
40-second idle test against a temporarily shortened 20-second timeout, native
touch/navigation, retained owner tabs and restored power/lock state. It is not
an overnight test or an authenticated live-client/backend test.

### Current wireless status and evidence (on Pro)

Read these under `~/.local/share/nuzantara/iqoo/` before wireless QA:

- `wireless-qa-status.json`: latest recorded verdict and observation time;
  historical PASS is not a live readiness check.
- `wireless-qa-operations.md`: wireless lifecycle and reuse requirements.
- `wireless-transport.json`: private authenticated transport/identity record;
  consume it locally without printing values. Ports can change after reboot or
  network/debugging changes. Recheck identity and authenticated connectivity.
- `evidence/20260926-wireless-v9-verified/`: preserved controller, generated runner,
  source template, receipts, independent final gate and SHA-256 manifest.

The archived controller is a completed synthetic smoke test, not a general
product runner. It writes to a fixed evidence directory. Do not run it over the
archived receipts: use new evidence, validate the pinned controller/template/
runner hashes, and apply the verified lifecycle to the approved product flow.

## One device, one session

- Acquire an exclusive device session on the driver host before changing tabs,
  display state or ADB forwards. An atomic `mkdir /tmp/nuzantara-iqoo-qa.lock`
  suffices for this single-host device; failure means another session owns it.
  Record task, driver host, agent, start time, expiry and the long-lived session
  PID inside it. Expiry must cover the bounded scrcpy session plus cleanup;
  an SSH launcher PID alone is not ownership proof. An expired lock is a stale
  candidate, not permission to interrupt a still-running test. Verify ownership
  and process state before reclaiming it. Remove only the lock you created.
- Confirm `adb get-state` returns `device`. With multiple devices, explicitly
  select this phone for every ADB and scrcpy invocation. Never kill the shared
  ADB server to solve a routine connection issue.
- If absent: check the recorded wireless endpoint and Pro/Tailscale connectivity;
  USB remains an optional recovery path. If `unauthorized`: the owner checks the
  driver host's ADB key fingerprint and accepts the phone's RSA prompt locally.
  If genuinely locked or freshly rebooted: the owner unlocks locally once. Never put the
  PIN/password in commands, logs, prompts, screenshots, repo files or memory.
- Use the already authenticated wireless setup when it passes readiness checks.
  Do not enable legacy/broad TCP ADB or change tailnet/network policy as part of
  a browser test. Tailscale alone does not provide ADB authentication.

## Display-off control

The goal is to turn off the physical display while keeping the authorized test
session running. The phone remains unlocked and may accept physical touches;
use this mode only in a physically controlled workspace. A locked/sleeping
Android session is a different state. Do not
remove the lock screen, change the PIN or disable security to obtain this mode.

The verified lifecycle uses the installed scrcpy with explicit device selection,
no audio/video capture or clipboard synchronization, and a bounded lifetime
(120 seconds in the wireless smoke test). Apply these steps after taking the lease:

1. Verify the authenticated transport, physical identity, AC power and initial
   unlock. Save the original power settings. Refuse an existing Android scrcpy
   session rather than interfering with another owner.
2. Set the temporary powered keep-awake mask to 7 and verify `mStayOn=true`.
   Use scrcpy `--turn-screen-off`; do not assume `--stay-awake` changed settings.
   Normal product testing does not need to shorten the screen timeout.
3. Record the owned host process and new Android scrcpy process IDs. Verify the
   internal HWC display 0 section in `dumpsys SurfaceFlinger` reports
   `powerMode=Off`, while Android is Awake and keyguard `showing=false`.
   Logical display ON alone does not identify the physical panel state.
4. Run the scoped test, preserving owner tabs and checking focus before native
   input. The screen is physically off; Android remains awake and unlocked.
5. Stop only the owned host process. **Wait for its owned Android cleanup
   processes to disappear before restoring settings.** Host scrcpy exit alone
   is insufficient: wireless diagnostics observed a remaining cleanup process.
   Use bounded waits; timeout is a failed run requiring supervised recovery.
6. Restore the saved settings, verify multiple spaced readbacks, then send
   `KEYCODE_SLEEP`. Verify the phone is asleep and locked, and read the settings
   again. Screen-off alone is not lock confirmation. Never use a power toggle
   as a substitute for this verification.
7. Close only the owned tab/forward and release only the owned lease. Preserve
   cleanup errors and corrective writes in the receipt. An outer cleanup pass
   must never conceal an inner failure. For the v9 smoke protocol, both
   `receipt.verdict` and closure `session_verdict` must equal `PASS`; missing/null
   verdicts and a zero process exit code alone do not mean success.

This replaces the earlier shell cleanup example. If the Android side does not
settle, automatic restoration is deferred and the run fails; supervise recovery
instead of racing its cleanup process. Abrupt host failures still require a
restoration check. The keep-awake setting is not a permanent unlock or a
guarantee against vendor battery management.

Upstream also documents Android 15+ `adb shell cmd display power-off 0` and
`power-on 0`. Confirm device/version support before using these; do not substitute
them for a tested keep-awake lifecycle or assume the main display ID blindly.

Source: [scrcpy 4.1 device control](https://github.com/Genymobile/scrcpy/blob/2926c06c5dc3064ae6d8db706f1a98a37cfcf3f0/doc/device.md).

## Connect to the real browser

Start Chrome on the phone and bring the app to the Android foreground. Bringing
a CDP tab forward does not necessarily bring Android Chrome above Settings.
Discover the live Chrome devtools socket; do not hard-code a stale tab or port.
The usual local forwarding pattern is:

```sh
adb forward tcp:0 localabstract:chrome_devtools_remote
```

The returned port is owned by this session. Connect an existing CDP-capable
runner on Pro to that loopback endpoint; use a loopback-only SSH tunnel if a
lightweight controller runs on another host. Do not publish CDP to the LAN or tailnet. Filter target discovery on
the driver host to IDs/types before returning it to any agent: titles and URLs
can contain private data. Preserve original tab IDs and open owned test tabs.
Inventory target **types**: `/json/list` entries are not necessarily all page tabs.
Do not attach to or evaluate code in unrelated tabs, and do not read browser-wide
cookies or storage. Capture only the owned test page, with no personal browser
chrome, notifications or other applications visible.

Before every native ADB touch, verify Android Chrome is the foreground app and
the owned target is active, visible and focused. Recheck its DOM identity and
touch bounds immediately before input; stop if ownership or focus is uncertain.
Prefer native ADB touch for physical touch assertions. Translate CSS coordinates
using the measured pixel ratio, Android toolbar offset and
`visualViewport.offsetTop`; remeasure with the keyboard open. Do not claim native
touch from a JavaScript click or a screenshot. Save the actual commands and DOM
predicates used, with secrets and client PII removed.

Use the browser CDP socket's `Target.createTarget` and `Target.closeTarget` for
owned tabs. On this Chrome build, the HTTP new-tab endpoint failed and an
immediate check after HTTP close still saw the target. Confirm the target has disappeared;
an HTTP response alone is not cleanup evidence.

## Client identity and evidence levels

Declare the mode in every test report:

1. **Physical frontend + synthetic API:** real phone and published assets, but
   intercepted API responses and synthetic identities. This proves frontend
   behavior only, not authentication, database writes, delivery or backend rules.
2. **Live QA client:** an approved, dedicated test-client account authenticated
   normally against production. Record only a test account ID/hash. Use this
   mode to test the actual client role, session behavior and approved writes.
3. **Real external delivery:** Zero approves the recipient and send scope for the
   run. Provider acceptance and recipient receipt are different
   observations. Never infer either from a mocked request.

Do not borrow a real customer's account or impersonate one for routine testing.
Mode 2 additionally needs a dedicated QA browser/profile or a browser context
whose isolation from the owner's sessions has been verified. Another tab in the
same profile is not isolation. If that prerequisite is missing, mode 2 is
unavailable. No approved QA account means live authenticated testing is unavailable; document
that fact instead of fabricating a successful login. Check for existing browser
sessions before use. Do not overwrite cookies/local storage, sign the owner out,
close unrelated tabs or present the default Chrome profile as isolated. A storage
shim is not browser-profile isolation; cookies, cache and IndexedDB are separate.

Block external analytics and outbound APIs in fixture mode. In live mode,
scope mutations and cleanup to the approved QA account. Email uses the existing
Zantara sender through `/api/notifications/send-email`; never create a second
notification path for the test. Keep PII and secrets out of all evidence.

## Acceptance and cleanup

Before changing the status to verified, preserve a dated, redacted receipt of:

- Device model, Android/Chrome/scrcpy versions and driver host; no device serial.
- Physical display state OFF, session unlocked/interactive, browser visible and
  advancing. Test after an idle interval longer than the configured timeout;
  temporarily shortening that timeout is acceptable if explicitly recorded and
  restored. Do not describe such a test as an overnight or normal-timeout soak.
- A harmless native touch and navigation with the physical display still off.
- Session exit/restoration: owned tabs/processes/forwards closed, original tabs
  retained, temporary power settings restored, phone asleep and locked, and
  exclusive lock released. Remove only the owned forward with
  `adb forward --remove tcp:N`, never `--remove-all`.
  Record remaining target IDs/types without private URLs.

Client-flow verification is separate and remains pending for each selected
journey: record its real-vs-fixture boundary, concrete DOM predicates, keyboard
geometry where relevant and post-action evidence. The lifecycle receipt does
not satisfy these flow-specific checks.

A disconnect, reboot, re-lock or authorization loss stops dependent testing.
Report the missing physical prerequisite and continue only independent work;
do not silently replace a physical test with desktop emulation.

The BLUE release owner publishes the runbook, receipt and door links together
after independent review, then checks the document revision on Pro, M5 and Mini.
An unreachable or dirty main checkout is recorded as `PENDING-ALIGN`; never
stash or overwrite another session's work to force fleet alignment.
