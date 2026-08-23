---
date: 2026-08-23
domain: compliance
client_case: none
sources:
  - measured-on-disk-and-in-prod (every row in §1 carries the probe that produced it)
  - research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md (§6 gate ladder G-P1..G-P6)
  - .agents/skills/bot/SKILL.md §1 (LIVE STATE, BOT-V4 S2/S3 entries)
  - memory decision_gemini_is_not_the_bot_chatgpt_is_2026_08_21 (Zero ruling — destination)
  - memory decision_wa_openai_provider_subscription_path_owner_ruling_2026_08_15 (subscription-only constraint)
adversarial_review: kimi-k3
---

# What is still missing between "daemon live on Pro" and "WhatsApp answers through ChatGPT by subscription"

**Purpose.** This is the input for Zero's next ruling. It does **not** arm the switch and does not
ask for it to be armed. It answers one question: *given where the lane actually is on 2026-08-23,
what stands between here and S4, in order, and who owns each step.*

**Measurement stamp.** Every claim in §1 was probed on **2026-08-23 between 01:00Z and 01:40Z**,
from Pro, against repo SHA **`148f0bfca`**. A claim with no probe named beside it is not in this
document.

---

## 0. The headline, before the list

**The premise this memo was commissioned on — "daemon live on Pro" — is false as of today.**

The Pro-side broker daemon has not claimed a single job since **2026-08-20T03:45:11Z** —
**69.6 hours** before this measurement. It is not stopped: it is **crash-looping roughly every 30
seconds** and has done so **7,514 times** since the machine last rebooted.

**The cause is only half identified, and the memo says which half.** A version-pin mismatch
(`codex-cli` auto-updated 0.147.0 → 0.149.0 while the pin did not) is real and is certainly
blocking the daemon *now* — but the arithmetic in §1.2 proves the crash-loop began **at least 10
hours before that upgrade**, so it is a second cause, not the first. **What killed it on 08-20 is
still unknown, and the answer is in a root-only log.**

What is fully established is the part that matters most: **nobody was listening.** Every health
indicator read green for the whole outage.

So the ordered list below starts at step 0, and step 0 is not on the ladder.

---

## 1. Measured state, 2026-08-23

### 1.1 Server side (Fly) — HEALTHY, LIVE, DARK. Nothing to do here.

| What | Probe run today | Result |
|---|---|---|
| App health | `curl https://nuzantara-rag.fly.dev/health` | `200` |
| Broker claim endpoint | `curl -X POST .../api/wa-broker/claim`, no key | `401 {"detail":"wa-broker key required"}` — live and correctly dark |
| Broker key + canaries | `fly secrets list -a nuzantara-rag` (names only, never values) | `WA_BROKER_KEY`, `WA_CODEX_CANARY_TOKENS` both `Deployed` |
| Provider switch | same listing | **`WA_GENERATION_PROVIDER` is ABSENT** → defaults off → **WA is served by Gemini**, as intended |

The S2 server-side build is fine. It is the only half of this lane that is.

### 1.2 Pro side — INSTALLED, THEN DIED 2.5 HOURS LATER, SILENTLY, FOR 72 HOURS

| What | Probe run today | Result |
|---|---|---|
| launchd job | `launchctl print system/com.balizero.wa-codex-broker` | `active count = 0` · `state = spawn scheduled` · **`runs = 7514`** · **`last exit code = 1`** · `job state = exited` |
| Running process | `ps -eo pid,user,command \| grep wa-codex` | **none** |
| Downstream ground truth | prod `SELECT * FROM wa_broker_gauge` via `fly ssh console` | `broker_last_seen_at = 2026-08-20 03:45:11Z` · `in_flight 0` · `breaker_state closed` · `consecutive_failures 0` |
| Installed payload vs repo | `cmp -s /usr/local/libexec/wa-codex-broker-wrapper.sh infra/launchagents/wrappers/…` | **IDENTICAL** — no HOME-fork (superscar #1 clean) |
| Runtime tree | `ls -la /usr/local/lib/wa-codex-broker/` | present, root-owned, installed `2026-08-20 08:39` local |

**Cause — and this section was WRONG in the first draft of this memo; an adversarial pass
(Kimi K3, on the frozen diff) forced the correction. The corrected version is the one that
matters, so it is stated in full rather than patched.**

The tempting story was: the pin says `0.147.0`, Pro now runs `codex-cli 0.149.0`, the daemon
fail-closes on the mismatch, done. **The timeline refuses that story as the ORIGINAL cause.**

| Event | When (UTC) | How it was measured |
|---|---|---|
| Gauge advancing, daemon healthy | 2026-08-20 01:11→01:12Z | ledger row, 08-20 |
| **Gauge freezes — daemon stops claiming** | **2026-08-20 03:45:11Z** | `wa_broker_gauge` today |
| **Pro reboots** | **2026-08-20 09:49:54Z** | `sysctl -n kern.boottime` |
| **codex-cli 0.149.0 installed** | **2026-08-21 15:59:23Z** | `stat` on the resolved binary |
| Measurement | 2026-08-23 ~01:20Z | this document |

Two consequences, both arithmetic:

1. **launchd's `runs` counter resets at boot**, so the 7,514 restarts span the window since
   **09:49:54Z on 08-20**, not since the gauge froze: 63.50 h, an implied spacing of **30.42 s**
   against a 30 s floor.
2. The window since the CLI updated is only 33.35 h, which at a strict 30 s floor caps the
   restarts at **4,002**. We observe **7,514**. **Therefore ~3,512 restarts (~29 hours) predate
   the 0.149.0 upgrade — the version-pin mismatch cannot be the original cause.**

**What is actually established:**

- The daemon stopped claiming at 03:45:11Z on 08-20, **6.08 h before the reboot** — so it was
  already failing under the pre-reboot launchd session. **That first cause is unknown.**
- Since 15:59:23Z on 08-21 the pin mismatch is real and, given the code path, would by itself be
  sufficient to keep the daemon down. So it is a genuine **second** cause, layered on the first.
- **Consequence for the cure: bumping the pin alone may not revive the daemon.** It removes a
  blocker that certainly exists now; it does not address whatever killed it on 08-20.

**A corroboration the first draft claimed, now withdrawn.** That draft read the implied spacing as
"throttle floor + ~3.3 s of real work per cycle" and offered it as evidence the process was
reaching the `codex --version` call. It is not evidence of anything: `ThrottleInterval` is measured
**from launch, not from exit**, so any runtime under 30 s produces the same ~30 s spacing. The
figure is uninformative about which early-exit path fires, and the 0.42 s excess is scheduling
jitter. It was also computed from the wrong start time.

**Still not measured, and it is the thing that would settle this:** the daemon's own log
(`/Users/zantara-codex/logs/wa-codex-broker.err`) — root-only, and Pro has no passwordless sudo
(probed: `sudo -n true` → password required). The pin's current on-disk value is unread for the
same reason; the `0.147.0` figure comes from the ledger row of 08-20, not from the file. Ruled out
by the wrapper's own exit codes: missing env file, unfilled placeholders, missing venv python (all
exit **78**) and the kill switch (exit **0**). Everything else that can exit **1** remains open.

**The daemon's two version-check paths are ASYMMETRIC, and that asymmetry proves a separate
termination event.** (Found by the same adversarial pass; confirmed by reading the code.) The
STARTUP check raises and exits 1. The MID-RUN recheck does the opposite — `if not
self._version_ok: await self._sleep(self._config.poll_s); continue` — it **stops claiming and
keeps the process alive**. So if the CLI had auto-updated under a healthy daemon, the designed
end-state would be *process alive, gauge frozen, `runs` flat*. What we observe is *no process,
`runs` climbing, exit 1*. **Therefore something terminated the daemon at ~03:45Z on 08-20, and
only afterwards did every respawn hit the startup refusal.** The pin story explains the outage's
*persistence*; it cannot explain its *initiation*.

**Named candidates for the initiation event, so the log read in §3 is targeted rather than
open-ended.** All of them exit **1** and are indistinguishable from outside:

- **The `codex` binary not resolvable on the daemon's PATH.** `_read_cli_version` resolves
  `self._config.codex_bin or shutil.which("codex")`, and the plist gives the job only
  `/opt/homebrew/bin:/usr/bin:/bin`. `/opt/homebrew/bin/codex` is an npm symlink whose mtime is
  **2026-08-21T15:59Z** — i.e. it was last rewritten *during* the outage. `shutil.which` returning
  `None`, an `OSError`, a non-zero `codex --version`, or output with no semver token all collapse
  into the same "mismatch" refusal. **If this is the cause, bumping the pin changes nothing.**
- **`DaemonConfig.from_env` raising `ValueError`** — it validates every knob and refuses to start
  half-configured: blank `WA_BROKER_KEY`, blank base URL, non-numeric `WA_BROKER_POLL_S` /
  `WA_BROKER_NET_MARGIN_S`, or a `WA_CODEX_MODEL` outside the allowlist
  (`gpt-5.6-sol|terra|luna`; the template sets `gpt-5.6-terra`).
- Any import-time failure in the runtime tree.

**What the pin bump IS good for, verified today rather than assumed.** `codex --version` prints
`codex-cli 0.149.0`, and the daemon's own `_SEMVER_RE` (`(\d+\.\d+\.\d+)`) parses that to
`0.149.0` — so a pin of `0.149.0` will match. And the adapter's exact call shape —
`_FIXED_ARGV_PREFIX` = `exec --sandbox read-only --skip-git-repo-check --ephemeral
--ignore-user-config --ignore-rules` plus the `-` stdin sentinel, **all five flags together**, not
one flag as the first draft's probe used — was executed live against 0.149.0 today and returned
its expected token, rc 0.

**The bump is safe, and this was verified rather than assumed.** The five flags the adapter passes
— `--sandbox`, `--skip-git-repo-check`, `--ephemeral`, `--ignore-user-config`, `--ignore-rules` —
are all still accepted by 0.149.0 (`codex exec --help`), and a live `codex exec --sandbox
read-only` probe returned normally today. Nothing in the adapter's call shape depends on 0.147.0.

**The log has now been read, and it confirms the CURRENT crash cause — not the initiating one.**
The operator read `/Users/zantara-codex/logs/wa-codex-broker.err` (the root-only blocker noted
above is cleared). The tail shows exactly the pin-mismatch startup refusal: `RuntimeError:
wa-codex-daemon: startup refused — CLI version does not match
WA_CODEX_CLI_VERSION_PIN='0.147.0'`, with the daemon separately logging `CLI version '0.149.0'
does not match pin '0.147.0'`. The wrapper sidecar
`/Users/zantara-codex/.organism/last_seen/pro.wa_codex_broker.json` reads `{"status":"starting",
"note":"exec daemon"}`, confirming the wrapper reached `exec` (its own guards would have exited
78, not 1, had it failed earlier). **This settles the CURRENT cause and NOT the initiating one**:
the log tail shows today's crashes, and the ~29 h window before the upgrade (arithmetic above) is
still unexplained. The leading untested hypothesis: an intermediate codex version (0.148.x)
auto-installed around `2026-08-20T03:45Z` — the exact moment the gauge froze — which npm would
have overwritten invisibly, since only the latest install's mtime survives on disk.

### 1.3 The seat sentinel — never armed, and the reason is a timing accident worth recording

| What | Probe run today | Result |
|---|---|---|
| Probe state dir | `ls /usr/local/var/wa-codex-broker` | **does not exist** |
| Sentinel crontab | `crontab -l \| grep -c seat-sentinel` | **0** |

The corner records that Zero executed the provisioning on 2026-08-20 — and the installed files
prove he did (wrapper + runtime tree, timestamped `08:39` local = `00:39Z`). But the seat-probe
section, including the `install -d … /usr/local/var/wa-codex-broker` line, was **added by #4405
(`ecd3a3da0`), merged at 07:48Z the same day** — *after* that run. So the provisioning Zero
performed could not have installed a section that did not yet exist.

This is not an operator error and not a failed step: **it is a run that predates its own feature.**

### 1.4 The meta-pattern — why 72 hours passed with nothing red

Three organs each did the right thing individually, and the chain still went dark:

1. The daemon **refused loudly** and exited non-zero, exactly as its own comment promises.
2. The wrapper writes a heartbeat sidecar — but the registry entry deliberately carries
   `expected_hb_seconds=0`, because the wrapper's own comment names the **server-side claim gauge**
   as the running daemon's liveness ground truth, not the sidecar. So the sidecar is not watched.
3. The server-side gauge went stale at 03:45:11Z on 08-20 and **has been stale ever since** — while
   `breaker_state` reads `closed` and `consecutive_failures` reads `0`, i.e. **perfectly green**,
   because the daemon never connects far enough to fail. A dashboard reading the breaker would
   report health throughout the entire outage.

The organ that closes this loop is precisely the **seat sentinel** — the one thing §1.3 shows was
never armed. This is superscar family #2 in its purest form: not a component that lies, but a
correct fail-closed refusal wired to an alarm channel nobody armed.

The 2026-08-20 corner entry "S3 ARMED — gauge ADVANCING" was **true when written** (01:11→01:12Z)
and stopped being true 2.5 hours later. Nothing existed to notice the transition — which is the
same lesson the ledger already carries in a different costume: *"armata" non è uno stato, è un
istante*.

---

## 2. What is missing, in order, with owner

Steps are ordered by dependency: each is blocked by the one above it.

| # | Step | Owner | Why it sits here |
|---|---|---|---|
| **0** | **Diagnose, THEN revive the Pro daemon.** Read `/Users/zantara-codex/logs/wa-codex-broker.err` — that is the one artifact that names the original cause, and it is root-only. Then bump `WA_CODEX_CLI_VERSION_PIN` to `0.149.0` and kickstart. Proof = `broker_last_seen_at` ADVANCES between two reads. | **`operator[secret]`** — both the log and the env file are root/other-user-owned, and Pro has no passwordless sudo (probed: `sudo -n true` → password required). One paste, exact text in §3. | Nothing on the ladder can be measured while the executor is dead. **Do not skip the log:** §1.2 proves the pin mismatch is not the original cause, so the bump alone may leave the daemon down. Re-running the provisioning script does **not** touch the pin either — it skips an existing env file by design ("never overwritten"). |
| **0b** | **Arm the seat sentinel** — the organ that would have caught step 0 within the hour instead of after 72. Re-run the provisioning (idempotent; installs the §1.3 section the 08-20 run predated), then arm the crontab from the **GUI terminal**. | **`operator[secret]`** for the provisioning, **`operator[tcc]`** for the crontab: writing the crontab on Pro is TCC-blocked from every non-GUI context (measured 2026-08-20 via both sshd and a live tmux server). | Without it, the next silent death also lasts days. Highest value-per-minute item on this list. |
| **0c** | **Cure the class, not the instance:** make version-pin drift *detectable* — the sentinel's RED must name "pin mismatch", and the pin bump belongs to whatever updates codex-cli. | session | codex-cli auto-updates. This will recur, and next time it should be a 5-minute alert rather than an archaeology exercise. |
| **1** | **G-P1** — live verification of the ChatGPT **and Codex-specific** data-control settings on the seat, dated, re-checked at S4. | **`operator[gui]`** + session record | Account-level toggles are visible only in the web UI. The 2026-08-19 owner attestation covered the ChatGPT-level toggle; the spec (§6, G-P1) leaves the Codex-specific controls explicitly open. |
| **2** | **G-P3** — the named DLP policy with a **measured recall floor**. | session | **In flight today.** The redaction module is built and tested; the round-2 cure batch (NIK-vs-date over-match plus four smaller findings) is the PR this session is shipping. What remains after that PR is the *registered recall number* on the synthetic corpus — a figure Zero should see, not a claim. |
| **3** | **G-P5** — S1.5 quota classifier + capacity model, merged. | session | Needs the daemon alive (step 0): the classifier's whole job is to predict when the ChatGPT seat's own limits bite, and it cannot be calibrated against a dead executor. |
| **4** | **G-P4** — shadow sink design: minimized columns, worker-role-only access, no export path, TTL ≤ 14 d **whose effect is verified** (post-TTL count asserted zero, alarmed otherwise), plus a deletion runbook. | session | Pure build, but it must land before any shadow traffic exists to sink. |
| **5** | **S3a → S3c** — synthetic shadow, then the pre-registered real-traffic shadow (N, strata, primary metrics, non-inferiority margin and stop rules frozen *before* enabling). | session | S3c is the first step that touches real client text, so it sits behind every gate above it. |
| **6** | **G-P2** — the UU PDP / Art. 56 transfer-basis artifact: the basis and the revocation path for routing client chat text to OpenAI. | **`operator[business]`** — Zero, 2026-08-23: *"non ora"* | Legge 5. It does not re-litigate the provider decision, which is made; it documents the basis. **This is the hard blocker on S4** — see §2.1. |
| **7** | **G-P6** — owner's recorded acceptance of the §4.2 bounded residual (seat-credential exfiltration past the pattern/canary scans). | **Zero — ACCEPTED 2026-08-23** | Recorded. One precondition remains outstanding; §2.2 states it plainly rather than reading the acceptance as wider than it is. |
| **8** | **S4 cutover** — flip `WA_GENERATION_PROVIDER`. | **Zero alone.** No session may flip it. | The end state ruled on 2026-08-21. Until it is flipped, WA stays on Gemini: the ruling names the destination, it does not throw the switch. |

### 2.1 The critical path is G-P2, not engineering

Steps 0, 0b, 0c, 2, 3, 4 and 5 are all session work or one operator paste. **G-P2 is the only item
on this list that no amount of building can advance**, and every step from S3c onward sits behind
it, because S3c is where real client text first reaches the provider. If G-P2 stays open, the lane
can be fully built, fully shadow-tested on synthetic traffic, and still not cut over.

That is not an argument for prioritising it — that is Zero's call (Legge 5). It is an argument for
not reading a green engineering board as "nearly there".

### 2.2 G-P6: what was accepted, and what was not

Zero recorded acceptance of the bounded residual on **2026-08-23**: the residual is that a stolen
seat credential could, in principle, carry data past the pattern-and-canary egress scans, and Zero
accepts it **at the bound as stated in spec §4.2**.

**The spec attaches a precondition to that acceptance which is not yet satisfied, and closing the
gate without saying so would be dishonest.** G-P6's own row requires the bound to be *verified, not
assumed*: a measured inventory of what a stolen `auth.json` can actually reach (scopes and surfaces
**probed**, not presumed seat-only), plus a revocation test — re-login performed, the pre-rotation
token then probed **dead**. Neither probe has been run.

The spec is explicit about the consequence: *"If either probe widens the bound, the acceptance is
re-put to the owner with the wider bound."* So the correct ledger state is **accepted at the stated
bound, bound not yet measured**. The probes are session work (the spec's own row says so) and must
run before G-P6 is marked closed. Recording it as flatly "closed" today would be accepting a number
nobody has measured.

---

## 3. The exact operator text for steps 0 and 0b

Both are single pastes into Pro's **GUI terminal** — not ssh, not tmux: the crontab leg is
TCC-blocked from every non-GUI context.

```sh
# Step 0a — READ THE LOG FIRST. This is the only artifact that names the ORIGINAL cause, and
# §1.2 shows the pin story does not explain it. Paste the last lines back rather than acting
# on the assumption below.
sudo /usr/bin/tail -40 /Users/zantara-codex/logs/wa-codex-broker.err

# Step 0b — confirm the pin's actual value. Prints ONLY that line: never `cat` the whole file,
# it carries WA_BROKER_KEY (superscar #4).
sudo /usr/bin/grep '^WA_CODEX_CLI_VERSION_PIN=' /Users/zantara-codex/.wa-codex-broker.env

# Step 0c — bump the pin (parse + all five adapter flags verified against 0.149.0 today).
# This clears a blocker that certainly exists NOW; whether it is SUFFICIENT depends on 0a.
sudo /usr/bin/sed -i '' 's/^WA_CODEX_CLI_VERSION_PIN=.*/WA_CODEX_CLI_VERSION_PIN=0.149.0/' \
  /Users/zantara-codex/.wa-codex-broker.env
sudo launchctl kickstart -k system/com.balizero.wa-codex-broker

# Step 0b — install the seat-probe section the 2026-08-20 run predated (idempotent)
cd ~/nuzantara && sudo bash scripts/provision_zantara_codex.sh
```

**How to know it worked — do not read the exit code, read the downstream state.** Within about a
minute the prod gauge must start advancing:

```sh
fly ssh console -a nuzantara-rag -C "python -c \"
import asyncio,os,asyncpg
async def m():
    c=await asyncpg.connect(os.environ['DATABASE_URL'])
    print(await c.fetchrow('SELECT broker_last_seen_at, breaker_state FROM wa_broker_gauge'))
    await c.close()
asyncio.run(m())\""
```

`broker_last_seen_at` must be within seconds of now, and must **change** between two consecutive
runs. A single fresh-looking timestamp is not proof; two advancing ones are. `breaker_state` reading
`closed` proves nothing on its own — it read `closed` throughout the entire 72-hour outage.

---

## 4. What this memo deliberately does not do

- It does not arm `WA_GENERATION_PROVIDER`, propose a date for S4, or recommend one.
- It does not treat Zero's 2026-08-21 destination ruling as a schedule. WhatsApp stays on Gemini
  until the subscription path is armed, and "armed" means every row in §2 closed — not merged.
- It does not claim G-P6 is closed. See §2.2.

---

## Adversarial review

Seat: **Kimi K3**, on the frozen diff, fresh context, generator≠grader. Verdict **FIX-FIRST(6)**.
Three findings were material and are folded into the text above; three survive as stated limits.
Kimi's own second pass confirmed the three survivors were correctly dispositioned rather than
argued away.

### Folded in (the memo was WRONG before these)

1. **The daemon's cause was misattributed.** The first draft said codex-cli's auto-update broke the
   version pin, full stop. Kimi attacked the arithmetic and was right. Re-measured: launchd's `runs`
   counter **resets at boot** (`sysctl -n kern.boottime` = `09:49:54Z 08-20`), so 7,514 restarts span
   the 63.50 h since boot, not since the gauge froze; and the 33.35 h since the 0.149.0 binary's
   mtime cap restarts at 4,002 against a 30 s floor. Observing 7,514 proves **the crash-loop began
   ~29 h before the upgrade**. The pin explains persistence, never initiation. The initiating cause
   is **unknown** and sits in a root-only log.
2. **A corroboration was withdrawn, not weakened.** The draft argued "restart spacing = the 30 s
   floor plus ~3.3 s of real work, therefore the daemon reached `codex --version`". Void:
   `ThrottleInterval` is measured **from launch, not from exit**, so any sub-30 s runtime yields the
   same spacing. It distinguishes nothing and was removed rather than hedged.
3. **"Verified, not assumed" was overstated.** The draft claimed the five adapter flags were
   verified against 0.149.0; one flag had been probed. The exact five-flag call shape was then run
   live — rc 0 — and `_SEMVER_RE` confirmed to parse `codex-cli 0.149.0`. The claim now matches
   what was actually executed.
4. The headline duration was corrected 72 h → **~70 h** (69.58 h measured).

### Surviving objections, recorded as limits rather than cured

5. **The initiating cause remains unidentified.** Named candidates, none proven: `shutil.which("codex")`
   returning `None` under the plist's `PATH` (the `/opt/homebrew/bin/codex` symlink was rewritten
   `2026-08-21T15:59Z`, *during* the outage); a `DaemonConfig.from_env` `ValueError`; an import-time
   failure. Reading the log is `operator[secret]` — Pro has no passwordless sudo, probed this
   session (`sudo -n true` → password required). This is a measured boundary, not a deferral.
6. **G-P6's accepted bound is still unmeasured.** Zero accepted the residual, and the spec's own row
   requires the bound be *verified*: a probed scope inventory of what a stolen `auth.json` reaches,
   plus a revocation test. Neither has run. Acceptance of a number nobody measured is recorded here
   as exactly that.
7. **This memo cannot prove its own §3 paste works.** The cure is written from source, not from a
   successful execution — nobody has run it. Its proof-of-armed is therefore stated as a *future*
   observation (two advancing reads of `broker_last_seen_at`), never as a result.
