# operations.md — behavior, PR mechanics, anti-hallucination, hooks, ops rules

> Moved verbatim out of repo-root `CLAUDE.md` on 2026-09-04 (context-diet,
> root-CLAUDE.md-becomes-index). Covers: Agent PR Contract (classification call — not
> explicitly named in the split mandate, grouped here as agent-lifecycle-procedure content
> parallel to §2), §2 Behavior & Autonomous Ops (whole section, including the short lines
> not individually named in the mandate — moved together rather than picked apart), §6
> Anti-Hallucination, §7/§7bis Hooks + Repomap, §13 Critical Operational Rules, §14
> Escalations & Continuity (PII/OSINT boundary intero, verbatim — è legale).

---

## Agent PR Contract (Merge-OS v2 Wave 0)

These seven rules apply to every agent-produced PR. They govern lifecycle discipline; they do
not grant a role authority that its own contract withholds (for example, an external builder
still does not arm, merge, or deploy). The operational commands are documented in
`docs/runbooks/merge-queue-discipline.md`.

1. **One PR, one concern.** Target no more than about 400 net lines when the nature of the work
   permits it.
2. **Arm means freeze.** After `mq arm`, the branch is read-only. Put every follow-up in a new
   PR created from a fresh `origin/main`.
3. **Never rerun a check without first knowing WHY it is red.** The gesture depends on the cause,
   and a blanket prohibition here deadlocked two PRs on 2026-08-21. If the red is the CODE or the
   base has moved, `gh run rerun` replays a stale merge ref (W111) — repoint it: `mq requeue`, or
   `gh pr update-branch` first. If instead the red is an EXTERNAL COMMIT STATUS on an unchanged
   head SHA — a Gear-3 gate verdict posted after the run finished — then `gh run rerun` on the
   original `pull_request` run is the ONLY instrument that clears the PR's rollup, because a
   `workflow_dispatch` run's check-run lands in a different check suite and never enters that
   rollup at all. Details and the diagnostic traps: `docs/runbooks/merge-queue-discipline.md`.
4. **Never commit while a push is in flight.** Judge the push by its captured return code, not
   by a background-task summary.
5. **Serialize Dependabot PRs that share a lockfile.** Arm them one at a time.
6. **Use a dedicated worktree and make the claim commit first.** Branches use the
   `agent/<host>/<lane>/...` namespace.
7. **After merge, run `mq handoff`.** The merged branch is dead; its successor starts from a
   fresh `origin/main`.
8. **Three rounds, then suspend.** A PR that goes red for the SAME cause three times — gate,
   lint, or refuter finding on the same surface — gets no fourth round: it SUSPENDS (one
   PENDING-ARMS line naming the cause, branch left alive) and the session moves to the next
   mandate. A fix-of-a-fix chain stops at depth 1: if the correction is itself wrong, the
   surface is under-specified — write the spec, do not open the third PR. Measured 2026-08-22:
   PR #4547 (a 1-file hook fix) took 14 commits, 11 adversarial rounds and ~6h; the 44h session
   driving it spent 3.9M output tokens, and 27 of the 200 commits that landed on main 2026-08-20..22 (195 merged PRs) existed
   only to correct a claim made by a previous one.

## 1bis. The `Bites:` contract, and the one shape a machine can execute

Contract §2 says every PR body carries a `Bites:` line naming the CONSUMER and the
observation that proves the change is in force. Measured 2026-09-04 21:40 WITA over the
209 PRs merged since 2026-09-01: **139 bodies (66%) mention one, and nothing reads any of
them** — `grep -rlE Bites .github/workflows scripts/*.py scripts/ci/*.py infra/claude-hooks`
returns zero files. (The ratio drifts with every merge and is dated for that reason; the
ZERO is the load-bearing half, and it is the one that does not drift on its own.)
The machine verifies the DIFF; the runtime is verified by a sentence someone wrote
about it. Prose stays welcome and stays the default. What follows is the
OPTIONAL second shape, for when you want the claim checked rather than believed.

> ✅ **RULED 2026-09-04 (Zero, Legge 5): the executable contract lives in the DIFF, not in
> the PR body.** The first draft read the block out of the body, which meant deciding which
> Markdown region a human actually SAW — a `<!-- -->` comment, a fenced block, a four-space
> indent and a raw `<pre>` all render as page furniture rather than as a contract, and a
> block hidden in one of them must not become an executable observation. Three adversarial
> rounds closed five spellings of that one defect and found a sixth; CodeQL named the
> pattern independently (`py/bad-tag-filter`). The class does not close by patching: a
> hand-rolled CommonMark reader can only ever approximate the renderer it is guessing at.
> So the block moved into a file the diff carries, read by a real YAML parser. Hidden
> regions and line-splitting cease to EXIST rather than being guarded — a pack has no
> rendered form, so there is no gap between what a reviewer sees and what the machine reads.

It is a top-level `bites:` mapping in the evidence pack's `pack.yml`, under the dated
directory `scripts/ci/evidence_paths.py` emits — never a hand-built path:

```yaml
bites:
  consumer: <who reads or executes the changed thing>
  where: ci | fly | pro | mini
  observe: python3 scripts/ci/bites_parse.py --selftest
  expect: exit0            # or contains:<text> / regex:<pattern>
```

**Three outcomes, and the difference between them is the whole migration story.** A pack
with no `bites:` key is `absent`; a `bites:` block with no `observe:` key is `legacy`
(prose, the old shape). **Neither is ever an error.** Every pack merged before this format
existed is `absent`, and no merged pack may turn red retroactively because a format
arrived after it. Only a block that HAS `observe:` and then fails the guards is malformed.

**`observe:` is executed post-merge by a runner holding a write-scoped token, so it takes
exactly TWO shapes and nothing else parses.** An allow-list over a general command line
has to model every option of every binary it admits, and this one was rewritten three
times because each pass found another option whose VALUE reached further than the option
looked — `curl -b`, `pytest -W`, `gh --jq` (gojq's `env` builtin prints the runner's
environment). So the surface was narrowed instead of patched again:

```
observe: python3 scripts/<path>.py [literal args]    # anything you can write in Python
observe: fly status                                  # also: releases, image show,
                                                     #       machine list
```

(Spelled one per line on purpose: a `|` in an `observe:` value is a shell metacharacter
and is refused, so it must not appear in the example that teaches the format either.)

Anything else is malformed, and the cure is always the same: **wrap it in a script under
`scripts/ci/`**, where it is reviewable code in the diff rather than a command line a
parser has to second-guess. Two things the parser cannot decide from a command string and
the executor must honour: a sanitised environment (half of git's dangerous behaviour is
reached through CONFIG, not argv) and POST-MERGE ONLY (a PR can add a script and its
observable marker in the same diff, so pre-merge the marker is worth exactly what the
review of that diff is worth).

**Nothing reads this yet, and that is the point of saying so here.** As of 2026-09-04 the
parser is not on `main` — it lands with the parser PR replacing #5673. The advisory lint
stacks AFTER that: `harness-floor.yml` checks out the BASE ref, not HEAD, so a step
calling the parser cannot run until the parser is on `main`. The post-merge executor that
actually closes the loop is PR-2. Until it lands, an executable `bites:` block is a
well-formed claim, not a verified one — the same distance this section was written to
close, and writing it down does not close it.

## 2. Behavior & Autonomous Ops

**DO NOT ask the user to write code.** Act first, ask if blocked. Use `Edit`/`Write`/`Bash` without asking permission.

**No phantom operator lane** (Zero, 2026-07-06: *"io sono te — non c'è nessun operatore"*). Sessions ARE the operator for all repo/infra work, on every machine. Never park work behind a waiting-for-human fence: investigate dirty/anomalous state (whose is it? runtime-state? live sibling? residue?) and handle it — "alive" is verified (processes, mtime, file nature), never presumed. The ONLY true operator-only categories are: physical device actions, GUI-only surfaces (interactive logins, GitHub settings, external-UI paste), TCC grants, consents/credentials only the human holds, `~/.claude/hooks/` control-plane one-liners (host_boundary stays hard by design), and business decisions (Legge 5) — where the business decision is AUTHORISING, never executing: a publish order for a News Room article, a WR2 carousel or a WR3 video that reached you through an authenticated channel from Zero or Damar (2026-09-01 editorial delegation, `SYMBIOSIS.md` Law 5) is a decision already taken, so carrying it out is the session's work and not an operator hand-off. In the PENDING-ARMS ledger these MUST be declared as `operator[<category>]`; any bare `operator` owner is flagged PHANTOM-OPERATOR by `scripts/pending_arms_report.py` (CI-enforced: `immune-enforcement.yml` strict-phantom gate + `test_real_ledger_has_zero_phantom_operator`). Sibling discipline (#5) still holds toward LIVE sessions' work. Reference: memory `feedback_no_operator_lane_io_sono_te_2026_07_06`.

**⚡ SHIP-LIFECYCLE OWNERSHIP (HARD RULE — Zero, 2026-07-16: *"tu mergi fai review armi deploy testi. il codeowner non lo fa, non lo sa fare"*).** **THE SESSION DOES IT ALL: REVIEW → MERGE → ARM → DEPLOY → PROVE-LIVE. THE CODEOWNER DOES NOT MERGE, DOES NOT REVIEW, DOES NOT DEPLOY — BY DESIGN.** Never park a PR on "waiting for the codeowner's review/merge"; never end a mandate at "attende merge". Concretely: (1) arm `gh pr merge --auto --squash` at PR-open on every L2 feature PR — "client-facing/sensitive data" is NOT an exception: sensitivity raises the rigor of the ADVERSARIAL gate (generator≠grader — the diff's author never gates its own diff), it never moves the merge to a human; (2) post-merge, the session runs the deploy and apply steps itself (dry-run → apply → verify), per §11; (3) "done" is declared only after PROVE-LIVE on EVERY consuming surface (consumer-map first — memory `feedback_merged_is_not_live_consumer_map_first_2026_07_16`); (4) the codeowner keeps ONLY: business decisions (Legge 5) — the DECISION itself, never its execution, so an authenticated publish order from Zero or Damar on the editorial perimeter is a decision already taken and the session carries it out; consents/credentials only the human holds; physical/GUI/TCC actions; (5) the auto-merge-OFF exceptions (guardrail hooks, DB migrations, force-push class — per `feedback_arm_automerge_default_not_leave_to_operator`) still get merged by the SESSION after their specific gates, never by the codeowner. Reference: memory `feedback_session_owns_full_ship_lifecycle_2026_07_16`.

**Master loop (2026-07-02)**: skill **`modus`** (`.claude/skills/modus/`) governs every non-trivial mandate end-to-end — TRIAGE gears (1 liscio / 2 standard / 3 profondo) → GROUND → DESIGN → BUILD → VERIFY → SHIP+ARM → PROVE-LIVE → ALIGN-FLEET → CLEAN → CAPTURE. It absorbs `stadio-zero` (entry gate) and `sota-architecture-loop` (design) as stages; **`opus-mythos` is superseded** (its deep/wide TAC patterns = modus Gear 3). W81 ledger: `.claude/skills/modus/PENDING-ARMS.md` · loop scar-file: `AMENDMENTS.md` · self-refinement: `infra/workflows/modus-bench.js` (operator-gated, on demand).

**Product assembly line (RULED Zero 2026-08-24)**: for PRODUCT builds (a user-facing thing with a business outcome), `docs/factory/ASSEMBLY-LINE.md` is the governing procedure — 5-artifact set, contract-first, journey-tests-red-first, one cross-family refuter per PR (risk-tiered), business-invariant paging + synthetic purchase probes, ship dark → 5% with real users → 100%, kill criterion in the mandate. It composes with `modus`; on product work, where they overlap, ASSEMBLY-LINE wins. Panel evidence: `research/operations/2026-08-24-product-factory-procedure-5-seat-panel.md`. First product: GARUDA VOA (`docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`).

Read `AUTONOMOUS_OPS.md` (L2 active 2026-04-21) before: `git push`, PR ops, deploy, `fly ssh`, shared-state changes. Check "active since" date — if stale >30 days, conservative fallback. **User's veto is NOT the safety layer** — guardrails in that file are.

**Federation Orchestrator triggers** (`python scripts/federation_orchestrator.py "task"`):

| Trigger | Dispatch | Why |
|---|---|---|
| KBLI, visa, normativa | Gemini `search` | Claude hallucinates regulations |
| Refactor 3+ app | Gemini `explore` | 1M ctx maps dependencies |
| Grounding / Oracolo | NotebookLM `oracolo` | NB-1 ground truth |
| Alembic migration | Codex `sandbox` | Tests upgrade+downgrade |
| Pre-deploy Fly.io | Gemini `redteam` | Mai deploy senza red team |
| Fix dependencies.py / service_initializer | Codex `sandbox` | Import chain SPOF |

**Preflight SDD**: 3+ file/L1 · dependencies.py + migration + KBLI/visa + pre-deploy/L2 · auth/billing/RAG/L3.
`./scripts/ai-dispatch.sh preflight-{l1,l2,l3} "desc"`. Escape `SKIP_PREFLIGHT=1`.

**Escalations**: check `shared/escalations_pro.jsonl` + `~/.agent/decisions/claude_tasks/` at session start. HIGH first.

## 6. Anti-Hallucination

> Errare è umano, allucinare è diabolico. (Antonello, 2026-05-13)

**Mai citare output di un tool senza averlo eseguito in QUESTO turn.** Full discipline in `~/.claude/CLAUDE.md §Anti-hallucination` (5 rules). Load-bearing on every tool call. When in doubt "ho letto X o lo sto inventando?" → tool call adesso.

**4-LLM panel mandatory pre-approval** per spec architetturale, quote cliente, pre-deploy critical path: Gemini agy + Codex GPT-5.6 family (`sol` xhigh/max for red-team; full arsenal routing `.claude/skills/modus/SKILL.md` §Arsenal) + Kimi K3 (`kimi -m kimi-code/k3 -p`; DeepSeek seat RETIRED 2026-07-19) + opzionale NB-1. Cost: flat-sub only, ~2min wall. Reference: `feedback_always_review_spec_with_4_llm.md`. **Reusable workflow (generator≠grader as default)**: `infra/workflows/verify-template.js` — a gather→adversarial-refute→synthesize Workflow script promoted to a citable artifact (self-loop Ring A4). For any research/audit/critical-finding, run it via `Workflow({scriptPath:"infra/workflows/verify-template.js", args:<question>})` so the refuter-on-fresh-context pattern is the path of least resistance, not a thing to remember. (The `sota-architecture-loop` skill STEP-3/6 is its doctrine; this file is the runnable default.) **Terminology note (2026-06-28):** the A1-A4 rings are a *self-HEALING / reliability* loop (catch regressions, restart dead organs, verify findings) — **NOT** the recursive self-improvement (RSI) Amodei describes ("models building better models"; Anthropic "we are not there yet"). A4 is a safety primitive a safe RSI would need first, not RSI itself. Don't call it "self-improvement".

## 7. Hooks enforce what prompts cannot

Hooks (`~/.claude/hooks/`) sono il backstop quando il system prompt non basta. Active 2026-05-23:

- **`stop_verify.py`** (T2.6): blocca Stop con git dirty + no intent marker. Override `STOP_VERIFY_ALLOW_DIRTY=1` o intent marker in transcript (WIP/checkpoint/leave dirty).
- **`dispatch_nudge.py`** (T1.1): reminder dispatch subagent quando transcript >500 lines + zero Agent.
- **Guardrails daemon** (T1.2): blocca MCP destructive patterns (`drop_*`, `delete_*`, `truncate_*`, `wipe_*`, `purge_*`).
- **SessionStart repomap inject** (SOTA L4, 2026-05-24): se `~/.nuzantara-repomap.txt` esiste e ha age <30min, viene auto-iniettato in context all'inizio sessione. Riduce esplorazione iniziale di ~50 tool calls. Stale >30min skipped (no inject). Kill switch: rimuovi entry da `~/.claude/settings.json`.
- **`pre-commit lease-check`** (SOTA L2, 2026-05-24): blocca commit su hot-zone (LaunchAgent wrappers, migrations, auth/billing/pricing, .github/workflows/, sentinel/dlq scripts) se file ha lease attivo da altro agent task. Backend Redis `agent_lock:<resource>` con TTL + heartbeat. Override `AGENT_LEASE_ENFORCEMENT=false`. Graceful degradation se Redis down → pass-through con WARN log (mai blocco per outage Redis). Runbook: `docs/runbooks/redis-lease-registry.md`. SOTA panel reference: `research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`.

**Principio**: se una regola critica è violabile, scrivi un hook. Documentazione non basta.

## 7bis. Repomap + Branch cleanup (SOTA L4 2026-05-24)

- **Repomap cron** (`com.nuzantara.repomap.15min`): aggiorna `~/.nuzantara-repomap.txt` ogni 15min via `scripts/build_repomap.sh` (strategia aider tree-sitter, ~8KB / 264 righe, signatures only). SessionStart hook injetta in context se age <30min. Kill switch: `REPOMAP_ENABLED=false` nell'env del plist.
- **Branch cleanup weekly** (`com.nuzantara.branch-cleanup.weekly`, lunedi 08:00 WITA): genera report `~/logs/branch-cleanup-YYYYMMDD.md` via `scripts/branch_graveyard_cleanup.sh`. Default dry-run (REPORT ONLY). Apply solo categoria "merged & deletable" via `--apply`. Categorie zombie `claude/*` >30d e stale >90d sono REPORT-ONLY (mai auto-cancel). Kill switch: `BRANCH_CLEANUP_ENABLED=false`.
- **Install**: `bash infra/launchagents/install_repomap_cron.sh`. Runbook: `docs/runbooks/repomap-and-branch-cleanup.md`.

## 13. Critical Operational Rules

- **Email sending** (REGOLA FISSA): always `from=zantara@balizero.com` via Brevo `/api/notifications/send-email` + `X-API-Key: <NOTIFICATIONS_API_KEY>` (the literal `REDACTED-ROTATED-KEY` was a public-repo admin key — rotated + revoked 2026-07-12; read the key from the env, never hardcode it). Never `notifications@`/`subhi@`/personal addresses.
- **CRM RBAC**: Admin (`zero@`, `antonellosiano@`, `asya@balizero.com`) = all access. Team = only `assigned_to` matches.
- **Team perimeter rule**: full roster in memory `reference_bali_zero_team.md`. **Subhi — WHOLE-SYSTEM code access (widened 2026-07-16 by Zero: "eliminiamo il perimetro no-backend-rag, allarghiamo all'intero sistema"; probation 90gg 2026-04-30 → 2026-07-29 unchanged).** The old `apps/mouth/**`-only perimeter + "NO backend RAG" ban is LIFTED: he may work anywhere in the codebase (backend RAG, organs_registry.yaml, migrations included). **The ban existed because there was no safe verification for his backend diffs; there is now** — so the perimeter is replaced by a VERIFICATION model, not a path fence:
  - **Verification = MACHINE + AI, NEVER human review** (the codeowner cannot review — [[feedback_session_owns_full_ship_lifecycle_2026_07_16]]). Every PR (his or anyone's) must pass the required CI gates (test suite, `actionlint`, RAG data-invariant tripwires `test_data_invariant_tripwires.py`, migration Squawk, R1 adversarial-review gate, …), plus a SESSION's independent verification (generator≠grader — Subhi never grades his own diff; sensitivity raises the rigor of the adversarial gate, it never moves the merge to a human). **The Layer-2 AI-review Action is DISABLED as of 2026-08-20** (`.github/workflows/ai-pr-review.yml.disabled-2026-08-20-zero-value-ci-trust-gate`) — measured over ~30h/100 runs, "Run advisory review" failed on a CI workspace-trust gate on every single run (never reached the model) and posted zero comments, so it was silently delivering none of the coverage this paragraph used to credit it with; the session's own independent verification is what actually carries this weight until the trust-gate fix lands and it is deliberately re-armed (see the disabled file's header for the exact fix and re-enable steps).
  - **The grader self-protects** (this is what makes widening safe): Subhi cannot disarm a check — `.github/workflows/` + `CODEOWNERS` are CODEOWNERS-TIER1, actionlint-gated, and meta-verifier-protected. A diff that weakens a gate fails CI by construction.
  - **Still ❌ (credential/infra, NOT code-perimeter)**: Fly secrets / `fly ssh`, direct prod-DB writes, Actions secrets, repo/branch-protection settings, secret rotation. These are operator actions, not reviewable diffs.
  - RBAC detail (self-merge on green, GA4 Editor, CRM read-only) in memory `subhi-rbac-permissions.md`.
- **OCR multi-page**: ALWAYS all pages — directors typically page 2-3 of akta. Timeout 120s for >3 pages. Vision: `qwen2.5vl:7b` ONLY.
- **Drive OAuth** (corrected 2026-08-06 — the old "90d expiry, watchdog alerts 7d before" described a model this codebase never had): `google_drive_tokens.expires_at` is the **one-hour access token** (`google_drive_service.py:163` sets `now + expires_in`; `:230` refreshes lazily on use, 5-min buffer). Measured on both live rows, `expires_at - updated_at == 1h` exactly — **no column anywhere records the refresh token's validity**, so no query against this table can distinguish a live credential from a revoked one. Proven the hard way: on 2026-08-05 Google answered `invalid_grant: Token has been expired or revoked` to the GARUDA indexer while the row looked fully populated. The only thing that knows is an actual refresh attempt, and the consumers make one every time they run — so **the ground truth is a consumer's failure, not a watchdog's countdown**. `scripts/drive_token_watchdog.py` therefore alerts on the two states the table CAN express (no row / no `refresh_token`) and never on a day count; anything that reintroduces a day-scale reading of `expires_at` is unreachable at best and a nightly false CRITICAL at worst. Live Drive traffic does **not** use this table at all — 16 production files go through `ServiceAccountDriveService` (domain-wide delegation), and `_refresh_token` deliberately refuses to refresh the `SYSTEM` row since 2026-05-10. Re-auth `https://kita.balizero.com/settings/integrations`.
- **GitHub Secrets** (Actions + cron alerts): `FLY_API_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID=8847435604` (Zero's `@balizero` chat with **`@zantara0bot`**, delivery verified live from Pro and Mini on 2026-08-13). Never commit, never log. Rotation via `gh secret set`.
  - **The previous pair is dead and must never come back.** `@Balizerobot` (bot id `8295471667`) is decommissioned: its token sat in cleartext on the default branch of this **public** repo, so it must be treated as burned. It **cannot be revoked** — BotFather answers only to the account that created it, and Zero no longer has the number or access for that account. The token therefore stays valid indefinitely in the hands of anyone who reads git history: never route anything through it again, and treat any message claiming to be from `@Balizerobot` as untrusted.
  - The old destination `1125336968` (`dewi0101010101010`) belongs to that same lost account. Anything still sending there is writing to a mailbox nobody can open — which is what 119 hardcoded fallbacks in this repo were doing until 2026-08-13.
- **WR2 image-generator backend** (`WR2_IMAGE_BACKEND` env): `auto` (default, FlowKit primary + Playwright fallback) / `flowkit` / `playwright`. See `docs/wr2/flowkit-integration.md`.

## 14. Escalations & Continuity

- **Session start**: check `shared/escalations_pro.jsonl` + `~/.agent/decisions/claude_tasks/` HIGH first. Delete file after fix + verify with `test_cmd`.
- **PII/OSINT output boundary**: il vincolo non e' "nessun LLM vede contesto operativo"; il vincolo interno di sicurezza e minimizzazione e' che nessun output, memoria, skill, report, log, alert o artefatto condiviso trascriva PII/OSINT in chiaro. È una politica interna più rigorosa, sostenuta dai doveri del titolare negli Artt. 35-39 UU PDP; non afferma che ogni cleartext integri automaticamente gli Artt. 65/67, e l'Art. 68 riguarda la falsificazione. **Cloud/transito alleggerito 2026-06-20**: l'inferenza cloud su testo chat contenente PII è essa stessa processing e trasferimento. L'Art. 56 segue, per singolo trasferimento, la cascata adequacy → safeguard adeguato e vincolante → consenso esplicito soltanto se i primi due livelli non sono soddisfatti; la regola interna raccoglie comunque il consenso e richiede DPA + consenso dove si usa il cloud. `cloud_vision_gate` governa soltanto OCR/vision di documenti e immagini, non il testo chat. Il gateway chat non prova oggi clausola, base Art. 56, revoca o consenso per-cliente: finché la base non è dimostrabile prima dell'invio, il testo con PII cliente deve restare locale/off-cloud oppure la richiesta deve essere bloccata/astenersi. Questo fail-closed è la condotta richiesta, non uno stato già implementato; il gap resta in PENDING-ARMS. Il mirror raw resta Pro-bound per scelta operativa (onere-della-prova), non per divieto assoluto. Reference SYMBIOSIS.md Law 2. **Una sola deroga nominata esiste (Zero, 2026-08-21)**: il digest yield `S7` recapitato su WhatsApp al membro del team a cui il cliente è già assegnato, con payload limitato a nome+iniziale, `client_id` e scadenza, destinatari `@balizero.com` attivi a roster e nessun fallback. Il testo vincolante è in `SYMBIOSIS.md` Legge 2 — non ri-derivarne l'estensione da qui, e non trattarla come precedente per altre superfici.
- **Local sovereignty** (Law 6): organismo vive su macchine Zero. Disconnessione internet NON è guasto — è stato naturale.
