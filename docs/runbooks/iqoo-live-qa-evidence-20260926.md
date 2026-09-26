# iQOO display-off verification receipt

Mandate: `IQOO-LIVE-QA-20260926`. Observation started at
`2026-09-26T14:34:16.736162Z`. Driver: Pro, owner-authorized USB.

Scope: a synthetic local page on the physical phone, controlled over loopback
CDP with a native ADB touch. No customer login, backend message, email or other
external delivery is asserted by this receipt.

| Check                                      | Observed result                                                        |
| ------------------------------------------ | ---------------------------------------------------------------------- |
| Device                                     | vivo iQOO I2508, Android 16                                            |
| Host tools                                 | Android platform-tools 37.0.1; scrcpy 4.1                              |
| Browser at final test                      | Chrome 153.0.8010.52                                                   |
| Physical panel before and after idle/touch | SurfaceFlinger `powerMode=Off`                                         |
| Android before and after idle/touch        | `mWakefulness=Awake`, `mStayOn=true`, keyguard `showing=false`         |
| Temporary settings                         | screen timeout 20,000 ms; powered keep-awake mask 7                    |
| Idle interval                              | 40 seconds; browser timer advanced from 0 to 40; document visible      |
| Native action                              | `adb shell input tap 630 1375`                                         |
| Action outcome                             | tap counter 0 to 1; hash changed to `#step-two`; timer reached 41      |
| Viewport                                   | 387 by 708 CSS pixels; pixel ratio 3.25                                |
| Browser cleanup                            | owned tab removed; both original targets retained; 2 targets remaining |
| Host cleanup                               | owned ADB forward removed; scrcpy exited 0; device lease released      |
| Restored settings                          | screen timeout 600,000 ms; powered keep-awake mask 0                   |
| Final device state                         | `mWakefulness=Asleep`, keyguard `showing=true`, `mStayOn=false`        |

Empirical corrections incorporated into the runbook: powered keep-awake must
cover AC charging (`mPlugType=1`) even over this USB cable; scrcpy option flags
alone did not change the settings during the probe; physical SurfaceFlinger
power must be checked separately from logical display ON. Chrome changed from
140 to 153 between probes; rediscover the browser endpoint after a restart or
update. Only the final successful probe is represented in the table above.

The independent review consumes this receipt, the redacted machine receipt and
the local test controller. No PIN, credential, device serial, owner tab URL or
customer data is included in the published evidence.

## Unlock path and limits

For this one-off owner-authorized test, the provided unlock credential was
transported through encrypted SSH stdin and process memory, then entered through
ADB shell stdin after checking that the secure keyguard/SystemUI was foreground.
No credential value was written into commands recorded by the tool interface,
files, logs, documentation or evidence. This was an explicit session exception;
it is not a reusable runbook unlock procedure. Future routine sessions require
the owner to provide the initial local unlock.

The counter and hash confirm that the native injected tap reached the test
document. The probe did not separately record Android foreground/focus at the
instant before the tap; the runbook now requires that check for subsequent QA.

## Retained diagnostic evidence

Redacted inputs are retained on Pro under
`~/.local/share/nuzantara/iqoo/evidence/20260926/`. The controllers are diagnostic
evidence for this run, not a production QA runner; their cleanup is not hardened
against every mid-cleanup ADB failure. Use the reviewed runbook for future work.

- `device-receipt.json` SHA-256: `52f3f87bf3bc42a9476bb6b386d7b353c676e5feb5594979af1390f8eaa8d525`
- `device-test.py` SHA-256: `981833834b476e089280f80b9e595a90fe43cb7a7b06ec02121f85d59d45dfc4`
- `device-test.mjs` SHA-256: `2d5d8d2d0867d31268577c5f1a31fa7926f5e50ca4021354764a17938f0e7276`
