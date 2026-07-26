---
date: 2026-07-19
domain: operations
client_case: none
adversarial_review: kimi-k3
sources:
  - 10-lane Workflow sweep wf_422d6a24-c22 (3 ground on-disk + 7 web lanes, 216 tool calls, every claim carries URL or file:line; journal in session transcript dir)
  - https://code.claude.com/docs/en/routines · /workflows · /agent-teams · /chrome (official, fetched live)
  - https://ollama.com/library/{qwen3.6,qwen3-vl,glm-ocr,qwen3-embedding} (fetched live)
  - https://www.kimi.com/agent-swarm · https://github.com/MoonshotAI/kimi-agent-sdk · kimi-cli skills docs
  - live `gh api repos/*` maintenance checks on every reuse candidate (2026-07-19)
  - prior captures re-verified still-current: 2026-07-06-codex-gpt56-deep-research.md · 2026-07-06-glm52-zai-deep-research.md · 2026-06-27-local-ocr-model-bakeoff-indonesian-id-docs.md
---

# Arsenal capability map 2026-07-19 — what every stack can do TODAY, magic combos, reuse-first

> Mandate (Zero): "deep research su tutti gli llm che usiamo e le loro potenzialità ad oggi…
> più tutti i tools, app che il nostro arsenale raggiunge tramite cli, browser, mcp… o
> singolarmente o in magic combo. ricorda che online puoi trovare pezzi da prendere /reuse-first".
> Method: 10 parallel lanes (3 ground: CLI probe M5 / MCP inventory / repo assets · 7 web:
> Claude, Codex, Google, Kimi, GLM+Ollama, browser+connectors, reuse-first). All flat-sub;
> no paid API proposed anywhere; PII/Legge-5 boundaries restated inline where an item grazes them.

## 0. TL;DR — the 6 findings that matter most

1. **Same-day cascade debt (bounded fix, do first):** three cascade-definition scripts still
   carry the DeepSeek seat retired by owner decision 2026-07-19 (source:
   `research/operations/2026-07-19-kimi-arsenal-integration-deepseek-retirement.md` + memory
   `decision_kimi_enters_arsenal_deepseek_retired_2026_07_19` — the scripts themselves still
   describe it as allowed, which IS the drift): `scripts/arsenal_probe.py` ALL_SEATS `:82` +
   REQUIRED_SEATS['pro'] (kimi is ALREADY wired into REQUIRED_SEATS for all 3 machines — the
   twin's #2791 leg landed — the deepseek residue is what remains), `scripts/
   codex_tri_llm_review.py:479-564` (a live leg aimed at the dead api.deepseek.com; note the
   gate itself is W64-aware — errors are logged and `MIN_LIVE_REVIEWERS=2` quorum decides over
   live seats only, so the panel is *effectively 2-way by design, not silently broken*: the
   real gap is that "tri"-review has been nominal since the seat died), and `scripts/
   cost_breaker.py:74,81,91,100,118` (cascade table + a $5.00 budget line for a seat we must
   never top up). And **Kimi has zero `scripts/` wrapper** (this probe, file-count in
   `scripts/`: 25 files shell out to claude, 2 to agy, 0 to kimi) — a thin
   `scripts/kimi_client.py` unlocks Kimi for every existing cascade.
2. **`claude ultrareview` exists and is unused** (CLI v2.1.215, cloud multi-agent PR review,
   MAX-quota) — a free automated first-pass before the manual panel on every substantive PR.
3. **Claude Code Routines** (cloud-hosted scheduled sessions, MAX-quota, official docs) are a
   *structural cure* for our three dominant scar families (#1 HOME-fork, #2 esiste≠armato on
   launchd, #7 KeepAlive/TCC): no plist, no local checkout, fresh clone of origin/main every
   run. Pilot with one PII-free cron. Gate: enabling "Claude Code on the web" is operator[gui].
4. **Cross-family vision witness is one flag away:** `codex exec -i <png>` (unused, grep=0)
   gives an OpenAI-family look at the SAME rendered slide the Claude pipeline produced — the
   cheapest real answer to `discovery_wr2_factcheck_degraded_no_independent_witness` (and
   GLM-vision already plays this seat in KBLI Lot-2/3 — precedent exists in production).
5. **K3 Swarm + Meta's July-2026 Insights fields** are the two levers that revive the falsified
   WR2 engagement→selector prior (n=45→n≥200): Swarm for the wide public-data sweep,
   the new Insights fields (Reels Skip Rate, cross-placement aggregates) for richer per-post signal.
6. **Negative findings that save future wasted builds:** claude.ai connectors = 0/5 live when
   called from a CLI subagent (schema-visible ≠ live-usable); claude-in-chrome is absent from
   this env (docs describing it as default browser MCP are stale for M5 — the working path is
   `nuzantara-browser`/Playwright); IG browser automation = never (hours-to-ban in 2026; the
   sanctioned path is `wr2_publish.py:453` Graph API); OSS-RBA/AHU = CAPTCHA + anti-scraping
   ToS → human-in-the-loop only.

## 1. Per-stack capability highlights (new/unused headroom only — full inventory in workflow journal)

### Claude MAX (CLI v2.1.215)
- `claude ultrareview <PR#|branch>` — cloud multi-agent review, unused (see TL;DR 2).
- `claude -p --json-schema '<schema>'` — native schema-validated print output; removes the
  hand-rolled JSON-repair layer in structured-I/O crons (wr2-brief-interpreter family).
- `claude -p --fallback-model sonnet,haiku` — first-class same-provider fallback; replaces the
  fragile stdout-grep tier logic in `regulatory-watcher-run.sh` for the Claude leg.
- `claude -p --max-budget-usd` · `claude setup-token` (long-lived automation auth,
  subscription-backed) · `claude agents --json` (orchestration liveness probe) ·
  `claude plugin eval` (scored skill regression harness — our skill drift is currently caught
  by hand-made `.bak-drift-*` copies).
- **Routines** (cloud cron, API `/fire` trigger → alert-triage front door for Sentry/Fly
  alerts) · **Agent Teams** (flag already armed fleet-wide since the 2026-05-13 pilot, never
  absorbed into modus doctrine — fits the WR2 adversarial critic pair shape) · native
  `/deep-research` workflow bundled free (triage pass before the expensive tri-LLM panel).
- Trail of Bits security plugins (differential-review, static-analysis, second-opinion):
  **enabled in settings.json but zero invocations found** — armed-but-dormant for auth/backend PRs.

### Codex / ChatGPT Pro (v0.144.4, GPT-5.6 GA since Jul 9)
- `codex exec --search` — native live web search, flat-sub: a genuinely independent 4th search
  witness for deep-research/regulatory (non-Anthropic, non-Google index).
- `codex exec -i <img>` — multi-image input, unused (TL;DR 4).
- `codex doctor --json` — auth-aware health probe; replaces `codex --version` greps in cascade
  wrappers (kills the green-but-401 failure that already bit Tier-3 once).
- `codex review --uncommitted|--base main` — re-probe on 0.144.4 (was broken at v0.133); if
  fixed, cleaner pre-push local gate than the [SPALLA]-prompt workaround.
- `codex cloud exec --attempts 2-4` — server-side best-of-N for the hardest single-shot
  problems (still zero adoption, second consecutive audit).
- `codex sandbox <cmd>` — standalone seatbelt runner for untrusted one-off scripts (OSINT/
  competitor-monitor scraped code) without a full agent turn.
- `mcp__codex-redteam__codex` MCP server is live in-session — red-team as a first-class tool
  call instead of subprocess+stdout-scrape.
- Sora: **discontinued Apr 26 2026** — drop from any perks list. "250 Deep Research runs/mo"
  and "1M ctx" Pro figures: secondary sources, UNVERIFIED.

### Google AI Ultra (agy + Flow + NotebookLM)
- **Veo 3.1 Lite [Lower Priority] = zero Flow credits** — motion cover/Reel variants for WR2 at
  no budget cost; **Nano Banana Pro "ingredients" chaining** (hero still → consistent video) vs
  our FlowKit bridge which still treats image/video as two unrelated calls
  (`docs/wr2/flowkit-integration.md:20,84-85`).
- **NotebookLM June-8 agentic upgrade** (per-notebook code execution + fresh web sourcing) —
  route regulatory Tier-2 grounding through NB-Regulation WITH fresh sourcing in the same query
  → direct W90 mitigation ("il ground-truth invecchia"). NotebookLM **Enterprise REST API**
  exists (official) — candidate to de-risk the unofficial browser-automation notebooklm-mcp
  for create/add-source/audio verbs (parity check needed; chat surface unconfirmed).
- **Antigravity Scheduled Tasks** — Google-hosted cron with persistent task context: another
  plist-free cron surface for PII-free jobs. Antigravity subagents have **no default recursion
  depth cap** — always set one or they eat the Ultra credit pool.
- `agy models` lists **Claude Sonnet/Opus 4.6 (Thinking)** under Ultra quota — UNVERIFIED
  billing path (could breach the Anthropic-paid-endpoint ban); needs 1-shot probe + owner
  check before ever treating it as MAX-overflow. 1M-ctx marketing caveat: MRCR v2 collapses to
  ~26% near 1M on both Gemini 3.1 Pro and 3.5 Flash — chunking/RAG stays necessary.

### Kimi (Moonshot flat sub)
- **K3 Swarm** (≤300 subagents, hosted) — shape-match for the IG metrics/competitor wide sweep
  and multi-source regulatory scans (public data only). **kimi-agent-sdk (Python)** makes a
  swarm cron-schedulable headlessly — today Swarm is Desktop/operator-only.
- **K2.6-Agent / Kimi Slides** — internal-only decks (WR2 status, client-quote summaries):
  formatting offload with zero Legge-5 exposure.
- kimi-cli **auto-discovers `.claude/skills/` at the git root** (official docs) — our wr2/
  kbli-navigator/modus corners are ALREADY visible to Kimi sessions; the missing piece is one
  line in `~/.kimi-code/AGENTS.md` telling it to load them.
- CLI default is k3 at effort=max for everything — route the refuter-cascade middle tier to
  `kimi-for-coding-highspeed` for cheaper/faster review calls.
- `kimi server run` / `kimi web` (loopback REST) and `kimi acp` (editor protocol) exist;
  loopback-only, never `--dangerous-bypass-auth`. Desktop MCP scope-down remains
  operator[consent] — until then Desktop stays supervised.
- Caveats: BrowseComp 91.2 is the 300K-compaction figure (90.4 at full 1M); K2.7-Code vendor
  benchmarks disputed by practitioners (VentureBeat) — treat as vendor-reported.

### GLM z.ai + Ollama local
- GLM Coding Plan bundles a **Web Search/Web Reader MCP tool** (free allocation by tier) —
  an unused, differently-biased second search lane for regulatory delta-hunting.
- **Off-peak scheduling** (22:00-06:00 WITA, promo through Sep 2026) for GLM batch calls —
  proposed 07-06, still unarmed. GLM-vision is already our production cross-family
  image-grounded verifier in KBLI Lot-2/3 (not hypothetical).
- Ollama upgrade candidates (all Apache/MIT, all local, bake-off-gated):
  - `qwen3.6:35b` MoE (~3B active) — beats deepseek-r1-0528 on 6/7 benchmarks (third-party);
    reasoner-tier replacement on Pro 48GB; verify headroom before pinning on M5 24GB.
  - `glm-ocr` (2.2GB, #1 OmniDocBench 94.62, ~6-7× faster) + `qwen3-vl:8b` — the OCR bake-off
    scoped 2026-06-27 is still unexecuted; frozen `qwen2.5vl:7b` stays default until a 50-doc
    Indonesian-ID gold set says otherwise (CLAUDE.md §9 invariant).
  - `qwen3-reranker` / `bge-reranker-v2-m3` — reranking stage on top of bge-m3 for KBLI/visa
    RAG (check `backend/services/rag/` first: existence of a reranker stage UNVERIFIED).
  - `qwen3-embedding:8b` (#1 MTEB multilingual) — OSINT-Neo4j semantics + WA-corpus catalog
    ONLY; production RAG index stays frozen on text-embedding-3-small (93,283 vectors).

### MCP / browser reality check (ground truth, tested live)
- **11 servers** in `.mcp.json` (re-counted this session; note the file is UNTRACKED,
  per-machine state — worktrees don't inherit it): codex-redteam, ga4-analytics, github,
  notebooklm-mcp, nuzantara-browser, nuzantara-fetch, nuzantara-mcp, nuzantara-mcp-advanced,
  ocr-tesseract, playwright, postgres-nuzantara. Only ~3 are referenced by any agent def.
  Orphans worth wiring or pruning: **ga4-analytics** (zero agent-def refs — the missing
  conversion signal for the WR2 selector prior), **postgres-nuzantara** (absent even from
  mcp-health's checklist), **ocr-tesseract** (unwired or dead weight), **nuzantara-fetch**
  (redundant vs WebFetch — prune candidate).
- claude.ai marketplace connectors (Canva/Drive/Calendar/Vercel/Exa): **0/5 callable from a
  CLI subagent** despite rich schemas. Re-test interactively once; never rely on them in cron.
- `mcp__exa__web_search_advanced_exa` is live and **paid** ($0.007/q) — it comes from the
  USER-SCOPE MCP config (`~/.claude.json` mcpServers: exa, gdrive), a different surface from
  the dead claude.ai Exa connector above (that's the reconciliation). Surfaced for Zero's
  sanction — not adopted into any cron by this session.
- Own Drive OAuth (`nuzantara-mcp` drive.py) > claude.ai Drive connector (failed live 2×).

## 2. Magic combos (cross-stack, each tied to a live lane)

| # | Combo | Stacks | Lane it feeds |
|---|---|---|---|
| A | **Regulatory Radar 2.0**: changedetection.io diff-trigger on JDIH/BKPM/OSS pages → fire LLM verify only on real diffs → NotebookLM agentic (NB-Regulation + fresh sourcing, W90-proof) → `codex exec --search` + GLM Web Reader as two independent witnesses | reuse + Google + Codex + GLM | regulatory-watcher (cuts daily cascade spend, closes gazette latency) |
| B | **WR2 Motion Loop**: Nano Banana ingredients (hero still → consistent video) → Veo 3.1 Lite zero-credit Reel variant → publish via existing Graph API path (owner-gated) → July-2026 Insights fields (Skip Rate etc.) → K3 Swarm competitor sweep → selector prior revived at n≥200 | Google + Kimi + Meta API | WR2 growth loop (attacks the falsified prior with new signal AND new sample) |
| C | **Render-QA Independent Witness**: `codex exec -i slide.png` (OpenAI eyes) + GLM-vision seat (proven in KBLI) on the SAME artifact vs brief.json | Codex + GLM | WR2 fact_check degraded — cross-family witness without new infra |
| D | **Cascade 3.0**: `--fallback-model` for the Claude leg + `codex doctor --json` health + `scripts/kimi_client.py` new wrapper + GLM off-peak windows → every 2-tier wrapper becomes a true 4-tier cascade | Claude + Codex + Kimi + GLM | all cron wrappers (kills the 2-deep silent degradation found in the 05-24 audit) |
| E | **Sovereign OSINT bench**: official neo4j/mcp (read-only Cypher on localhost) + flowsint UI (local Docker, 7.4k★) + `qwen3-embedding` local semantics; K3 Swarm public-web-only pre-triage AFTER the Desktop consent gate | reuse + Ollama + Kimi | OSINT-Nexus (answers the "cutover UI TODO" without building bespoke) |
| F | **PR gate stack**: `claude ultrareview` first pass → R1 GLM first-call (compact) → codex-redteam MCP native call for deep diffs → Trail of Bits differential-review on auth/backend | Claude + GLM + Codex | ship-lifecycle on every substantive PR, all flat-sub |

## 3. Reuse-first shortlist (all checked live via `gh api` on 2026-07-19)

| Piece | What | Lane | Status |
|---|---|---|---|
| [changedetection.io](https://github.com/dgtlmoon/changedetection.io) (Apache-2.0, 32.4k★, pushed today) | self-hosted page-diff watcher + alerts | regulatory diff-trigger (combo A) | adopt-ready |
| [qdrant/mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant) (official, Apache-2.0) | semantic search/inspect on our vector store from sessions | KBLI/visa RAG debugging | adopt-ready |
| [neo4j/mcp](https://github.com/neo4j/mcp) (official, pushed today) | read-only Cypher/schema MCP on localhost Neo4j | OSINT graph exploration | adopt-ready (local-only) |
| [flowsint](https://github.com/reconurge/flowsint) (Apache-2.0, 7.4k★) | local-first OSINT investigation UI (Neo4j+FastAPI) | OSINT-Nexus cutover UI | owner review (OSINT sensitivity) |
| [indonesia-gov-apis](https://github.com/suryast/indonesia-gov-apis) (MIT, pushed today) | 50+ ID gov API/data-source map + gotchas | before ANY new gov-data build | consult-first reference |
| [instagram_monitor](https://github.com/misiektoja/instagram_monitor) (GPL-3.0, 1.1k★) | public-account IG tracker (posts/followers/shadowban) + webhooks | IG metrics + competitor-monitor | evaluate vs our scraper |
| [vercel/satori](https://github.com/vercel/satori) (13.7k★) | HTML/CSS→SVG without browser | WR2 render latency | future option only (CSS-subset port cost) |
| pasal-id-mcp / ilhamfp/pasal (AGPL-3.0) | 100k+ ID regulations MCP/API | secondary regulation cross-check | UNVERIFIED accuracy + AGPL legal review first |
| IG/Meta Graph MCP servers (3 surveyed) | Graph API via MCP | — | ALL fail the trust bar (≤25★, stale, token-holding) — do not wire |

## 4. Do-not-do list (negative knowledge, each saves a wasted build)

- **Never browser-automate instagram.com** — hours-to-ban in 2026; the sanctioned path is the
  admin-gated Graph API publisher (`wr2_publish.py:453`), and publishing stays Zero-only anyway.
- **Never scrape OSS-RBA/AHU** — CAPTCHA + explicit anti-scraping ToS; human-in-the-loop GUI only.
- **Don't rely on claude.ai connectors in automation** — 0/5 live from subagents (tested).
- **Don't use agy's Claude models** until the billing path is verified (Anthropic-paid ban).
- **Don't touch frozen invariants** on the back of this report: qwen2.5vl OCR default and
  text-embedding-3-small production index change only via their own gated bake-offs.
- **Don't cron the paid Exa tool** without Zero's explicit sanction.

## 5. Operator-gated items (surfaced, not armed — Legge 5 / consent / GUI)

1. Enable "Claude Code on the web" at claude.ai → unlocks the Routines pilot (operator[gui]).
2. Kimi Desktop MCP scope-down to aggregate/health/intel/KBLI-only (operator[consent], already
   ledgered — blocks unsupervised Desktop/Swarm use until done).
3. Exa advanced search ($0.007/q, already installed): sanction or leave manual (operator[cost]).
4. Gemini-in-Gmail AI-Inbox pilot — **operator[PII/Law-2]**, not a mere business call: it runs
   a cloud LLM over client correspondence. Only viable shapes: PII-free mailboxes, or with a
   redaction layer in front; the "already Workspace-resident" argument softens transit, not the
   output-boundary rule. Default stance: skip unless Zero explicitly rules the Law-2 reading.
5. Flow/Veo Reel variants: generation is autonomous-safe, any publish remains Zero's act.

## 6. Recommended sequencing (when Zero picks up items)

1. **Cascade-debt fix** (TL;DR 1) — bounded, same-day-rot, restores 3/3 panel review.
2. **Combo F PR-gate** (`ultrareview` + GLM-R1) — pure doctrine, zero infra.
3. **Combo A regulatory radar** — biggest recurring-spend cut; changedetection.io is adopt-ready.
4. **Combo C render witness** — one flag (`-i`) + one precedent (GLM-vision) = closes an open wound.
5. **Combo D cascade 3.0** — kimi_client.py + doctor-json + fallback-model sweep over wrappers.
6. **Routines pilot** (after operator[gui]) — one PII-free cron, then judge.
7. **Combo B/E** — bigger builds, gated on Meta fields verification and the Kimi consent gate.

## Adversarial review

Cascade honestly declared: **GLM 5.2 first-call** probed alive (PONG) but dropped the
multi-file agentic review with ECONNRESET → escalated per doctrine to **Kimi K3**
(`kimi -m kimi-code/k3 -p`, agentic read-only run on this file + the three cascade scripts +
`.mcp.json`). 7 findings returned; every load-bearing one was re-probed on disk by the
conductor before applying (W65 — the refuter's verdicts are leads, not facts).

1. **Gmail AI-Inbox gate too weak (OK-BUT-SHARPEN, most severe)** — the one recommendation
   grazing the absolute PII rule carried only an operator[business] label. APPLIED: re-gated
   as operator[PII/Law-2] with PII-free-mailbox/redaction-only shapes and skip-by-default.
2. **"9 servers in .mcp.json" (WRONG)** — re-count on disk: **11**. APPLIED: corrected, full
   list named, and the fragility noted (file is untracked per-machine state).
3. **DeepSeek retirement premise uncited (UNVERIFIED-NOT-FLAGGED)** — the scripts themselves
   say "explicitly allowed"; retirement is established by the owner decision, not by the code.
   APPLIED: citation added (retirement capture + memory); the drift IS the finding.
4. **"silently degrades to 2/3 every run" (OVERSTATED)** — re-probed: `MIN_LIVE_REVIEWERS=2`,
   W64-aware quorum, errors logged. APPLIED: reworded to "effectively 2-way by design; the
   'tri' label has been nominal since the seat died".
5. **Exa dead-AND-live contradiction (internal)** — re-probed: the live paid tool comes from
   user-scope `~/.claude.json` (servers: exa, gdrive), a different surface from the dead
   claude.ai connector. APPLIED: reconciliation stated inline.
6. **grep counts 16/9 not reproducible (OVERSTATED)** — re-run with declared scope:
   25 claude / 2 agy / 0 kimi (file-count, `scripts/`). APPLIED: replaced with the declared
   method's numbers.
7. **arsenal_probe line cite off (OK-BUT-SHARPEN)** — re-probed; also surfaced that the twin
   had ALREADY wired kimi into REQUIRED_SEATS (all 3 machines) — the residue is deepseek in
   ALL_SEATS + the pro row. APPLIED: cite fixed and the fresher ground truth recorded.

Verified-clean by the reviewer (not re-listed): `codex exec -i` unused; codex-redteam MCP
live-in-session; frozen invariants protected; publishing owner-only throughout; paid items
gated not armed.
