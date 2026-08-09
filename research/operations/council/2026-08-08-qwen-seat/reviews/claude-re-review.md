---
adversarial_review: exempt-council-artifact
---

## VERDICT: REQUEST-CHANGES
The four originally-demonstrated bypass forms are genuinely closed, but the fix's own design choice (strip-only, no forced-safe-mode) leaves the wrapper's primary sanctioned command (`review run`) defaulting to `--approval-mode=yolo` with no way to override to `plan` through this wrapper — a live, direct violation of Fable gate Q2's explicit ruling — and the commit's declared "no recording-disable surface" claim is factually false (the flag exists, live-verified, on the exact command family that matters).

## PER-FINDING STATUS

**1. P0 wrapper bypasses — CLOSED (as literally specified)**
Tested via a PATH-shadowed fake `qwen` stub that echoes exactly what argv reaches "the binary" — more rigorous than "did it reach the credential-gate error," since it shows the post-strip argv directly, at zero API cost:
```
bash scripts/qwen-cloud-code.sh -p hi --yolo                    → ARGS=[-p, hi]        (stripped)
bash scripts/qwen-cloud-code.sh -p hi --approval-mode yolo      → ARGS=[-p, hi]        (stripped)
bash scripts/qwen-cloud-code.sh -p hi --approval-mode=auto-edit → ARGS=[-p, hi]        (stripped)
bash scripts/qwen-cloud-code.sh review run 123 --comment        → refused, exit 1, fake qwen never invoked
```
All four hold. Control (`--approval-mode=yolo` exact) also correctly stripped.

**2. P0 settings.json perms — CLOSED, with a minor caveat**
```
chmod 0644 ~/.qwen/settings.json && bash scripts/qwen-cloud-code.sh -p hi --yolo (via fake qwen) → settings.json now 0600
```
Reassertion confirmed durable across invocations. Caveat (see findings): a *refused* call (dies at the Legge-5 scan, step 1) exits before reaching the chmod at step 3, so "re-asserted on every invocation" isn't literally true for that path — low severity, doesn't undermine the fix.

**3. P1 recording — STILL-OPEN (the declared gap is false)**
```
qwen review --help      → --chat-recording  [boolean]  "Enable chat recording to disk. If false, chat history is not saved..."
qwen review run --help  → same flag present
qwen --help (top-level) → no chat-recording mention (41 lines total)
```
The flag exists, is not deprecated, and lives exactly on the `review` command family — the wrapper's stated purpose. The commit's claim ("no flag... found in the installed package") only checked bare `qwen --help`, missing the subcommand tree — the same blind spot that produced finding NEW-1 below.

**4. Probe change — CLOSED, no issues**
```
python3 scripts/arsenal_probe.py --selftest              → SELFTEST OK — 18 checks
python3 scripts/arsenal_probe.py --seats qwen-cloud-code --table → LIVE 5938ms PONG, safe-mode note, well under the 15s mandate
```
`--safe-mode` is a sound addition: disables MCP/hooks/extensions/skills for a probe that only needs a PONG.

## NEW FINDINGS

- **NEW-1, P0 — `review run` always executes in `yolo` by default, unblockable through this wrapper.** The strip loop removes *any* `--approval-mode` value, safe or not. Live-proved: `bash scripts/qwen-cloud-code.sh review run 123 --approval-mode=plan` → only `review run 123` reaches exec, `--approval-mode=plan` silently dropped. `qwen review run --help` documents the child default as `yolo`. Every review through this wrapper — including a bare `review run` with no target (reviews the local working tree) — runs with the child CLI auto-approving every action, directly contradicting Fable gate Q2's ruling text ("approval `plan`"). This is the same underlying requirement as the original finding #2, just defeated by omission instead of bypass.
- **NEW-2, P1 — `--yolo=true` (equals-form) is not stripped**, asymmetric with the `--approval-mode=*` glob. Currently inert since `--yolo` isn't a live flag anywhere in this build's help surfaces, but it's the one form the wrapper's own "future-proofing" comment doesn't actually cover.
- **NEW-3, P2 — 0600 reassertion skips the refusal path** (documented above under #2).

## RECORDING-GAP RULING: surface-exists-here
`--chat-recording=false` on `qwen review`/`qwen review run` (verified live, qwen 0.21.7). Not a declared-and-accepted gap — it's a missed surface. The fix should append `--chat-recording=false` unconditionally for review-family invocations, satisfying Fable Q5 directly.
