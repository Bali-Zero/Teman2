---
panel: beyond-sota-xfamily
lane: 13-security-secrets-pii
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T19:20:59Z
finished: 2026-08-28T19:29:36Z
duration_s: 517
exit: 0
words: 5944
prompt_sha256_16: c5061e0de56a43f3
prompt_chars: 19401
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 13/13 — Security, secrets & PII engineering
model: OpenAI GPT-5.6 sol, reasoning effort ULTRA (pinned lane)
sources: 12
repo_files_verified: 20
status: complete
---

## 0. TL;DR

Nuzantara is **ahead of SOTA in privacy doctrine**, **at SOTA in several defensive components**, but **behind SOTA in proving that those components form a closed, fail-safe boundary**.
The strongest asset is SYMBIOSIS Law 2: an unusually strict output boundary covering LLMs, agents, memory, logs, alerts, notebooks and shared artifacts.
The largest gap is process isolation: an inspected OAuth wrapper inherits most of the parent environment and passes prompts in process arguments, while multiple hooks warn or pass open instead of enforcing.
Secrets are well understood as a recurring failure family, yet the narrow credential declaration contains one entry while 29 `operator[secret]` ledger rows remain open.
Supply-chain scanning is broad, but W98 proved that green scanners do not ensure a lockfile still honors an explicit anti-malware constraint.
Top move 1: a revocation-first exposure circuit breaker for every public-history secret incident.
Top move 2: a metadata-only credential surface graph that binds issuer, identity, consumer, node and health without storing secret material.
Top move 3: a hermetic LLM process capsule—allowlisted environment, stdin-only prompts, verified sandbox and default-denied egress.
The defective belief underneath the gaps is: **“declared, warned or scanned” means “armed and enforced.”**

## 1. How Nuzantara does it today

### Scope and evidence boundary

This lane inspected 20 repository files without opening any secret-bearing file or printing any credential value. The brief’s named `MEM:` cases and live home-directory files—including the Chronicle, GitHub secret-scanning API, external-CLI inheritance and live guardrail discoveries—were outside the snapshot and therefore unavailable. They are not treated as evidence here. Repository copies and the scar/ledger corpus are used instead.

Because the deliverable is explicitly a final message, no report file was created; an `ls -la`/`wc -w` file probe would therefore be inapplicable and claiming one would violate the anti-hallucination rule.

### Privacy and PII boundary

SYMBIOSIS Law 2 forbids any LLM, agent, skill, memory, report, log, alert, notebook or shared/public artifact from persisting cleartext client PII or OSINT. Authorized processing may consume operational context, but outputs must use identifiers, hashes, placeholders or redaction. This is expressly framed as an internal policy more stringent than a claim that every cleartext occurrence is automatically criminal under UU PDP (`SYMBIOSIS.md:179-181`).

The rule has a DEV/PROD distinction. DEV permits cloud tooling over code, synthetic fixtures and non-client data while retaining the output boundary. PROD treats PII-bearing inference as processing and potentially cross-border transfer; the document records that the gateway lacks per-client proof, revocation and consent enforcement, requiring local/off-cloud processing or block/abstain until that gap closes (`SYMBIOSIS.md:181,240`). The sole bounded exception is S7: an internal yield digest sent to the assigned team member over an existing business channel. The exception is explicitly non-precedential (`SYMBIOSIS.md:242-253`).

The compliance corpus is broad. `docs/PDP_COMPLIANCE_PLAN.md:36-64,79-179,183-277` inventories classification, legal bases, scanning, audit logging, retention, encryption, erasure, cross-border safeguards, incident response, DPIA and DPO evaluation. `docs/UU_PDP_COMPLIANCE_REPORT.md:52-127,180-204` covers consent, DPIA/DPO posture, a 72-hour incident protocol and RAG-specific privacy directives. These are valuable control maps, but their headings and plans are not proof that each control is deployed, required or continuously tested.

### Secrets and credential lifecycle

`docs/runbooks/secret-rotation.md:1-66` correctly defines rotation as an atomic fleet operation: issuer change, propagation to every consumer and node, then an empirical work probe. A changed issuer credential without propagation is explicitly incomplete.

`scripts/secrets_permissions_audit.py:2-20,120-177,305-309,336-398` is stronger than a naïve mode checker:

- It uses path metadata and `lstat`, not file contents.
- It treats `.bak`, `.orig` and editor backups as inheriting the original sensitivity.
- It distinguishes a nominally permissive file inside an inaccessible parent directory from an actually reachable secret.
- Its remediation path applies mode `0600`.
- It avoids following symlinks during traversal.

Its candidate model is nevertheless primarily filename-shaped. The ledger records a real generic `settings.json` carrying a credential at mode `0644` that the auditor missed because the filename did not resemble a credential (`.claude/skills/modus/PENDING-ARMS.md:41`).

The inspected declaration `infra/llm-credentials/declared.json` contains one metadata-only entry, represented by a truncated fingerprint and operational labels rather than secret material. That is sound for its narrow allowlist purpose, but it is not a fleet-wide inventory. Consequently, “declared credential surfaces versus guarded surfaces” has no trustworthy denominator: the repository proves one declared narrow surface, not that every credential-bearing launcher, daemon, node or backup is declared.

### OAuth subprocess boundary

`apps/backend-rag/backend/llm/claude_oauth_client.py:1-9` follows the sanctioned OAuth CLI route rather than the paid Anthropic API. It strips exact Anthropic/provider-selector variables plus AWS, Bedrock and Vertex prefixes before launching the CLI (`:118-145`). It collects numbered token slots plus legacy/keychain sources, deduplicates by value, tracks cooldowns through non-secret fingerprints and avoids logging token material (`:194-240,330-340`).

Two structural weaknesses remain:

1. `_build_env` starts from the parent `os.environ` and removes a provider blocklist. Every unrelated exported variable remains inherited. This is the opposite of a least-privilege allowlist.
2. The prompt is appended to the subprocess argument vector (`:676-706`). Arguments can be observable through process inspection. The scar corpus already records the same class of defect in another client-data loop and its correction from argv to stdin (`.claude/rules/cicatrix-scars.md:1046`).

Token labels also do not establish account identity. A non-secret fingerprint proves “same token bytes,” not which subscription/account owns the token or whether that slot remains entitled. A closed or revoked slot can therefore remain structurally present while its lane is operationally dead.

A doctrine/enforcement conflict is visible. `CLAUDE.md:155-166` bans the Anthropic SDK and authorizes the OAuth CLI path. However, `.github/workflows/catE-sovereignty-lint.yml:68-95` explicitly permits an SDK constructor using an OAuth auth token and only blocks newly introduced paid-key paths relative to a baseline. The hard rule is CLI-only, but the gate encodes a broader exception.

### Hooks, sandboxing and prompt-injection boundary

`infra/claude-hooks/host_boundary.py:2-23,48-82,232-275` blocks writes to sensitive home destinations and secret-like dotfiles, but secret reads merely warn and continue. Parse failures also pass. A warning is useful operator feedback, but it does not prevent a secret from entering an agent transcript.

`infra/claude-hooks/data_plane_guard.py:2-12,139-164,538` protects registered curated datasets across write-capable tools and shell commands. Its registry currently contains two data-plane entries (`infra/claude-hooks/data-plane-registry.json`). It is not a general PII exfiltration control, and malformed or unreadable registry state warns and passes open. It also has an explicit kill switch.

The live `guardrails-static.py`, `guardrails-client.sh` and prompt-injection scan requested by the lane brief are outside this snapshot. Their installation, configuration and fail-open/fail-closed behavior cannot be confirmed here.

Agent sandbox doctrine is clear: Codex work must use `read-only` or `workspace-write`, never dangerous bypass (`CLAUDE.md:166`). What is missing from the inspected evidence is a machine-verifiable receipt proving that every external agent actually started inside the expected OS sandbox with network policy applied.

### CI, RBAC and supply chain

The repository contains ten security-shaped workflow filenames: `security.yml`, `semgrep.yml`, `sbom.yml`, `sonarqube.yml`, `fly-secrets-check.yml`, `catE-sovereignty-lint.yml`, `telegram-secret-healthcheck.yml`, `lint-content-reasoning-leak.yml`, `yield-optimizer-pii-gate-tests.yml` and `p3-sandbox-gates.yml`. `token-lint.yml` was inspected and excluded from this count because it checks visual design tokens, not credentials.

`.github/workflows/security.yml:52-53` declares ownership of four of 25 required contexts: two CodeQL contexts, Detect Secrets and Bandit. It runs on pull requests, pushes, merge-group events and schedules. Detect Secrets runs diff-scoped for PRs/merge groups and broadly for push/schedule, with a baseline and automated triage of known findings. CodeQL actions are commit-SHA pinned (`:650-664`). Some auxiliary scanners are advisory or `continue-on-error`; the workflow explains that Docker Snyk cannot be required where Dependabot lacks secrets (`:478-486`).

This is a strong design, but repository comments cannot prove current GitHub branch-protection state. The sovereignty workflow is explicitly non-required (`.github/workflows/catE-sovereignty-lint.yml:1-35`), so it can report a violation without preventing merge.

`.github/CODEOWNERS:25-92,95-143,176-201` assigns owner review to workflows, dependency configuration, auth, deployment, migrations, guard code and doctrine, with an explicit contributor co-review lane. That is a mature tier model. Its effectiveness still depends on branch protection, dismissal of stale approvals and administrator-bypass settings, none of which are proven by the file itself.

`.github/dependabot.yml` schedules updates across Python, npm and GitHub Actions and holds selected versions. W98 demonstrates the remaining semantic gap: a lockfile regeneration selected a version explicitly excluded in the manifest; scanners stayed green because no gate re-evaluated the lock against the manifest constraint.

Tailnet policy files exist under `infra/tailscale/`, but their contents were not inspected within the file budget. File existence is not evidence that future team onboarding is deny-by-default or that policy tests cover every role.

## 2. Scars & ledger evidence in this area

| Evidence | What actually happened | What it proves |
|---|---|---|
| Superscar family #4 | Five explicit “secret in clear” members: permissive credential files, sensitivity inherited by backups, a secret consumed as the first line of `bash -s`, repeated password material and a permissive launch configuration (`.claude/rules/cicatrix-superscar.md`) | Secret exposure is a recurring family, not a one-off typo. |
| Transcript exposure | An environment diagnostic printed inherited environment material into an agent transcript; another fleet diagnostic dumped far more environment than requested (`.claude/rules/cicatrix-scars.md:246-266,746-754`) | Read-only diagnostics can be exfiltration operations. Least-output probes matter as much as write controls. |
| Shell/stdin collision | A secret supplied on the same stdin consumed by `bash -s` became shell program text (`.claude/rules/cicatrix-scars.md:345-353`) | “Use stdin” is insufficient unless command input and secret input are separate channels. |
| W98 | Dependabot regenerated a lockfile with a version deliberately excluded as malicious; CI installed it, scanners remained green and production exposure lasted roughly two hours, although the optional payload was not installed (`.claude/rules/cicatrix-scars.md:692-714`) | Dependency intent must be revalidated after resolution; scanner plurality is not semantic verification. |
| W104 | A credentialed CLI returned exit code zero while stdout contained an authentication refusal (`.claude/rules/cicatrix-scars.md:799-814`) | Exit code is not a work probe. Authentication health must verify the requested operation and parse semantics. |
| Environment precedence | A session environment token could override a good stored credential; a shell default-expression diagnostic risked printing the selected token (`.claude/rules/cicatrix-scars.md:862-870`) | Credential source selection must be explicit, observable without values, and tested end-to-end. |
| Prompt in argv | A client-data loop exposed prompts through process arguments and was corrected to stdin (`.claude/rules/cicatrix-scars.md:1046`) | The currently inspected OAuth wrapper repeats a known failure class. |
| Public history | At least two explicit ledger rows record credential material entering public Git history; editing the current tree did not remove historical exposure (`.claude/skills/modus/PENDING-ARMS.md:61-62`) | Revocation is the first response. Squash, redaction or later history rewriting cannot make prior publication cease to have occurred. |
| Inert privacy metadata | The Visa Oracle question structure had 56 `sensitive:` declarations and zero code consumers (`.claude/skills/modus/PENDING-ARMS.md:31`) | Classification without an enforcing sink is security documentation, not a control. |
| Audit blind spot | A generic settings filename containing credential material evaded the filename-based permission audit (`.claude/skills/modus/PENDING-ARMS.md:41`) | Surface discovery needs a content-shape detector that reports only path/category—not matching content. |
| Dead OAuth lane | A revoked/closed OAuth seat remained represented while its cron lane was dead; labels did not prove identity (`.claude/skills/modus/PENDING-ARMS.md:159`) | Token lifecycle needs identity and entitlement attestation, not only possession. |
| Probe contamination | A probe inherited the normal shell environment and generated a real outbound false alert; the amendment prescribes a clean environment or blank alert credentials (`.claude/skills/modus/AMENDMENTS.md:12`) | Probes require hermetic side-effect and credential boundaries. |

Measured ledger state:

- `operator[secret]` appears 45 times in `PENDING-ARMS.md`.
- Row-state parsing finds 29 open and 11 closed rows; the other five appearances are contextual or taxonomy text rather than independently countable rotations.
- Superscar #4 contains five explicit secret-clear incidents.
- The accessible ledger records at least two explicit public-history credential incident classes.
- Only one narrow LLM credential declaration was found, so fleet-wide guard coverage cannot honestly be expressed as a percentage.

The unavailable memory cases—especially Chronicle screen recording and the behavior of GitHub’s secret-scanning API—remain unverified in this lane and are not included in the incident count.

## 3. World SOTA survey

| System or practice | Primary source | Mechanism | Measured effect | Transferability |
|---|---|---|---|---|
| OWASP LLM Top 10 | [OWASP 2025 Top 10](https://genai.owasp.org/llm-top-10/) | Separates prompt injection, sensitive disclosure, supply chain, improper output handling and excessive agency into explicit threat classes. | Ten-category coverage framework; no control-effect percentage published. | Use as the minimum threat-model checklist for every LLM launcher and MCP consumer. |
| OWASP Agentic Top 10 | [OWASP Agentic AI release](https://genai.owasp.org/2025/12/09/owasp-genai-security-project-releases-top-10-risks-and-mitigations-for-agentic-ai-security/) | Extends security to behavior hijacking, tool misuse, identity abuse and cascading autonomous failure. | Developed with input from over 100 practitioners and researchers; not an efficacy benchmark. | Directly maps to Nuzantara’s CLI fleet, tool-capable agents, persistent memory and automated operations. |
| CaMeL | [Defeating Prompt Injections by Design](https://arxiv.org/abs/2503.18813) | Separates trusted control instructions from untrusted data and uses capabilities/data-flow enforcement around a still-vulnerable LLM. | Reports completion of 67% of AgentDojo tasks while providing a provable security property for protected flows. | Strong foundation for Law 2 labels and MCP/web-output isolation; should protect sinks, not merely scan strings. |
| Google layered prompt-injection defense | [Google Security Blog](https://blog.google/security/mitigating-prompt-injection-attacks/) | Combines threat modeling, adversarial evaluation, red-teaming, model hardening and product-layer controls. | Google reports significant improvement in Gemini 2.5 defenses but does not publish one universal percentage. | Adopt layered fixtures and runtime policy; do not treat a prompt-injection classifier as a complete boundary. |
| Claude Code sandbox | [Anthropic sandbox documentation](https://code.claude.com/docs/en/sandboxing) | OS filesystem/network isolation with explicit deny rules and configurable `failIfUnavailable`. | Deterministic startup failure is available; default behavior otherwise warns and can run unsandboxed. | Set failure-on-unavailable for managed lanes and attest the effective sandbox in each launch receipt. |
| OpenAI Codex sandbox | [OpenAI sandbox engineering](https://openai.com/index/building-codex-windows-sandbox/) | OS-enforced write restriction and network suppression propagated to descendant processes. | Default workspace writes with network disabled; article explains why environment poisoning alone was rejected as bypassable. | Confirms that hook warnings and poisoned proxy variables are not substitutes for an OS boundary. |
| GitHub push protection | [GitHub push protection](https://docs.github.com/en/code-security/concepts/secret-security/push-protection) | Scans CLI, UI, uploads, REST and supported MCP interactions before accepting a push; records bypasses. | Blocks supported secret patterns before repository publication; legacy and generic patterns remain imperfect. | Make repository push protection mandatory, delegated-bypass only and pair it with provider-independent local patterns. |
| Vault leases | [HashiCorp Vault leases](https://developer.hashicorp.com/vault/docs/concepts/lease) | Dynamic secrets receive TTLs, renewals, audit metadata and immediate/prefix revocation. | Automatically invalidates leased credentials on expiry; no organization-wide incident-rate figure published. | The fleet can emulate lease semantics as metadata even when flat-subscription OAuth tokens cannot be dynamically minted. |
| SLSA Build | [SLSA v1.1 terminology](https://slsa.dev/spec/v1.1/terminology) | Trusted control-plane provenance from Build L2; stronger isolation and tamper resistance at higher levels. | Defines verifiable levels rather than a universal reduction percentage. | Generate and verify provenance for deployable artifacts; do not accept “SBOM exists” as source/build integrity. |
| Sigstore keyless signing | [Sigstore signing overview](https://docs.sigstore.dev/cosign/signing/overview/) | Ephemeral signing keys, short-lived OIDC certificates and Rekor transparency-log inclusion. | Removes long-lived signing-key management from the normal path and makes signing auditable. | Fits public-repo CI; artifact identity can bind workflow and commit without another static signing secret. |
| Tailscale ACLs/Grants | [Tailscale ACL documentation](https://tailscale.com/docs/features/access-control/acls) | Directional, locally enforced, deny-by-default policy once an ACL/Grants section is defined. | Deterministic policy enforcement; crucially, absence of a policy section leaves the product’s initial allow-all policy. | Team expansion must begin with tested empty-deny policy, then add minimum role grants. |
| NIST Privacy Framework | [NIST Privacy Framework](https://www.nist.gov/privacy-framework/privacy-framework) | Core activities, current/target profiles and implementation tiers for continuous privacy-risk governance. | A risk-management framework rather than a product benchmark. | Convert PDP plans into a current/target profile with evidence owner, test, expiry and residual-risk acceptance. |

### The five most consequential transfers

**Capability separation beats prompt wording.** CaMeL is the strongest architectural result because it assumes the model may remain vulnerable. Nuzantara’s opportunity is to attach trust and sensitivity labels to data at ingestion, preserve them through tool calls and prevent unauthorized sinks. This is materially stronger than regex-scanning an already assembled prompt.

**The sandbox must fail closed.** Both Anthropic and OpenAI distinguish OS enforcement from advisory policy. Nuzantara already has disciplined sandbox vocabulary, but needs a launch receipt proving effective filesystem roots, network policy and environment projection. A warning that isolation was unavailable is unacceptable for PII-bearing or credential-bearing lanes.

**Credential lifecycle is a graph, not a file.** Vault’s most transferable concept is not necessarily installing Vault; it is the lease contract connecting issuer, consumer, TTL, revocation and audit. Subscription OAuth credentials still need that metadata even when their providers cannot mint per-job dynamic secrets.

**Prevent publication; revoke before cleanup.** GitHub push protection is the correct outer barrier, but supported-pattern coverage is incomplete. Once material reaches public history, repository surgery is secondary to issuer revocation and consumer propagation.

**SBOM is not provenance or policy intent.** SLSA and Sigstore provide artifact origin and signing evidence; W98 shows Nuzantara additionally needs semantic validation that the resolved dependency set still satisfies security exclusions in the source manifest.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence and judgment |
|---|---|---|
| Law 2 output boundary | **AHEAD** | It covers outputs, memory, logs, alerts, notebooks and agents, distinguishes authorized processing from persistence and names one tightly bounded exception (`SYMBIOSIS.md:179-181,242-253`). Most surveyed guidance is less operationally explicit. |
| PDP governance | **BEHIND** | The compliance documents cover the right domains, but plans and headings are not per-control evidence. The PROD cross-border enforcement gap is openly recorded (`SYMBIOSIS.md:240`; `docs/PDP_COMPLIANCE_PLAN.md`). |
| Data sensitivity enforcement | **BEHIND** | Fifty-six `sensitive:` declarations had zero consumers (`PENDING-ARMS.md:31`). SOTA privacy engineering requires a label to alter behavior at every sink. |
| Secret file hygiene | **AT** in mechanism, **BEHIND** in closure | Backup-aware reachability analysis and `0600` remediation are strong, but filename discovery missed a real generic settings surface; 29 operator-secret rows remain open. |
| Credential identity and lifecycle | **BEHIND** | Token possession/fingerprint is not account identity, entitlement or revocation proof. The narrow declaration has one entry and does not define the fleet denominator. |
| LLM subprocess environment | **BEHIND** | Provider blocklisting leaves unrelated parent variables inherited, whereas SOTA uses a clean, explicit environment capability set (`claude_oauth_client.py:118-240`). |
| Prompt transport | **BEHIND** | The prompt is carried in argv despite a prior scar proving that process arguments expose client prompts (`claude_oauth_client.py:676-706`; `cicatrix-scars.md:1046`). |
| Agent sandboxing | **AT** in doctrine, **UNPROVEN/BEHIND** in attestation | Read-only/workspace-write and no-dangerous-bypass are correct, but the inspected repo evidence does not prove fail-if-unavailable or per-run OS sandbox receipts. |
| Prompt-injection defense | **BEHIND** | Repository hooks protect selected paths and warn on secret reads, but no inspected control provides CaMeL-style control/data separation and sink capabilities across MCP/web/LLM flows. |
| Public-repository prevention | **AT** in scanning, **BEHIND** in incident state | Detect Secrets is required according to workflow comments, yet at least two public-history incident classes reached the ledger. Push protection and revocation-first state are not proven from the snapshot. |
| Security CI truth | **AT** structurally, **BEHIND** mechanically | Ten security-shaped workflow files exist and `security.yml` declares four required contexts, but sovereignty is explicitly non-required and live branch protection was not verified. |
| RBAC/CODEOWNERS | **AHEAD** in repository design | Critical auth, deployment, workflow and guard surfaces have tiered ownership and a separate contributor lane. Effectiveness depends on external branch-protection settings. |
| Supply chain | **AT** in breadth, **BEHIND** in semantic integrity | CodeQL, Bandit, Detect Secrets, SBOM and dependency automation are broad; W98 proves they did not validate manifest intent against the lock. |
| Tailnet expansion | **BEHIND pending proof** | Policy files exist, but a deny-first role matrix and executable policy tests were not verified. Tailscale’s initial no-policy state can be allow-all. |
| Paid Anthropic API prohibition | **AHEAD** in doctrine, **BEHIND** in consistency | The CLI-only rule avoids duplicate paid exposure, but the sovereignty gate permits an OAuth SDK form forbidden by current doctrine. |

## 5. Beyond-SOTA recommendations

Scoring is `(impact 1–10 × confidence) / first-increment person-days`. Cost excludes paid APIs: all LLM work uses existing flat subscriptions or local execution.

### 1. Revocation-first exposure circuit breaker — score 4.28

- **What:** A repository-wide incident state machine: `suspected → publication-blocked → issuer-revocation-requested → propagation-proven → history-treated → closed`. It must store only provider category, fingerprint, path and timestamps—never secret material.
- **Why it beats SOTA:** GitHub prevents supported leaks and Vault revokes managed leases; neither composes public-history irreversibility, PII-safe evidence, multi-node propagation and autonomous-session suspension into one control.
- **Cost:** 2 person-days; approximately two Gear-3 review sessions on flat-subscription seats.
- **Gear:** 3.
- **Risk/scar:** False positives could halt work; a receipt could itself expose material. Superscar #2 “exists ≠ armed” and #4 “secret in clear.”
- **Metric:** Baseline at least two explicit public-history incident classes. Target zero accepted synthetic canary pushes, median detection-to-operator-revocation acknowledgement under 15 minutes, and 100% propagation probes before closure.
- **Measurement:** Nightly synthetic nonfunctional canaries plus immutable state-transition timestamps.
- **Kill criterion:** More than 2% false blocking over 30 days or any stored receipt containing matched material.
- **First PR:** `feat(security): add revocation-first exposure state machine`; proposed `scripts/secret_exposure_gate.py` and tests, plus `.github/workflows/security.yml`; ≤350 net lines.

### 2. Metadata-only credential surface graph — score 3.00

- **What:** Generate a graph from launchers and declarations: credential class → issuer → account/seat identity proof → source precedence → consumers → machines → last empirical probe → rotation state. The schema must reject token-shaped values.
- **Why it beats SOTA:** Vault maps leases to consumers, but this composes flat-subscription OAuth seats, multiple always-on machines, token identity ambiguity and scar-driven propagation evidence without centralizing secret bytes.
- **Cost:** 3 person-days; flat-subscription analysis only.
- **Gear:** 3.
- **Risk/scar:** Metadata may accidentally become identifying or operators may treat declarations as proof. Superscar #2 and #4.
- **Metric:** Baseline one narrow declared entry and 29 open operator-secret rows. Target 100% of credential-bearing launchers represented, 100% of nodes attached to a work probe and dead-slot detection within 15 minutes.
- **Measurement:** AST/config discovery compared with declarations; synthetic revoked-slot fixture.
- **Kill criterion:** The design requires copying a token, email or provider identity into an artifact, or coverage cannot exceed 90% after two iterations.
- **First PR:** `feat(security): declare credential surface graph schema`; extend `infra/llm-credentials/declared.json`, add proposed `scripts/credential_surface_audit.py` and tests; ≤380 lines.

### 3. Hermetic LLM process capsule — score 2.85

- **What:** Replace inherited-environment blocklists with an explicit environment allowlist; send prompts through a dedicated stdin/file descriptor; keep command-program stdin separate from credential input; attest sandbox mode and default-denied egress; emit only a non-secret launch receipt.
- **Why it beats SOTA:** OpenAI and Anthropic sandbox commands; Vault controls credentials. This capsule binds environment projection, prompt transport, token identity health, OS sandbox and output sensitivity into one reusable launcher contract across LLM families.
- **Cost:** 3 person-days plus one compatibility sweep.
- **Gear:** 3.
- **Risk/scar:** Removing implicit variables may break CLI authentication or locale/tool discovery. Superscar #4 and the W104 false-success class.
- **Metric:** Baseline is an unbounded inherited environment and one inspected argv prompt path. Target zero undeclared child variables, zero prompt bytes in argv, 100% sandbox receipts and no credential material in 10,000 synthetic diagnostic lines.
- **Measurement:** Spawn a test child that reports variable names and argv lengths only; inspect process metadata with synthetic prompts.
- **Kill criterion:** More than 5% legitimate launcher failures after a seven-day shadow run, or any fallback launches without the capsule.
- **First PR:** `fix(llm): seal OAuth subprocess boundary`; `apps/backend-rag/backend/llm/claude_oauth_client.py` plus a proposed adjacent test module; ≤300 lines.

### 4. Law 2 capability-and-taint plane — score 2.00

- **What:** Assign source labels such as `trusted-control`, `untrusted-content`, `pii`, `osint`, `secret`, and `public`; carry them through MCP/tool results; require sink capabilities before prompt assembly, logging, memory, alerting or publication.
- **Why it beats SOTA:** CaMeL protects data flows but does not encode Nuzantara’s UU PDP output boundary, S7 exception, local-sovereignty routing and scar corpus. This composition does.
- **Cost:** 4 person-days for the first vertical slice; 10–15 days for broad adoption.
- **Gear:** 3.
- **Risk/scar:** Over-redaction could destroy operational utility; missing adapters could produce a false sense of coverage. Superscar #2 and #4.
- **Metric:** Baseline 56 sensitivity declarations with zero consumers. First target: 100% of those declarations consumed, zero cleartext leaks across 10,000 synthetic PII/prompt-injection cases, false-block rate below 2%.
- **Measurement:** Property-based sink tests with synthetic identity data and malicious retrieved instructions.
- **Kill criterion:** After two iterations, false blocks remain above 5% or any unlabeled path can reach a protected sink.
- **First PR:** `feat(privacy): enforce sensitivity labels at one output sink`; proposed `infra/claude-hooks/law2_sink_guard.py`, registry and tests; ≤400 lines.

### 5. Security-gate truth compiler — score 1.90

- **What:** One machine-readable contract maps each security promise to workflow, exact required context, negative fixture, CODEOWNER and liveness probe. CI fails if a risk-critical workflow is advisory, renamed or absent from required checks.
- **Why it beats SOTA:** Branch protection and CODEOWNERS are standard; compiling the scar corpus and PENDING-ARMS receptors into continuously verified gate topology is organism-specific.
- **Cost:** 4 person-days.
- **Gear:** 3.
- **Risk/scar:** Check renames can deadlock merges; external status APIs can lie or lag. Superscar #2 and W104.
- **Metric:** Baseline ten security-shaped workflows, four of 25 contexts declared required, one inspected sovereignty gate explicitly non-required. Target 100% risk-critical controls required and 100% negative fixtures rejected.
- **Measurement:** Daily comparison of contract, workflow YAML and live branch rules; deliberate harmless failure fixture.
- **Kill criterion:** Two false merge freezes in 30 days caused by contract drift, without automatic diagnosis.
- **First PR:** `feat(ci): compile security gate contract`; `.github/workflows/security.yml`, `.github/workflows/catE-sovereignty-lint.yml`, proposed contract/auditor and tests; ≤390 lines.

### 6. Dependency-intent and artifact-provenance gate — score 1.44

- **What:** Re-evaluate every lockfile selection against source-manifest constraints, preserve security exclusions through automation, generate SBOM/provenance and verify a Sigstore identity-bound attestation before release.
- **Why it beats SOTA:** SLSA proves how an artifact was built; this adds scar-derived semantic proof that the resolver did not negate explicit anti-malware intent.
- **Cost:** 5 person-days.
- **Gear:** 3.
- **Risk/scar:** Resolver differences and optional dependency markers can produce false failures. W98 and Superscar #2.
- **Metric:** Baseline one W98 production incident. Target 100% lock entries satisfy source constraints, 100% release artifacts carry verified provenance and zero unresolved security exclusions.
- **Measurement:** Preserve W98 as a regression fixture; verify attestations against repository/workflow identity.
- **Kill criterion:** More than 1% false dependency failures over four update cycles or provenance is generated but not verified at consumption.
- **First PR:** `fix(deps): enforce manifest constraints after lock resolution`; `.github/dependabot.yml`, `.github/workflows/security.yml`, proposed verifier and W98 fixture; ≤350 lines.

### 7. Mandate-bound tailnet grants — score 1.23

- **What:** Compile owner-approved human roles and agent mandates into minimum Tailscale Grants, short-lived device tags and executable deny tests. Each agent launch receipt identifies the allowed service set; no role receives ambient machine-wide access.
- **Why it beats SOTA:** Tailscale provides deny-by-default policy; this binds it to agent sandbox capabilities, temporal mandates and owner rulings.
- **Cost:** 4 person-days after role approval.
- **Gear:** 3.
- **Risk/scar:** Lockout or accidental additive privilege from overlapping grants. Superscar #2.
- **Metric:** Target zero connectivity for an unknown device, 100% policy tests for approved source/destination pairs and automatic expiry for all temporary grants.
- **Measurement:** Offline policy tests followed by synthetic device-role probes.
- **Kill criterion:** Any broad wildcard is required for normal operations or two unplanned lockouts occur during staged rollout.
- **First PR:** `test(tailnet): codify deny-first role matrix`; `infra/tailscale/policy.hujson` and a proposed policy-test fixture; ≤250 lines. Activation waits for ruling.

## 6. 90-day roadmap + first PRs

### Wave 1 — Days 0–30: stop recurrent exposure classes

1. Arm the revocation-first circuit breaker.
2. Seal `claude_oauth_client.py`: allowlisted environment and stdin-only prompts.
3. Create the metadata-only credential graph and import every known launcher as metadata.
4. Reconcile CLI-only doctrine with the sovereignty gate.
5. Enable shadow metrics before changing live credential routing.

| First PR | Files | Limit | Gear | Acceptance test |
|---|---|---:|---:|---|
| `feat(security): add revocation-first exposure state machine` | `.github/workflows/security.yml`; proposed `scripts/secret_exposure_gate.py` and test | ≤350 | 3 | A synthetic canary push is blocked; receipt contains fingerprint/category only. |
| `fix(llm): seal OAuth subprocess boundary` | `apps/backend-rag/backend/llm/claude_oauth_client.py`; proposed adjacent tests | ≤300 | 3 | Child sees only allowlisted variable names; prompt absent from argv; auth work probe succeeds. |
| `feat(security): declare credential surface graph schema` | `infra/llm-credentials/declared.json`; proposed auditor/test | ≤380 | 3 | Unknown credential-bearing launcher fails; token-shaped schema values are rejected. |
| `fix(ci): enforce CLI-only sovereignty doctrine` | `.github/workflows/catE-sovereignty-lint.yml` and baseline | ≤200 | 2 | OAuth SDK constructor fixture fails; sanctioned CLI subprocess fixture passes. |

Wave-1 exit: zero synthetic publication escapes, all inspected LLM launchers have bounded environments, and graph coverage has a real denominator.

### Wave 2 — Days 31–60: turn declarations into enforcing boundaries

1. Implement the first Law 2 taint vertical slice from structured intake to one log/memory/output sink.
2. Compile security workflows, required contexts, CODEOWNERS and negative fixtures into a gate contract.
3. Make prompt-injection fixtures cross trust boundaries rather than merely matching phrases.
4. Extend permission auditing with content-shape classification that never emits matching content.

| First PR | Files | Limit | Gear | Acceptance test |
|---|---|---:|---:|---|
| `feat(privacy): enforce sensitivity labels at one output sink` | proposed `infra/claude-hooks/law2_sink_guard.py`, registry and tests | ≤400 | 3 | Synthetic PII and retrieved injection cannot reach log/memory output; public synthetic data still flows. |
| `feat(ci): compile security gate contract` | `.github/workflows/security.yml`; `.github/workflows/catE-sovereignty-lint.yml`; proposed contract/auditor | ≤390 | 3 | Removing or making a critical check advisory causes the contract test to fail. |
| `fix(security): detect credential-shaped generic files safely` | `scripts/secrets_permissions_audit.py` and tests | ≤300 | 2 | A synthetic generic settings file is classified without reading content into output; safe file remains clean. |

Wave-2 exit: every protected sensitivity declaration in the selected slice has a consumer; every critical security promise has a required negative test.

### Wave 3 — Days 61–90: provenance, privacy posture and least privilege

1. Preserve W98 as a permanent resolver-intent regression.
2. Generate and verify artifact provenance, not merely SBOM presence.
3. Convert PDP documents into NIST-style current/target profiles with evidence expiry.
4. Stage tailnet deny-first tests before onboarding any additional human or device.
5. Run a Gear-3 adversarial exercise: injected web content attempts to read a synthetic secret, call a tool and persist to memory.

| First PR | Files | Limit | Gear | Acceptance test |
|---|---|---:|---:|---|
| `fix(deps): enforce manifest constraints after lock resolution` | `.github/dependabot.yml`; `.github/workflows/security.yml`; proposed verifier/W98 fixture | ≤350 | 3 | A lock selecting an explicitly excluded version fails before install. |
| `feat(supply-chain): verify release provenance` | `.github/workflows/sbom.yml` plus proposed verification policy | ≤400 | 3 | Artifact from an unapproved workflow identity is rejected. |
| `docs(privacy): add evidence-backed PDP current-target profile` | `docs/PDP_COMPLIANCE_PLAN.md`; `docs/UU_PDP_COMPLIANCE_REPORT.md` | ≤350 | 2 | Every “implemented” control has owner, evidence path, last test and expiry; unsupported claims remain planned. |
| `test(tailnet): codify deny-first role matrix` | `infra/tailscale/policy.hujson`; proposed tests | ≤250 | 3 | Unknown user/device has zero access; each allowed pair is individually asserted. |

Ninety-day success means: zero unbounded LLM subprocess environments, zero prompt argv paths, all credential consumers declared, all critical security gates mechanically required, 100% W98-style constraint coverage and zero cleartext leakage in the synthetic Law 2 corpus.

## 7. Needs-ruling

1. **Credential rotation and retirement:** issuer-side revocation, replacement and tolerated downtime for the 29 open `operator[secret]` rows require operator authority. The organism may identify and stage them but must not choose business disruption autonomously.
2. **GitHub organization settings:** enabling push protection, delegated bypass, required status contexts, stale-review dismissal and administrator-bypass policy requires owner/admin action outside the repository.
3. **Tailnet team expansion:** Zero must approve the human role matrix, device eligibility, emergency access and initial deny-first activation before any additional person or device is admitted.
4. **UU PDP legal posture:** lawful-basis selection, cross-border transfer basis, DPO appointment, DPIA residual-risk acceptance, retention periods and incident notifications require business/legal rulings.
5. **Screen recording:** Zero must decide whether any screen-recording product is permissible in operational sessions and define retention/deletion rules. The named Chronicle discovery was unavailable here, so this is a policy question—not a finding that recording is currently active.
6. **S7 boundary changes:** any expansion beyond the single documented internal exception requires an explicit ruling and a revised legal/security basis.
7. **Credentials without usable revocation:** if a provider truly offers no revocation path, the operator must decide between retiring the integration, isolating it behind a compensating boundary or accepting documented residual risk.

The paid Anthropic API path is not a needs-ruling item: current doctrine already resolves it as prohibited. The CI inconsistency should be corrected.

## 8. §Meta-pattern

The single defective belief is:

> **A control exists when it has been named, documented, scanned or made visible.**

That belief explains almost every finding:

- A `sensitive:` field was considered privacy engineering despite having no consumer.
- A credential was considered inventoried despite only one narrow declaration and no fleet denominator.
- A warning hook was treated as a boundary even though secret reads and parse failures continued.
- A sovereignty workflow existed but was explicitly non-required.
- Multiple scanners were green while W98 violated an intentional anti-malware constraint.
- An exit-zero probe was treated as authentication success in W104.
- A token label was treated as seat identity despite dead entitlement.
- A sanitized current tree was treated as if it could undo public history.
- A PDP plan risks being read as deployed compliance without evidence owner, test and expiry.

The corrective belief is:

> **A security control exists only when an adversarial input reaches it, the forbidden transition is mechanically denied, the denial is observable without exposing the protected material, and a second independent mechanism proves the control remains armed.**

For Nuzantara, the beyond-SOTA move is to turn scars into executable negative capabilities: each recurrence becomes a forbidden transition, each transition has a test and required gate, and each gate emits a non-secret liveness receipt. That composition exploits the organism’s unique scar corpus, always-on machines, full-lifecycle sessions and cross-family review fleet.

## 9. Sources

1. [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/llm-top-10/) — 2025; accessed 2026-08-29. Primary community threat taxonomy covering prompt injection, sensitive disclosure, supply chain and excessive agency.
2. [OWASP Top 10 for Agentic Applications release](https://genai.owasp.org/2025/12/09/owasp-genai-security-project-releases-top-10-risks-and-mitigations-for-agentic-ai-security/) — 2025-12-09; accessed 2026-08-29. Primary OWASP release describing the expert-reviewed agentic threat model.
3. [Debenedetti et al., “Defeating Prompt Injections by Design”](https://arxiv.org/abs/2503.18813) — submitted 2025-03-24, revised 2025-06-24; accessed 2026-08-29. Primary CaMeL paper on capability-based control/data separation.
4. [Google, “Mitigating prompt injection attacks with a layered defense strategy”](https://blog.google/security/mitigating-prompt-injection-attacks/) — 2025-06-13; accessed 2026-08-29. Primary engineering account of Gemini’s layered prompt-injection defenses.
5. [Anthropic Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing) — continuously updated; accessed 2026-08-29. Official behavior and fail-if-unavailable documentation.
6. [OpenAI, “Building a safe, effective sandbox to enable Codex on Windows”](https://openai.com/index/building-codex-windows-sandbox/) — 2026-05-13; accessed 2026-08-29. Primary engineering explanation of OS-enforced agent isolation and network suppression.
7. [GitHub push protection](https://docs.github.com/en/code-security/concepts/secret-security/push-protection) — continuously updated; accessed 2026-08-29. Official prevention, bypass and supported-surface semantics.
8. [HashiCorp Vault leases, renewal and revocation](https://developer.hashicorp.com/vault/docs/concepts/lease) — continuously updated; accessed 2026-08-29. Official dynamic-secret lifecycle and revocation contract.
9. [SLSA v1.1 terminology and verification model](https://slsa.dev/spec/v1.1/terminology) — specification v1.1; accessed 2026-08-29. Primary supply-chain provenance and build-isolation model.
10. [Sigstore keyless signing overview](https://docs.sigstore.dev/cosign/signing/overview/) — continuously updated; accessed 2026-08-29. Official description of ephemeral keys, OIDC identity and Rekor transparency.
11. [Tailscale ACL documentation](https://tailscale.com/docs/features/access-control/acls) — last validated 2026-01-05; accessed 2026-08-29. Official deny-by-default, directional and locally enforced policy semantics, including the initial allow-all caveat.
12. [NIST Privacy Framework](https://www.nist.gov/privacy-framework/privacy-framework) — version 1.0 published 2020-01-16; accessed 2026-08-29. Authoritative risk-management framework for privacy controls, profiles and implementation maturity.