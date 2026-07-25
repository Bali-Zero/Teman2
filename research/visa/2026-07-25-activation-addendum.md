---
date: 2026-07-25
domain: visa
client_case: none
author: Kimi (Air-M5) — W2 closeout: pack on main; activation addendum
adversarial_review: kimi
status: READY — completes the arming runbook with the exact activation ops
---

# Activation addendum — provisioning + activating the first PRODUCTION pack

Complements `research/visa/2026-07-24-shadow-arming-runbook.md`. With #3090 merged
(`3c412c96b085`), the signed pack `rulepack-prod-001.signed.json` is on main at
`apps/backend-rag/backend/services/visa_engine/contracts/packs/`. This is the exact ops
sequence to make it the active PRODUCTION ruleset. DB steps run on Pro against the prod
DB; never from M5 directly (R3); the read-only credential is NOT enough for these steps —
they need the operator's write-capable role, one-time.

## Step 1 — provision the executor role (one-time, operator)

Migration 251 auto-grants only if the role exists at apply time; it did not, so provision
manually (as a superuser):

```sql
CREATE ROLE visa_activation_executor NOLOGIN;
GRANT SELECT, INSERT ON TABLE public.visa_rule_packs TO visa_activation_executor;
GRANT EXECUTE ON FUNCTION public.visa_activate_rule_pack(uuid, text, text)
  TO visa_activation_executor;
-- then GRANT visa_activation_executor TO <the activating app's/operator's role>;
```

## Step 2 — insert + activate (ops tool needed)

No activation script exists yet (pack count in prod is 0). Small tool to build
(`apps/backend-rag/backend/scripts/visa_engine/activate_pack.py`): reads the signed bundle,
verifies it against the trust store (fail-closed — never insert an unverifiable pack),
inserts it into `public.visa_rule_packs` via the repository's pack-insert path, then calls:

```sql
SELECT public.visa_activate_rule_pack(
  '446ee4ee-1bae-5b9e-b361-ea26f2ab5dd9'::uuid,  -- rule_pack_id
  '<activating-actor-token>',                    -- e.g. 'operator.zero-2026-07'
  '<reason token>'                               -- e.g. 'w2-first-prod-pack'
) AS activation_id;
```

The writer is append-only and self-guarding (migration 251/253/254): hash-chain check
against the pack's own `payload_sha256`, partial legal-period overlap refusal, sequence
rollback guard. A failed call raises — never partial-activates.

## Step 3 — verify activation

```sql
SELECT rule_pack_id, environment, is_active, activated_at
FROM public.visa_ruleset_activations
WHERE rule_pack_id = '446ee4ee-1bae-5b9e-b361-ea26f2ab5dd9';
```

Then the SHADOW secrets from the arming runbook, then the smoke (endpoint flips from
`EVALUATE_SURFACE_DISABLED` TEMP to real CURATED-mode evaluation + first `visa_decisions`
row with `engine_surface='RECOMMEND'`).

## Adversarial review

Self-reviewed (kimi): the function signature/grants were read from migration 251 + the
repository call site (3 args: uuid, text, text), not assumed. The ops tool is explicitly
NOT built yet — flagged as the next W item. None survived, 0 raised.
