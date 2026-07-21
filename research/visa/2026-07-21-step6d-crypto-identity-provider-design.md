---
date: 2026-07-21
domain: visa
client_case: none (platform/engine infrastructure — Visa Oracle decision engine)
sources:
  - apps/backend-rag/backend/services/visa_engine/evaluator.py (IdentityProvider contract; _facts_fingerprint; _deterministic_ids; _placeholder_identity_provider)
  - apps/backend-rag/backend/services/visa_engine/bundle.py (StaticTrustStore.from_env — the env-key-loader pattern mirrored here)
  - apps/backend-rag/backend/services/visa_engine/shadow.py (the one production caller of evaluate(); the PlaceholderIdentityNotAllowedError skip path)
  - apps/backend-rag/backend/services/visa_engine/models.py (Fingerprint, RulePackRef)
  - research/visa/2026-07-20-step6c-shadow-wiring-design.md (§1 OUT / §5 limitations naming STEP-6d)
---

# STEP-6d — real crypto-backed IdentityProvider (visa_engine/crypto.py)

## 1. Scope
The evaluator computes a per-decision DecisionIdentity = (decision_id, public_id, facts_fingerprint). The default `_placeholder_identity_provider` uses a NON-secret HMAC key and fail-closes (PlaceholderIdentityNotAllowedError) for any environment != TEST. Consequence today: SHADOW yields real visa_decisions rows only for a TEST-env activated pack; STAGING/PRODUCTION packs hit the guard and shadow skips.

STEP-6d ships the real crypto-backed provider so STAGING/PRODUCTION packs get a genuine secret-keyed identity — unblocking the real SHADOW signal (the substrate the ENFORCE-GATE needs).

IN scope: the HMAC facts-fingerprint key store + the real IdentityProvider + the env resolver + shadow wiring + tests.
OUT of scope (documented deferral in crypto.py's docstring): AesGcmPayloadCipher / EncryptedPayload / Pseudonymizer (subject/consent pseudonymization, encrypted visa_decision_payloads) — they serve tables migration 252 deliberately omitted; building them now is scope-creep against a non-existent consumer.
No DB migration: migration 252 (visa_decisions) does NOT persist facts_hmac; the fingerprint lives only in the in-memory Decision; decision_id/public_id stay deterministic. Zero schema change.

## 2. Governing invariant
Per evaluator.py divergence note #4: the real provider differs from the placeholder in EXACTLY one thing — the HMAC key (non-secret placeholder → real secret with a real key_id). decision_id/public_id are the SAME deterministic derivation and change only because their facts_digest input changes with the key (the point: a secret-keyed digest makes public_id genuinely unguessable). Derivation parity is a correctness invariant → we DO NOT duplicate the derivation in crypto.py; we extract a shared public helper `evaluator.build_decision_identity(...)` that BOTH the placeholder and the real provider call. `_facts_fingerprint` is generalized to accept (key, key_id) defaulting to the placeholder constants.

## 3. Key store (crypto.py) — mirrors StaticTrustStore.from_env
NEW symmetric key store, distinct from the Ed25519 trust store (asymmetric, pack-signature-scoped). Env var VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON — JSON array of {kid, secret(base64url-unpadded, >=32 bytes decoded), environment, valid_from, valid_to, revoked_at}. Fail-closed (typed FactsFingerprintKeyError) on: env unset/empty, non-JSON, non-array, malformed/duplicate entry, secret below the 32-byte (256-bit) HMAC floor, naive (non-tz-aware) datetime. No filesystem access; the key ceremony is the operator's, offline — respects the __init__.py FIREBREAK (no key GENERATION; key USE is fine). Keys are environment-scoped (TEST/STAGING/PRODUCTION).

Key selection is DETERMINISTIC on effective_at (the provider gets no wall-clock — evaluate() is pure): among the store's keys for `environment` that are in-window at effective_at ([valid_from, valid_to), valid_to=None=open) and not revoked-as-of effective_at, pick the latest valid_from (tie-break: highest kid). None → FactsFingerprintKeyUnavailableError. In the shadow path effective_at==now (tz-aware UTC), so this == "current signing key".

## 4. Public surface of crypto.py
FactsFingerprintKey (frozen: kid, secret: bytes, environment, valid_from, valid_to, revoked_at). FactsFingerprintKeyStore (.select(environment, effective_at); .from_env(); .from_iterable()). build_identity_provider(store) -> IdentityProvider (delegates to evaluator.build_decision_identity). resolve_identity_provider() -> if env var unset/empty return evaluator._placeholder_identity_provider (UNCHANGED behavior); else build the store and return the real provider. Errors FactsFingerprintKeyError (config/parse) + FactsFingerprintKeyUnavailableError (no active key) in errors.py, both VisaEngineError subclasses.

## 5. Shadow wiring
At shadow's single evaluate() call: identity_provider = resolve_identity_provider(); pass identity_provider=. Broaden the except from PlaceholderIdentityNotAllowedError to (PlaceholderIdentityNotAllowedError, FactsFingerprintKeyUnavailableError) → skip. FactsFingerprintKeyError (malformed config) is caught by the outer whole-body except Exception (logs type(exc).__name__ only — never the secret, Law 2). Firebreak preserved: env var unset (default prod) → resolver returns placeholder → PROD still fail-closes → no behavior change on deploy. Once the operator provisions a PRODUCTION key, prod packs start writing real rows. Flip is operator-gated (key ceremony), like the trust store.

## 6. Security posture (adversarial checklist)
Secret never logged / never in an exception message (only kid/environment/counts). HMAC key floor 32 bytes. Fail-closed on every malformed-config + no-active-key path; default (unset) == placeholder == current fail-closed behavior. Determinism preserved (evaluator determinism tests stay green). No cyclic import (crypto imports evaluator; evaluator does NOT import crypto). public_id still NOT an access-control capability even with a real secret.

## 7. Tests
test_crypto_identity.py: store loading (valid → store; unset/badJSON/non-array/missing-field/bad-base64/dup-kid/short-secret/naive-dt → FactsFingerprintKeyError); selection (single open-ended resolves; env mismatch/revoked/out-of-window → unavailable; rotation two-keys → latest valid_from wins; tie-break by kid); provider (build_identity_provider in evaluate(..., identity_provider=) on a PRODUCTION pack → Decision, no raise; fingerprint uses the real key_id; decision_id/public_id differ from placeholder yet deterministic across repeats); resolver (unset → placeholder; set with PROD key → real provider). Update test_shadow_match.py: keep the placeholder-noop test valid for the UNSET case; ADD a PRODUCTION-pack + provisioned-PROD-key test → a row IS written (still SHADOW). Unchanged & must stay green: test_evaluator_determinism.py, test_evaluator_gate_round1.py.

## 8. Gate
generator≠grader cross-family: Codex GPT-5.6-sol (crypto red-team) + Kimi K3 (refuter). Fable does the final on-disk gate. No self-merge before green + R1 record.

## 9. Cross-family gate outcomes (2026-07-21, R1 record)

generator = Sonnet 5 implementer (per exact spec). Graders (generator≠grader, cross-family):

- **Kimi K3 (Moonshot)** — LIVE. Full-file review. 1 Medium + 4 Low/cosmetic.
- **Gemini 3.1 Pro (agy, Google)** — LIVE. Diff+file review. Converged on the Medium; 1 new Medium (revocation), 1 false-positive (diff-only context), 1 info.
- **Codex GPT-5.6-sol / gpt-5.1-codex (OpenAI)** — DEAD (all gpt-5.x slugs 400 "not supported with ChatGPT account"). Declared.
- **GLM 5.2 (Zhipu)** — DEAD (Keychain token absent). Declared.
- **Fable (final on-disk gate)** — independent re-read + re-run of the full targeted suite; added the secret-dependence test proactively.

Dispositions (all findings verified on disk before acting — W65 verdicts are leads):

1. **[Medium, Kimi+Gemini CONVERGED] dataclass auto-`__repr__` leaks the 256-bit secret** → FIXED: `secret: bytes = field(repr=False)` + regression test `test_secret_never_appears_in_repr`.
2. **[Low, Kimi] empty JSON array `[]` silently breaks the TEST placeholder path** → FIXED: `from_env` rejects empty array + test.
3. **[Low, Kimi] duplicate `kid` allowed across environments → ambiguous `Fingerprint.key_id`** → FIXED: global kid uniqueness in `__post_init__` + test.
4. **[Low, Kimi] naive `effective_at` silently coerced to UTC in `select` but not in the id seed** → FIXED: removed the silent coercion, added an explicit fail-closed guard + test.
5. **[cosmetic, Kimi] malformed-config `FactsFingerprintKeyError` logged as "evaluate() failed"** → FIXED: dedicated `except FactsFingerprintKeyError` in shadow with a clear message.
6. **[High-claimed, Gemini] shadow omits `FactsFingerprintKeyError` from its except → crash** → FALSE POSITIVE (diff-only context): the generic `except Exception` already caught it (Kimi, full-file, correctly ranked it cosmetic), and #5 now catches it explicitly. No action.
7. **[Medium, Gemini — NEW] revoked key remains selectable for retroactive `effective_at`** → DOCUMENTED, not "fixed": binding selection to `effective_at` is the deliberate audit-reproducibility design (a hard-revocation change would break historical replay). NOT reachable on the shadow path (`effective_at = now` excludes revoked keys for new decisions) and `public_id` is explicitly not an access-control capability. The boundary + the required future hardening (a wall-clock revocation check for any future flow that mints from caller-supplied historical `effective_at`, or treats the id as authoritative) are documented in `crypto.FactsFingerprintKey.is_active_at`.
8. **[info, Gemini] base64 decode relies on `binascii.Error ⊂ ValueError`** → CONFIRMED correct (py3.3+); no action.

Refactor equivalence (old placeholder body vs `build_decision_identity` with the placeholder key) verified byte-identical by BOTH live seats + the unchanged determinism suite.
