---
date: 2026-08-19
domain: operations
client_case: kbli-navigator-phase2
discovered_by: "Fable session (Mini), on Zero's 2026-08-19 order («aggiorna il corner e comincia la phase 2 ma non con openclaw. studia /bot dove abbiamo messo direttamente chatgpt con abbonamento pro»)"
sources:
  - "apps/backend-rag/backend/llm/codex_exec_client.py on origin/main (the proven ChatGPT-Pro adapter: stdin-only prompt, --ephemeral --ignore-user-config --ignore-rules, neutral tempdir cwd, minimal env, auth-death taxonomy; its kill is proc.kill() only — line 553, no process group, see §2)"
  - "research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md on origin/main (§2 synchronous broker, §2.2 deterministic retrieval / allowlist package, §2.3 one finalization pipeline, §4 seat isolation)"
  - "research/operations/2026-08-18-bot-openai-shadow-wiring-plan.md on origin/main (§3 offline-evidence-first discipline, §3.5 no-session-persistence, §4 acceptance matrix)"
  - "memory: decision_wa_openai_provider_subscription_path_owner_ruling_2026_08_15 (owner ruling: OpenAI provider = ChatGPT Pro subscription via headless codex exec, NEVER a per-token API key)"
  - "Live harness on Pro 2026-08-19 (/bot lane): codex-cli 0.147.0 `Logged in using ChatGPT`; 3/3 role-aware multi-turn blind probes returned the exact synthetic sentinel (Terra/Luna/Sol, 6.6-8.6s) — falsifying OpenClawRunner.swift's own comment that codex exec is «agentic and unusable as chat» (spec §9 F1)"
  - "M5:/Users/balizero/Desktop/logo/kbli-navigator-app/Sources/OpenClawRunner.swift (read 2026-08-19 via ssh 100.110.186.116: dual-mode openclaw-local/ssh-mini, agent zantara-kbli, 120s timeout, no-shell argv, JSON from combined 2>&1)"
  - "data/source_documents/KBLI_2025_FINAL_CLEAN.json measured THIS session on this checkout: 25200/51101/79122 pma_status=TERBATAS (cap 49/49/0) while each record's intel_2026.zantaraOpener claims Open (79122 verbatim: «Nationally this carries PMA status: Open»); whole-record compact sizes 25.5/28.3/40.5 KiB, 262/1559 records >24KiB; reduced-package worst case 58.4KiB (61108, 64 per_skala rows = 528KiB raw)"
  - ".agents/skills/kbli-navigator/SKILL.md (Phase 2 original design of 2026-08-09: KBLIBrainClient → prod chat_kbli, ~25-question benchmark; superseded on the brain choice by this document)"
adversarial_review: codex
---

# KBLI Navigator Phase 2 — chat brain on ChatGPT Pro (`codex exec`), not OpenClaw

## 0. Mandate and route change

Zero, 2026-08-19 (verbatim): *«aggiorna il corner e comincia la phase 2 ma non con openclaw.
studia /bot dove abbiamo messo direttamente chatgpt con abbonamento pro»*.

This supersedes the brain choice of the 2026-08-09 Phase 2 design (which was
`KBLIBrainClient` → prod `chat_kbli` over HTTP, awaiting GO). The GO has now arrived **with a
route change**: the chat brain becomes **ChatGPT Pro via headless `codex exec`**, mirroring the
/bot lane's proven adapter pattern. What Phase 2 keeps from the original design: the
benchmark against the old brain, graceful degradation where the brain is absent, and the
current code-card context riding with the question.

Two constraints inherited unchanged from the owner's standing rulings:

- **Subscription path only** — the seat is the ChatGPT Pro subscription consumed through the
  `codex` CLI. No `OPENAI_API_KEY`, no per-token endpoint, ever
  (`decision_wa_openai_provider_subscription_path_owner_ruling_2026_08_15`).
- **BKPM variant keeps chat in the product** (Zero 2026-08-09: «we need it perfect at
  answering KBLI questions») — but this design does **not** clear BKPM chat for hand-off:
  §6 states exactly what stands between here and that (isolation + seat + G-P1), as owner
  decisions, not assumptions.

**Scope of the SHIP claim, stated up front:** this document + the P2a/P2b increments clear
the chat for the **INTERNAL fleet** (the operator's own Macs). BKPM remains gated.

## 1. Ground — what is proven, this turn or dated

- **The adapter pattern works as chat.** `codex_exec_client.py` (merged #4216, deployed
  dormant) is the reference implementation; on Pro the live blind harness (2026-08-19) passed
  3/3 role-aware multi-turn probes across `gpt-5.6-terra`/`luna`/`sol` in 6.6–8.6 s — with
  history **serialized into the prompt**, which is the same mechanism §3 uses. The old thesis
  inside `OpenClawRunner.swift` («codex exec is agentic and unusable as chat») is falsified
  by measurement.
- **The current chat is the weakest part of the app.** OpenClaw `zantara-kbli` reached over
  `ssh mini` from M5/Pro: fleet-only reachability, no retrieval, cold KBLI questions get
  "I don't have FONTI" refusals, and on a BKPM Mac (no ssh keys) it fails with an Italian
  error. This is blocker #1 of the BKPM hand-off.
- **The dataset is already in the bundle** (all 1,559 canonical records + bilingual search
  index). Deterministic grounding therefore needs **no network and no server**.
- **⚠️ The dataset contradicts itself on the exact trap codes — measured this session.**
  `25200`, `51101`, `79122` carry `pma_status=TERBATAS` (caps 49/49/0) while each record's
  own `intel_2026.zantaraOpener` editorial text claims Open (79122 verbatim: *«Nationally
  this carries PMA status: Open»*). Consequence for THIS design: the package is an allowlist
  that **excludes all editorial prose** (§3). Consequence for the corner: a new red row —
  `zantaraOpener` is rendered by `apps/mouth/src/app/kbli/[code]/page.tsx:1050` (from the
  gold store) and indexed by `index_kbli_gold_content.py`, so whether this contradiction is
  client-visible on those surfaces needs its own verification lane; not cured here.
- **Record sizes forbid "send the full record".** Whole-record compact JSON: 262/1559 records
  exceed 24 KiB; `79122` is 40.5 KiB; `61108` is ~532 KiB raw (64 `per_skala` rows). §3's
  reduction is therefore measured, not stylistic.
- **Seat availability is per-machine and measured, not assumed**: Pro = logged in
  (codex-cli 0.147.0, verified 2026-08-19; `~/.codex/auth.json` present, 0600). M5 =
  probe-positive, measured 2026-08-19 (codex-cli 0.147.0 at `/opt/homebrew/bin/codex`,
  `~/.codex/auth.json` present 0600 — live entitlement proven at first real call, per the
  probe-is-a-pre-filter rule). Mini = AUTH_DEAD (proprioception 2026-08-19) and headless
  anyway. BKPM Mac = no seat, no ssh keys.
- **The reference adapter's kill is NOT a process-group kill.** `codex_exec_client.py:553`
  calls `proc.kill()` and never creates a process group — the broker spec's §2 diagram says
  "kill process group on expiry" but the deployed implementation does not deliver it. The
  Swift runner must do better (§2), and this spec-vs-impl gap is handed back to the /bot
  lane via a modus PENDING-ARMS row **opened in this same PR** — quoted so the pairing is
  checkable in the diff (R3-7): the row opens `opened 2026-08-19 (kbli-navigator Phase-2
  design session, Mini) | **codex_exec_client.py promises no process-group kill …**` in
  `.claude/skills/modus/PENDING-ARMS.md`; a reviewer of this PR verifies both files move
  together. (A refuter reading `origin/main` will not see it until the merge.)

## 2. Design — `KBLICodexRunner` (Swift), porting the adapter invariants and exceeding them where measured

A new `Sources/KBLICodexRunner.swift` replaces `OpenClawRunner` in the chat flow.

| Invariant | Origin | Concrete rule |
| --- | --- | --- |
| stdin-only prompt | W115 / codex_exec_client | argv ends with `-`; the prompt (preamble + package + history + question) is written to stdin and never appears in argv (`ps`-readable) |
| fixed argv prefix | #4216 | `codex exec --sandbox read-only --skip-git-repo-check --ephemeral --ignore-user-config --ignore-rules -m <model> -` — `--ephemeral` closes local session persistence (wiring-plan §3.5) |
| neutral cwd | codex_exec_client | per-call temp directory, removed after the call |
| minimal child env | codex_exec_client + measured gate | explicit env only: `PATH` **including `/opt/homebrew/bin`** (codex is a Node shebang script — re-measured this session: without it, `env: node: No such file or directory`), `HOME`, optional `CODEX_HOME`; nothing else inherited |
| timeout + **group** kill, on every interceptable exit path | broker-spec §2 (spec), NOT the Python impl | spawn codex in its **own process group** (POSIX spawn attrs / `setpgid`); `killpg` the group on timeout **and on cancellation** (user closes the chat/view, Swift `Task` cancelled, `applicationWillTerminate`) — the same reap path everywhere; tempdir removed only after the process is reaped, never under a live process (R2-8). **Declared residual + launch sweep (R5-2, identity hardened per R6-2)**: a `SIGKILL`/crash of the app itself runs no handler and the detached group survives — no in-process design prevents that; mitigation: the runner writes a durable **intent record** (the per-call tempdir path) BEFORE `posix_spawn`, completes it into a job record (pgid + leader pid + leader start-time) after spawn, and removes it at reap — so a crash in the spawn→record window (R7-1) leaves a recoverable intent: the launch sweep treats an intent without completion as "a spawn may have happened" and hunts processes whose cwd is inside that intent's tempdir. Every app launch sweeps the namespace. The kill decision uses the DURABLE job identity, not the bare pgid: enumerate live processes in the recorded pgid and `killpg` only if at least one has its cwd inside the recorded per-call tempdir — which correctly kills a LEADERLESS group (grandchildren keep the job cwd) and correctly spares a recycled pgid now owned by someone else's codex (different cwd). Declared residual: a grandchild that `chdir`s away evades the identity check and survives until it exits on its own. Orphan window = call timeout + time-to-next-launch, stated as such. P2a tests: grandchild survives neither timeout nor cancellation nor ordinary app exit; launch sweep kills a planted LEADERLESS orphan group; sweep spares a same-pgid process whose cwd is elsewhere (the recycled-by-another-codex case); crash injected at EACH record transition (pre-intent, intent-no-spawn, spawn-no-completion, completion-no-reap) leaves no unkillable orphan and no false kill. This deliberately exceeds `codex_exec_client.py`, which only `proc.kill()`s the direct child (line 553) |
| output bounds + draining | wiring-plan §4 matrix | stdout and stderr read concurrently (Swift `readabilityHandler`, never sequential waits), each capped at 256 KiB — beyond the cap the call is failed as `oversized`, never truncated-and-served |
| single-flight | broker daemon rule | one in-flight chat call per app instance; the send control is disabled while a call runs |
| availability probe | codex_exec_client `available` + finding 13 + R4-4 + R5-3 | **per SPAWN, not per chat-open** (a per-open check leaves a TOCTOU window in which Homebrew swaps the binary under an open chat): before every call the runner resolves the binary through its symlink chain to the real file (on Pro `/opt/homebrew/bin/codex` IS a symlink into the global Node module — measured by the round-6 refuter), re-reads `codex --version`, requires it **exactly equal to the benchmark manifest's version** (fail-closed on drift, with a message to restore the pinned version or re-run the §8 new-brain suite — a `≥` floor would let an upgrade serve under a benchmark it never passed), and captures the real file's identity (device, inode, mtime, size). **Version check, re-stat, and `posix_spawn` all target that SAME resolved real path — never the symlink and never a PATH lookup (R7-2)**, so a Homebrew symlink retarget between probe and spawn changes nothing the spawn sees. Immediately before `posix_spawn` the runner re-stats that real path and fails closed on any identity change (R6-3) — shrinking the TOCTOU window from "probe→send" to "stat→spawn". Declared residual: that final microseconds-wide window on the real file itself is irreducible without `fexecve`, which macOS does not provide; it is stated, not hidden. Auth: non-empty `$CODEX_HOME/auth.json` (default `~/.codex/auth.json`), also checked per spawn. P2a guilt tests: swap between chat-open and send; swap immediately after the version check; and a symlink RETARGET (codex→B while A is unchanged) — all fail closed or provably execute the verified file A. The probe is a cheap pre-filter only — the authoritative signal is the first real call's typed failure: model-entitlement or flag rejection surfaces as a typed process error with guidance, never a crash. Declared residual (R4-4): `gpt-5.6-terra` is a hosted alias no manifest can freeze — provider-side drift is covered by an operational re-benchmark policy (new-brain suite re-run on every codex CLI upgrade and as a quarterly canary), not by a false claim of frozenness |
| error taxonomy | codex_exec_client + finding 11 + R2-7 | typed states, classified in this order on non-zero exit: (1) `auth_death` — stderr regex after whole-line stripping of BOTH the echoed prompt AND the stdout echo (the adapter strips both, `codex_exec_client.py` ~line 1020, precisely so a partial answer quoting "not logged in" cannot fake an auth death — v1 of this doc under-described that and would have regressed it); (2) `quota_throttle` — only stderr matching a pinned recognized-throttle set (seeded conservatively, replaced verbatim by the /bot S1.5 measurement when it lands); (3) `process_error` — everything else, INCLUDING flag/entitlement rejection: unknown is never classified transient. **The app never auto-retries any class** — single-flight, retry is a user action; classification drives only the message shown. Raw stderr is never shown in the UI and never logged |
| model roster | #4216 | `gpt-5.6-terra` serves; `sol` is used only as the benchmark judge (§8); `luna` not used |

**Host isolation — the honest boundary (refuter P0-1).** `--sandbox read-only` blocks
writes, not reads: a codex process can read the invoking user's whole home (ssh keys,
repos, tokens) and is network-connected to OpenAI. The /bot broker cures this with a
dedicated login-less OS user; a desktop GUI app cannot cheaply `sudo -u` per call.
Disposition, split by audience:

- **INTERNAL fleet (Pro/M5)**: residual **accepted and documented** — on these machines the
  operator already runs `codex` interactively every day with identical read scope and the
  same seat; the Navigator adds a new *invocation path*, not a new *capability*, and its
  inputs are the operator's own typed text plus bundled public records. This acceptance is
  recorded here and in the corner; it is not silence.
- **BKPM Mac**: this residual is **not acceptable** (third-party staff + a Bali Zero seat on
  third-party hardware). BKPM chat therefore REQUIRES the isolation decision in §6 (dedicated
  OS user or equivalent) before any seat is installed. The app's honest-offline state (§4) is
  the default until then.

Non-goals, stated so nobody re-imports them: **no broker, no `broker_jobs`, no Fly leg, no
new server surface**. The /bot broker exists because WhatsApp serving needs fences, PII
lifecycle and fail-off inside a DB claim; the Navigator's caller is a human at the machine.
The correct borrowing is the adapter invariants and the deterministic-package discipline,
not the transport.

## 3. Grounding — deterministic context package, allowlist-only, measured caps

Port of broker-spec §2.2's discipline to the local dataset. The package is built **in-app,
deterministically, with zero LLM calls** (P2a carries this as an executable assertion, same
as the broker's S2 criterion). Contents, in fixed priority order:

1. **Current code card** — the record of the page the user is on (if any), reduced per the
   allowlist below.
2. **Explicit code references — capped at 3 (R6-1)** — 5-digit tokens in the question that
   exactly match a `kode_kbli_2025`, looked up in the bundled dataset. A question naming
   MORE than 3 codes gets the honest "please narrow the comparison to at most 3 codes"
   state and no call is made — an unbounded explicit set plus card plus anchors is
   arithmetically unsatisfiable under the cap, so the bound is declared instead of
   discovered at overflow. The full priority ladder is total and has a declared victim
   order: question codes (≤3) > current card > session anchors (≤4, reserved slice) —
   under pressure anchors drop first (declared in the preamble), the card shrinks next
   (byte-budgeted rows), question codes are never dropped. P2a tests the refuter's exact
   scenario: worst card + 4 anchors + 3 explicit codes fits; a 5-code question gets the
   narrow state.
3. **Search-term matches** — up to 5 records from the app's existing bilingual search index,
   using that index's own normalization (the same lowercase/diacritic-fold matching the
   search UI already applies — the chat retriever IS the search index, not a new engine),
   ranked by the index's score, deduplicated by code, minimum-score threshold equal to the
   search UI's display threshold. P2a carries a retrieval-recall test: every benchmark
   question (§8) must retrieve its target code(s) through this exact pipeline.
4. **History** — the last ≤12 turns of the current chat, serialized with explicit role labels
   (`USER:` / `ASSISTANT:`), the mechanism the 2026-08-19 Pro harness proved 3/3. This is the
   multi-turn contract: `--ephemeral` gives codex no memory, the package carries it.
   **Referent continuity (R3-3, hardened per R4-2, bounded per R5-1)**: codes cited in the
   retained history become **session anchors, capped at the 4 most recent distinct codes**
   — an unbounded "every history code survives" promise is arithmetically impossible under
   a 64 KiB cap (a dozen ordinary records exceed it on scalar fields alone), so the
   contract is bounded and honest instead: the 4 newest anchors get a **reserved 16 KiB
   slice**, older anchors drop with a declared preamble note plus the instruction that,
   when asked about a dropped referent, the model must ask the user to re-name the code
   (which then re-enters as an explicit question reference — priority: question codes
   outrank the current card, and the card shrinks via the byte-budgeted selector). P2a
   tests: the combination worst-case card × explicit reference × anchors, AND a saturation
   case with 12 history codes asserting the 4 newest survive and the rest are
   declared-dropped. Deterministic (regex over history), zero LLM.
5. **Honest-abstain preamble** — answer ONLY from the provided records; a fact not present ⇒
   say the navigator does not carry it; answer in the user's language (EN/ID); never invent
   risk/licensing rows; cite the KBLI code(s) used; regulatory facts come only from the
   structured fields, never from free prose.

**Field allowlist — RECURSIVE (refuter P0-2/P1-4, R2-2/R2-3 — measured cure).** The
allowlist is a **nested schema**, not a top-level key list. Top level: `kode_kbli_2025`,
`judul`, `uraian`, `ruang_lingkup`, `sektor_id`, `pma_status`, `pma_max_asing`,
`pma_kondisi`, `pma_nota`, `pma_verification_status`, `per_skala`, `l4_bali`,
`bps_2020_ancestors`, `status_mapping`. Nested objects serialize only named sub-fields
(e.g. `per_skala` rows: `skala_usaha`, `kategori_risiko`, `jangka_waktu`, `scope_uraian`,
`perizinan`, `persyaratan`, `kewajiban`; `l4_bali`: `verdict_state`, `blocked`, `status`,
`reason`, `moratorium.{rule,effective,source}`). The builder **fails closed on unknown
nested keys** (a schema-snapshot test in P2a): a field added to the dataset tomorrow breaks
the build test, it never serializes silently. **Excluded by construction**: the whole
`intel_2026` object (`zantaraOpener` editorial prose — proven contradictory on 79122),
`per_skala_legacy`, `_source*` provenance internals, and every digest/adjudication metadata
inside nested objects.

**Cross-field consistency gate (R4-1 — verified and censused this session).** The
structured fields can contradict EACH OTHER, not only the editorial prose: `50111` and
`50112` carry `pma_max_asing=49` while their own `pma_kondisi` reads *"Hanya PMDN (100%
domestik)"* — a class sweep over all 1,559 records found **exactly these 2**. A gate that
certifies "49% == pma_max_asing" would bless an answer another allowlisted field calls
false. Cure: the package builder runs a build-time cross-field consistency sweep (this
class check, extensible); a record that fails it serializes with `pma_conflict: true` IN
PLACE OF its ownership fields, the preamble instructs "this record carries a declared
internal conflict on the foreign-ownership axis — do not answer that axis, point to the
code page and the team", and the post-generation gate **rejects any % ownership claim on a
conflict-marked record** (fail-closed on both generation and verification). The dataset
cure itself (adjudicating which field is right for 50111/50112) is a separate corner lane,
recorded there — this design refuses to serve the conflict, it does not resolve it.

**Semantic collision cure (R2-2 — verified this session).** `l4_bali` on 79122 says
`blocked: false` / "not blocked by moratorium" while `pma_max_asing=0` — two different
axes that a model WILL conflate if the package presents them as siblings. Cure: `l4_bali`
serializes under the renamed key **`bali_moratorium_status`**, and the preamble states:
*"`bali_moratorium_status` concerns ONLY the Bali moratorium / risk-scale axis; foreign
ownership comes ONLY from the `pma_*` fields — 'not blocked' does NOT mean open to foreign
capital."* P2a carries the guilt test: "Can a foreign company open 79122 in Bali?" must
answer 0% foreign ownership, never "open".

**Size discipline — TOTAL prompt budget (refuter P0-3, R2-4/R2-5 — measured, not
asserted).** Typed reductions, matching the fields' real shapes (`ruang_lingkup` is an
array on all 1,559 records — census this session — never a string): scalar regulatory
fields always whole; `uraian` (string) clips at 4 KiB with an explicit
`…[truncated — full text on the code page]` marker; `ruang_lingkup` serializes whole (the
measured worst case below already includes uncapped arrays); `per_skala` rows are selected
**question-matched first** (deterministic keyword match of the question against
`skala_usaha`/`scope_uraian`), then physical order — but the selector is
**byte-budgeted, not row-counted (R3-2)**: rows accumulate in priority order until the
record's byte budget is reached (measured why: 46710 has 4 rows matching "bahan bakar gas
cair" at 20.8 KiB each = 83.0 KiB — a 6-row count cap alone breaks the package cap), with
per-row caps on the large list sub-fields (`persyaratan`, `kewajiban`) carrying declared
truncation markers, and the whole reduction serialized as
`{rows_included, rows_total, note: "full table on the code page", rows: […]}` — a
**declared** reduction, never a silent one. The P2a size test is **query-adversarial**: it
includes the 46710 case and a sweep that, for every record, queries the terms of its
largest rows. Measured over all 1,559 records this yields a
record worst case of **58.4 KiB** (61108). The budget is TOTAL, not per-record: package
≤ 64 KiB (whole lowest-priority records drop first, never partial ones, and the preamble
names the included codes — the current code card is never the one dropped), history
≤ 16 KiB (oldest whole turns drop; each stored assistant turn is clipped to 4 KiB at
storage time), question ≤ 4 KiB (longer input gets the honest "please shorten" state, no
call is made), fixed preamble ~2 KiB — hard total < 90 KiB asserted by a P2a test that
exercises worst-record + full history + max question together, not records alone.

**Post-generation gate (refuter P1-7, R2-6) — prompt instructions are not the only
control, and the % check binds number to code.** Before display, a deterministic in-app
check on the returned text: (a) every 5-digit code cited in the answer must be present in
the package (else rejected); (b) every sentence containing a `%` ownership figure **must
also name a KBLI code, and the figure must equal THAT code's `pma_max_asing`** — an
unnamed-% sentence or a mismatch rejects (this closes the exact multi-record bypass:
package {51101→49, 79122→0}, answer "79122 allows 49%": 49 exists in the package but not
on 79122 → rejected). The pairing rule is defined, not implied (R3-6): **exactly one code
and one `%` figure per clause** — a clause with multiple codes AND multiple figures
("…0% and 49%, respectively") is rejected as unverifiable, and the preamble instructs one
code-cap statement per sentence, so a false-reject costs the model a rephrase, never the
user a wrong fact; (c) the preamble mandates ownership caps be expressed as digits+`%`, and the gate
**normalizes every numeric percentage surface form before checking (R4-5, R5-4)**: the
answer text is **NFKC-normalized first** (which folds fullwidth `％` and friends into
`%`), then the numeric token is parsed **maximally and atomically** — the full decimal
number adjacent to the sign, so `49,0%` / `49.0%` parse as the number 49.0 and compare
numerically against the record cap (they can never be read as a trailing `0%`); digit
forms followed by `%`, `٪`, `percent`, `per cent`, or `persen` (case- and
whitespace-insensitive) all canonicalize to the same claim and enter check (b), while
spelled-out number forms (`forty-nine percent`, `empat puluh sembilan persen`; EN/ID word
lists pinned in the builder) are rejected as unverifiable rather than skipped. P2a guilt
tests include `49 percent`, `49 persen`, `49,0%`, `49.0%`, `49％` (U+FF05) and `٪`. Rejection shows an honest "the assistant produced an unverifiable answer — try
rephrasing" state; the raw text is never displayed. Declared residual: the gate is
syntactic — semantic fabrication is what §8's zero-fabrication floor and the abstain
preamble exist for.

## 4. What replaces what — migration inside the app

- Chat flow: `ChatView` → `KBLICodexRunner` (new); `OpenClawRunner` stays compiled but
  unreachable behind a build-time constant until the §8 benchmark gate passes, then its path
  is **deleted** (a dead dual path is W84-class drift waiting to happen).
- The fallback chain of the original design ("HTTP → legacy ssh → offline message") becomes:
  **seat present → codex; seat absent/auth-dead → honest offline message** ("Chat requires
  the assistant seat on this Mac — the navigator's pages remain fully available."). The
  message names no host, no vendor, no internal infrastructure. No silent fallback to a
  weaker brain: a wrong-but-confident fallback answer is exactly what the north star forbids.
- **The BKPM variant is policy-gated CLOSED, not seat-gated (R3-1 — fail-closed by
  construction).** Seat presence must never enable chat on a BKPM machine: BKPM staff
  logging into a personal codex seat for unrelated work would otherwise switch our chat on
  inside their home directory, bypassing every §6 gate. The `BZVariant=bkpm` build therefore
  ships chat DISABLED by build-time policy regardless of seat availability; enabling
  requires an owner-provisioned enablement artifact, checked in addition to — never instead
  of — the seat probe. **The marker is not a bearer token (R4-3)**: its signed claims bind
  the specific machine (hardware UUID), the app build, an expiry (≤90 days — re-issuing is
  the re-attestation cadence), and the G-P1 verification date; the runner validates every
  claim, so a marker copied to a different Mac, an expired marker, or one predating a G-P1
  re-check is dead. Revocation = deletion or expiry. The INTERNAL variant remains
  seat-gated. P2a guilt tests: BKPM build + valid auth.json + no marker ⇒ offline; valid
  marker for machine A presented on machine B ⇒ offline; expired marker ⇒ offline.

## 5. Per-machine consumption

| Machine | Seat today | Phase 2 behavior |
| --- | --- | --- |
| Pro | logged in (measured 2026-08-19) | full chat — primary dev/QA machine |
| M5 | probe-positive (0.147.0 + auth.json, measured 2026-08-19) | full chat — implementation machine (app repo lives here) |
| Mini | AUTH_DEAD + headless | not a chat target (server role) |
| BKPM Mac | none | honest offline message until the §6 owner decisions |

## 6. §Solo-operatore — decisions only the owner can make

1. **BKPM chat enablement** — now explicitly a **bundle** of three gates, none assumed:
   (a) isolation: a dedicated login-less OS user (or equivalent measured isolation) on the
   BKPM Mac so the seat process cannot read staff/home data — the §2 INTERNAL residual
   acceptance does NOT transfer; (b) the seat itself: whose account, cost, credential on
   third-party hardware; (c) G-P1: the seat's "Improve the model for everyone" toggle
   verified OFF **at marker issuance and at every re-issue** — the §4 marker attests a
   point-in-time check, not a continuously monitored state (R5-5): a toggle flipped back
   the day after issuance stays undetected until the ≤90-day expiry forces re-attestation.
   That intra-window residual is part of what the owner accepts in this bundle, stated
   here rather than hidden; a shorter expiry is the knob if 90 days is too long. Default
   remains honest-offline; the data pages are already the hand-off deliverable.
2. **M5 codex login** if the P2a verification finds the seat absent (`operator[gui]`).
3. **Fleet seat identity** — today the personal ChatGPT Pro; acceptable for internal use per
   the 2026-08-15 ruling, with G-P1 verification still open.

## 7. Privacy posture

KBLI questions are public regulatory data by design; the deterministic package contains only
bundled public records. Residual, stated plainly: the free-text box accepts anything, and
whatever is typed reaches the ChatGPT seat — the in-UI note ("do not paste client personal
data — this chat is for KBLI regulatory questions") is **advisory, not preventive**; no DLP
is built in Phase 2. That is the reason §2 confines the SHIP claim to the INTERNAL fleet,
where the typist is the operator under the same UU PDP duties as in any other tool on those
machines. For BKPM the advisory control is insufficient by itself — folded into §6's gate
bundle. The /bot lane's DLP work, when it lands, is reusable here; it is not a Phase 2
dependency for INTERNAL.

## 8. Benchmark — the gate that lets OpenClaw die

- **Corpus**: ~25 KBLI questions from the 78-question team test + the cured traps
  (51101→49% foreign cap, 79122→0%, 25200, the moratorium class, paid-up 2.5 mld
  per-KBLI-per-location, SLHS certification), in EN and ID, plus ≥3 out-of-corpus probes
  that MUST produce abstention. **Every question is classified at corpus-freeze (R2-1)** as
  either `structured` (answerable from the §3 allowlisted fields — verified against the
  dataset at classification time, not assumed) or `known-gap` (the fact is NOT in the
  allowlisted fields — measured this session for the 2.5-mld minimum-investment rule: the
  only "paid-up" mentions in allowlisted fields are ownership-cap conditions like 65111's
  80%-of-paid-up-capital, not the BKPM 5/2025 investment floor). For `known-gap` questions
  the CORRECT answer is the declared abstention with a pointer — a §3-grounded brain cannot
  and must not answer them from thin air, and grading them as accuracy failures would make
  §3 and §8 mutually unsatisfiable.
- **Runs**: old brain (OpenClaw via ssh, where reachable) vs new brain (KBLICodexRunner),
  same questions, same machine.
- **Scoring**: against the canonical **structured fields only** (the allowlist of §3 — the
  measured 79122 contradiction proves editorial prose cannot be trusted as ground truth, so
  it is excluded from judging exactly as from serving). Fabrication detection is
  **deterministic-first, judge-second (R3-5)**: (1) a machine check runs on 100% of answers
  in 100% of runs — every code→figure tuple extractable from the answer (the §3 answer
  format mandates extractable digits+code form) is verified against the structured fields;
  any violation is a fabrication, no sampling involved; (2) judge = `sol` with the relevant
  structured record inline and a fixed rubric (correct / wrong / fabricated / abstained) for
  the claims the extractor cannot see; generator≠grader holds (`terra` serves, `sol`
  judges against supplied fields, not its own knowledge); (3) session hand-check: 100% of
  extractor-or-judge-flagged answers + a fixed 20% random sample. Declared residual: a
  prose-only fabrication that evades both the extractor's tuple grammar and the stochastic
  judge in an unsampled answer is not provably caught — the floor below is therefore
  "zero fabrications across the deterministic check (exhaustive) and the judged+sampled
  layers", stated as what it measures, not more.
- **Gate — absolute floors, not only relative (refuter P1-8, R2-1)**: (i) zero fabricated
  regulatory facts, in ANY run; (ii) accuracy ≥ 80% on the `structured` set; (iii) wrongful
  abstention ≤ 10% of the `structured` set; (iv) 100% declared abstention on `known-gap`
  questions AND the out-of-corpus probes; (v) new ≥ old on accuracy. Each question runs
  **3 times** (generator and judge are stochastic — R2-9): accuracy scores by majority,
  fabrication fails on any single run.
- **Bound to the artifact, not the air (R2-9, R3-4)**: the report records a manifest —
  app-repo commit, bundled dataset SHA-256, `codex --version`, serving model id, corpus
  SHA-256, judge rubric + run count. The ordering resolves the A-vs-B commit gap the naive
  sequence had: (1) candidate build **A** (OpenClaw compiled-but-unreachable) runs the FULL
  benchmark — both brains; (2) on green, the OpenClaw deletion produces build **B**;
  (3) the **new-brain suite re-runs on B** (no old-brain runs needed — the comparison is
  between brains, the floors bind to the installed artifact) and B is manifested;
  (4) the fleet installs exactly B, verified by app commit + dataset SHA. A later rebuild
  re-runs the new-brain suite or does not claim the benchmark.

## 9. Increments

| Step | Content | Where |
| --- | --- | --- |
| P2a | `KBLICodexRunner.swift` + package builder + tests (argv shape, stdin-only, env minimality, process-group kill with grandchild, output caps, single-flight, availability probe incl. version pin, auth-death classification on fixture stderr, zero-LLM builder assertion, ≤64KiB over all 1,559 records, retrieval-recall on the benchmark corpus, post-generation gate guilt+innocence) | app repo on M5, build farm on Pro |
| P2b | benchmark corpus + runs + report; gate decision | Pro (seat present) |
| P2c | OpenClaw path deletion + fleet install (INTERNAL) + §6 BKPM bundle execution when ruled | fleet |

The app repo has **no git remote** (local commits are complete actions there); the monorepo
carries this design, the corner update, and later the benchmark report.

## Adversarial review

Refute-stance review by **Codex GPT-5.6 sol (xhigh), run live on Pro 2026-08-19** (seat
`Logged in using ChatGPT`, codex-cli 0.147.0; prompt = full v1 document via stdin).

- **Round 1 on v1: VERDICT BLOCKED — 13 findings (3×P0, 9×P1, 1×P2).** Every load-bearing
  claim was independently re-measured by the session before folding (W65 — the refuter's
  file citations pointed at Pro's gitignored zombie copy of the dataset, but all three P0s
  reproduced on the canonical `data/source_documents/KBLI_2025_FINAL_CLEAN.json` of this
  checkout): P0-1 sandbox≠host-isolation → §2 split disposition (INTERNAL accepted residual
  / BKPM hard gate); P0-2 dataset self-contradiction on 25200/51101/79122 (zantaraOpener
  "Open" vs TERBATAS — 79122 quote verified verbatim) → §3 allowlist excludes `intel_2026`,
  + new corner red row for the render surfaces; P0-3 24KiB cap incompatible with full
  records (measured 262/1559 over, 79122=40.5KiB, 61108=532KiB) → §3 measured reduction,
  cap 64KiB, worst case 58.4KiB, per-record CI test; P1-4 no field allowlist → §3; P1-5
  multi-turn absent → §3.4 serialized role-labelled history (mechanism already proven 3/3 on
  Pro); P1-6 retrieval underspecified → §3.3 pinned to the existing search index + recall
  test; P1-7 prompt-only factual control → §3 post-generation deterministic gate (residual
  declared); P1-8 relative-only benchmark gate → §8 absolute floors; P1-9 judge shares the
  defective evidence → §8 judges against structured fields only + fixed spot-check protocol;
  P1-10 "process-group kill" was not actually in the reference (verified: `proc.kill()` only,
  line 553; no setpgid) → §2 real group-kill with grandchild test + gap handed to /bot via
  PENDING-ARMS; P1-11 missing bounds → §2 output caps, concurrent draining, single-flight,
  quota-vs-auth taxonomy deferred to /bot S1.5 measurement; P1-12 advisory-only privacy →
  §7 concession + SHIP claim confined to INTERNAL, BKPM gated in §6; P2-13 availability≠
  compatibility → §2 version pin + probe demoted to pre-filter.
- **Round 2 on v2: VERDICT BLOCKED — 10 new findings (2×P0, 7×P1, 1×P2), three of them twin
  bugs born from the round-1 fixes (the W84 class the review prompt explicitly hunted).**
  Load-bearing claims re-measured before folding: R2-1 the 2.5-mld benchmark trap is
  unanswerable from the allowlist (verified: the only "paid-up" hits in allowlisted fields
  are ownership-cap conditions, e.g. 65111) → §8 corpus classification `structured` vs
  `known-gap`, floors computed per class; R2-2 `l4_bali` reintroduces an "open"-reading on
  79122 inside the allowlist (verified: `blocked:false`, "not blocked by moratorium",
  `verdict` present, while `pma_max_asing=0`) → §3 semantic rename `bali_moratorium_status`
  + preamble axis note + guilt test; R2-3 allowlist not recursive → §3 nested schema +
  fail-closed unknown-key test; R2-4 64KiB covered records only → §3 TOTAL budget
  (package/history/question/preamble, <90KiB, worst-case combined test); R2-5
  `ruang_lingkup` is an array on all 1,559 (verified by census — the v2 "prose clip" was
  type-wrong; the 58.4KiB worst case already included whole arrays, so the measurement
  stands) → §3 typed reductions + question-matched `per_skala` selection; R2-6 the % gate
  accepted cross-record attribution → §3 sentence-level code-bound matching + spelled-out
  percentage rejection; R2-7 taxonomy contradiction + stderr-stripping regression vs the
  adapter (which strips prompt AND stdout) → §2 ordered classification, unknown =
  `process_error` never transient, no auto-retry of any class; R2-8 cancellation/app-exit
  uncovered → §2 group-kill on every exit path + tempdir-after-reap + tests; R2-9 benchmark
  unbound from the artifact → §8 manifest + 3 runs/question + install-time verification;
  R2-10 the PENDING-ARMS hand-back "not found" — refuter read `origin/main` on Pro, the row
  is opened in this same PR (claim wording corrected).
- **Round 3 on v3: VERDICT BLOCKED — 7 findings (1×P0, 5×P1, 1×P2), again mostly twins of
  the v3 fixes.** R3-1 BKPM gates were fail-open (seat presence alone enabled chat) → §4
  build-time policy gate, BKPM closed regardless of seat, owner enablement artifact, guilt
  test; R3-2 question-matched row selection breaks the cap (verified to the decimal: 46710
  has 4 rows matching "bahan bakar gas cair" at 20.8 KiB each = 83.0 KiB) → §3 byte-budgeted
  selection + per-row sub-field caps + query-adversarial size sweep; R3-3 history preserved
  dialogue but lost referents (the gate would reject the natural follow-up) → §3.4 session
  anchors: history-cited codes join the retrieval set; R3-4 benchmark commit A ≠ installed
  commit B after the OpenClaw deletion → §8 A/B ordering: full benchmark on A, new-brain
  re-run + manifest on B, install exactly B; R3-5 the zero-fabrication floor over-claimed
  vs 20% sampling → §8 deterministic tuple check on 100% of answers/runs + judge + sample,
  floor re-stated as what it measures; R3-6 code↔% pairing undefined for multi-code clauses
  → §3 one-code-one-figure-per-clause rule, "respectively" constructions rejected as
  unverifiable; R3-7 the PENDING-ARMS hand-back was an unverifiable assertion → §1 quotes
  the row so the diff pairing is mechanically checkable.
- **Round 4 on v4: VERDICT BLOCKED — 5 findings (1×P0, 4×P1); R3-2/R3-5/R3-7 accepted as
  materially resolved.** R4-1 the structured fields contradict EACH OTHER on 50111/50112
  (`pma_max_asing=49` vs `pma_kondisi="Hanya PMDN (100% domestik)"` — verified, and the
  class censused: exactly those 2 records in 1,559) → §3 cross-field consistency gate,
  conflict-marked records refuse the ownership axis on BOTH generation and verification,
  dataset adjudication handed to the corner; R4-2 session anchors at lowest-priority were
  evictable by a worst-case card → §3.4 question-first priority + reserved 16 KiB anchor
  slice + combination test; R4-3 the BKPM marker was a transferable bearer capability →
  §4 signed claims bind machine UUID, build, expiry ≤90d, G-P1 date, with copy/expiry guilt
  tests; R4-4 the benchmark bound the build but not the runtime → §2 exact-version
  fail-closed probe + declared-unfreezable hosted alias + re-benchmark policy; R4-5
  "49 percent" bypassed the digits+`%` grammar → §3 normalization of all numeric percentage
  surface forms before the check.
- **Round 5 on v5: VERDICT FIX-FIRST — 5 findings (4×P1, 1×P2); R4-1 accepted as closed
  (the refuter independently re-confirmed 50111/50112 on the canonical).** R5-1 "every
  anchor survives" was arithmetically impossible under the 64 KiB cap (the refuter measured
  12 ordinary history records at ~75 KiB on scalar fields alone) → §3.4 anchors bounded to
  the 4 most recent distinct codes + declared drops + re-name instruction + saturation
  test; R5-2 SIGKILL/crash of the app is not interceptable and the detached group survives
  → §2 declared residual + pidfile launch sweep with recycled-pid guard; R5-3 per-chat-open
  version check left a TOCTOU window for a binary swap → §2 per-spawn absolute-path
  resolution + version re-check + swap test; R5-4 decimal (`49,0%`) and fullwidth (`％`)
  forms could bypass or, worse, read as a trailing `0%` match → §3 NFKC + maximal atomic
  numeric parse + extended guilt tests; R5-5 the marker attests G-P1 history, not current
  state → §6(c) names the intra-window residual as part of the owner's acceptance, expiry
  as the knob.
- **Round 6 on v6: VERDICT FIX-FIRST — 3 findings (3×P1); R5-4 and R5-5 accepted as
  closed.** R6-1 unbounded explicit question codes made the priority ladder unsatisfiable
  (measured by the refuter: card + 4 anchors + 5 explicit codes = 68,720 bytes on mandatory
  fields alone) → §3.2 explicit codes capped at 3 with the honest "narrow the comparison"
  state, total priority ladder with a declared victim order, exact-scenario test; R6-2 a
  bare-pgid pidfile both spares a leaderless orphan group and can kill someone else's codex
  on pgid reuse → §2 durable job identity (pgid + leader start-time + per-call tempdir
  cwd), kill only on cwd match, leaderless-kill and recycled-spare tests, chdir residual
  declared; R6-3 probe→spawn TOCTOU with the symlinked binary (measured: Pro's codex IS a
  symlink) → §2 symlink-chain resolution + file identity capture + pre-spawn re-stat,
  microseconds residual declared as irreducible without fexecve.
- **Round 7 on v7: VERDICT FIX-FIRST — 2 findings; R6-1 ACCEPTED (cap + total ladder +
  combinatorial test).** R7-1 a crash in the spawn→sidecar window left an unknown orphan
  the sweep could not find → §2 durable intent record BEFORE spawn, completion after,
  incomplete-intent recovery by tempdir hunt, crash injection at every record transition;
  R7-2 the verified file was not explicitly the executed file (a symlink retarget between
  probe and spawn would execute B after verifying A) → §2 version check, re-stat and
  `posix_spawn` all bound to the SAME resolved real path, symlink-retarget guilt test.
- **Round 8 on v8: VERDICT SHIP.** Both R7 dispositions verified real (durable intent
  precedes spawn, every ambiguous state recoverable, transition matrix covers
  spawn-no-completion; resolution/version/re-stat/spawn all on the same real path, symlink
  retarget cannot change the executed file). The refuter found no concrete scenario outside
  the declared tests and residuals; remaining risk is implementation-level and belongs to
  the P2a gate. Eight rounds total: BLOCKED(13) → BLOCKED(10) → BLOCKED(7) → BLOCKED(5) →
  FIX-FIRST(5) → FIX-FIRST(3) → FIX-FIRST(2) → SHIP — 45 findings folded or declared, every
  measurable claim re-verified on the canonical dataset before folding (W65), and two of
  the findings were promoted to their own artifacts: the 50111/50112 + zantaraOpener
  dataset defects (corner red row) and the adapter group-kill gap (PENDING-ARMS row for
  /bot S2).
