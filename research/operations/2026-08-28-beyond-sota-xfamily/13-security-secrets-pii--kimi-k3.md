---
panel: beyond-sota-xfamily
lane: 13-security-secrets-pii
seat: kimi-k3
model: "kimi-code/k3 · Kimi CLI print mode (tools)"
started: 2026-08-28T19:31:38Z
finished: 2026-08-28T19:37:49Z
duration_s: 371
exit: 0
words: 5072
prompt_sha256_16: fbb47e99edf00f6d
prompt_chars: 19404
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

• I'll ground in the repository evidence first, then survey the web, then write the report. Starting with parallel repo probes.

• Strong scar evidence already. Continuing with the mechanism files and security CI gates.

• Two final verifications of primary sources, then I'll write the report.

• Grounding and survey complete. The deliverable follows as my final message (per the lane brief, the report is returned inline rather than written to disk; the worktree path in the protocol is outside this read-only snapshot, and no `ls`/`wc` probe is applicable).

  ---

  ```
  ---
  date: 2026-08-28
  domain: operations
  panel: beyond-sota-2026-08-28
  part: 13/13 — Security, secrets & PII engineering
  model: Moonshot Kimi K3 (pinned lane)
  sources: 14
  repo_files_verified: 39
  status: complete
  ---
  ```

  # Beyond-SOTA — Lane 13: Security, secrets & PII engineering

  ## 0. TL;DR

  Nuzantara is **AT or slightly AHEAD of SOTA on doctrine and PII-boundary discipline, and BEHIND on the mechanical enforcement planes** — network (tailnet default allow-all with a measured unauthenticated writable shell), agent sandboxing (hooks instead of OS-level isolation), and token lifecycle (6 OAuth seats with no identity, no dead-slot detection). The biggest gap is not a missing control but a missing **census**: credentials, secret-bearing surfaces and outbound lanes are guarded one-at-a-time, after each incident, by hand — 45 open `operator[secret]` rows in PENDING-ARMS prove the backlog is operator-bound, not knowledge-bound. Top-3 moves: (1) generalize `infra/llm-credentials/declared.json` into a **fleet credential capability-ledger with a CI lint that fails on undeclared secret references**; (2) a **denylist env-scrubbing launcher** for every external LLM CLI seat (Codex/Kimi/agy), generalizing the defense already proven in `apps/backend-rag/backend/llm/claude_oauth_client.py`; (3) **transcript/outbound PII+secret egress gate** — the yield pitch-gate pattern lifted to harness level. Honest credits: the Law-2 output boundary with a deterministic fail-closed gate and guilt+innocence corpus, the scar corpus as a public incident ledger, and CODEOWNERS tier-1 anti-injection design are genuinely rare in the surveyed world.

  ## 1. How Nuzantara does it today

  Every claim below was verified in this session against the snapshot.

  **The PII output boundary (Law 2).** `SYMBIOSIS.md:242-255` carries the output frontier as non-negotiable: no client PII/OSINT transcribed in cleartext into outputs, memories, skills, logs, reports, alerts, reusable prompts, or shared artifacts — IDs/hashes/placeholders instead. Exactly **one named derogation** exists: the `S7` yield digest to the assigned team member's WhatsApp, with an explicit allowed payload (first name + surname initial, `client_id`, deadline type/date, pitch text), an explicit forbidden payload (passport/KTP/NPWP/any document number/address/DOB/full name), a **content-level** filter on the free-text pitch (field-level filters declared insufficient), roster-resolved recipients with no fallback, and — critically — status **"authorized, NOT yet armed"**: no sending until the enforcement PR merges with a green corpus (`SYMBIOSIS.md:255`). `CLAUDE.md` §14 restates the boundary, anchors it to UU PDP Artt. 35-39, and records the chat-gateway fail-closed gap (no Art. 56 basis demonstrable before send) as an open PENDING-ARMS item — stated as *required conduct, not implemented state*, which is unusually honest doctrine.

  **Enforcement of the boundary exists as code, not prose.** `scripts/yield_optimizer_pitch_gate.py` is the deterministic, fail-closed PII gate for the S7 pitch, and `.github/workflows/yield-optimizer-pii-gate-tests.yml` arms its guilt+innocence+class-guard test suite per-PR — the header explicitly says the suite previously ran only in a report-only nightly sweep, which would be superscar #2 for a guardrail whose whole point is to be armed. `infra/claude-hooks/data_plane_guard.py` + `data-plane-registry.json` (2 entries: `kbli-filiera`, `kbli-gold-editorial`) block hand-edits of curated datasets across Edit/Write/Bash/Monitor with segment-scoped command parsing informed by five prior over-match scars. `infra/claude-hooks/host_boundary.py` blocks writes into `~/.claude`, `~/.ssh`, `~/.aws`, secret dotfiles, `~/.agent/decisions/` — and exists *because* plan mode is not a sandbox: without it an agent could rewrite `_phase.py` and disarm the phase switch itself. Reads of secret files emit WARN, not BLOCK.

  **Secrets hygiene.** Superscar family #4 (`Secret in the clear`) has an executable antidote: `scripts/secrets_permissions_audit.py` — an lstat-only auditor (it never opens a file it inspects, "an audit tool for secrets must not itself become a way to exfiltrate them"), `--fix` chmods 0600 on dotfiles *and* `.bak`/`.orig`/`~` siblings. `docs/runbooks/secret-rotation.md` encodes the atomic fleet-rotation rule born from the 2026-07-18 incident: "a secret is rotated only when every consumer reads the NEW value"; canonical store = per-machine `~/.nuzantara-secrets.env` 0600; `.mcp.json` env blocks FORBIDDEN for the rotated key class; plist `EnvironmentVariables` forbidden (W65). CI backstops: `fly-secrets-check.yml` (weekly dead-man's-switch validity check of `FLY_API_TOKEN`), `telegram-secret-healthcheck.yml` (fails loud on 401 from getMe — born because 13 alerting workflows all `curl || true` and a rotated token failed silently for 10 days). `catE-sovereignty-lint.yml` + `catE-paid-anthropic-baseline.txt` (3 known sites) fail the build if a NEW paid-Anthropic instantiation appears — the SDK ban (`CLAUDE.md:155`) enforced at CI, plus an `apps/*/.env` permission check.

  **Repo hygiene / public surface.** The repo is **public**. Pre-commit: `.pre-commit-config.yaml` runs Yelp detect-secrets v1.5.0 against `.secrets.baseline`. CI `security.yml` has a required `detect-secrets` job with an auto-triage rule set (`scripts/detect_secrets_auto_triage.py`) — the FROZEN.json false-positive incident (scar, 2026-06-02) shows the gate is armed repo-wide. `.github/CODEOWNERS` puts `.github/workflows/`, `dependabot.yml`, `CODEOWNERS` itself and the unattended-autofix scripts under TIER-1 owner review, with the stated threat model "agentic workflow injection … block any agent from silencing CI checks". GitHub-side push protection is **not evidenced anywhere** in the repo (no mention in workflows/docs) — assumption stated: not enabled, or at least not relied upon.

  **Supply chain.** `.github/dependabot.yml` (weekly, grouped, carefully-curated ignores with measured ceilings), `sbom.yml` (SPDX/CycloneDX per push to main, framed as UU-PDP audit posture), `semgrep.yml` (path-scoped, explicitly **not** a required check), `sonarqube.yml`, `docs/security/CVE_TRIAGE_POLICY.md` (closes the "everything was continue-on-error:true" gap with severity→action rules). W98's antibody is a CI test (`backend/tests/test_lock_honors_requirements.py`) that fails if the lock violates a manifest specifier — because Dependabot's lock-regenerator does not read manifest `!=` pins and shipped a known-malicious fastapi to prod for ~2h with green Snyk/Socket.

  **RBAC & verification model.** `CLAUDE.md` §13: CRM admin set is 3 named accounts; team sees only `assigned_to` rows. Subhi's perimeter is a **verification model, not a path fence**: whole-repo code access, but machine+AI verification only (the owner does not review), grader self-protection via TIER-1 CODEOWNERS on the gates themselves. `docs/runbooks/portal-auth-session-operations.md` documents token revocation (jti, 1h access tokens, revoke-all epoch). One measured defect from the lane brief's memory list (front-end auth state in localStorage) is consistent with repo evidence: `apps/mouth/src/lib/realtime.test.ts` reads `auth_token` from localStorage with sessionStorage fallback — JWT-in-localStorage is XSS-exposable by construction.

  **Tailnet.** `infra/tailscale/policy.hujson` is **PROPOSED, not applied**: measured 2026-08-11, the live tailnet runs default allow-all, and `tailscale serve` on Pro publishes an **unauthenticated writable ttyd zsh shell** (`/term` → `ttyd -W zsh`, answered 200 from another node) on the machine holding the wa-mirror raw PII and the secrets env. The file is a model of honest posture: it declares its own validation limit (no Tailscale API token on the fleet; only the admin console can accept it) and orders the apply **before** any team device joins. Latent passwordless-root Tailscale SSH grant is deliberately narrowed in the proposed policy at zero operational cost.

  **OAuth seats / banned paid path.** `apps/backend-rag/backend/llm/claude_oauth_client.py` shells out to the `claude` CLI with 4-token fallback (`CLAUDE_CODE_OAUTH_TOKEN_{1..4}` + legacy), and `_build_env` (lines ~221-240) **strips** `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, Bedrock/Vertex prefixes from the child environment — the one place in the repo where env-inheritance poisoning is defended mechanically. `infra/llm-credentials/declared.json` is the start of a credential census: sha256-hashed credential identifiers (never the uid), each with a label and owner, born from a rogue dev key that made 5,344 billable calls invisible to the cost ledger. **Assumption stated:** the MEM-referenced discoveries (Chronicle screen recording, secret-scanning API returning the secret, external CLIs inheriting session env, fly-env token poisoning, team_members holding logins on personal domains, squash not unpublishing leaks) were not readable — memory is outside this snapshot; I treat them as unverified but consistent with on-disk scars.

  ## 2. Scars & ledger evidence in this area

  This is the richest evidence base on the panel — security is the organism's most-scarred craft.

  | Evidence | What bit | Recurrence |
  |---|---|---|
  | Superscar **#4** whole family (`.claude/rules/cicatrix-superscar.md:103-114`) | Prod credentials world-readable on disk; `.bak` inherits exposure; secret on the same stdin `bash -s` consumes | **5 named members**: P0 2026-06-03 `apps/cell/.env` (superuser DB password into a session transcript via plain `cat`), W65 (skills-bridge `.bak` 64-hex key), W75 (fly-ssh secret leak on pipe — fixed PR #1372 with `_shq()`), P0 2026-05-21 (postgres password in 32 files), 2026-04-29 (plist world-readable) |
  | `cicatrix-scars.md:746-754` (P0 2026-07-14) | `launchctl print` — a *diagnostic probe* — dumped the whole inherited env incl. `TELEGRAM_BOT_TOKEN` into the transcript → fleet-wide rotation across GH Actions (11 consumers), Fly (2 names, same digest), 3 machines, 2 plists with the literal value | New vector class: *the blast radius of a probe exceeds the question asked* |
  | **W98** (`cicatrix-scars.md:692`) | Dependabot lock-regen bypassed the `!=0.136.3` anti-malware manifest pin; MAL-2026-4750 ran in prod ~2h, Snyk+Socket green | Family #2 (Esiste≠Armato): constraint armed at compile time, nobody armed it at install time |
  | FROZEN.json incident (`cicatrix-scars.md:443-453`) | Own audit artifacts tripped the required detect-secrets gate, blocking every PR repo-wide | Self-inflicted: the scanner scans the auditors |
  | 2026-07-18 rotation scar (`docs/runbooks/secret-rotation.md` header) | Rotated key lived only on Pro; every `.mcp.json` shadowed it with a stale inline copy; 2 days of silent 401s | "Rotated ≠ propagated" |
  | W102-adjacent (`telegram-secret-healthcheck.yml` header) | Rotated bot token never re-set in Actions; every alert workflow swallowed the failure (`|| true`) — 10 days of green-but-dead alerting | Fail-open alerting is the default failure mode of every notifier in the repo |
  | Burned `@Balizerobot` (`CLAUDE.md` §13) | Bot token committed to the **public** repo's default branch; **cannot be revoked** (BotFather answers only the lost creator account); valid indefinitely in git history | The public-repo forcing function at its most irreversible; 119 hardcoded fallbacks to a dead destination cleaned 2026-08-13 |
  | `infra/llm-credentials/declared.json` comment | Rogue M5 dev key: 5,344 billable calls in 3 days, invisible to every repo-side cost check, silenced the production WhatsApp bot | Ledger-blind credential = invisible spend |
  | PENDING-ARMS | `grep -c "operator\[secret\]"` = **45 open operator[secret] rows** | The remediation backlog is gated on one human's GUI/ceremony time, not on knowledge |
  | AMENDMENTS | (52 KB loop misfire log — grep found no security-specific rows beyond those above; stated as checked) | — |

  Pattern across all of these: **every control exists; almost every incident is an unarmed, unpropagated, or un-censused instance of a control that exists elsewhere.** Rotation runbook exists → `.mcp.json` copies unrotated. Env-strip defense exists → only inside one OAuth client. chmod antidote exists → 5 incidents before it, 45 operator rows after it.

  ## 3. World SOTA survey

  | System / practice | Source | Mechanism | Measured effect | Transfer to this organism |
  |---|---|---|---|---|
  | OWASP Top 10 for LLM Apps (2025): LLM01 prompt injection, LLM02 sensitive-info disclosure, LLM03 supply chain, LLM06 excessive agency | [owasp.org GenAI project](https://owasp.org/www-project-top-10-for-large-language-model-applications/) (2025 ed.) | Community risk canon every pentest maps to | Industry-standard checklist | Directly: Law 2 covers LLM02; hooks cover parts of LLM06; no systematic mapping exists in-repo |
  | OWASP Agentic AI threats & mitigations | [genai.owasp.org](https://genai.owasp.org/agentic-ai-threats/) | Threat model for tool-using agents (memory poisoning, tool misuse, privilege compromise) | Reference taxonomy | High — the fleet is exactly this deployment shape |
  | **CaMeL** (Google DeepMind/ETH, arXiv:2503.18813, Mar 2025) | [arxiv.org/abs/2503.18813](https://arxiv.org/abs/2503.18813), 291 citations | Privileged LLM (trusted queries only, emits plans) + Quarantined LLM (untrusted data, no tools) + capability-tagged data-flow interpreter — injection becomes *structurally* impossible, not probabilistically reduced | Provable guarantees under the paper's threat model | Partial: full CaMeL needs a custom interpreter; but the **priv/quar split transfers cheaply** to the intel-scraper→RAG and web-fetch→session paths |
  | Design Patterns for Securing LLM Agents (Beurer-Kellner et al., arXiv:2506.08837, Jun 2025) | [arxiv.org/abs/2506.08837](https://arxiv.org/abs/2506.08837) | Six patterns (action-selector, plan-then-execute, LLM map-reduce, dual-LLM, code-then-execute, context-minimization); core law: "once an agent ingests untrusted input, it must be constrained so that input cannot trigger consequential actions" | Analytical, benchmarked on AgentDojo | High — the organism's hook layer already enforces this *for files*; not yet for data-to-action flows |
  | **Lethal trifecta** (Willison, Jun 16 2025) | [simonwillison.net/2025/Jun/16/the-lethal-trifecta/](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) (fetched) | private data + untrusted content + exfiltration channel = exploitable, *regardless of guardrails*; "95% detection is a failing grade" | Dozens of documented production exploits (Copilot, Slack AI, GitHub MCP…) | Definitional: every agent session here holds all three legs (secrets env + web content + outbound curl/TG). The organism's only structurally-sound move is breaking a leg, not scanning content |
  | **Claude Code sandboxing** (Anthropic, Oct 20 2025) | [anthropic.com/engineering/claude-code-sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing) (fetched) | OS-level filesystem isolation (bubblewrap/seatbelt) + network isolation via egress proxy with domain allowlist; credentials never inside the sandbox (proxy injects them) | 84% fewer permission prompts, safely | **The headline gap.** Nuzantara's hooks are advisory pre-execution filters in the *same* process trust domain; Anthropic's SOTA is kernel-enforced fs+net boundaries. macOS seatbelt is available on all three fleet machines today |
  | GitHub push protection + secret scanning | [docs.github.com](https://docs.github.com/en/code-security/concepts/secret-security/push-protection); [GitGuardian analysis](https://blog.gitguardian.com/github-push-protection-enhancing-open-source-security-with-limitations-to-consider/) (Jul 2025) | Push-time blocking of ~200 token formats, free + default-on for public repos; provider partner program auto-revokes | Prevents the leak class at push time | Trivially applicable — this repo is public and the burned-token scar is exactly what push protection exists for. Not evidenced as enabled |
  | gitleaks / trufflehog / detect-secrets | [github.com/gitleaks/gitleaks](https://github.com/gitleaks/gitleaks) | Pre-commit + CI regex/entropy scanning | Baseline table stakes | Already present (detect-secrets pre-commit + required CI job) — AT SOTA |
  | SLSA + Sigstore + SBOM | [slsa.dev](https://slsa.dev) | Provenance attestation, hash-pinning, signed releases | Framework, no single number | SBOM exists (AT); provenance/hash-pinning absent (BEHIND) — and W98 shows the lock pipeline is the weak link |
  | Tailscale ACLs / BeyondCorp zero-trust | [tailscale.com/kb/1018/acls](https://tailscale.com/kb/1018/acls); [BeyondCorp papers](https://research.google/pubs/beyondcorp-a-new-approach-to-enterprise-security/) | Deny-by-default ACLs, device identity, no implicit network trust | Google's post-2009 operating model | The proposed `policy.hujson` *is* this — unapplied. The measured unauth ttyd shell would be a career-ending finding at any surveyed org |
  | Microsoft Presidio (PII detection/redaction) | [github.com/microsoft/presidio](https://github.com/microsoft/presidio) | NER + recognizers for PII in text streams, pluggable deny-recognizers | Production-grade OSS | Already a dependency (dependabot.yml wrestles presidio's cryptography ceiling) — but not evidenced as an **egress filter on agent outputs**, which is where Law 2 actually lives |
  | Anthropic Auto Mode / permission classifiers | [anthropic.com/engineering/claude-code-auto-mode](https://anthropic.com/engineering/claude-code-auto-mode) (Mar 2026, via index) | Two-stage classifier gates overeager actions; approval-fatigue is the enemy (93% of prompts approved) | 0.4% FP on n=10,000 real traffic | Validates the organism's instinct: deterministic hooks for known-bad, classifier for novel-bad |

  The three that matter most. **Willison's trifecta** reframes the whole lane: Nuzantara's prompt-injection surface is not scannable away; the live defenses (`guardrails-static.py`, `prompt-injection-scan.sh` — both host-side, verified only by name in `infra/claude-hooks/README.md` references, not readable from this snapshot) are exactly the "95% guardrail" category Willison warns about. The structurally sound responses are the ones already half-built: env-scrubbing (breaks the private-data leg for CLI seats), sandboxed egress (breaks the exfiltration leg), S7-style payload allowlists (breaks it for data lanes). **Anthropic's sandboxing post** is the uncomfortable benchmark: same threat model (prompt-injected agent on a developer machine), same OS (macOS seatbelt is native to every fleet machine), and they went kernel-level while Nuzantara stayed hook-level. Hooks are bypassable by any subprocess the hook doesn't see; a seatbelt profile is not. **CaMeL** matters because the organism's highest-value data flow — untrusted web/intel content flowing into sessions that hold credentials and outbound tools — is precisely the priv/quar split's home turf, and a cheap approximation (untrusted content enters only through tools whose outputs are tagged and never interpolated into system/tool-call positions) needs no research interpreter.

  ## 4. Position vs SOTA

  | Sub-dimension | Verdict | Evidence |
  |---|---|---|
  | PII output boundary (Law 2) doctrine + derogation engineering | **AHEAD** | `SYMBIOSIS.md:242-255` — named-exception-with-enforcement-before-arming, content-level (not field-level) filtering, no-fallback recipients, explicit anti-generalization clause. I found no surveyed org writing derogations this rigorously |
  | PII boundary *mechanization* | AT→BEHIND | One deterministic gate (`yield_optimizer_pitch_gate.py`) for one lane; Presidio in the dep tree but not wired as an egress filter; chat-gateway fail-closed is doctrine, not code (CLAUDE.md §14 says so) |
  | Secrets at rest on machines | BEHIND→AT | 5-incident family (#4) *but* executable antidote + runbook + CI perm check; Vault/SOPS-class management absent (flat env files), acceptable at this scale only because machines are owner-only — breaks at team expansion |
  | Secrets in motion (transcripts/probes/env) | BEHIND | Three measured transcript leaks (cat .env, launchctl print, bash -s stdin); env-strip defense exists in exactly one file; no general launcher hygiene |
  | Public-repo hygiene | AT | detect-secrets pre-commit + required CI + auto-triage + rotation-first doctrine; but no push protection evidenced, and a permanently-unrevocable token in history |
  | Prompt-injection defense | BEHIND | Guardrail-scan class only; no trifecta-leg-breaking architecture, no priv/quar separation on intel ingestion |
  | Agent sandboxing | BEHIND (the biggest structural gap) | Hooks-as-backstop + Codex `--sandbox workspace-write` convention (AGENTS.md:190-202, discipline-by-convention, hooks are Claude-side only) vs Anthropic's kernel fs+net isolation. No network egress control anywhere on the agent plane |
  | Supply chain | AT | SBOM + CVE triage policy + W98 lock-integrity test (that test is rarer than SBOMs); but Dependabot regen risk class remains, no hash-pinning/provenance |
  | RBAC / CODEOWNERS / verification-not-perimeter | AT→AHEAD | TIER-1 anti-injection CODEOWNERS with the grader-self-protection property (a gate-weakening diff fails by construction) is a genuinely strong design for a solo-owner repo |
  | Tailnet / zero trust | BEHIND (most dangerous single finding) | Default allow-all live; unauthenticated writable ttyd shell on the PII machine measured 2026-08-11; fix written, unapplied, operator-GUI-gated |
  | Token lifecycle (OAuth seats, Drive, Fly) | BEHIND | Tokens carry no identity; dead slots fail silently (Drive `invalid_grant` discovered by consumer failure, CLAUDE.md §13); only 2 dead-man's-switch healthchecks exist (Fly, Telegram) against a fleet of credential consumers |
  | Incident recording & disclosure discipline | **AHEAD** | The scar corpus is a public, measured, recurrence-tracked incident ledger with executable antidotes. Most surveyed orgs do this internally; almost none make it load-bearing for the next incident |

  ## 5. Beyond-SOTA recommendations

  Ranked by (impact × confidence) / cost.

  **R1 — Credential Capability Ledger (generalize `declared.json` to every secret-bearing surface) + CI lint.**
  *What:* One registry (`infra/credentials-ledger.json`) where every credential the fleet holds gets an entry: hashed identifier, owner, consumer list (files/launchd labels/workflows), rotation runbook pointer, last-rotated, healthcheck pointer. A CI lint greps the repo + declared consumer manifests for secret *names* and fails on any reference to an undeclared credential — the exact `declared.json`/cost-ledger pattern, lifted from one Google key to the whole fleet.
  *Why beyond SOTA:* Vault/1Password answer "where is the secret"; nobody in the survey answers "which surfaces can this secret silently die or leak on, and is every one of them registered." The organism's measured failures (stale `.mcp.json` shadows, 2-name Fly secrets, plist literals, ledger-blind keys) are all *census* failures. It exploits the declared-pairs/declared.json asymmetry already proven in-repo.
  *Cost:* ~6h + flat-sub tokens. *Gear:* 2. *Risk:* registry drift → same superscar #1 class the `lint_home_fork.py` merge pattern already solves; low. *Metric:* declared credential surfaces ÷ discovered surfaces (weekly scanner diff) — before: 1 declared (Gemini key) vs dozens referenced in CLAUDE.md §13/workflows; after: 100%, and every open `operator[secret]` row (45) mapped to a ledger entry. *Kill:* lint false-positive rate blocks PRs >2×/month. *First PR:* `infra/credentials-ledger.json` (schema + seed from the 3 known stores) + `scripts/credential_ledger_lint.py` + one workflow job (~300 lines).

  **R2 — Env-scrubbing launcher for all external LLM CLI seats (`agent-exec` shim).**
  *What:* A single wrapper (e.g. `scripts/agent_exec.sh`) through which every headless `codex exec` / `kimi` / `agy` invocation runs: it rebuilds the child environment from an **allowlist** (PATH, HOME, TERM, git, the seat's own OAuth token) instead of inheriting the session env — generalizing `claude_oauth_client.py::_build_env`'s denylist-strip into an allowlist, which is the robust direction.
  *Why beyond SOTA:* surveyed practice scopes *credentials* to sandboxes (Anthropic's proxy-injection); an allowlist env for CLI seats on a mixed-use workstation — where `.nuzantara-secrets.env` is sourced into shells — is a gap nobody productizes, and it directly breaks the lethal trifecta's private-data leg for every non-Claude seat (the seats with the weakest native sandboxing).
  *Cost:* ~4h. *Gear:* 2. *Risk:* a missing allowlisted var breaks a seat's workflow — superscar #3 (over-match) shape; mitigate with WARN-log of dropped names. *Metric:* `env | grep -cE 'TOKEN|KEY|SECRET|PASSWORD'` inside a child process — before: everything exported (dozens, per the launchctl P0), after: ≤5 declared. *Kill:* breaks ≥1 production cron that can't be allowlisted in 1 iteration. *First PR:* the shim + unit test asserting denylist names absent + AGENTS.md one-line convention change (~150 lines).

  **R3 — Harness-level egress gate: Law-2 + secrets filter on outbound text (PostToolUse / send-path).**
  *What:* One shared module (`pii_egress_filter`) — Presidio recognizers + Indonesian-format regexes (KTP 16-digit, NPWP, passport) + detect-secrets entropy pass — applied at every *outbound* chokepoint: Telegram/alert sends, memory saves, report artifact writes, and the S7 dispatcher (which already has its own gate — this subsumes it). Fail-closed with HELD semantics copied from the S7 design.
  *Why beyond SOTA:* PII DLP exists (Nightfall/Presidio) for *data stores*; enforcing a statutory output boundary at the *agent harness* level, with the organism's signature guilt+innocence corpus, is not in any surveyed system — and it converts Law 2 from "every program must remember" (the yield-gate header's own critique: "prose an LLM has to remember every run") into "the harness cannot emit it."
  *Cost:* ~10h + corpus curation. *Gear:* 3 (touches outbound lanes). *Risk:* false positives HELD legitimate alerts (recurrence of the FROZEN.json self-block class) — corpus-first development is the mitigation. *Metric:* armed outbound surfaces ÷ total (before: 1 of ~15 alert/notification workflows; after: all); plus replay of the 3 transcript-leak scars as test cases → 0 pass. *Kill:* FP rate >1/week on the TG alert lane after tuning. *First PR:* the module + guilt/innocence corpus + wiring into ONE lane (TG alerts) (~380 lines).

  **R4 — Apply the Tailscale policy + kill the unauth ttyd shell.** `needs-ruling` (GUI/console). *Why:* the single highest-severity live exposure measured in the repo; the policy file is already written, ordering-safe, and zero-downtime. *Metric:* packet-filter rule count on the live netmap (1 → policy count); `/term` answers 401/none from a peer node. *Kill:* n/a. *First PR:* none possible — operator console action; the PR is a post-apply verification script committed to `infra/tailscale/`.

  **R5 — Seat-identity manifest for the 6 OAuth seats + dead-slot canary.**
  *What:* a per-seat manifest (seat id → token sha256[:16], machine, lane) mirroring `declared.json`, plus a scheduled canary that performs one cheap authenticated call per seat and pages on failure — the `telegram-secret-healthcheck.yml` dead-man's-switch pattern generalized to the seat fleet.
  *Why:* "a token on a closed slot = a silently dead lane" is the W102/Telegram-401 failure mode transplanted to the fleet's most expensive dependency. *Metric:* time-to-detect a dead seat — before: unbounded (discovered by work stalling), after: <1 canary interval. *Cost:* ~3h. *Gear:* 2. *Kill:* canary itself pages falsely >2×/month. *First PR:* manifest + canary script + cron entry (~200 lines).

  **R6 — Privileged/quarantined split for untrusted-content ingestion (cheap CaMeL).**
  *What:* convention + lint: content fetched from web/MCP/intel scrapers enters sessions only via tool results marked untrusted, and a `zantara-core`-level rule (already the SSOT for prompt rules) plus a lint in `catE`-style that fails new code paths interpolating fetched content into system prompts or tool-call arguments.
  *Why beyond SOTA:* CaMeL proper needs an interpreter nobody will maintain here; the *pattern* (LLM06/trifecta leg-breaking by construction) enforced by a CI lint on the prompt SSOT is a composition none of the surveyed systems ship as a lint. *Metric:* count of code paths interpolating untrusted fetch output into privileged positions — before: unmeasured; after: 0 new ones (ratchet, like the catE baseline). *Cost:* ~6h. *Gear:* 2. *Risk:* superscar #3 over-match in the lint. *Kill:* lint requires >3 baseline entries in first month (pattern too fuzzy to ratchet). *First PR:* `scripts/lint_untrusted_context_flow.py` + baseline + zantara_core section (~350 lines).

  **R7 — Enable GitHub push protection + leak-runbook addendum.** `needs-ruling` (repo setting, operator GUI). Free for public repos; blocks the @Balizerobot class at push time. Pair with a `docs/runbooks/public-repo-leak.md`: revoke-first, filter-repo second, "squash does not unpublish" (per the lane's MEM discovery, unverified here) as the standing doctrine. *Metric:* push-protection enabled flag; simulated test-push of a known-format dummy token blocked. *Cost:* 30 min operator.

  **R8 — macOS seatbelt profile for headless agent lanes (track Anthropic SOTA).**
  *What:* wrap `codex exec`/headless claude lanes in `sandbox-exec` with a profile granting worktree-write + deny-by-default network except an allowlist. *Why:* closes the structural sandboxing gap on the fleet's own OS primitive; Anthropic open-sourced theirs. *Metric:* exfiltration drill (canary file read + outbound curl attempt from inside the lane) blocked 100%. *Cost:* ~12h tuning; highest cost on the list, hence ranked last despite highest ceiling. *Gear:* 3. *Risk:* profile friction breaks builds (permission-prompt class failure). *Kill:* >2 broken lanes/week after 2 tuning rounds. *First PR:* profile for ONE lane (codex headless) + drill script (~250 lines).

  ## 6. 90-day roadmap + first PRs

  **Wave 1 (days 0-30) — census and leg-breaking, all Gear 2:**
  - PR-A "Credential Capability Ledger v1" (R1): `infra/credentials-ledger.json`, `scripts/credential_ledger_lint.py`, `.github/workflows/credential-ledger-lint.yml`. ≤350 lines. Acceptance: lint red on a synthetic undeclared `FOO_API_KEY` reference in a test fixture; green on main; ledger maps all 45 PENDING-ARMS `operator[secret]` rows to entries.
  - PR-B "agent-exec env allowlist shim" (R2): `scripts/agent_exec.sh` + `scripts/tests/test_agent_exec_env.py`. ≤150 lines. Acceptance: child `env` contains only allowlisted names; 3 transcript-leak scar vectors replayed (cat .env content never reaches a child env).
  - PR-C (operator, needs-ruling): apply `infra/tailscale/policy.hujson` + decommission `tailscale serve /term`; commit `infra/tailscale/verify_policy_applied.sh`. Acceptance: netmap rule count >1; `/term` not 200 from a peer.

  **Wave 2 (days 31-60) — egress boundary, Gear 3:**
  - PR-D "PII/secret egress filter on TG alert lane" (R3, stage 1): module + corpus + one wiring. ≤380 lines. Acceptance: 3 historical leak payloads replayed → HELD; 30 days of real alert traffic shadow-mode FP log reviewed before enforce.
  - PR-E "Seat manifest + canary" (R5). ≤200 lines. Acceptance: simulated revoked seat pages within one interval.
  - PR-F (operator, needs-ruling): enable GitHub push protection + `docs/runbooks/public-repo-leak.md`.

  **Wave 3 (days 61-90) — architecture:**
  - PR-G "Untrusted-context-flow lint + baseline" (R6). ≤350 lines. Acceptance: ratchet baseline generated; synthetic interpolation fixture red.
  - PR-H "seatbelt profile for codex-headless lane" (R8, pilot). ≤250 lines. Acceptance: exfiltration drill blocked; lane's normal workload suite green.
  - Close-out: re-run measures (declared ÷ discovered = 1.0; armed outbound ÷ total ≥ 0.8; operator[secret] rows 45 → <10) and scar the residuals.

  ## 7. Needs-ruling

  - **Apply the Tailscale ACL** in the admin console and remove/replace the unauthenticated `ttyd` serve — GUI-only; also the *timing* decision relative to any teammate device joining (policy itself declares ordering load-bearing).
  - **Enable GitHub push protection** on the public repo (repo setting, owner action).
  - **45 open `operator[secret]` rotations** in PENDING-ARMS — each is a credential ceremony only Zero can perform; R1's ledger at least sequences them by blast radius.
  - **Chronicle screen-recording surface** (MEM discovery, unreadable from this snapshot): whether to keep, sandbox, or drop a recorder that captures the screen of the PII machine is a business/privacy decision.
  - **E33/client-facing consent posture** for any future cloud-processing basis under UU PDP Art. 56 (the chat-gateway fail-closed gap is already declared open doctrine in CLAUDE.md §14).

  ## 8. §Meta-pattern

  One defective belief generates nearly everything in this lane: **"a control that exists protects."** It is superscar #2 (Esiste≠Armato) specialized to security, and the evidence is uniform: the rotation runbook existed while `.mcp.json` copies silently shadowed the new key; the `!=` anti-malware pin existed while the installer never read it (W98); 13 alert workflows existed while the token was dead (W102); the PII gate existed while its tests ran in a report-only sweep (yield-gate header); the Tailscale policy exists *today* while the tailnet is allow-all with an unauthenticated root-adjacent shell; the env-strip defense exists in exactly one OAuth client while every other seat inherits the whole environment. The organism's security incidents are never "we didn't know" — they are "we knew, built it, and armed it one surface at a time, by hand, after each incident." The beyond-SOTA moves that matter (R1, R2, R3) are therefore all the same move: **convert each proven per-incident control into a censused, CI-armed, fleet-wide default** — which is precisely the asymmetry this organism has and the surveyed giants lack: a complete, measured, machine-readable record of exactly how every control failed to be armed.

  ## 9. Sources

  1. [OWASP Top 10 for LLM Applications 2025](https://owasp.org/www-project-top-10-for-large-language-model-applications/) — accessed 2026-08-28 — canonical risk taxonomy for LLM apps (LLM01/02/03/06 map directly to this lane).
  2. [CaMeL: Defeating Prompt Injections by Design (arXiv:2503.18813)](https://arxiv.org/abs/2503.18813) — accessed 2026-08-28 — strongest architectural prompt-injection defense with provable guarantees (291 citations).
  3. [Design Patterns for Securing LLM Agents against Prompt Injections (arXiv:2506.08837)](https://arxiv.org/abs/2506.08837) — accessed 2026-08-28 — six deployable patterns; the "untrusted input must not trigger consequential actions" law.
  4. [Simon Willison — The lethal trifecta for AI agents](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) — accessed 2026-08-28 (fetched in full) — definitional framing of the exfiltration risk shape this organism lives in.
  5. [Anthropic — Claude Code sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing) — accessed 2026-08-28 (fetched in full) — the vendor SOTA benchmark for agent sandboxing on the same OS primitives the fleet runs.
  6. [GitHub Docs — Push protection](https://docs.github.com/en/code-security/concepts/secret-security/push-protection) — accessed 2026-08-28 — primary docs for the push-time secret block relevant to this public repo.
  7. [GitGuardian — GitHub push protection: benefits and limitations](https://blog.gitguardian.com/github-push-protection-enhancing-open-source-security-with-limitations-to-consider/) — accessed 2026-08-28 — independent analysis incl. default-on for public repos.
  8. [gitleaks](https://github.com/gitleaks/gitleaks) — accessed 2026-08-28 — reference OSS secret scanner (the repo uses detect-secrets, same class).
  9. [SLSA](https://slsa.dev) — accessed 2026-08-28 — supply-chain provenance framework against which SBOM-only posture is measured.
  10. [Tailscale KB — ACLs](https://tailscale.com/kb/1018/acls) — accessed 2026-08-28 — authoritative ACL syntax/semantics for the deny-by-default recommendation.
  11. [Google — BeyondCorp: a new approach to enterprise security](https://research.google/pubs/beyondcorp-a-new-approach-to-enterprise-security/) — accessed 2026-08-28 — zero-trust origin paper; the standard the flat tailnet violates.
  12. [Microsoft Presidio](https://github.com/microsoft/presidio) — accessed 2026-08-28 — production OSS PII detection/redaction; already in the repo's dependency tree, proposed here as egress filter.
  13. [OWASP Agentic AI — threats and mitigations](https://genai.owasp.org/agentic-ai-threats/) — accessed 2026-08-28 — threat taxonomy for tool-using agent fleets.
  14. [Anthropic — Claude Code Auto Mode](https://anthropic.com/engineering/claude-code-auto-mode) — accessed 2026-08-28 (via indexed research notes) — approval-fatigue evidence (93% auto-approval) justifying deterministic-over-interactive gates.

  **Verification note:** 39 repository paths verified on disk in this session (listed throughout §1-2 with exact paths and line numbers where useful). The lane brief's `MEM:` memory files were unavailable (memory directory is outside this read-only snapshot); each such claim is marked unverified where used. No secret file was opened and no secret value appears in this report.

