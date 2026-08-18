---
title: "ADR — OpenAI WhatsApp provider groundwork: OFFLINE and unwired (NO-WIRING)"
date: 2026-08-15
author: Sonnet 5 implementer session, worktree `bot-openai-adapter`, rework after a first
  builder session shipped a VETOED design (an unwired "shadow" branch presented as live state
  in `.agents/skills/bot/SKILL.md`, plus config/gateway wiring that never actually dispatched
  anything real). This PR is a full rebuild on top of that revert.
status: "NO-WIRING. The selected provider is the standalone CodexExecClient authenticated by
  the existing ChatGPT subscription; the Responses API-key client remains dormant. The only
  selected-provider consumer in this PR is the human-run offline blind-benchmark facade.
  Nothing in the live WhatsApp runtime imports, calls, flags-gates, deploys, or cuts over to
  either client."
adversarial_review: pending-kimi-k3
sources:
  - .agents/skills/bot/SKILL.md (WA-bot corner, live wiring GROUND)
  - apps/backend-rag/backend/services/rag/agentic/llm_gateway.py (confirmed UNCHANGED —
    identical to origin/main, see §6)
  - apps/backend-rag/backend/app/core/config.py (confirmed UNCHANGED — identical to
    origin/main, see §6)
  - Council verdict (verbatim below), delivered with the original mandate
  - Team-lead binding correction, mid-rework, 2026-08-15 (verbatim in §5)
client_case: null
---

# ADR — OpenAI WhatsApp provider groundwork: offline and unwired

## 1. Context

Zantara's WhatsApp bot (Meta channel) runs entirely on Gemini today:
`POST /api/agentic-rag/query` → the agentic-RAG orchestrator →
`LLMGateway.send_message()` → `GenAIClient` (Gemini). The mandate was to
build the groundwork for evaluating OpenAI's **Responses API** as a
future second provider — never as a live wiring in this PR.

**A prior builder session on this branch shipped a design the lead
orchestrator VETOED.** That design added a `_shadow_provider.py` module,
two new `Settings` fields (`agentic_rag_provider`, `openai_shadow_enabled`)
wired into `apps/backend-rag/backend/app/core/config.py`, a comment-stub in
`llm_gateway.py` implying a dispatch point had been considered and
half-built there, and — worst — a `.agents/skills/bot/SKILL.md` §1 LIVE
STATE entry that read as if a real (if flag-gated) capability existed,
backed by "54 new tests, all green." The tests were real; the framing was
not. None of it was reachable from any live path, and presenting an
unreachable branch as LIVE STATE in the corner every future session reads
first is exactly the cicatrix family #2 pattern ("esiste≠armato" —
existence mistaken for arming) this repo has been bitten by repeatedly.

**This PR is a full rework**, not a patch: every config/gateway change and
the `_shadow_provider.py` module were reverted byte-for-byte to
`origin/main` (verified — §6), the SKILL.md entry was reverted, and the
one component worth keeping — the standalone HTTP client — was rebuilt
against a corrected, binding spec.

## 2. Council verdict (implemented verbatim, non-negotiable)

- **NO-GO** on using the ChatGPT Pro / Codex OAuth subscription as a
  WhatsApp runtime credential. That subscription is a human interactive
  seat, not a service credential; routing production traffic through it
  conflates identity and blast radius in a way the council rejected
  outright.
- **CONDITIONAL-GO** on the OpenAI **API**, conditioned on:
  - a least-privilege **project service account** key, held server-side,
  - the **Responses API**, never Chat Completions,
  - the human ChatGPT Pro seat kept **identity/billing-separated** from
    the runtime credential,
  - no secrets installed, no traffic armed, in this phase.

## 3. What this PR actually ships

One file with zero live callers:

- **`apps/backend-rag/backend/llm/openai_responses_client.py`** —
  `OpenAIResponsesClient`, a standalone async HTTP wrapper over
  `POST https://api.openai.com/v1/responses`. Accepts
  `(input_text, system_prompt, model, max_output_tokens, tools)`, returns
  a provider-neutral `LLMResult`. It is a peer of `GenAIClient` /
  `OpenRouterClient` in shape (persistent `httpx.AsyncClient`, Golden Rule
  #10) but is not registered anywhere any router, service, or gateway can
  reach it. `grep -rln "openai_responses_client" apps/backend-rag/backend`
  returns exactly one hit — its own test file
  (`apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`) —
  because a search scoped to that directory cannot see
  `scripts/bot/wa_blind_bench.py`, which lives outside it; the repo-root
  search in the frontmatter `status:` field above is the one that actually
  confirms the module's only caller (corrected 2026-08-15 — an earlier
  draft of this line claimed this scoped command's hits included "the
  module itself", which it does not: a file does not grep-match its own
  filename unless its content happens to contain that string, and this
  one's does not).

Plus its own offline test/tooling surface:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py` —
  HTTP-boundary tests (fakes at the `httpx.MockTransport` layer, never a
  mock of the client's own methods — cicatrix W114). Run
  `pytest backend/tests/llm/test_openai_responses_client.py -v` for the
  current count and names rather than trusting a number written here —
  see the cicatrix #9 lesson on stale counts embedded in prose.
- `scripts/bot/build_deid_corpus.py` + its test — a local-only WA-export
  de-identifier (unrelated to and never called by the runtime).
- `scripts/bot/wa_blind_bench.py` + its test — a human-run blind
  benchmark harness against the client above.

**`.agents/skills/bot/SKILL.md` carries ZERO net change from
`origin/main` in this PR** — no LIVE STATE entry, no mention of this
adapter at all. An earlier pass in this rework added one (framed as "not
wired, offline only") and the team-lead flagged even that hedged framing
as a regression of the exact disease this PR exists to fix: an unwired,
gated component is not the /bot corner's "live state" of anything. That
entry was reverted; the corner will be updated only in the future PR that
actually wires something real (§6).

**Nothing else changed.** `apps/backend-rag/backend/app/core/config.py`
and `apps/backend-rag/backend/services/rag/agentic/llm_gateway.py` are
byte-identical to `origin/main` — no new `Settings` field, no env var, no
comment referencing this adapter, no dispatch point, half-built or
otherwise. There is no flag to flip, because there is no branch for a flag
to gate.

## 4. Design decisions in the client (binding correction applied)

The team-lead issued a mid-rework correction on the exact shape of the
fail-closed contract; every point below is that correction, implemented,
not a restatement of the first (vetoed) draft's design:

1. **Credential.** The client reads exactly one env var,
   `OPENAI_WA_PROVIDER_API_KEY`. It is never `OPENAI_API_KEY` — that name
   is already a live Fly secret backing `embedding_provider="openai"`
   (`text-embedding-3-small`, Golden Rule §9, FROZEN) and reusing it would
   collapse two different trust boundaries and billing lines onto one
   credential. `available` re-reads the environment on every access, never
   caches a value from `__init__` — `test_available_is_a_live_read_not_cached`
   and `test_dedicated_env_var_not_embeddings_key` pin both properties.
   **No such env var is set anywhere today** — `available` is `False` in
   every environment that exists. **What this PR actually implements is
   the static-key path only** (P2 correction, 2026-08-15): the client has
   exactly one authentication mechanism, `Authorization: Bearer <static
   key from OPENAI_WA_PROVIDER_API_KEY>` (`_headers()`). §2's council
   verdict lists "held server-side (or WIF)" as a CONDITION on the
   project-service-account key, not as two implemented alternatives —
   Workload Identity Federation is a possible FUTURE credential-delivery
   mechanism for that same key, named as an option for whoever provisions
   it, and nothing in this client, this PR, or this ADR builds, wires, or
   depends on it. The module docstring's "(or WIF — see the ADR)" pointer
   means exactly this paragraph: WIF is not implemented here.
2. **Fail-closed on response shape, not only on transport — and on more
   shapes than the first pass caught (second binding correction,
   2026-08-15).** HTTP 200 is necessary but not sufficient. A response
   body that isn't valid JSON at all raises `OpenAIResponseShapeError`
   (`response.json()`'s `JSONDecodeError` is caught explicitly, never left
   to propagate uncaught). Once parsed, the body must be a JSON object;
   `_parse_responses_payload` then requires `data["status"] == "completed"`
   — `"failed"`, `"incomplete"`, `"cancelled"`, or any other value raises.
   A present `incomplete_details` raises the same way, even if `status`
   somehow also read `"completed"`. `output` must be present, a list, and
   non-empty; each item must be a JSON object with a `type` in a small
   known set (`message`/`function_call`/`refusal`/`reasoning` — corrected
   2026-08-15, R13-5, Kimi K3 round-13 review: `reasoning` was missing
   from this list, stale since the P0 fix documented in §10/A1 of this
   same ADR added it to `_KNOWN_OUTPUT_ITEM_TYPES`; this is a normative
   section describing live behavior, not a round log, so it is corrected
   in place rather than appended-to per the round-log convention); a
   message item's
   `content` must itself be a list of JSON objects whose `type` is
   `output_text`/`refusal`. Any deviation — missing, wrong type, or an
   unrecognised value — raises rather than being silently skipped or
   coerced, because a silently-dropped item is exactly how a real answer
   becomes a truncated one with nothing to say so. **A `"completed"`
   response that ends up with no text, no refusal, and no tool call is
   itself rejected** — an empty "success" is a shape defect, not a quiet
   no-op. Refusal is represented explicitly as
   `LLMResult(refusal=True, refusal_reason=...)`, never folded into
   `.text`.
3. **No remote value — status, reason, item type, part type, or response
   body — in any exception message or log line, ever (tightened by the
   second binding correction).** `OpenAIAPIError` carries only the HTTP
   status code and a category derived purely from the numeric code —
   never `response.text`. `OpenAIResponseShapeError` messages are built
   exclusively from `_local_category()`, a function that compares a
   remote-controlled value against a small fixed set of local literals
   and returns ONLY one of that set's own members or the literal
   `"unknown"` — never the remote object itself, regardless of whether it
   matched. The Responses API can echo request content back into an error
   payload on some 4xx shapes (e.g. malformed `input`), and that `input`
   can itself carry client-derived text; the same risk applies in
   principle to any field in a 200 body, which is why the shape-error path
   gets the identical treatment rather than being assumed safe because it
   isn't `OpenAIAPIError`. Network-error logging and the final
   `OpenAINetworkError` message use `type(exc).__name__` only, never
   `str(exc)`. `test_api_error_never_carries_remote_body` and
   `test_error_messages_never_contain_the_remote_value` plant marker
   strings and assert they never reach an exception's message.
4. **Tool policy: positive allowlist, fail-closed on the WHOLE request,
   fail-closed on unsolicited tool calls too (tightened by the second
   binding correction).** `ALLOWED_TOOL_NAMES` is an explicit, empty
   `frozenset` in this phase — nothing has been reviewed/censito for this
   offline adapter. `generate(tools=...)` validates every requested name
   against it BEFORE any network call; if even one name is unknown — a
   mixed list of some allowed and some unknown names included — the
   ENTIRE request is refused with `OpenAIToolNotAllowedError`. The first
   draft of this check partially filtered a mixed list (dropping the
   unknown names, forwarding the rest), which the correction rejected: a
   caller asking for tools and silently getting a subset reads as success,
   not as the refusal it should be. Independently, the parser fails closed
   in the other direction too: a `function_call` item the server returns
   for a name outside what was actually sent in `requested_tool_names` is
   rejected as unsolicited — with the allowlist empty (today, always),
   ANY function_call from the server is rejected, because nothing was ever
   offered for it to call.
5. **Statelessness.** Every request sends `"store": false` and there is
   no `previous_response_id` parameter anywhere in this client —
   server-side conversation threading is out of scope entirely, not
   partially built.
6. **`store: false`, described honestly, not oversold.** `store: false`
   means OpenAI does not persist this call as retrievable application
   state (no conversation history, no `previous_response_id` continuity).
   It does **not** mean zero retention: per OpenAI's platform data usage
   policy, API content is retained for up to **30 days** for abuse and
   safety monitoring even under `store: false`, unless a Zero Data
   Retention agreement is separately negotiated — this ADR makes no claim
   that one exists. Anyone reasoning about PII exposure from this adapter
   must reason about that 30-day abuse-log window, not about "nothing is
   stored".
7. **Retries.** Max 2, exponential backoff, only on transient failures
   (429, 5xx, network-level timeout/connect). 4xx is never retried.

## 5. Team-lead's binding corrections (verbatim, applied above)

Two corrections landed mid-rework, both incorporated into §3–§4 above, not
left as a to-do:

**First** — on credential naming, the fail-closed response contract, no
remote body, tool allowlist, ADR honesty on rollback, and corpus honesty:

> CORREZIONE VINCOLANTE /BOT prima di modificare: nel tuo mandato, il
> punto 4a contiene un errore. La chiave DEVE essere esclusivamente
> OPENAI_WA_PROVIDER_API_KEY, MAI OPENAI_API_KEY (questa e gia usata dagli
> embeddings e non va riutilizzata). Fail-closed Responses: response.status
> deve essere completed; failed/incomplete/cancelled e incomplete_details
> (max_output_tokens/content_filter/unknown) sono errore tipizzato; output
> item/content type sconosciuti sono errore; refusal va rappresentato
> esplicitamente come refusal, mai testo di successo. Nessun body remoto
> in eccezioni/log. Tool policy: allowlist positiva esplicita; se non puoi
> provare i nomi censiti, rifiuta tutti i tools in questa lane offline. In
> ADR niente promessa rollback config-only: non c'e config/wiring; rollback
> = rimozione componente offline. Corpus role/multi-turn mancante => V5
> INCOMPLETE esplicito.

**Second**, issued after the first pass at implementing the above,
tightening exactly the gaps that pass had left — a mixed allowlist list
that silently filtered instead of refusing whole, remote values still
reaching some error messages, JSON-invalid not yet a typed error, an
unsolicited `function_call` not yet rejected, and no validation that
`output`/items were actually well-formed:

> PRIORITA BOT REVIEW VINCOLANTE: prima di congelare il diff correggi
> tutti questi punti. Allowlist fail-closed: rifiuta intera richiesta se
> QUALSIASI tool o schema e sconosciuto, inclusa lista mista; correggi il
> test che oggi accetta drop silenzioso. Nessun valore remoto status,
> reason, item_type, part_type negli errori o log: solo categorie locali
> note o unknown. JSON invalido deve diventare
> OpenAIResponseShapeError. Con allowlist vuota, function_call inattesa
> dal server deve fallire chiuso. Valida output list e item dict;
> completed vuoto o invalido fallisce chiuso. Nel bench usa SHA-256
> stabile al posto di hash Python e testa cross-process; logga solo tipo
> o categoria di eccezione, mai la stringa. Usa solo
> OPENAI_WA_PROVIDER_API_KEY. Pulisci __pycache__. Nessun wiring, config,
> hot path, push o PR prima del riesame finale Kimi e Google.

Every point in both corrections is implemented in §4 above (or, for the
bench-specific SHA-256/logging points, in `scripts/bot/wa_blind_bench.py`
directly — see `_stable_int_hash` and the fixture-failure log line) and
verified by a named test (`test_mixed_allowed_and_unknown_tools_rejects_
entire_request`, `test_error_messages_never_contain_the_remote_value`,
`test_invalid_json_body_raises_response_shape_error`,
`test_unexpected_function_call_fails_closed_by_default`,
`test_output_empty_list_raises` /
`test_completed_with_message_but_no_text_no_refusal_raises`,
`TestStableHash.test_stable_hash_matches_across_a_fresh_subprocess`). §6
(scope confirmation — no rollback section, no SKILL.md change) and §7
(corpus V5 INCOMPLETE) apply the first correction's last two points. No
wiring, config, or hot-path change exists in this PR (§3, §6), and
nothing has been pushed or opened as a PR — both corrections'
final line stands: Kimi K3 and Gemini review come before any of that.

## 6. Scope confirmation, and why there is no "rollback" section here

**This ADR deliberately does not describe a rollback mechanism.** An
earlier draft claimed "rollback is config-only" — a claim later corrected
to "rollback is component removal" in a second draft. Both were struck by
the team-lead's binding correction: **in a NO-WIRING PR there is no
config to flip and no dispatch point to disarm, so any "here is how you
roll this back" narrative describes a mechanism that does not exist** —
the same class of defect (claiming a capability shape for something that
is actually inert) as the vetoed SKILL.md entry this rework replaced. The
correct treatment is to say nothing about rollback here at all; a
rollback story belongs in the ADR of the future PR that actually wires
something, when there will be something concrete to roll back.

What this PR's scope actually is, confirmed by measurement, not assumed:
`git diff origin/main -- apps/backend-rag/backend/app/core/config.py
apps/backend-rag/backend/services/rag/agentic/llm_gateway.py
.agents/skills/bot/SKILL.md README.md` is empty — those four files carry
zero net change from `origin/main`. **This includes
`.agents/skills/bot/SKILL.md`**: an earlier pass in this same rework
added an entry there describing this offline client as the /bot corner's
LIVE STATE, and the team-lead flagged that as a regression of the exact
disease this rework exists to cure — an unwired, gated component is not
"live state" of anything, however carefully hedged the wording. That
entry was reverted; the file carries zero net diff from `origin/main` in
this PR, and the corner will only be updated in the future PR that
actually wires something real.

**R8-7 CORRECTION, 2026-08-15 (Kimi K3 round-8 review): the paragraph
above originally also listed `docs/AI_ONBOARDING.md` among the five
empty-diff files — false, measured.** `git diff origin/main --
docs/AI_ONBOARDING.md` is NOT empty: the `<!-- DOCSYNC:QUICK_NUMBERS_START
-->` block's test count moved `1359 tests` → `1360 tests`, a genuine,
correctly-scoped `+1` — this PR adds exactly one new test FILE
(`apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`,
confirmed absent at the immutable base `6a8ab5180`), and `docs_sync.py`'s
own counter is file-granular (see §13's F8 refutation below). Per CLAUDE.md
§9's same-commit discipline for DOCSYNC regeneration, that bump landed
atomically in the same commit that added the file, not as a separate
follow-up — it is real, intentional scope, correctly attributed here now
that it has been re-measured rather than assumed empty alongside its four
genuinely-empty siblings.

## 7. Historical corpus gap: V5 INCOMPLETE (superseded by §30.10 R28)

This section records the 2026-08-15 state and is intentionally not rewritten
as if role awareness existed then. R28 closes both tooling gaps in the default
builder mode; the current contract and residual limits are in §30.10.

`scripts/bot/build_deid_corpus.py` and `scripts/bot/wa_blind_bench.py` are
built and unit-tested against **synthetic fixtures only** — neither has
ever run against a real Zantara WA export in any session. Per the binding
correction, the gaps below are declared here rather than silently carried:

- **No role awareness.** The corpus builder buckets fixtures by guessed
  language only (`en`/`it`/`id`/`other`). It does not distinguish a
  client-role message from a Bali Zero team/staff message — a real WA
  export mixes both, and the two need different treatment (client
  messages are the actual PII-sensitive surface; staff messages have
  different content shape and different privacy stakes).
- **No multi-turn structure.** Every fixture is one isolated message; the
  live bot ships up to 12 prior turns of history to the model
  (`wa_inbox_bot._HISTORY_TURNS`), and single-turn benchmarking cannot
  measure anything about how a candidate model behaves with that context
  loaded, including the false-continuity and context-contamination
  failure modes the `/bot` corner has repeatedly measured on the current
  (Gemini) provider.
- **Consequence:** any blind-bench run produced by this tooling as it
  stands today benchmarks single-turn, role-blind responses only. This is
  **V5 INCOMPLETE** — it is not a claim that OpenAI-vs-Gemini quality on
  the real, multi-turn, role-aware WA task has been measured, and no
  future reader should treat a `wa_blind_bench.py` transcript as settling
  that question until role-awareness and multi-turn fixtures are added.
  Tracked here as an open gap, not silently deferred by omission.

## 8. Historical arming requirements (subscription ruling supersedes point 1)

This list records the pre-ruling Responses/API-key path. §30.1 supersedes
point 1 with the owner-selected ChatGPT-subscription path; the remaining
privacy, independent-scoring, runtime-host, review, and no-wiring gates remain.

1. Zero's explicit business/cost authorization to provision
   `OPENAI_WA_PROVIDER_API_KEY` as a least-privilege project
   service-account key (`CLAUDE.md` §5 / `~/.claude/CLAUDE.md` §Cost
   constraint) — nothing is provisioned in this PR.
2. A real shadow-dispatch design with one dispatch per user-facing turn
   and genuine context parity (history + tool schemas), reviewed and
   merged as its own PR — not the reverted `send_message()`-level stub.
3. An independent human privacy/legal review before any real WA export is
   fed to `build_deid_corpus.py` beyond synthetic-fixture testing; role
   and multi-turn awareness added first (§7).
4. A real `wa_blind_bench.py` run, scored by a non-OpenAI seat (Kimi K3 or
   Gemini) reading only the blind transcript, never the label key.
5. A real Kimi K3 adversarial security review of the client and any
   future wiring — `adversarial_review: pending-kimi-k3` above stays
   pending until that runs; this field is not hand-edited to a passing
   value.
6. Gemini constructive review and the Fable final on-disk gate, per the
   repo's standard ship-lifecycle.

None of the above is started in this PR.

## 9. Adversarial review notes (partial — review still in progress)

`adversarial_review: pending-kimi-k3` in the frontmatter stays as written
— the Kimi K3 review of this diff has not been confirmed complete from
this session's side, and this field is never hand-edited to a passing
value ahead of that. One finding has surfaced and been dispositioned so
far, and per team-lead instruction it is recorded here rather than
silently dropped — a refuted finding that stays visible is worth more
than one that vanishes (cicatrix W65: "even the refuter hallucinates" —
the record protects the next reviewer from re-raising the same
already-checked question, or from wrongly assuming nobody checked it):

- **Finding R3**: `gpt-5.6-sol` / `gpt-5.6-terra` / `gpt-5.6-luna`
  (`MODEL_SOL`/`MODEL_TERRA`/`MODEL_LUNA` in
  `openai_responses_client.py`) are internal codenames, not real OpenAI
  API model IDs.
  **Disposition: REVIEWER ERROR — refuted by primary source (OpenAI
  model docs, https://developers.openai.com/api/docs/models and the
  per-model pages, verified 2026-08-15).** All three are genuine OpenAI
  API model IDs and all three support `v1/responses`. **Not applied**:
  `DEFAULT_MODEL`/`MODEL_SOL`/`MODEL_TERRA`/`MODEL_LUNA` are unchanged
  from this ADR's earlier draft; nothing in `wa_blind_bench.py`'s
  candidate list was reverted, because nothing was ever changed in
  response to R3 in the first place — this session never received R3
  directly and made no edit against it. Documented here purely so the
  finding-and-refutation pair has a durable record.

Further findings, if and when relayed with enough detail to act on, will
be appended to this section rather than replacing it.

## 10. Second-round cross-family audit (Gemini + Kimi K3 + Codex, 2026-08-15)

A second review pass on this diff surfaced further findings across three
independent seats, all confirmed on disk before being applied (per team-lead
instruction: a claim that does not reproduce gets a reviewer-error
disposition here, never a fix applied to nothing). Every fix below is a
same-freeze addition to §4's design decisions, not a separate future PR.

**G1 (Gemini) — Scan A missed separator-formatted digit runs.**
`build_deid_corpus.py`'s `_RESIDUAL_LONG_DIGIT_RUN_RE` matched only
CONTIGUOUS digits; a phone or NIK typed with everyday WA-style separators
(`0812 3456 7890`, `3171 2345 6789 0123`) has no 8-digit contiguous run at
all, and a bare NIK with no ID-keyword nearby escaped Scan B's
`_ID_DOC_NEAR_DIGITS_RE` too. **Confirmed and fixed**: new
`_has_spaced_digit_pii()` matches `\d[\d\s.\-]{6,}\d` spans (`/` deliberately
excluded — WA timestamps and Indonesian regulation citations both use it),
requires ≥8 actual digit characters, and excludes ISO-date and
thousands-grouped-amount shapes (`_is_date_or_amount_shape`) so a date or a
currency figure isn't eaten as a phone number. Both positive (spaced
phone/NIK dropped) and negative (date, amount, larger amount, short
run, slash-separated citation all survive) cases are pinned in
`TestG1SpacedDigitRuns`.

**G2 (Gemini, deduplicated with Kimi's MEDIUM) — Scan B was case-sensitive
against Title-Case marker literals.** Real WhatsApp text is overwhelmingly
lowercase ("ibu siti", "jl. sunset road"); `_HONORIFIC_NAME_RE` and
`_ADDRESS_MARKER_RE` matched almost nothing on real export text.
**Confirmed and fixed**: both patterns now carry `re.IGNORECASE`, verified
empirically both ways before applying — guilt (lowercase real-style input
now matches both) and innocence (this file's own three clean-message
fixtures still match neither pattern under case-insensitivity, because both
patterns anchor on a small fixed marker-word alternation, not a generic
shape). **A later cross-check message additionally named
`_TITLECASE_BIGRAM_RE` as "still case-sensitive"** — investigated and
**NOT applied**: `_TITLECASE_BIGRAM_RE`'s entire selectivity comes from
requiring an actual capital letter; adding `re.IGNORECASE` degrades it to
"any two adjacent 3+-letter words", which — verified with a standalone
script before deciding — flags ALL THREE of this file's own clean-message
innocence fixtures ("quanto costa", "Berapa biaya", "How long" all match
case-insensitively). That is not a wider PII net, it is the heuristic
losing its only signal; applying it would have silently broken
`TestInnocenceCleanMessagesSurvive`. Disposition: confirmed observation,
proposed remedy rejected as actively harmful — documented in-code at
`_TITLECASE_BIGRAM_RE`'s definition and pinned by
`test_titlecase_bigram_deliberately_not_made_case_insensitive`, deferred to
a future pass that needs something smarter than a blanket flag flip.

**G3 (Gemini) — WA line-parser prefix `(?:‎)?` claimed "no-op".**
**Disposition: REVIEWER ERROR**, confirmed by hexdump before this session
touched anything: the group is not empty — it already contains U+200E
(LEFT-TO-RIGHT MARK), the invisible marker WhatsApp prepends to exported
lines. Gemini lost the invisible character reading the prompt; the pattern
was already intentional. Not extended to U+200F/U+FEFF either — no evidence
surfaced that either appears in a real export this session has access to;
extending on no evidence would be exactly the same class of unverified
claim this ADR's whole audit trail exists to avoid.

**K1 (Kimi K3) — narrow httpx exception catch.** `generate()` caught only
`(httpx.TimeoutException, httpx.TransportError)`. **Confirmed**: the
installed `httpx==0.28.1`'s actual hierarchy (checked directly, not
assumed) has `httpx.DecodingError` and `httpx.TooManyRedirects` as
`RequestError` subclasses that are NOT `TransportError` subclasses — both
would have risen raw, uncaught, unwrapped, past this client. **Fixed**:
widened to `except httpx.RequestError`, the correct common base (both
previously-caught types are already `RequestError` subclasses, so this is
a pure widening, not a behavior change for the cases already handled).
Retry semantics unchanged — this file never distinguished retryability
*within* transport-level failures, only between transport failures (always
retried) and API status codes (retryable only if listed). Pinned by
`test_decoding_error_wrapped_as_network_error` and
`test_too_many_redirects_wrapped_as_network_error`.

**K2 (Kimi K3) — model allowlist was a comment, not code.** `generate()`'s
`model` argument and `OPENAI_RESPONSES_MODEL` env var accepted ANY string;
"approved candidates" and "sol is ceiling-only" were prose, never enforced.
**Confirmed and fixed**: new `_RUNTIME_MODEL_CANDIDATES = frozenset({
MODEL_SOL, MODEL_TERRA, MODEL_LUNA})` and a check in `generate()` that
raises the new `OpenAIModelNotAllowedError` for anything outside it, before
the network call, whether the model came from an explicit `model=` kwarg or
from the env var. `MODEL_SOL` stays a MEMBER of the allowlist — the policy
is "only these three reviewed candidates", not "sol may never be
requested"; `wa_blind_bench.py`'s explicit ceiling-reference call to `sol`
keeps working (pinned by `test_sol_accepted_when_explicitly_requested`).
**Declared scope**: this allowlist enforces WHICH THREE slugs may ever be
requested — it does not itself decide which of the three a given future
runtime caller should pick; there is no live caller of `generate()` in this
PR to make that decision for.

**K1 SECOND (Kimi K3, round 2) — `httpx.RequestError` alone still wasn't the
complete pre-response failure surface.** `httpx.StreamError` (base of
`RequestNotRead`/`ResponseNotRead`/`StreamClosed`/`StreamConsumed`) inherits
from `RuntimeError` directly, NOT from `RequestError` — verified directly
against the installed `httpx==0.28.1` (`isinstance(httpx.RequestNotRead(),
httpx.RequestError)` is `False`), so `except httpx.RequestError` alone would
have let `RequestNotRead` rise raw out of `client.post(...)`. Separately,
`response.json()` sat OUTSIDE the post-site try/except and only caught
`ValueError` (invalid JSON syntax) — `httpx.DecodingError`, a `RequestError`
subclass the body-decode step can itself raise, is not a `ValueError` and
would have risen raw from that second call site too. **Confirmed and
fixed**: the post-site except clause widened to
`except (httpx.RequestError, httpx.StreamError)`; the `.json()` site widened
to `except (ValueError, httpx.DecodingError)`. Both destinations unchanged
(`OpenAINetworkError` / `OpenAIResponseShapeError` respectively, both still
`from None` per K4's discipline). Pinned by
`test_request_not_read_wrapped_as_network_error` (guilt at the post site)
and `test_response_json_decoding_error_wrapped_as_response_shape_error`
(guilt at the `.json()` site, isolated via a direct `httpx.Response.json`
patch since a `MockTransport` fake does not reproduce a real
encoding/content-encoding failure) — existing `TimeoutException`/
`TransportError`/first-round `DecodingError`/`TooManyRedirects` tests stay
green as innocence.

**K1 live-gate addendum (2026-08-15) — `from None` doesn't clear
`__context__`.** The live gate correctly pointed out that a bare
`pytest.raises(TYPE)` doesn't prove K4's no-leak discipline holds for the
two new except branches above, and specifically that `raise X(...) from
None` only sets `__cause__ = None` and `__suppress_context__ = True` — it
does NOT clear the `__context__` Python's interpreter populates
automatically whenever a new exception is raised while another is being
handled. Verified empirically (not assumed): raising the local exception
*inside* the except block left `err.__context__ is exc` still `True` even
with `from None`; only the STANDARD traceback formatter's printed output
respects `__suppress_context__`, an attribute-walking consumer (a
debugger, some error-reporting SDK integrations) would still reach `exc`
— and therefore the outgoing request's headers / the raw response body —
via `__context__`. **Confirmed and fixed properly, not just documented**:
both call sites now build the local exception object inside the except
block but defer the actual `raise` statement to immediately after that
block exits (`pending_network_error` / `pending_shape_error`, checked
right after the `except` clause) — verified empirically that raising once
no exception is "currently being handled" leaves BOTH `__cause__` and
`__context__` genuinely `None`, closing the gap outright instead of only
suppressing its display. Pinned by strengthened assertions in all four
K1/K4 tests (`test_request_not_read_wrapped_as_network_error`,
`test_response_json_decoding_error_wrapped_as_response_shape_error`,
`test_network_error_cause_is_none_not_original_exception`,
`test_json_decode_error_cause_is_none_not_original_exception`), each now
asserting `__context__ is None` in addition to `__cause__ is None` and
marker-absent-from-message.

**K2 SECOND (Kimi K3, round 2) — the model allowlist didn't distinguish an
explicit request from an inherited one.** The first K2 fix treated
`_RUNTIME_MODEL_CANDIDATES` as one flat set regardless of how `model_name`
was resolved, so "sol is ceiling-only, never a runtime/shadow default" (the
module comment on `MODEL_SOL`) was enforced only against slugs OUTSIDE the
three-candidate set — a `MODEL_SOL` reaching `generate()` via
`OPENAI_RESPONSES_MODEL` (a persistent env var, not a per-call decision)
would have been silently ACCEPTED, since `sol` is a legitimate member of
that flat set. **Confirmed and fixed**: a second, narrower frozenset
`_ENV_OR_DEFAULT_MODEL_CANDIDATES = frozenset({MODEL_TERRA, MODEL_LUNA})`
now gates the env/default resolution path specifically; `generate()` checks
`model is not None` to decide which allowlist applies — explicit
`generate(model=...)` may still request any of the three
(`wa_blind_bench.py`'s ceiling-reference call keeps working), while a model
resolved from `OPENAI_RESPONSES_MODEL` or `DEFAULT_MODEL` resolving to
`MODEL_SOL` is rejected with a distinct message
(`category=sol_requires_explicit_request`), before any network call.
`DEFAULT_MODEL` itself is `MODEL_TERRA` and always has been — the only real
path to sol-via-non-explicit-resolution is the env var. Pinned by
`test_sol_from_env_var_rejected_zero_network_calls` (guilt — env=sol raises
with zero HTTP traffic), `test_sol_accepted_when_explicitly_requested`
(pre-existing, now doubling as the explicit-path innocence case), and
`test_terra_from_env_var_accepted` (innocence — the env/default path is not
blanket-blocked, `terra`/`luna` still resolve and work via
`OPENAI_RESPONSES_MODEL`).

**K3 (Kimi K3) — Ollama subprocess got the FULL process environment.**
`_ollama_ner_pass` passed `dict(os.environ)` to the `ollama run` subprocess
— every secret this process's environment happened to be carrying, none of
which the subprocess needs. **Confirmed and fixed**: new
`_OLLAMA_SUBPROCESS_ENV_ALLOWLIST = frozenset({"PATH", "HOME", "USER",
"TMPDIR", "LANG", "LC_ALL"})`, an explicit allowlist (not a blocklist —
a blocklist only catches secrets someone thought to name), plus the
pre-existing forced `OLLAMA_HOST` loopback override, unchanged. Pinned by
`test_secret_env_var_not_forwarded_to_ollama_subprocess` (a planted
sentinel env var never reaches the subprocess env) and
`test_allowlisted_vars_still_forwarded` (innocence — `PATH` still gets
through, so the subprocess call itself doesn't silently break).

**K4 (Kimi K3) — exception `__cause__` carried secrets/body content.**
Two `raise X(...) from exc` sites: `OpenAINetworkError` from an
`httpx.RequestError` (whose `.request` attribute carries the actual
outgoing request, headers included — this client's own
`Authorization: Bearer <key>` among them), and `OpenAIResponseShapeError`
from a `json.JSONDecodeError` (whose `.doc` carries the FULL raw response
body that failed to parse). Both messages already followed the
no-remote-value discipline, but `__cause__` was an unguarded side door — a
future serializer/error-reporting integration that walks `__cause__` would
have reached the secret/body regardless of what the message said.
**Confirmed and fixed**: both re-raises changed to `from None`. Pinned by
`test_network_error_cause_is_none_not_original_exception` and
`test_json_decode_error_cause_is_none_not_original_exception`, each
planting a marker in the suppressed cause and asserting it is reachable
through neither `__cause__` nor the exception's own message.

**K5 (Kimi K3) — output directories had no explicit permission mode.**
Both `build_deid_corpus.py`'s and `wa_blind_bench.py`'s `output_dir.mkdir(
parents=True, exist_ok=True)` created the directory at the process umask's
permissions (typically 0o755) — the file-level 0600-from-creation
discipline (`_write_jsonl_private`/`_open_private`) had no directory-level
counterpart. **Confirmed and fixed**: new `_mkdir_private()` in each file
(duplicated rather than shared — each file already duplicates its own
private-file-write helper independently, same pattern), clearing the umask
around `Path.mkdir(mode=0o700)` and then unconditionally `os.chmod`-ing to
0700 afterward (so an already-existing looser directory is TIGHTENED, not
left alone under `exist_ok=True`). Only the leaf directory is guaranteed
0700; missing parent directories still get default `mkdir -p` permissions.
Pinned in both files' test suites, including an end-to-end check that
`build_corpus(execute=True)`'s real output directory lands at 0700.

**A1 (Codex, on this session's own P0 fix) — reasoning item was ignored
without being validated first.** The original P0 mandate said "validate
the minimal shape and then ignore it"; the first pass only ignored it,
with zero validation — any dict carrying `type: "reasoning"`, however
malformed otherwise (a `summary` that's a string instead of a list, an
`id` that's an int), passed through silently. **Confirmed and fixed**:
isinstance-only checks on `id` (str), `summary`/`content` (list),
`encrypted_content` (str) — every field OPTIONAL, but a PRESENT
wrong-typed field now raises `OpenAIResponseShapeError`
(`category=malformed_reasoning_item`). No field's VALUE is ever read into
a variable that could reach an error message or log line — this still
cannot leak chain-of-thought content, it only confirms the shape looks
genuine before moving on. Pinned by four guilt tests (bad `summary`,
`content`, `id`, `encrypted_content`) plus an innocence test (a reasoning
item with only `type` — every field legitimately absent — still parses).

**A2 (Codex, on this session's own P1 fix) — `_get_str_field` silently
defaulted missing fields to `""`.** A `function_call` missing `call_id` or
`arguments` entirely passed through as a valid-looking-but-empty string,
indistinguishable from a server that genuinely sent an empty string.
**Confirmed and fixed**: `_get_str_field` is now REQUIRED by default (a
`_REQUIRED_STR_FIELD` sentinel distinguishes "no default passed" from "the
caller explicitly wants some other default"); a missing key with no
explicit `default=` now raises. None of this module's three call sites
(`function_call.name`/`call_id`/`arguments`) pass an explicit default, so
all three are required. Pinned by `test_function_call_missing_call_id_raises`,
`test_function_call_missing_arguments_raises`,
`test_function_call_missing_name_raises`, plus direct unit tests on
`_get_str_field` itself for both the required-by-default and
explicit-default-opt-out paths.

**A3 (Codex, on this session's own P1 fix) — `_extract_refusal_reason`'s
`if value:` guard conflated absent with present-but-falsy.** A present
`{"refusal": 0}` or `{"refusal": {}}` was silently SKIPPED (treated as
"nothing sent here", falling through to the next candidate or the
`"refused"` fallback) rather than rejected as malformed — exactly the
"shape error masquerading as absence" class of bug this parser's whole
fail-closed discipline exists to prevent. **Confirmed and fixed**:
declared, precise rule — a key that is ABSENT, or explicitly `None`, or an
empty string, means "no reason given via this key" (try the next
candidate); any OTHER non-string present value raises, regardless of
Python truthiness (`0`, `False`, `[]`, `{}` all now raise). Pinned by nine
tests directly against `_extract_refusal_reason` (every absent/None/empty/
malformed/valid combination) plus two full-parse integration tests.

## 11. Third-round adversarial review on the frozen diff (Kimi K3, 2026-08-15)

A fresh cross-family adversarial review ran on the FROZEN `6a8ab5180..1be079571`
diff (agy GREEN — its findings dispositioned reviewer-error/by-design; Kimi K3
produced 1 MEDIUM + 4 LOW confirmed on disk before any fix was applied, per the
same discipline as every prior round). Every fix below lands in the same
commit boundaries as before (client+tests[+AI_ONBOARDING] / corpus+bench /
this ADR) on a NEW hash — the review that passed `1be079571` does not carry
forward to whatever hash supersedes it.

**MEDIUM — membership on a non-hashable remote value.** Three gates in
`_parse_responses_payload` — `status not in _ACCEPTED_STATUS`, `item_type not
in _KNOWN_OUTPUT_ITEM_TYPES`, `part_type not in _KNOWN_MESSAGE_CONTENT_TYPES`
— used Python's `in` operator against a `frozenset`, which requires the
left-hand value to be HASHABLE. A remote `status`/`type` field that is a list
or dict (not just "the wrong string") would have raised a raw, uncaught
`TypeError: unhashable type`, breaking the fail-closed-with-a-typed-error
contract this module holds everywhere else. **Confirmed and fixed** (class
audit, not a point fix — all three sites share the same shape):
`isinstance(x, str)` now guards each `in` check via `or` short-circuit, so a
non-hashable value never reaches the membership test; `_local_category` was
already isinstance-safe internally (loops with `==`, never `in` on a
frozenset), so only the three CALLER guards needed the fix. Pinned by
`test_status_not_hashable_raises_shape_error_not_typeerror`,
`test_output_item_type_not_hashable_raises_shape_error_not_typeerror`,
`test_message_content_part_type_not_hashable_raises_shape_error_not_typeerror`
— existing string-mismatch tests (e.g.
`test_error_messages_never_contain_the_remote_value`) stay green as
innocence, confirming the fix is additive, not a behavior change for the
already-handled case.

**LOW — `output_text.text` absent degraded to `""`.** `part.get("text", "")`
made a genuinely MISSING `text` key indistinguishable from a server that sent
`"text": ""` on purpose — inconsistent with this module's own A2 doctrine
(`_get_str_field`'s required-by-default rule) applied to every other string
field read from remote JSON. **Confirmed and fixed**: `"text" not in part`
now raises `OpenAIResponseShapeError`, same as a missing `function_call.name`
already did; a present-and-empty `"text": ""` still parses (it's a real,
if unusual, value). Pinned by `test_output_text_missing_text_field_raises`
(guilt) and `test_output_text_explicit_empty_string_still_parses`
(innocence).

**LOW — `usage` present but not a dict silently zeroed.** `data.get("usage")
or {}` collapsed EVERY falsy value (`0`, `""`, `[]`, `False`) — not just a
genuinely absent key — down to the same silent `{}` an absent/`None` usage
already gets, and a second `isinstance` check caught the remaining
non-dict-and-truthy cases (a string, a non-empty list) the same way. A
malformed `usage` was therefore indistinguishable from "no usage data given"
either way. **Confirmed and fixed**: absent/`None` still means "no usage
data" (0-default, unchanged); present-and-not-a-dict now raises
`OpenAIResponseShapeError` regardless of truthiness. Pinned by
`test_usage_present_but_not_a_dict_raises`,
`test_usage_present_but_falsy_non_dict_raises` (guilt, the falsy case
specifically — the old `or {}` masked exactly this), and
`test_usage_explicit_none_defaults_to_zero` (innocence).

**LOW — `incomplete_details` truthiness masked a malformed-but-falsy
value.** `if incomplete_details:` used Python truthiness — a
present-but-falsy value (`0`, `""`, `[]`, `False`) read as equivalent to
ABSENT and the entire "response marked incomplete" branch was silently
skipped, meaning a response OpenAI explicitly flagged as incomplete
(however oddly-shaped the flag) could have been accepted as a normal
completed answer. **Confirmed and fixed**: same A3 rule this module
already applies elsewhere — absent or explicit `None` means "nothing to
report" (skip, unchanged); ANY other present value, dict or not, truthy or
not, is processed (dict → extract `reason` as before) or rejected
(non-dict → `reason_category=malformed_incomplete_details`), never
silently waved through. Pinned by
`test_incomplete_details_falsy_non_dict_present_raises`,
`test_incomplete_details_empty_string_present_raises` (guilt) and
`test_incomplete_details_explicit_none_does_not_raise` (innocence) —
`test_incomplete_details_present_raises_even_if_status_completed`
(pre-existing, dict case) stays green.

**LOW — a non-dict `tools` entry raised a raw `AttributeError`.**
`_validate_tools_allowlisted`'s `t.get("name")` assumed every entry in the
caller-supplied `tools` list is itself a dict; a bare string or other
non-dict entry raised `AttributeError: 'str' object has no attribute
'get'` instead of a typed, pre-network refusal. **Confirmed and fixed**: a
new isinstance guard rejects any non-dict entry via `OpenAIToolNotAllowedError`
BEFORE the allowlist check — the same exception type as an unknown tool
name (declared criterion: both mean "this `tools=` call cannot be honored
at all", the caller-visible outcome is identical either way, so this reuses
the existing type rather than introducing a new exception class for a
distinction the caller doesn't observe). Pinned by
`test_tools_entry_not_a_dict_raises_typed_error_pre_network` and
`test_tools_entry_not_a_dict_among_valid_ones_still_refuses_whole_request`
(guilt — a malformed entry mixed with an allowlisted one still refuses the
WHOLE request, same all-or-nothing discipline as the existing mixed-names
test).

**Same-class residual (live-gate second pass, 2026-08-15) — a `tools`
entry's `name` value could itself be unhashable.** The non-dict-entry guard
above did not cover a dict entry whose `name` is a list/dict: `unknown =
sorted({... for t in tools if t.get("name") not in ALLOWED_TOOL_NAMES})`
performs `in` against a frozenset on the RAW `t.get("name")` value BEFORE
the `str()` wrapping that only applies to the emitted set element — the
exact same "unhashable value reaches `in` on a frozenset" class the MEDIUM
finding above was just fixed for, here on the caller side instead of the
remote-response side. **Confirmed and fixed**: the same loop that already
validates each entry is a dict now also validates `t.get("name")` is a
`str` (an absent `name` key is caught the same way, since `None` isn't a
`str` either — a tool entry without a name can never be validated against
the allowlist anyway), raising `OpenAIToolNotAllowedError` with
`category=malformed_tool_name` before the membership comprehension ever
runs; the comprehension itself now reads `t["name"]` (guaranteed present
and `str` by that point) instead of `t.get("name")`. **Symmetry check on
`generate()`'s second comprehension** (`requested_tool_names = frozenset(
str(t.get("name")) for t in tools) ...`): confirmed SAFE, not by
coincidence — `_validate_tools_allowlisted(tools)` runs unconditionally
before this line and raises on any problem, so this comprehension is only
ever reached once every entry is a dict with a `str` name; the `str()`
call there is a type-narrowing no-op at that point, not a safety
mechanism reached before the guard ran. Documented inline at that call
site rather than changed. Pinned by
`test_tools_entry_name_not_hashable_raises_typed_error_pre_network`
(guilt — `tools=[{"name": ["x"]}]`, zero HTTP calls) and
`test_tools_entry_unknown_string_name_behaviour_unchanged` (innocence —
a well-formed string name that's simply not allowlisted still raises the
ORIGINAL unknown-name refusal, not the new malformed-name one).

**Micro — the reasoning-item comment overclaimed "never read".** The module
docstring and the inline comment on the `reasoning` parsing branch both
said reasoning fields are "never read" — false: `reasoning_id =
item.get("id")` etc. DO read the value into a local variable, for an
isinstance type-check. What never happens is that value reaching an error
message, a log line, or `LLMResult` — the leak-prevention claim was always
true, but the comment describing HOW it's achieved was not. **Corrected**:
both comments now say the value is read locally for type-validation only,
never interpolated anywhere observable.

**Micro — a near-vacuous second assertion in
`test_reasoning_summary_text_never_leaks_into_result`.** The original
`assert (result.refusal_reason or "") == "" or marker not in
result.refusal_reason` is always `True` on its own payload (a text
response with no refusal item at all, so `refusal_reason` is always
`None`) — Python's `or` short-circuits on the always-true left side and
the right side (the actual marker check) never executes. The assertion
would have passed even if the marker somehow DID leak into a refusal
reason. **Rewritten**: the test now also builds a refusal-response variant
(genuinely non-`None` `refusal_reason`) with the same marker planted in a
leading reasoning item, and asserts marker-absence there as a standalone
statement — real signal, not the disarmed half of an `or`.

Suite counts after this round: **120 tests** in `backend/tests/llm/`
(105 → 118 → 120, +15 total: 3 hashability guilt tests, 2 output_text
tests, 3 usage tests, 3 incomplete_details tests, 2 tools-entry-not-a-dict
tests, plus 2 more from the live-gate second pass on the tools-`name`
residual — `test_tools_entry_name_not_hashable_raises_typed_error_pre_network`
and `test_tools_entry_unknown_string_name_behaviour_unchanged`), **56
tests** unchanged in `scripts/bot/` (this round touched only the client +
its test file). Both suites green, ruff clean on both, run with
`PYTHONDONTWRITEBYTECODE=1`.

## 12. Fourth-round consolidated fix list A-F, plus two orchestrator refinements (Kimi K3, 2026-08-15)

A single consolidated mandate (six points, A through F) thawed the frozen
`0a3c13796` diff after it failed the orchestrator gate, followed mid-round
by two orchestrator refinements to points A and D that superseded this
round's own first-pass fixes for those two points before recomposition.
Every fix below lands across the same three commit boundaries as every
prior round (client+tests[+`AI_ONBOARDING.md`] / corpus+bench / this ADR)
on a new hash on top of the still-immutable base `6a8ab5180`.

**A (MEDIUM) — `os.open(..., mode=0o600)` does not tighten a
pre-existing looser file, and the first-pass fix for this destroyed
content on a failed permission check.** `mode=` on `os.open` only applies
when `O_CREAT` actually CREATES the file — reopening an existing 0644
file for writing silently preserves its loose permissions. Both writer
functions (`_write_jsonl_private` in `build_deid_corpus.py`,
`_open_private` in `wa_blind_bench.py`) now call `os.fchmod(fd, 0o600)`
unconditionally right after `os.open`, closing the fd and propagating the
exception (fail-closed, never writing) if `fchmod` itself raises.
**Orchestrator refinement, applied before recomposition**: this session's
own first-pass fix opened with `O_TRUNC` up front, so a FAILED `fchmod`
still meant pre-existing file content had already been destroyed by the
truncating open before the permission check could even run — fail-closed
in name only. Corrected by opening WITHOUT `O_TRUNC` (`O_WRONLY |
O_CREAT` only), confirming `fchmod` succeeds FIRST, and only THEN
explicitly `os.ftruncate(fd, 0)` + `os.lseek(fd, 0, os.SEEK_SET)` before
writing new content. Pinned by six new tests across the two paired test
files (`TestWriteJsonlPrivateFchmod` in `test_build_deid_corpus.py`,
`TestOpenPrivateFchmod` in `test_wa_blind_bench.py`, three tests each):
guilt-tightening (`test_preexisting_loose_file_is_tightened_to_0600` —
pre-existing 0644 rewritten becomes 0600), fail-closed guilt with a
`fchmod`-raises monkeypatch plus an `os.close` spy
(`test_fchmod_failure_leaves_original_content_untouched_and_fd_closed` —
original content byte-identical, fd closed exactly once, `OSError`
propagates), and a happy-path shrink test
(`test_happy_path_replaces_longer_preexisting_content_with_no_residual_tail`
— shorter new content over a longer pre-existing file leaves no residual
tail bytes, proving `ftruncate` genuinely runs, not just that `fchmod`
did).

**B — the ADR declares corpus tooling "V5 INCOMPLETE" but the module
docstring never said so.** `build_deid_corpus.py`'s module docstring now
carries an explicit "V5 INCOMPLETE" marker, aligned with §7's two
declared gaps (no role awareness — client vs staff message distinction —
and no multi-turn structure — single-turn fixtures vs. the live bot's
12-turn history), with a pointer back to this ADR.

**C (MEDIUM, same class as the third-round MEDIUM in §11) — `model=`
membership check on a non-hashable value raised a raw `TypeError`.**
`model_name not in allowed_candidates` performs Python's `in` on the raw,
possibly-unhashable caller-supplied value — `generate(model=[])` (or any
list/dict) raised `TypeError: unhashable type` instead of this module's
typed `OpenAIModelNotAllowedError`, the same bug class as the §11 MEDIUM
finding (status/item_type/part_type) and the §11 tools-`name` residual,
now found a third time on the model-selection path. **Confirmed and
fixed**: an `isinstance(model_name, str)` guard runs BEFORE the
membership check, raising `OpenAIModelNotAllowedError` with
`category=malformed_model_type` that cites only `type(model_name).__name__`
— never the raw value, even though it is caller-supplied and could be
large or awkward. Pinned by three new tests in `TestModelAllowlist`:
`test_unhashable_model_value_rejected_before_network_call` (guilt —
`model=[]`, zero network calls, typed error),
`test_unhashable_model_value_never_echoes_raw_value` (guilt — a marker
planted inside the unhashable value never surfaces in the exception
message), and `test_unknown_string_model_still_gets_original_refusal_not_malformed_type`
(innocence — an unknown-but-string model name still gets the original
unknown-name refusal, not the new malformed-type category).

**D (LOW, superseding the LOW fix already logged in §10/§11's regex
comment) — date-shape exemption accepted calendar-impossible values.**
`_is_date_or_amount_shape` exempts date-SHAPED spans from the PII scan;
this round's first pass validated only that the captured month/day fell
in numeric range (1-12, 1-31), which still wrongly accepts values like
`"2026-02-30"` (February never has a 30th day) — a NIK/phone number
formatted with such separators would still slip the exemption on a shape
that only LOOKS like a date. **Orchestrator refinement, superseding the
first pass**: real calendar validation via `datetime.date(year, month,
day)` inside a `try`/`except ValueError` block — the standard,
already-correct way to ask "does the calendar contain this day" without
hand-rolling per-month day-counts and the leap-year rule.
`_ISO_DATE_SHAPE_RE` now captures the year too (previously only
month/day), since `datetime.date` needs all three fields. Documented
inline in `_is_date_or_amount_shape`'s docstring, including why a bare
range check was insufficient. Pinned by three new tests alongside the
pre-existing `test_is_date_or_amount_shape_direct`:
`test_out_of_range_month_shaped_number_not_exempted` (guilt —
`"6208-15-15"`, month=15, still caught), `test_calendar_impossible_day_not_exempted`
(guilt — `"2026-02-30"`, caught by the new calendar check specifically),
and `test_leap_year_valid_date_still_exempted` (innocence — `"2024-02-29"`,
a real leap-year date, still recognized and exempted).

**E (MEDIUM) — any HTTP status below 400 fell through to JSON parsing,
contradicting the module's own documented invariant.** `if
response.status_code >= 400:` let ANY status under 400 — a 1xx an
intermediary sent through, a non-200 2xx (`201`/`204`/...), or a 3xx
redirect httpx followed — reach `response.json()` parsing, contrary to
this module's docstring ("HTTP 200 is necessary but not sufficient").
**Confirmed and fixed**, per team-lead's explicit binding decision that
the Responses API only ever answers `200` on genuine success (a
documented, deliberate design choice, not an assumption): the gate is now
strictly `!= 200` rather than merely "not obviously an error". Any
non-200 that is retryable (per `_RETRYABLE_STATUS_CODES`, unchanged —
every code already in that set is `>= 400`, so retry behaviour for the
previously-handled cases is identical) is retried as before; anything
else raises `OpenAIAPIError(status_code)`. `OpenAIAPIError`'s category
classification gained a fifth branch, `unexpected_status`, for the
newly-reachable sub-400/non-200 case (neither `rate_limited` nor
`server_error` nor `client_error` applies) — more descriptive than a
generic `unknown` fallback, per team-lead's suggestion. Pinned by three
new tests in `TestErrorHandling`:
`test_http_100_continue_raises_api_error_never_parsed` and
`test_http_304_not_modified_raises_api_error_never_parsed` (guilt — both
responses carry a deliberately INVALID JSON body, so reaching
`OpenAIAPIError` rather than `OpenAIResponseShapeError` proves the parser
was never invoked, not merely that "something" was raised), and
`test_unexpected_status_category_for_sub_400_non_200` (pins the
`unexpected_status` category specifically, via a bare `204`).

**F(i) (MICRO) — `_get_str_field`'s docstring claimed an explicit
`default` is type-checked; the code did not check it.** The absent-key
branch (`if default is _REQUIRED_STR_FIELD: raise ... else: return
default`) returned `default` completely unchecked, contradicting the
docstring's claim. Per team-lead's explicit preference ("choose the path
that makes the text TRUE — preferred: a real check"), the CODE was fixed
to match the docstring, not the other way around: a real
`isinstance(default, str)` check now guards that branch, raising the same
`OpenAIResponseShapeError` category as the present-non-string-value path.
Pinned by `test_missing_key_with_non_string_default_raises` (guilt — a
non-string `default=123` on a missing key now raises); the pre-existing
`test_missing_key_with_explicit_default_returns_default` (a string
default) stands as innocence, unchanged.

**F(ii) (MICRO, documentation-only) — a test's own comment misrepresented
what `MockTransport` can and cannot reproduce.** The comment on
`test_response_json_decoding_error_wrapped_as_response_shape_error`
claimed a real encoding/content-encoding failure "is a property of the
transport layer that a `MockTransport` fake does not reproduce" —
team-lead flagged this as factually wrong, and it was verified empirically
before correcting (a standalone async script driving `httpx.MockTransport`
with a `content-encoding: gzip` header over non-gzip bytes does raise a
genuine `httpx.DecodingError`). The catch is that it always surfaces from
`client.post()` itself — httpx reads/decodes eagerly for a non-streaming
request, before `post()` even returns — never from `response.json()`.
The comment now says so accurately: the `.json()`-site catch is a
DEFENSIVE branch, likely unreachable via any real httpx failure mode in
this client's non-streaming flow, and the direct `httpx.Response.json`
monkeypatch used by the test is "the only way to reach this specific
line", not "MockTransport can't produce the real error". The catch itself
stays (defense in depth is cheap here); only the justification text
changed — the test's assertions are unchanged.

Suite counts after this round: **127 tests** in `backend/tests/llm/`
(120 → 127, +7: 3 for point C, 3 for point E, 1 for point F(i)), **65
tests** in `scripts/bot/` (56 → 65, +9: 3 for point A on the
`build_deid_corpus.py` side, 3 for point A on the `wa_blind_bench.py`
side, 3 for point D — `test_build_deid_corpus.py` carries 52 of the 65,
`test_wa_blind_bench.py` carries 13). Both suites green (`127 passed`,
`65 passed`), ruff clean on both fenced areas across two consecutive
runs, all runs with `PYTHONDONTWRITEBYTECODE=1`. Worktree swept of stray
`__pycache__` residue in the fenced paths before recomposition.
`docs/AI_ONBOARDING.md` carries no test-count references tied to these
components and needed no change this round.

**R8-7 reconciliation, 2026-08-15**: "needed no change this round" (round
4) stays true — but "carries no test-count references tied to these
components" overreaches, corrected in §6 above. `test_openai_responses_client.py`
already existed as a FILE by this point (its 120 pre-round-4 tests prove
it), so `docs/AI_ONBOARDING.md`'s aggregate `... tests` count already
carried the `+1` file-level reference this component's very existence
produced — round 4 (functions-only, no new files) simply had nothing
further to add to a count that only tracks files, which is the part of
this note that remains accurate.

## 13. Fifth-round review disposition (Kimi K3 on frozen 9010a0c44)

A sixth review pass from Kimi K3 on the frozen `9010a0c44` diff (the commit
that logged §12's disposition) surfaced eight fixes (R6-1 through R6-8,
prefixed in code/test comments accordingly), triaged by the team-lead. All
eight are fixes, not design notes; each is documented below with what
shipped, which test(s) pin it, and why it mattered. A ninth item — the
CLI shape of R6-2's own fix — was itself superseded mid-round by a
binding orchestrator/Codex refinement before this round closed; that
supersession is logged in its own subsection, not folded silently into
R6-2's entry. Two Kimi findings (F5, F8) were investigated and REFUTED
with disk evidence, logged below rather than silently dropped. Four
design notes were reviewed and accepted AS-IS, with no code change.

**R6-1 (three composed PII-scan gaps, `build_deid_corpus.py`).**
(a) the grouped-amount exemption in `_is_date_or_amount_shape` had no
ceiling on total digit count, so a 16-digit NIK written with
thousands-style comma/dot grouping borrowed the amount exemption and
escaped the PII scan entirely; capped at `_MAX_EXEMPT_AMOUNT_DIGITS = 13`
(a real Bali Zero amount tops out well below that; a NIK is always 16).
(b) `,` was missing from `_RESIDUAL_SPACED_DIGIT_RUN_RE`'s separator
class, so a comma-only-separated NIK/phone (`"3171,2345,6789,0123"`, no
space/dot/dash at all) never matched the spaced-digit-run scan in the
first place. (c) `NIK` was absent from Scan B's `_ID_DOC_NEAR_DIGITS_RE`
alternation despite this file's own G1 comment naming it as the exact
shape being protected against; `KK`/`SIM` were investigated and
DELIBERATELY excluded (empirically verified to over-match ordinary
Indonesian chat slang — "kk" = "kakak"/sibling — before deciding not to
add them). Pinned by `TestR6_1PIIScanGaps` (10 tests: guilt + innocence
for each of (a)/(b)/(c) individually, plus two end-to-end pipeline tests
proving the composed NIK-as-grouped-amount shape is dropped and a
legitimate large amount is kept).

**R6-2 (per-fixture shuffle seed derived from PUBLIC inputs only,
`wa_blind_bench.py`).** The original seed was `seed_base +
_stable_int_hash(fixture_id) % 10_000` — a function of `--seed` (default
42, printed in `--help`) and `fixture_id` (printed in plain text inside
the blind transcript itself). Anyone holding the transcript plus this
file's source — i.e. every legitimate scorer — could recompute the whole
shuffle without ever seeing the key file, defeating the point of
blinding. Fixed by folding a per-RUN SECRET nonce
(`secrets.token_hex(16)`) into `_fixture_seed`, written ONLY to the key
file's first line. Pinned by `TestR6_2NonceBasedBlinding` (5 tests: guilt
— the old public-only formula no longer matches; innocence — same nonce
reproduces the same seed; guilt-companion — different nonce yields a
different seed; two end-to-end tests — same nonce across two runs
reproduces the identical label shuffle, and an omitted nonce generates a
fresh secret per run, never a fixed constant).

**R6-2 REFINEMENT — orchestrator/Codex order, binding, supersedes the
CLI shape of the fix above.** The round-6 fix above made the nonce a
secret, then shipped it behind a `--nonce <value>` CLI flag — a secret
value typed on a command line is visible in plaintext to any OTHER
process on the same machine (via `ps`/`/proc`) for this process's whole
lifetime, the exact class of exposure R6-4 (below) already treats as
unacceptable for non-secret WhatsApp text; a stricter standard applies to
an actual secret. Codex's binding order: remove `--nonce` from the CLI
entirely. The nonce is now either generated fresh internally (the
default, unchanged) or, for a legitimate re-run, read directly off disk
from a PRIOR run's own key file via `--reuse-nonce-from <path>` — main()
reads only the file's first line, parses the `{"nonce": ...}` row, and
fails LOUD (return 1, nothing run) on a missing/malformed file rather
than silently falling back to a fresh nonce. A path in argv identifies a
file, not a secret value, so it carries none of the exposure a bare
`--nonce <value>` did. `run_bench(..., nonce=...)` still accepts an
explicit nonce as a plain Python function parameter — unchanged, and
correctly scoped: that path is for in-process callers only (this
session's own test suite, or `main()` after it has already resolved the
nonce off disk), never a value crossing an OS process boundary via argv.
Pinned by `TestR6_2RefinementReuseNonceFromFile` (4 tests): guilt — the
removed `--nonce` flag now raises `SystemExit(2)` (argparse's own
"unrecognized argument" behaviour); innocence — a full CLI invocation
with `--reuse-nonce-from <run_a's key file>` reproduces run_a's exact
label shuffle, with the nonce value itself asserted absent from the argv
list used to invoke it; two guilt tests for fail-loud — a malformed
(non-JSON) key file and a missing key file both return 1 with nothing
written to the output directory, never a silent fresh-nonce fallback.

**R6-3 (export filename reaching this script's own logs,
`build_deid_corpus.py`).** A real WhatsApp export filename is
`WhatsApp Chat with <contact name>.txt`-shaped — exactly the class of
identifier this whole script exists to keep off every output surface,
logs included. Four log sites logged `path`/`input_dir` verbatim:
unparseable-JSON warning, non-dict-line warning (R6-7's own new site),
the "no files found" warning, and the `--input-dir` missing error.
All four now log an opaque per-file ordinal (`file_index`, stable within
one `_load_records` run) or nothing at all, never the operator-typed or
export-derived path/name. Class-audit, not a spot-check: one test per
named log site plus an end-to-end pipeline test with a contact-named
export filename and a malformed sibling file, asserting the name is
absent from every captured log record across every level
(`TestR6_3NoExportFilenameInLogs`, 5 tests).

**R6-4 (Ollama NER prompt via argv, `build_deid_corpus.py`).** The
optional `--use-ollama-ner` pass built its subprocess command as
`["ollama", "run", model, prompt]` — the WhatsApp text (already
redacted, but not yet Scan A/B verified at the point this pass runs)
landed directly in this process's own argv, visible to any other process
on the machine via `ps`/`/proc`, with an ARG_MAX truncation risk for a
long chat export on top. `ollama run <model>` with no positional prompt
reads the whole piped stdin as the prompt when stdin is not a tty — the
documented non-interactive shape — so the prompt now travels via
`subprocess.run(..., input=prompt)` and `cmd` is fixed-shape
`["ollama", "run", model]`, never carrying the text. Pinned by
`TestR6_4OllamaPromptViaStdin` (3 tests): guilt — a sentinel string
planted in the prompt is absent from every element of the captured
`cmd`; innocence — the same sentinel DOES arrive via the `input=` kwarg
(the pass still actually works); and a direct assertion that `cmd` is
exactly `["ollama", "run", model]` with nothing appended, proving the
prompt was removed rather than merely failing to match by coincidence.

**R6-5 (a malformed API key escapes this module's own typed exception
taxonomy, `openai_responses_client.py`).** `httpx` encodes HTTP header
VALUES as Latin-1; building `Authorization: Bearer <key>` via
`_headers()`'s f-string with a key containing a non-ASCII character
(e.g. `'é'`) or an embedded control character (e.g. `\r\n`, a header-injection
shape `isascii()` alone would miss) raises a raw `UnicodeEncodeError`
from deep inside httpx — never one of `OpenAIClientUnavailableError` /
`OpenAINetworkError` / `OpenAIAPIError` / `OpenAIResponseShapeError`, the
set `generate()`'s own `Raises:` docstring presents as exhaustive. Fixed
by `_validate_api_key_ascii` (isascii + a dedicated control-char regex,
`_API_KEY_CONTROL_CHAR_RE`), raising the typed `OpenAICredentialFormatError`
with a coarse `category` only — never the key's content, and never even
its length, which alone can fingerprint some key formats.
**Live-gate finding this round, not carried over from a prior round**:
`_validate_api_key_ascii` was fully implemented and extensively
documented — including a "R6-5 binding correction" docstring on
`OpenAICredentialFormatError` itself — but was never actually CALLED
from `generate()`. The function existed as dead code; a malformed key
still reached `client.post()` unchanged and still raised the raw
`UnicodeEncodeError` the whole guard was written to prevent. Found by
writing this round's own first guilt test for the class (a fake
transport asserting zero network calls for a malformed key) rather than
trusting the extensive inline documentation — the test failed with the
raw `UnicodeEncodeError`, not the documented typed error. Fixed by adding
the missing `_validate_api_key_ascii(api_key)` call in `generate()`,
immediately after resolving the key and before any model/tool
validation. Pinned by the new `TestR6_5CredentialFormatValidation` (5
tests, this file's first coverage of the class at all): two guilt tests
(non-ASCII key, control-char key — each asserting `OpenAICredentialFormatError`
with the correct `category`, via a fake transport that raises
`AssertionError` if the network is ever reached, proving zero HTTP
calls); one guilt test that the exception message never contains the
key's content or its length; two innocence tests (a normal ASCII key
passes `_validate_api_key_ascii` unchanged, and the same key reaches the
network and produces a real result through the full `generate()` path).

**R6-6 (a run where every response fails still reports success,
`wa_blind_bench.py`).** `main()` exited 0 whenever the harness reached
the API at all, even if EVERY response across every fixture/candidate
pair came back as an `[ERROR: ...]` placeholder — a run that never
actually produced a usable answer looked identical, from the exit code
alone, to a genuine (possibly partial-failure) pass. `run_bench` now
counts total vs. error responses across the whole run and prints
`WA_BLIND_BENCH_STATUS=RAN_ALL_FAILED` (distinct from `RAN`) when
`error_responses == total_responses > 0`; `main()` returns 1 in that
case, 0 otherwise (including for a genuine partial failure, which stays
`RAN`). Pinned by `TestR6_6AllFailedStatus` (4 tests): guilt — all
candidates failing yields the `RAN_ALL_FAILED` status line and a nonzero
`main()` exit; two innocence tests — a mixed success/failure run and an
all-success run both stay `RAN` with the correct error count reported in
`stats`, never miscategorized as `RAN_ALL_FAILED`.

**R6-7 (a non-dict JSONL line crashes the loader, `build_deid_corpus.py`).**
A syntactically valid JSONL line whose top-level value is not an object —
`[1, 2]`, `"just a string"`, `42`, `null` — used to reach `obj.get("text")`
directly and raise a raw `AttributeError`/`TypeError`, contradicting this
module's own docstring promise that unparseable input is "counted and
skipped, never guessed at". `_iter_jsonl_records` now guards with an
explicit `isinstance(obj, dict)` check, logging (type only, per-file
ordinal, never the path — R6-3) and skipping rather than crashing.
Pinned by `TestR6_7NonDictJsonlLineDoesNotCrash` (5 tests): three guilt
tests covering list/string/number-and-null-valued lines, one innocence
test that a genuinely well-formed dict line still yields normally, and
one end-to-end test proving a non-dict line mixed with a clean record
does not crash `build_corpus` and the clean record is still kept.

**R6-8 (a test claiming independence from its own subject was a
self-comparison, `wa_blind_bench.py`).** The pre-existing
`test_stable_hash_matches_known_sha256_digest` computed its `expected`
value as `int(hashlib.sha256(...).hexdigest(), 16)` — the EXACT SAME
expression `_stable_int_hash` itself evaluates — while its own docstring
claimed to be "not a self-comparison". A genuine regression in
`_stable_int_hash`'s implementation (or its input encoding) could never
be caught by a test computing the identical thing twice. Fixed by pinning
against a LITERAL, pre-computed hex digest string (`"732535bfbf82b..."`)
pasted once and never recomputed inline — this test now checks
`_stable_int_hash` against an external, independently-verifiable value.
No new test added (the fix hardens the existing test in place); `TestStableHash`
still carries 3 tests, unchanged in count.

### REFUTED (Kimi findings investigated and rejected, with disk evidence)

**F5 — async test execution.** Kimi's finding questioned whether the
retry/backoff tests in `TestErrorHandling` (`openai_responses_client.py`'s
client tests) genuinely exercise real asynchronous execution — i.e.
whether `pytest-asyncio` is actually driving the `await asyncio.sleep(backoff)`
calls inside the retry loop, or whether something in this repo's test
configuration silently degrades them to synchronous/mocked execution.
**REFUTED by team-lead, with disk evidence**: `apps/backend-rag/pytest.ini:17`
sets `asyncio_mode = auto` — every `async def test_...` in this repo's
test suite is collected and run as a real coroutine by pytest-asyncio,
with no per-test `@pytest.mark.asyncio` decoration required. Corroborated
empirically, not just by config: this round's own test run
(`--durations=10`) measured real wall-clock durations of ~1.50-1.51s on
the retry-backoff tests in `TestErrorHandling` — `test_retryable_5xx_retries_then_succeeds`,
`test_network_error_raises_distinct_exception`, `test_retries_exhausted_raises_api_error`,
and others — which is exactly the sum of the real `asyncio.sleep(0.5 * 2**(attempt-1))`
backoff delays the retry loop actually schedules. A mocked-away or
synchronously-degraded async path could not produce that measured
latency; the durations ARE the proof the awaits are real, not merely
configured to look real.

**F8 — a stale test-count reference.** Kimi's finding raised a concern
that this file's growing test count (127 → 132 this round alone) would
leave some documented count elsewhere in the repo stale or wrong.
**REFUTED by team-lead, with disk evidence**: `docs_sync.py::count_test_files`
counts test FILES matching `test_*.py`, scoped to `backend/tests` only —
never individual test FUNCTIONS, and never anything under `scripts/bot/`.
`test_openai_responses_client.py` was created once, in an earlier round
of this same PR chain (confirmed: `git show 6a8ab5180:apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`
fails — the file does not exist at the immutable base), so it already
contributed its one `+1` to that count in the round it was first added.
This round added 5 tests INSIDE that already-existing file — zero new
files under `backend/tests` — so the FILE count `count_test_files`
tracks is unchanged this round, and no drift exists for it to catch.
Consistent with §12's closing note that `docs/AI_ONBOARDING.md` carries
no test-count references tied to these components at all, reconfirmed
this round by grep (zero hits for any of this component's file/test
names or prior round's counts).

**R8-7 reconciliation, 2026-08-15 (Kimi K3 round-8 review): "at all"
overreaches — corrected in §6.** `docs/AI_ONBOARDING.md`'s own
`<!-- DOCSYNC:QUICK_NUMBERS_START -->` aggregate DOES carry a test-count
reference tied to this component: `1359 tests` → `1360 tests`, the exact
`+1` this refutation's own logic predicts (`test_openai_responses_client.py`
being a genuinely new FILE, and `count_test_files` being file-granular).
The grep that found "zero hits" was looking for THIS ROUND's names/counts
specifically (correct — round 6 added no new file), not for the
FILE-COUNT bump that a different, earlier round already produced and
recorded. F8's core verdict (no drift, nothing stale) still holds; the
"at all" in its closing sentence does not.

### Design notes reviewed and accepted AS-IS (no code change)

- **`finish_reason` is a constant by construction.** `_parse_responses_payload`
  sets `finish_reason=status`, and `status` is gated to exactly
  `_ACCEPTED_STATUS = frozenset({"completed"})` a few lines earlier — by
  the time a `LLMResult` is ever constructed, `finish_reason` can only
  ever be the literal string `"completed"`. Reviewed and accepted: this
  is not dead code or an oversight, it mirrors the Responses API's own
  shape (status IS effectively the finish reason on this endpoint) and
  costs nothing to keep as a named field for callers that pattern-match
  on it generically across providers.
- **The top-level `refusal` output-item branch is speculative but
  fail-closed.** `_parse_responses_payload` handles a refusal nested
  inside a message's `content` parts (the shape this client's own
  fixtures exercise) AND a refusal surfaced as a top-level `output` item
  type — the second shape has no fixture or observed-in-the-wild example
  backing it in this PR. Reviewed and accepted as a defensive branch: if
  the shape never occurs, the branch is simply unreached; if it does
  occur, this client already fails closed on any output-item type it
  doesn't recognise, so leaving the branch out would have meant a
  genuine top-level refusal raising `OpenAIResponseShapeError` instead
  of being reported as `LLMResult(refusal=True, ...)` — the safer
  direction to guess wrong in is "recognise more, not less" for a
  refusal specifically, since silently failing closed on a real refusal
  is strictly worse than a no-op branch on a shape that never arrives.
- **Retry has no `Retry-After` header honoring and no jitter, capped at
  `max_retries=2`.** Reviewed and accepted: this client's retry loop
  (429/5xx/transient network errors, exponential backoff `0.5 * 2**(attempt-1)`)
  does not read a `Retry-After` response header and does not add jitter
  across concurrent callers. For an OFFLINE, unwired, human-invoked
  benchmark harness with no live traffic and no concurrent-caller
  thundering-herd risk (see §1/§6 — nothing calls this client except
  `wa_blind_bench.py`, run by hand), the added complexity of
  header-aware backoff and jitter buys nothing at this PR's actual scope
  and would be over-engineering ahead of a real caller's actual needs.
  Flagged as a genuine gap to close IF this client is ever wired to live
  traffic (§8, arming requirements) — not closed here.
- **The U+200E (left-to-right mark) in `_WA_LINE_RE` is a real WhatsApp
  export byte — an earlier draft of this note wrongly attributed it to
  in-file prose that keeps mixed-direction text rendering correctly in
  certain terminals/editors.** Corrected here (orchestrator thaw #2):
  grepping the file for U+200E finds exactly one occurrence, in the
  leading `(?:‎)?` group of `_WA_LINE_RE` itself — nowhere else, and
  certainly not attached to any explanatory remark. The real reason:
  WhatsApp's own `.txt` export prefixes each timestamped line with this
  mark, and the optional
  group exists so those lines still match — strip the literal and every
  line of a real WA export would silently stop parsing (`_iter_txt_records`
  has no error path for "the regex matched nothing," it just yields zero
  records for that line). Documented truthfully + pinned by a guilt test
  in `test_build_deid_corpus.py` (a mark-prefixed export line parses via
  `_iter_txt_records` into the record with the correct text) — every
  pre-existing test in this file constructs WA lines WITHOUT the mark, so
  a regression that stripped the literal would previously have passed
  every suite silently.

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition — never quoted from
an earlier round's own count:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **132 tests** (127 → 132, +5, all from R6-5's new
  `TestR6_5CredentialFormatValidation`). `PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=. pytest backend/tests/llm/test_openai_responses_client.py -q`
  — green, zero failures.
- `scripts/bot/test_build_deid_corpus.py`: **76 tests** (52 → 75 → 76,
  +24 total: 10 for R6-1, 5 for R6-3, 3 for R6-4, 5 for R6-7, +1 thaw #2 —
  `TestWAExportLeftToRightMarkPrefix`, pinning the U+200E guilt case
  above).
- `scripts/bot/test_wa_blind_bench.py`: **26 tests** (13 → 26, +13: 5
  for R6-2's original fix, 4 for the R6-2 CLI refinement, 4 for R6-6; R6-8
  hardened an existing test in place, +0 to the count).
  `PYTHONDONTWRITEBYTECODE=1 apps/backend-rag/.venv/bin/python -m pytest
scripts/bot/test_build_deid_corpus.py scripts/bot/test_wa_blind_bench.py -q`
  from the repo root — **102 passed**, zero failures.
- `ruff check --no-cache` on all six fenced `.py` files (client, its
  test file, the two `scripts/bot` modules, their two test files): clean.

## 14. Seventh-round review disposition (Kimi K3 on frozen 90c07b696)

A seventh review pass from Kimi K3 on the frozen `90c07b696` diff (the
commit that logged §13's disposition, base still the immutable
`6a8ab5180`, fence still exactly 9 files) came back RED with 7 findings.
The orchestrator verified all 7 as reproducible on disk before dispatch;
`bot-writer6` applied all 7 fixes. Documented below with what shipped and
which test(s) pin it.

**R7-1 (per-fixture failure log named the real model, `wa_blind_bench.py`).**
The per-candidate `except Exception` handler in `_run_one_fixture` logged
`"Fixture %s, model %s failed (%s)"` with the REAL model name — combined
with the `[ERROR: ...]` marker already visible in plain text inside the
blind transcript itself, a scorer reading both the transcript and this
process's own log output could match a failed response's opaque label
back to its real model for every fixture that hit an error, de-blinding
exactly the mapping the separate key file exists to keep secret. Fixed:
the log line now names the shuffled `label` (A/B/C…) instead — already
visible in the transcript alongside the `[ERROR: ...]` text it
corresponds to, so this adds no information a legitimate scorer doesn't
already have — never the real model name, in any per-fixture log line.
Pinned by `TestR7_1PerFixtureFailureLogNeverNamesTheRealModel` (2 tests):
guilt — neither candidate's real model name appears in any captured log
record when both fail; innocence — the fixture id and the word "label"
still appear, so the fix didn't go silent, just stopped naming models.

**R7-2 (a non-dict `--reuse-nonce-from` first line raised a raw
`TypeError`, `wa_blind_bench.py`).** `json.loads(first_line)["nonce"]`
with `except (OSError, IndexError, json.JSONDecodeError, KeyError)` —
a first line that is syntactically valid JSON but NOT a JSON object
(`[1,2]`, `42`, `"str"`, `null`) raised `TypeError`
(list/int/str/NoneType is not subscriptable by a string key), which was
absent from the except tuple and propagated as an unhandled traceback
instead of `main()`'s promised clean `return 1` — the existing
`isinstance(reused_nonce, str)` check one line below was unreachable in
that case because the exception fired first. Fixed by parsing first,
THEN checking `isinstance(parsed, dict)` before any indexing, folded into
the existing "is 'nonce' a non-empty string" validation. Pinned by
`TestR7_2NonDictNonceLineDoesNotCrash` (4 parametrized guilt tests:
`[1,2]`, `42`, `"just a string"`, `null` — each must return 1 cleanly,
never raise); innocence for the valid-file path is already covered by
§13's pre-existing `test_innocence_reuse_nonce_from_reproduces_the_same_shuffle_via_the_cli`.

**R7-3 (a malformed fixture crashed `run_bench` PARTWAY THROUGH a run,
`wa_blind_bench.py`).** `_load_fixtures` appended `json.loads(line)` with
zero shape validation. `fixture["id"]` (seed of the label_map) and
`fixture["language"]` (blind-transcript row) are read OUTSIDE any
per-candidate try/except in the caller — a fixture that was valid JSON
but not a dict, or missing those keys, crashed the run AFTER
`_open_private` had already created (and possibly partially written) the
blind transcript and key files, with no status line recorded (`fixture["text"]`
is inside the per-candidate try and would have degraded to
`[ERROR: KeyError]` instead; a pure `JSONDecodeError` already crashed
before any output opened, unchanged). Fixed: a new `FixtureFormatError`
raised by `_load_fixtures` itself — `isinstance(dict)` plus non-empty
string checks on `id`/`language`/`text` — runs BEFORE `run_bench` ever
calls `_mkdir_private`/`_open_private`, so a malformed corpus now fails
loud with zero output files touched, never a half-written run. Per the
VINCOLO in the fix order: the raised message never contains the line's
raw content nor any operator-chosen path component (R6-3 discipline) —
only the file's own generated basename (`fixtures_<lang>.local.jsonl`,
builder-chosen, never operator-chosen) and the line number. Pinned by
`TestR7_3FixtureShapeValidation` (6 tests): guilt — non-dict line,
missing required key, empty-string value, each raising
`FixtureFormatError`; innocence — a well-formed fixture still loads;
end-to-end — a malformed fixture mixed with a clean one raises before
`run_bench`'s output directory is ever created; and a dedicated test that
the exception message contains neither the line's secret content nor the
fixtures-dir's operator-chosen name, only the safe basename and line
number.

**R7-4 (path-verbatim logging class incomplete — R6-3 covered input-side
only, both scripts).** §13's R6-3 fix applied the "never log an
operator-chosen path verbatim" discipline to `build_deid_corpus.py`'s
`--input-dir` sites only. Four more sites on the OUTPUT side carried the
same class of leak this round: `build_deid_corpus.py:789`
(`"Wrote %d fixtures -> %s"`, embedding `--output-dir`),
`wa_blind_bench.py`'s `"No fixtures found under {fixtures_dir}"`, its
`"Wrote blind transcript -> %s"` / `"Wrote label key -> %s"` / SCORING
log lines (all three embedding `--output-dir` via `blind_path`/`key_path`),
and the `--reuse-nonce-from` error-message interpolation (fixed together
with R7-2 above, same site). **R6-3's claim is hereby extended to cover
the whole class, input AND output** — any operator-chosen `--*-dir`/`--*-file`
CLI argument can be named after what it contains (a directory holding a
WA export or a bench run can be contact-named exactly like the export
file itself), so every log/print site touching such a path must refer to
it generically ("the --output-dir you passed") and, where a specific
filename is useful, log only the tool's own GENERATED basename
(`fixtures_<lang>.local.jsonl`, `blind_transcript.local.jsonl`,
`label_key.local.jsonl` — always builder-fixed, never operator-chosen).
Pinned by `TestR7_4OutputDirPathClassCoversTheOutputSide` (1 test, in
`test_build_deid_corpus.py`) and `TestR7_4OutputDirPathNeverLoggedVerbatim`
(2 tests, in `test_wa_blind_bench.py`): end-to-end tests planting a
contact name in the OUTPUT directory and asserting it (and the full path)
never reach any captured log record across every level, plus a direct
check that the SKIPPED_NO_FIXTURES message doesn't leak the
`--fixtures-dir` path either.

**R7-5 (`_iter_jsonl_records` missing `errors="replace"`, `build_deid_corpus.py`).**
Its `.txt` sibling `_iter_txt_records` already opens with
`errors="replace"`; `_iter_jsonl_records` did not. A single non-UTF-8
byte in a `.jsonl` input file raised `UnicodeDecodeError` straight out of
the file iterator itself — not `json.JSONDecodeError`, so the per-line
try/except couldn't catch it — killing the entire build over one bad
byte in one input file. Fixed: `errors="replace"` added to match the txt
path; a line mangled by the replacement (U+FFFD) becomes invalid JSON and
is counted as unparseable by the existing mechanism, same fail-soft
posture as every other malformed-input case in this file. Pinned by
`TestR7_5InvalidUtf8InJsonlDoesNotCrashTheBuild` (2 tests): guilt — a
`.jsonl` file with an invalid leading byte does not raise out of
`_load_records`, and the clean second record still loads; end-to-end —
the same shape run through the full `build_corpus` pipeline still keeps
the one clean record.

**R7-6 (stale docstring naming a nonexistent field, `build_deid_corpus.py`).**
`RawRecord`'s docstring described a `_sender_for_grouping` field that
does not exist on the dataclass — the actual fields are `text` and
`source_file`; sender is read only transiently while parsing a `.txt`
export's continuation lines and is never captured into a `RawRecord` at
all. Fixed: docstring rewritten to describe the real fields, while
preserving (and sharpening) the data-minimization point the old text
made — the sender isn't merely unhashed/unstored on this dataclass, it is
never captured here in the first place. No test added (pure docstring
correction, no behavior change).

**R7-7 (`latency_ms` included retry backoff and failed round-trips,
`openai_responses_client.py`).** `t0 = time.perf_counter()` was set ONCE
before the whole retry loop; `latency_ms = (time.perf_counter() - t0) * 1000`
therefore measured from the START of attempt 1 even when the response
that produced the result came from attempt 2 or 3 — including every
backoff sleep (`0.5 * 2**(attempt-1)`) and every failed round-trip before
the successful one (e.g. ~1600ms reported for a call whose successful
3rd-attempt round-trip was actually ~100ms). This systematically
penalized, in the blind bench, whichever candidate happened to hit a
transient network/5xx blip — a latency measurement of the retry
machinery, not of the model. Fixed: `t0` is now reset at the top of
EVERY retry-loop iteration, so `latency_ms` reflects only the single
attempt that actually produced the returned result. Documented at both
the measurement site and the `LLMResult.latency_ms` field's own
docstring. No existing test asserted the old (inflated) semantics.
Pinned by the new
`test_latency_ms_measures_only_the_successful_attempt_not_retry_overhead`
in `TestErrorHandling`: real wall-clock timing (not a mocked
`time.perf_counter` — that function is a process-wide singleton shared
with asyncio/httpx internals, and an earlier draft of this test that
patched it broke unrelated machinery deep in the event loop with
`StopIteration`) — real backoff between attempts 1→2 (0.5s) and 2→3
(1.0s) totals ~1.5s of real sleep before the successful 3rd attempt even
starts, so a `latency_ms < 500` assertion reliably distinguishes the
fixed (near-instant) behavior from the pre-fix (≥1500ms) one.

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **133 tests** (132 → 133, +1, R7-7's new latency test).
  `apps/backend-rag/.venv/bin/python -m pytest
  apps/backend-rag/backend/tests/llm/test_openai_responses_client.py -q`
  — green, zero failures (confirmed both by `--collect-only -q` reporting
  133 and by the full run producing zero `F` markers, RC 0).
- `scripts/bot/test_build_deid_corpus.py`: **79 tests** (76 → 79, +3: 2
  for R7-5, 1 for R7-4's output-side coverage).
- `scripts/bot/test_wa_blind_bench.py`: **40 tests** (26 → 40, +14: 2 for
  R7-1, 4 for R7-2, 6 for R7-3, 2 for R7-4).
  `apps/backend-rag/.venv/bin/python -m pytest
  scripts/bot/test_build_deid_corpus.py scripts/bot/test_wa_blind_bench.py -q`
  from the repo root — **119 passed**, zero failures.
- `ruff check` on all six fenced `.py` files (client, its test file, the
  two `scripts/bot` modules, their two test files): clean.

## 15. Eighth-round review disposition (Kimi K3 on frozen 16185be2a)

An eighth review pass from Kimi K3 on the frozen `16185be2a` diff (the
commit that logged §14's disposition, base still the immutable
`6a8ab5180`, fence still exactly 9 files) came back RED with 12 findings
≥ LOW, all confirmed reproducible on disk by the orchestrator's gate, plus
2 MICRO findings. `bot-writer6` applied all 14 confirmed fixes (R8-1
through R8-14) and investigated, then left unchanged, the 1 MICRO finding
the mandate itself flagged as refuted. The review deliverable that
produced this round also carried two defects of its own, documented in
their own subsection below rather than folded silently into the fix list.

**R8-1 (`_load_fixtures` missing `errors="replace"`, `wa_blind_bench.py`).**
`path.open(encoding="utf-8")` had no `errors="replace"` — the exact gap
§14's R7-5 already closed on `build_deid_corpus.py::_iter_jsonl_records`,
left open here. A single non-UTF-8 byte in a fixtures file raised a raw
`UnicodeDecodeError` straight out of the file iterator, uncaught by the
per-line `json.JSONDecodeError` handling that follows. Fixed to match:
`errors="replace"` turns a mangled byte into U+FFFD, which becomes
invalid JSON and is now handled by the R8-11 fix below (a clean
`FixtureFormatError`, never a raw crash). Pinned by
`TestR8_1InvalidUtf8FixtureFileDoesNotCrash` (2 tests): guilt — an
invalid-UTF-8 leading byte in a fixtures file raises `FixtureFormatError`,
not `UnicodeDecodeError`; innocence — a clean UTF-8 file still loads.

**R8-2 (`generate()` docstring omitted `OpenAICredentialFormatError` from
its own `Raises:` section, `openai_responses_client.py`).** The method can
and does raise that exception (credential-shape validation happens before
any network call), but the docstring's `Raises:` list didn't mention it —
a caller reading only the docstring would not know to catch it. Fixed:
added to the `Raises:` section. Pure docstring correction, no behavior
change, no dedicated test (the exception's own raise-path is already
covered by the client's existing credential-format test class).

**R8-3 (per-response latency was neither recorded nor available anywhere,
plus a stale comment already claiming it was, `wa_blind_bench.py` +
`openai_responses_client.py`).** (a) `_run_one_fixture` discarded
`LLMResult.latency_ms`/`.attempts` entirely — useful per-candidate timing
data an operator debugging the bench would want, and notably NOT safe to
put in the blind transcript itself (different candidate models have
measurably different latency profiles; a scorer who could see per-response
timing alongside the blind responses could infer which label maps to which
model without ever opening the key file — the exact de-blinding risk
`label_map` already lives in the key file, never the transcript, to avoid).
Fixed: both fields now recorded in `key_row`, keyed by the same shuffled
label as `label_map`; a failed response records `None` for both (no
successful round-trip to time). (b) `LLMResult.latency_ms`'s own field
comment and the retry-loop comment near line 1163 both asserted, in
present tense, that failed/retried attempts were "systematically
penalized … in the blind bench" — a claim about `wa_blind_bench.py`'s
behavior that (before this same round's (a) fix) was not even true yet,
since latency wasn't recorded anywhere in that script at all; corrected to
describe the actual key-file consumer this round introduces. Pinned by
`TestR8_3LatencyAndAttemptsOnlyInKeyFile` (3 tests): guilt — latency never
appears in the blind transcript; innocence — latency/attempts are recorded
in the key file's `key_row` under the correct shuffled label; innocence —
a failed response records `None` for both fields.

**R8-4 (fixture-loader glob accepts contact-renamed filenames the loader
would then log verbatim, `wa_blind_bench.py`).** `_load_fixtures`' glob
(`fixtures_*.local.jsonl`) is looser than the EXACT basename shape the
actual writer (`build_deid_corpus.py::build_corpus`) ever generates
(`fixtures_{en,it,id,other}.local.jsonl`) — it also accepts a file an
operator renamed to something contact-identifying
(`fixtures_<contact-name>.local.jsonl`), and the R7-3 fix's own error
message interpolated `path.name` directly, which would log that renamed
basename verbatim on a malformed line. Fixed: `_safe_fixture_ref` logs the
basename ONLY if it matches the exact generated shape, else an opaque
per-file ordinal (`fixtures file #N`), mirroring the `file_index`
convention `build_deid_corpus.py::_iter_jsonl_records` already uses for
the same reason. Pinned by `TestR8_4SafeFixtureRefFallback` (2 tests):
innocence — the exact generated basename is returned verbatim; guilt — a
contact-renamed basename falls back to the opaque ordinal and the contact
name never appears in the returned reference.

**R8-5 (`_ID_DOC_NEAR_DIGITS_RE` missing `re.DOTALL`, `build_deid_corpus.py`).**
Without `re.DOTALL`, `.` in the `.{0,20}?` window between an ID-document
keyword and its digit run never matches `\n` — and `_iter_txt_records`
joins a WA export's continuation lines with `\n`. A real multi-line
message ("ini nomor paspor saya:\nA1234567") puts the keyword and the
digits on DIFFERENT lines; the window couldn't cross that newline, so the
pattern never matched at all — and the digit run alone (7 digits) is too
short for either of Scan A's own thresholds, so the message escaped BOTH
scans entirely. Fixed: `re.DOTALL` added so the window can cross line
breaks. Pinned by `TestR8_5IdDocNearDigitsCrossesNewlines` (4 tests):
guilt — keyword and digits on different lines are now caught; innocence —
same-line matching is unchanged; innocence — the 20-character budget is
still enforced across the newline, a keyword far beyond it is not
flagged; end-to-end — a multi-line WA message with this shape is dropped
by the full `build_corpus` pipeline.

**R8-6 (the nonce alone did not make a re-run reproducible; seed/candidates
silently diverged, `wa_blind_bench.py`).** The per-fixture shuffle is a
function of nonce + `seed` + `candidates` (`_fixture_seed` folds in
`seed_base`; `_blind_labels` shuffles exactly the `candidates` list it's
given), but the key file's first line carried only the nonce. A
`--reuse-nonce-from` re-run that supplied the same nonce but a different
`--seed` or `--candidates` silently produced a DIFFERENT shuffle — exactly
the outcome R6-2 says must fail loud, not happen quietly. Fixed:
`seed`/`candidates` now ride alongside the nonce on the key file's first
line; `main()` adopts them from the key file on `--reuse-nonce-from`, an
explicit conflicting `--seed`/`--candidates` fails loud (never silently
prefers one), and an OLDER key file that predates this tracking (only
`"nonce"`) fails loud asking for the missing value explicitly rather than
falling back to today's default — unless the operator supplies BOTH
values explicitly, in which case reproduction against an old-format file
still works. `--seed`/`--candidates` argparse defaults changed to the
sentinel `None` (`_DEFAULT_SEED` factored out as a module constant) so
`main()` can distinguish "operator didn't pass this flag" from "operator
explicitly passed today's default value" — both need different treatment
under `--reuse-nonce-from`. Pinned by `TestR8_6SeedAndCandidatesTracking`
(6 tests): guilt — a conflicting explicit `--seed` fails loud; guilt — a
conflicting explicit `--candidates` fails loud; innocence — matching
explicit `--seed`/`--candidates` succeeds; guilt — an old-format key file
(only `"nonce"`) with neither flag supplied fails loud; innocence — the
same old-format file succeeds when BOTH flags are supplied explicitly.

**R8-7 (ADR text overreached past what its own R6/R7 corrections actually
established — see §6/§12/§13, already corrected in-place this round,
not a new section).** Documented in §6, §12, and §13 above via inline
"R8-7 CORRECTION"/"R8-7 reconciliation" paragraphs rather than here, since
each correction sits directly next to the claim it narrows. Summary: §6's
file list wrongly included `docs/AI_ONBOARDING.md` among "empty diff"
files when its DOCSYNC test-count bump is real, intentional, in-scope
content (verified via `git diff origin/main -- <path>` on each of the
five files individually); §12's closing note overreached from "needed no
change this round" to implying it carries no test-count references at
all; §13's F8 refutation closing overreached with "at all" — F8's core
verdict (the file-granularity of `docs_sync.py::count_test_files`) still
holds, only the absolute phrasing needed narrowing.

**R8-8 (`/` excluded from the residual-digit-run separator class,
`build_deid_corpus.py`).** `_RESIDUAL_SPACED_DIGIT_RUN_RE`'s separator
class excluded `/` on the theory that including it would make the scan
eat every timestamp-shaped and citation-shaped string — right about the
risk, but the tradeoff left a real gap: a NIK/phone number typed with
slashes instead of spaces/dots/commas (`"3171/2345/6789/0123"`) escaped
Scan A entirely, the same class of hole R6-1(b) already closed for
commas. Fixed the same way amounts are already handled: `/` is now
included in the separator class, and `_is_date_or_amount_shape` gained a
new `_DMY_DATE_SHAPE_RE` branch recognizing the day-first
`DD/MM/YYYY`/`DD-MM-YYYY` shape, real-calendar validated via
`datetime.date` (same posture as the existing ISO-shape branch — a
calendar-impossible value like `"32/15/2026"` falls through to the amount
check, never exempted on shape alone). A short legal citation
(`"UU 6/2023"`, 6 characters) never reaches this regex's own 8-character
minimum span in the first place, so it was never at risk from this
change. Pinned by `TestR8_8SlashSeparatedDigitRunsAndDayFirstDates` (6
tests): guilt — a slash-separated NIK-shaped run is flagged; innocence —
valid `DD/MM/YYYY` and `DD-MM-YYYY` dates are exempt; guilt — a
calendar-impossible day-first shape (month 15) is NOT exempted; innocence
— a short legal citation is unaffected; end-to-end — a slash-separated NIK
message is dropped by the full pipeline.

**R8-9 (`UnicodeDecodeError` absent from the `--reuse-nonce-from` except
tuple, `wa_blind_bench.py`).** A binary/non-UTF-8 `--reuse-nonce-from`
file raises `UnicodeDecodeError` from `read_text(encoding="utf-8")` — a
sibling of `ValueError`, NOT a subclass of `json.JSONDecodeError`, so it
was absent from the existing `except (OSError, IndexError,
json.JSONDecodeError)` tuple and propagated raw as an unhandled
traceback. Fixed: `UnicodeDecodeError` added explicitly to the tuple
(rather than widening to a bare `ValueError`, which would also silently
swallow unrelated `ValueError`s a future change to this block might
raise). Pinned by `TestR8_9BinaryReuseNonceFromFileFailsLoud` (1 test):
guilt — a binary `--reuse-nonce-from` file returns `rc == 1` cleanly,
never raises, and no output directory is created.

**R8-10 (stale warning text post-R7-1, `wa_blind_bench.py`).** The
partial-failure warning in `run_bench` still said "model/fixture pairs
failed" — stale since R7-1 (§14), which changed the PER-FIXTURE failure
log to name the shuffled LABEL, never the model. Fixed: corrected to say
what the per-fixture warnings actually name, plus where the label→model
mapping actually lives (cross-reference the key file's `label_map`). Pure
text correction, no behavior change, no dedicated test.

**R8-11 (a malformed-JSON fixture line propagated a raw traceback with no
status line, `wa_blind_bench.py`).** A fixtures line that is not valid
JSON at all (`json.loads` raising `json.JSONDecodeError`) was not caught
by `_load_fixtures` — it propagated raw through `run_bench`/`asyncio.run`/
`main()`, printing no `WA_BLIND_BENCH_STATUS=` line at all, contrary to
this module's own docstring, which presents that status line as how ANY
outcome is machine-greppable. Fixed: converted to the same
`FixtureFormatError` R7-3 already uses for a wrong-shape-but-valid-JSON
line; `main()` now catches it and reports the new `FAILED_BAD_FIXTURES`
status, non-zero exit, same clean-failure posture as every other
malformed-input path in this file. Pinned by
`TestR8_11MalformedFixturesJsonReportsCleanStatus` (1 test): guilt — an
invalid-JSON fixtures line produces `WA_BLIND_BENCH_STATUS=FAILED_BAD_FIXTURES`
on stdout and `rc == 1`, with no output directory created.

**R8-12 (`httpx.AsyncClient` trusted ambient proxy env vars,
`openai_responses_client.py`).** `_get_client()` constructed
`httpx.AsyncClient(...)` without `trust_env=False` — by default httpx
reads `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` (and `.netrc`) from the
process environment, which could silently redirect this client's
authenticated OpenAI traffic through an ambient proxy neither this file
nor its operator configured. Fixed: `trust_env=False` added to the
constructor call. No dedicated test added this round (the client's
existing HTTP-boundary fake-transport tests don't exercise real proxy
resolution; the fix is a one-line construction-time flag, verified by
reading the constructed client's `_transport`/config directly is out of
scope for the mock-transport pattern this suite already uses).

**R8-13 (MICRO — no symlink defense on file creation, both `wa_blind_bench.py`
and `build_deid_corpus.py`).** Neither `_open_private`
(`wa_blind_bench.py`) nor `_write_jsonl_private` (`build_deid_corpus.py`)
passed `O_NOFOLLOW` to `os.open()` — a symlink pre-planted at the target
path before either function ran would be followed, redirecting the write
to wherever the symlink pointed. Fixed: `os.O_NOFOLLOW` added to both
`os.open()` calls, alongside the existing `O_WRONLY | O_CREAT`. Pinned by
`TestR8_13SymlinkRefusedOnWrite` in BOTH test files (2 tests each, 4
total): guilt — a pre-planted symlink raises `OSError` and the symlink
target's original content is left byte-identical, never overwritten;
innocence — a plain new (non-symlink) path is still written normally.

**R8-14 (a documented promise `_load_records` never actually implemented,
`build_deid_corpus.py`).** `_iter_txt_records`'s own docstring promised a
`.txt` file that yields zero records is "counted by the caller as
unparsed" — `_load_records` IS that caller, and never actually counted or
logged anything for that case; the promise was aspirational, not
implemented. Fixed: `_load_records` now logs a warning by opaque per-file
ordinal (never the path — R6-3 discipline) when a `.txt` file yields zero
records, so a genuinely empty/unparseable export is never silently
indistinguishable from one with 0 legitimate messages. Pinned by
`TestR8_14ZeroRecordTxtFileWarns` (2 tests): guilt — a `.txt` file with no
WA-shaped lines logs a "yielded zero records" warning, and a contact name
embedded in the file's own filename never leaks into that warning message;
innocence — a `.txt` file that does yield records does not warn.

### REFUTED (1 MICRO finding, left unchanged per the mandate)

**MICRO — the SHA-256 literal in `TestStableHash::test_stable_hash_matches_known_sha256_digest`
(`test_wa_blind_bench.py`).** The round-8 mandate itself flagged this
finding as refuted and instructed `bot-writer6` not to touch it; the
finding's original wording, as authored by Kimi, is not independently
available to this session this round (only the mandate's own
"MICRO — sha256 literal — do NOT touch" summary of it), so it is not
restated here as if independently reconstructed. What was directly
re-verified on disk this round, consistent with a refutation: the literal
(`known_digest_hex = "732535bfbf82b429d6d8075342c5f0bdf5bea92ba257e0f6eea77708a789d7ec"`)
is not a live self-comparison — the test's own docstring documents it was
computed ONCE, externally, via `hashlib.sha256(b"fixture-000001").hexdigest()`,
and pasted as a literal specifically so the test is not the same
expression written twice (that was the actual bug R6-8, §13, fixed —
see that section for the before/after). No code or test change made.

### Review-deliverable defect (found in the round-8 review artifact itself,
not in this repo's code)

One defect in the Kimi round-8 review deliverable itself surfaced during
this round's work, disclosed here per the same anti-hallucination
discipline applied to code findings — a review artifact can be wrong
about itself, and that is worth recording distinctly from a refuted code
finding. (A second item originally logged here as a review-deliverable
defect was itself mis-attributed — see "Orchestrator-mandate defect"
below for the arbitrated correction.)

1. **Footer count mismatch.** The review's own footer stated a total of
   13 findings; the numbered findings actually enumerated in the body ran
   1 through 12. This is reported as RELAYED (via the team-lead's mandate
   text), not independently re-derived — `bot-writer6` never had direct
   access to Kimi's raw review output this round to recount the numbered
   list against the footer itself.

### Orchestrator-mandate defect (found and arbitrated this round)

This item was originally logged above as a second "review-deliverable
defect" — a claim that the round-8 mandate's R8-8 text, as relayed,
asserted the reviewer cited a comment explaining the `/` exclusion that
did not exist on disk, which this session's own first-hand `Read`/`grep`
of `build_deid_corpus.py` (done BEFORE applying the R8-8 edit) directly
contradicted: the comment DID exist, as part of the "G1 binding
correction" block above `_RESIDUAL_SPACED_DIGIT_RUN_RE`. The gate
arbitrated the discontinuity this session flagged and found: (a) the
false claim originated in the **orchestrator's own mandate text**, not in
Kimi's review — `git show 16185be2a:scripts/bot/build_deid_corpus.py`,
lines 159-170, shows the G1 block with the slash-exclusion comment intact
on the exact pre-R8-8 commit the round-8 review was run against; (b) the
arbitration was performed by the gate itself via that `git show`, not by
this session; (c) root cause: an under-match in the gate's own
verification probe — literal grep patterns (`slash`, `'/'`, `"/"`)
against a slash written between backticks in prose, plus a rushed reading
of the single line the probe DID return (line 165, itself part of the
same G1 block) — the same class of failure catalogued in this repo as
`cicatrix-superscar.md` W107 ("the probe that measures a disease can have
it"); (d) Kimi's review was correct on every detail of this point,
including the distinction it drew between a comment that documents WHY
`/` is excluded and one that also admits the resulting leak shape as a
declared residual — no defect on Kimi's side here; (e) this session's
first-hand re-check before applying R8-8, and its refusal to silently
adopt the relayed claim over its own direct disk read, remains the
correct posture regardless of source — generator≠grader applies to the
orchestrator's own mandate text, not only to code diffs. The underlying
R8-8 bug itself is unaffected by any of this and remains real and
independently verified: the slash-separated NIK shape genuinely escaped
both scans before this round's fix, confirmed by the guilt tests in
`TestR8_8SlashSeparatedDigitRunsAndDayFirstDates` above.

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **133 tests, unchanged** (R8-2/R8-3(b)/R8-12 were docstring/comment
  corrections and a one-line construction flag, no new test added this
  round for the client side). `apps/backend-rag/.venv/bin/python -m
  pytest apps/backend-rag/backend/tests/llm/test_openai_responses_client.py
  --collect-only -q` — 133; full run RC 0, zero failures.
- `scripts/bot/test_build_deid_corpus.py`: **93 tests** (79 → 93, +14: 4
  for R8-5, 6 for R8-8, 2 for R8-13, 2 for R8-14).
  `--collect-only -q` — 93; full run RC 0, zero failures.
- `scripts/bot/test_wa_blind_bench.py`: **56 tests** (40 → 56, +16: 2 for
  R8-1, 3 for R8-3, 2 for R8-4, 6 for R8-6, 1 for R8-9, 1 for R8-11, 2 for
  R8-13). `--collect-only -q` — 56; full run RC 0, zero failures.
  `apps/backend-rag/.venv/bin/python -m pytest
  scripts/bot/test_build_deid_corpus.py scripts/bot/test_wa_blind_bench.py -q`
  from the repo root — **149 passed**, zero failures.
- `ruff check` on all five fenced `.py` files touched this round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`): clean.

## 16. Ninth-round review disposition (Kimi K3 on frozen 6ddc67bec)

A ninth review pass from Kimi K3 on the frozen `6ddc67bec` diff (the
commit that closed §15's round-8 disposition, base still the immutable
`6a8ab5180`, fence still exactly 9 files, terna unchanged:
`56a352584` client → `4d91b6c1d` scripts/bot → `6ddc67bec` ADR) came back
RED with 5 LOW findings and 3 MICRO findings, all 8 confirmed reproducible
on disk by the orchestrator's gate. `bot-writer7` applied all 8 confirmed
fixes (R9-1 through R9-8). The gate's own note on this round's deliverable:
it was internally coherent (the review's footer count matched its numbered
findings 1 through 8) and the non-findings the reviewer declared under its
own "WHAT I CHECKED THAT HELD" section (transport/HTTP-boundary behavior,
retry/backoff, statelessness, model/tool allowlists — the surfaces
covered by the client's existing test classes) were relayed by the
orchestrator's mandate as still valid; this session did not have direct
access to Kimi's raw review text this round and does not restate that
section's specifics as independently re-derived — same anti-hallucination
discipline §15 already applies to a relayed, not directly re-verified,
claim.

**R9-1 (LOW — stale docstring on `_has_spaced_digit_pii`, `build_deid_corpus.py`).**
The function's own docstring still said "see the module-level comment on
`_RESIDUAL_SPACED_DIGIT_RUN_RE` for why `/` is excluded from the separator
class" — but R8-8 (§15) had already INCLUDED `/` in that class and
rewritten the module-level comment to match. A stale docstring pointing a
future maintainer at a since-reversed exclusion is a real risk on its own
terms, spelled out by the reviewer: reading only the docstring, a
maintainer could conclude the date/amount exemption below it is now dead
weight (since the reason it was cited for — protecting `/`-shaped
citations from a scan that didn't yet include `/` — no longer applies as
described) and simplify it away, silently reopening the slash-separated-
NIK hole R8-8 closed. Fixed: the docstring now describes what is actually
true — `/` is INCLUDED, the over-match risk that inclusion creates is
what `_is_date_or_amount_shape` exists to close (both the ISO and the
day-first shape, each validated against the real calendar), and an
explicit note that the exemption is not dead code to simplify away. Pure
docstring correction, no behavior change, no dedicated test (nothing in
the runtime behavior moved — R8-8's own guilt/innocence tests in
`TestR8_8SlashSeparatedDigitRunsAndDayFirstDates` already pin the
behavior this docstring describes).

**R9-2 (LOW — the zero-record warning covered only the `.txt` branch,
`build_deid_corpus.py`).** R8-14 (§15) made `_load_records` warn when a
`.txt` file yields zero records, but the sibling `.jsonl` branch counted
and warned nothing — a `.jsonl` file consisting entirely of blank lines
(or lines that all fail `_iter_jsonl_records`'s own per-line skip checks)
silently contributed zero records with no signal at all, the exact gap
R8-14 closed for `.txt` left open for its sibling format. Fixed: both
branches now share the identical "yielded == 0 → warn by opaque per-file
ordinal (never the path)" posture. Pinned by
`TestR9_2ZeroRecordJsonlFileWarns` (2 tests): guilt — a `.jsonl` file of
only blank/whitespace lines logs a "yielded zero records" warning naming
`(.jsonl)`; innocence — a `.jsonl` file that does yield a record does not
warn.

**R9-3 (LOW — `FixtureFormatError` leaked the raw fixture line via its
exception chain, `wa_blind_bench.py`).** `_load_fixtures`'s invalid-JSON
branch did `raise FixtureFormatError(...) from exc`, chaining the caught
`json.JSONDecodeError` as `__cause__` — and `JSONDecodeError.doc` carries
the FULL raw fixture line that failed to parse, exactly the unverified
fixture content this module's own R7-3 discipline (§14) says the raised
message must never contain, reachable here one hop away via the
exception's cause chain instead of its message. `from None` alone would
not have closed the gap — Python's implicit chaining still sets
`__context__` to the original exception while raised inside an active
`except` block; only `__suppress_context__` changes, which affects the
standard traceback formatter's printed output, not attribute access (a
tool walking `__context__` directly — an error-reporting SDK integration,
a debugger — would still reach it). Fixed with the same deferred-raise
pattern the client already uses at its own two JSON-decode sites (K4,
§8/§9 — see `openai_responses_client.py`): the exception is built inside
the `except` block (only the safe file ref + line number captured, never
`exc`/`str(exc)`/the raw line), but the `raise` itself happens AFTER the
`except` block exits, when no exception is "currently being handled" —
verified empirically this leaves BOTH `__cause__` and `__context__`
`None`, not merely display-suppressed. Pinned by
`TestR9_3FixtureFormatErrorHasNoCauseOrContext` (2 tests): guilt — an
invalid-JSON fixture line raises `FixtureFormatError` with `__cause__ is
None` AND `__context__ is None`; innocence — a well-formed fixture still
loads normally.

**R9-4 (LOW — an empty `candidates` list in a `--reuse-nonce-from` key
file was silently adopted, `wa_blind_bench.py`).**
`all(isinstance(c, str) for c in file_candidates)` is vacuously True on
`[]` — a key file carrying `"candidates": []` was accepted as valid by
`main()`'s adoption check, `_blind_labels([])` then produces an empty
label map, zero responses are generated, `all_failed` stays `False`
(it requires `total_responses > 0`), and `main()` reports
`WA_BLIND_BENCH_STATUS=RAN` with `rc == 0` for a run that never called a
single model. Fixed in two layers, per the mandate: (a) `main()`'s
key-file adoption now requires a non-empty list of non-empty strings, not
merely a list of strings; (b) `run_bench` itself refuses an empty
`candidates` list as defense in depth, raising a new dedicated
`CandidatesEmptyError` BEFORE `_mkdir_private`/`_open_private` ever touch
the output directory — `main()` catches it and reports the new
`WA_BLIND_BENCH_STATUS=FAILED_NO_CANDIDATES`, `rc == 1`, added to the
module docstring's status-value list alongside `FAILED_BAD_FIXTURES`.
Pinned by `TestR9_4EmptyCandidatesNeverSilentlyAdopted` (3 tests): guilt —
a `--reuse-nonce-from` key file with `"candidates": []` never reports
`RAN`, `rc == 1`, no output directory created; guilt — `run_bench` called
directly with `candidates=[]` raises `CandidatesEmptyError` before any
output file exists; innocence — a key file with a valid non-empty
candidates list still adopts and runs normally (`rc == 0`, transcript
written).

**R9-5 (LOW — `trust_env=False` had no regression pin,
`openai_responses_client.py` + its test file).** R8-12 (§15) added
`trust_env=False` to the real `_get_client()`'s `httpx.AsyncClient(...)`
construction, but every existing test in `test_openai_responses_client.py`
goes through `_client_with_transport`, which builds its OWN
`httpx.AsyncClient` by hand and never calls the real `_get_client()` at
all — so a future accidental drop of the `trust_env=False` kwarg would
pass the entire suite while silently letting an ambient
`HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` route this client's
`Authorization: Bearer <key>` traffic through a third-party proxy. Fixed:
a new test exercises the REAL `_get_client()` method by monkeypatching
`httpx.AsyncClient` inside the client module to capture the kwargs it is
constructed with (rather than faking the transport, the pattern every
other test in this file uses), then asserts `trust_env is False` plus the
`timeout`/`limits` values. Pinned by
`TestR9_5GetClientTrustEnvRegression` (1 test): a future drop of the
`trust_env=False` kwarg turns this test red.

**R9-6 (MICRO — a comment misclassified `UnicodeDecodeError`'s own class
hierarchy, `wa_blind_bench.py`).** The R8-9 (§15) comment on the
`--reuse-nonce-from` except tuple said `UnicodeDecodeError` "is a sibling
of `ValueError`" — false: `UnicodeDecodeError` IS a subclass of
`ValueError` (via `UnicodeError`), so it is a SIBLING of
`json.JSONDecodeError` (also a `ValueError` subclass), not of `ValueError`
itself. The fix R8-9 shipped was already correct; only the reasoning text
was wrong. Fixed: comment text corrected, no behavior change, no
dedicated test (a class-hierarchy claim in a comment has no runtime
surface to pin).

**R9-7 (MICRO — a comment promised "read ONLY the first line" while the
code read the whole file, `wa_blind_bench.py`).** The comment above the
`--reuse-nonce-from` parse block said "Read ONLY the first line ... never
the rest of the key file" — but the code did
`args.reuse_nonce_from.read_text(encoding="utf-8").splitlines()[0]`,
which reads the ENTIRE file (real per-fixture models and label
assignments included — "the rest of the key file" the very same comment
says is out of scope for this read) into memory before discarding
everything past the first newline. Fixed: `with
args.reuse_nonce_from.open(encoding="utf-8") as f: first_line =
f.readline().strip()` reads exactly one line off the file object; the
rest of the file is never pulled into memory. An empty key file now
yields `""` from `readline()` rather than raising `IndexError` from
`splitlines()[0]` — `json.loads("")` already raises
`json.JSONDecodeError`, already in the except tuple, so the fail-loud
outcome for an empty file is unchanged; `IndexError` is dropped from the
except tuple as dead (unreachable via this read path any more). No new
test added — the empty/malformed-key-file fail-loud path this change
preserves is already pinned by the existing R7-2/R8-9 tests
(`splitlines()[0]`'s `IndexError` case and `readline()`'s `""` case both
resolve to the same already-covered `json.JSONDecodeError` outcome).

**R9-8 (MICRO — `_mkdir_private` had no symlink defense on the leaf
directory itself, BOTH `wa_blind_bench.py` and `build_deid_corpus.py`).**
R8-13 (§15) added `O_NOFOLLOW` defense against a pre-planted symlink to
both files' leaf-FILE writers (`_open_private` / `_write_jsonl_private`)
but left the directory-component twin open: `Path.mkdir(parents=True,
exist_ok=True)` silently accepts a pre-planted symlink at `path` whose
target is a directory (no `O_NOFOLLOW` equivalent exists for `mkdir`),
and the unconditional `os.chmod` that follows FOLLOWS a symlink to its
target by default — so a symlink leaf would get its chmod applied to
whatever directory it points at, not `path` itself. Fixed identically in
both files: after `mkdir`, `if path.is_symlink(): raise OSError(...)`
before the `chmod`, no operator-chosen path component in the error
message. Pinned by `TestR9_8MkdirPrivateRefusesSymlinkLeaf` in BOTH test
files (2 tests each, 4 total): guilt — a pre-planted symlink leaf raises
`OSError` and the symlink's real target directory's permissions are left
byte-identical, never tightened through the symlink; innocence — a plain
(non-symlink) directory is still tightened to 0700 as before.

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **134 tests** (133 → 134, +1 for R9-5). `apps/backend-rag/.venv/bin/python
  -m pytest apps/backend-rag/backend/tests/llm/test_openai_responses_client.py
  --collect-only -q` — 134; full run RC 0, zero failures, 134 passed.
- `scripts/bot/test_build_deid_corpus.py`: **97 tests** (93 → 97, +4: 2
  for R9-2, 2 for R9-8). `--collect-only -q` — 97.
- `scripts/bot/test_wa_blind_bench.py`: **63 tests** (56 → 63, +7: 2 for
  R9-3, 3 for R9-4, 2 for R9-8). `--collect-only -q` — 63.
  `python3 -m pytest scripts/bot/test_build_deid_corpus.py
  scripts/bot/test_wa_blind_bench.py -q` from the repo root — **160
  passed**, zero failures, RC 0.
- `ruff check` on all six fenced `.py` files touched this round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.

## 17. Tenth-round review disposition (Kimi K3 on frozen 1ed1099c7)

A tenth review pass from Kimi K3 on the frozen `1ed1099c7` diff (the
commit that closed §16's round-9 disposition, base still the immutable
`6a8ab5180`, fence still exactly 9 files, terna unchanged:
`56a352584` client → `4d91b6c1d` scripts/bot → `1ed1099c7` ADR) came back
RED with 2 LOW findings and 4 MICRO findings, all 6 confirmed reproducible
on disk by the orchestrator's gate. `bot-writer7` applied all 6 confirmed
fixes (R10-1 through R10-6). Transport identical to every prior round of
this ADR — nothing in the live WhatsApp runtime imports any of this. The
gate's own note on this round's deliverable: internally coherent (footer
count matched the 6 numbered findings), and the reviewer's own "Checked
and held" section — validating R9-3's deferred-raise (`__cause__`/
`__context__` both `None`), R9-5's real-`_get_client()` regression test,
R9-2's jsonl zero-record symmetry, R9-7's genuine single-line read, and
the R8-8 slash-separated-NIK/day-first-date shapes — was relayed by the
orchestrator's mandate as still valid; this session did not have direct
access to Kimi's raw review text this round either and does not restate
that section's specifics as independently re-derived.

**R10-1 (LOW — the `WA_BLIND_BENCH_STATUS=` contract was broken on
early-exit sites, `wa_blind_bench.py`).** Every `return 1` inside
`main()`'s `--reuse-nonce-from`/adoption block skipped `_print_status`
entirely — an unreadable/malformed key file, a missing or non-string
nonce, a non-integer seed field, a conflicting explicit `--seed`, a
legacy key file predating R8-6's seed tracking, an unusable `candidates`
field (including R9-4(a)'s empty-list rejection), a conflicting explicit
`--candidates`, and a legacy key file predating R8-6's candidates
tracking — 8 sites at the time this fix was authored, none of them
printing the status line this module's own docstring presents as how ANY
outcome is machine-greppable. **R11-5 correction, 2026-08-15 (Kimi K3
round-11 review): "8 sites" and "7 of the 8" below described the block as
R10-1 itself left it — R10-3, in this SAME round, added a NINTH site to
the identical block (the duplicate-candidates check in key-file
adoption), and this paragraph was never updated to say so. Recounted on
disk, not assumed: `grep -c` of `_print_status("FAILED_BAD_REUSE_FILE")`
plus `_print_status("FAILED_NO_CANDIDATES")` calls inside `main()`'s
`--reuse-nonce-from` block (excluding the 3 separate sites in the
`asyncio.run(...)` except-clauses further down, which are outside this
block) is **9 today**: 7 `FAILED_BAD_REUSE_FILE` + 2
`FAILED_NO_CANDIDATES` (the original candidates-malformed site this
paragraph names, plus R10-3's duplicate-candidates site). The R10-3
paragraph below already describes its own site correctly; only THIS
paragraph's site count was stale.** Separately, an `OSError` raised
inside `run_bench` itself (from `_mkdir_private`/`_open_private` — a
permission failure, or the R9-8 symlink-leaf refusal) propagated raw
past `asyncio.run`/`main()` with no status line either. Fixed: (a) a new
`FAILED_BAD_REUSE_FILE` status is printed before 7 of the (then-)8 sites;
the 8th (the candidates-field-is-unusable site) prints
`FAILED_NO_CANDIDATES` instead, for symmetry with
the `run_bench`-level `CandidatesEmptyError` catch already using that
status (R9-4(b)) — the mandate was explicit that this one site should NOT
get the generic reuse-file status, since the underlying defect (an
unusable candidates list) is the same one `FAILED_NO_CANDIDATES` already
names; (b) `main()`'s `asyncio.run(...)` call gained a new
`except OSError as exc:` clause printing the new `FAILED_IO` status,
logging ONLY `type(exc).__name__` — never `str(exc)`, since an
`OSError`'s message commonly embeds the filesystem path that triggered it
(this file's own R6-3/R7-4 discipline never logs an operator-chosen path
verbatim); (c) both new status values documented in the module docstring
alongside `FAILED_BAD_FIXTURES`/`FAILED_NO_CANDIDATES`. Pinned by
`TestR10_1StatusContractOnEveryEarlyExit` (3 tests: guilt — a key file
missing 'nonce' reports `FAILED_BAD_REUSE_FILE`, never `RAN`; guilt — a
conflicting explicit `--seed` reports `FAILED_BAD_REUSE_FILE`; guilt — a
pre-planted symlink at `--output-dir` reports `FAILED_IO`, never `RAN`,
and the real symlink-target path never appears in the log output) plus
the existing R9-4 guilt test reinforced with `capsys` per the mandate:
it now asserts BOTH that `RAN` is absent AND that `FAILED_NO_CANDIDATES`
is present, not merely `rc == 1`.

**R10-2 (LOW — `if not candidates:` did not mirror the adoption layer's
element-level predicate, `wa_blind_bench.py`).** `run_bench`'s own
candidates guard checked only emptiness — `[""]` is truthy, so it passed
this guard and failed later via the WRONG mechanism
(`OpenAIModelNotAllowedError` raised per-candidate deep inside
`_run_one_fixture`, surfacing as `RAN_ALL_FAILED` rather than the
`FAILED_NO_CANDIDATES` R9-4(b) exists to produce for exactly this class
of defect). Fixed: a second, separate `raise CandidatesEmptyError(...)`
after the emptiness check, testing `all(isinstance(c, str) and c for c in
candidates)` — kept as a distinct raise (not folded into one combined
message) so the two failure modes get distinct log text, and the
offending element's own content is never echoed (same R6-3-class
discipline as every other operator-input message in this file). Pinned
by `TestR10_2CandidatesElementLevelValidation` (1 test): guilt —
`candidates=[""]` raises `CandidatesEmptyError` before any output file
exists.

**R10-3 (MICRO — duplicate candidate names were accepted everywhere,
`wa_blind_bench.py`).** `["gpt-5.6-terra", "gpt-5.6-terra"]` passes both
the emptiness and element-type checks — it IS a non-empty list of
non-empty strings — but `_blind_labels` then binds two DIFFERENT blind
labels to the SAME underlying model, defeating the point of blind
scoring: a scorer reading the transcript would judge them as independent
candidates. Fixed in BOTH layers, per the mandate: `run_bench`'s own
guard (`len(set(candidates)) != len(candidates)` →
`CandidatesEmptyError("candidates list contains duplicate candidate
names")`) — reached by every caller, CLI included, even when
`main()`'s adoption layer doesn't apply — and the same check added to
`main()`'s `--reuse-nonce-from` key-file adoption, printing
`FAILED_NO_CANDIDATES` for symmetry with every other candidates-defect
site (R10-1). Pinned by `TestR10_3DuplicateCandidatesRejected` (3 tests):
guilt — `run_bench` called directly with a duplicate pair raises
`CandidatesEmptyError`; guilt — a `--reuse-nonce-from` key file with a
duplicate pair reports `FAILED_NO_CANDIDATES`, never `RAN`; innocence —
two DISTINCT candidate names still run normally.

**R10-4 (MICRO — `os.ftruncate`/`os.lseek` were naked after the guarded
`os.fchmod`, BOTH `wa_blind_bench.py` and `build_deid_corpus.py`).** Both
`_open_private` and `_write_jsonl_private` wrap `os.fchmod(fd, 0o600)` in
a `try/except OSError: os.close(fd); raise` — but the `os.ftruncate`/
`os.lseek` calls immediately after sat OUTSIDE that guard. An `OSError`
from either (disk full on `ftruncate`, an unlikely-but-real `lseek`
failure) would leak the fd and propagate past the function, violating the
exact "any post-open failure closes the fd" invariant both docstrings
already claimed. Fixed identically in both files: `os.fchmod`,
`os.ftruncate`, and `os.lseek` now all sit inside the same
close-then-reraise `try/except OSError` block; docstrings updated to
describe the actual (now true) guarantee. No dedicated test added — the
mandate did not call for one, and the fix is a pure reordering of
existing calls into an existing guard clause with no new branch to pin
(the guard's own close-and-reraise behavior on `os.fchmod` failure is
already covered by this function's existing test coverage from earlier
rounds).

**R10-5 (MICRO — a comment referenced a call site that no longer exists,
`wa_blind_bench.py`).** The R8-9/R9-6 comment on the `--reuse-nonce-from`
except tuple still said `UnicodeDecodeError` "is raised by
`read_text(encoding=\"utf-8\")`" — stale since R9-7 (§16) replaced that
call with `open(encoding="utf-8")` + `f.readline()`. Fixed: reference
corrected to describe the actual current read path (the file object's own
text-mode decoding on `readline()`); the except-tuple entry itself was
never wrong and needed no change. Pure comment correction, no dedicated
test (a stale code-reference in a comment has no runtime surface to pin).

**R10-6 (MICRO — the symlink-leaf refusal's docstring overstated its own
guarantee, BOTH files).** R9-8's `_mkdir_private` fix (§16) checks
`path.is_symlink()` then calls `os.chmod` — a real check-then-act
sequence, not atomic, leaving a TOCTOU window where a symlink could in
principle be swapped in between the two calls. The mandate was explicit
that closing this window is out of scope (a same-user local race is a
different, not-yet-declared threat model from the pre-planted-symlink
class R8-13/R9-8 target) — the fix here is a single honest sentence added
to both docstrings: this protects against a symlink planted BEFORE the
function runs, it is not a TOCTOU-proof guarantee against a same-user
attacker racing this exact call. No behavior change, no dedicated test
(a docstring scope clarification has no runtime surface to pin).

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **134 tests, unchanged** (no round-10 finding touched this file — R10-1
  through R10-6 are all `scripts/bot/` findings). `PYTHONPATH=. apps/backend-rag/.venv/bin/python
  -m pytest apps/backend-rag/backend/tests/llm/test_openai_responses_client.py
  --collect-only -q` — 134; full run RC 0, zero failures, 134 passed.
- `scripts/bot/test_build_deid_corpus.py`: **97 tests, unchanged** (R10-4
  and R10-6 both touch this file but neither adds a test, per the
  mandate — a reordering-into-an-existing-guard and a docstring scope
  note). `--collect-only -q` — 97.
- `scripts/bot/test_wa_blind_bench.py`: **70 tests** (63 → 70, +7: 3 for
  R10-1, 1 for R10-2, 3 for R10-3). `--collect-only -q` — 70.
  `python3 -m pytest scripts/bot/test_build_deid_corpus.py
  scripts/bot/test_wa_blind_bench.py -q` from the repo root — **167
  passed**, zero failures, RC 0.
- `ruff check` on all six fenced `.py` files touched across every round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.

## 18. Eleventh-round review disposition (Kimi K3 on frozen edbc04e85)

An eleventh review pass from Kimi K3 on the frozen `edbc04e85` diff (the
commit that closed §17's round-10 disposition, base still the immutable
`6a8ab5180`, fence still exactly 9 files, terna unchanged:
`56a352584` client → `4d91b6c1d` scripts/bot → `edbc04e85` ADR) came back
RED with 4 LOW findings and 2 MICRO findings, all 6 confirmed
reproducible on disk by the orchestrator's gate. `bot-writer7` applied all
6 confirmed fixes (R11-1 through R11-6). Transport identical to every
prior round. The reviewer's own "what held" section — validating the 9
early-exit sites once correctly counted (see R11-5 below), the ordering
of the candidates guards (emptiness → element-type → duplicates, R10-2/
R10-3), and the deferred-raise pattern (R9-3/K4) — was relayed by the
orchestrator's mandate as still valid; this session did not have direct
access to Kimi's raw review text this round either and does not restate
that section's specifics as independently re-derived.

**R11-1 (LOW — R10-4's own guilt test never reached the branch it was
supposed to pin, BOTH `wa_blind_bench.py` and `build_deid_corpus.py`
test files).** The only failure test either private writer had before
this round monkeypatches `os.fchmod` to raise — which fires FIRST in the
guarded `try` block (`os.fchmod` → `os.ftruncate` → `os.lseek`), so the
`os.ftruncate`/`os.lseek` code R10-4 (§17) actually added to that guard
was never exercised by any existing test. §17's own R10-4 paragraph
claimed "no new branch to pin" — false: the fd-closed-on-truncate-failure
BEHAVIOR is genuinely new (before R10-4, an `os.ftruncate` failure leaked
the fd; after, it doesn't), and a behavior that changed with no test
covering the changed path is exactly the gap this finding names. Fixed:
a new guilt test in BOTH files monkeypatches `os.ftruncate` to raise
`OSError`, spies on `os.close` to assert the fd is closed EXACTLY once
(not zero, not twice), and asserts the exception propagates —
`test_r11_1_ftruncate_failure_closes_fd_exactly_once_and_propagates` in
`test_wa_blind_bench.py`'s `TestOpenPrivateFchmod` and the equivalent
class in `test_build_deid_corpus.py`. The R10-4 paragraph in §17 above
is NOT rewritten (this ADR's own convention, established at R8-7: correct
forward, never silently edit a prior round's claim) — this paragraph is
the correction.

**R11-2 (LOW — the same class of gap, one call later: `os.fdopen` sat
OUTSIDE the R10-4 guard, BOTH files).** `os.fdopen(fd, "w",
encoding="utf-8")` — the very next statement after the guard R10-4
closed — was never inside it. An `os.fdopen` failure (fd exhaustion,
errno 24 EMFILE/ENFILE — a real, reachable condition on a
process/system fd-table limit, not a hypothetical) would leak `fd` past
this function's return/write path, violating the exact "any post-open
failure closes the fd" invariant both docstrings already claimed one
statement too early. Fixed identically in both files: `os.fdopen` now
sits inside the SAME `try/except OSError: os.close(fd); raise` guard as
`os.fchmod`/`os.ftruncate`/`os.lseek`. Close-on-exception-ONLY, by
construction — once `os.fdopen` returns successfully, ownership of `fd`
passes to the returned file object (`wa_blind_bench.py::_open_private`
returns it directly; `build_deid_corpus.py::_write_jsonl_private` wraps
it in its own `with f:` block) — closing it again unconditionally on the
success path would be a double-close of a live fd the caller is about to
use. Pinned by a new guilt test in both files monkeypatching `os.fdopen`
itself to raise (bypassing the real `FileIO` implementation entirely, so
the test's own `os.close` spy count is unambiguous): the fd is closed
exactly once, the exception propagates.

**R11-3 (LOW — the `FAILED_IO` test's negative assertion was VACUOUS,
`test_wa_blind_bench.py`).** `assert str(real_target) not in
captured.err` (added in §17's R10-1 test) could never fail, for a reason
specific to this test suite's structure rather than to the code under
test: `logging.basicConfig` (called once, inside `main()`, on every
invocation across this whole pytest session) attaches a `StreamHandler`
bound to whichever `sys.stderr` OBJECT is live at the moment of the
FIRST `main()` call anywhere in the session — `capsys` replaces
`sys.stderr` with its own capture object on every test, but the
already-constructed handler from an earlier test keeps writing to the
STALE reference, so `captured.err` can be, and in practice was, empty
regardless of what `logger.error` actually emitted. An assertion that
something is absent from a capture stream that may never receive
anything proves nothing — this repo's own scar catalogue
(`cicatrix-superscar.md` family "the probe that measures a disease can
have it") names exactly this class: a probe that cannot say "yes" is not
a probe. Fixed: switched to `caplog` (pytest's own handler, attached
independently of whatever `logging.basicConfig` did) for BOTH halves —
the negative assertion (the real symlink-target path never appears in
any captured log message) AND a new POSITIVE control proving the log
line this test exists to verify actually fired (`"OSError" in m and
"I/O error" in m` across `caplog.records`). The `FAILED_IO`
status-on-stdout half is untouched — `capsys` IS reliable for stdout,
since this module's status line is `print()`, never routed through
`logging`.

**R11-4 (LOW — `max_retries` was never validated at construction,
`openai_responses_client.py`).** `OpenAIResponsesClient.__init__`
accepted any value for `max_retries` with no type or range check — the
THIRD recurrence in this codebase of the "a caller-supplied value of the
wrong type or shape bypasses this module's own typed exception taxonomy"
class (siblings: R8-6's `isinstance(file_seed, int) or
isinstance(file_seed, bool)` guard on `wa_blind_bench.py`'s seed field;
R9-4/R10-2's element-level candidates validation in the same file — both
in this ADR's own prior rounds). Two concrete failure modes: (a)
`max_retries=2.5` reaches `range(1, self.max_retries + 2)` inside
`generate()` and raises a raw `TypeError`
(`'float' object cannot be interpreted as an integer`) — NOT one of this
module's own documented exception types, so a caller written against
this client's exception hierarchy would not catch it; (b)
`max_retries=-1` produces `range(1, 1)`, an EMPTY range — the retry
loop's body never executes, zero network calls are ever made, and
execution falls through to the loop's trailing `raise
OpenAINetworkError("exhausted retries with no response and no captured
exception...")` — a transport-flavored exception naming a transport that
was never touched, misleading about what actually happened. Fixed:
`__init__` now validates `isinstance(max_retries, int) and not
isinstance(max_retries, bool) and max_retries >= 0`, raising `ValueError`
with a message naming only the offending TYPE (never a raw value that
could in principle be operator-influenced, matching this file's own
no-raw-content discipline elsewhere), documented in a new `Raises:`
section on the constructor's docstring. `bool` is explicitly excluded
even though `isinstance(True, int)` is `True` in Python — the same
bool-exclusion trap R8-6 already had to guard against. Pinned by
`TestR11_4MaxRetriesValidation` (5 tests, exactly the guilt/innocence
split the mandate specified): guilt — `2.5`, `-1`, `True` each raise
`ValueError` at construction; innocence — `0` and the default `2` both
construct normally.

**R11-5 (MICRO — the R10-1 paragraph in §17 undercounted the
early-exit sites it describes, `research/operations/2026-08-15-adr-wa-
runtime-openai-provider.md`).** §17's R10-1 paragraph said "8 sites
total" and "7 of the 8" — accurate for what R10-1 itself authored, but
R10-3, in that SAME round, added a NINTH site to the identical block
(the duplicate-candidates check added to `main()`'s `--reuse-nonce-from`
key-file adoption) and the R10-1 paragraph was never revisited to say
so. Recounted on disk, not assumed or taken from the reviewer's number
either: `grep -n` of every `_print_status("FAILED_BAD_REUSE_FILE")` and
`_print_status("FAILED_NO_CANDIDATES")` call site inside `main()`'s
`--reuse-nonce-from` block (excluding the 3 separate sites in the
`asyncio.run(...)` except-clauses further down the function, which are
outside that block) gives **9**: 7 `FAILED_BAD_REUSE_FILE` + 2
`FAILED_NO_CANDIDATES`. Fixed: a correction inserted directly into the
R10-1 paragraph in §17 (this ADR's own convention — correct forward with
an inline dated note, never silently rewrite a prior round's prose), not
a rewrite of the surrounding numbers, which remain historically accurate
for what R10-1 itself did. No code or test change — this is a pure
documentation-accuracy finding.

**R11-6 (MICRO — a code-span was split mid-token across a line break,
`build_deid_corpus.py`).** `_mkdir_private`'s docstring rendered
`` `Path.mkdir(parents=`` on one line and `` True, exist_ok=True)` `` on
the next — a backtick-delimited code span broken by a hard line wrap in
the middle of an identifier, malformed Markdown wherever this docstring
is rendered. The sibling docstring in `wa_blind_bench.py::_open_private`
carries the equivalent line correctly. Fixed: rejoined into one
unbroken code span, docstring re-wrapped around it. Pure formatting
correction, no behavior change, no dedicated test (a docstring rendering
defect has no runtime surface to pin).

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **139 tests** (134 → 139, +5 for R11-4). `PYTHONPATH=. apps/backend-rag/.venv/bin/python
  -m pytest apps/backend-rag/backend/tests/llm/test_openai_responses_client.py
  --collect-only -q` — 139; full run RC 0, zero failures, 139 passed.
- `scripts/bot/test_build_deid_corpus.py`: **99 tests** (97 → 99, +2: 1
  for R11-1, 1 for R11-2). `--collect-only -q` — 99.
- `scripts/bot/test_wa_blind_bench.py`: **72 tests** (70 → 72, +2: 1 for
  R11-1, 1 for R11-2; R11-3 modified an existing test in place, adding no
  new test). `--collect-only -q` — 72.
  `python3 -m pytest scripts/bot/test_build_deid_corpus.py
  scripts/bot/test_wa_blind_bench.py -q` from the repo root — **171
  passed**, zero failures, RC 0.
- `ruff check` on all six fenced `.py` files touched across every round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.

## 19. Twelfth-round review disposition (Kimi K3 on frozen 3db60aeea)

A twelfth review pass from Kimi K3 on the frozen `3db60aeea` diff (the
commit that closed §18's round-11 disposition, base still the immutable
`6a8ab5180`, fence still exactly 9 files, terna unchanged: `5e024a976`
client → `01524fdf9` scripts/bot → `3db60aeea` ADR) came back RED with 4
LOW findings and 1 MICRO finding, all 5 confirmed reproducible on disk by
the orchestrator's gate. `bot-writer7` applied all 5 confirmed fixes
(R12-1 through R12-5). Transport identical to every prior round. This
round is notable for containing a REVERT: R12-4 undoes R11-2 — the
round-11 gate mandate chose a hazardous fix direction (wrap `os.fdopen`
inside the close-on-exception guard) over a safer alternative the
round-11 reviewer had also offered (leave `os.fdopen` narrowly outside
the guard); round-12 measured why "wrap" is dangerous in CPython and
mandates reverting to "narrow", with the attribution recorded honestly
below rather than silently rewriting §18's R11-2 paragraph.

**R12-1 (LOW — `timeout` was never validated at construction,
`openai_responses_client.py`).** `OpenAIResponsesClient.__init__` accepted
any value for `timeout` with no type or range check, handed unexamined to
`httpx.AsyncClient(timeout=...)` inside `_get_client()`. `timeout="abc"`
or `timeout=True` would only fail deep inside httpx's own timeout-config
parsing — an exception outside this module's typed hierarchy, on the
FIRST real network call rather than at construction. `timeout=float("nan")`
is worse: httpx does not reject NaN, so every per-attempt deadline
comparison against it is silently always-false and a hung connection
would never time out at all. Fixed: `__init__` now validates
`isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and
math.isfinite(timeout) and timeout > 0`, raising `ValueError` naming only
the offending type (same no-raw-value discipline as R11-4's
`max_retries` check), documented in a new `Raises:` entry. `bool` is
excluded for the same subtype-trap reason as every prior instance of this
class in this file. Pinned by `TestR12_1TimeoutValidation` (6 tests):
guilt — `"abc"`, `True`, `-1`, `float("nan")` each raise `ValueError` at
construction; innocence — `30` (int) and `12.5` (float) both construct
normally.

**R12-2 (LOW — `api_key` type was never validated at construction,
`openai_responses_client.py`).** A non-`str`, non-`None` `api_key` (e.g.
`123` or `b"sk-x"`) previously reached `_resolve_api_key()` and then
`_validate_api_key_ascii()` unexamined — the ASCII/control-char regex
match on a non-`str` raises a raw `TypeError` from `re.search`, again
outside this module's typed exception hierarchy. This is the FOURTH/FIFTH
recurrence (alongside R12-1 in this same round) of the "a caller-supplied
value of the wrong type bypasses this module's own typed taxonomy" class
first named at R8-6 and repeated at R9-4/R10-2 and R11-4 in prior rounds
of this ADR. Fixed: `__init__` now validates `api_key is None or
isinstance(api_key, str)`, raising `ValueError` naming only the offending
type. The existing empty-string-is-falsy-and-therefore-unavailable
semantics (`api_key=""` behaves as "no key provided", not as an error)
are preserved unchanged — only the *type* is validated here, not the
value. Pinned by `TestR12_2ApiKeyTypeValidation` (5 tests): guilt — `123`
(int), `b"sk-x"` (bytes) each raise `ValueError`; innocence — `None`,
`"sk-x"`, and `""` all construct normally.

**R12-3 (MICRO — the R10-1/R11-5 "9 sites" text still said "8" in three
more places, `wa_blind_bench.py` and `test_wa_blind_bench.py`).** §18's
R11-5 corrected the ADR's own prose from "8" to "9" but the corresponding
in-code comments and docstrings were never revisited: `wa_blind_bench.py`
still said "8 distinct exit sites" (module docstring) and "all 8
early-exit sites" (inline comment at the R10-1 fix site);
`test_wa_blind_bench.py` still said "7 of the 8 sites" / "the 8th" (class
docstring), "site 2 of the 8", and "site 4 of the 8" (two inline test
comments). Recounted on disk again this round, not assumed: `grep -n` of
every `_print_status("FAILED_BAD_REUSE_FILE")` and
`_print_status("FAILED_NO_CANDIDATES")` call site inside `main()`'s
`--reuse-nonce-from` block confirms **9** (7 + 2), matching §18's R11-5
figure exactly — this finding is a code/test-comment sync-up, not a new
recount. Fixed: all five stale "8"/"8th" occurrences corrected to "9",
each with an inline R12-3 dated note so the correction itself is
traceable. No behavior or test-assertion change — pure documentation
accuracy, same class as R11-5, just found in code comments this time
instead of the ADR.

**R12-4 (LOW — SUPERSEDES R11-2: wrapping `os.fdopen` in the
close-on-exception guard is itself hazardous in CPython, both
`wa_blind_bench.py::_open_private` and
`build_deid_corpus.py::_write_jsonl_private`).** §18's R11-2 moved
`os.fdopen(fd, "w", encoding="utf-8")` INSIDE the same
`try/except OSError: os.close(fd); raise` guard that already covered
`os.fchmod`/`os.ftruncate`/`os.lseek`, reasoning that an unguarded
`os.fdopen` failure would leak `fd`. The round-11 reviewer had in fact
offered TWO options — wrap `os.fdopen` in the guard, or leave it narrowly
outside it — and the round-11 gate mandate picked "wrap" without the
CPython-internals analysis below. Round-12 measured why that choice is
dangerous: `os.fdopen` constructs an `io.TextIOWrapper` around an
`io.FileIO(fd, closefd=True)` (the default); if construction fails
PARTWAY THROUGH — after `FileIO` has already taken ownership of `fd` but
before `fdopen` returns — CPython may have already closed `fd` itself as
part of unwinding the partially-constructed object. A blind
`os.close(fd)` in the `except` clause then either (a) raises `OSError:
[Errno 9] Bad file descriptor` on an already-closed fd, masking the
ORIGINAL exception, or (b) — worse, in a multithreaded process — closes a
DIFFERENT, unrelated fd that the OS has already recycled to the same
integer, silently corrupting another part of the process. Both outcomes
are strictly worse than the single-fd leak the wrap was meant to prevent.
Fixed: reverted in BOTH files — `os.fdopen` sits OUTSIDE the guard again,
which now covers only `os.fchmod`/`os.ftruncate`/`os.lseek` (R10-4's
original scope, before R11-2 widened it). Both docstrings rewritten to
explain the CPython hazard honestly rather than merely restoring the
pre-R11-2 text verbatim — a silent revert-and-forget would leave the next
reviewer to rediscover the same "should this be wrapped?" question with
no record of why the answer is no. The R11-2 factual claim "errno 24
EMFILE/ENFILE" is also corrected in passing: `ENFILE` is errno 23, not
24, and neither applies to `os.fdopen` in the first place, since it wraps
an already-open fd and never allocates a new one — the realistic residual
failure modes are a bad `mode` string (programmer error) or a rare
in-process memory-allocation failure while constructing the wrapper
objects. **Test impact, declared explicitly per this round's mandate:**
the two guilt tests R11-2 added
(`test_r11_2_fdopen_failure_closes_fd_exactly_once_and_propagates` in
both `test_wa_blind_bench.py` and `test_build_deid_corpus.py`) pinned
EXACTLY the reverted behavior and are DELETED, not rewritten — there is
no close-on-exception branch left around `os.fdopen` to pin. The
`scripts/bot` combined test count therefore DROPS by 2 this round (see
final counts below), the only round in this ADR where a test count goes
down rather than up. The R11-2 paragraph in §18 is NOT rewritten (this
ADR's own R8-7 convention: correct forward, never silently edit a prior
round's claim) — this paragraph, and this table entry, are the
correction, with the attribution stated plainly: round-11's reviewer
offered "narrow" as an option, round-11's gate chose "wrap", round-12
proved "wrap" hazardous, the cure is "narrow" — i.e. a return to what
R10-4 already had before R11-2 touched it, now with the reasoning
recorded so it does not get re-wrapped a third time.

**R12-5 (LOW — the R11-1 `os.ftruncate`-failure guilt tests never
asserted content preservation, both `test_wa_blind_bench.py` and
`test_build_deid_corpus.py`).** §18's R11-1 added a guilt test for the
`os.ftruncate` failure branch that asserts the fd is closed exactly once
and the exception propagates, but — unlike its sibling `os.fchmod`-
failure test immediately above it in the same class, which also reads
the file back and asserts `target.read_text(...) == original_content` —
the R11-1 test never checked that the pre-existing content actually
survived untouched. Both docstrings (`_open_private` and
`_write_jsonl_private`) claim the SAME guarantee for the `os.ftruncate`
branch as for the `os.fchmod` branch: "the file's pre-existing bytes are
UNTOUCHED" on any post-open failure. A test that verifies fd-closed but
not content-preserved was only proving half of that guarantee for this
specific branch. Fixed: added
`assert target.read_text(encoding="utf-8") == original_content` (with an
explanatory message) to both R11-1 tests, mirroring the sibling
`os.fchmod`-failure test's own assertion verbatim in shape. No new test
method — this widens an existing one, so it adds no count to the totals
below.

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition/deletion above,
from the worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **150 tests** (139 → 150, +11: 6 for R12-1, 5 for R12-2).
  `PYTHONPATH=. apps/backend-rag/.venv/bin/python -m pytest
  apps/backend-rag/backend/tests/llm/test_openai_responses_client.py
  --collect-only -q` — 150; full run RC 0, zero failures, 150 passed.
- `scripts/bot/test_build_deid_corpus.py`: **98 tests** (99 → 98, −1:
  R12-4 deletes the R11-2 `os.fdopen`-guilt test; R12-5 widens an
  existing test in place, adding no new one). `--collect-only -q` — 98.
- `scripts/bot/test_wa_blind_bench.py`: **71 tests** (72 → 71, −1: same
  R12-4 deletion; same R12-5 in-place widening). `--collect-only -q` —
  71.
  `python3 -m pytest scripts/bot/test_build_deid_corpus.py
  scripts/bot/test_wa_blind_bench.py -q` from the repo root — **169
  passed** (171 → 169, the only round in this ADR where this combined
  count goes DOWN — declared explicitly, not a regression: R12-4's
  revert removes the two tests that pinned the behavior it undoes), zero
  failures, RC 0.
- `ruff check` on all six fenced `.py` files touched across every round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.

## 20. Thirteenth-round review disposition (Kimi K3 on frozen 648468a98)

A thirteenth review pass from Kimi K3 on the frozen `648468a98` diff (the
commit that closed §19's round-12 disposition, base still the immutable
`6a8ab5180`, fence still exactly 9 files, terna unchanged: `5ef979adb`
client → `92978928c` scripts/bot → `648468a98` ADR) came back RED with 3
LOW findings and 2 MICRO findings, all 5 confirmed reproducible on disk
by the orchestrator's gate — F1 (R13-1) was reproduced EMPIRICALLY,
against this project's own venv, not merely reasoned about. `bot-writer7`
applied all 5 confirmed fixes (R13-1 through R13-5). Transport identical
to every prior round.

**R13-1 (LOW — `math.isfinite` RAISES on an oversized `int` rather than
returning `False`, `openai_responses_client.py`).** §19's R12-1 guarded
`timeout` with `not math.isfinite(timeout)`, assuming `math.isfinite`
always returns a bool. It does not: on an `int` too large to convert to
`float` (`timeout=10**400`), `math.isfinite` itself raises
`OverflowError: int too large to convert to float` — reproduced
empirically by the gate against this project's own venv, not a
theoretical concern. That `OverflowError` escaped the constructor raw,
outside the exception taxonomy the R12-1 `Raises:` docstring block had
just declared complete for this parameter — the same "wrong-type/shape
value bypasses this module's own typed exceptions" class named across
R8-6, R9-4/R10-2, R11-4, R12-1, and R12-2 in prior rounds, one call
deeper than R12-1's own fix reached. Fixed: the `math.isfinite(timeout)`
call is now wrapped in its own `try/except OverflowError:`, treating the
conversion failure as `timeout_is_finite = False` — an `int` too large to
convert to `float` is, for the purposes of this guard, exactly as useless
as `inf` or `nan`, so it resolves to the same `ValueError` rather than a
new exception type. Pinned by
`test_guilt_oversized_int_timeout_raises_value_error_not_overflow_error`
in `TestR12_1TimeoutValidation` (added to the existing R12-1 test class
rather than a new one, since it exercises the same guard the class
already covers).

**R13-2 (LOW — the module docstring's "Covers:" header described the
REJECTED design, not the shipped one, `test_openai_responses_client.py`).**
Line 23 read "a name added to the allowlist is forwarded, others are
dropped" — a partial-filter design. The actual, pinned behavior (see
`test_mixed_allowed_and_unknown_tools_rejects_entire_request`) is
fail-closed on the ENTIRE request the moment it mixes an allowed tool
name with an unrecognised one: nothing is silently forwarded, nothing is
silently dropped, the whole call raises. This line has apparently been
stale since whichever earlier round actually shipped the fail-closed
design (not independently re-dated here — the mismatch is documentation
accuracy, not a behavior change). Fixed: the header line now states
whole-request fail-closed explicitly and cites the pinning test by name.

**R13-3 (LOW — the "never destroys data on the failure path" claim was
unqualified, and the gate DECLARES rather than eliminates the residual,
both `wa_blind_bench.py::_open_private` and
`build_deid_corpus.py::_write_jsonl_private`).** Both docstrings' original
fail-closed claim ("if `os.fchmod` raises... never destroys data on the
failure path") was written before R12-4 existed and is true only for a
failure inside the guarded syscalls (`os.fchmod`/`os.ftruncate`/
`os.lseek`). Since R12-4 reverted `os.fdopen` to sit OUTSIDE that guard
(§19), the claim as written no longer covers the whole function: by the
time `os.fdopen` runs, `os.ftruncate(fd, 0)` has ALREADY zeroed the
pre-existing file on disk, so an `os.fdopen` failure at that point leaves
BOTH a leaked `fd` AND an already-truncated file — not the "no data
destroyed" outcome the unqualified claim implies. **The gate's decision,
recorded here rather than left implicit**: this residual is DECLARED, not
reordered away. Reordering — running `os.fdopen` before `os.ftruncate` so
a failure there could no longer follow a successful truncate — would
introduce a NEW ownership-transfer mechanic (deciding who owns `fd` if
`os.fdopen` succeeds but the subsequent truncate/lseek then fails) at
almost exactly the hazard class R11-2's wrap already demonstrated in
§19's R12-4: the gate's own most recent mechanical fix to this exact
function generated its own new hazard. A prose correction — scoping the
claim to what it actually covers and stating the residual plainly — does
not risk generating a twin gap the way a mechanical reorder would. Fixed:
both docstrings gained a scoped `R13-3 binding correction` paragraph
narrowing the "never destroys data" guarantee to the three guarded
syscalls and stating the fdopen-failure residual verbatim: "one leaked
fd AND the pre-existing file already truncated (the truncate preceded
it)." No code change, no new test — this is a documentation-accuracy
finding about an already-declared-and-accepted residual (§19's R12-4
already accepted the single-fd-leak risk; this finding sharpens what
that residual actually is on this specific writer path).

**R13-4 (MICRO — the empty-string-`api_key` innocence test never
asserted the property its own docstring promises,
`test_openai_responses_client.py`).**
`test_innocence_empty_string_api_key_constructs_normally`'s docstring
says "the existing falsy-is-unavailable semantics are unchanged by this
type check" but the test body only ever asserted `_explicit_api_key ==
""` — never `available`, the property the promise is actually about.
Fixed: added `assert client.available is False`. Verified safe against
ambient environment leakage before adding it: `_resolve_api_key` returns
`self._explicit_api_key` whenever it is not `None`, and an explicit `""`
is not `None`, so `available` reads `bool("")` regardless of whatever
`OPENAI_WA_PROVIDER_API_KEY` happens to be set in the process environment
— no `monkeypatch.delenv` needed for this assertion to be meaningful.

**R13-5 (MICRO — §4 point 2's known-output-item-type list was stale,
missing `reasoning`, this ADR).** §4 point 2 listed the known
`output`-item types as `message`/`function_call`/`refusal` — three, not
the four `_KNOWN_OUTPUT_ITEM_TYPES` actually contains
(`frozenset({"message", "function_call", "refusal", "reasoning"})`).
`reasoning` was added by the P0 fix this same ADR documents in §10/A1
("reasoning item was ignored... with zero validation"), but §4 — written
before that fix — was never revisited. **Correction convention note**:
§4 is a normative section describing this module's LIVE behavior, not a
round-disposition log — the R8-7 "correct forward, never silently edit"
convention applies to round logs (§11 onward), not to normative sections,
so this is corrected DIRECTLY IN §4 itself (inline dated note), not via
an appended paragraph here that leaves §4's prose stale. This paragraph
in §20 exists only to record that the correction happened and why it was
made in place rather than appended.

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **151 tests** (150 → 151, +1 for R13-1). `PYTHONPATH=.
  apps/backend-rag/.venv/bin/python -m pytest
  apps/backend-rag/backend/tests/llm/test_openai_responses_client.py
  --collect-only -q` — 151; full run RC 0, zero failures, 151 passed.
- `scripts/bot/test_build_deid_corpus.py`: **98 tests**, unchanged from
  §19 (R13-3 added no test — documentation-accuracy finding on an
  already-accepted residual). `--collect-only -q` — 98.
- `scripts/bot/test_wa_blind_bench.py`: **71 tests**, unchanged from §19
  for the same reason. `--collect-only -q` — 71.
  `python3 -m pytest scripts/bot/test_build_deid_corpus.py
  scripts/bot/test_wa_blind_bench.py -q` from the repo root — **169
  passed**, unchanged from §19, zero failures, RC 0.
- `ruff check` on all six fenced `.py` files touched across every round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.

## 21. Fourteenth-round review disposition (Kimi K3 on frozen df74de3d0)

A fourteenth review pass from Kimi K3 on the frozen `df74de3d0` diff (the
commit that closed §20's round-13 disposition, base still the immutable
`6a8ab5180`, fence still exactly 9 files, terna unchanged: `b27272d9b`
client → `b17e784ce` scripts/bot → `df74de3d0` ADR) came back RED with 2
LOW findings and 2 MICRO findings, all 4 confirmed reproducible on disk
by the orchestrator's gate. `bot-writer7` applied all 4 confirmed fixes
(R14-1 through R14-4). Transport identical to every prior round.

**R14-1 (LOW — a stale test docstring described the WRONG mechanism as
this repo's slash-separated-citation protection,
`test_build_deid_corpus.py:184`).** `test_slash_separated_regulation_number_not_flagged`'s
docstring said "`/` is deliberately excluded from the separator class" —
true before R8-8, false since: R8-8 INCLUDED `/` in
`_RESIDUAL_SPACED_DIGIT_RUN_RE`'s separator class specifically to close a
slash-separated-NIK hole ("3171/2345/6789/0123"). The real protection for
a citation like "PP 45/2024" or a timestamp like "15/08/2026" is two
independent things downstream of the (now slash-inclusive) regex: the
`_is_date_or_amount_shape` real-calendar exemption (§ noted at R8-8 in
`build_deid_corpus.py` itself), and the regex's own 8-character minimum
span, which a short citation like "45/2024" (7 characters) never reaches
in the first place. The reviewer named the concrete risk of leaving the
docstring wrong: a maintainer who reads only that comment could
"simplify away" the date-shape exemption as dead weight, believing `/`
was never actually scanned — and reopen the exact hole R8-8 closed.
Fixed: the docstring now names both real mechanisms and states the R8-8
history accurately. No code change — this is a documentation-accuracy
finding on already-correct, already-tested behavior.

**R14-2 (LOW — `generate()`'s payload fields were unvalidated, the FIFTH
recurrence of the out-of-taxonomy class, `openai_responses_client.py`).**
`input_text`, `system_prompt`, and `max_output_tokens` flowed straight
into `payload` with no type/range check — siblings R8-6, R9-4/R10-2,
R11-4, R12-1, R12-2 all guarded CONSTRUCTOR arguments; this is the same
class on the PAYLOAD side of `generate()` itself.
`generate(input_text=object())` reached `json.dumps` deep inside httpx's
own request-body encoding and raised a raw `TypeError` — not
`httpx.RequestError`/`httpx.StreamError` (the only types the retry
loop's `except` clause catches), so it escaped the retry loop entirely
and left the method's own `Raises:` block, which presents itself as
exhaustive, incomplete. Fixed: validated BEFORE `payload` is built —
`input_text` must be `str`; `system_prompt` must be `None` or `str` (the
parameter's type hint widened from `str = ""` to `str | None = ""` to
match — `None` is now an explicitly accepted value, not merely an
absence); `max_output_tokens` must be `None` or a positive `int` (`bool`
excluded, the same subtype trap every other numeric guard in this file
already handles) — each raising `ValueError` naming only the offending
type, consistent with `__init__`'s own guard style, with a new `Raises:`
entry. **Reviewer's note on the `tools=` twin, confirmed and recorded
here as instructed**: `tools=` has the identical shape of exposure in
principle — an unhashable or otherwise malformed entry could in theory
reach `json.dumps` unvalidated — but it is UNREACHABLE today:
`_validate_tools_allowlisted` already rejects the entire request the
moment `tools` is non-empty and `ALLOWED_TOOL_NAMES` is itself empty by
default, so every `tools=` call is refused before this point in the
function is ever reached. No parallel guard was added for `tools=` this
round; the reason is recorded both here and as an inline comment at the
new guard's call site, so the gap is legible rather than silently absent.
Pinned by `TestR14_2GeneratePayloadValidation` (8 tests): guilt —
`input_text=object()`, `input_text=b"hi"`, `system_prompt=123`,
`max_output_tokens=True`, `max_output_tokens=0`,
`max_output_tokens=-1`, each asserting ZERO network calls (the fake
transport raises `AssertionError` if reached, matching this file's
established constructor-guard test pattern); innocence — valid values
reach the network, and `system_prompt=None`/`max_output_tokens=None`
explicitly (not just the defaults) also reach the network.

**R14-3 (MICRO — failure counting used an in-band text sentinel on
model-controlled content, `wa_blind_bench.py:767`).** The per-run
failure counter tested `response_text.startswith("[ERROR:")` against
`blind_row["responses"]` — text the underlying model itself controls. A
genuine response that happens to start with that exact literal (a model
quoting an error message back, an adversarial/red-team fixture, ...)
would be miscounted as a failure, and in the limiting case where every
fixture's response happened to start that way, this would flip
`all_failed`/`RAN_ALL_FAILED` on a run that actually succeeded
end-to-end on every candidate. The structural distinction already
existed and was simply not used for counting: `_run_one_fixture` sets
`key_row["attempts"][label]`/`latency_ms[label]` to `None` if and only if
that label's `except` branch ran. Fixed: the counting loop now iterates
`key_row["attempts"].values()` and counts `None` entries, never
inspecting response text. Pinned by
`test_innocence_genuine_response_starting_with_error_marker_not_counted_as_failed`
in `TestR6_6AllFailedStatus` — a genuine (non-erroring) fake response
whose `.text` is literally `"[ERROR: the customer's own message, quoted
back verbatim]"` must still report `errors == 0`, `all_failed is False`,
and `WA_BLIND_BENCH_STATUS=RAN`, never `RAN_ALL_FAILED`.

**R14-4 (MICRO — a `finally` block could mask the exact exception the
test exists to pin, `TestR9_5GetClientTrustEnvRegression`).**
`underlying = client._get_client()` was assigned only inside the `try`
block, while `finally: asyncio.run(underlying.aclose())` referenced it
unconditionally. If `_get_client()` itself raised — precisely the
regression class this test exists to catch, since a future code change
could make `_get_client()` fail outright rather than merely construct
the `httpx.AsyncClient` with a wrong kwarg — `underlying` would never be
bound, and the `finally` clause would raise its own `NameError: name
'underlying' is not defined`, masking the real exception a developer
would need to see to diagnose the actual regression. Fixed:
`underlying = None` before the `try`, and the `finally` clause now
closes only `if underlying is not None`. No new test — this is a
test-harness robustness fix to an existing pinning test, not a new
behavior to pin; the existing test continues to pass.

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **159 tests** (151 → 159, +8 for R14-2; R14-4 modified an existing
  test in place, adding no new one). `PYTHONPATH=.
  apps/backend-rag/.venv/bin/python -m pytest
  apps/backend-rag/backend/tests/llm/test_openai_responses_client.py
  --collect-only -q` — 159; full run RC 0, zero failures, 159 passed.
- `scripts/bot/test_build_deid_corpus.py`: **98 tests**, unchanged from
  §20 (R14-1 corrected a docstring on an existing test, adding no new
  one). `--collect-only -q` — 98.
- `scripts/bot/test_wa_blind_bench.py`: **72 tests** (71 → 72, +1 for
  R14-3). `--collect-only -q` — 72.
  `python3 -m pytest scripts/bot/test_build_deid_corpus.py
  scripts/bot/test_wa_blind_bench.py -q` from the repo root — **170
  passed** (169 → 170, +1), zero failures, RC 0.
- `ruff check` on all six fenced `.py` files touched across every round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.

## 22. Fifteenth-round review disposition (Kimi K3 on frozen efad689e8)

A fifteenth review pass from Kimi K3 on the frozen `efad689e8` diff (the
commit that closed §21's round-14 disposition, base still the immutable
`6a8ab5180`, fence still exactly 9 files, terna unchanged: `f2577d445`
client → `3c8636519` scripts/bot → `efad689e8` ADR) came back RED with
severity climbing: 1 HIGH + 2 MEDIUM + 1 LOW, all 4 confirmed reproducible
on disk by the orchestrator's gate. Unlike prior rounds, all four are NEW
angles on the base code — not residuals already disposed of in an earlier
section. `bot-writer7` applied all 4 confirmed fixes (R15-1 through
R15-4). Transport identical to every prior round.

**R15-1 (HIGH — the amount exemption was context-free, letting a
non-contiguous phone number or bare reference number borrow it,
`build_deid_corpus.py`).** `_is_date_or_amount_shape`'s amount branch
exempted any thousands-grouped digit run under the 13-digit ceiling
regardless of what surrounded it — a confirmed, reproduced scenario: "Call
me on +62.812.345.678" (an 11-digit phone number typed with dots) matches
`_GROUPED_AMOUNT_SHAPE_RE` exactly as readily as a genuine IDR figure and
was silently exempted, letting the phone number survive the residual PII
scan that exists specifically as the backstop for what the primary
Redactor misses; "123.456.789" (a bare 9-digit reference/account number)
has the identical exposure. Fixed: the amount exemption now REQUIRES an
explicit currency/amount marker (`Rp`/`Rp.`/`IDR`/`USD`/`$`/`€`/`juta`/
`miliar`/`ribu`, case-insensitive — the reviewer's list, plus `rupiah`
added because this file's own pre-existing innocence fixtures spell the
word out in full) within a 30-character window before or after the
candidate span; with no marker, the span is now treated as PII-shaped and
the fixture is dropped. **This file's own declared fail-closed cost
model is the explicit justification for choosing "context-dependent",
named directly in the new code comment**: `_TITLECASE_BIGRAM_RE`'s
pre-existing comment already states it for a different heuristic in this
same file — "the cost of a dropped legitimate fixture is zero, the cost
of a leaked name is not" — and the same accounting applies here: a
missed real amount costs a fixture, a missed real phone number costs a
PII leak. `_is_date_or_amount_shape` gained `text`/`span` keyword
parameters (both optional, defaulting to no context — a context-free
direct call now correctly returns `False` for the amount branch, since
"no information available" and "no marker present" resolve to the same
answer); `_has_spaced_digit_pii` now passes `text=text, span=match.span()`
through. Three PRE-EXISTING tests in `TestR6_1PIIScanGaps` (a class from
an earlier round, unrelated to this one) needed their fixture text
updated to include an explicit marker their original text lacked
(`"harga 10,000,000,000"` → `"...IDR"`, etc.) — declared here rather than
silently patched, since removing a marker-free amount's exemption is
exactly the behavior change R15-1 makes, not a test regression. Pinned
by 7 new tests: `test_amount_shape_exempted_only_with_currency_marker_in_context`
(direct-call guilt+innocence), `test_non_contiguous_phone_number_without_currency_marker_flagged`,
`test_bare_grouped_reference_number_without_currency_marker_flagged`
(the reviewer's exact confirmed scenarios, via `_has_spaced_digit_pii`),
`test_grouped_amount_with_explicit_marker_still_exempted_at_eight_digits`
(innocence at the 8-digit threshold), plus the rewritten
`test_is_date_or_amount_shape_direct`.

**R15-2 (MEDIUM — `tools=` was never validated as a `list`, and the
allowlist validator's own double iteration lets a one-shot iterator
bypass it entirely, `openai_responses_client.py`).**
`_validate_tools_allowlisted` iterates its argument TWICE — once to
shape-check each entry (dict, string `name`), then separately in the
`unknown = sorted({...})` comprehension that actually performs the
allowlist check. `generate(tools=iter([{"name": "crm_query"}]))` passes
the first loop (the entry looks valid), then the second iteration sees
an ALREADY-EXHAUSTED iterator — `unknown` comes back empty no matter
what the name actually was, no exception is raised, and the "empty
allowlist rejects everything" invariant this whole adapter's offline
posture depends on is silently defeated. The exhausted iterator then
reaches `payload["tools"]` and `json.dumps` unchecked — a raw `TypeError`
outside this method's documented taxonomy. `tools=object()` (not
iterable at all) fails even earlier, inside
`_validate_tools_allowlisted`'s own first loop, with a different raw
`TypeError`. Fixed: `tools is None or isinstance(tools, list)` validated
in `generate()` BEFORE `_validate_tools_allowlisted` is ever called,
`ValueError` naming only the offending type, new `Raises:` entry — this
is the SIXTH recurrence of the class first named at R8-6. **This
CORRECTS §20's R14-2 paragraph** (not rewritten there, per the R8-7
convention — corrected here): R14-2 reasoned the `tools=` twin exposure
was "unreachable today" purely because an empty allowlist would reject
any non-empty `tools`. That reasoning assumed `_validate_tools_allowlisted`
always actually performs the rejection its own docstring promises —
R15-2 shows that assumption is false for non-`list` iterables
specifically; a malformed `list` (however bad its entries) was never at
risk, only this narrower iterator/iterable case was. Pinned by
`TestR15_2ToolsListTypeValidation` (4 tests): guilt —
`tools=object()` and `tools=iter([...])`, the confirmed bypass shape,
each asserting ZERO network calls; innocence — a real `list` with an
unknown name still raises `OpenAIToolNotAllowedError` unchanged (the new
guard does not intercept the case it was never meant to), and
`tools=None`/`tools=[]` both still reach the network unchanged.

**R15-3 (MEDIUM — the date exemption validates the calendar, never the
NATURE of the data, so a birth date passes as freely as any other date,
`build_deid_corpus.py`).** A date of birth is a genuine calendar date —
"DOB saya 15/08/1990" parses to a real, valid `datetime.date` — and was
exempted by `_is_date_or_amount_shape` exactly like a meeting date or a
regulation's effective date, despite a birth date being itself
identifying PII. No birth-context handling existed anywhere in this file
before this fix (grep-verified RC=1 for `lahir`/`dob`/`born` prior to
this round). Fixed: both date branches (ISO and DMY) now check for a
birth-context marker (`lahir`/`ttl`/`dob`/`date of birth`/`born`,
case-insensitive — `lahir` alone also matches inside the longer phrase
`tanggal lahir`) within a 40-character window BEFORE the span (before
only, not after — unlike R15-1's currency check, a birth date is
typically introduced by a preceding label, not followed by one). A
marker present VETOES the exemption regardless of calendar validity; no
marker leaves the date exemption completely unaffected. Same fail-closed
cost-model justification as R15-1 — a dropped legitimate meeting-date
fixture costs nothing, a leaked birth date does not. Pinned by 3 new
tests: `test_birth_context_vetoes_date_exemption_dob_marker`,
`test_birth_context_vetoes_date_exemption_tanggal_lahir_marker` (guilt,
both the reviewer's exact confirmed scenarios), and
`test_date_without_birth_context_still_exempted` (innocence — an
ordinary meeting date is unaffected).

**R15-4 (LOW — `max_output_tokens`'s type hint contradicted its own
validation and the payload emitted a literal `null`,
`openai_responses_client.py`).** The signature still read
`max_output_tokens: int = 2048` after §20's R14-2 validation (and its
`Raises:` entry) explicitly accepted `None` as a valid value — the hint
and the actual accepted contract disagreed. Separately, the payload
included `"max_output_tokens": max_output_tokens` unconditionally, so
`max_output_tokens=None` sent a literal `"max_output_tokens": null` to
the API on every such call, rather than omitting the key so the API
could apply its own default. Fixed: the hint now reads
`max_output_tokens: int | None = 2048`, and the key is included in
`payload` only when a value is actually given. **Reviewer's note on the
existing test confirmed and acted on**: §20's own R14-2 innocence test
for this exact case
(`test_innocence_none_system_prompt_and_max_output_tokens_reach_the_network`)
asserted only `result.text == "ok"` — vacuous on the specific claim its
own docstring made, since it never inspected the request body and would
have stayed green even sending the literal `null` this fix removes.
Extended (not replaced) to capture the serialized body via the fake
transport and assert `"max_output_tokens" not in captured["body"]` when
`None` is passed — no new test method, this widens the existing one, so
it adds no count to the totals below.

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **163 tests** (159 → 163, +4 for R15-2; R15-4 widened an existing test
  in place, adding no new one). `PYTHONPATH=.
  apps/backend-rag/.venv/bin/python -m pytest
  apps/backend-rag/backend/tests/llm/test_openai_responses_client.py
  --collect-only -q` — 163; full run RC 0, zero failures, 163 passed.
- `scripts/bot/test_build_deid_corpus.py`: **105 tests** (98 → 105, +7
  for R15-1; R15-3 added no new count of its own to THIS file's total
  breakdown since its 3 tests are included in the same +7 — see the
  R15-1/R15-3 paragraphs above for the exact 7-test list). `--collect-
  only -q` — 105.
- `scripts/bot/test_wa_blind_bench.py`: **72 tests**, unchanged from §21
  (no wa_blind_bench.py changes this round). `--collect-only -q` — 72.
  `python3 -m pytest scripts/bot/test_build_deid_corpus.py
  scripts/bot/test_wa_blind_bench.py -q` from the repo root — **177
  passed** (170 → 177, +7), zero failures, RC 0.
- `ruff check` on all six fenced `.py` files touched across every round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.

### R15-1b micro-disposition (orchestrator live-gate on the frozen
round-15 delivery, `f496010b1`)

The gate found one bounded defect IN this section's own R15-1/R15-3 fix
before the next full THAW round started: `_CURRENCY_MARKER_RE` was a bare
substring match, not an entity-anchored one — the same "guard judges the
FORM, not the ENTITY" class this repo's own scar catalogue tracks as a
recurring family (`cicatrix-superscar.md` family #3, "guard-over-match /
substring trapping"). Proven empirically: the everyday Indonesian words
"terpisah" ("separate") and "terpercaya" ("trustworthy") both CONTAIN the
substring "rp" and satisfied the marker with no currency meaning at all —
"nomor terpisah: 62.812.345.678" ("separate number: ...") had "terpisah"
inside the 30-character window, re-opening the amount exemption and
letting the pointed phone number survive the residual scan again. **The
direction matters and is named explicitly**: this over-match is
FAIL-OPEN — a marker that spuriously WIDENS an exemption partially
re-opens the exact HIGH-severity hole R15-1 was written to close, unlike
`_BIRTH_MARKER_RE`'s over-match risk (fail-closed: a spurious veto only
drops an extra fixture, cost zero under this file's own cost model).
Fixed: both patterns are now word-boundary anchored —
`_CURRENCY_MARKER_RE` = `\b(?:rp\.?|idr|usd|juta|miliar|ribu|rupiah)\b|
[$€]` (the two currency symbols deliberately left without `\b`, since
neither is a word character and `\b` only fires at a word/non-word
transition); `_BIRTH_MARKER_RE` = `\b(?:lahir|ttl|dob|date of birth|
born)\b`, anchored for entity-not-form CONSISTENCY across both markers in
this file even though its own over-match direction was never a live hole.
`tanggal lahir` stays covered because `lahir` is a whole word inside it.
Pinned by 2 new tests in `test_build_deid_corpus.py`:
`test_currency_marker_substring_inside_unrelated_word_does_not_reopen_exemption`
(guilt — the orchestrator gate's exact confirmed scenario) and
`test_currency_marker_word_boundary_innocence_cases` (innocence — a
marker with a space, a marker adjacent to the digits with no space at
all — pinning the slice-ends-exactly-at-the-span subtlety noted directly
in `_CURRENCY_MARKER_RE`'s own code comment — and a marker AFTER the
span). `scripts/bot/test_build_deid_corpus.py` count: **105 → 107**
(+2); combined `scripts/bot` run: **177 → 179** (+2), RC 0.
`apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
unaffected, **163**, unchanged.

### R15-1c correction (attribution error in the R15-1b micro-disposition
above, wording-only, no code or test change)

The R15-1b subsection above, as first written, attributed its finding to
"Kimi K3 live-gate on the frozen round-15 delivery" in its own heading,
plus the same phrase repeated in two code comments
(`build_deid_corpus.py:267` and `:308`) and one test docstring
(`test_build_deid_corpus.py:281`). That attribution is FALSE: R15-1b was
found by the **orchestrator's own live-gate** — an independent
verification pass over the frozen round-15 delivery (`f496010b1`), not by
Kimi K3. The round-15 Kimi deliverable this session actually received
carried exactly 4 findings (R15-1 through R15-4, see the section above),
and this defect was not among them. This is the same misattribution class
already arbitrated once in this ADR — see §15's "Orchestrator-mandate
defect" — where a claim's true origin (reviewer vs. orchestrator) was
confused in the written record; here the confusion runs the other
direction (an orchestrator finding credited to the reviewer instead), but
the underlying failure mode is identical: **a record that credits a
finding to a reviewer who never wrote it pollutes the audit trail** a
future review round reads against — Kimi's round-16 pass would see, in
the frozen diff, a "finding" attributed to itself that it never made.
Fixed: all four occurrences (the two code comments, the test docstring,
and this section's own heading) now read "orchestrator live-gate on the
frozen round-15 delivery"; two adjacent "the reviewer's confirmed
scenario" phrases (one in the code comment's sibling test docstring, one
directly above in this section) were corrected to "the orchestrator
gate's confirmed scenario" for the same reason, even though neither
literally said "Kimi" — both still implied the reviewer as source.
`grep -n "Kimi"` across all 9 fenced files, restricted to lines also
matching `R15-1b`, returns zero results after this fix. No code behavior
changed; no test assertions changed; test counts are identical to the
R15-1b subsection above (llm **163** unchanged, `scripts/bot` **179**
unchanged), re-verified this round with the same RC-direct suite runs.
`ruff check` on all six fenced `.py` files: clean.

## 23. Sixteenth-round review disposition (Kimi K3 on frozen fe6d665c5)

A sixteenth review pass from Kimi K3 on the frozen `fe6d665c5` diff (the
commit that closed §22's R15-1c correction, base still the immutable
`6a8ab5180`, fence still exactly 9 files) came back RED with 2 MEDIUM + 2
LOW + 2 MICRO findings, all six confirmed reproducible on disk by the
orchestrator's gate (F1/F2/F3 proven fail-open live with an empirical
probe before any fix was applied). `bot-writer7` applied all six.

**R16-1 (MEDIUM, F1) — ORCHESTRATOR-MANDATE DEFECT, same class as §15's
"Orchestrator-mandate defect", `build_deid_corpus.py`.** The R15-1b
mandate that ordered `\b` word-boundary anchoring on `_BIRTH_MARKER_RE`
analyzed only the exemption-WIDENING direction (`_CURRENCY_MARKER_RE`'s
fail-open risk) and extended the same fix to `_BIRTH_MARKER_RE` "for
entity-not-form consistency," without checking whether a VETO pattern has
the opposite cost-model asymmetry. It does: for a pattern that WIDENS an
exemption, over-matching is fail-open (dangerous) and under-matching is
harmless — anchoring was correctly protective there. For a pattern that
VETOES an exemption, the asymmetry inverts: over-matching only drops an
extra fixture (this file's own declared cost model already treats that as
free), while UNDER-matching is fail-open — a birth-context word the
anchored pattern fails to catch lets a real birth date slip through
exempted. The `\b` anchoring regressed exactly that. Proven empirically:
"kelahiran saya 15/08/1990" — pre-R15-1b, the bare substring "lahir"
matched inside "kelahiran" ("[date of] birth", a noun) and correctly
vetoed the exemption; post-R15-1b, `\blahir\b` requires "lahir" to be a
whole word, which it is not inside "kelahiran" (bounded by word
characters on both sides, no `\b` fires there), so the veto silently
stopped firing and the date came back exempt. Reproduced identically for
"anak itu dilahirkan 15/08/1990" ("the child was born on 15/08/1990").
Fixed: `_BIRTH_MARKER_RE` reverted to a bare substring match (no `\b`),
with a module-level comment stating the general rule as directional, not
"always anchor" or "never anchor" — a pattern that GRANTS/WIDENS an
exemption must be entity-anchored; a pattern that VETOES/NARROWS one may
over-match freely and must not be anchored tighter than the substrings it
needs to catch. This attribution is recorded here honestly per the
mandate's own instruction: the defect was found by **Kimi K3's round-16
review**, not by the orchestrator — the orchestrator's fault was in the
round-15b MANDATE text that ordered the anchoring without the directional
analysis, the same "arbitrate before crediting" discipline §15
established (there the misattribution ran reviewer→orchestrator; here it
is mandate-authorship→code-defect, but the root class — a claim's true
origin not verified before being written into a binding instruction — is
the same). Pinned by `test_birth_marker_substring_inside_kelahiran_vetoes_exemption`
and `test_birth_marker_substring_inside_dilahirkan_vetoes_exemption` (2
tests): guilt — both scenarios above are now flagged, not exempted.

**R16-2 (MEDIUM, F2) — `build_deid_corpus.py`.** The currency-marker
check (R15-1/R15-1b) required a marker only SOMEWHERE within the
`_CURRENCY_CONTEXT_WINDOW_CHARS`-char window, not adjacent to the
candidate span — a marker that genuinely belongs to one amount could
exempt an unrelated span later in the same message. Proven with the
ordinary shape of a real Bali Zero client message, a price and a phone
number in the same sentence: "biaya Rp 2.500.000, hubungi 812.345.678" —
"Rp" (a genuine, correctly word-boundary-anchored marker for the amount
earlier in the sentence) still fell inside the PHONE NUMBER's own 30-char
window and wrongly exempted it too. Fixed: the marker must now be
ADJACENT to the span — the pre-slice must END with a marker (optionally
followed by light whitespace/`:`/`=` before the span itself), or the
post-slice must START with one (optionally preceded by the same light
separators) — via two new regexes,
`_CURRENCY_MARKER_ADJACENT_BEFORE_RE`/`_AFTER_RE`, built from
`_CURRENCY_MARKER_RE`'s own pattern; a plain `.search()` anywhere in the
window is retired. Verified empirically before writing any test (a
consolidated Python script covering all guilt/innocence shapes for R16-1
through R16-3 against the real, already-edited module) that the phone
number in the two-amount scenario is now flagged while the amount itself,
and every prior round's marker-adjacency innocence fixture, remain
correctly exempted — the full pre-existing `test_build_deid_corpus.py`
suite (107 tests, pre-this-round) was re-run against the new adjacency
logic and passed unchanged, confirming no regression on any earlier
round's fixtures. Pinned by
`test_currency_marker_must_be_adjacent_not_merely_co_located_in_window`
(guilt — the two-amount scenario above) and
`test_currency_marker_adjacent_innocence_cases_still_exempted` (4
innocence cases: marker-space-before, marker-no-space-before,
marker-space-after, light-punctuation-before-the-marker-itself).

**R16-3 (LOW, F3) — `build_deid_corpus.py`.** The birth-context veto only
ever checked the window BEFORE the candidate span, on the undocumented
assumption a birth-context label always precedes the date it labels.
Proven false: "15/08/1990 itu tanggal lahir dia" ("15/08/1990, that's his
date of birth") puts the label AFTER the date — the pre-only veto missed
it and the date came back exempt. Fixed: the veto now checks a
`_BIRTH_CONTEXT_WINDOW_CHARS`-char window on BOTH sides of the span
(either side vetoing is enough), using the substring pattern R16-1
restored — same asymmetric-cost reasoning as R16-1: a marker wrongly
found on either side and vetoing an unrelated date still only costs a
dropped fixture, never a leaked one. Pinned by
`test_birth_context_veto_also_applies_when_label_follows_the_date` (1
test): guilt — the scenario above is now flagged.

**R16-4 (LOW, F4) — DECLARE-NOT-FIX (precedent §20), `openai_responses_client.py`.**
Only a tool entry's `name` field is ever validated (by
`_validate_tools_allowlisted`); with `ALLOWED_TOOL_NAMES` populated (a
documented future act), `tools=[{"name": "x", "parameters": object()}]`
would pass every current guard and reach `json.dumps` unvalidated,
raising a raw `TypeError` — the same "a caller-supplied value of the
wrong type/shape bypasses this module's own typed exception taxonomy"
class as R14-2/R15-2, one level deeper into the entry (a per-field gap
rather than a per-name or per-list one). DORMANT today only because the
empty allowlist rejects any non-empty `tools` before this point is ever
reached — not fixed with new code this round, per the mandate's explicit
disposition. Fixed instead: corrected the comments that read as implying
the tools surface is completely guarded once names are validated —
`ALLOWED_TOOL_NAMES`'s own definition now carries a SENTINEL comment
naming the exact gap and requiring whoever populates it to add
entry-field serializability validation as a mandatory companion change,
the `payload["tools"] = tools` site's comment now distinguishes "nothing
to FILTER" (true, all-or-nothing) from "nothing to VALIDATE" (false, only
`name` is checked), and the pre-existing R14-2 "UNREACHABLE today"
paragraph now cross-references the sentinel so the dormancy reads as
scoped-to-today rather than permanent. No new code, no new test — pure
comment corrections, consistent with §20's declare-not-fix disposition
and the no-dedicated-test precedent for pure-text corrections (R8-2,
R8-10).

**R16-5 (MICRO, F5) — `build_deid_corpus.py`.** The comment explaining
why the currency SYMBOLS (`$`/`€`) are left un-anchored claimed `\b`
"would never match adjacent to one anyway" — false, verified empirically:
`re.search(r"\b\$", "total$100")` DOES match (a word character sits
immediately before `$`, exactly the transition `\b` fires on). The real
reason is the opposite of what was claimed: a `\b` immediately before `$`
requires a WORD character directly preceding it, which is exactly what is
MISSING in the common client layout `" $100"` (space before `$` — a
non-word-to-non-word transition, no boundary at all, verified via
`re.search(r"\b\$", " $100")` returning no match) — anchoring `$`/`€`
would BREAK that ordinary case, not merely be redundant for it. Comment
rewritten with the correct mechanics. Pure text correction, no behavior
change, no dedicated test (consistent with R8-2/R8-10 precedent).

**R16-6 (MICRO, F6) — `build_deid_corpus.py`.** The R15-1 comment cited
the fixture text as "budget is 25.000.000 IDR total" — the actual text in
`test_build_deid_corpus.py` (line 176 at the time of this fix) has always
been "budget is 25.000.000 rupiah total". Comment corrected to quote the
real text. Pure text correction, no behavior change, no dedicated test.

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **163 tests, unchanged** (R16-4 was comment-only, no new test).
- `scripts/bot/test_build_deid_corpus.py` + `scripts/bot/test_wa_blind_bench.py`
  combined: **179 → 184** (+5: 2 for R16-1, 1 for R16-3, 2 for R16-2),
  zero failures, RC 0.
- `ruff check` on all six fenced `.py` files touched across every round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.

### R16-2b micro-disposition (Codex gate on the R16-2 adjacency
implementation, found after round 16 (`af7763b21`) had already been
delivered — MICRO-THAW, same pattern as R15-1b on §22)

R16-2's adjacency fix reused `_CURRENCY_MARKER_RE.pattern` verbatim for
the BEFORE-adjacency regex (`_CURRENCY_MARKER_ADJACENT_BEFORE_RE`). That
pattern's `"rp\.?"` branch is `\brp\.?\b` — trailing `\b` included.
Appending the adjacency tail `[ \t:=]*$` to that pattern regressed the
documented "Rp"/"Rp." marker contract specifically on the dotted form:
"Rp. 25.000.000 dana masuk" was wrongly flagged even though both "Rp"
and "Rp." are explicitly documented, contract-listed markers, while "Rp
25.000.000" and "Rp25.000.000" kept working. Mechanism, both failure
paths: (a) if the optional `.` is consumed by the match, the trailing
`\b` needs a word/non-word transition between `.` and the character
after it — but `.` and a following space are BOTH non-word characters,
so no boundary fires there and the match attempt fails; (b) if the
engine instead stops before consuming the `.` (matching only "rp",
where the p→. transition IS a valid boundary), the leftover `.` is not
itself accepted by `[ \t:=]*` and the `$` anchor is never reached —
also fails. Direction: fail-closed (a legitimate fixture wrongly
flagged, not a PII leak), but still a real regression against the
contract this round's own R16-2 fix documented.

Fixed: the BEFORE regex now uses its own alternation,
`_CURRENCY_MARKER_ADJACENT_BEFORE_ALT`, where the `"rp\.?"` branch drops
its own trailing `\b` — safe to drop specifically because the adjacency
tail `[ \t:=]*$` already enforces what may follow the marker (only
light separators up to the span itself), which is a STRICTER
right-boundary constraint than a bare `\b` would provide, not a looser
one. Verified empirically before any edit and again before commit: `"
harp "`/`" corp "`/`" rpz"` (a marker substring embedded in or run into
another word, with no legitimate adjacency) still correctly fail to
match, since the leading `\b` before "rp" (unchanged, still required)
rejects a preceding word character, and for the `" rpz"` shape the tail
constraint itself rejects the trailing non-separator character. The
AFTER regex (`_CURRENCY_MARKER_ADJACENT_AFTER_RE`) is deliberately left
UNCHANGED, still built from `_CURRENCY_MARKER_RE.pattern` verbatim — the
same relaxation applied there would be a genuine widening rather than a
tightening: the AFTER regex only requires a PREFIX match at the start of
the post-context, with nothing else in the pattern constraining what
follows "rp" — dropping its trailing `\b` there would let a marker
substring run into an unrelated following word (e.g. a hypothetical
`"rpxyz"` right after a span) match spuriously. No "Rp." AFTER-the-span
case is documented or required by any round's mandate, so no matching
change was made on that side — the two directions are not symmetric
here and were not treated as if they were.

Pinned by `test_currency_marker_with_period_stays_adjacent_and_exempt`
(1 test): innocence — `"Rp. 25.000.000 dana masuk"`, `"Rp 25.000.000"`,
`"Rp25.000.000"`, `"harga 25.000.000 rupiah"` all stay exempt; guilt —
the R16-2 two-amount scenario (`"biaya Rp 2.500.000, hubungi
812.345.678"`) and the R15-1b "terpisah" substring scenario (`"nomor
terpisah: 62.812.345.678"`) both still flag correctly, re-run in the
same test to confirm the addendum's tightening did not collaterally
loosen either prior round's guilt case.

Final measured test counts, this micro-round (re-collected fresh from
the worktree on disk immediately before recomposition, superseding the
counts in the bullet list above):

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  unaffected, **163**, unchanged.
- `scripts/bot/test_build_deid_corpus.py` + `scripts/bot/test_wa_blind_bench.py`
  combined: **184 → 185** (+1), zero failures, RC 0.
- `ruff check` on all six fenced `.py` files: clean.

## 24. Seventeenth-round review disposition (Kimi K3 on frozen c1f2f1da8)

A seventeenth review pass from Kimi K3 on the frozen `c1f2f1da8` diff (the
commit that closed §23's R16-2b micro-disposition, base still the
immutable `6a8ab5180`, fence still exactly 9 files) came back RED with 2
MEDIUM + 1 LOW, all three confirmed reproducible on disk by the
orchestrator's gate with a live empirical probe. `bot-writer7` applied
all three, all on `build_deid_corpus.py`.

**R17-1 (MEDIUM) — supersedes the R16-2b "AFTER unchanged" defense (§23),
same honest-correction convention as §19.** §23's R16-2b fix correctly
patched the BEFORE-side period-consumption bug, but its closing paragraph
declared the AFTER regex (`_CURRENCY_MARKER_ADJACENT_AFTER_RE`, still
built verbatim from `_CURRENCY_MARKER_RE.pattern`) safely UNCHANGED on
the reasoning that "the AFTER regex only requires a PREFIX match, with
nothing constraining what follows 'rp'." That reasoning was wrong, not
merely unproven — "nothing constrains what follows" is exactly the
problem, not a safety argument: a prefix match can stop at "rp" (the p→.
or p→space transition both satisfy `\b`) with nothing requiring the
match to extend further, so an entirely unrelated word starting with
"rp" right after a span could satisfy the AFTER check. Proven
empirically: "hubungi 812.345.678 rp. palsu" and "hubungi 812.345.678 rp
palsu" ("palsu" = "fake/counterfeit") both wrongly exempted the phone
number — the exact fail-open class R16-2 exists to close, re-opened on
the side §23 declared safe. Fixed structurally, not by patching the
period mechanics again: `rp\.?` is removed from the AFTER alternation
entirely — in Indonesian, currency stated AFTER a number is always
spelled out ("rupiah"/"juta"/"miliar"/"ribu"/"IDR"/"USD"), never a bare
"N rp", so the AFTER pattern needed no bare-"rp" branch in the first
place; the AFTER alternation is now
`(?:idr|usd|juta|miliar|ribu|rupiah)\b|[$€]`, still fully `\b`-anchored
(this pattern GRANTS an exemption, so it stays entity-anchored per the
R16-1 directional rule). The BEFORE regex and its own `rp\.?` branch are
UNAFFECTED — "Rp"/"Rp." legitimately precede an amount in Indonesian.
Pinned by `test_rp_removed_from_after_side_no_longer_exempts_unrelated_span`
(1 test): guilt — both scenarios above now flag; innocence — the real
AFTER-side markers ("rupiah", "idr") still exempt.

**R17-2 (MEDIUM) — `build_deid_corpus.py`.** `_BIRTH_MARKER_RE`'s
vocabulary was incomplete: "birthday"/"b-day" (English) and "ulang
tahun"/"ultah" (Indonesian, both meaning "birthday") contain none of the
prior tokens (`lahir|ttl|dob|date of birth|born`). Proven: "my birthday
is 15/08/1990", "ultah saya 15/08/1990", and "ulang tahun 15/08/1990" all
came back exempt. Fixed under the R16-1 directional rule (a veto pattern
may over-match freely, so widening is always safe): "date of birth" is
dropped as its own alternative and replaced by the more general "birth"
— a strict widening, since "birth" is already a substring of "date of
birth"/"birthday"/"birthdate" (verified: "date of birth" still matches,
via "birth"); "dob" is kept as its own token since it does not contain
"birth" as a substring (it is an acronym, not a shortened spelling).
"ulang tahun"/"ultah"/"b-day" added as new literal alternatives — final
pattern `r"lahir|ttl|dob|birth|born|ulang tahun|ultah|b-day"`. Pinned by
`test_birth_marker_vocabulary_covers_birthday_and_indonesian_synonyms`
(1 test): guilt — the three scenarios above all flag; innocence — an
ordinary meeting date is unaffected.

**R17-3 (LOW) — `build_deid_corpus.py`.** `_ADDRESS_MARKER_RE` required
`\s+` immediately after the marker word — a common WA-typing style that
skips the space after a period ("jl.sunset road", "gang.mawar no 3")
escaped Scan B entirely (proven: both passed undetected). Fixed: the
literal dot moved out of the "Jl\." alternative and became its own
optional suffix on the whole alternation (`\.?`), and the mandatory
`\s+` became optional `\s*` — a widening on a DETECTOR pattern (narrows
what counts as PII-shaped address text further, grants nothing), so
over-matching is fail-closed and free under the same directional rule.
Declared bonus: "jln mawar" (a further-abbreviated but real Indonesian
address marker, "jln" being a common abbreviation of "jalan") now also
matches via "Jl" + `\S+` consuming "n mawar" — in-scope for what this
marker class is trying to catch, not an unrelated side effect. Declared
residual, out of this round's scope, verified but not fixed: dropping the
mandatory `\s+` also lets "Jalan" match as a prefix of the unrelated
Indonesian verb "jalankan" ("run/execute") with no address meaning —
verified empirically
(`_ADDRESS_MARKER_RE.search("kita mau jalankan program ini")` is
truthy); same cost model as every other over-match on this detector, a
lost fixture, never a leaked one. Pinned by
`test_no_space_wa_typing_style_address_marker_flagged` (1 test): guilt —
both no-space scenarios above are now flagged via `_independent_pii_scan`
(`"address_marker"` in findings); pre-existing spaced-form innocence
already covered by `test_lowercase_address_marker_flagged`/
`test_mixed_case_honorific_and_address_flagged`, both re-run this round
and unaffected.

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **163 tests, unchanged** (no fenced client file touched this round).
- `scripts/bot/test_build_deid_corpus.py` + `scripts/bot/test_wa_blind_bench.py`
  combined: **185 → 188** (+3: 1 each for R17-1/R17-2/R17-3), zero
  failures, RC 0.
- `ruff check` on all six fenced `.py` files touched across every round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.

## 25. Eighteenth-round review disposition (Kimi K3 on frozen 4e7a3787c)

An eighteenth review pass from Kimi K3 on the frozen `4e7a3787c` diff (the
commit that closed §24's THAW round 17, base still the immutable
`6a8ab5180`, fence still exactly 9 files) came back RED with 3 MEDIUM + 1
LOW + 1 MICRO. F1-F4 were confirmed reproducible on disk by the
orchestrator's gate with a live empirical probe; F5 was disposed
DECLARE-NOT-FIX (a documentation correction, not a code defect). All five
findings are on `build_deid_corpus.py`. `bot-writer7` applied F1-F4 and
wrote F5's declaration.

**R18-1 (MEDIUM) — `_HONORIFIC_NAME_RE`, dot-attached WA-typing shortcut,
plus an ADDENDUM (Codex pre-freeze gate) and a discovered pre-existing
over-match bug (disclosed in full below, not part of the mandate).** A
real WA-typing shortcut — the dot-elided, no-space honorific ("ibu.siti
rahayu", "pak.budi santoso datang") — passed both scans entirely. The
mandate's own premise (that the name-arm's `[A-Z]` rejects lowercase, so
a separator-only fix would suffice) was verified FALSE before
implementing: the pre-round-18 pattern compiled with a GLOBAL
`re.IGNORECASE`, and Python's `re.IGNORECASE` loosens ALL character
classes in a compiled pattern, not just literal alternation words —
`_HONORIFIC_NAME_RE.search("makasih pak sudah bantu")` already returned
`True` on the unmodified module, an unnoticed over-match dating back to
the G2 fix's original authorship. A separator-only fix would have
satisfied the mandate's guilt cases but failed its innocence
requirement, since "makasih pak sudah bantu" already (wrongly) matched
for this unrelated, pre-existing reason. Fixed with two branches: (a) a
new dot-attached branch, `\.\s*[A-Za-z][a-zA-Z'’-]{2,}`, allows a
lowercase name only when the literal dot is present — the dot-attachment
itself is the name-elision signal, since nobody writes "pak.sudah" to
mean the ordinary word; (b) the pre-existing spaced branch is made
genuinely case-sensitive on the name-arm via Python's scoped inline flag
`(?i:...)` wrapped ONLY around the marker-word alternation — the global
`re.IGNORECASE` compile flag is dropped entirely, so `[A-Z]` now means
what it always claimed to mean, while marker-word case-insensitivity
(the G2 fix's actual, still-valid intent) is fully preserved.
**ADDENDUM (Codex pre-freeze gate on this round's own implementation,
integrated before commit):** the `Sig\.`/`Sig\.ra` alternatives baked
their own literal dot into the marker token, which combined with the new
dot-attached branch's own required leading `.` would have made
"Sig.Rossi" need two literal dots to match (none exist) — losing that
shape. Fixed by moving the dot OUT of the marker token so it becomes the
branch's own separator: `Sig(?:\.ra)?` (bare "Sig" matches abbreviated
"Signore"; the optional `.ra` suffix covers "Sig.ra" = "Signora").
Verified empirically, including the backtracking edge cases: "Sig.Rossi"
matches via bare "Sig" plus the dot-attached branch consuming ".Rossi";
"Sig.ra Rossi" matches via the full "Sig.ra" token (tried first, greedy)
plus the spaced branch on " Rossi" — not mis-parsed as "Sig" + "." +
"ra" (the dot-attached branch's own 3-character minimum rejects "ra"
before reaching " Rossi"); "Sig.raffaele" still matches via backtracking
to bare "Sig" once the greedy "Sig.ra"-then-spaced path fails (no
whitespace follows). **Disclosed consequence, made autonomously and
reported transparently here:** the genuine case-sensitivity fix in (b)
above is a real, verified regression against 2 pre-existing PASSING
tests that had exploited the same accidental global-IGNORECASE
over-match — `test_lowercase_honorific_name_flagged` and
`test_mixed_case_honorific_and_address_flagged`, both in
`TestG2CaseInsensitiveScanB`. Both fixtures are fixed by capitalizing
only the name portion (`"ibu siti rahayu"` → `"ibu Siti rahayu"`,
`"Ibu siti tinggal"` → `"Ibu Siti tinggal"`), preserving lowercase on the
marker word so each test still exercises marker-word case-insensitivity
(the G2 fix's actual intent), with explicit docstrings in both tests
citing this round and explaining why. Pinned by 5 new tests in
`TestR18_1DotAttachedHonorificAndSigNormalization`: guilt — the two
dot-attached fixtures above; innocence —
`"makasih pak sudah bantu"`/`"bu, besok ya"` (proving the newly-closed
over-match hole); existing-preserved — `"ke Ibu. Siti Rahayu"`; ADDENDUM
guilt — `"Sig.Rossi chiede update"`; ADDENDUM form-innocence —
`"Sig.ra Rossi"` (long form does not regress).

**R18-2 (MEDIUM) — `_BIRTH_MARKER_RE`, remaining vocabulary gaps.**
Still-missing tokens let a birth date slip past the birth-context veto
in `_is_date_or_amount_shape`: "bday" (no hyphen, distinct spelling from
the already-covered "b-day" — neither contains the other as a
substring), "d.o.b." (with periods, distinct literal from the
already-covered "dob"), and the Italian birth vocabulary
("compleanno" = "birthday", "nascita" = "birth" as in "data di nascita",
"nato"/"nata" = "born", masculine/feminine) — this corpus's
`_LANG_MARKERS` already includes an `it` bucket, so Italian is in-scope.
Proven: "my bday 15/08/1990", "d.o.b. 15/08/1990", "compleanno
15/08/1990", "nato il 15/08/1990" all came back exempt before this fix.
Fixed under the same R16-1 directional rule (a veto pattern may
over-match freely): all six tokens added to the alternation, final
pattern
`r"lahir|ttl|dob|d\.o\.b|birth|born|bday|b-day|ulang tahun|ultah|compleanno|nascita|nato|nata"`.
Declared, not a defect: "nato" as a bare substring will also match
inside unrelated Italian words containing it (e.g. "coordinato") — free
under the directional rule, since over-matching this veto only costs a
dropped fixture, never a leaked one. Pinned by 2 new tests in
`TestR18_2ExtendedBirthMarkerVocabulary`: guilt — all four scenarios
above now veto the exemption; innocence — an ordinary meeting date with
no birth marker nearby stays exempt.

**R18-3 (MEDIUM) — `_ADDRESS_MARKER_RE`, remaining vocabulary gaps.**
Standard Indonesian address abbreviations were still missing: "Gg." (for
"Gang"), "Komp."/"Perum." (for "Komplek"/"Perumahan"), and several
street/complex-type words never covered at all ("Dusun", "Kampung",
"Ruko", "Blok"). Proven: "alamat: Gg. Melati II No. 4, Denpasar" passed
both scans — not caught here (no "Gg" token existed) and not caught by
`_TITLECASE_BIGRAM_RE` either, because "Melati II" has no lowercase
letters in "II" for that heuristic's bigram shape to recognize. Fixed:
alternation extended to
`Jl|Jalan|Gg|Gang|Komp|Komplek|Perum|Perumahan|Banjar|Dusun|Kampung|Ruko|Blok`,
same `\.?\s*\S+` suffix — a DETECTOR widening, fail-closed and free
under the same directional rule. Declared residual, out of this round's
scope: "Blok" as a marker will over-match ordinary uses like "blok
timur" ("east block", a compass direction) — same cost model as every
other over-match on this detector. Pinned by 2 new tests in
`TestR18_3ExtendedAddressMarkerVocabulary`: guilt — both the
full-punctuation and lowercase-no-space "Gg." scenarios above now flag
`"address_marker"` via `_independent_pii_scan`.

**R18-4 (LOW) — dead-code removal, `_CURRENCY_MARKER_RE`.** Censused: 7
prose/docstring references to `_CURRENCY_MARKER_RE`, zero executable
call-sites — every live consumer had already moved to the independent
`_CURRENCY_MARKER_ADJACENT_BEFORE_ALT`/`_AFTER_ALT` alternations
(R16-2/R16-2b/R17-1). A defined-but-unreferenced symbol left in place is
a liability, not neutral: both R16-2b and R17-1's regressions stemmed
from reusing `.pattern` off this exact symbol. Removed the definition,
replaced with a comment documenting the removal rationale and the
regression history; the 4 remaining historical prose references (the
R16-2b comment block, twice in the R16-1/`_BIRTH_MARKER_RE` block, and
`_is_date_or_amount_shape`'s docstring) updated to cite "the
since-removed `_CURRENCY_MARKER_RE`" and the live authorities by name.
No test needed — a pure removal of unreferenced code with no behavior
change, verified by the unchanged pass/fail status of every other test
in the suite.

**R18-5 (MICRO, DECLARE-NOT-FIX) — `\n` adjacency edge case,
`_CURRENCY_MARKER_ADJACENT_BEFORE_RE`.** Disposed declare-not-fix per the
review's own verdict: documented, not code-changed. In verifying the
finding before writing its declaration (anti-hallucination discipline —
nothing here is asserted without having run it in this turn), the
mandate's own literal example, `"totalnya Rp\n2.500.000"`, was found NOT
to actually reproduce the described adjacency-loss bug: Python's `$`
anchor has a special case that matches immediately before a trailing
`\n` that is the string's own last character, so
`_CURRENCY_MARKER_ADJACENT_BEFORE_RE.search("totalnya Rp\n")` returns
`True` even though the separator class `[ \t:=]` excludes `\n` itself. A
more general, realistic shape — anything following the newline before
the digits — does reproduce the bug: verified
`_has_spaced_digit_pii("totalnya Rp\n 25.000.000")` returns `True`
(wrongly flagged). The code comment records this precise, empirically-
verified nuance (the mandate's exact example does not reproduce; the
corrected variant does) rather than restating the mandate's claim as
fact — same `$`-precedent already established at R8-5. No code change
and no new test, consistent with this round's declare-not-fix
disposition.

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **163 tests, unchanged** (no fenced client file touched this round).
- `scripts/bot/test_build_deid_corpus.py` + `scripts/bot/test_wa_blind_bench.py`
  combined: **188 → 197** (+9: 5 for R18-1 including its ADDENDUM, 2 for
  R18-2, 2 for R18-3; R18-4/R18-5 need no dedicated test per their own
  dispositions above), zero failures, RC 0. Also confirmed: the 2
  pre-existing tests corrected as a disclosed side effect of R18-1
  (`test_lowercase_honorific_name_flagged`,
  `test_mixed_case_honorific_and_address_flagged`) pass cleanly with
  their corrected fixtures.
- `ruff check` on all six fenced `.py` files touched across every round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.

### R18-1b micro-disposition (orchestrator live-gate on the frozen
round-18 delivery — attribution: the gate, not Kimi — MICRO-THAW, same
pattern as R15-1b on §22 and R16-2b on §23)

R18-1(b)'s scoped case-sensitivity fix (§25 above) correctly closed the
marker-followed-by-ordinary-lowercase-word over-match
(`_HONORIFIC_NAME_RE` used to fire on ANY honorific + ANY lowercase
word) but, as an unnamed side effect, also closed the spaced-lowercase
NAME case entirely — the single most common real WA shape, honorific +
space + an all-lowercase name with no dot ("ibu siti rahayu", "pak budi
santoso datang"). Proven by the gate: `_independent_pii_scan("tolong ke
ibu siti rahayu besok")` returned `[]` under R18-1's delivered fix,
though the same text matched before it (via the pre-R18-1 accidental
global-IGNORECASE over-match). This file's own cost model — "a dropped
fixture costs zero, a leaked name does not" — means the pre-R18-1
behavior was on the SAFE side of this specific trade; R18-1 traded that
safety for corpus utility (the "makasih pak sudah bantu" innocence
requirement) without naming the fail-open residual it opened.

Honesty note on the root cause, stated plainly rather than smoothed
over: the innocence requirement that drove R18-1's design was MY OWN
(the orchestrator's) mandate requirement for that round — and it was
correct for utility, a detector that fires on every honorific followed
by any ordinary word is useless. But the right resolution was never
"flag every honorific+word" (the pre-R18-1, useless-detector behavior)
nor "only flag titlecase/dot-attached" (R18-1's new, name-losing
behavior) — it needed a THIRD branch with a STOPWORD GUARD, which
inverts the direction of the residual back onto this file's safe side:
an unrecognized word after the marker (names are, by definition, not
members of a short closed vocabulary) FLAGS — cost is a dropped
fixture, free under the cost model; only a marker followed by a KNOWN
common non-name word is exempted — cost is an over-drop, also free.

Fixed: a new `_HONORIFIC_SPACED_LOWERCASE_CANDIDATE_RE` (honorific +
optional dot + `\s+` + a captured all-lowercase word) plus
`_has_honorific_spaced_lowercase_name`, which rejects the match only
when the captured word is a member of `_HONORIFIC_NON_NAME_STOPWORDS` —
a short closed frozenset of common Indonesian particles (`sudah`,
`saja`, `ya`, `juga`, `bisa`, `mau`, `tolong`, `terima`, `kasih`,
`makasih`, `minta`, `boleh`, `nanti`, `besok`, `ini`, `itu`, `yang`,
`dulu`, `dong`, `deh`, `kok`, `sih`, `belum`, `lagi`, `aja`, `gak`,
`tidak`, `jangan`, `harus`, `sedang`, `masih`, `baru`, `mohon`,
`silakan`). Implemented as plain code around the match rather than
folded into the regex itself, per the mandate's own guidance — a
pattern expressing "match this alternative UNLESS the captured group is
one of N literal words" is a much harder read than a frozenset
membership check — verified empirically before committing, not assumed:
guilt — `"tolong ke ibu siti rahayu besok"` and `"pak budi santoso
datang"` now flag; innocence — `"makasih pak sudah bantu"` (guarded by
"sudah"), `"pak tolong kirim"` (guarded by "tolong", a DIFFERENT
stopword than the guilt fixture's, proving the guard checks the actual
captured word rather than scanning the sentence for any stopword
anywhere), and `"bu, besok ya"` (unflagged for a structural reason
independent of the stoplist — the comma breaks the marker-then-space
adjacency the candidate regex requires) all stay unflagged. Every
guilt/innocence case R18-1 and its Sig ADDENDUM already pinned re-run
identically (the new branch is purely additive, OR'd into the existing
check).

Declared residual, NOT closed by this fix (inherent to any
stopword-based approach, out of this micro-round's scope): a name that
happens to be spelled identically to one of these stopwords (e.g. an
Indonesian given name coinciding with a common particle) still
escapes — accepted, since disambiguating a name from an
identically-spelled function word needs more than a fixed short list
can ever provide.

Pinned by 4 new tests in `TestR18_1bSpacedLowercaseNameStopwordGuard`:
guilt (the two spaced-lowercase-name fixtures above), innocence-by-
stopword (two DIFFERENT stopwords across two fixtures), innocence-by-
structure (the comma case), and an explicit regression test re-running
every R18-1/ADDENDUM guilt case byte-for-byte.

Final measured test counts, this micro-round (re-collected fresh from
the worktree on disk immediately before recomposition, superseding the
counts in the bullet list above):

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  unaffected, **163**, unchanged.
- `scripts/bot/test_build_deid_corpus.py` + `scripts/bot/test_wa_blind_bench.py`
  combined: **197 → 201** (+4), zero failures, RC 0.
- `ruff check` on all six fenced `.py` files: clean.

## 26. Nineteenth-round review disposition (Kimi K3 on frozen 037d697c9)

A nineteenth review pass from Kimi K3 on the frozen `037d697c9` diff (the
commit that closed §25's R18-1b micro-disposition, base still the
immutable `6a8ab5180`, fence still exactly 9 files) came back RED with 1
HIGH + 1 MEDIUM + 2 LOW + 1 MICRO, all five confirmed reproducible on
disk by the orchestrator's gate with a live empirical probe (F1/F2/F3
directly; F5 was line-wrapped in the original claim and found by hunting
variants). Four findings are on `build_deid_corpus.py`, one (F5) is on
`openai_responses_client.py`.

**R19-1 (HIGH) — `_has_honorific_spaced_lowercase_name`, single-word
stopword guard bridged over by a preceding stopword.** §25's R18-1b
guard judged ONLY the first word after the honorific — a single
bridging stopword shields the real name pair behind it entirely.
Proven: "pak minta budi santoso datang" and "ibu tolong siti rahayu"
both passed BOTH scans (the checked word — "minta"/"tolong" — is in the
stoplist, and the guard stopped there without ever looking at "budi
santoso"/"siti rahayu" behind it) — a fail-open regression in the very
fix meant to close a fail-open hole. Fixed under an ADJACENT-PAIR rule:
look at the next ~4 words after the honorific (any case) and flag if
any TWO CONSECUTIVE words in that window are BOTH lowercase AND BOTH
outside the stoplist — Indonesian names characteristically come in
pairs (given name + family name), so requiring adjacency (not just two
non-stopwords anywhere in the window) keeps the detector anchored to
that shape. `_HONORIFIC_SPACED_LOWERCASE_CANDIDATE_RE`/single-word logic
replaced with `_HONORIFIC_MARKER_ONLY_RE` (marker-only match) plus a
pairwise scan over the next `_HONORIFIC_FOLLOWING_WORDS_WINDOW` (4)
tokens. Verified empirically against every mandate case: the two guilt
scenarios now flag; "makasih pak sudah bantu" and "pak tolong kirim"
stay unflagged (their only candidate pair has a stopword on one side);
every pre-existing R18-1b guilt case ("pak budi santoso datang", "tolong
ke ibu siti rahayu besok") is unaffected, since their name pair was
already adjacent to the marker. **Declared residual, narrower than the
hole this round closes**: a SINGLE lowercase name word followed by a
stopword or the end of the sentence ("pak budi ya") still escapes, since
no second non-stopword word is ever adjacent to it — inherent to any
positional-pair heuristic, out of this round's scope. Pinned by 4 new
tests in `TestR19_1HonorificAdjacentPairStopwordGuard`: guilt (both
bridging-stopword scenarios), innocence (no adjacent pair), declared
residual (single name before a stopword), regression (pre-existing
R18-1b guilt cases re-run identically).

**R19-2 (MEDIUM) — `_ADDRESS_MARKER_RE`, short markers as unanchored
word prefixes.** The short markers ("Komp", "Blok", "Gang", …) were
unanchored PREFIXES of ordinary Indonesian words with no address
meaning — "komplain" ("complaint"), "blokir" ("block/ban"), "gangguan"
("disturbance"), "kompensasi" ("compensation") all matched via a bare
prefix, proven empirically. Unlike prior over-matches this file's
directional rule accepted as free (a detector may over-match — cost is
a dropped fixture), this class is different: at corpus scale, ordinary
business vocabulary this common would starve the Indonesian-language
bucket rather than merely drop occasional fixtures — Scan B feeds a
corpus-ELIGIBILITY gate, so systematically excluding a whole register of
common words is a coverage bias, not a free cost, and was worth
tightening. Fixed: a zero-width lookahead `(?=[\s.])` right after the
alternation requires the marker to be followed by whitespace or a
literal dot — a genuine word/token boundary — before the existing
`\.?\s*\S+` tail runs; this is a NARROWING (grants nothing new), so no
conflict with the directional rule. `Jln` added as its own explicit
alternative, since the R17-3 "jln mawar" bonus used to work only via
"Jl" matching as an unanchored prefix of "jln" — the new lookahead would
otherwise silently lose that shape. Verified empirically: guilt (now NOT
flagged) — all four scenarios above; innocence-regression (still
flagged) — "Gg. Melati II No. 4", "jl.sunset road", "gg.mawar no 3", "Jl
Sunset", and "jln mawar" (now via the explicit token). **Measured bonus,
not required by the mandate:** the R17-3-declared "jalankan"
("run/execute") false positive is also incidentally closed by this same
lookahead — the character right after "Jalan" in "jalankan" ("k") is
neither whitespace nor a dot. The R18-3-declared "blok timur" residual
is UNCHANGED (still over-matches), confirmed empirically — that shape
has a genuine space after the marker, exactly what the lookahead is
designed to accept, so tightening the prefix boundary does not touch a
whole-word-followed-by-space over-match. Declared residual of this
tightening: a no-separator run like "KompGriya" no longer matches —
never a real WA-typing address form to begin with. Pinned by 4 new
tests in `TestR19_2AddressMarkerPrefixBoundary`: guilt (all four
ordinary-word scenarios), innocence-regression (five genuine markers),
the `Jln` explicit-token case, and the incidental "jalankan" closure.

**R19-3 (LOW) — dot-attached honorific branch missing the stopword
guard.** The dot-attached branch (previously living inside
`_HONORIFIC_NAME_RE`) never carried the R18-1b/R19-1 stopword guard its
spaced-lowercase sibling has — an inconsistency between two branches of
the same class. Proven: "makasih pak.sudah bantu" and "bu.tolong kirim"
both flagged, while the spaced equivalents (guarded) did not. Fixed:
the branch is extracted into its own
`_HONORIFIC_DOT_ATTACHED_CANDIDATE_RE` + `_has_honorific_dot_attached_name`
(placed after the stopword frozenset both it and the R19-1 pair-guard
share), and the captured word is checked against the same
`_HONORIFIC_NON_NAME_STOPWORDS` frozenset. `_HONORIFIC_NAME_RE` itself
is now the spaced-TITLECASE branch only; the historical G2/R18-1/
ADDENDUM prose describing its prior combined form is left intact as
narration of that PRIOR state, per this file's own convention for
correcting prior-round prose, with a new paragraph noting the
extraction. Verified empirically: "ibu.siti rahayu" (R18-1 guilt) and
"Sig.Rossi"/"Sig.ra Rossi"/"Sig.raffaele" (ADDENDUM guilt) all still
flag; "makasih pak.sudah bantu" and "bu.tolong kirim" no longer do.
Pinned by 2 new tests in `TestR19_3DotAttachedHonorificStopwordGuard`:
guilt-no-longer-flagged (both stopword-after-dot scenarios), regression
(every R18-1/ADDENDUM dot-attached guilt case re-run identically).

**R19-4 (LOW) — stale `_CURRENCY_MARKER_RE` pointers in the test file,
plus a third instance found while fixing the two named.** §24's R18-4
claimed "the 4 remaining historical prose references … updated" but
that sweep covered `build_deid_corpus.py` only — `test_build_deid_corpus.py`
still carried two live-looking "see `_CURRENCY_MARKER_RE`"/"noted in
`_CURRENCY_MARKER_RE`'s own comment" pointers to the deleted symbol, at
the docstrings for `test_is_date_or_amount_shape_direct` and
`test_currency_marker_word_boundary_innocence_cases`. Both re-pointed to
the live authorities, `_CURRENCY_MARKER_ADJACENT_BEFORE_ALT`/`_AFTER_ALT`
(and, for the second, `_CURRENCY_MARKER_ADJACENT_BEFORE_RE`'s own
comment specifically, since that is where the cited slice-adjacency
detail actually lives now). **Disclosed addendum, not named by the
mandate:** while fixing the two cited locations, a THIRD identical
live-looking pointer was found at `test_a_legitimate_large_amount_still_exempted`'s
docstring ("the amount exemption is now context-dependent (see
`_CURRENCY_MARKER_RE`)") — same defect class, same fix applied. The
historical "used to be a …"/"reusing `_CURRENCY_MARKER_RE.pattern`
verbatim" narrations elsewhere in the test file (describing PAST states
at R15-1/R16-2b) are left untouched, per the mandate's own instruction.
No dedicated test — pure prose correction, no behavior change,
consistent with the R8-2/R8-10/R18-4 precedent for comment-only fixes.

**R19-5 (MICRO) — `_parse_responses_payload`'s docstring, third stale
instance of an already-corrected claim.** The docstring still read "a
`reasoning` output item … is recognised and silently ignored — none of
its fields are ever read", while the parsing loop at (what were)
lines 839/844 reads `item.get("id")`/`item.get("summary")` for
isinstance-only type checks — the same correction already made at
`_KNOWN_OUTPUT_ITEM_TYPES`'s own comment and at the parsing loop's own
comment, both of which explicitly flag their own PRIOR draft as having
made this exact false claim. This docstring was the one place the
correction had not yet propagated. Aligned to match: fields are read
into local variables for an isinstance() check only; no value is ever
interpolated into an `LLMResult`, an exception message, or a log line.
Pure prose correction, no behavior change, no dedicated test.

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **163 tests, unchanged** (R19-5 was comment-only, no new test).
- `scripts/bot/test_build_deid_corpus.py` + `scripts/bot/test_wa_blind_bench.py`
  combined: **201 → 211** (+10: 4 for R19-1, 4 for R19-2, 2 for R19-3;
  R19-4 needs no dedicated test per the R8-2/R8-10/R18-4 comment-only
  precedent), zero failures, RC 0.
- `ruff check` on all six fenced `.py` files touched across every round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.

### R19-1b micro-disposition (Codex pre-freeze gate on R19-1's own
implementation, integrated after round 19 (`037d697c9`) had already
been delivered — MICRO-THAW, same pattern as R15-1b/R16-2b/R18-1b)

R19-1's pure ADJACENT-PAIR rule closed the bridging-stopword hole
(§26's R19-1) but introduced its own declared residual: "pak budi ya"
stayed unflagged, because "budi" — the real, single name word — had no
adjacent non-stopword partner anywhere in the window. That residual was
unnecessary: it existed only because the pair rule was applied
uniformly, even to the FIRST word right after the marker, where
R18-1b's original single-word rule was already correct and never
needed replacing — only the case where that first word is ITSELF a
stopword ever needed a smarter rule.

Corrected to TWO-MODE semantics, which eliminates the "pak budi ya"
residual entirely without reopening the bridging-stopword hole R19-1
closed: (a) if the word immediately after the honorific is a valid
non-stopword candidate, that single word suffices to flag — R18-1b's
original rule, restored for this specific position; (b) only when that
first word is NOT a qualifying candidate (a stopword) does the
adjacent-pair rule from R19-1 apply, scanning the rest of the window
for two consecutive non-stopword candidates. Implemented via a shared
`_is_honorific_name_candidate` helper (extracted from the inline
pair-check condition) and a two-branch body in
`_has_honorific_spaced_lowercase_name`: check `tokens[0]` alone first
(mode a), fall through to the adjacent-pair scan (mode b) only if that
fails.

Verified empirically against the full case set: "pak budi santoso"/"pak
budi ya" both flag via mode (a) — the residual is closed; "pak minta
budi santoso"/"ibu tolong siti rahayu" still flag via mode (b) — the
leading stopword disqualifies mode (a), and the pair behind it
satisfies mode (b); "pak tolong kirim"/"makasih pak sudah bantu" stay
unflagged — mode (a) fails on the leading stopword, mode (b) finds no
adjacent pair (only one candidate word follows); every R18-1/ADDENDUM/
R18-1b/R19-1/R19-3 case re-run identically, including the dot-attached
branch (untouched by this fix) and the titlecase-spaced branch.

**Declared residual, STRICTLY NARROWER than R19-1's own** (inherent to
mode (b), the only case left needing a pair at all): a bridging
stopword followed by exactly ONE name word and nothing else that
qualifies — "pak minta budi" (nothing follows "budi") or "pak tolong
siti ya" (only a stopword follows "siti") — still escapes, since mode
(b) never fires on a single candidate.

**R19-2 confirmation (Codex gate, not a code change):** the gate
additionally asked to confirm "jl.sunset", "Gg. Melati", "Jln mawar",
and "Blok C" all survive the R19-2 tightening — all four verified still
flagged; "Blok C" specifically was not previously in the pinned
innocence-regression set and is now added to it.

Pinned by 4 new tests in `TestR19_1bHonorificTwoModeStopwordGuard`
(mode-a residual closure, mode-b regression, mode-b innocence
regression, the new narrower declared residual) — the R19-1-era test
asserting the OLD "pak budi ya" residual
(`test_declared_residual_single_lowercase_name_before_stopword_not_flagged`)
is REMOVED, since its assertion is now the opposite of correct
behavior, rather than left stale; plus 1 addition to
`TestR19_2AddressMarkerPrefixBoundary`'s existing innocence-regression
test ("Blok C").

Final measured test counts, this micro-round (re-collected fresh from
the worktree on disk immediately before recomposition, superseding the
counts in the bullet list above):

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  unaffected, **163**, unchanged.
- `scripts/bot/test_build_deid_corpus.py` + `scripts/bot/test_wa_blind_bench.py`
  combined: **211 → 214** (+3: net of −1 removed stale-residual test
  +4 new `TestR19_1bHonorificTwoModeStopwordGuard` tests; the "Blok C"
  addition extends an existing test, no new count), zero failures, RC 0.
- `ruff check` on all six fenced `.py` files: clean.

## 27. Twentieth-round review disposition (Kimi K3 on frozen 30da031ea)

A twentieth review pass from Kimi K3 on the frozen `30da031ea` diff (the
commit that closed §26's R19-1b micro-disposition, base still the
immutable `6a8ab5180`, fence still exactly 9 files) came back RED with 2
MEDIUM + 1 LOW + 1 MICRO, all four confirmed reproducible on disk by the
orchestrator's gate with a live empirical probe. The review also
CONFIRMED every positive claim from round 19 as holding (the lookahead,
the two-mode semantics, the re-pointed prose, the docstring correction).
All four findings are on `build_deid_corpus.py`.

**R20-1 (MEDIUM) — dot-attached branch missing the mode-(b) bridging-
pair mirror.** The dot-attached branch only ever had §26's mode-(a)
single-word check — it was never given the mode-(b) bridging-pair
mirror R19-1/R19-1b added to the spaced branch, and a dot-attached
honorific cannot fall through to the spaced function either (that one
requires literal whitespace right after the marker, which a dot-attached
form never has). Proven: "ibu.tolong siti rahayu" and "pak.minta budi
santoso datang" both passed BOTH scans — the same fail-open class as the
HIGH-severity R19-1. Fixed by REFACTORING both branches onto a single
shared two-mode scan, `_has_honorific_name_after_marker(text,
marker_only_re, mode_a_is_candidate)`, parameterized on (i) which
marker-only regex to anchor on (`_HONORIFIC_MARKER_ONLY_RE` for the
spaced branch, the new `_HONORIFIC_DOT_MARKER_ONLY_RE` for the dot
branch) and (ii) what counts as a mode-(a) candidate — the spaced branch
keeps `_is_honorific_name_candidate` (lowercase-only, since spaced
titlecase is handled separately by `_HONORIFIC_NAME_RE`), while the dot
branch gets a new `_is_honorific_dot_attached_mode_a_candidate`
(any-case, preserving the original R19-3 rule for titlecase dot-attached
names like "Sig.Rossi", which has no separate titlecase branch). Mode
(b) is IDENTICAL on both branches — the shared, lowercase-only
`_is_honorific_name_candidate` pair-scan, per the mandate's own
instruction to reuse it rather than duplicate the logic. The old
`_HONORIFIC_DOT_ATTACHED_CANDIDATE_RE` (a single-capture regex with no
room for a multi-word pair-scan) is REMOVED as dead code, zero
call-sites remaining, per this file's own R18-4 convention. Verified
empirically: the two guilt scenarios above now flag; "makasih
pak.sudah bantu"/"bu.tolong kirim" stay unflagged (their only candidate
pair fails on the leading stopword); every pure mode-(a) case
("ibu.siti rahayu", "Sig.Rossi", "Sig.raffaele") is unaffected.
**Historical note, verified rather than assumed**: "Sig.ra Rossi" was
never actually caught by the dot-attached branch at all — it matches
`_HONORIFIC_NAME_RE` (the spaced-titlecase branch) instead, via the
"Sig.ra" marker token backtracking to combine with the SPACED " Rossi"
tail; confirmed empirically before relying on it for this round's
restructure. **Declared residual, MIRRORING the spaced branch's own
R19-1b residual exactly**: a dot-attached bridging stopword followed by
exactly ONE name word and nothing else that qualifies ("pak.minta budi")
still escapes, since mode (b) never fires on a single candidate.

**R20-2 (MEDIUM) — `_ID_DOC_NEAR_DIGITS_RE`, Indonesian enclitic
suffixes rejected.** The trailing `\b` right after the keyword
alternation rejected Indonesian enclitic suffixes ("-nya"/"-ku"/"-mu"/
"-lah", possessive/emphatic particles glued directly onto the noun with
no space) — since both the keyword and its suffix are word characters,
there is no word/non-word transition for `\b` to fire on between them.
Proven: "paspornya A1234567", "KTPnya 3171234567", "NIKnya
317123456789" all passed BOTH scans, while the bare unsuffixed "paspor
A1234567" was already caught — and the suffixed form is the MORE common
one on real WhatsApp chat, not an edge case. Fixed: an optional
non-capturing enclitic-suffix group, `(?:nya|ku|mu|lah)?`, inserted
between the keyword alternation and the trailing `\b` — a DETECTOR
widening, free under the R16-1 directional rule. Verified empirically:
all three suffixed guilt scenarios now flag; the pre-existing unsuffixed
"paspor A1234567" guilt case is unaffected.

**R20-3 (LOW) — honorific separator rejected light punctuation.** The
separator between the marker and the name allowed only an optional
literal dot (`\.?`) before the mandatory whitespace — real WA messages
routinely punctuate an honorific with a colon or comma instead ("pak:
budi santoso", "pak, budi santoso ok"), which this separator rejected
entirely. Fixed: `\.?` widened to `[.:,]?` on both `_HONORIFIC_NAME_RE`
(spaced-titlecase) and `_HONORIFIC_MARKER_ONLY_RE` (the two-mode
spaced-lowercase scan) — a DETECTOR widening, free under the same
directional rule. Verified empirically: both guilt scenarios now flag;
"pak, sudah bantu" stays unflagged (stopword guard). **Declared,
INTENDED side effect**: "bu, besok ya" (the R18-1b structural-innocence
fixture) now REACHES the two-mode scan and stays unflagged via the
stopword guard on "besok" instead of via the comma blocking the match
entirely — the VERDICT is unchanged, only the MECHANISM is. The test
that declared this "structural"
(`test_innocence_comma_after_marker_still_not_flagged`) had its
docstring corrected to name the mechanism change rather than left
describing a reason that no longer applies.

**R20-4 (MICRO) — `test_innocence_no_adjacent_non_stopword_pair_not_flagged`,
semi-vacuous fixture after R20-3.** The test's second fixture, "bu,
besok ya", stopped exercising what the test's own name claims ("no
adjacent non-stopword pair") once R20-3 changed why it stays unflagged —
it now reaches the scan via the same stopword mechanism as the OTHER
fixture already in the test, for a reason unrelated to the comma the
test's history was actually about. Replaced with "ibu minta bantu" — a
genuinely different marker+stopword+single-word combination ("minta" is
the stopword, "bantu" the lone content word, no adjacent partner) that
exercises the same mode-(b)-no-pair mechanism without inheriting a
fixture whose own history is about punctuation, not the pair rule. No
regression: the comma-specific case remains pinned in its own dedicated
test (§ R20-3 above).

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **163 tests, unchanged** (no fenced client file touched this round).
- `scripts/bot/test_build_deid_corpus.py` + `scripts/bot/test_wa_blind_bench.py`
  combined: **214 → 222** (+8: 4 for R20-1, 2 for R20-2, 2 for R20-3;
  R20-4 replaces a fixture inside an existing test, no new count),
  zero failures, RC 0.
- `ruff check` on all six fenced `.py` files touched across every round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.

### R20-3b micro-disposition (Codex gate, in-flight during round 20 —
integrated before this round's recomposition; same pattern as
R15-1b/R16-2b/R18-1b/R19-1b, distinguished by arriving BEFORE the
crossing rather than after)

F3's own finding text named "colon/HYPHEN-after-honorific" explicitly,
but R20-3's delivered separator class, `[.:,]?`, omitted the hyphen —
proven: "pak- budi santoso" and "bu- besok ya" both passed undetected
under the round-20 fix as first landed. Fixed: the hyphen added to the
class on both sites — `_HONORIFIC_NAME_RE` (spaced-titlecase) and
`_HONORIFIC_MARKER_ONLY_RE` (the two-mode spaced-lowercase scan) —
`[.:,]?` → `[.:,-]?`. No escaping needed: a hyphen placed at the END of
a character class is always literal in Python `re`, never a range
operator; confirmed clean under `ruff` in this exact form, as the
mandate asked to verify. Same DETECTOR-widening, free-under-R16-1
reasoning as the rest of R20-3 — no new directional-rule question.
Verified empirically: "pak- budi santoso" now flags; "bu- besok ya"
stays unflagged via the stopword guard on "besok", the same mechanism
R20-3's own comma case uses. Full comprehensive regression re-run
across every case from R18-1/ADDENDUM/R18-1b/R19-1/R19-1b/R19-3/R20-1/
R20-2/R20-3/R20-4 — all identical.

Pinned by 1 new test, `test_r20_3b_guilt_and_innocence_hyphen_separator`,
added to `TestR20_3HonorificLightPunctuationSeparator` (its class
docstring updated to name the amendment); no separate micro-round test
class, since this corrects R20-3 itself rather than introducing a new
mechanism.

Final measured test counts, this micro-round (re-collected fresh from
the worktree on disk immediately before recomposition, superseding the
counts in the bullet list above):

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  unaffected, **163**, unchanged.
- `scripts/bot/test_build_deid_corpus.py` + `scripts/bot/test_wa_blind_bench.py`
  combined: **222 → 223** (+1), zero failures, RC 0.

## 28. Twenty-first-round review disposition (Kimi K3 on frozen 8082b14d0)

A twenty-first review pass from Kimi K3 on the frozen `8082b14d0` diff (the
commit that closed §27's R20-3b micro-disposition, base still the immutable
`6a8ab5180`, fence still exactly 9 files) came back RED with 2 MEDIUM + 2 LOW
+ 2 MICRO. The mandate's own triage carried a PARTIAL REFUTATION on F1
("confirmed only on the punct-then-named dot-attached branch — the spaced
branch already handles it"), which the empirical work below DISPROVES — see
R21-1. All six findings are on `build_deid_corpus.py` (five in the honorific
two-mode scan machinery, one in `_ID_DOC_NEAR_DIGITS_RE`; R21-4 and R21-6(b)
are on `test_build_deid_corpus.py`).

**R21-1 (MEDIUM) — mode (b)'s pair-scan rejected a capitalized pair member,
on BOTH branches, identically — the gate's partial refutation does not
hold up empirically.** Mode (b)'s adjacent-pair check reused
`_is_honorific_name_candidate` — LOWERCASE-ONLY via `token[0].islower()` —
for both the spaced and (then-)dot-attached branches (R20-1's shared-helper
refactor). That rejects a capitalized token like "Budi" or "Siti"
identically on either branch: `_is_honorific_name_candidate("Budi")` is
`False`. The gate's triage argued the spaced branch was UNAFFECTED, citing
"pak minta Budi santoso datang" as still flagging. **Disproven by
empirical trace, not assumed**: `_independent_pii_scan("pak minta Budi
santoso")` — the SAME fixture with the trailing "datang" removed —
returns `[]`. The mandate's fixture only flagged because of an unrelated,
purely-lowercase adjacent pair later in the same 4-word window
(`("santoso", "datang")`, both ordinary lowercase non-stopwords), not
because "Budi" was ever recognized as a candidate. Confirmed directly:
`_is_honorific_name_candidate('Budi')` → `False`,
`_is_honorific_name_candidate('budi')` → `True`. So the true bug (mode
(b)'s case-sensitivity restriction) is SYMMETRIC across both branches —
the apparent asymmetry in the gate's own fixture set was an artifact of
fixture choice, not evidence the spaced branch handles mixed case
correctly. Fixed: a new `_is_honorific_pair_candidate` (any-case,
stopword-guarded, otherwise identical to
`_is_honorific_attached_mode_a_candidate` — R21-2 below) is used for mode
(b)'s pair-scan uniformly on both branches, replacing the reused
`_is_honorific_name_candidate` there; `_is_honorific_name_candidate` itself
is UNCHANGED and remains the spaced branch's mode-(a) check (lowercase-only
is still correct there — it is what distinguishes a bridging lowercase
name from `_HONORIFIC_NAME_RE`'s separate titlecase-spaced match). Verified
empirically: "ibu.tolong Siti rahayu" (punct-attached) and "pak minta Budi
santoso" (spaced, WITHOUT the lucky trailing word) both now flag directly
via mode (b) recognizing "Budi"/"Siti"; the mandate's own fixture ("pak
minta Budi santoso datang") stays flagged, for the correct reason now;
"makasih pak.sudah bantu"/"makasih pak sudah bantu" stay unflagged on
both branches (stopword guard unaffected by the case widening). This
corrects the R19-1b/R20-1 module comments elsewhere in the file that
describe mode (b) as "always lowercase-only" — accurate for the rounds
that wrote them, no longer accurate as of this fix; corrected via a new
dated comment paragraph in place, per this file's own convention, not a
silent edit of the R19-1b/R20-1 prose.

**R21-2 (LOW) — punct-attached branch's marker regex never carried the
comma/colon/hyphen widening its siblings got in R20-3/R20-3b.** The
branch's marker-only regex (then `_HONORIFIC_DOT_MARKER_ONLY_RE`) matched
only a literal dot (`\.\s*`) between the marker and the name — real WA
messages punctuate this no-space-before-punctuation shape with a comma,
colon, or hyphen too, exactly as `_HONORIFIC_NAME_RE`/
`_HONORIFIC_MARKER_ONLY_RE` were already widened to accept. Proven:
"pak,budi santoso ok", "pak-budi santoso", and "pak:budi santoso" all
passed undetected. Fixed: `\.` widened to `[.:,-]` (still MANDATORY, not
optional — this branch's entire purpose is "punctuation glued directly
onto the marker with no space before it"; an optional form would just
duplicate the spaced branch). Renamed throughout the live code —
`_HONORIFIC_DOT_MARKER_ONLY_RE` → `_HONORIFIC_ATTACHED_MARKER_ONLY_RE`,
`_has_honorific_dot_attached_name` → `_has_honorific_attached_name`,
`_is_honorific_dot_attached_mode_a_candidate` →
`_is_honorific_attached_mode_a_candidate` — "dot" no longer describes what
the class matches. Per this file's own corrections convention, the
historical prose narrating what the R19-3/R20-1 rounds did AT THE TIME
(which used the old names) is left intact; the docstrings directly
attached to the renamed symbols, which describe LIVE behavior, are updated
in place, with a new dated correction paragraph pointing from the old
narration to the rename. Verified empirically: all three guilt scenarios
above now flag; "bu,tolong kirim"/"pak-sudah bantu" stay unflagged
(stopword guard, same mechanism as the pre-existing dot-form cases).

**R21-3 (MEDIUM) — a STACK of leading bridging stopwords exhausted the
fixed pair-scan window before ever reaching the real name pair.** Mode
(b)'s pair-scan ran over a window of `_HONORIFIC_FOLLOWING_WORDS_WINDOW`
(4) words measured from the marker itself. A single leading stopword was
already handled (the pair sits inside the remaining window); a STACK of
several was not. Proven: "pak minta tolong dong budi santoso" (three
leading stopwords, "minta"/"tolong"/"dong", then the real pair
"budi"/"santoso") passed undetected under the fixed-window scan — the
4-word window from the marker covered only "minta tolong dong budi",
never reaching "santoso". Fixed: leading stopwords are now skipped first
(bounded by a new `_HONORIFIC_STOPWORD_SKIP_CAP` = 4, so a pathological
all-stopword run can't scan unboundedly), THEN the
`_HONORIFIC_FOLLOWING_WORDS_WINDOW`-wide pair-scan runs starting after
that skip, on BOTH branches (shared `_has_honorific_name_after_marker`).
Verified empirically: the guilt scenario above now flags; every
pre-existing R19-1/R19-1b/R20-1 single-stopword guilt case ("pak minta
budi santoso", "ibu tolong siti rahayu") and innocence case ("makasih pak
sudah bantu", "pak tolong kirim") is unaffected. **Declared residual, SAME
SHAPE as R19-1b/R20-1's own, generalized rather than changed**: a
bridging stopword (or stack of stopwords) followed by exactly ONE name
word and nothing else that qualifies still escapes ("pak minta tolong
budi") — mode (b) still never fires on a single candidate, regardless of
how many leading stopwords preceded it.

**R21-4 (LOW) — `TestR19_3DotAttachedHonorificStopwordGuard`'s docstring
names a symbol removed two rounds ago.** The test class's docstring
narrates R19-3's own extraction, naming `_HONORIFIC_DOT_ATTACHED_CANDIDATE_RE`
— a symbol R20-1 already REMOVED as dead code (§27, R20-1) and this round's
R21-2 further renamed the surviving branch away from "dot" entirely.
Judgment call per the mandate: this is historical narration of what R19-3
did AT THE TIME (accurate as history), not a live claim about current
code, so the text itself is left intact per this file's convention — a
new paragraph is APPENDED to the class docstring declaring the symbol's
removal and pointing to where the surviving branch now lives
(`_has_honorific_attached_name`), so a reader who greps for the named
symbol and finds nothing has an explanation in the same place they looked.

**R21-5 (MICRO) — `_ID_DOC_NEAR_DIGITS_RE`'s enclitic group missed
`-kah`/`-pun`.** R20-2's enclitic suffix group named only
`nya`/`ku`/`mu`/`lah`. Two other common Indonesian enclitics — the
interrogative/emphatic `-kah` and the emphatic `-pun` — were absent.
Proven: "KTPkah 3171234567" and "KTPpun 3171234567" both passed
undetected, the same fail-open shape as R20-2's original finding. Fixed:
`(?:nya|ku|mu|lah)?` widened to `(?:nya|ku|mu|lah|kah|pun)?` — a DETECTOR
widening, free under the R16-1 directional rule. Verified empirically:
both new suffixed guilt scenarios now flag; the pre-existing R20-2
suffixes and the bare unsuffixed form are unaffected.

**R21-6 (MICRO, two-part) — (a) one untyped parameter; (b) one
mislabeled test name.** (a) `_has_honorific_name_after_marker`'s
`mode_a_is_candidate` parameter was the module's one function parameter
without a type annotation (Golden Rule §5, project CLAUDE.md — full
annotations on every function). Fixed: annotated
`Callable[[str], bool]`, importing `Callable` from `collections.abc`
(consistent with the file's existing `from collections.abc import
Iterator`, not the deprecated `typing.Callable`). (b) In
`TestR20_2IdDocEncliticSuffix`,
`test_innocence_regression_unsuffixed_form_still_flagged` pinned a
POSITIVE match (`assert "id_doc_near_digits" in ...`) while its name
claimed "innocence" — innocence means NOT flagged; this test is a
guilt-regression pin. Renamed to
`test_regression_unsuffixed_form_still_flagged`, content unchanged, a
docstring added naming the mislabel it corrects. The mandate's other
candidate,
`test_innocence_regress_dot_attached_single_word_after_stopword_not_flagged`
(`TestR20_1DotAttachedTwoModeStopwordGuard`), was checked and found
correctly labeled — it asserts NOT-flagged, which IS an innocence
verdict — so it was left unrenamed; per the mandate's own instruction to
fix only "where the name lies about the pinned verdict", not every
occurrence of a since-renamed branch's old vocabulary in a round-tagged
class/test name (those are left as-is throughout this file, matching
every other Round-N-tagged class name that is never retroactively
renamed when the branch it tests is later renamed).

### Final measured test counts (this round, not carried forward from memory)

Re-collected fresh after every fix and test addition above, from the
worktree on disk, immediately before recomposition:

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **163 tests, unchanged** (no fenced client file touched this round).
- `scripts/bot/test_build_deid_corpus.py` + `scripts/bot/test_wa_blind_bench.py`
  combined: **223 → 234** (+11: 4 for R21-1, 2 for R21-2, 3 for R21-3, 2
  for R21-5; R21-4 and R21-6 are prose/naming-only, no new tests), zero
  failures, RC 0.
- `ruff check` on all six fenced `.py` files touched across every round
  (`openai_responses_client.py`, `build_deid_corpus.py`,
  `test_build_deid_corpus.py`, `test_wa_blind_bench.py`,
  `wa_blind_bench.py`, `test_openai_responses_client.py`): clean.
- The mandatory round-20 gate's 18-case probe (the full
  R18-1/ADDENDUM/R18-1b/R19-1/R19-1b/R19-3/R20-1/R20-2/R20-3/R20-3b
  regression set) was re-run in full against the fully-edited module: 18/18
  pass, zero regressions from this round's shared-function rework (R21-1's
  case-widening and R21-3's skip-then-scan restructure both touch
  `_has_honorific_name_after_marker`, which every prior honorific-round
  test ultimately exercises through `_independent_pii_scan`).
- `ruff check` on all six fenced `.py` files: clean.

### R21-1b micro-disposition (orchestrator gate, in-flight during round
21 — integrated after round 21 (`3b93726fd`) had already been delivered
— MICRO-THAW, same pattern as R15-1b/R16-2b/R18-1b/R19-1b/R20-3b)

The gate's own initial triage of this round's R21-1 mandate had carried a
"partial refutation" framing — F1 confirmed only on the punct-attached
branch, the spaced branch supposedly already handling mixed-case pairs.
The delivered R21-1 fix ALREADY DISPROVED that framing empirically
(§28 above) and landed the fix symmetrically on both branches — no code
change was needed for this correction. What this micro-disposition adds
is a sharper, explicitly-stated record: **F1 is valid on BOTH branches,
there is no asymmetry** — Kimi's own example, "pak minta Budi santoso
datang", reproduced the defect only by ACCIDENT, via an unrelated,
purely-lowercase pair further in the same window ("santoso", "datang"),
never because the capitalized "Budi" was recognized; that accident made
the spaced branch look already-correct when it was not. The CANONICAL
spaced reproduction ends on the surname with nothing lowercase-pair-
shaped left in the window behind it: "pak minta Budi santoso" (bare,
already pinned in §28) and, added this micro-round, "pak minta Budi
santoso ya" (trailing STOPWORD — "ya" cannot itself supply a rescuing
pair the way "datang" did, so this variant isolates the same mechanism
from a second angle). Both fail without the fix, both flag with it.
Pinned by 1 new test,
`test_guilt_mixed_case_pair_flagged_on_spaced_branch_with_trailing_stopword`,
added to `TestR21_1HonorificPairScanAnyCase` (its class docstring
sharpened to state the both-branches, no-asymmetry finding explicitly,
and to name Kimi's example as an accidental, non-canonical reproduction
rather than a valid isolation of the defect); no separate micro-round
test class, since this corrects R21-1's own record rather than
introducing a new mechanism.

Final measured test counts, this micro-round (re-collected fresh from
the worktree on disk immediately before recomposition, superseding the
counts in the bullet list above):

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  unaffected, **163**, unchanged.
- `scripts/bot/test_build_deid_corpus.py` + `scripts/bot/test_wa_blind_bench.py`
  combined: **234 → 235** (+1), zero failures, RC 0.
- `ruff check` on all six fenced `.py` files: clean.

## 29. Bounded-scope disposition for Scan B honorific heuristics (round 22, Codex-authorized)

A twenty-second review pass — GLM-5.2, substituting for the Kimi K3 seat
after its quota death — on the frozen `54ada3d57` diff (the commit that
closed §28's R21-1b micro-disposition, base still the immutable
`6a8ab5180`, fence still exactly 9 files) came back RED with 4 findings
≥ LOW, all four confirmed reproducible on disk by the orchestrator's
probes. Per a pre-authorized Codex ruling, this round activates a
**BOUNDED-SCOPE DISPOSITION**: no heuristic code change to
`build_deid_corpus.py` this round. Sixteen honorific-heuristic rounds
(R18 through R21, plus the ADDENDUM/R18-1b/R19-1b/R20-3b/R21-1b
micro-disposition line) have chased a fix→twin-variant loop on this same
Scan B heuristic — every closed finding has, on the next pass, spawned a
sibling variant in the adjacent shape (case, punctuation, stopword
count, token length). This round's disposition is the deliberate
circuit-breaker on that loop, not a claim that the heuristic is
perfect.

**(1) Statement of the disposition.** Scan B (`_independent_pii_scan`,
including the honorific-name heuristic this ADR has iterated on since
§13/R18) is a bounded heuristic **BACKSTOP** in the offline de-id corpus
builder, not the primary defense — the primary defense is the
`Redactor` (shape-based PII redaction, unconditional) PLUS Scan A/B's
fail-closed behavior: any message either scan flags is DROPPED from the
corpus entirely, never redacted-and-kept. A backstop that over-catches
costs a dropped fixture (free, per this file's own cost model); a
backstop that under-catches costs a corpus leak, bounded by the fact
that this builder's OUTPUT is a de-identification training/eval corpus,
not a client-facing surface — a residual here does not reach a WhatsApp
client, a bot reply, or any production channel. The four variant classes
enumerated below in (2) are hereby marked **RESIDUALS**: this lane will
not iterate further heuristic fixes on THESE classes. Any NEW class not
already enumerated here, or any finding outside Scan B entirely (the
`Redactor`, the OpenAI Responses client, the corpus I/O/dedup/manifest
logic), re-enters normal THAW triage without restriction — this
disposition is scoped narrowly to the four classes named below, not to
Scan B as a whole going forward.

**(2) The four GLM round-22 findings — class, direction, canonical
reproduction, all orchestrator-verified live on disk at `54ada3d57`
before this section was written:**

- **(a) MEDIUM, fail-closed starvation — the interrogative/pronoun class
  is absent from `_HONORIFIC_NON_NAME_STOPWORDS`.** The stoplist covers
  particles/emphatics (R19-1's original 33-word set) but not the
  interrogative/pronoun vocabulary a real client question is built from
  — "saya", "berapa", "apa", "kapan", "gimana", "kenapa", "dimana",
  "kami", "kita", "dia". Mode (a) treats the FIRST word after the marker
  as a name candidate whenever it is not a recognized stopword, so
  `"Pak berapa biaya untuk PT PMA?"` → `["honorific_name"]` — the single
  most common real-WA client-question shape (an honorific opening a
  price/service question) is dropped from the corpus. Confirmed on both
  the spaced and attached branches: `"pak saya mau tanya soal visa"` →
  `["honorific_name"]`, `"pak.saya mau tanya"` → `["honorific_name"]`.
  This is the R19-1/R19-2 stoplist-VOCABULARY axis (not a new mechanism)
  — the fix shape, when it lands, is a stoplist ADDITION, not a scan
  restructure; see (4) below.
- **(b) MEDIUM, fail-open — intra-name dot-elision at the NAME position
  collapses the pair.** `_HONORIFIC_FOLLOWING_WORD_TOKEN_RE` (the
  per-word tokenizer used to build the mode-(b) candidate list) does not
  cross a literal `.` — R18-1's own documented Indonesian elision habit
  ("no space after a period" — the reason the punct-attached MARKER
  branch exists at all) can also occur INSIDE the name itself, between
  given and family name: `"pak minta budi.santoso ya"` → `[]`. Traced:
  the tail tokenizes to `["minta", "budi", "ya"]` (the tokenizer stops
  at the dot inside "budi.santoso", producing "budi" and silently
  dropping ".santoso" — `_HONORIFIC_FOLLOWING_WORD_TOKEN_RE` never
  yields a second token for the family-name half), so the adjacent-pair
  scan never sees a `("budi", "santoso")`-shaped pair at all — "budi" is
  a valid mode-(b) candidate on its own but has no adjacent partner
  once "santoso" never becomes its own token. The full given+family name
  enters the corpus.
- **(c) LOW, fail-open — the R21-3 stopword-skip loop halts on
  punctuation-only or short non-stopword function-word tokens, silently
  re-opening the window-exhaustion shape R21-3 closed.** R21-3's skip
  loop advances past a token only while
  `tokens[skip].lower() in _HONORIFIC_NON_NAME_STOPWORDS`; a token that
  is neither a recognized stopword NOR a valid name candidate (an
  em-dash tokenizing to `""`, or a short function word like "di" that
  fails the `len(token) >= 3` floor) satisfies neither branch of the
  loop and neither branch of the pair-scan, so the scan silently gives
  up at that position without reaching the real pair behind it. Proven:
  `"pak minta — tolong dong budi santoso"` → `[]` (the em-dash token
  breaks the skip AND fails the pair-candidate check) and
  `"pak di minta tolong dong budi santoso"` → `[]` (the leading "di", 2
  characters, is neither a stoplist member nor a length-3+ candidate).
  Same window-exhaustion FAMILY as R21-3, reopened through a token shape
  R21-3's fix did not anticipate (a non-stopword, non-candidate token
  mid-stream) rather than through a longer stopword stack.
- **(d) LOW, fail-open — sub-3-character name tokens escape every
  branch of the heuristic.** Every mode-(a)/mode-(b) candidate predicate
  requires `len(token) >= 3`, and `_HONORIFIC_NAME_RE`'s own titlecase
  match requires `{2,}` MORE characters after the first (3+ total) —
  none of the three paths recognize a 2-character surname. Real
  Chinese-Indonesian family names are commonly this short (Ng, Li, Oh).
  Proven: `"kirim ke Ibu Ng besok ya"` → `[]`.

**(3) REFUTED sibling, recorded here so it is NOT enumerated as a
residual.** GLM's review also flagged all-lowercase `"sig.ra rossi"` as
an escape. **False on disk**: `"sig.ra rossi datang besok"` →
`["honorific_name"]` — the spaced branch's `_HONORIFIC_MARKER_ONLY_RE`
matches the full "Sig.ra" token (its own alternation includes
`Sig(?:\.ra)?`), leaving "rossi" as the word immediately after the
marker match; "rossi" is lowercase, 6 characters, not in the stoplist,
so it satisfies the spaced branch's mode-(a) candidate check directly.
Verified before writing this paragraph, not assumed, per this file's
own anti-phantom-citation discipline (§6/W65) — a finding this round's
own disposition declares CLOSED must not silently absorb a false
positive alongside the four real ones.

**(4) Maintenance path, so the disposition does not read as
permanent.** The first real corpus build (not this test/probe
exercise) reviews per-bucket drop rates as a matter of course. If that
review shows the interrogative/pronoun starvation in (2)(a) — or any of
(2)(b)/(c)/(d) — measurably biasing the corpus, extending
`_HONORIFIC_NON_NAME_STOPWORDS` (for (a)) or a targeted tokenizer/
skip-loop fix (for (b)/(c)/(d)) is **normal post-freeze maintenance**,
scoped to the SPECIFIC class the drop-rate review names, and does **NOT**
by itself reopen this lane to another open-ended THAW/FREEZE cycle on
Scan B as a whole — it is a bounded follow-up PR against a measured
signal, not a resumption of the review cadence this section closes.

### Final measured test counts (this round, not carried forward from memory)

- `apps/backend-rag/backend/tests/llm/test_openai_responses_client.py`:
  **163 tests, unchanged** (no fenced client file touched this round —
  forbidden by this round's own scope).
- `scripts/bot/test_build_deid_corpus.py` + `scripts/bot/test_wa_blind_bench.py`
  combined: **235, unchanged** (R22-2 is a docstring-only fix, zero
  assertion changes, zero new tests — see R22-2 below), zero failures,
  RC 0.
- `ruff check` on all six fenced `.py` files: clean.

**R22-2 (MICRO, doc-only) — `TestR20_1DotAttachedTwoModeStopwordGuard`'s
class docstring still claimed mode (b) uses "the shared lowercase-only
`_is_honorific_name_candidate` pair-scan"** — true when R20-1 wrote it,
false since R21-1 widened mode (b) to the any-case
`_is_honorific_pair_candidate` on both branches (§28). Same doc-accuracy
class as R19-4/R21-4 (a docstring narrating a mechanism a LATER round
changed, left unchecked). Corrected in place in
`scripts/bot/test_build_deid_corpus.py` — the sentence now names
`_is_honorific_pair_candidate` (any-case) instead of
`_is_honorific_name_candidate` (lowercase-only); this is the exception
in this file's own corrections convention (a docstring directly
attached to a live test class describes LIVE behavior, corrected in
place, not narrated-and-superseded like the deep historical paragraphs
elsewhere in this module). Zero assertion changes — the test bodies
were already correct, only the prose was stale.

## 30. Owner ruling — subscription path (2026-08-15)

### 30.1 The ruling, and its precedence over §2's NO-GO

Zero (direct, Legge 5 — business decision, the one category this ADR's own
doctrine reserves for the human owner) ruled 2026-08-15: **the WA OpenAI
provider goes through the ChatGPT Pro SUBSCRIPTION (headless `codex exec`),
not a per-token OpenAI API key.**

Honest narration of what this does and does not change:

- **§2's council verdict is not erased.** It stays recorded, verbatim, as
  history — the exact "NO-GO on using the ChatGPT Pro / Codex OAuth
  subscription as a WhatsApp runtime credential ... conflates identity and
  blast radius" reasoning the council gave is still true and still on the
  record. This ruling **overrides** it for this lane, it does not retroactively
  declare it wrong.
- **Zero was shown the residual risk once, explicitly, and accepted it.**
  The specific risk the council named — a human interactive seat's ToS terms
  not being written for unattended service traffic — was not resolved by new
  evidence; it was a business risk-acceptance call, the kind only the owner
  can make (this ADR's own §2 framed the council's NO-GO as a
  recommendation to the business, not a technical impossibility).
- **The house precedent Zero cited is real and on-disk, not a rationalization
  invented for this ADR.** `backend/llm/claude_oauth_client.py` already
  routes 100% of this repo's Claude traffic — including the OpenClaw/Telegram
  channel and every cron `claude` wrapper — through exactly this shape:
  shell out to the vendor's own CLI, authenticate via the human MAX-plan
  OAuth subscription, never the metered API. `codex_exec_client.py` (§30.3)
  is architecturally the same pattern one vendor over: a subprocess wrapper
  around a CLI that authenticates via a ChatGPT Pro subscription instead of
  `OPENAI_WA_PROVIDER_API_KEY`.

### 30.2 The Responses client is demoted to a dormant alternative

`openai_responses_client.py` (§3) is unchanged by this ruling — it is not
deleted, not modified, not superseded in the sense of being replaced. It is
demoted in PRIORITY: under this ruling, `OPENAI_WA_PROVIDER_API_KEY` **will
never be provisioned**. The client stays in-tree as a dormant, fully
reviewed (twenty-one adversarial rounds, §§6-28) alternative — available if
a future, separately-authorized business decision ever wants the API-key
path instead of (or alongside) the subscription path. Nothing in this
section changes that file's own NO-WIRING status, its exception taxonomy,
or its test suite (163 tests, confirmed unchanged this round — §29's own
"Final measured test counts").

### 30.3 The new provider's binding invariants

`apps/backend-rag/backend/llm/codex_exec_client.py` (new, this round) ships
under the same NO-WIRING discipline as its sibling: zero imports from any
live module, offline tests only. Its binding invariants, verified against
its own module docstring and test suite:

1. **Async subprocess only** — `asyncio.create_subprocess_exec`, never
   `shell=True`. Fixed argv shape `codex exec --sandbox read-only
   --skip-git-repo-check --ephemeral --ignore-user-config --ignore-rules
   -m <model> -` (CORRECTED, R28, 2026-08-18: `--ephemeral` suppresses
   persisted session files and `--ignore-rules` suppresses user/project
   exec-policy rules; CLI 0.147.0 help was read locally before both flags
   were fixed into the adapter). The earlier R26 correction added
   `--ignore-user-config`, the R25-1 HIGH security fix that stops host-level
   `~/.codex/config.toml` hooks from receiving the prompt outside the
   model's sandbox. `cwd` is a fresh, empty, per-call
   `tempfile.mkdtemp()` directory, removed in a `finally` block — never the
   repo, never an inherited/shared cwd (see §30.4 for why this was
   empirically, not just theoretically, load-bearing).
2. **Prompt text never on argv, never in the child env** (W115 scar) — the
   literal argv token `-` plus `proc.communicate(input=prompt.encode())`
   delivers the prompt via stdin only, verified against `codex exec --help`'s
   documented stdin contract.
3. **`available` is a fail-closed property**, computed fresh on every read:
   binary presence (constructor arg → `WA_CODEX_BIN` env → `codex` on
   `PATH`) AND a non-empty `auth.json` under `CODEX_HOME` (constructor arg →
   `CODEX_HOME` env → `~/.codex`). Never raises on construction.
4. **Output judgment is asymmetric by design, not "stdout+stderr+exit-code
   together"** (W104 scar; CORRECTED, R26 GLM addendum F26-3, 2026-08-15 —
   this line previously read "judged on stdout+stderr+exit-code together",
   the exact phrasing §30.6's R25-6 already flagged as false against the
   code/test-file docstrings and corrected THERE, but this ADR sentence was
   never updated to match): against a MEASURED contract (§30.4), stdout is
   the clean answer text on `exit_code == 0` — nothing else;
   empty/whitespace-only stdout on a zero exit is a typed
   `CodexExecOutputShapeError`, never a best-effort blank answer. stderr is
   ALWAYS decoded but is a signal source ONLY on `exit_code != 0`; on a
   successful run it echoes the client's own prompt/answer verbatim and is
   never scanned or logged (see point 5, and §30.8).
5. **Auth-death is a distinct typed error** (`CodexExecAuthError`, house scar
   2026-05-24 class), detected only on `exit_code != 0` (CORRECTED, R26 GLM
   addendum F26-3, 2026-08-15 — this line previously said auth-death is
   detected "only after stripping the caller's own prompt text from the
   scanned output", which described the R25-3 shape, not the FINAL one):
   the scan reads STDERR ONLY — stdout is never part of the scanned text at
   all (§30.8) — after removing, WHOLE-LINE-ONLY, any stderr line that
   verbatim-equals a complete line of the prompt or of this run's own stdout.
   See §30.4's stderr-echo finding for why the scope is
   `exit_code != 0`-only, and §30.8 for the full evolution of the stripping
   mechanism (R25-3 → R26-2 → the R26-addendum unified stderr-only design).
6. **Sanitized errors and logs** — no prompt text, no raw stdout/stderr
   content, no auth material ever reaches an exception message or a log
   line; `CodexExecProcessError` carries only the numeric exit code and
   arbitrary post-launch communication failures become the fixed-literal
   `CodexExecCommunicationError` after the child is killed and reaped.
7. **Model governance** — `gpt-5.6-sol` / `gpt-5.6-terra` (default) /
   `gpt-5.6-luna`, the same GPT-5.6 family CLAUDE.md §5 already names for
   this repo's Codex cascade; any other slug is refused pre-launch via
   `CodexExecModelNotAllowedError`.

### 30.4 Grounding-probe outcome (measured, with one honest caveat)

**Measured, not assumed.** One designated live call was run from the
`bot-openai-adapter` session, 2026-08-15, against the operator's real
ChatGPT Pro subscription (`codex login status` → `Logged in using ChatGPT`,
`codex-cli 0.147.0`):

```
$ printf 'Reply with exactly PONG' | codex exec --sandbox read-only \
    --skip-git-repo-check -m gpt-5.6-terra -
# cwd: /tmp/codex-probe-neutral
exit_code=0
stdout: b'PONG\n'
```

*(This is the ORIGINAL R24 probe, quoted exactly as run — it predates the
`--ignore-user-config` fix, which is why that flag is absent from its argv
here; it is not a template to copy. The RE-MEASURED R25-1 probe, with the
fix applied and confirming zero `hook:` lines, is narrated in §30.6; the
code's `_FIXED_ARGV_PREFIX` is the authoritative CURRENT argv shape,
corrected in §30.3 point 1 above per F26-3.)*

The full stderr transcript of the RE-MEASURED R25-1 probe (banner +
echoed prompt/answer + token-count footer) is captured verbatim in
`test_codex_exec_client.py`'s `_MEASURED_SUCCESS_STDERR` fixture.
CORRECTED (R26 GLM addendum, F26-5, 2026-08-15): this sentence, and the
sibling claim in the code's point 7 docstring, previously said "both probe
transcripts are quoted in the ADR §30" — false; no stderr transcript is
quoted inline anywhere in §30 (the code block above is the closest thing,
and it shows only `exit_code`/`stdout`, never stderr). Only the
RE-MEASURED (R25) transcript survives at all, and only in the test
fixture — not here. The ORIGINAL R24 transcript (the one that actually
contained the `hook: SessionStart`/`hook: UserPromptSubmit` lines cited as
the evidence for the next finding below) was overwritten in place by the
re-measure and is not preserved verbatim anywhere in this tree or in git
history (`git log -p` on the test file shows a single commit already
containing only the re-measured content) — declared as a genuine gap, not
reconstructed from memory. Three findings came directly out of the
original probe (and two adjacent, deliberately-scoped diagnostic calls —
see the disclosure below), each of which changed the client's design from
what the mandate had assumed going in:

- **stdout is clean; stderr is not.** stdout on success is *only* the
  answer text (`b'PONG\n'`) — no banner, no metadata. stderr, by contrast,
  is a full human-readable transcript that echoes the CLIENT-SUPPLIED
  prompt text verbatim (`user\n<prompt>`) before the model's answer
  (`codex\n<answer>`). This is why §30.3 point 5 scopes auth-death detection
  to `exit_code != 0` only and strips the known prompt substring before
  scanning: a WA immigration bot's real traffic routinely contains words
  like "login"/"expired"/"unauthorized" as ordinary Indonesian-visa
  vocabulary (a client asking why their KITAS portal login is expired), and
  scanning success-path stderr indiscriminately for those words would be a
  textbook cicatrix family #3 guard-over-match.
- **cwd is load-bearing, empirically, not just in theory.** A diagnostic
  call made from the repo worktree's own cwd (an operator slip, not the
  designated probe) had `codex exec` pick up this repo's own Claude-hook
  machinery (`SessionStart`/`UserPromptSubmit` hooks, a cross-machine "Peer
  Pro" reachability ping) and answer in a machine-specific persona
  ("[Air-M5] Pong. Peer Pro non raggiungibile; sync non verificato.") — live
  proof that an unset/inherited cwd leaks ambient repo/host context into the
  model's turn, not a hypothetical the client's design merely gestures at.
- **`auth.json` file-presence is a necessary-but-not-sufficient proxy.**
  The 2026-08-15 `CODEX_HOME` variant appeared to authenticate without an
  `auth.json`, leading to an explicitly labelled inference that a Keychain
  credential might exist outside the directory. **R28 correction,
  2026-08-18:** a fresh isolated-home reproduction did not reproduce that
  behavior: `codex login status` reported "Not logged in" and two controlled
  `codex exec` attempts failed with HTTP 401. The default authenticated home
  succeeded. The adapter therefore does not rely on the historical Keychain
  inference. `available=True` means only "the configured auth file exists and
  is non-empty", not "the credential is live"; §30.3 point 5's auth-death
  handling remains necessary.

**Honest disclosure — scope of live calls made.** The mandate authorized
exactly one designated grounding-call for this round (R25-1 later
authorized exactly ONE additional designated re-measure — §30.6).
CORRECTED (R27-4, GLM F5, 2026-08-15 THAW round): this paragraph
previously said "Three real codex exec invocations were made in total",
undercounting by one against the module docstring's own point 7 ("all
FOUR calls are declared") — the R25-1 re-measured probe (§30.6) is a real,
separate live call this paragraph never folded in. As of the end of R27,
FOUR real `codex exec` invocations had been made: (1) the designated R24
probe above; (2) an
ACCIDENTAL diagnostic call — an operator slip, cwd left at the repo
default, NOT a deliberately-scoped probe — that produced the cwd-leak
finding below; (3) a deliberately-scoped `CODEX_HOME`-override variant
that produced the third finding below; and (4) the designated R25-1
re-measure (§30.6), confirming `--ignore-user-config` closes the point-1
finding on the wire. All four used the same non-PII "PONG"/health-check-
shaped prompt; none carried client data. This is disclosed here rather
than silently normalized to a lower number — the extra calls were not
free, and the number is stated in the freeze report verbatim rather than
rounded down. (The prior wording also lumped call (2) together with call
(3) as "two additional ... diagnostic calls", implying both were
deliberately scoped — false for call (2), an operator slip, not a design;
corrected here to distinguish an accident from a probe.)

**R28 disclosure, 2026-08-18:** three additional synthetic, non-PII calls
were made, bringing the declared historical total to seven. Two used a fresh
isolated `CODEX_HOME` and failed at authentication; neither created a session
file or left the runtime-generated sentinel on the searched isolated surface.
The third exercised `CodexExecClient` itself with the final fixed argv and the
default authenticated ChatGPT-subscription home: it returned the generated
sentinel exactly, the observed session-file count stayed `3273 -> 3273`, and
no file containing that sentinel was found under `~/.codex`. These are narrow
observations about the exact call and searched surfaces, not a claim that no
other persistence surface can exist. No client data was used, and no further
live calls are planned for this offline lane.

**Auth-failure evidence boundary, corrected R28:** the isolated-home calls now
measure `codex exec`'s own HTTP-401 failure class without logging the operator
out of the working default home. The test fixture remains deliberately
CONSTRUCTED because the full volatile stderr transcript was not promoted into
source. Only the stable `codex login status` phrase "Not logged in" and the
HTTP-401 class are treated as measured; the broader regex vocabulary remains
constructed from the house `claude_oauth_client.py::_AUTH_DIAGNOSTIC_PATTERN`.

### 30.5 Fence update, and what is still unchanged

Fence: **9 → 11 files.** This round adds exactly
`apps/backend-rag/backend/llm/codex_exec_client.py` and
`apps/backend-rag/backend/tests/llm/test_codex_exec_client.py` on top of the
nine files from the original NO-WIRING PR (`git diff 6a8ab5180..1a76f1ce3
--name-only`).

**Correction (R25-6, 2026-08-15 THAW round):** the sentence that used to
stand here — "the nine files ... are unchanged" — was false against this
very round's own delta: `docs/AI_ONBOARDING.md`, one of the original nine,
carries a pre-commit-hook-auto-regenerated `DOCSYNC` test-count line
(`scripts/docs_sync.py::count_test_files` counts test FILES via
`Path.rglob("test_*.py")`, so one new test file bumps the count by exactly
1 — see the REFUTED F5 note below). The accurate statement: the fence stays
**11 files total**; eight of the original nine are byte-identical to the
R24 round, and the ninth (`docs/AI_ONBOARDING.md`) carries only that
mechanically-regenerated count-line delta, folded into the SAME commit as
the feature per the W86 house rule (cicatrix family #9 — "the docs_sync
regen goes in the same commit as the feature, never separate").

**NO-WIRING is unchanged.** This ruling closes the business/cost gate this
ADR's own three-gate framing (§3, module docstrings) named for the
Responses client and now names identically for the subscription client:
security review, and a real shadow-hook design with context parity, are
both still open, both still required before either client gets a live
caller. This ruling is a business decision about WHICH credential path is
authorized when that day comes — it is not itself an activation, and
neither client acquires a caller, a config flag, or a gateway branch as a
result of it. Grep it yourself before trusting this sentence, same standing
instruction as every other NO-WIRING claim in this file.

### 30.6 R25 THAW round — adversarial fix disposition (2026-08-15)

GLM-5.2 delta review on `1a76f1ce3..812f5c594` (the R24 recomposition):
RED, 10 findings. Team-lead's gate: 8 CONFIRMED (fixed below), 1 reframed
into a doc-accuracy fix (folded into §30.5 above and point 4's docstring),
1 REFUTED. Disposition, most-severe first:

- **R25-1 (HIGH, CONFIRMED)** — host-level `codex` config hooks execute
  from the neutral tempdir regardless of cwd; a `UserPromptSubmit` hook
  receives the prompt OUTSIDE the model sandbox (the "[Air-M5]" persona leak
  in point 1 is this class, not a pure cwd issue). Fix: `--ignore-user-config`
  added to `_FIXED_ARGV_PREFIX`; RE-MEASURED (point 7) — zero `hook:` lines
  in the re-probed stderr.
- **R25-2 (MEDIUM, CONFIRMED)** — the `available` gate honored env
  `CODEX_HOME` but `_build_env` injected it into the child ONLY when
  explicitly constructed; a gate/child mismatch was reachable via the env
  var alone. Fix: `_build_env` always injects
  `CODEX_HOME=str(self._resolve_codex_home())`, the same call the gate
  makes — structurally impossible to diverge now.
- **R25-3 (MEDIUM, CONFIRMED)** — (a) a partial answer echoed into stderr
  before a late failure survived prompt-only stripping and could contain
  client-conversation auth-shaped words; (b) bare `401` false-positived on
  ordinary text ("completed after 401 ms"). Fix: `_strip_known_texts` now
  strips BOTH the prompt AND the run's own stdout from the stderr scan
  text; `_AUTH_DEATH_RE` drops bare `401` in favor of context-anchored
  `401 unauthorized|error 401|401 error|http 401` (plus the pre-existing
  bare `unauthorized`). Pinned tests both directions, plus a boundary-
  collision regression proving the stdout-echo strip closes a real
  concatenation false-positive.
- **R25-4 (MEDIUM, CONFIRMED)** — under-match: "token has expired", "you
  need to sign in", "session invalidated", "sign-in required" matched
  nothing. Fix: `_AUTH_DEATH_RE` extended with these phrasings, still
  word-boundary/multi-word-anchored (bare "expired"/"sign" deliberately
  still do NOT match — see the innocence tests for "your passport has
  expired" / "please sign the form").
- **R25-5 (LOW, CONFIRMED)** — `generate()` caught only `FileNotFoundError`
  at launch (a `PermissionError`/other `OSError` would escape untyped), and
  `_kill_and_reap` ran only on `asyncio.TimeoutError` (any other exception
  out of `communicate()` left the child unreaped). Fix: launch catch
  widened to `OSError` (a superclass covering both); `communicate()` wrapped
  with a catch-all that reaps before re-raising the original exception
  unchanged.
- **R25-6 (LOW, CONFIRMED, doc-accuracy)** — point 4's "judged together"
  claim was false on the success path (stderr is decoded but never scanned
  when `exit_code == 0`); the test file's "Invariant 8/9" section headers
  named a taxonomy the module never had (7 invariants, not 9); §30.5's
  "nine files unchanged" claim was false against this round's own
  `docs/AI_ONBOARDING.md` delta. All three corrected in place (point 4's
  docstring, the test file's section headers, §30.5 above).
- **R25-7 (LOW, CONFIRMED)** — missing test coverage: empty/whitespace
  prompt validation through `generate()`, a per-call model override
  reflected in the spawned argv, the `CODEX_HOME` env-tier agreement (R25-2),
  `WA_CODEX_BIN` honored at `generate()`-launch time (not merely by
  `available`). All four added to `test_codex_exec_client.py`.
- **R25-8 (MICRO, CONFIRMED)** — `_build_env`'s docstring omitted `TMPDIR`
  despite the code already passing it through; declared (not coded) residual
  that `errors="replace"` decoding can make the prompt/stdout strip miss at
  a multibyte margin — both now documented on `_build_env` and
  `_strip_known_texts` respectively.
- **REFUTED — F5**, recorded here so it is not re-raised: GLM claimed the
  `docs/AI_ONBOARDING.md` count bump `1360→1361` should have been `+38`
  (the number of new tests this round added). False, verified against
  `scripts/docs_sync.py:89-94`: `count_test_files()` returns
  `len(list(tests.rglob("test_*.py")))` — it counts test FILES, not test
  functions. One new file (`test_codex_exec_client.py`) is `+1` by the
  generator's own, correct semantics; `+38` would be a defect, not the fix.

All fixes re-measured/re-tested where the mandate authorized it (R25-1's
one re-probe; everything else offline per W114). Suite counts, RCs, and
ruff status for the fixed round are in the freeze report for this THAW.

### 30.7 R26 THAW round — second-gate disposition, all three self-inflicted (2026-08-15)

Gemini/agy second-gate review on the R25 delta (the round in §30.6): RED,
3 findings, all orchestrator-confirmed on disk, and — unlike every prior
round — all three are **regressions the R25 fixes introduced themselves**,
not pre-existing defects. Disposition:

- **R26-1 (HIGH, CONFIRMED)** — `asyncio.CancelledError` has been a
  `BaseException` subclass, not an `Exception` subclass, since Python 3.8.
  R25-5's catch-all `except Exception:` around `communicate()` therefore
  never sees a cancellation — the coroutine is torn down without running
  `_kill_and_reap`, and because the caller's tempdir cleanup can race ahead
  of an unreaped child, the subprocess is orphaned. Fix: an explicit
  `except asyncio.CancelledError:` branch, ordered BEFORE the generic
  `except Exception:`, that runs `_kill_and_reap(proc)` and then
  `raise` with no arguments — re-propagating cancellation unchanged rather
  than swallowing or rewrapping it (a cancelled caller must see
  `CancelledError`, never a `CodexExecProcessError` in its place). Pinned
  with a REAL cancellation test: the `generate()` call is scheduled as an
  actual `asyncio.Task`, cancelled mid-flight while the fake process is
  parked in a `communicate()` that never resolves on its own, and the test
  asserts both that `CancelledError` propagates out of the awaited task AND
  that the fake process's kill/wait bookkeeping ran — not a
  `ConnectionResetError` stand-in (the R25-5 test of that shape is kept,
  since it still pins the general catch-all, but it does not exercise this
  clause and was never claimed to).
- **R26-2 (MEDIUM, CONFIRMED)** — `_strip_known_texts` (R25-3) used a
  whole-text `str.replace()`: stripping a short or common stdout answer
  (agy's repro: a one-word answer, `"in"`) deleted every occurrence of that
  substring from stderr, including the one embedded inside the genuine
  diagnostic phrase `"not logged in"` — mangling it to `"not logged "` and
  making the auth-death scanner **fail OPEN** at the exact moment it must
  page. The R25-3 fix closed one false-positive path by opening a
  false-negative one. Fix: renamed to `_strip_known_lines` and rewritten to
  operate on whole lines only — a stderr line is dropped in its entirety
  when it verbatim-equals or is contained in a known line (prompt or
  stdout, split the same way); a line that is not dropped is never
  otherwise touched, so a short/common candidate can no longer reach INTO a
  surviving line and mutate it. Required tests added: (1)
  `test_guilt_bare_common_word_stdout_does_not_mangle_stderr_scan` — agy's
  exact scenario (stdout `"in"`, stderr containing `"Not logged in"`, exit
  1) now correctly still raises `CodexExecAuthError`; (2)
  `test_innocence_echoed_401_unauthorized_prompt_does_not_false_positive` —
  reconfirms the original R25-3 protection (an echoed client message
  containing "401 unauthorized" as content, not diagnostic, must not
  false-page) still holds under the line-based rewrite; (3) the R25-3(a)
  boundary-collision test is RE-EXPRESSED as
  `test_guilt_echoed_stdout_line_prevents_boundary_false_positive` — its
  original form relied on intra-line substring concatenation, which no
  longer applies the same way once stripping is line-granular, so it is
  rebuilt against the measured whole-line wire shape (stdout echoed as its
  own line between `user`/`codex` role markers) to keep proving the same
  property: an echoed stdout line cannot bridge into an adjacent
  stderr-only line to form a false auth-death phrase.
- **R26-3 (MEDIUM, CONFIRMED)** — the `run\s+`codex\s+login`?\b` clause
  (backtick optional) was flagged as failing to match between a closing
  backtick and a following space/end-of-line, because a trailing `\b`
  asserts a word-character boundary and a backtick is a non-word character
  on both sides. Fix applied regardless of the paragraph below: the
  trailing `\b` is replaced with a negative lookahead `(?!\w)`, which
  asserts "not immediately followed by a word character" without requiring
  a *preceding* word character the way `\b` does — strictly at least as
  permissive, and a closer match to the actual intent ("don't let this
  clause bleed into a longer word"). Two isolated fixtures added,
  deliberately containing NO other `_AUTH_DEATH_RE` alternative's
  vocabulary (every pre-existing fixture that used this clause, e.g.
  `_CONSTRUCTED_AUTH_FAIL_STDERR`, also contains `"Not logged in"`, which
  matches independently and would mask this specific clause being broken):
  `test_guilt_run_codex_login_clause_without_backticks` and
  `test_guilt_run_codex_login_clause_with_backticks`.
  **Honest measured caveat** (anti-hallucination discipline, per §6/CLAUDE.md
  — a reviewer's claim is verified independently, not relayed as fact): I
  ran the actual compiled pre-fix pattern directly against several
  backtick-boundary inputs ("Run \`codex login\` to authenticate.",
  "Please run \`codex login\` now.", "run \`codex login\`" at end-of-string,
  before a period, and before a newline) and **did not reproduce the
  claimed non-match** — in every case tested, Python's `re` engine
  backtracked on the optional `?` quantifier (un-consuming the backtick)
  until `\b` could hold against the bare word `login`, so the clause
  matched under the OLD pattern too. I am not able to confirm the exact
  failure mode the review described reproduces in Python's `re` module on
  the inputs I tried. What is NOT in question: the fix is safe (strictly
  widens or leaves unchanged what matches, never narrows) and it closes a
  real, independently-verified gap — this specific clause had zero isolated
  test coverage before this round, so whether it worked was previously
  unproven either way. Recorded here rather than silently agreed with or
  silently dropped.

  **REFUTED IN MECHANISM (team-lead's independent confirmation, R26 GLM
  addendum GO message, 2026-08-15):** the team-lead ran the same probe
  independently — `re.search(r'\b(?:...|run\s+`?codex\s+login`?)\b', 'Run
  `codex login` to authenticate.')` — and reports the SAME result: it
  MATCHES (backtracking leaves the trailing optional backtick group empty
  and `\b` holds against the bare word "login"). Two independent probes,
  same non-reproduction, same conclusion: the reviewer's claimed non-match
  does not occur in Python's `re` module on the tested inputs. This
  strengthens, not weakens, the disposition above — the `(?!\w)` fix is
  kept as strictly non-narrowing hardening, and the closed
  isolated-test-coverage gap remains the real, independently-verified
  finding.
- **Doc-accuracy (same class as R25-6)** — the `except Exception:` branch's
  comment, added in R25-5, claimed the branch "reaps ... for e.g. a
  cancelled task" — false after the R26-1 fix (cancellation now has its own
  branch above it and never reaches this one); corrected in place to
  describe only what this branch now actually handles: any other exception
  out of `communicate()` (OSError variants, decode errors, etc.).

Fence unchanged at 11 files. All three fixes are code+test only, in the
same unpushed 4th commit as §30.6 (amended, not a new commit) once the
team-lead's go-ahead lands — this section was written and held per an
explicit sequencing instruction (a parallel GLM re-check on the R25 delta
was still in flight) to prevent an amendment from crossing a recomposition
mid-flight, a failure class this lane has hit five times. Suite counts,
RCs, and ruff status for this round are in the freeze report for this
THAW.

### 30.8 R26 GLM addendum — second-gate re-check completes the round (2026-08-15)

While §30.7 (agy's 3 findings) was fixed and held per the explicit
sequencing instruction above, the parallel GLM re-check on the same R25
delta landed: RED, 6 findings. One duplicates §30.7's R26-1
(`asyncio.CancelledError` bypassing the R25-5 catch-all) — no separate
action, already fixed there. The remaining 5, all orchestrator-confirmed
on disk:

- **F26-1 (HIGH, CONFIRMED) + F26-4 (MEDIUM, CONFIRMED) — unified into ONE
  design fix, not two patches.** §30.7's R26-2 fix (line-based stripping)
  still concatenated `_strip_known_lines(stdout, prompt) + "\n" +
  _strip_known_lines(stderr, prompt, stdout)` — putting the model's OWN
  partial answer back into the scanned text on a late failure. F26-1: a
  constructed example — stdout = "Your KITAS login has expired; you are
  unauthorized until renewal (401 on the portal)." with a clean, unrelated
  stderr — would still false-page, because that sentence was never
  stripped from ITSELF. F26-4: the `"\n"` join between the two
  independently-stripped streams was itself a seam `_AUTH_DEATH_RE`'s
  `\s+` alternatives (which match a newline) could bridge across. Fix,
  UNIFIED per the team-lead's design directive: (a) the scan now reads
  STDERR ONLY — stdout is never part of the scanned text at all, declared
  (not silently assumed) on the grounds that no measured evidence places
  `codex exec`'s own diagnostics on stdout (§30.4); (b) stderr is still
  stripped of known prompt/stdout LINES via `_strip_known_lines` (§30.7's
  R26-2 mechanism, unchanged) before scanning; (c) the scan itself now
  goes through a new `_auth_death_detected(*texts)` helper that searches
  each argument INDEPENDENTLY and never joins them with a separator —
  removing the concatenation seam structurally, not only for today's
  single-argument call site. Required tests added:
  `test_innocence_late_failure_partial_stdout_answer_mentions_401_does_not_page`
  (F26-1 scenario, end-to-end through `generate()`) and
  `test_guilt_boundary_formation_never_bridges_across_independently_searched_texts`
  (F26-4, a direct unit test on `_auth_death_detected` proving two
  fragments that WOULD combine if concatenated do not match when searched
  separately). All prior R25-3/R25-4/R26-2/R26-3 pins re-verified passing
  under the new design — none needed behavior changes (they were already
  stderr-scoped, or, for the boundary-adjacency test, safe by construction
  under the new stdout exclusion).
- **F26-3 (MEDIUM, CONFIRMED, doc-accuracy with security relevance)** —
  §30.3's restatements had drifted from the code across two rounds: (a)
  point 1's quoted argv shape omitted `--ignore-user-config`, the R25-1
  HIGH security fix — a reader rebuilding the client from this ADR alone
  would have re-opened the host-hook prompt leak; (b) point 4 still read
  "judged on stdout+stderr+exit-code together", the exact phrasing
  §30.6's R25-6 already corrected in the code/test docstrings but never in
  this sentence; (c) point 5 still said auth-death is detected "only after
  stripping the caller's own prompt text", describing the R25-3 shape, not
  the current stderr-only one. All three corrected in §30.3 above, and
  updated to describe THIS round's final design rather than re-fixed to
  the intermediate R25/R26-2 shape. The §30.4 code-block probe transcript
  was left as-is — it is a historical record of the literal R24 command
  actually run, and editing it to add a flag it never used would
  misrepresent the evidence — but is now annotated to say so explicitly
  and point to the current authoritative argv shape.
- **F26-5 (LOW, CONFIRMED, doc-accuracy)** — two related false claims:
  §30.4 and the code's point 7 docstring both said "both probe transcripts
  are quoted in the ADR §30" — false; verified (grep across the whole
  document plus a manual read of §30.1–30.7) that no stderr transcript is
  quoted inline anywhere in this ADR, only the RE-MEASURED one lives in
  the test fixture. The ORIGINAL R24 transcript (the one with the `hook:`
  lines — the actual evidence for R25-1) was overwritten by the re-measure
  and does not survive anywhere in this tree or in git history — confirmed
  via `git log -p` on the test file, which shows a single commit already
  containing only the re-measured content. Both claims corrected to state
  this honestly rather than fabricate a reconstruction of a transcript no
  longer on disk (anti-hallucination discipline, CLAUDE.md §6).
- **F26-6 (LOW, CONFIRMED, test-file accuracy)** — `test_codex_exec_client.py`
  had two section headers both claiming "Invariant 4" (the genuine one,
  output contract, and a duplicate on the `TestTimeout` class). Timeout is
  a deadline/output-shape behavior, not one of the module's 7 numbered
  invariants — the duplicate header relabeled to say so.

All ten of GLM's independently-verified R25 claims (argv flag, env
unification, 401 anchoring, vocabulary, OSError widening, the 59/222
suite counts) are unchanged by this round and were not regressed by the
stderr-only redesign.

Verification (all from repo root, after every fix above): `ruff check` +
`ruff format --check` on both `codex_exec_client.py` and
`test_codex_exec_client.py` — clean. `test_codex_exec_client.py` alone: 66
passed (was 64 pre-addendum: +2 for F26-1/F26-4), 0 failed. Full suite
counts and RCs for `backend/tests/llm/` and `scripts/bot/` are in the
freeze report for this THAW.

This addendum completes the R26 round per the team-lead's explicit
instruction — no further go-signal is needed; recomposition and the
freeze report follow this section.

### 30.9 R27 THAW round — final polish (2026-08-15)

Round-27 reviews on `0c8dd281c`: agy RED-1 (REFUTED), GLM RED-6 (F1
refuted — same claim as agy's, F2-F6 orchestrator-confirmed on disk; GLM's
review was truncated at `max_tokens` mid-F6 with no VERDICT line, treated
as RED by content per the mandate — F6's fix direction was unambiguous
regardless).

**Refutations, recorded rather than silently agreed with or silently
dropped:**

- **(a) agy's claim (HIGH) and GLM's F1 (same claim, hedged: "if auto,
  collapses to a consistency defect") — that two R26-2 pin tests
  (`test_innocence_echoed_401_unauthorized_prompt_does_not_false_positive`,
  `test_guilt_bare_common_word_stdout_does_not_mangle_stderr_scan`) are
  INERT without an explicit `@pytest.mark.asyncio` decorator — REFUTED,
  independently re-verified in THIS session, not merely relayed: grepped
  `apps/backend-rag/pytest.ini:17` → `asyncio_mode = auto` (confirmed on
  disk); ran the named test individually
  (`pytest backend/tests/llm/test_codex_exec_client.py::TestAuthDeathDetection::test_innocence_echoed_401_unauthorized_prompt_does_not_false_positive`)
  → 1 passed. Under `asyncio_mode = auto`, pytest-asyncio wraps every
  `async def test_*` regardless of an explicit marker — no marker was ever
  needed, and both tests were live and exercised in every prior suite run
  this round reported ("66 passed" etc. genuinely ran them, not silently
  skipped them).
- **(b) Residual consistency nit (not a bug, declared choice):** ~30
  explicit `@pytest.mark.asyncio` markers already exist elsewhere in this
  file against 2 unmarked async tests (the ones in (a)) — harmless under
  `asyncio_mode = auto` but genuinely confusing to any text-only reviewer
  who checks marker-presence as a correctness signal (as both agy and GLM
  independently did). Resolved in the cheaper direction: added the 2
  missing markers rather than a file-header comment, matching the file's
  own dominant convention rather than asking ~30 existing tests to
  conform to the minority shape.

**Confirmed fixes:**

- **R27-1 (GLM F3, LOW but real fail-open)** — `_strip_known_lines`'s
  original containment check (`stripped == kl or stripped in kl`) dropped
  a GENUINE diagnostic stderr line whenever it was merely a SUBSTRING of
  any known (prompt/stdout) line — symmetric to the R26-2 mangle bug, just
  on the opposite side of the equality/containment boundary. Measured
  example: prompt "why am I not logged in after midnight, is this
  urgent?" contains the substring "not logged in"; an independent, genuine
  diagnostic stderr line reading exactly "not logged in" was silently
  dropped before ever reaching `_AUTH_DEATH_RE`, silencing a real page.
  Fix: EQUALITY ONLY (`stripped in known_lines`, a set-membership check) —
  the measured wire shape never needed containment tolerance (prompt and
  answer are always echoed as their own complete, unwrapped line(s)).
  Tests added: `test_guilt_diagnostic_substring_of_prompt_line_still_pages`
  (the regression pin) and
  `test_innocence_genuine_echoed_line_still_dropped_under_equality_only`
  (confirms the original R25-3/R26-2 defusal still holds under
  equality-only). Full suite re-verified: all pre-existing R26-2 mangle
  pins (`test_guilt_bare_common_word_stdout_does_not_mangle_stderr_scan`
  and siblings) still pass unchanged — the fix narrows a false-drop
  condition that neither of those tests exercised.
- **R27-2 (GLM F4, LOW)** — `_resolve_codex_home` returned a RELATIVE path
  as-is on all three resolution tiers, re-opening the exact gate/child
  divergence R25-2 (§30.6) declared structurally impossible: `available`
  (the gate) resolves a relative `Path` against the CALLING process's cwd
  at property-access time, while the spawned child always runs from a
  fresh NEUTRAL TEMPDIR cwd (point 1) created and torn down per call — the
  same relative string meant two DIFFERENT directories depending on WHEN
  it was resolved. Fix: `.resolve()` on all three tiers (explicit
  constructor arg, `CODEX_HOME` env var, and — harmlessly, since it is
  already absolute — the `~/.codex` default). Test added:
  `test_guilt_relative_codex_home_resolves_absolute_and_agrees` —
  chdir's into a tmp dir, constructs the client with a RELATIVE
  `codex_home=`, and asserts `available` still resolves correctly, the
  resolved path is absolute, and the actual spawned child's env carries
  that SAME absolute path.
- **R27-3 (GLM F2, MEDIUM doc-accuracy, security-relevant class)** — two
  in-code restatements had drifted from the R26-addendum's stderr-only
  design (§30.8) without being updated: point 5's LEAD sentence still said
  "stdout+stderr are scanned", true only through the R25-3/R26-2
  intermediate design; and `CodexExecAuthError`'s docstring still said
  "(prompt-stripped) output". Both corrected in place, with the file's own
  established CORRECTED-marker convention, to describe the FINAL design
  (stderr-only, line-based-equality strip of prompt+stdout). The
  `_strip_known_lines` function docstring and its inline "equals, or is a
  substring of" phrasing were also brought in line with the R27-1 fix
  above in the same pass (avoiding re-introducing the doc/code drift this
  finding is about).
- **R27-4 (GLM F5, LOW doc)** — ADR §30.4's "Honest disclosure" paragraph
  said "Three real codex exec invocations were made in total", undercounting
  by one against the module docstring's own point 7 ("all four calls are
  declared") — the R25-1 re-measured probe (§30.6) was never folded into
  that count. It also lumped the accidental cwd-leak call together with
  the deliberately-scoped `CODEX_HOME` variant as "two ... diagnostic
  calls", contradicting its own "operator slip" framing of the first.
  Corrected to FOUR, with each of the four calls named and the
  accident/design distinction made explicit (§30.4 above).
- **R27-5 (GLM F6, MICRO)** — `tempfile.mkdtemp()` (creating the per-call
  neutral cwd, point 1) was called OUTSIDE every typed-exception wrapper in
  `generate()` — a raw `OSError` (disk full, `/tmp` unwritable, a TOCTOU
  permission change) would have propagated straight out, breaking this
  module's own fail-closed-with-typed-exceptions contract. Fix: wrapped,
  mapped to `CodexExecUnavailableError`, added to the `Raises:` docstring.
  Test added: `test_guilt_mkdtemp_failure_maps_to_unavailable` —
  monkeypatches `tempfile.mkdtemp` to raise, asserts the typed error and
  that the subprocess was never launched.

**Verification** (all from repo root, after every fix above): `ruff check`
+ `ruff format --check` on both `codex_exec_client.py` and
`test_codex_exec_client.py` — clean. `test_codex_exec_client.py` alone: 70
passed (was 66 pre-R27: +4 for R27-1×2/R27-2/R27-5), 0 failed. Full suite
counts and RCs for `backend/tests/llm/` and `scripts/bot/` are in the
freeze report for this THAW.

No further hold protocol for this round — fix, recompose, freeze, deliver,
HALT, per the team-lead's explicit instruction opening this round.

### 30.10 R28 reconciliation — current main, subscription proof, and residual boundary (2026-08-18)

This branch was reconciled with `origin/main` at
`993e4e868a6e8210328f69ccd136ca9d5c54d776`; the only merge conflict was the
mechanically maintained `docs/AI_ONBOARDING.md` test-count text, resolved to
current main. The feature fence is now ten files relative to main, not eleven:
that generated documentation file no longer differs.

The selected path remains `CodexExecClient`, authenticated by the operator's
existing ChatGPT subscription. The dormant `OpenAIResponsesClient` remains
unwired and receives no paid API key. Local `codex-cli 0.147.0` help was read
for the final subprocess contract. In addition to the existing neutral cwd,
read-only sandbox, stdin-only prompt, and `--ignore-user-config`, the fixed argv
now includes:

- `--ephemeral`, whose local help contract is to run without persisting session
  files;
- `--ignore-rules`, which prevents user/project `.rules` policy files from
  changing this adapter's execution contract.

The adapter now converts arbitrary post-launch `communicate()` failures into a
sanitized `CodexExecCommunicationError` only after killing and reaping the
child. The raw exception object and text do not cross the provider boundary.
Two static-analysis findings were also closed without broad refactoring:
finite timeout validation uses `math.isfinite`, and refusal-reason extraction
type-checks before comparing with the empty string.

Three R28 subscription calls and their limits are disclosed in §30.4. The
successful call was executed through the adapter, not a hand-assembled proxy
command, and observed exact sentinel output, no session-count increase, and no
sentinel residue under the searched `~/.codex` tree. The isolated-home calls
failed with `Not logged in`/HTTP 401, so the R24 Keychain inference is not a
current dependency and is explicitly superseded. These probes prove only the
observed surfaces; they do not prove universal non-persistence or unattended
production suitability.

The offline benchmark is now aligned to the selected provider. Its default
client is a narrow `CodexSubscriptionBenchClient` facade over
`CodexExecClient`; it never reads `OPENAI_WA_PROVIDER_API_KEY` and never arms
the dormant paid client. The facade records one subprocess attempt after a
successful response and leaves structured refusal as unknown rather than
inventing a boolean. Candidate calls remain strictly sequential, so maximum
provider concurrency is one.

The historical §7 V5 gap is closed at the tooling level. Default
`build_deid_corpus` behavior now accepts only structured JSONL turns carrying
canonical `user`/`assistant` roles plus a local conversation identifier, emits
only user targets, and attaches at most 12 prior independently redacted and
scanned role-labelled turns. Conversation identifiers never reach output or
logs. Any unsafe or unverified turn clears that conversation's accumulated
history; if the turn lacks an identifier, every accumulated conversation from
that source file is cleared because the gap cannot be attributed safely. Plain WhatsApp TXT
exports lack a trustworthy role field and therefore yield no default-mode
fixture; historical role-blind single-turn output requires the explicit
`--allow-legacy-single-turn` opt-in and is not promotion evidence.

The blind transcript now carries `history` separately from the current user
`prompt`; the text-only Codex provider receives the same structure encoded as
JSON beneath fixed benchmark instructions. The benchmark loader rejects legacy
fixtures that omit `role='user'` or an explicit role-aware `history` list. This closes role loss inside the
harness but does not reproduce production RAG/tool state, so it remains a
comparative conversational-safety bench, not proof of end-to-end Gemini parity.
No real WhatsApp export was processed in this PR.

`codex exec --output-schema <FILE>` was evaluated and deliberately not added.
The option constrains the model's final response shape; it does not provide
provider completion metadata, a refusal object, or a reliable truncation
signal. Adding a schema would therefore create false confidence without
closing the partial-output boundary. The provider continues to return text
only and leaves answer-quality/refusal evaluation to the offline benchmark.

The operational boundary is unchanged: no runtime import, flag, channel
wiring, WhatsApp traffic, deployment, or cutover is part of this PR. A future
runtime host remains an explicit architecture gate because Fly production does
not inherit this Air-M5 user's local Codex CLI or ChatGPT OAuth state.

R28 verification was run from the reconciled worktree with the backend virtual
environment active. One combined pytest process collected 481 cases (70 Codex
adapter, 163 dormant Responses adapter, and 248 corpus/benchmark) and exited
zero. Running the four suites together exposed and then closed a test-isolation
bug: backend tests left `DATABASE_URL` in the process, which made later corpus
tests attempt a dynamic CRM-name lookup against an unrelated database. The
corpus test module now removes `DATABASE_URL` and `PGURL` per test; production
code and its fail-closed CRM-name behavior are unchanged. `git diff --check`
and targeted Ruff `F,I` checks over the four script files also exited zero.
