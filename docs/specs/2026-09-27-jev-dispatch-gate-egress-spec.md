# Jev dispatch gate — outbound state (egress) specification

> **Status:** FROZEN 2026-09-27, written after the r2 on-disk gate of PR #7487 found that the
> correction commit (clip-before-redact) leaked PII fragments at the cut points. Builder
> Contract §1: a fix-of-a-fix stops at depth 1; the surface was under-specified, so this is
> the spec. Consumer: `infra/claude-hooks/jev_dispatch_gate.py::build_state`.
> Ruling: RULED 2026-09-27 (`docs/rules/RULINGS.md`).

## 1. What may leave the machine

Exactly one JSON object per judged dispatch, sent to the TypeSafe endpoint pinned in
`scripts/typesafe_client.py`, with four fields and nothing else:

| field             | source                     | bound                                   | transform                       |
| ----------------- | -------------------------- | --------------------------------------- | ------------------------------- |
| `description`     | `tool_input.description`   | 500 chars + separator                   | redact, then cut (§3)           |
| `subagent_type`   | `tool_input.subagent_type` | 80 chars                                | none (caller-chosen identifier) |
| `requested_model` | `tool_input.model`         | 80 chars                                | none                            |
| `prompt`          | `tool_input.prompt`        | HEAD 5000 + TAIL 1500 chars + separator | redact, then cut (§3)           |

## 2. What never leaves

- The whole dispatch when the raw description+prompt is PII-shaped (`pii|ktp|nik|npwp|passport|paspor`,
  or `client` with a data-ish token), judged by a cabled regex BEFORE any transform.
- Anything when the redactor raises: the hook skips Jev with receipt `skip=redaction_failed`.
- The credential: the hook never reads `TYPESAFE_API_KEY`; only the pinned client does.
- Any prompt or description text into receipts, stdout messages or the deny reason.

## 3. Redact everything, then cut — and why the two earlier shapes are rejected

Redaction masks tokens; a cut can split a token; a split token escapes the mask. **No cut may
precede a mask.** The whole text is redacted, then cut:

```
red = redact(text)
state.prompt = red if len(red) <= HEAD + TAIL else red[:HEAD] + "\n[...]\n" + red[-TAIL:]
```

A cut on a redacted string can split at most a placeholder. The time bound comes from the
masks, not from the cut: every pattern has bounded lookahead, so redaction is linear in the
input — email local part ≤ 64 chars and ≤ 8 domain labels of ≤ 63; phone body 7–40 chars with
no newline; digit and opaque runs are greedy single passes; name runs are structured; the
credential value is one `\S+`. Measured worst case 0.6 s on 200 000 pathological characters (a bare run of word characters against the email mask).

Rejected shapes, recorded so nobody rebuilds them:

- **clip-then-redact** (correction r1, PR #7487): the cut splits tokens and the fragments
  escape every pattern — an email local part, 31 of 37 chars of an opaque token and half a
  surname reached the vendor (gate r2).
- **windowed redaction with a margin** (correction r2): cutting the REDACTED window at a fixed
  offset assumes masks do not move the cut; when masks shrink the window by more than the
  margin the cut slides past it and the fragment at the window edge leaks (gate r3).

Masks, in order: credential assignments (`token|secret|password|passwd|api_key|apikey|
authorization` `[:=]` value, and `bearer` + value) → `[SECRET]`; emails → `[EMAIL]`; opaque runs
≥ 32 `[A-Za-z0-9_-]` → `[TOKEN]`; digit runs ≥ 6 → `[NUM]`; phone shapes → `[PHONE]`; runs of ≥ 2
capitalised words unless every word is in the technical allowlist → `[NAME]`. The repository
redactor (`scripts/_redact_pii.Redactor.load_static().redact_fragment`) runs first when
importable; its static passes cover team first names, credential shapes and emails per its
config — **it does not cover CRM client names** (`load_static` leaves pass4 empty by design).

## 4. Known limits, stated

- Lowercase or single-word personal names are not recognised: no name list exists in the hook
  process. Cover: the PII-shaped skip (§2) and the over-redaction bias of the name rule.
- The whole-process alarm (deadline + 3 s) raises a `BaseException` subclass so no broad
  `except Exception` can swallow it; it bounds the hook, it does not make it fast.

## 5. Tests that pin this spec (`scripts/tests/test_jev_dispatch_gate.py`)

- an email, a 37-char opaque token and a two-word name placed exactly across the head cut and
  across the tail cut never appear in the outbound prompt, not even as fragments;
- the same holds when masks before the cut shrink the text by far more than any margin;
- every mask finishes in under 1.5 s on 200 000 pathological characters of six shapes;
- the outbound prompt length is bounded by HEAD + TAIL + separator;
- `Authorization: Bearer <short>` is masked whole;
- a 200 000-char prompt is judged in under 4 s with exit 0.
