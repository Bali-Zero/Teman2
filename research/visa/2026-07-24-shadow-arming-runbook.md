---
date: 2026-07-24
domain: visa
client_case: none
author: Kimi (Air-M5) — W1 arming runbook (post-#3061)
adversarial_review: kimi
status: READY — fires when the first signed PRODUCTION pack is activated (W2)
---

# SHADOW arming runbook — evaluate read-path API

Sequence discipline: **pack first, arm second.** With no active PRODUCTION pack the
endpoint answers TEMPORARILY_UNAVAILABLE (HTTP 200, `retryable=true`) and persists nothing —
arming early is inert but produces zero evidence, so don't bother before W2 lands a pack.

## Prerequisites (in order)

1. `#3061` merged + deployed on `nuzantara-rag` (evaluate endpoint live).
2. First signed PRODUCTION RulePack authored (W2, M5 key custody) and activated via
   `visa_activate_rule_pack()` — requires the `visa_activation_executor` DB role provisioned
   (the known test skip). Provisioning statement: see the activation-writer migration 251/253
   comments; the role is granted via the ops runbook, never ad-hoc.
3. Trust store already staged: `VISA_ENGINE_TRUST_STORE_KEYS_JSON` (digest `a68f076bc9993f0c`).

## Fly secrets to set (one operator action)

```bash
ssh pro 'bash -lc "fly secrets set -a nuzantara-rag \
  VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON=\"$(cat ~/.config/nuzantara/visa-signing/facts-fingerprint-keys.json)\" \
  VISA_ENGINE_EVALUATE_MODE=SHADOW \
  VISA_ENGINE_DRIVER_TOKEN=\"$(openssl rand -hex 32)\""'
```

- `VISA_ENGINE_EVALUATE_MODE=SHADOW` — arms the endpoint (OFF-default; resolver re-reads env
  per call, but Fly injects secrets at boot, so the set triggers one rolling redeploy).
- `VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON` — the HMAC store minted at the 2026-07-19 key
  ceremony (`docs/runbooks/visa-engine-key-ceremony.md`; M5 custody file, never committed).
- `VISA_ENGINE_DRIVER_TOKEN` — fresh random, shared ONLY with the W4 synthetic driver
  (X-Visa-Driver-Token header). Store a copy in the M5 custody dir (0600).
- Leave `VISA_ENGINE_MATCH_MODE` **OFF**: the v1 thin-fact path stays dark so the window's
  evidence is full-fact only (collector reads MATCH+RECOMMEND surfaces — MATCH rows would be
  legacy-class and counted toward neither gate anyway, but keeping it OFF keeps the window
  clean to read).

## Smoke (after redeploy)

1. **No-pack behavior (pre-activation only):** `POST /api/visa-oracle/evaluate` with a
   minimal valid facts body → expect 200 TEMP shape, `retryable=true`, and **zero** new rows
   in `visa_decisions`.
2. **First real row (post-activation):** same call → 200 ENGINE-mode-available response
   (`mode=CURATED` until ENFORCE is a thing), one `visa_decisions` row with
   `engine_surface='RECOMMEND'`, `engine_mode='SHADOW'`, `traffic_source='real'`, derived
   `request_category`, 32-byte fingerprint, `ruleset_activation_id` set.
3. **Driver check:** same call with `?traffic_source=synthetic_gold` WITHOUT the token →
   400; with `X-Visa-Driver-Token` → row with `traffic_source='synthetic_gold'`.
4. **Collector read-back:** `scripts/visa_shadow_evidence.py` (read-only) shows the rows in
   the right G-a-vol / G-a-breadth buckets.

## Rollback (G-d drill precursor)

`fly secrets unset -a nuzantara-rag VISA_ENGINE_EVALUATE_MODE` → one rolling redeploy and the
endpoint returns TEMP again instantly. The G-d drill (post G-a/G-c green) records exactly
this flip + back with before/after evidence.

## Adversarial review

Self-reviewed (kimi): the arm-early-is-inert claim rests on the endpoint's fail-closed
TEMP-with-zero-writes path (tested in #3061). The MATCH_MODE=OFF recommendation is a plan
decision (full-fact evidence only), not a code requirement. None survived, 0 raised.
