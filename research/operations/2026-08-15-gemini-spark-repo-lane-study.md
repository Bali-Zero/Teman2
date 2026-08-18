---
date: 2026-08-15
domain: operations
client_case: none — fleet capability study (Armata H24)
sources:
  - https://techcrunch.com/2026/05/19/google-introduces-gemini-spark-a-24-7-agentic-assistant-with-gmail-integration/
  - https://www.bloomberg.com/news/articles/2026-08-13/google-debuts-new-gemini-flash-while-top-ai-model-still-delayed
  - https://www.macrumors.com/2026/07/01/google-gemini-spark-comes-to-mac/
  - https://winbuzzer.com/2026/07/02/google-rolls-out-gemini-spark-on-mac-for-ultra-users-xcxwbn/
  - https://support.google.com/gemini/answer/17094710 (schedules — official)
  - https://support.google.com/gemini/answer/16176929 (GitHub import — official)
  - https://www.forbes.com/sites/paulmonckton/2026/05/26/google-announced-gemini-spark-but-left-out-an-uncomfortable-warning/
adversarial_review: codex
discovered_by: spark-study subagent (Sonnet 5, WebSearch), dispatched 2026-08-15 by the M5 Fable session on Zero's order "studialo perché può lavorare sul repo"
---

# Gemini Spark — repo-lane study (2026-08-15)

> Verdict up front: **Spark is NOT a repo-lane worker today.** It IS a real H24
> scheduler (15 concurrent tasks / 50 schedules, official docs) for
> Gmail/Calendar/Docs/local-Mac-folder *document-shaped* chores. The repo-worker
> role belongs to Jules / Codex / Antigravity. Fleet note 2026-08-15: the G1 seat
> (Zero's consumer Google account) holds AI Ultra, so the Mac folder-connector
> gate (F4) is satisfied for non-code folders.

## Findings

**F1. Existence/launch — VERIFIED.** Announced Google I/O, 2026-05-19: always-on agentic assistant, initially "Gemini 3.5 + Antigravity-class harness," runs on dedicated Google Cloud VMs (not the user's device), Gmail/Docs/Workspace integration, MCP-extensible, Chrome web interaction. Ultra-only at launch. Sources: TechCrunch 2026-05-19, thenextweb.

**F2. Engine is now Gemini 3.7 Flash — VERIFIED, dated 2026-08-13.** Google shipped Gemini 3.7 Flash and Spark runs on it as of that date (Gemini 3.5 Pro itself is still undelivered/delayed). This confirms the internal relay's "3.7 Flash engine" claim — current, not stale. 3.7 Flash is pitched as materially better at debugging/producing deployable code than its predecessor. Sources: Bloomberg 2026-08-13, Axios 2026-08-13, 9to5google 2026-08-13, DeepMind model card.

**F3. Local folder access — VERIFIED but narrower than the relay claimed.** Exists **only** via the Gemini **macOS desktop app** ("Connected folders" under a Spark tab), beta since 2026-07-01/02. User explicitly links specific folders; Spark can read/organize/edit/move/delete files **only inside linked folders**; auto-backups of touched files are kept and deleted after 24h or at next task start. **Critically: files are processed "within that cloud environment rather than exclusively on the device"** — content leaves the machine to the VM. **No Windows/Linux support.** Sources: MacRumors 2026-07-01, 9to5google 2026-06-30, AppleInsider 2026-07-01.

**F4. Local-folder feature requires AI ULTRA, not Pro — VERIFIED, corrects the relay.** The general Spark agent rolled out to Pro (US 2026-07-16, 160+ countries 2026-07-30), but the Mac-local-folder connector specifically stayed Ultra-gated ($99/mo) as of sources through early July 2026. Source: Winbuzzer 2026-07-02. *(Fleet note: G1 = AI Ultra, renewed 2026-05-21 — gate satisfied on Zero's account.)*

**F5. GitHub — two unrelated things, neither is what's needed. UNVERIFIED that Spark has a real GitHub connector.**

- (a) The plain Gemini web app has an old, Spark-unrelated "Import GitHub repo" feature: one repo per chat, ≤5,000 files/100MB, **no sync after import**, unreliable on private repos (Google support 16176929).
- (b) A "GitHub connector" with create/update/read ops exists for **Gemini Enterprise** (separate Google Cloud product) — NOT consumer Spark, no evidence it's exposed to Spark.
- **Verdict: treat "Spark can operate a git repo via GitHub" as false/unsupported** absent better evidence.

**F6. Scheduled/recurring tasks (true standing work) — VERIFIED, official docs.** Time-based (once/hourly/daily/weekly/monthly/yearly), Gmail-trigger monitors, topic monitors. **Hard limits: max 15 tasks running concurrently; max 50 active schedules.** Timing approximate; runs can be skipped/delayed under high traffic or usage cap. No documented pre-run approval gate for scheduled runs (approval is per-action inside a run). Source: Google Support 17094710.

**F7. Quota/metering — VERIFIED structure; UNVERIFIED exact caps.** Compute-credit budget refreshing every 5 hours up to a weekly ceiling, weighted by complexity. Spark draws from **its own separate quota pool**, distinct from Google AI Credits, and **cannot be topped up** — you wait for the reset. Ultra ($99.99/mo) = 5x Pro; new top Ultra tier ($199.99/mo) = 20x Pro. Sources: Forbes 2026-05-26, Business Standard.

**F8. Oversight model — VERIFIED (partially), weaker than "user oversight for major actions" implies.** Google's own onboarding copy (quoted by Forbes) admits Spark "**may do things like share your info or make purchases without asking**." A secondary claim that external-impact actions require explicit confirmation is UNVERIFIED and conflicts with the onboarding quote. **Do not assume a reliable approval gate exists — supervise everything.**

**F9. Sandbox/network "fail-closed gate" — UNVERIFIED for Spark; likely product conflation.** Every concrete "default-deny/allowlist" description found belongs to Gemini Enterprise Agent Platform / Agent Gateway or to Gemini CLI's sandbox — neither confirmed for consumer Spark. (Google Bug Hunters "Spark release" post exists but content not retrievable this pass — manual follow-up worth doing.) **Do not rely on it as a safety property.**

**F10. Subagent fan-out — UNVERIFIED for Spark.** All subagent/fan-out documentation found (v0.36 subagents, `--max-subagents`, per-subagent budgets) is for **Gemini CLI**, not Spark. The relay's "subagent fan-out depth-1" claim cannot be substantiated — likely a mixed-up reference to Gemini CLI or Antigravity.

**F11. Shell/git/code-execution — UNVERIFIED, and the one source claiming it is a red flag.** Official Mac-app coverage describes Spark purely as a file-management/organization agent. The single "shell command execution / run tests / commit changes" claim traces to a GitHub repo (`spark-gemini-agent/gemini-spark`) marketed as an "official Spark API" with "Brand Approved partnership with Google" — **HTTP 404 when fetched**, marketing language matches scam/malware-lure patterns impersonating Google. **Do not use, install, or cite that repo. Treat its shell/git claim as fabricated.** Official docs also explicitly instruct users NOT to link folders containing API keys, secrets, `.env`, or client-sensitive code — a strong indirect signal there is no secrets-safe execution sandbox.

**F12. Code-editing comparisons — largely absent; the one found is unfavorable.** No independent review positions Spark as a coding agent at all; the one direct comparison found says Claude Cowork "wins decisively for coding agents and long-form document work" vs Spark. Spark sits capability tiers below Jules (PR-producing coding agent, 100 sessions/24h on AI Pro), Codex (sandboxed GitHub-connected cloud coding agent), Antigravity (agent-first IDE). Source: byteiota.

**F13. Geographic/age gating — VERIFIED.** EEA, UK, Switzerland, Nigeria excluded pending EU AI Act review. 18+. Always paid (Pro or Ultra). Confirmed present on Zero's consumer account from Indonesia 2026-08-14.

## Capability verdict for repo work

**Do not build a standing mandate around Spark editing this repo today.**

- ❌ No confirmed GitHub read/write connector (F5).
- ❌ No confirmed shell/git/test execution (F11).
- ⚠️ Folder access is Mac-only, Ultra-only, cloud-routed (F3/F4) — a file editor, not a git-aware agent.
- ✅ True H24 scheduling is real (F6) — but built for Gmail/Docs/Workspace-shaped chores, not code.
- ⚠️ Oversight weaker than assumed (F8); sandbox claims unconfirmed (F9).

At most: point Spark (Ultra, Mac) at a **non-code, document-shaped folder** — sorting/summarizing research PDFs, drafting doc prose — never at repo source outside a dedicated task-scoped worktree (and inside one, only the document-shaped files the task names — per the standing-mandate scoping below), never unsupervised, never as a git-committing worker. The repo-worker role belongs to **Jules / Codex / Antigravity**.

## Standing mandate draft — GATED, NOT ARMED

Status: **NOT ARMED** until at least one of F5/F9/F11 is re-verified against the live
product (operator inspects the actual macOS Spark UI for a "run command / terminal /
GitHub" affordance no public source documents).

If/when armed — scope (summary):

- Spark operates ONLY inside a dedicated `.worktrees/spark-<task-id>/` worktree (agent_start.py pattern), never the main checkout; that worktree is the ONLY connected folder; no `.env`/secrets/PII inside it (Google's own guidance + SYMBIOSIS Law 2).
- Spark NEVER commits/pushes/opens PRs; a Claude session independently diffs, tests, and ships through the Agent PR Contract (generator ≠ grader).
- Until a network-egress control is confirmed, treat every Spark session as fully networked and scope tasks so that assumption is safe.
- MAY own (once armed): read-only doc/audit sweeps producing report files; draft-only prose staged for review; test-gap "read and describe" analysis (never running suites).
- BARRED (hard): `.git` internals, `.github/workflows/`, CODEOWNERS, migrations, auth/billing/pricing, hot-zone files; mechanical refactors/"commit changes" (until F11 verified); client PII (Spark's cloud processing = paid-cloud-equivalent, same bar as OpenRouter/DeepSeek); architecture/deploy/secrets.

Operator steps (GUI-only): confirm tier (G1 = Ultra: satisfied), link only the per-task worktree folder via Gemini macOS app → Spark tab → Connected folders, manually inspect UI for command/GitHub affordances and report verbatim, never connect `~/nuzantara`.

Fleet infra: an `infra/army/` queue-file pattern for Spark tasks should be built ONLY after the operator's manual UI inspection — building earlier risks encoding capabilities Spark doesn't actually have.

## Open questions for the operator (Zero)

1. ~~Which tier does the account hold?~~ **Resolved in-session: G1 = AI Ultra (renewed 2026-05-21).**
2. Open the Spark UI (Mac app) and report verbatim whether a "run command / terminal / GitHub" option exists — public sources through 2026-08-13 say no; only the live product can confirm.
3. The internal relay's "folder connesso ~/nuzantara + subagent fan-out + fail-closed gate" — source? Three of four relay claims came back UNVERIFIED or contradicted; worth tracing before acting on them.
4. Given F12, the "autonomous-but-verified repo work" role is better served by doubling down on Jules (PR #4180 lane) + Codex Spark (PR #4179 lane) + Antigravity — Spark's H24 value is real but document/Workspace-shaped.

## Adversarial review

Seat: **codex** (`gpt-5.6-terra`, read-only sandbox, dispatched 2026-08-15 by the same
M5 session that authored this file — cross-family, generator != grader per R1). Codex
was instructed to try to refute the F1-F13 findings and the "NOT ARMED" verdict, checking
internal consistency, over-confident claims relative to cited evidence, whether "NOT ARMED"
actually follows from the findings, and whether the four UNVERIFIED findings (F5/F9/F10/F11)
stay hedged downstream instead of being silently treated as confirmed.

**Verdict: 15 objections raised, 11 survived.**

The core conclusions held up:

- **F5 (no GitHub connector) and F8 (oversight weaker than assumed) — REFUTED**: both are
  correctly hedged against their own cited evidence.
- **The "NOT ARMED" verdict itself — REFUTED**: the unverified GitHub-write, shell/git-execution,
  and network-egress claims are sufficient on their own to justify refusing a repo-worker mandate;
  the gating is not overreach.
- **Silent confirmation of F5/F9/F10/F11 — REFUTED**: the downstream sections (Standing mandate,
  BARRED list) consistently keep those capabilities withheld rather than assuming them.

11 objections survived as real weaknesses, mostly about evidentiary rigor rather than the
headline verdict:

- Several F1-F4/F6/F7/F13 claims cite a source by name without a retrievable link for the
  specific granular fact asserted — the bundles are not independently reproducible from this
  document alone.
- F6's "approval is per-action inside a run" is this document's own inference from the schedules
  page, not something that page states directly.
- F9/F10's "likely product conflation" / "likely a mixed-up reference to Gemini CLI" framings are
  reasonable inferences but are stated with more confidence than an unpreserved search actually
  supports.
- F11: an HTTP 404 on the counter-source repo is real and worth flagging, but does not by itself
  prove the repo was fraudulent/malware — "treat its claim as fabricated" is a stronger claim than
  the 404 alone establishes (the marketing-language pattern-match is the actual basis, and that is
  in the text, but the two grounds read as one).
- **Real scope inconsistency, worth fixing**: the BARRED list says "never at `.git`-tracked source,"
  but the Standing mandate scopes Spark to `.worktrees/spark-<task-id>/`, which is itself a git
  worktree with `.git`-tracked content. The intended distinction (never the *main checkout* /
  history-mutating operations, vs. a disposable per-task worktree) is clear from context elsewhere
  in the doc but is not stated precisely at that line.
- Re-arming on any single one of F5/F9/F11 being re-verified may be too permissive — F9 in
  particular currently has no stated test procedure that could prove fail-closed egress even if an
  operator tried to re-verify it.

None of the survived objections overturn the headline verdict (Spark is not a repo-lane worker
today, NOT ARMED); they sharpen citation rigor and flag one real wording inconsistency in the
BARRED list that a future edit should tighten.
