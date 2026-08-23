# P03 Deliverable 4 — zero-spend dry run (PROVE-LIVE)

**Host:** Pro · **Date:** 2026-08-23 ~12:23 WITA · **base:** `5117d9908a37cdc5f23924f6fe19cd823e2ed6c5`
**Episode:** synthetic fixture `simulated: true` (no real episode on disk carries a `shot-pack.json`,
and generating one would be *storyboard execution*, barred by the frozen must-not).

## The run

Path exercised: `submit_clip` per shot, adapting `shot_id → shot_index` **exactly as
`wr3_render_episode.py:46` does** (`int(shot["shot_id"].lstrip("s"))`) — i.e. the live production
call shape, not a convenience fixture. Env: `WR3_ZERO_SPEND=1`,
`WR3_FLOWKIT_ENDPOINT=http://127.0.0.1:1` (**dead port**), `WR3_CREDIT_LEDGER=<temp>`.

```
clips: 3
  shot 1  cost_cr=0  job=placeholder:dryrun-episode:01  01.mp4
  shot 2  cost_cr=0  job=placeholder:dryrun-episode:02  02.mp4
  shot 3  cost_cr=0  job=placeholder:dryrun-episode:03  03.mp4
SUM cost_credits = 0
```

| Property | Measured |
|---|---|
| clips | 3 × h264, **720×1280**, **8.000000 s**, 200 frames |
| clips distinct | sha256 `e10b59c7…` / `8ce10087…` / `a6a4a6c2…` — all different |
| ledger rows | 3, all `mode=placeholder`, `credits=0`, `veo_job_id=None`, `source=submit_clip:zero_spend` |
| **credits BEFORE → AFTER** | **0 → 0** |
| rows BEFORE → AFTER | 0 → 3 (three placeholder rows — the expected delta) |

## Why this proof is not empty — the two falsification checks

A green run against a dead port proves nothing on its own: the code might simply never have needed
the network. Both halves were therefore tested.

**A — the socket WOULD have opened.** Same episode, zero-spend OFF, valid decision token:
```
_generate_video → URLError <urlopen error [Errno 61] Connection refused>
```
So the port is genuinely dead **and** the charging path genuinely reaches for it. The zero-spend
run's success is not an artifact of an unused code path.

**B — the gate fires BEFORE the socket.** Same episode, no decision token:
```
_generate_video      → SpendNotAuthorizedError: WR3_SPEND_DECISION is unset or empty
_generate_start_image → SpendNotAuthorizedError: WR3_SPEND_DECISION is unset or empty
```
Note the discriminator: an **authorization** error, not a connection error. If the guard sat after
the POST we would have seen `URLError` here, as in A.

**What would make this RED:** credits differ · row count differs by anything but the 3 placeholder
rows · the two runs print different ledger paths · integrity reads DEGRADED · any byte reaches the
gateway (caught by A/B above).

## Gate mutation-verified (5/5 bite)
| Mutation of `wr3_spend_authority.py` | Result |
|---|---|
| gate always authorizes | **12 tests red** |
| `WR3_ZERO_SPEND` no longer wins over a token | **1 red** |
| log-write failure swallowed (spend unlogged) | **2 red** |
| `episode_id` match removed (token replay) | **1 red** |
| date check removed (stale token authorizes) | **2 red** |

## F10 / F11 — two gaps this run exposed, both stated rather than hidden

**F10 — `render_shot_pack` cannot read a real shot-pack.** It reads `shot["index"]` /
`positive_prompt`; the real schema is `shot_id` / `prompt_positive`. **Pre-existing** — present at
base SHA `5117d9908:scripts/wr3_flowkit_client.py:656-657` — and **knowingly** so: the 2026-05-30
design doc declares it out of scope verbatim ("pre-existing, the real renderer is the clip-renderer
agent dispatcher, not this function. Not introduced or fixed here"). Consequence for this packet:
any zero-spend test driven through `render_shot_pack` with an `{"index": …}` fixture would be
**green on a code path production never executes**. Not fixed here (it would change behaviour on a
real spend path, outside the mandate); the dry run above deliberately routes around it.

**F11 — the production driver does not honour zero-spend.** `scripts/wr3_render_episode.py:33`
calls `_health()` unconditionally, before any zero-spend consideration. Measured against a dead
port it dies with `URLError [Errno 61]`. Against the **live** gateway the consequence follows from
two independently measured facts — (i) that unconditional `_health()` call plus its
`return 2` on `extension_connected` false, read on disk this session; (ii) the live gateway answering
`extension_connected: false`, measured by curl this session — therefore **under zero-spend the
production driver halts with exit 2 and renders nothing**. *(Deduced from those two measurements; I
did not execute the driver against the live gateway — that command was declined, and I did not
retry it.)*

So zero-spend is currently reachable at the **library** level (`submit_clip`, `_generate_video`,
`_generate_start_image`, `render_shot_pack`) but **not** through the CLI driver. `wr3_render_episode.py`
is **outside this packet's owned file scope**, so it is NOT edited here. The exact successor patch:

```python
# scripts/wr3_render_episode.py, top of main(), before `h = _health()`
from wr3_spend_authority import zero_spend_enabled   # noqa: E402
if not zero_spend_enabled():
    h = _health()
    if not h.get("extension_connected"):
        ...
else:
    print("[render] WR3_ZERO_SPEND — health gate skipped, placeholder path", file=sys.stderr)
```
