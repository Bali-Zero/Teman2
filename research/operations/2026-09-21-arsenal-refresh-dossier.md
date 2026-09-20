---
date: 2026-09-21
domain: operations
client_case: none
adversarial_review: codex
sources:
  - https://openai.com/index/gpt-5-6/
  - https://developers.openai.com/codex/changelog
  - https://developers.googleblog.com/en/an-important-update-transitioning-gemini-cli-to-antigravity-cli/
  - https://ai.google.dev/gemini-api/docs/latest-model
  - https://blog.modelcontextprotocol.io/posts/2026-07-28
  - https://modelcontextprotocol.io/specification/2026-07-28
  - https://github.com/ollama/ollama/releases
  - https://qwen.ai/blog?id=qwen3.8
  - https://z.ai/subscribe
  - https://api-docs.deepseek.com/
  - https://github.com/deepseek-ai
---

# Arsenal refresh — what changed June–September 2026, and what it costs us

Six research lanes (Anthropic, OpenAI, Google, China seats, local+MCP, TypeSafe). **Every claim
that touches our own stack was re-verified on disk before it entered this file**; lane output
that could not be verified is quarantined in §7 rather than promoted.

The headline is not a model. It is that our declared topology has drifted from our own machines,
and that four standing alarms turned out to be misreadings.

---

## 1. The finding that outranks the rest

`MODEL_TOPOLOGY.json` is `_updated: 2026-06-16`. Measured against the live daemons on 2026-09-21:

| Machine | ollama-shaped roles resolving |
|---|---|
| pro | 5 / 16 |
| mini | 8 / 16 |

Declared but installed **nowhere**: `gemma3:27b` (`translation`, `cron_fallback`), `gemma4:26b`
(`kg_json`, `cell_tier1`, and named in 19 source files), `deepseek-r1:32b` (`reasoning`),
`qwen3:4b` (`sentry`), `aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m` (`intake_extraction`).

Installed but **undeclared**: `muse-glimmer:30b-mlx` (pro, 21GB), `qwen3.8:27b-mlx` (pro AND mini,
18GB), `qwen3-vl:8b` (mini, 6.1GB), `glm-ocr`, `bge-m3`, `nomic-embed-text`.

Three of the five models a research lane recommended "to try" were already installed, one of them
for two months. The gap is not between us and the state of the art. It is between our SSOT and
our own disks.

**`intake_extraction` is broken, not degraded.** `ocr_vision` survives its drift because
`classify.py`'s hardcoded default (`qwen2.5vl:7b`) is installed. `extract.py:48` defaults to the
*same absent SEA-LION model* the topology names, so role → default both terminate on something that
is not there. The `INTAKE_EXTRACTION_MODEL` env override is the one escape, and the repo sets it
nowhere outside tests — if it is set in the deployed environment, that is invisible from here and
would change this verdict.

Also: `qwen3.8:27b-mlx` (18GB) sits on mini's 24GB. The policy in that same file names only
`gemma4:26b` as forbidden there and otherwise allows cold loads for explicit jobs — so this is a
tension worth a look, **not** a policy violation: installed is not resident.

→ Probe shipped: PR #6975, first probe of the `defined<->live` class, `machines: ["pro","mini"]`.
It reports the drift and deliberately does not choose replacements — that is a quality decision
with a client-document cost.

---

## 2. Four alarms that were misreadings

| Alarm | What it actually was |
|---|---|
| "Gemini CLI deprecated 2026-06-18 → `agy` dead for 3 months" | `agy` **is** the new binary's name. Live: Antigravity CLI **1.2.7**, Go, migrated 19 Sep. Nothing to do. |
| Three `tp1-` seats `QUOTA_DEAD` | HTTP 429 `insufficient_quota`, reset **2026-09-25 10:19 UTC**. Models all alive and vendor-confirmed. Nothing to buy. |
| "MCP spec 2026-07-28 breaks our server" | Not today — but **not because we pinned**. `apps/nuzantara-mcp/pyproject.toml` declares `fastmcp>=2.0.0`, an OPEN constraint; the venv merely happens to hold `fastmcp 3.4.3` / `mcp 1.28.1`. A `pip install -U` pulls 4.x and the breaking change with it. Deprecation floor is July 2027; our protection expires at the next upgrade. |
| "DeepSeek R2" as an open-weight release | The `deepseek-ai` GitHub org publishes neither R2 nor V4 weights; last published reasoning model is V3.2-Exp. This does **not** contradict §4: `deepseek-v4-pro`/`-flash` are documented API models on `api-docs.deepseek.com`. API model ≠ open weights, and the earlier lane conflated them. |

**The `tp1-` result carries a second observation worth more than the first:** all three report the
identical message and the identical reset instant (`09-25 10:19:00 UTC`). The simplest explanation
is one shared Alibaba Token Plan serving Qwen, GLM and DeepSeek — but a shared reset instant is
consistent with three separate plans opened together on the same weekly cycle, and this run did not
distinguish the two. **What is measured is that they died together**; whether they share one pool is
inferred. It matters, because if inferred correctly the cascade's three fallbacks degrade as one —
family #2 in a shape we have not catalogued. Falsifiable cheaply: spend one seat's quota and watch
whether the others move.

---

## 3. Capability we already own and do not use

`agy` 1.2.7 is a second agent harness sitting unused on every machine:

| Flag / subcommand | What it would buy us |
|---|---|
| `--json-schema` + `--output-format stream-json` | typed, schema-enforced output from an external seat — today we parse stdout by hand |
| `--mode plan` | an external seat **structurally** unable to ship, which is BUILDER CONTRACT §5 enforced by the machine rather than by discipline |
| `agent` / `agents`, `plugin`, `mcp` | native subagents; `nuzantara-knowledge` reachable from `agy`, not only from Claude |
| `--effort low\|medium\|high`, `--sandbox` | cost routing, and terminal restriction without `--dangerously-skip-permissions` |

`--mode plan` and `--json-schema` together are the pair worth the work.

---

## 4. Real changes, by door

**Anthropic** — Claude Code **2.1.278** live here. `AGENTS.md` is read as a fallback where no
`CLAUDE.md` exists (2.1.277); we already carry three door files. `TaskOutput` removed —
background output is read with `Read`, and `taskOutputMaxChars` / `TASK_MAX_OUTPUT_LENGTH` are
inert. Verified against `~/.claude/cache/changelog.md`, i.e. the shipped changelog, not a summary
of it.

**OpenAI** — GPT-5.6 (Sol / Terra / Luna) is real and vendor-confirmed. `codex mcp-server` is
**gone** in `codex-cli 0.155.1`: the removed subcommand falls through to the interactive CLI, so
any `.mcp.json` invoking it opens a session instead of a server and hangs. Our `.mcp.json` carries
only `nuzantara-knowledge`; no live damage, but `PENDING-ARMS.md:316` (codex-redteam on pro/mini)
should close as **obsolete upstream**, not as "still to align". GPT-5.3-Codex-Spark was deprecated
14 Sep — which is the external cause of the 400s we diagnosed empirically on 15 Sep and worked
around by moving the lane to `gpt-5.6-luna`. Worth adopting: `/review` and `codex-action` as a CI
gate, on subscription rather than per-token.

**Google** — Gemini CLI → Antigravity CLI, announced 19 May, cutoff 18 Jun; we are migrated. The
Flash line moved three times in six weeks (3.6 Jul → 3.7 Aug → **3.8 Sep**, 1M ctx) while the Pro
line has not moved since February — and `MODEL_TOPOLOGY.json` routes `agy_gemini_pro_high` at
**3.1 Pro**. Worth measuring, not adopting blind. NotebookLM renamed Gemini Notebook (16 Jul,
rename not shutdown); **since 2026-09-02 its quota is compute-based** rather than fixed, refreshing
every 5h against a weekly ceiling — we run ~60 notebooks on cron and did not register this.

**China seats** — Qwen3.8-Max, Kimi K3, GLM-5.3, DeepSeek V4-pro/-flash, MiniMax M2.7/M3 all
vendor-confirmed. GLM-5.3 (14 Aug) rides the same Coding Plan as 5.2 at no extra cost.

**Local** — real tags, `:cloud` excluded as not PII-safe: `qwen3-embedding:8b` (4.7GB, MTEB #1
multilingual), `qwen3-vl:8b-instruct-q4_K_M` (6.1GB, the same-footprint successor to the
`qwen2.5vl:7b` we run for `ocr_vision`), `deepseek-ocr:3b` (6.7GB), and for pro only
`nemotron-3.5-lightning:30b-a3b-mlx` (23GB) and `muse-glimmer:30b-q4_K_M` (18GB).
**SEA-LION is not on ollama at all** — `sea-lion`, `nemotron-sea-lion` and `sea-lion-embedding` all
404; ours would come from HuggingFace, and the tag the topology names has no official aisingapore
GGUF, only a community quantisation.

**MCP** — spec 2026-07-28 drops the `initialize` handshake and `Mcp-Session-Id`, adds
`server/discover`, replaces server-push (sampling / elicitation / roots) with Multi Round-Trip, and
deprecates Roots, Sampling, Logging, HTTP+SSE and OAuth DCR on a 12-month floor. `mcp` 2.0.0
shipped the same day; `fastmcp` 4.0.0 on 31 Aug. We are on the maintained old branch.

---

## 5. Jev / TypeSafe

Key provisioned 2026-09-20, validated against the live endpoint. Two dossiers merged (#6909,
#6922) covering 17 lanes. `scripts/typesafe_client.py` (branch `jev-ban-entity-v3`, unmerged)
matches the documented contract: endpoint, `Bearer`, `{model, state, questions}`, retry on the
documented `{429, 529}` pair, fail-open to `None`.

**Bench reproduced from a seat outside the lane** (2026-09-21, `jev-1.13.0`, ~$0.001):

```
guilt recall 16/19 · recall on grep-misses 15/17 · false alarms 0/20 · threshold 0.8
sensitivity: t=0.5 16/17 0/20 · t=0.6 15/17 0/20 · t=0.7 15/17 0/20 · t=0.8 15/17 0/20 · t=0.9 13/17 0/20
```

Identical to the lane's own receipt of 2026-09-20 — which is the point: the number existed, an
independent reproduction of it did not. **0.80 is confirmed by measurement**: recall is flat from
0.6 to 0.8, so 0.8 buys maximum margin for free. The stronger argument is the distribution — the
lowest caught guilt sits at 0.86, the highest innocence at 0.34, and exactly one case falls in the
0.52-wide gap between them. The threshold sits in a hole, not on a slope.

Two defects recorded on the lane's PR: `MODEL = "jev-latest"` is a moving alias in a CI gate (the
docs recommend pinning; `jev-1.13.0` is what these numbers were measured against), and `shell_curl`
(0.43) escapes at every threshold because all four questions are phrased in terms of
imports/SDKs/wrappers/credentials and none describes a shell process issuing a POST.

None of the 17 designed lanes covers multi-agent research orchestration — pre-dispatch dedup and
cross-agent contradiction are genuinely missing. Citation check (L5) and rerank (L2) are reusable
nearly as-is.

---

## 6. Method, which is the reusable part

**Three of six lanes ran without WebFetch.** It is a deferred tool in this session and the agents
did not know to load it with `ToolSearch`; they also cannot delegate to a `web-fetch` subagent
(child delegation depth). The first round therefore produced dates wrong by a year (2025 Ollama
features dated 2026), one false P1, one oversold claim, and one lane rewriting a dossier that had
merged the previous day — caught only because `ListAgents` was checked by hand.

Two agents recovered with `curl`; one with WebSearch restricted to official domains. Both work.
**Put it in the dispatch prompt**, together with the instruction to mark UNVERIFIED anything not
confirmed on a primary source — that instruction is the only reason the first round was salvageable.

---

## 7. UNVERIFIED

- Claude Code changelog June–September **line by line**: the lane worked from third-party summaries
  (`gradually.ai`, `releasebot.io`, `morphllm.com`, `digitalapplied.com`). The claims reproduced in
  §4 are only those re-checked against `~/.claude/cache/changelog.md` on disk. "Routines replace
  external cron" did **not** survive that check — the matching entries are Claude Tag and Claude
  Code on the web.
- Agent SDK → Managed Agents rename: single secondary source, no dated Anthropic post.
- Jules: no changelog entry found after 9 March 2026; absence of evidence only.
- `deepseek-ocr` on ollama: cannot tell whether the tag is v1 or v2; `deepseek-ocr-2` 404s.
- Gemini 3.8 Flash confirmed on `ai.google.dev`; the 90.8% Terminal-Bench 2.1 figure is the
  vendor's own and unreproduced by us.
- `Nemotron-SEA-LION-v4.8-30B-A3B` as a replacement for `intake_extraction`: official GGUF exists
  (23.7GB, fits pro's 48GB), but **no published benchmark compares it to the current model on
  Indonesian extraction**. A/B candidate, not a safe swap.
- TypeSafe batching multiplier (12.2×) is the vendor's, on the vendor's document.
- Whether the three `tp1-` seats share one quota pool or three same-cycle plans — see §2.
- Whether `INTAKE_EXTRACTION_MODEL` is set in the deployed environment; the repo does not set it,
  but a Fly secret would not be visible from the checkout.

## Adversarial review — 8. what the refuter broke

Codex, read-only, as a non-author. Five of its six hits landed and are folded in above rather than
patched silently, because the CLASS of each is more portable than the fix:

1. **"We pin `mcp`/`fastmcp`" was false, and it inverted the conclusion.** Those were the versions
   installed in a venv; the declared constraint is `fastmcp>=2.0.0`, wide open. "We are safe
   because we pinned" became "we are safe until someone upgrades" — a different sentence with a
   different owner.
2. **"env-override → role → default all terminate on something that is not there"** asserted the
   state of an environment variable this checkout cannot see.
3. **The mini RAM claim was an overread**: the policy forbids `gemma4:26b` by name and permits cold
   loads; *installed* was silently read as *resident*.
4. **"They are one Token Plan" was a mechanism inferred from a correlation** — a shared reset
   instant. Now stated as the observation plus the inference, with a cheap falsification.
5. **§2 and §4 contradicted each other on DeepSeek V4**, because one lane meant open weights and
   the other meant an API model, and this file adopted both words.

The sixth (vendor benchmarks, SEA-LION scope) was already quarantined in §7.
