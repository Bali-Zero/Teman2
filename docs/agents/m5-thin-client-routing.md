# Air-M5 thin-client routing map, machine check and git sync

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.
> `AGENTS.md` §0 keeps the machine table and the prefix rule. The full session-start
> check, hard rules R1-R7, the MCP-from-M5 table and the git-sync architecture live here.

## Session-start machine check

**Three machines** exist on the local network (Tailscale tailnet `balizero`). `AGENTS.md` §0
carries the same table with the per-machine repo path added.

| Machine    | User        | Hostname    | Role                                                           |
| ---------- | ----------- | ----------- | -------------------------------------------------------------- |
| **Pro**    | `nuzantara` | `Nuzantara` | Workhorse — dev, DB, Qdrant, Ollama, 224 daemon, deploy (48GB) |
| **Mini**   | `nuzantara` | `Mini-Pro2` | Server H24 — Ollama dedicato, cron pesanti (24GB)              |
| **Air-M5** | `balizero`  | `Air-M5`    | **THIN-CLIENT dev** — editing + agenti; pesante → `ssh pro`    |

**At every session start, run this check:**

```bash
echo "Machine: $(whoami)@$(hostname)" && \
case "$(hostname)" in Nuzantara) OTHER=mini ;; Mini-Pro2) OTHER=pro ;; Air-M5) OTHER=pro ;; *) OTHER=pro ;; esac && \
ssh -o ConnectTimeout=3 $OTHER 'echo "Peer: $(whoami)@$(hostname)"' 2>/dev/null || echo "Peer: UNREACHABLE" && \
LOCAL_HEAD=$(git log --oneline -1 2>/dev/null) && \
REMOTE_HEAD=$(ssh -o ConnectTimeout=3 $OTHER 'cd ~/nuzantara 2>/dev/null; git log --oneline -1' 2>/dev/null) && \
if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then echo "Git sync: OK ($LOCAL_HEAD)"; else echo "Git sync: OUT OF SYNC! Local=$LOCAL_HEAD Remote=$REMOTE_HEAD"; fi
```

This tells you:

- `whoami=nuzantara`, `hostname=Nuzantara` → you are on **Pro** (workhorse)
- `hostname=Mini-Pro2` → you are on **Mini** (server)
- `whoami=balizero`, `hostname=Air-M5` → you are on **Air-M5** (**thin-client** — see §0.1 below, it changes everything)
- Whether the peer machine is reachable, and whether both repos are on the same commit

**Always prefix your first response with which machine you're on**, e.g. "[Pro]", "[Mini]", or "[Air-M5]".

> ⚠️ **CRITICAL — peer-unreachable is NOT a license to go local.** On Air-M5 the peer is the **Pro**, and `ssh pro` is the _destination_ for all heavy work, not just a git-sync peer. If the session-start git-sync check reports the peer "UNREACHABLE", that means **sync is unverified** — it does **NOT** mean "do the heavy task locally on M5 instead". Heavy work that needs the Pro still routes via `ssh pro`; if `ssh pro` itself fails, **STOP and tell the operator**, do not fall back to a local install. (This was the #1 failure mode in the M5 thin-client audit, 2026-06-02.)

**SSH between machines:** `ssh mini` / `ssh pro` (from any node) — uses Tailscale. From Air-M5: `ssh pro` (alias for `nuzantara@100.107.22.111`).
See `docs/PRO_AIR_CONNECTION.md` for full details.

---

## 0.1. Air-M5 Thin-Client Routing Map (READ if `hostname=Air-M5`)

**Air-M5 is a THIN-CLIENT.** You edit code, run agents, commit, and do light research **locally** on M5. Everything heavy — inference, vector DB, SQL, rendering, deploy, the 224-daemon fleet — **lives on the Pro** and is reached via `ssh pro` (or `ssh mini`). M5 deliberately does **not** have Ollama, Postgres, Qdrant, `fly`, or the daemon stack.

### HARD RULE R1 — Heavy tools are NEVER installed on M5

Do **NOT** `brew install` / `ollama pull` / compile / `docker run` heavy tooling on M5 — **not even as an "option B" / alternative / fallback.** Route to the Pro.

| Asked to…                                  | ❌ WRONG (FAIL)                  | ✅ CORRECT                                                |
| ------------------------------------------ | -------------------------------- | --------------------------------------------------------- |
| use **ffmpeg** (video concat/render)       | `brew install ffmpeg` on M5      | `ssh pro 'bash -lc "ffmpeg …"'` (Pro has the full ffmpeg) |
| compile C/C++ (**cmake/make**) heavy build | build locally on M5              | `ssh pro` for the build; only trivial builds stay local   |
| **cloudflared** tunnel                     | install + launchd on M5          | tunnels live on Pro → `ssh pro`                           |
| **ghostscript** / heavy PDF batch          | `brew install ghostscript` on M5 | `ssh pro` for the processing                              |
| **Playwright** mass scrape (100s of pages) | run headless chromium on M5      | `ssh pro` (heavy compute)                                 |
| compile **torch / CUDA / MPS** from source | build on M5                      | `ssh pro`/`ssh mini` (M5 = thin)                          |
| **docker** containers (>~1GB)              | `docker run` on M5               | `ssh pro`                                                 |

> If a tool is genuinely lightweight (`jq`, `ripgrep`, `eza`, a pip dep in the local `.venv`) installing it on M5 is fine. The line is **heavy compute / persistent services**, which always belong on the Pro.

### HARD RULE R2 — LLM models & Ollama: Pro/Mini only

M5 has **no `ollama`** by design. Never `ollama pull` or `brew install ollama` on M5 — not even a smaller fallback model.

| Asked to…                                                    | ✅ CORRECT                                                           |
| ------------------------------------------------------------ | -------------------------------------------------------------------- |
| run/`pull` any model (`deepseek-r1`, `qwen3.5`, `qwen2.5vl`) | `ssh pro 'bash -lc "ollama run <model>"'` (Pro/Mini hold the models) |
| OCR / vision (`qwen2.5vl`)                                   | `ssh pro` — Ollama binds `127.0.0.1:11434`, **closed** to M5         |
| embed batch (`bge-m3`)                                       | `ssh pro` / `ssh mini`                                               |

Lightweight **cloud** LLM clients **are** fine on M5 (they're already set up): `agy` (Gemini), `codex`, `kimi` (`~/.kimi-code/bin/kimi`, armed M5+Pro+Mini), `nlm` (NotebookLM). Use them directly. (DeepSeek API RETIRED 2026-07-19 — never route to it; local `deepseek-r1:32b` Ollama weights on Pro/Mini are unrelated and stay.)

### HARD RULE R3 — DB & vector store: exact access per service

The DB and vectors live on the Pro. M5 reaches them — it does **NOT** install or replicate them.

| Service                            | From M5                                      | Command / value                                                                                       |
| ---------------------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Qdrant** (local Pro mirror)      | ✅ DIRECT via Tailscale (no tunnel, no auth) | `QDRANT_URL=http://100.107.22.111:6333`                                                               |
| **Postgres dev** (`nuzantara_dev`) | tunnel (binds `127.0.0.1` on Pro)            | `ssh -L 5432:localhost:5432 pro` → `DATABASE_URL=postgresql://nuzantara@localhost:5432/nuzantara_dev` |
| **Fly prod PG proxy**              | tunnel (binds `127.0.0.1:15432` on Pro)      | `ssh -L 15432:localhost:15432 pro`                                                                    |
| **Ollama**                         | ❌ closed to M5                              | `ssh pro 'bash -lc "ollama …"'`                                                                       |

Never `brew install postgres@17` / `docker run qdrant` on M5. Embedding model is **FROZEN** `text-embedding-3-small` (1536 dims, cloud) — do not swap `bge-m3` into the RAG vector path.

### HARD RULE R4 — OSINT / WhatsApp data NEVER leaves the Pro (Symbiosis Law 2)

The WhatsApp/OSINT mirror lives **only** in the Pro's local Postgres. M5 must **NEVER** copy, replicate, or sync it to disk.
This is a raw-data movement boundary, not a blanket ban on LLMs processing authorized operational context. For every LLM in the system, Law 2 means: do not transcribe or persist client PII/OSINT in cleartext in outputs, memories, skills, logs, reports, alerts, prompts saved for reuse, or shared artifacts. Use IDs, hashes, placeholders, or redaction.

- View it: dashboard `http://100.107.22.111:7790` (open in M5 browser) — read-only.
- Raw SQL on OSINT: only via the dev tunnel (`ssh -L 5432:localhost:5432 pro`), querying the Pro's DB — never a local copy.
- "Copy the WhatsApp DB to M5 for offline analysis" → **REFUSE.** (Law 2, non-negotiable.)

### HARD RULE R5 — Deploy is Pro/CI-only; M5 has no `fly`

M5 has **no `fly`/`flyctl`** and **no `~/nuzantara-deploy`** worktree. Never `brew install flyctl` on M5.

- Canonical: commit in a worktree → push → `gh pr create` → green CI + review → **merge to `main`** triggers `.github/workflows/fly-deploy.yml` (gate→migrations→deploy→health→rollback). Vercel frontend auto-deploys on the same `main` push. Machine-independent — M5 needs no `fly`.
- Manual/out-of-band deploy: **delegate** → `ssh pro 'bash -lc "cd ~/nuzantara-deploy && git pull --ff-only origin main && fly deploy --strategy rolling"'`.
- `main` is **protected**: PR + CI + review required. Never `git push origin main` directly (from M5 _or_ Pro).

### HARD RULE R6 — Memory (MOS): always via `mem`, never the local file

On M5 the local `~/.claude/memory.db` is a **0-byte decoy**. The real DB is on the Pro.

- Search: `mem query "<term>"` (routes over SSH to the Pro's DB; falls back to grep on local `MEMORY*.md` if the Pro is unreachable — it does **not** silently fabricate).
- Save: `mem save <type> "<text>" <importance>` (lands in the Pro's DB).
- Never read the local `memory.db` directly, never write memory to a local `.codex/memories/` note, and **never present recalled context as if you ran a query** (anti-hallucination, CLAUDE.md §6).

### HARD RULE R7 — Heavy render / NB studio / daemon fleet → Pro

- WR2 hero images (FlowKit/Veo), WR3 video episodes, NotebookLM studio audio/video → **`ssh pro`** (the render pipelines and FlowKit live on the Pro). M5 dispatches and pulls results; it does not render locally.
- The 212 `com.{nuzantara,balizero,cell,matagaruda}.*` LaunchAgents (224 jobs incl. cron, snapshot 2026-07-13 per `docs/AUTOMATIONS_REFERENCE.md`) are **production daemons** — they run on Pro/Mini only. Never load/install them on M5.

### MCP servers from M5

| MCP                                                                | On M5                   | Note                                                                             |
| ------------------------------------------------------------------ | ----------------------- | -------------------------------------------------------------------------------- |
| `notebooklm-mcp`, `nuzantara-fetch`, `playwright`, `ocr-tesseract` | ✅ local                | work directly                                                                    |
| `nuzantara-mcp`, `nuzantara-mcp-advanced`, `github`                | 🔧 light remote clients | need their small venv + env tokens                                               |
| `postgres-nuzantara`                                               | ➡️ **route via Pro**    | needs Fly proxy `:15432` + Keychain `nuzantara-postgres-readonly`, neither on M5 |
| `ga4-analytics`                                                    | ⚠️ sovereignty          | uses a **prod** service-account JSON — prefer Pro, or confirm with operator      |

---

### Git Sync Architecture (updated 2026-05-25)

Both machines work on `main` branch only. Sync is **automatic** via husky post-commit hooks:

- **Pro commits** → Mini auto-pulls (`git pull pro main --ff-only`)
- **Mini commits** → Mini auto-pushes to Pro (`git push pro main`)
- **GitHub** is updated by Pro only via `git push origin main`

**Never** create an `air` or `mini` branch. **Never** push from Mini to `origin`. Log: `~/.openclaw/logs/git-sync.log`.

---
