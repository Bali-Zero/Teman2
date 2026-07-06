---
date: 2026-07-06
domain: operations
topic: Google Antigravity CLI (agy) headless/non-GUI authentication on macOS under sshd/cron/launchd
sources:
  - https://github.com/google-antigravity/antigravity-cli/issues/85
  - https://github.com/google-antigravity/antigravity-cli/issues/51
  - https://github.com/google-antigravity/antigravity-cli/issues/78
  - https://github.com/google-antigravity/antigravity-cli/issues/315
  - https://github.com/google-antigravity/antigravity-cli/issues/88
  - https://github.com/google-antigravity/antigravity-cli/issues/57
  - https://github.com/google-antigravity/antigravity-cli/releases
  - https://github.com/google-antigravity/antigravity-cli/blob/main/CHANGELOG.md
  - https://github.com/openclaw/openclaw/issues/1402
  - https://github.com/lbjlaq/Antigravity-Manager/issues/2200
  - https://discuss.ai.google.dev/t/bug-report-antigravity-agent-executor-fails-to-initialize-in-remote-ssh-environment-stuck-in-loading-authenticating/145233
  - https://discuss.ai.google.dev/t/resolved-authentication-required-loop-on-macos-root-cause-is-corrupted-keychain-entry-not-app-files/135744
  - https://antigravitylab.net/en/articles/integrations/antigravity-cli-agy-headless-non-tty-stdout-ci
  - https://antigravitylab.net/en/articles/integrations/antigravity-cli-headless-non-interactive-ci-design
  - https://thekodelab.com/en/posts/macos-ssh-keychain-unlock/
  - https://www.aibuilderclub.com/blog/antigravity-cli-guide
  - https://developer.apple.com/forums/thread/685967
  - https://blog.surajdev.tech/antigravity-login-issue-on-macbook-how-i-finally-fixed-it-after-hours-of-trying
client_case: null
adversarial_review: glm
---

# Google Antigravity CLI (agy) headless auth on macOS — is there a working path under sshd/cron/launchd?

**Verdict up front: no working path exists today (as of agy v1.0.16, released 2026-07-02).** The failure is two independent, stacked problems — one macOS OS-level (SSH sessions never inherit the unlocked GUI login keychain) and one agy-specific (a hardcoded 1-second Keychain-read timeout that misfires even when the keychain *is* reachable) — and agy's own file-based fallback path, which would sidestep both, is Linux-only by design. The least-bad pattern is GUI-session persistence hardening, not a CLI-side fix.

## 1. Where agy stores its token, and why sshd specifically breaks it

Confirmed via ≥2 independent sources (GitHub issues + third-party technical writeups that quote the same log lines, cross-checked against a `security find-generic-password` empirical test result from issue #51):

- **macOS**: the OAuth token is stored as an **encrypted macOS Keychain item** named `"Antigravity Safe Storage"` (via `security find-generic-password -s "Antigravity Safe Storage" -w` or similar) — **not a file**. [github.com/…/issues/85](https://github.com/google-antigravity/antigravity-cli/issues/85), [blog.surajdev.tech](https://blog.surajdev.tech/antigravity-login-issue-on-macbook-how-i-finally-fixed-it-after-hours-of-trying)
- **Linux**: the same credential is a **plain file** at `~/.gemini/antigravity-cli/antigravity-oauth-token` (some sources also cite `credentials.enc` alongside it). [aibuilderclub.com](https://www.aibuilderclub.com/blog/antigravity-cli-guide), corroborated by the ComputingForGeeks install guide.

This is the load-bearing platform split: **on Linux, "sign in once on a workstation, copy the token file to the headless server" is an explicitly documented, working pattern** for exactly the CI/headless case in the research prompt. **On macOS, there is no equivalent file path** — and critically, one community report states that manually placing a token in `~/.gemini/antigravity-cli/google_credentials`, `auth.json`, or `config.json` **is silently ignored**, because "the application strictly enforces the keyring check" [source for this specific claim traces back through the #85/#51 issue-comment ecosystem — flagging as **single-thread-attested**, not independently reproduced by us]. So even manually exfiltrating the raw token via `security find-generic-password -w` and writing it to a file will not make macOS agy read it back — the code path for file-based credentials doesn't exist on this platform.

**Why sshd specifically (not just "background process") fails:** this is a well-documented macOS OS-level constraint independent of agy. The macOS **login keychain auto-unlocks only through `loginwindow`** (i.e., an actual GUI login) — SSH sessions never go through `loginwindow`, so they start with the login keychain **locked**, and unlocking it interactively in one SSH session does not propagate to a different SSH session or to launchd/cron jobs run under the same user unless *that specific process* also unlocks it. Apple's own developer forums confirm daemons (system context) have a structurally different, harder problem than agents (user context) here. [developer.apple.com/forums/thread/685967](https://developer.apple.com/forums/thread/685967), [thekodelab.com](https://thekodelab.com/en/posts/macos-ssh-keychain-unlock/) — 2 independent sources, consistent.

## 2. The agy-specific bug stacked on top: 1-second keyring timeout

Even setting aside the SSH-keychain-lock problem, agy has its own known, **currently unfixed** defect: a **hardcoded 1-second timeout** in `keyring.go:89` for the macOS Keychain read (`keyringAuth: timed out after 1s, skipping keyring auth`). macOS's `security` daemon frequently needs longer than 1s to respond for background/non-interactive processes (binary signature re-verification, system load), so agy gives up, concludes "no token," and either falls back to a fresh browser OAuth flow (interactive context) or fails outright (headless/print context). One reporter demonstrated the token was directly readable via `security find-generic-password` in ~42ms — the token and Keychain access were both fine, but agy's own timeout fired first regardless. [github.com/…/issues/85](https://github.com/google-antigravity/antigravity-cli/issues/85), [github.com/…/issues/51](https://github.com/google-antigravity/antigravity-cli/issues/51) — 2 independent issue threads reporting the identical log line and root cause, both **still open with no maintainer response visible**, and **no CHANGELOG.md entry across all 10 tracked releases 1.0.7→1.0.16 (2026-06-09 → 2026-07-02) mentions keyring/keychain/timeout/SSH/headless-auth** — confirmed by direct changelog read, so this is not fixed in your currently-newer-than-recorded v1.0.2 install.

Note the two bugs are **orthogonal, not the same failure**: the Keychain-lock problem (§1) means the *item is unreachable at the OS level*; the timeout bug (§2) means *even a reachable item may not be read in time*. Fixing one does not fix the other. This matters for interpreting the exact "authentication failed or timed out" message your empirical test surfaced — it is consistent with either failure mode and the two GitHub issues don't quote that exact user-facing string, so we cannot definitively attribute it to one over the other from public sources; it is plausibly both compounding.

## 3. Does the pseudo-TTY wrapper make sense as a fix here? (No — different bug class)

The `script -q /dev/null agy -p ...` wrapper your team already tried addresses a **third, unrelated** documented agy defect: on non-TTY stdout (CI/cron), agy can silently drop its final response while returning exit 0 — a "succeeded but did nothing" output-plumbing bug, not an auth bug. [antigravitylab.net/…/non-tty-stdout-ci](https://antigravitylab.net/en/articles/integrations/antigravity-cli-agy-headless-non-tty-stdout-ci) is explicit that this wrapper is about output capture, and does not mention Keychain, sshd, or `security unlock-keychain` at all. So the fact that the wrapper also failed under sshd is not surprising and does not tell us anything new about the auth mechanism — it was targeting a different problem than the one you're hitting. This confirms your team's read ("not a TTY issue") was correct, just via a slightly different mechanism than "the credential is GUI-session-bound" alone — it's GUI-session-bound **plus** a currently-broken Keychain-read-timeout on top.

## 4. `security unlock-keychain` workaround — plausible in theory, unconfirmed against agy specifically

This is a real, independently-documented pattern for **other** macOS CLI tools with the identical Keychain-locked-under-SSH symptom (the cited example is Claude Code itself): `security unlock-keychain ~/Library/Keychains/login.keychain-db` run once in an SSH session unlocks it for that session and (per the source) the unlock state is process-shared such that subsequent processes on the same login session can then read it. [thekodelab.com](https://thekodelab.com/en/posts/macos-ssh-keychain-unlock/) is explicit this generalizes: "anything that stores tokens or credentials in the login keychain can show the same symptom" — implying the fix should generalize too.

**However — no source in this research confirms this has actually been tried against agy and worked.** This is a **gap, not a negative result**. Given §2 (the 1-second timeout bug is independent of whether the keychain is locked or unlocked), the honest expectation is: unlocking the keychain removes failure mode §1, but agy's own 1-second race condition in §2 may still misfire intermittently even with the keychain unlocked — issue #51's reporter demonstrated the token was Keychain-readable via `security` directly (implying keychain state was fine) and agy *still* timed out internally, which suggests the unlock-keychain workaround alone is not sufficient by itself, though it may reduce failure frequency (a fully-unlocked keychain probably responds faster than a cold/locked one under load, narrowing the race window without eliminating it).

**Recommended combined experiment** (unconfirmed by any source, but the closest a-priori-sound synthesis of the two documented mechanisms):
```bash
# In the sshd session, before invoking agy:
security unlock-keychain ~/Library/Keychains/login.keychain-db   # prompts for password interactively — do NOT use -p inline (shell history/process-list leak)
agy -p "PONG"
```
If this still intermittently fails, it is consistent with §2 firing independently of lock state. Retry-loop wrapping (3× with short backoff) would be the mitigation the timeout bug itself implies, since one community-proposed fix (never shipped) was literally "retry, don't just fall back to OAuth on first miss."

**launchd-specific note:** for a *launchd* LaunchAgent (not raw sshd) invoking agy, adding `<key>SessionCreate</key><true/>` to the plist is cited by Apple's own developer forum as helping LaunchAgents (user-context) access Keychain items that a fresh launchd-spawned process otherwise cannot see — distinct from LaunchDaemons (system-context), which have a structurally harder version of this problem. [developer.apple.com/forums/thread/685967](https://developer.apple.com/forums/thread/685967) — **single-source for this specific plist key recommendation**, not cross-verified against a second source or against agy specifically.

## 5. Vertex AI / API-key mode — confirmed dead end, and NOT just "unsupported," actively refused

- `GOOGLE_API_KEY` / `GEMINI_API_KEY` env vars: **not honored by agy at all**, confirmed by 2 independent sources (the aibuilderclub CLI guide explicitly states "`GEMINI_API_KEY` is ignored" and issue #78 confirms neither var is currently read).
- **Issue #78** ("Feature Request: Support Gemini API Key... for Headless Environments") is the canonical open ask. Maintainer Rody Davis's pinned reply (2026-06-29, i.e., **one week before your test**): *"Gemini API Key is not supported currently. We are reviewing the feedback from the community but do not have any updates at this time."* **Status: open, no ETA, no linked PR.** This matches what you already found via "GitHub issue #78," now confirmed verbatim with a date and named maintainer.
- The maintainer's own suggested alternative is **not** Vertex/AI-Studio API-key mode — it's **"the Antigravity SDK... should fit a lot of the use cases you need for CI workflows."** This is a materially different product surface: the SDK exposes `ANTIGRAVITY_TOKEN` as its CI credential (distinct from `agy auth login`'s interactive token), described in third-party guides as "CI uses `ANTIGRAVITY_TOKEN`." **We could not find, in any source, documentation of how `ANTIGRAVITY_TOKEN` is provisioned, whether it draws on the AI Ultra OAuth subscription quota or requires separate (paid) enrollment, or whether it is even available to individual/non-enterprise accounts** — this is a genuine, unresolved gap, flagged as such rather than guessed at. Given the maintainer redirected to it as the CI-appropriate answer, it is worth a direct, small-scope follow-up (check `agy auth --help` output and the SDK's own onboarding docs on a GUI-authenticated session) before assuming it's paid-only — but do not assume it is free/OAuth-backed without that verification.
- One retail workaround exists for a **different problem** (weekly quota exhaustion, not headless auth): pasting an AI Studio-generated API key into Antigravity **Settings → Models** inside the desktop GUI app routes future *interactive* calls to a separate 150 RPM AI-Studio quota pool. This does not help headless/cron use — it's a GUI-only settings toggle, and AI-Studio API keys are billed/quota'd separately from the OAuth subscription per Google's standard AI Studio terms, so it would also violate the "OAuth Ultra, not paid API" constraint even if it were scriptable.

## 6. Issue tracker snapshot (as of 2026-07-06 research date)

| Issue | Title | Status | Key fact |
|---|---|---|---|
| [#78](https://github.com/google-antigravity/antigravity-cli/issues/78) | API-key auth for headless | **Open** | Maintainer confirmed unsupported 2026-06-29, no ETA; SDK redirect |
| [#85](https://github.com/google-antigravity/antigravity-cli/issues/85) | 1s keyringAuth timeout (macOS) | Reported closed by one crawl, but **no comments/PR/fix visible**, and **not in CHANGELOG through v1.0.16** — treat as functionally unresolved | Root cause = hardcoded 1s timeout in `keyring.go:89` |
| [#51](https://github.com/google-antigravity/antigravity-cli/issues/51) | Same timeout bug, different reporter | Open, no maintainer response | Empirically proved token *is* readable via `security` in ~42ms; agy still times out |
| [#315](https://github.com/google-antigravity/antigravity-cli/issues/315) | OAuth URL corrupted by SSH pty line-wrap (v1.0.6) | Open, no workaround documented | 500+ char OAuth URL splits mid-parameter under narrow pty width → Google rejects with `invalid_request` |
| [#88](https://github.com/google-antigravity/antigravity-cli/issues/88) | Login state not persisted (Win/WSL) | Closed, no resolution detail | **Not macOS** — do not conflate with your case |
| [#57](https://github.com/google-antigravity/antigravity-cli/issues/57) | "does not remember OAUTH login" | Referenced, not deep-fetched this pass | Likely same family as #85/#51 |

No beta flag (`AGY_HEADLESS`, service-account support) was found anywhere in the CHANGELOG (v1.0.7 through v1.0.16, 2026-06-09 to 2026-07-02) or in any issue thread. `--headless` **does exist** as a flag, but it governs **approval-policy** for file writes/command execution during a run (paired with `--approve all|...`) — it is not an authentication mode and does not touch the Keychain problem at all. Do not confuse the two; a run with `--headless --approve all` will still hang/fail at the auth step if the Keychain read fails first.

## 7. Best-practice pattern if truly impossible today: GUI-session persistence hardening

Since no CLI-side fix exists, the only documented and mechanistically sound approach is to **keep a real, unlocked GUI login session alive on the Mini** so agy's local calls run in a context where Keychain access behaves as designed (no SSH-lock problem, though the 1s-timeout bug from §2 can still misfire — mitigate with a retry loop):

- **Auto-login the user at boot** — macOS auto-login unlocks the login keychain automatically at boot as a side effect (same keychain-unlock-at-login mechanism `loginwindow` normally performs), removing the "SSH never went through loginwindow" gap entirely for that always-on session. This is the standard pattern for unattended Mac minis.
- **Keep the session alive**: `caffeinate -d -i -u` (or a LaunchAgent wrapping it) prevents display sleep/logout from tearing down the session; Screen Sharing kept connected (or simply never disconnected) avoids any logout-triggered keychain re-lock.
- **What breaks it** (per the pattern's known failure modes, generalized from the keychain-unlock literature, not agy-specific testing): a **reboot** without auto-login re-triggers the lock; a **logout** (explicit or idle-timeout-triggered) re-locks the keychain; a **macOS update** can reset auto-login settings or trigger a fresh login requiring re-entry of the password (and possibly re-triggering agy's own OAuth re-prompt if the Keychain item was touched); **agy's own version updates** are an additional risk given the Keychain item name and format could change between releases (16 point releases in ~7 weeks is a high churn rate) — pin the agy version once a working state is achieved rather than auto-updating.
- Given this, **cron jobs should run *inside* that persistent GUI session's process tree** (e.g., a LaunchAgent in the user's context with `SessionCreate` true, launched by/alongside that session) rather than via sshd from a separate login, since sshd is confirmed (§1) to never inherit the unlocked state regardless of GUI persistence elsewhere.
- Layer the `security unlock-keychain` + retry-loop mitigation (§4) as defense-in-depth even inside the persistent session, since §2's 1-second race is independent of lock state.

This is explicitly a workaround for an unresolved upstream limitation, not a permanent architecture — re-audit when #78 or #85 gets a maintainer response, since a shipped fix would likely obsolete the need for session-persistence entirely.

## Adversarial self-check

- Could the "authentication failed or timed out" message be something else entirely (e.g., network egress blocked from the Mini, corporate proxy, expired refresh token requiring full re-consent)? Plausible but not supported by the evidence gathered — no source describes that exact string, and the empirical fact that the *same account* works fine in the GUI session on the *same machine* moments earlier strongly favors a session/keychain-locality explanation over a network/token-validity one.
- Is it possible agy v1.0.16 (2 releases ahead of your recorded v1.0.2) already silently fixed this and the CHANGELOG just doesn't mention it? Possible but unlikely — a fix to a load-bearing, actively-reported auth bug would typically appear in release notes, and the fact that #78 (a much more prominent, pinned, maintainer-acknowledged issue) got an explicit "no updates" as late as 2026-06-29 suggests the auth subsystem overall has not seen a recent overhaul. Recommend upgrading to v1.0.16 before further workaround engineering regardless — cheap to test, and would rule this out.
- Single-source claims flagged explicitly in-line above (§1 "silently ignored" file-fallback claim, §4 SessionCreate plist recommendation) — both plausible and consistent with the surrounding evidence, but not independently corroborated by a second source in this research pass.

---

**10-line verdict for team lead:**

1. Mechanism is two stacked, independent failures: (a) macOS never unlocks the SSH session's login keychain (`loginwindow`-only unlock, OS-level, no PAM/launchd bridge — confirmed via Apple dev forum) and (b) agy has a hardcoded, still-unfixed 1-second Keychain-read timeout (`keyring.go:89`, issues #85/#51, open through v1.0.16 released 2026-07-02, zero CHANGELOG mentions).
2. Your pseudo-TTY test (`script -q /dev/null`) was targeting a *third*, unrelated bug (non-TTY stdout dropping) — its failure under sshd tells us nothing new; correctly ruled out TTY as the cause.
3. macOS has **no file-based token fallback** (unlike Linux's `~/.gemini/antigravity-cli/antigravity-oauth-token`, which is explicitly copy-between-machines-safe) — manually injecting a token file is reported ignored; the Keychain path is hard-enforced on this platform.
4. `security find-generic-password -w` can read the token in ~42ms directly, proving Keychain access itself isn't the blocker — agy's own internal timeout is.
5. Untested-but-sound candidate: `security unlock-keychain ~/Library/Keychains/login.keychain-db` in the sshd session before `agy -p`, wrapped in a 3× retry loop to absorb the 1s race — no source confirms this against agy specifically, flagged as an experiment worth 10 minutes, not a guarantee.
6. `GOOGLE_API_KEY`/`GEMINI_API_KEY` are confirmed **not honored at all**; issue #78 maintainer confirmed (2026-06-29) API-key auth "not supported currently... no updates."
7. Maintainer's alternative is the **Antigravity SDK** (`ANTIGRAVITY_TOKEN` for CI) — a different product surface from `agy`; provisioning path and whether it draws OAuth-Ultra quota vs. requires separate enrollment is an **unresolved gap**, worth a 5-minute check (`agy auth --help`, SDK onboarding docs) before ruling it out.
8. No beta headless-auth flag exists anywhere in the codebase/changelog/issues as of this date.
9. **Verdict: impossible today via any CLI-only fix.** Least-bad pattern is GUI-session persistence hardening on the Mini: auto-login at boot (which performs the same keychain-unlock `loginwindow` normally does) + `caffeinate`/kept-alive session + cron running *inside* that session's process tree (LaunchAgent with `SessionCreate=true`), not via sshd — plus the retry-loop mitigation from point 5 as defense-in-depth.
10. This breaks on reboot (unless auto-login), logout, or macOS/agy updates (agy ships ~2 releases/week — pin the version once stable); re-audit if #78 or #85 gets a maintainer fix.

## Adversarial review

**Reviewer**: GLM 5.2 (z.ai seat, generator≠grader — author was Claude Fable 5). Run 2026-07-06, prompt: attack the 5 core claims, verdict per claim, list surviving objections.

**Verdicts**: claims 3 (sshd cannot inherit the unlocked login keychain), 4 (API-key auth refused upstream, #78) and 5 (pseudo-TTY wrapper targets an unrelated stdout bug) **SURVIVE** the attack. Claims 1–2 were **challenged on version-reach and framing**, not on the operational conclusion:

- **Meta-weakness (accepted)**: the "no working path as of v1.0.16" verdict rests on a version no source — including this report — actually exercised; the installed CLI was **v1.0.2**. Combined with a §2/table inconsistency on issue #85's status, the "impossible today" framing is firmer than the evidence licenses.
- **Framing overclaim (accepted)**: §5's "NOT just 'unsupported,' actively refused" escalates beyond the cited maintainer quote ("not supported currently… reviewing the feedback"), which is consideration, not refusal. The operational conclusion (API-key auth is a dead end today) stands regardless.
- Claim 5's stdout-drop bug is single-sourced (antigravitylab.net) — the claim as stated survives because it only concerns what the wrapper *addresses*.

**Empirical addendum (operator experiment, 2026-07-06)**: Zero ran `security unlock-keychain` in the SAME sshd session and immediately invoked `agy -p "PONG"` — still `authentication failed or timed out`. This confirms the keychain-unlock alone does not cure the failure **on v1.0.2**, consistent with the 1s-timeout hypothesis but not a test of newer releases.

**Surviving action item**: upgrade agy to the latest release on the Mini and re-run the sshd probe BEFORE treating headless auth as permanently impossible; re-audit on any maintainer movement on #78/#85. Until then the operative classification stays CONTEXT_AUTH (GUI-bound), as encoded in `scripts/arsenal_probe.py`.

**Capture caveat**: the refuter's detailed reasoning for claims 1–2 was truncated in the session capture (only the meta-weakness paragraph and the final verdict line were retained); the version-reach and #85-status objections above are quoted from the retained portion. Claims 1–2 should be treated as *unproven at latest version*, not refuted at v1.0.2.
