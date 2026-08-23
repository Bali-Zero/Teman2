---
adversarial_review: kimi-k3
---

# P03 — WR3/FlowKit zero-spend — design decision

**Builder:** H3 · **Gear:** 2 · **base:** `5117d9908a37cdc5f23924f6fe19cd823e2ed6c5`
**Ceiling:** no Flow/Veo submission, no credit spend, no render/publish execution, no WR2 edits,
no scheduler/service/LaunchAgent load-unload-install. `service_control: none`.

## Ground findings (all re-verified on disk this session)

| # | Finding | Evidence |
|---|---|---|
| F1 | **No credit ledger exists.** The cost circuit breaker reads `~/.cache/wr3/flow-quota.json`; **nothing in the repo ever writes it.** Hand-seeded `as_of: 2026-05-29`, `daily_spent_cr: 0`, `balance_remaining_cr: 2400` — while real clips were rendered (see F1b for the corrected count). | only reader: `scripts/wr3_gatekeeper_check.py:15`; zero writers (repo-wide grep) |
| F2 | **Per-clip cost disagrees 2×.** Client charges 20 cr/clip; gate projects 10 cr/clip. A 19-shot episode: gate computes 190 cr (== its own `expected_cr`, PASSES) while reality is 380 cr. **The breaker passes an episode costing 2× its ceiling.** | `wr3_flowkit_client.py:48-49` = 20 · `wr3_gatekeeper_check.py:24` `CR_PER_CLIP = 10` · `wr3_probe_single_clip.py:4` "~10 Veo cr" |
| F3 | **The gatekeeper is advisory, not enforcing.** `wr3_render_episode.py` — the actual render driver — never reads `gate-verdict.json` and never calls the gatekeeper. It checks `/health.extension_connected`, then goes straight to `submit_clip`. | `wr3_render_episode.py:28-70` |
| F4 | **`wr3_probe_single_clip.py` bypasses `submit_clip` entirely**, calling `fk._generate_start_image` + `fk._generate_video` directly. A guard in `submit_clip` alone is bypassable. | `wr3_probe_single_clip.py:38-45` |
| F5 | **Fail-open by configuration.** `flow-quota.json` is an unvalidated user-writable HOME cache; a large seeded `balance_remaining_cr` silently disables the breaker. Missing file = uncaught exception, not a named refusal. | `wr3_gatekeeper_check.py:15` (no try/except) |
| F6 | **WR2 shares the same credit pool.** `scripts/wr2_flowkit_client.py` posts to the same gateway `/api/flow/generate-image`. Out of this packet's scope to change (ceiling), so **the ledger cannot claim to be a complete account of Flow credit consumption** — it accounts for WR3 only. Stated as a limitation, never papered over. | `wr2_flowkit_client.py:81,308` |
| F7 | **`drawtext` is not compiled into this ffmpeg** (8.1, no libfreetype); `/tmp/ffmpeg-full/ffmpeg` referenced by the post-assembler docs does not exist. A placeholder spec naming `drawtext` would fail at runtime. PIL 12.1.1 is present — burned-in text goes through a PIL-rendered overlay PNG. | `ffmpeg -h filter=drawtext` → `Unknown filter` |

## Decision

**Guard at the lowest network layer, not at the caller.** Every credit-charging HTTP call in WR3
goes through exactly two functions — `_generate_start_image` and `_generate_video`. The spend
authorization check is installed **there**, so F4-class bypasses (and any future caller) fail
closed by construction rather than by remembering to add a check.

Three layers, defence in depth:

1. **`submit_clip` zero-spend short-circuit** — when `WR3_ZERO_SPEND` is truthy, returns a
   deterministic placeholder `ClipResult` (`cost_credits=0`) without touching the network.
2. **Low-level fail-closed gate** — `_generate_start_image` / `_generate_video` raise
   `SpendNotAuthorizedError` unless a well-formed `WR3_SPEND_DECISION=<episode_id>:<who>:<date>`
   is present, matches the episode being rendered, and is dated today. Raised *before* the POST.
3. **Ledger record at the same choke point** — every authorized spend and every placeholder is
   appended to the JSONL ledger, so before/after is measurable rather than asserted.

**Why not fix F2/F3 here:** repairing the gatekeeper's `CR_PER_CLIP` and wiring it as a blocker
changes render-path behaviour, which the frozen "must not" bars in this dispatch. They are
recorded as findings + PENDING-ARMS lines for the successor (P11 owns the paid pilot).

## Falsifiable acceptance criteria

- A1 `python3 scripts/wr3_credit_ledger.py report --days 30` prints per-episode credits from local artifacts only, exit 0, on an empty ledger too.
- A2 With `WR3_ZERO_SPEND=1`, a full episode run produces N placeholder mp4s, 8s, 720x1280, distinguishable per shot, and **zero** network calls to :8100 (proven by a listener-absent run, not by trust).
- A3 Without `WR3_SPEND_DECISION`, a direct call to `_generate_video` raises `SpendNotAuthorizedError` **before** any socket is opened.
- A4 With a *mismatched* or *stale-dated* `WR3_SPEND_DECISION`, same refusal.
- A5 Ledger total before the dry run == ledger total after the dry run.
- A6 Codex red-team finds no path to a charge that skips the gate; Kimi K3 does not falsify the ledger arithmetic.

## Live Pro-side facts (measured 2026-08-23 ~11:53 WITA, this session)

- FlowKit gateway **ALIVE**: PID 1062, `/Users/nuzantara/flowkit/venv/bin/python -m agent.main`,
  uptime **2d 17h 55m**, LISTEN on 127.0.0.1:8100 **and** :9222. Note the binary lives under
  `$HOME/flowkit/` — HOME-executed payload, superscar #1 surface (recorded, not touched here).
- `GET /health` → `{"status":"ok","version":"0.2.0","extension_connected":false,`
  `"ws":{"connected":false,"connects":17,"disconnects":17,"uptime_s":null}}`
  → **`status:"ok"` while `extension_connected:false`** — superscar #2 in the flesh: the top-level
  field a naive monitor reads says healthy; the field that decides whether a render can succeed
  says the browser extension is gone. 17 connects / 17 disconnects = it has flapped and is down.
- Consequence for the dry-run proof: **the listener is present**, so "nothing was listening" is NOT
  available as evidence of zero spend. Replaced by a falsifiable probe (below).

## Falsifiable zero-spend probe (what would make it RED)

Run the zero-spend path with `WR3_FLOWKIT_ENDPOINT=http://127.0.0.1:1` (a port with no listener).
- If zero-spend genuinely never opens a socket → the run **succeeds** and the ledger records 0 cr.
- If any code path still tries to reach the gateway → **ECONNREFUSED**, the run fails loudly.
This is the probe's answer to "what would have made this red": a single reachable byte to the
gateway turns it red. Absence of a listener is not being used as the proof; the *inversion* is.

## Dry-run episode: synthetic fixture, and why

**No episode on disk has a `shot-pack.json`** (checked all three under
`apps/war-room/output/episode/`). Generating a real one would be *storyboard execution*, which the
frozen "must not" bars. The dry run therefore uses a **synthetic fixture** episode
(`simulated: true`, neutral placeholder prompt strings, no regulatory claim, no PII) — which the
packet itself sanctions (deliverable 5 requires exactly a `simulated=true` fixture).
Verified this session: the fixture **PASSES the real gatekeeper** — `verdict: PASS`, 3/3 shots,
`projected_cr: 30`.

That gatekeeper run also **measured F2**: it projected `30 cr` for 3 shots (3 × 10) while the
client charges 20/clip → true cost 60 cr. The breaker under-reports by exactly 2×, on real output,
not by argument.

## F8 — THE PACKET'S BIGGEST FINDING: five doors, one credit pool, one gate

The mandate scopes the guard to WR3 (`wr3-clip-renderer` / the gatekeeper). Class-audited this
session (modus VERIFY: "a cure applied to 1-of-N paths is a time bomb"), the same charging
endpoints `/api/flow/generate-video` and `/api/flow/generate-image` on the same gateway
`127.0.0.1:8100` are reachable through **five** independent doors:

| Door | Lines | Charging call | Live? | Covered by this packet's gate |
|---|---|---|---|---|
| `scripts/wr3_flowkit_client.py` (WR3) | — | both | live | **YES** |
| `scripts/flowkit_cli.py` | 854 | `:617` image, `:382` video | **live** — a plain CLI, any terminal | no |
| `scripts/wr2_flowkit_client.py` (WR2) | — | `:308` image | **live** — `WR2_IMAGE_BACKEND=auto` probes FlowKit first | no — ceiling forbids WR2 edits |
| `apps/zantara-media/zantara_media/magazine/media_resolver.py` | 954 | `:671` image | **live** | no |
| `apps/nuzantara-mcp/nuzantara_mcp/tools/flowkit.py` | 424 | `:339` image, `:395` video | **DORMANT** | no |

**On the MCP door, stated precisely rather than dramatically** (verified, not assumed):
`.mcp.json` registers only `nuzantara-knowledge` → `server_knowledge.py`, which is fail-closed by
allowlist and registers ONLY `knowledge` + `pricing`. The flowkit tools are registered in
`server.py:184`, and `server.py` is **not** in `.mcp.json`. So no LLM can spend Veo credits through
MCP today. The risk is latent, not active: registering `server.py` would hand any model a
credit-spending tool (`flowkit_generate_video`) with no decision token anywhere in its path — and
that tool stages the CLI onto Pro over ssh, so it is remote execution as well as spend.

**Consequence, said plainly:** delivered exactly as specified, this packet makes the WR3 **library**
zero-spend (through the CLI driver it is unreachable — see F11) and
leaves four other doors to the same pool ungated. That is not a reason to widen the diff past the
ceiling — it is a reason the successor dispatch must be scoped to the CHOKE POINT (the gateway
itself, or a shared authority module every client imports), not to WR3. One PENDING-ARMS line per
door, and the P11 handoff inherits the whole list.

## F9 — the ledger records the charge in the wrong place (found reviewing the lane's diff)
`record_spend` was placed after `_download_video_media` succeeds. The charge happens at
`_generate_video`. A download failure therefore loses the record of a charge that already occurred —
and `wr3_render_episode.py` retries a failed shot **3×**, so one shot can be charged three times and
logged zero. Fixed during integration: record at the charge, not after the artifact arrives.


## F1b — CORRECTION to my own count: 34 was wrong, and the right answer is a RANGE

I asserted "34 real `.mp4` clips were rendered". That was a raw `find -name '*.mp4' | wc -l` over
the whole episode tree. The implementer lane caught it; I re-verified on disk and the lane is right:

- `master.mp4` (81,942,171 bytes, Jun 2) is the **assembled final episode**, not a clip charge.
- `clips_lipsync_bak_20260602T201944/` holds the **identical 11 shot numbers** as `clips_lipsync/` — a pure backup.
- `clips_original_backup_2026-06-01/606.mp4` duplicates `clips/606.mp4`.

Distinct shot keys: `01 02 04 06 07 09 10 11 13 17 18 606` = **12**.

**But 12 is a FLOOR, not a measurement, and that is the sharper point.**
`clips_lipsync_incoming_2026-06-03/` contains **both** `01_before_0432.mp4` and
`01_replaced_0433.mp4` — a **re-render of shot 01**. A re-render is a fresh Veo charge, and
dedupe-by-shot-key cannot see it. So the true number of charges lies in **[12, 34]** and **nothing
on disk can settle it**.

That range IS finding F1. The artifacts cannot tell you what was spent — which is precisely why a
ledger written at the charge site is the deliverable, and why a backfill must be reported as a lower
bound rather than a number.

## D4 proof design — REVISED after the refuter's verdict

The refuter's bottom line: *"the per-record arithmetic is correct where tested, but the claim
'before == after ⇒ no overspend' is not supported by this ledger"* — and specifically:
**a windowed report cannot carry the proof**, because with `--days 30` any spend older than the
window is invisible, so two windowed reports straddling an old overspend read identically.

So the PROVE-LIVE pair is NOT `report --days 30` before and after. It is a **four-part tuple**,
captured before and after, unwindowed:

1. **unwindowed total credits** (no `--days`) — a windowed total can hide an old delta;
2. **total record COUNT** — proves *no new rows appeared*, which a credit total of 0 cannot
   (a placeholder row and a swallowed-write both read as "no change" in credits alone);
3. **the resolved absolute ledger path** — printed by both runs, so a comparison across two
   different files (the `WR3_CREDIT_LEDGER` divergence) is visible on its face;
4. **the integrity line** — `OK` vs `DEGRADED — N write failure(s)`. A run whose ledger could not
   certify completeness does not get to claim zero spend.

**What would make this proof RED** (stated in advance, per the verification discipline):
any of — total credits differ; record count differs by anything other than the expected N
`placeholder` rows; the two runs print different ledger paths; integrity reads DEGRADED; or a
socket to the gateway is opened at all (caught by pointing `WR3_FLOWKIT_ENDPOINT` at a dead port).

**What this proof still CANNOT certify, stated plainly rather than glossed:** the ledger sees only
spend that passes the one instrumented call site. Per F8 there are four other live doors to the same
credit pool. So the honest claim is *"this run spent zero credits through WR3"*, never *"zero
credits were spent"*. The packet must not be reported as more than that.


## F1c — the range [12, 34] was ALSO wrong, and the correct answer is "undeterminable"

Byte-comparing the artifacts (this session) refutes both my `[12, 34]` and the implementer lane's
judgement that the sibling dirs are staging copies:

| Comparison | Result |
|---|---|
| `clips_lipsync_bak_20260602T201944` vs `clips_lipsync` | **3 identical, 8 DIFFERING** — not a pure backup |
| `clips_original_backup_2026-06-01/606.mp4` vs `clips/606.mp4` | identical — a true backup |
| `clips_lipsync_incoming_2026-06-03` vs `clips_lipsync` | 7 identical (staging copies), **shot 01 has two files, both differing** |

Byte-distinct contents, excluding `master.mp4` and exact duplicates: **22**.

**But 22 is not an upper bound on Veo charges, and this is the point.** Those directories hold
**lipsync** output — a local post-process. Re-encoding a clip changes its bytes **without any Veo
call**. So a byte difference does not evidence a second render, and the filesystem cannot
distinguish "re-rendered by Veo" from "re-encoded locally".

**Corrected finding:** the lower bound is 12 (distinct shot keys). There is **no derivable upper
bound** — not 34, not 22. The artifacts cannot settle the historical spend *even in principle*,
because the evidence a charge leaves (an API call) and the evidence a file carries (bytes) are not
the same evidence.

That is a stronger statement of F1 than the one it replaces: the ledger is not merely missing, it
is **unreconstructible after the fact**. Only a record written at the charge site can ever answer
this question — which is what this packet adds, and why the backfill is labelled a FLOOR with no
ceiling claimed.


## Adversarial review

Refuted by **Kimi K3** (cross-family, fresh context) against the whole evidence package. Accepted
findings, applied above or recorded here:

1. **A SIXTH door exists and this document missed it — the Google Flow web UI.** A human opening
   Flow in a browser and clicking generate spends the *same* credit pool and traverses none of the
   five code doors. The repo even carries a skill (`nuzantara-flowkit-flow-generation`) describing
   that manual path. No code gate can ever cover it. F8's table is therefore a count of *repo* doors,
   not of ways to spend.
2. **The MCP dormancy claim was scoped too broadly.** I proved it from ONE config file (`.mcp.json`
   registering only `server_knowledge.py`). Other agent CLIs on this fleet (kimi, codex, agy) carry
   their own MCP registrations, unexamined. Corrected claim: *no MCP server registered in this repo's
   `.mcp.json` exposes the flowkit tools*; whether another client registers `server.py` is
   **UNVERIFIED**.
3. **F8's audit is a lower bound, not a census.** It found doors by grepping charging-endpoint
   strings; a caller reaching the gateway via `localhost:8100`, a tailnet address, or an
   env-configured base URL would not match. "Five doors" means "five found by this search".
4. **The floor was challenged as 13, not 12 — and the challenge is itself refuted by F1c.** The
   refuter argued the surviving `01_before`/`01_replaced` pair proves a second charge, so the floor
   is 13. But F1c establishes that these directories hold **lipsync** output, and a local re-encode
   changes bytes with no Veo call. Byte difference does not evidence a render. **The floor stays 12**,
   and the reason it cannot be raised is the same reason it cannot be capped.
5. **The dead-port canary covers less than implied — CONCEDED, verified.** It only redirects paths
   that honor `WR3_FLOWKIT_ENDPOINT`. Measured: `wr3_probe_single_clip.py:17` **hardcodes**
   `http://127.0.0.1:8100`, and `flowkit_cli.py:26` reads a *different* variable
   (`FLOWKIT_BASE_URL`). The probe script is nonetheless safe — but by the **gate**, which raises
   before any socket, not by the canary. Two distinct protections; conflating them overstated the
   canary.
6. **The most dangerous unstated assumption — ACCEPTED, and it belongs at the top of any report of
   this packet.** *The Google account balance is never queried.* Every claim here is about the
   instrumentation, not about credits. The honest ceiling on what this packet can ever prove is
   **"this process spent nothing through the instrumented WR3 path"** — never "no credits were
   spent". Concurrent spend from another door, a queued job completing later, or a human in the web
   UI are all invisible to it by construction.
