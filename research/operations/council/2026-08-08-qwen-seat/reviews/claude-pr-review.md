---
adversarial_review: exempt-council-artifact
---

# PR #3884 Review — qwen-cloud-code seat registration

## VERDICT: REQUEST-CHANGES
The wrapper's entire stated purpose ("Legge-5-hardened, no yolo") is live-provably bypassable three separate ways, is missing a flag Fable's own SHIP-AFTER-FIXES gate explicitly required blocked, and — independent of this diff — I found the P0 cleartext credential this whole PR chain exists to contain is **currently sitting on disk at world-readable permissions with the secret inside**, contradicting the premise the operator ruling relies on.

## EVIDENCE
- `python3 scripts/arsenal_probe.py --selftest` → `SELFTEST OK — 18 checks`.
- `python3 scripts/arsenal_probe.py --seats qwen-cloud-code --table` → `qwen-cloud-code AUTH_DEAD 0ms keychain gate: keychain lookup failed (exit 44) — locked or absent — seat UNARMED (operator rotation pending, gate 2026-08-08)` — correct, matches design (dormant candidate).
- `python3 scripts/check_adversarial_review.py --diff origin/main` → `PASS — 9 research file(s) carry a valid adversarial review` (all 8 council artifacts `exempt-council-artifact`, main doc `adversarial_review: codex` + retitled `## Adversarial review` heading, per Fable's fixes 2/4).
- Live bypass tests against `scripts/qwen-cloud-code.sh` (credential absent, so each dies at the *next* gate — proving the verb/mode scan itself never fired):
  - `bash scripts/qwen-cloud-code.sh -p hi --yolo` → sailed past the scan to the credential-gate error (bare `--yolo` is a real, documented top-level flag; wrapper only checks `--approval-mode=yolo`).
  - `bash scripts/qwen-cloud-code.sh -p hi --approval-mode yolo` (space, not `=`) → same, sailed past.
  - `bash scripts/qwen-cloud-code.sh -p hi --approval-mode=auto-edit` → sailed past (real value is hyphenated `auto-edit`; wrapper blocks a fictional `auto_edit` with underscore).
  - `bash scripts/qwen-cloud-code.sh review run 123 --comment` → sailed past (real, documented flag on `qwen review run` that posts comments directly to a GitHub PR).
  - Control: `--approval-mode=yolo` (exact form) → correctly blocked. One shape defended, everything adjacent open.
- `qwen --help`, `qwen review --help`, and reading `~/.qwen/settings.json` bundled docs (`auth.md`, `model-providers.md`) confirm the flag semantics above, from the actual installed CLI (`@qwen-code/qwen-code` under mise node 22.22.3), not from memory.
- `ls -la ~/.qwen/` + `stat -f '%Sp'` right now: `settings.json` is `-rw-r--r--` (0644), mtime **today 16:25**, containing `/env/BAILIAN_TOKEN_PLAN_API_KEY` (name-only walk, value redacted) and `/providerMetadata/token-plan/*` — i.e. the live credential is present in cleartext, world-readable, right now.

## FINDINGS

1. **P0 — LIVE, out-of-band, not in the diff but directly bears on this PR's premise.** `~/.qwen/settings.json` is currently `0644` (world-readable) and contains the cleartext `BAILIAN_TOKEN_PLAN_API_KEY` — the exact P0 this whole chain exists to fix — right now, mtime today 16:25 (I ran unwrapped `qwen --help`/`qwen review --help` earlier in this review, and cannot rule out that those calls silently recreated the file at default perms; either way this proves the finding). The operator ruling states "the 0600 mitigation stands as forward-fix" — that mitigation is **not currently true on disk**, and it is not self-healing: any bare, unwrapped invocation of `qwen` (still fully on `$PATH`, ungated) appears to reset it. **Fix (operator, immediate, independent of this PR's merge):** `chmod 0600 ~/.qwen/settings.json` again now, and treat "0600 as forward-fix" as requiring active/periodic re-assertion (or a wrapper-level `chmod` on every invocation), not a one-time state.

2. **P0 — `scripts/qwen-cloud-code.sh:26-33`, Legge-5/yolo scan is a leaky blocklist, not the allowlist Fable's gate required.** Fable's SHIP-AFTER-FIXES ruling (Q2, `reviews/fable-gate.md:33`) required blocking `--comment` specifically, alongside `submit`/`publish-assets`/`channel`/`serve`. The shipped scan omits it, and additionally: (a) never checks bare `--yolo` (a real top-level flag, `docs/.../auth.md`/CLI `--help`), (b) only matches `--approval-mode=X` joined by `=`, not space-separated `--approval-mode X` (both are valid yargs forms), (c) blocks a fictional `auto_edit` (underscore) instead of the real `auto-edit` (hyphen) value. All four confirmed bypassing live in EVIDENCE above. **Fix:** stop matching literal argv strings; either force `--approval-mode=plan` unconditionally (strip/override any user-supplied approval-mode/`--yolo` arg rather than trying to enumerate every dangerous spelling), and add `--comment` to the verb/flag blocklist.

3. **P1 — `scripts/qwen-cloud-code.sh`, chat-recording is not wrapper-enforced.** Fable's Q4/Q5 ruling (`reviews/fable-gate.md:37`) required "recording-off must be wrapper-enforced" as part of the PII bar, not merely a one-time chmod. The shipped wrapper never sets `general.chatRecording=false` (or equivalent CLI override) before exec. **Fix:** add `--config-override general.chatRecording=false` or the documented equivalent to the `exec` line, or refuse to run if the live setting isn't false.

4. **P1 — Q3 (economics) remains genuinely open, and the operator ruling given to me doesn't close it.** The research doc itself (lines 355-358) and Fable's ruling (`reviews/fable-gate.md:35`) already flag that the credential authenticates against Alibaba's **Token Plan — usage-based/metered billing** (confirmed live: `providerMetadata/token-plan/*` in `settings.json`, ~6.95M tokens already consumed in one session per the doc), not the flat-fee Coding Plan, and that this "requires Zero's explicit confirmation" of plan/reset/overage/concurrency before the seat is anything more than an inert candidate. Today's operator ruling addresses only the credential-*rotation* question (Q2 sub-item), not Q3's billing-contract confirmation. Under CLAUDE.md's cost-constraint doctrine (paid per-token APIs need explicit authorization with knowledge of the cost model), this stays open regardless of my verdict on the code.
   *(Not a bug: the env var name `BAILIAN_TOKEN_PLAN_API_KEY` used by both the wrapper and the probe is technically correct — it matches the actual live credential type. It just confirms the seat is metered, reinforcing #4 rather than being a naming error.)*

5. **P2 — `scripts/arsenal_probe.py` — no functional issues found.** Probe registration is clean: correct status taxonomy (`AUTH_DEAD` via `load_keychain_token`, matching the `agy`/`kimi`/`claude` conventions), correct secret scrubbing (`extra_secrets=[token]` passed to `evidence_tail`, token never echoed — confirmed via the live probe run above showing only the exit-code-based note), correctly excluded from `REQUIRED_SEATS` on every machine, `DEFAULT_TIMEOUTS` entry added, selftest fixture added and passing. No P0/P1 here.

## RULING-1 RECOMMENDATION
Do **not** adapt the gate to trust "credential present + hardened file permissions" on `~/.qwen/settings.json` as literally proposed — I just demonstrated live that "hardened perms" on that file is not a durable state (it reverted within a day, likely from any bare `qwen` invocation). Gating on it would arm the seat against a condition that can silently flip back to insecure.

Instead: have the operator do a **value-preserving copy** of the *existing* (unrotated — satisfies "non ruoto") credential value into Keychain — `security add-generic-password -s qwen-cloud-code-token -a qwen-cloud-code -w '<the-same-existing-value>'` — then blank the key out of `settings.json` and `chmod 0600` it as defense-in-depth. This keeps the gate exactly as designed (Keychain-only, never reads/recreates the cleartext path, per the wrapper's own stated principle), satisfies "no rotation" literally (same secret value, just relocated), and actually closes the P0 rather than leaving it live on disk. Until that migration happens (and findings #2/#3 are fixed), the seat should stay dormant.

## CHECKLIST RESULTS
1. Probe registration correctness: **PASS** — conventions, taxonomy, evidence hygiene, timeout, machine-scoping all correct; selftest 18/18, live probe behaves as designed.
2. Wrapper Legge-5/bypass scan: **FAIL** — 3 live-proven bypasses (bare `--yolo`, space-separated `--approval-mode`, wrong `auto-edit` spelling) + missing `--comment` block that the PR's own governing gate required.
3. Security/secrets in the diff: **PASS on the diff itself** (no secrets committed, off-limits files untouched) — **but P0 live-state finding** (#1) outside the diff, directly relevant to this PR's premise.
4. Doctrine (AGENTS.md contract, R1 frontmatter, commit conventions): **PASS** — external-agent contract respected, R1 gate passes mechanically, commits are conventional/atomic/English with correct co-authorship.
5. v4 doc vs operator ruling: **Flag, not a re-gate** — Q3 (economics/billing-model confirmation) is still open and not addressed by today's ruling; nothing in v4 is contradicted by the "won't rotate" decision, since v4 already anticipated a non-rotation path was possible (Q2 lists rotation as *a* precondition, not asserts it will happen).
