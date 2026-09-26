# iQOO physical client QA

Status: **Physical display-off QA verified on Pro, 2026-09-26**.
Owner mandate: `IQOO-LIVE-QA-20260926` (BLUE). This runbook is a shared capability
for Claude, Codex, Gemini and Qwen; it does not grant release authority.

## Purpose and current availability

Use the owner's iQOO for physical Android client-journey checks: navigation,
touch, keyboard, responsive layout, message indicators and approved live flows.
For changes to a client-facing mobile journey, include a physical iQOO check
when the device is available and the flow is authorized. Record the tested
scope or the concrete availability blocker in the normal QA evidence.
Check current connectivity before claiming availability. A reachable Tailscale
peer alone does not mean ADB or browser control is available.

On 2026-09-26, the owner moved the USB cable to Pro. Its USB registry identifies
vivo I2508. Android platform-tools 37.0.1 and scrcpy 4.1 are now installed there;
ADB is authorized after the owner accepted Pro's key. The physical panel can be
turned off while Chrome remains interactive. Availability still requires a
connected, powered, authorized and initially unlocked phone; it is not an
unattended service that survives reboot, re-lock or USB removal.

The current USB driver host is **Pro**. M5/Mini agents use `ssh pro`; they do not
assume the phone is attached locally. If the owner moves the cable, rediscover
the driver host before use. Keep heavy browser builds/test runners on Pro. The
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
- If absent: the owner reconnects USB. If `unauthorized`: the owner checks the
  driver host's ADB key fingerprint and accepts the phone's RSA prompt locally.
  If genuinely locked or freshly rebooted: the owner unlocks locally once. Never put the
  PIN/password in commands, logs, prompts, screenshots, repo files or memory.
- Prefer USB. Do not enable broad TCP ADB or change tailnet/network policy as
  part of a browser test. Wireless ADB requires its own authenticated setup and
  live connection check; Tailscale does not supply that setup automatically.

## Display-off control

The goal is to turn off the physical display while keeping the authorized test
session running. The phone remains unlocked and may accept physical touches;
use this mode only in a physically controlled workspace. A locked/sleeping
Android session is a different state. Do not
remove the lock screen, change the PIN or disable security to obtain this mode.

After acquiring the device lease, USB authorization and initial unlock, keep
the phone powered and run on the driver host. Select the device explicitly if
more than one is attached. The following shell example temporarily keeps the
device awake while powered and restores the original value on normal exit or a handled
signal. An abrupt host failure still requires recovery and a restoration check.

```sh
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
export ADB="/opt/homebrew/bin/adb"
(
  previous_stay_awake="$(adb shell settings get global stay_on_while_plugged_in | tr -d '\r')"
  case "$previous_stay_awake" in ''|*[!0-9]*) exit 1 ;; esac
  restore_iqoo() {
    adb shell settings put global stay_on_while_plugged_in "$previous_stay_awake"
    adb shell input keyevent KEYCODE_SLEEP
  }
  trap restore_iqoo EXIT
  trap 'exit 130' INT TERM HUP
  adb shell settings put global stay_on_while_plugged_in 7
  test "$(adb shell settings get global stay_on_while_plugged_in | tr -d '\r')" = 7 || exit 1
  scrcpy --no-video --no-audio --no-window --no-clipboard-autosync \
    --turn-screen-off --stay-awake --time-limit=1800
)
```

This uses installed scrcpy rather than a new daemon or APK. It requests no audio,
video recording or clipboard synchronization. The session is bounded to 30
minutes. On this phone, `--stay-awake` and `--screen-off-timeout` alone left the
Android settings unchanged during the test. Explicit ADB settings writes worked;
check their actual values instead of assuming a flag took effect. The phone
reported charging type AC (`mPlugType=1`) despite the USB cable; mask 7 covers
AC, USB and wireless power, whereas USB-only mask 2 left `mStayOn=false`. Verify
`mStayOn=true` during the session. The temporary
keep-awake setting is not a permanent unlock or a guarantee against vendor
battery management. Normal testing does not need to change the screen timeout.

Verify physical power with the internal display's `powerMode` in
`adb shell dumpsys SurfaceFlinger`, together with `mWakefulness=Awake` and
keyguard `showing=false`. Android's logical display can report ON while the
physical panel is Off, so `dumpsys display` alone is insufficient here.

For initial visual diagnosis, run scrcpy with its normal mirror window and
`--turn-screen-off --stay-awake --no-audio --no-clipboard-autosync` instead.
Stop the owned scrcpy process at the end and verify restoration. Then send
`adb shell input keyevent KEYCODE_SLEEP` and verify the phone sleeps and locks;
screen-off alone is not lock confirmation. Do not use the physical power button
or the `KEYCODE_POWER` toggle as a substitute for display-off mode or cleanup.

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
- The selected client flow and its real-vs-fixture boundary, including concrete
  DOM predicates, keyboard geometry and post-action evidence.
- Session exit/restoration: owned tabs/processes/forwards closed, original tabs
  retained, temporary power settings restored, phone asleep and locked, and
  exclusive lock released. Remove only the owned forward with
  `adb forward --remove tcp:N`, never `--remove-all`.
  Record remaining target IDs/types without private URLs.

A disconnect, reboot, re-lock or authorization loss stops dependent testing.
Report the missing physical prerequisite and continue only independent work;
do not silently replace a physical test with desktop emulation.

The BLUE release owner publishes the runbook, receipt and door links together
after independent review, then checks the document revision on Pro, M5 and Mini.
An unreachable or dirty main checkout is recorded as `PENDING-ALIGN`; never
stash or overwrite another session's work to force fleet alignment.
