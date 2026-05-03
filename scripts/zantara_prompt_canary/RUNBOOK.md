# ZANTARA prompt v2 — A/B canary runbook

> **Owner**: Zero (decision) + on-call engineer (execution)
> **Goal**: promote `ZANTARA_PROMPT_VERSION=v2` from off → 100% prod traffic
> with measurable quality gates and an instant-rollback escape hatch.
> **Time budget**: ~7 days end-to-end, ~30 min/day of human supervision.

---

## 0. Pre-flight (do once, before any flip)

```bash
# Working tree
cd ~/Projects/nuzantara

# 1. Verify the prompt diff is structurally clean
PYTHONPATH=apps/backend-rag python3 scripts/zantara_prompt_canary/diff_prompts.py
# Expect: ✅ READY for canary

# 2. Run the unit tests around the v2 module
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/test_zantara_core_v2.py -v
PYTHONPATH=. pytest backend/tests/unit/test_business_rules_i18n.py -v

# 3. Confirm the env var is currently unset / "v1" in prod
fly secrets list -a nuzantara-rag | grep -i prompt_version || echo "(unset → defaults to v1)"

# 4. Save a baseline of LangSmith trace counts for the last 24h (manual,
#    use the LangSmith UI → project nuzantara-rag → filter by tag
#    "prompt_version=v1" if instrumented, otherwise total volume).
#    Capture: messages/h, tool_calls/h, average response length, escalation_rate
```

---

## 1. Day 0 — shadow canary (5%)

**Goal**: collect signal without affecting most users. If something is
catastrophically wrong, only 1 in 20 conversations is affected.

```bash
# Set the flag on the rag app. This triggers a Fly rolling restart (~2 min).
fly secrets set ZANTARA_PROMPT_VERSION=v2 -a nuzantara-rag

# IMPORTANT: today there is no built-in 5%-traffic split. The flag is
# all-or-nothing per machine. Two options:
#   (a) "soft canary": deploy v2 to ALL rag machines but watch closely
#       for the first 30 min — if anything goes wrong, rollback in <5 min.
#   (b) "split canary": scale rag to 4 machines, set the secret per-machine
#       (fly machines update --env ZANTARA_PROMPT_VERSION=v2 <machine_id>)
#       on 1 of 4 → ~25% traffic. (Documented; (a) is the default below.)
```

After the secret flip, watch in this order:

| Watch | Where | Threshold for rollback |
|---|---|---|
| `fly logs -a nuzantara-rag` | terminal | any `Traceback`, `KeyError`, repeated `prompt_manager` errors |
| LangSmith → `nuzantara-rag` project, last 30 min | LangSmith UI | error rate >2x baseline, p95 latency >2x baseline |
| WhatsApp `@Balizerobot` test message | Telegram | response in your language (IT for Antonello) and references no Italian leftovers if you query in EN |
| Pricing rule sanity check (manual) | WhatsApp test | "How much for KITAS?" → answer must reference real prices, never invent ranges |

**Hold for ≥2 hours** at this stage. If clean → proceed to Day 1.
If anything trips → see "Rollback" below.

---

## 2. Day 1-2 — observation window

**No flag changes.** Just watch:

- LangSmith: collect 200+ real conversation traces, randomly sample 20.
- For each sampled trace, score 1-5 on:
  - Language correctness (response language matches user query)
  - Tool-use accuracy (`get_pricing`/`vector_search` called when expected)
  - Pricing rule adherence (no invented prices, "verify with team" used when missing)
  - Identity lock (no `I am ChatGPT`, no `as an AI language model`)
- Compare vs Day -1/-2 baseline: average score should be **≥95%** of v1.

Track the daily average in this file (manual):

```
date       avg_lang  avg_tools  avg_pricing  avg_identity  notes
2026-04-26  v1: 4.8  v1: 4.6    v1: 5.0      v1: 5.0       baseline
2026-04-27  v2: ?    v2: ?      v2: ?        v2: ?
2026-04-28  v2: ?    v2: ?      v2: ?        v2: ?
```

If any column drops >5% vs v1 → investigate first, then decide whether
to rollback.

---

## 3. Day 3 — owner sign-off + ramp

If 48h of data is clean:

- Antonello reviews 5 sample EN responses + 5 IT responses + 3 ID responses
  manually. Brand voice must match Zantara persona (warm, professional,
  not corporate).
- If Antonello signs off → leave at 100% (already there with the soft-canary
  default in step 1).
- If Antonello flags issues → list them on the PR for follow-up.

---

## 4. Day 7 — promote to permanent default

After 1 week of stable v2:

- Open `PR-18 follow-up`: rename `zantara_core_v2.py` → `zantara_core.py`,
  delete the v1 conditional in `prompt_manager.py`, drop the
  `ZANTARA_PROMPT_VERSION` env var from `fly.toml` and `fly secrets`.
- Merge → deploy → end of canary.

---

## ROLLBACK (any time, any stage)

The escape hatch is **always one command + ~2 min**:

```bash
fly secrets set ZANTARA_PROMPT_VERSION=v1 -a nuzantara-rag
# Fly auto-restarts the machines. Within ~120s every new request
# uses v1 again. In-flight requests finish with v2 (negligible blast
# radius — they were going to finish anyway).

# Verify:
fly logs -a nuzantara-rag | grep -i "PromptManager"
# Should NOT see "using zantara_core_v2" log line on new requests.

# Optional: bump the secret cleanly off (= remove it, default goes back to v1):
fly secrets unset ZANTARA_PROMPT_VERSION -a nuzantara-rag
```

After rollback:
1. Capture the symptom in writing (`docs/sessions/zantara-prompt-v2-rollback-YYYY-MM-DD.md`).
2. Add a regression test to `backend/tests/unit/test_zantara_core_v2.py`
   that would have caught it.
3. Fix in a follow-up PR before retrying canary.

---

## Useful commands

```bash
# Status of the flag right now
fly ssh console -a nuzantara-rag -C 'env | grep ZANTARA_PROMPT_VERSION'

# Verify which template is actually loaded
fly ssh console -a nuzantara-rag -C 'python3 -c "from backend.llm.prompt_manager import ZANTARA_MASTER_TEMPLATE; print(len(ZANTARA_MASTER_TEMPLATE))"'

# Tail logs filtered for prompt-related signals
fly logs -a nuzantara-rag | grep -E "PromptManager|prompt_version|zantara_core"

# Run the offline diff once more after any change to v2
PYTHONPATH=apps/backend-rag python3 scripts/zantara_prompt_canary/diff_prompts.py
```

---

## Why this is structured this way

- **Single env var** (`ZANTARA_PROMPT_VERSION`) gives a one-line rollback —
  the rollback time is the same as a Fly rolling restart (~2 min), so the
  blast radius is bounded by minutes, not hours.
- **No traffic splitter** in the codebase today, so the canary is a
  time-boxed soft canary (deploy + watch for 2h, then 48h observation).
  The cost of building a per-request feature flag is higher than the cost
  of a 2-hour watch session, so we accept the tradeoff.
- **Manual quality scoring** instead of automated LLM-as-judge — Zantara
  ships in 3 languages and the model that would judge it (Gemini) is the
  same one we are testing. Self-evaluation is unreliable here. Antonello
  + on-call engineer eyeballing 30 traces over 48h is more truthful than
  a 100% automated score.
