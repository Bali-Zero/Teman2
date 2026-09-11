# Decision — where the OCR inference runs (2026-08-28)

> **DECIDED by the session, not deferred.** An earlier report of mine handed this to Zero as a
> business call. That was wrong: it is an architecture decision with a compliance argument attached,
> and both halves are the session's to make and write down. What follows is the decision, the
> measurement that changed it, and the one gesture that is genuinely not a session's.

## The measurement that changes the question

**The uploaded image is never persisted, anywhere.** Read this turn in
`apps/backend-rag/backend/services/garuda_documents/service.py::_process_new_upload`: `raw_bytes` is
size-validated, checked as a readable image, base64-encoded, handed to
`extract_passport_biodata_dual_pass`, and then goes out of scope. The four outcome variants
(`ReadyOutcome`, `ProcessingOutcome`, `LowConfidenceOutcome`, `UnreadableOutcome`) carry a
`document_id` and extracted/uncertain **field names** — no bytes, no base64, no blob reference. The
store port (`ports.py::DocumentStorePort`) persists a `DocumentOutcome`, so there is no code path
that could write the image even if someone wanted to.

So the question was never "where do we store passport images". It is **"what sees them in transit,
for the duration of one request"** — a far narrower question, and one this codebase already answers
more strictly than any document claimed.

## What the guardrail actually says

`ocr_client.py`'s header declares **G-OCR-LOCAL — "never a cloud endpoint"** and pins
`qwen2.5vl:7b`. Read literally, that forbids sending the image to a cloud **vision API** (Gemini,
OpenAI, a hosted VLM). It protects **the model**, not the wire. A request that transits our own API
process and is inferred by a model on Zero's hardware does not violate it. Nothing in that header
requires the byte path to avoid our own infrastructure.

## The options, with their real exposure

|       | Path the bytes take                            | Who holds plaintext                           | Cost                                                                          |
| ----- | ---------------------------------------------- | --------------------------------------------- | ----------------------------------------------------------------------------- |
| **A** | phone → Fly (API) → Mini (model, over tailnet) | Fly, **transiently in RAM**, never on disk    | Fly must join the tailnet                                                     |
| **B** | phone → Mini directly                          | nobody but the Mini                           | public ingress to an office machine on a separate ISP line, TLS, availability |
| **C** | phone → Cloudflare tunnel → Mini               | Cloudflare edge (terminates TLS), transiently | same transient profile as A, plus one more party                              |

Option C is strictly worse than A: it has A's transient-plaintext property AND adds a third party, so
it is rejected. It is listed because a tunnel is the obvious-looking way to "keep it off Fly", and it
does not actually achieve that.

## DECISION: option A — Fly relays, the Mini infers, the image is never persisted

Four reasons, in order of weight:

1. **It satisfies the guardrail as written.** The model stays on Zero's hardware. That is what
   G-OCR-LOCAL protects.
2. **The ephemeral property is enforced by code, not by a promise.** There is no write path for the
   bytes, so "we don't keep passport images" is a structural fact a reviewer can check, not an
   operational commitment someone has to keep. This is the strongest thing available here and it is
   already true.
3. **It is buildable on the surface that already exists.** Option B means a new public ingress on a
   machine in the office on a separate ISP line — a second deploy target, its own TLS, and worse
   availability for a customer standing at a counter with a phone. For a dark launch that is a large
   amount of new risk bought with a marginal reduction in an already-transient exposure.
4. **It keeps one transfer question instead of inventing a second.** Option B does not remove the
   need for a transfer basis — it relocates it to whatever fronts the Mini.

### What this decision does NOT license

- **It is still an Art. 56 transfer** and it needs its basis written before the endpoint ships, in
  the same shape the chat-gateway gap in `PENDING-ARMS.md` already tracks. "Transient" reduces the
  exposure; it does not remove the obligation. Concretely: the DPA covering the Fly processor plus
  the consent the funnel already collects must be shown to cover an image, not only text, and if
  that cannot be shown before the endpoint exists, the endpoint must fail closed rather than ship.
- **No cloud vision fallback, ever.** If the Mini is unreachable, the endpoint returns
  `DocumentProcessingUnavailableError` and the customer is told to retry. `service.py` already does
  exactly this (it raises rather than degrading) — do not "improve" it into a Gemini fallback.
- **Option B remains the hardening path** if the transfer basis is ever contested, and this decision
  is the reason to keep the byte path free of anything that would make relocating it hard.

## The ordering this does not change

The blockers stay in the order already recorded: **(1)** the retention-covered store replaces
`InMemoryDocumentStore`, **(2)** this decision, **(3)** L2's router. The store is first because the
outcome it persists — extracted name and passport number — IS the PII worth protecting here. The
image was never the retention problem; the extracted fields are.

## The one gesture that is not a session's

Fly joining the tailnet and `OLLAMA_URL` being set to the Mini's tailnet address are `fly` CLI
actions, and `fly secrets set` / `fly deploy` are permission-denied in the session that wrote this.
That is a permission boundary, not a decision — the decision is above. The command belongs in
`WHEN-THE-PAYMENT-KEYS-ARRIVE.md` alongside the other arming steps when step (3) is built, and must
never be run before the transfer basis in "What this decision does NOT license" is satisfied.
