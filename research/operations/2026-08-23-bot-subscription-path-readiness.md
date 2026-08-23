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
adversarial_review: pending
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

The Pro-side broker daemon has not claimed a single job since **2026-08-20T03:45:11Z**, roughly
**72 hours ago**. It is not stopped: it is **crash-looping every 30 seconds** and has done so
**7,514 times**. The cause is identified, and it is not a defect in the daemon — the daemon is
fail-closing exactly as designed. What failed is that **nobody was listening**.

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

**Root cause, established by reading the code rather than inferred from the symptom.**
`wa_codex_daemon.run_forever()` calls `_recheck_version()` and, on mismatch, raises `RuntimeError`
*before the loop starts* — with the comment *"a daemon that cannot legally exec must not sit green
(scar family #2)"*. An uncaught `RuntimeError` exits Python with status **1**; the plist is
`KeepAlive{SuccessfulExit:false}` with `ThrottleInterval 30`, so launchd restarts it every 30
seconds, forever. 7,514 restarts × 30 s ≈ **62 hours**, consistent with a death shortly after
03:45Z on 2026-08-20.

The mismatch itself: `WA_CODEX_CLI_VERSION_PIN` was filled by the operator on 2026-08-20, when Pro
carried **codex-cli 0.147.0** (recorded in the corner's own S3 entry). Pro today reports
**`codex-cli 0.149.0`** — the CLI auto-updated, the pin did not. The pin is exact-match and
fail-closed by design (spec chaos row 8).

**The bump is safe, and this was verified rather than assumed.** The five flags the adapter passes
— `--sandbox`, `--skip-git-repo-check`, `--ephemeral`, `--ignore-user-config`, `--ignore-rules` —
are all still accepted by 0.149.0 (`codex exec --help`), and a live `codex exec --sandbox
read-only` probe returned normally today. Nothing in the adapter's call shape depends on 0.147.0.

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
| **0** | **Revive the Pro daemon.** Set `WA_CODEX_CLI_VERSION_PIN=0.149.0` in `/Users/zantara-codex/.wa-codex-broker.env`, then kickstart the job. Proof = the gauge's `broker_last_seen_at` advances. | **`operator[credential]`** — the file is `0600` in another user's home and Pro has no passwordless sudo (probed: `sudo -n true` → password required). One paste, exact text in §3. | Nothing on the ladder can be measured while the executor is dead. Re-running the provisioning script does **not** fix this: it skips an existing env file by design ("never overwritten"). |
| **0b** | **Arm the seat sentinel** — the organ that would have caught step 0 within the hour instead of after 72. Re-run the provisioning (idempotent; installs the §1.3 section the 08-20 run predated), then arm the crontab from the **GUI terminal**. | **`operator[credential]`** for the provisioning, **`operator[tcc-gui]`** for the crontab: writing the crontab on Pro is TCC-blocked from every non-GUI context (measured 2026-08-20 via both sshd and a live tmux server). | Without it, the next silent death also lasts days. Highest value-per-minute item on this list. |
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
# Step 0 — revive the daemon (pin bump; flag-compatibility with 0.149.0 verified today)
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
