# B2.4 — SUPPORT JUDGE REACH — design (written before code)

Dux: Opus 5 xhigh, Pro, BLUE. Base `77af6c7ada8e1fc3de2f50ba3e64a78e330f9adf`.
Generation authority: ruling I96 (Desk), under Zero's full delegation.

## 0. Defect, re-verified this session (read-only)

| Probe                                                                     | Result                                                                                                                                                                                          |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `wa_outbox` rows 421-424 (SELECT, no PII columns)                         | 422-424 `status=done`, `generation_route` NULL (never offered), `evidence_score=0.08`; 422 `attempts=1`, `generation_fall_off_reason=package_build_error`                                       |
| `git grep -i codex\|ollama` on `apps/backend-rag/Dockerfile` + `fly.toml` | no match (rc=1)                                                                                                                                                                                 |
| `fly secrets list` names `^WA_`                                           | no `WA_CODEX_BIN`/`CODEX_HOME`/`OLLAMA_*`/`WA_BROKER_DEADLINE_S`                                                                                                                                |
| `_support_signal.evaluate_support` L382-409                               | Codex (local adapter) -> Ollama 127.0.0.1:11434 -> `UNAVAILABLE`, `judge="absent"`                                                                                                              |
| `wa_package_builder.build_context_package` L621-625                       | calls `evaluate_support` on every `dlp=True` build, inside `POST /api/wa-package/build`                                                                                                         |
| `wa_codex_leg._attempt` L374, L673-714                                    | 10 s build timeout; any non-SUPPORTED verdict -> terminal stub BEFORE the offer                                                                                                                 |
| `reasoning_utils.calculate_evidence_score` L790                           | `support=None` and `support=SUPPORTED` produce the SAME score; anything else zeroes relevance                                                                                                   |
| Pro daemon                                                                | `launchctl print system/com.balizero.wa-codex-broker` running, pid 637; runtime copies `cmp -s` identical to origin/main                                                                        |
| Pro daemon runtime                                                        | ROOT-OWNED copy under `/usr/local/lib/wa-codex-broker` of exactly 2 modules, installed by `scripts/provision_zantara_codex.sh`; provisioning skips bootstrap when loaded (needs `kickstart -k`) |
| `sudo -n true` on Pro                                                     | `a password is required` -> updating the daemon is an operator step                                                                                                                             |

## 1. Chosen shape — judge-before-generate on the claimed job, authenticated completion envelope

The daemon (Pro, real Codex seat) evaluates support on the package it has just
claimed, BEFORE generating, with the unchanged I26 judge (`CodexSupportJudge`,
`RUBRIC`, three repetitions, `majority()` strict, split -> NOT_SUPPORTED). The
build on Fly no longer consults any judge. The verdict travels back inside the
completion, in an envelope the model cannot forge.

### 1.1 Flow after both PRs

1. Fly leg: `POST /api/wa-package/build` (retrieval + DLP only, no judge -> the
   10 s timeout no longer absorbs judge work; I96-3). `evidence_inputs` carry
   `support_verdict=None`, `support_votes=[]`, `support_judge="deferred:broker"`,
   plus the precomputed pair `evidence_score_unsupported` / `abstain_unsupported`
   (the same pure scorer called with `support=NOT_SUPPORTED`). `evidence_score` /
   `abstain` stay the `support=None` values, which are byte-identical to the
   SUPPORTED branch (reasoning_utils L790) — the only branch that can release.
2. Leg offers the job unconditionally (the pre-offer support branch is removed).
3. Daemon claims, parses the wire, derives the judge input with ONE helper
   (`_support_signal.support_inputs_from_wire`: `history[-1].content`,
   `"\n\n".join(chunk.text)` — exactly what the builder used), runs the judge on
   the daemon's OWN `CodexExecClient` (its `CODEX_HOME`/binary), model pinned
   `MODEL_TERRA`, wall-clock `judge_budget = min(20 s, 0.45 * budget_s)`.
   - majority `UNAVAILABLE` -> `/complete` with `error_class="support_judge_unavailable"`
     (new closed-vocabulary entry; the broker folds it into the breaker like
     any seat failure) + daemon ERROR log. Nothing generated.
   - `NOT_SUPPORTED` / `UNKNOWN` -> `/complete` with `result_text = envelope(answer=null)`.
     Nothing generated (unsupported advice is never even produced).
   - `SUPPORTED` -> `generate(package, timeout_s=remaining budget)`; success ->
     `result_text = envelope(answer=<model text>)`; every existing failure class
     unchanged; size caps measured on the ENVELOPE (the bytes actually sent).
4. Leg consumes, then `wa_completion_envelope.decode(text, package_hash, key)`:
   - invalid / absent / MAC mismatch / hash mismatch -> fall-off
     `support_judge_absent:no_verdict` (ERROR log). Never released.
   - `SUPPORTED` + answer -> existing restore_text -> finalize (frozen label) -> send;
     INFO log names judge + votes.
   - `NOT_SUPPORTED`/`UNKNOWN` -> the existing terminal stub (served_by
     `support_abstain`, human told), carrier from the `*_unsupported` pair, log
     names judge + votes.
   - wait FAILED with `error_class=support_judge_unavailable` -> fall-off
     `support_judge_absent:unavailable` (ERROR log).

### 1.2 The envelope (`backend/services/integrations/wa_completion_envelope.py`, stdlib only)

```json
{"v": 1, "package_hash": "<hex>", "verdict": "SUPPORTED",
 "votes": ["SUPPORTED","SUPPORTED","NOT_SUPPORTED"], "judge": "codex:gpt-5.6-terra",
 "answer": "<text>" | null, "mac": "<hex>"}
```

- `mac = HMAC-SHA256(k, canonical_json(all fields but mac))`,
  `k = HMAC-SHA256(WA_BROKER_KEY, b"wa-completion-envelope/v1")` (domain-separated
  from the HTTP auth use of the same secret). Both sides already hold the key
  (Fly: `settings.wa_broker_key`; daemon: `DaemonConfig.broker_key`); the codex
  child never sees it. `hmac.compare_digest`.
- Strict decode: exact key set, `v == 1`, verdict in the 3 answerable values,
  `len(votes) == 3`, each vote in the 4-value vocabulary, `majority(votes) == verdict`,
  `answer` non-empty string iff `verdict == SUPPORTED`, `package_hash` equals the
  leg's own. Anything else -> `None` (fail-closed).
- Why authenticated and not just parsed: before the daemon is re-provisioned an
  old daemon returns RAW model text; a prompt-injected client message could make
  the model print a look-alike JSON claiming SUPPORTED. Binding `package_hash`
  alone is not enough — Codex runs read-only shell commands and could hash its
  own prompt. A MAC under a key the model never holds is unforgeable.

### 1.3 Ruling I96 conformance

| I96                                                                 | How                                                                                                                                                                                                                                                                |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1 fail-closed gate stays                                            | no text leaves without an authenticated SUPPORTED verdict; UNAVAILABLE is never "not consulted"                                                                                                                                                                    |
| 2 judge where a real Codex seat lives                               | inside `wa_codex_daemon` on Pro, same seat, same offer/claim/`WA_BROKER_KEY`                                                                                                                                                                                       |
| 3 judge latency outside the 10 s build                              | build does retrieval+DLP only; judge runs inside the job's T_exec (45 s) budget                                                                                                                                                                                    |
| 4 majority-of-3, split = NOT_SUPPORTED, votes in the abstain record | `majority()` unchanged; votes travel in the MAC'd envelope and are logged on the stub and on release                                                                                                                                                               |
| 5 absent judge LOUD                                                 | distinct durable `wa_outbox.generation_fall_off_reason = support_judge_absent` (migration 315 widens the CHECK); durable `broker_jobs.error_class = support_judge_unavailable` (7-day terminal retention, SQL-countable) + breaker fold + ERROR logs on both sides |

### 1.4 Rejected shapes

- **Judge-only job kind on the broker**: new job state/kind column, migration on
  `broker_jobs`, a second offer/wait per turn inside the same claim — strictly more
  contract surface for the same verdict.
- **Typed `support_record` column on `broker_jobs` + `/complete` field**: migration
  on the transport table, `consume_result` return-type change rippling into 6 test
  call sites, router schema change — forge-proof but larger than the envelope.
- **Verdict via `error_class` for NOT_SUPPORTED**: folds a healthy seat into the
  breaker (off-domain questions would open it) and cannot carry the votes.
- **In-container judge / treating UNAVAILABLE as not-consulted**: rejected by I96.

### 1.5 Declared deviations and residuals (for the imperator)

- **No Ollama fallback on the daemon path.** `OllamaSupportJudge` runs 3 sequential
  calls at 120 s each; it cannot fit T_exec = 45 s, and a to_thread call cannot be
  cancelled. I96-2 names the Codex seat. `evaluate_support()` is left intact for the
  B2.1 harness and has zero production callers after PR-2.
- **Quota**: an answered question costs 4 codex execs (3 votes + 1 generation);
  an unsupported one costs 3 and generates nothing.
- **Latency**: judge (parallel reps, <= 20 s) + generation (measured 8.5-10.1 s on
  outbox 363) inside 44 s budget; a judge timeout is UNAVAILABLE (breaker fold).
- **REATTACHED leg**: accepted only if the prior job's envelope carries this
  claim's `package_hash` (content-addressed, normally identical); otherwise
  `no_verdict` fall-off. Carrier stays NULL on REATTACHED as today (I83).
- **Transition safety both ways**: new daemon + old Fly = no offers reach it
  (old leg stubs at build). New Fly + old daemon = raw text -> MAC fails ->
  `support_judge_absent` fall-off, never a release. Hence the merge order below.

## 2. PR split and merge order (each <= ~400 net lines where the work allows)

1. **PR-1 `feat(wa-codex-daemon): judge support on the claimed job before generating`** — inert on Fly.
   `_support_signal.py` (client injection + `support_inputs_from_wire`),
   `wa_completion_envelope.py` (new), `wa_codex_daemon.py`, `wa_broker.py`
   (`ALLOWED_ERROR_CLASSES += support_judge_unavailable`), `scripts/provision_zantara_codex.sh`
   (install the 2 new modules + empty `services/rag/__init__.py`, `services/rag/agentic/__init__.py`),
   `infra/home-fork/declared-pairs.json` (2 pairs), tests.
   Fly behaviour after merge: unchanged (builder still judges in-container; router accepts one more error class).
2. **NEEDS-ZERO (operator[credential], sudo)** on Pro, from a checkout of the merged sha:
   `sudo scripts/provision_zantara_codex.sh` then
   `sudo launchctl kickstart -k system/com.balizero.wa-codex-broker`.
   Proof by the Dux: `cmp -s` of the 4 runtime modules vs origin/main, new pid,
   `wa_broker_gauge.broker_last_seen_at` advancing on two reads.
3. **PR-2 `fix(wa-codex-leg): release only on the broker judge's authenticated verdict`** — the switch.
   `wa_package_builder.py` (no judge; `*_unsupported` pair), `wa_codex_leg.py`
   (post-consume decode; stub/release/no_verdict/unavailable), fall-off map,
   migration `315_wa_outbox_fall_off_reason_support_judge_absent.sql` (widen CHECK,
   297 pattern), tests. Opened after step 2 is proven; armed at open.
4. **READY-FOR-B3-PROBE**: positive (PT PMA registration time) and negative (Nusa Penida ferry).

## 3. Bites (PR-2, mandatory before close)

Consumer: `wa_outbox_worker` -> `wa_codex_leg` on Fly `rag`, daemon on Pro.
Observation: a `wa_outbox` row created after the PR-2 deploy for the supported
question with `status=done`, `generation_route=codex`, `abstained_at IS NULL`,
`evidence_score` above the label threshold, plus a Fly log line
`support verdict SUPPORTED judge=codex:gpt-5.6-terra votes=...`; and the
off-domain row served `support_abstain` with the log naming a real judge (not
`absent`).
