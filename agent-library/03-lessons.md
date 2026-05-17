# Agent Library — Lessons (hand-written 2026-05-17, revised post 3-LLM panel)

<!-- DO NOT auto-regenerate — this file is curated by hand. -->
<!-- Curated index: each entry links to primary source (memory file or cicatrix). -->
<!-- 20 entries in 3 categories + 5 meta-patterns. -->
<!-- Revised 2026-05-17: pattern correlato cross-refs aligned to 02-patterns.md v2. -->

20 lezioni operative trasversali, curate da memory files + cicatrix-scars.
Ogni entry: sintesi (2 righe), quando applica (1 riga), link a fonte
primaria, **pattern correlato** (cross-ref a `02-patterns.md`).

**Lesson = incident evidence** showing why a pattern exists.
**Pattern = reusable design primitive** with trigger, invariant, implementation shape.
La cross-reference fra le 20 lessons e i 9 pattern è many-to-one (più lessons
sostengono lo stesso pattern, es. #1+#2 → P5 verify; #4 → P7 review gate).

Le 5 meta-pattern in coda sono **sintesi cross-source** (non in nessun
single file).

## Indice

### A — Orchestration & Wave (6)

1. Verify-not-trust durante orchestration
2. Errare è umano, allucinare è diabolico
3. Wave pacing: cap 4 parallele, brainstorm 3 scambi
4. Devils-advocate cap 3 iter
5. Close-out numbers unverified
6. Capacity exhaustion wave-level: 1/4 LLM è OK

### B — Infra & filesystem (8)

7. Sibling automation switches branches → untracked file loss
8. `fs_usage -w -f filesys` come trap 24/7 fonde il Mac
9. SSH non-interactive PATH trap
10. SSH remote claude requires absolute path
11. NordVPN blocks Tailscale data-plane
12. Pro↔Mini subnet split (Tailscale fallback)
13. fly CLI token regression → intel-lake cascade
14. Python SSH heredoc escape

### C — Design & process (6)

15. Brief stale premise pattern
16. Always review spec with 4-LLM panel BEFORE user approval
17. Backend RAG venv symlink trap
18. plist worktree path trap
19. Multi-agent topology Kim 2025
20. Orchestrator issue race

### Meta-patterns (5 emergenti)

- Silent failure shape
- Path-dependence trap (zsh/SSH/launchd)
- Cross-host async drift
- Premise staleness
- Self-induced load

---

## A — Orchestration & Wave

### 1. Verify-not-trust durante orchestration

**Sintesi**: orchestrator che dispatcha sub-agent deve verify disk state (gh/git/fs) prima di trust completion. Idle notification non = completion signal. Soglia pratica: 20-30min silence → disk investigate.
**Quando applica**: silenzio sostanziale ≥20-30min da un sub-agent in pipeline.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons.md:286` (Wave 2 Pro 2026-04-29 entry)
**Pattern correlato**: `02-patterns.md#5` (empirical post-action verification)

### 2. Errare è umano, allucinare è diabolico

**Sintesi**: mai fabbricare output di tool calls. Context buffer NON è autoritativo. Re-Read in this turn ogni citation critica. 5 regole operative + post-Write `ls -la` mandatory.
**Quando applica**: qualsiasi citation di file content, output Bash, ls/Read result, decisione downstream.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_hallucinating_tool_output_is_diabolical.md`
**Pattern correlato**: `02-patterns.md#5` (empirical post-action verification)

### 3. Wave pacing: cap 4 parallele, brainstorm 3 scambi

**Sintesi**: wave 6-sessioni 2026-05-07: FASE 2 gonfiata per brainstorm no-cap + design review missing + scope esterno-irreversibile in parallel. Cap 4 sessioni se ≥1 tocca prod esterna, brainstorm max 3 scambi.
**Quando applica**: prima di spawnare ≥3 agent paralleli; durante design phase.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_wave_pacing_design_rigor.md`
**Pattern correlato**: `02-patterns.md#8` (parallel wave + capacity caps)

### 4. Devils-advocate cap 3 iter

**Sintesi**: red-team loop senza cap → infinite refinement editorial (P1 BLOCK → P3 risolto → P4-P7 medium-only nitpicks). Cap 3 iterazioni hardcoded. 7-pass = 30min + $0.30 vs 3-pass 12min + $0.15 con same outcome.
**Quando applica**: red-team gate pre-publish su dossier/research/quote/strategy.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_devils_advocate_loop_pattern.md`
**Pattern correlato**: `02-patterns.md#7` (bounded adversarial review gate)

### 5. Close-out numbers unverified

**Sintesi**: close-out wave 2026-05-07 dichiarato "40 NB live, coverage 7/40=17%" senza verify. Reale empirico 2026-05-08: 6 ACTIVE in registry SSOT, coverage 117%. Nemmeno i numeri "tuoi" recenti sono trustabili — re-derive at declaration time.
**Quando applica**: ogni numero quantitativo (count, coverage %, PR shipped, registry entries) in close-out/status report.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_close_out_numbers_unverified.md`
**Pattern correlato**: meta `Premise staleness`

### 6. Capacity exhaustion wave-level: 1/4 LLM è OK

**Sintesi**: quando Codex+Gemini+NLM falliscono simultaneamente (pattern wave-level: ≥2 cloud LLM exhaust in 5min), 1/4 con DeepSeek/Ollama solido è preferibile a "wait for capacity". Stallo > singolo-LLM-bias.
**Quando applica**: brainstorm cross-LLM con 2/4 threshold target durante wave parallel.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons.md:286` (Wave 2 Pro 2026-04-29)
**Pattern correlato**: `02-patterns.md#4` (provider cascade + circuit breaker)

---

## B — Infra & filesystem

### 7. Sibling automation switches branches → untracked file loss

**Sintesi**: nuz-sync / parallel claude sessions fanno `git stash + checkout` automatico. `git stash` senza `-u` non stasha untracked. 2 incidenti 2026-04-29 in 9h, recovery via `git fsck --dangling --no-reflogs` (solo se `git add`-ed).
**Quando applica**: lunga sessione con untracked files; pre-sessione check `ps aux | grep claude | wc -l <3`. WIP-commit-every-10min se untracked exist.
**Fonte primaria**: `.claude/rules/cicatrix-scars.md:144` (Untracked files lost entry)
**Pattern correlato**: meta `Silent failure shape`

### 8. `fs_usage -w -f filesys` come trap 24/7 fonde il Mac

**Sintesi**: `fs_usage -f filesys` è firehose kernel. 4h30min idle = 158min CPU + 5.2GB RAM, load 12.07/14 core. Mai daemon hot 24/7. Alternative: eslogger (kernel-side filter), LaunchAgent intervallato + timeout, auto-kill watchdog su RSS>2GB/CPU>50%.
**Quando applica**: forensic trap per eventi rari (plist corruption, file deletion mystery). Decidi window max a priori.
**Fonte primaria**: SessionStart hook entry 2026-04-29 + `.claude/rules/cicatrix-scars.md` (P0-3 plist corruption)
**Pattern correlato**: meta `Self-induced load`

### 9. SSH non-interactive PATH trap

**Sintesi**: `ssh mini "which X"` usa PATH `/usr/bin:/bin:/usr/sbin:/sbin`, non sourca `.zshrc`. claude/ollama/tailscale appaiono missing ma esistono. 3 falsi negativi consecutivi 2026-05-04.
**Quando applica**: ogni script che fa `ssh peer "<cmd>"` per check tool presence. Sempre pre-export PATH o usa absolute path.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_ssh_path_audit.md`
**Pattern correlato**: meta `Path-dependence trap`

### 10. SSH remote claude requires absolute path

**Sintesi**: `ssh -t mini "claude"` fallisce con "command not found" anche con tty. `-t` alloca tty ma non cambia init flow (shell rimane non-interactive non-login → `.zshrc` non sourcato). Path assoluto `/opt/homebrew/bin/claude` obbligatorio. Stesso trap per gemini/codex/nlm.
**Quando applica**: alias SSH cross-machine LLM CLI; scripts che invocano CLI tramite ssh.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_ssh_remote_claude_path.md`
**Pattern correlato**: meta `Path-dependence trap`

### 11. NordVPN blocks Tailscale data-plane

**Sintesi**: NordVPN dirotta routing → `tailscale ping` OK via DERP relay USA (control plane) ma TCP timeout su 22/5900/11434/6333/5432 (data plane). NordLynx Extension al 28% CPU. Fix: disconnetti NordVPN, ritesta.
**Quando applica**: Tailscale ping OK ma SSH/HTTP/TCP timeout verso peer remoto. `ps -Ao comm | grep -iE "nordlynx|protonvpn|wireguard|openvpn"`.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_nordvpn_tailscale_block.md`
**Pattern correlato**: meta `Cross-host async drift`

### 12. Pro↔Mini subnet split (Tailscale fallback)

**Sintesi**: Pro 192.168.0.x, Mini 192.168.110.x → mDNS rotto bidirezionale. SSH alias usano Tailscale IP (100.93.236.6 Mini / 100.107.22.111 Pro), RTT 62ms via DERP USA. Mai mDNS hostname per peer cross-subnet.
**Quando applica**: ogni alias SSH peer cross-subnet; sync daemon Pro↔Mini deve avere LAN→Tailscale fallback.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/discovery_pro_mini_subnet_split_2026_05_06.md`
**Pattern correlato**: meta `Cross-host async drift`

### 13. fly CLI token regression → intel-lake cascade

**Sintesi**: fly CLI v0.4.49 ignora `access_token:` in `~/.fly/config.yml`. CLI dice "no token" pur token API-valido (curl OK). Cascade: pg-proxy fail → router/pusher no-PG → Telegram spam 13h. Fix: wrapper passa `-t <token>` esplicito.
**Quando applica**: ogni wrapper/cron che invoca `fly` CLI in non-interactive mode. Verifica token con API call diretta prima di sospettare expiry.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_fly_cli_token_regression_cascade.md`
**Pattern correlato**: meta `Silent failure shape` + `Cross-host async drift`

### 14. Python SSH heredoc escape

**Sintesi**: heredoc nested in ssh + python `-c` → 3 layer interpretation. Variabili shell `$VAR` → `\\\\\$VAR` (4 backslash). Bug live 2026-05-10 ha rotto git-pull-main.5min su Mini per 10 min.
**Quando applica**: ogni script che esegue Python remoto via ssh + heredoc. Prefer file upload + execute.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_python_ssh_heredoc_escape.md`
**Pattern correlato**: meta `Path-dependence trap`

---

## C — Design & process

### 15. Brief stale premise pattern

**Sintesi**: 4× incident in 24h (2026-05-07→05-08): brief orchestrator basati su content stale (cicatrix, MEMORY.md, design doc) vs codebase HEAD. Tasso errore ~50%. Mandatory pre-brief sweep 60-120s empirical contro HEAD.
**Quando applica**: prima di scrivere brief che deriva da cicatrix/memory/spec. Verifica scope claim empiricamente (launchctl list, sqlite count, redis XLEN, wc -l, gh pr view).
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_brief_stale_premise_pattern.md`
**Pattern correlato**: meta `Premise staleness`

### 16. Always review spec with 4-LLM panel BEFORE user approval

**Sintesi**: fan-out parallel Gemini + GPT-5.5 codex + DeepSeek V4 Pro (+ NB-1 se UUID noto). Cost $0.01/section, ~2min wall. Caught killer OAuth flaw in FileTokenStorage v1 (3/3 LLM convergence). Hard rule 2026-05-13.
**Quando applica**: ogni spec ≥3 file diversi o feature critical-path o qualsiasi cosa che mergia a main.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/feedback_always_review_spec_with_4_llm.md`
**Pattern correlato**: `02-patterns.md#7` (bounded adversarial review gate)

### 17. Backend RAG venv symlink trap

**Sintesi**: `apps/backend-rag/.venv` è SYMLINK al root `.venv` del repo, non venv reale. Tutti i 5 worktree puntano al parent → self-loop sovrascrive simbolicamente, sintomo "Too many levels of symbolic links" in cascata.
**Quando applica**: setup nuovo worktree con backend-rag deps; pre-commit hook che cerca venv path; mai sovrascrivere `apps/backend-rag/.venv`.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_backend_rag_venv_symlink.md`
**Pattern correlato**: meta `Path-dependence trap`

### 18. plist worktree path trap

**Sintesi**: sub-session che modifica plist live setta `PYTHONPATH`/`ORGANISM_RULES_PATH` al proprio worktree path. Quando worktree muore (auto-cleanup post-merge o manual remove), daemon error loop FileNotFoundError. P1 incident 2026-05-08, 4h24min.
**Quando applica**: qualsiasi modifica a plist loaded in launchd. Tutte `EnvironmentVariables` con path filesystem → main checkout `~/Desktop/nuzantara/`, MAI worktree.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_plist_worktree_path_trap.md`
**Pattern correlato**: meta `Path-dependence trap`

### 19. Multi-agent topology Kim 2025

**Sintesi**: Kim et al. arxiv 2512.08296 (Google DeepMind+MIT, Dec 2025). 5 topology controlled study, 180 configs. SAS=1× baseline, **Centralized (orchestrator-led)=4.4×**, **Independent (parallel no-coord)=17.2×** error amplification. Centralized preferito per task indipendenti parallelizzabili.
**Quando applica**: design wave/cron multi-LLM cross-tool; scelta topology fra single-agent vs orchestrator-led vs peer-to-peer.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_multi_agent_topology_kim_2025.md`
**Pattern correlato**: `02-patterns.md#8` (parallel wave + capacity caps)

### 20. Orchestrator issue race

**Sintesi**: orchestrator main + sub-session creano contemporaneamente issue/PR per stesso task → race window 5-30s genera duplicati. 2026-05-07: #491 (orchestrator) + #490 (sub-session) titoli identici, label diversi. Pre-search obbligatorio.
**Quando applica**: prima di `gh issue create` / `gh pr create` da orchestrator quando wave ≥4 sessioni attive.
**Fonte primaria**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_orchestrator_issue_race.md`
**Pattern correlato**: `02-patterns.md#1` (single-flight / lease / idempotency guard — questa lesson è l'evidence empirica del pattern).

---

## Meta-patterns (5 emergenti — cross-source synthesis)

Questi **NON sono in nessun memory file singolo** — emergono dal confronto di 2+ entries sopra. Esplicitamente **sintesi**, non quote. Sono i pattern di secondo livello che fanno da "framework di lettura" alle 20 lezioni.

### Meta: Silent failure shape

**Supported by**: #7 (untracked file loss, no exception), #13 (fly CLI silent "no token" pur API-valido), #8 (fs_usage idle killing Mac without alert).

I peggiori failure non lanciano exception: file scompaiono, processo "completa" con exit=0, log gridano successo ma metric=0. Il pattern di mitigation è **empirical post-action verify**, mai trust del solo status code. Esempi concreti: post-Write `ls -la` (regola anti-hallucination); post-commit `git status`; post-deploy verify endpoint; post-fly-CLI verify token con API call diretta. Lo status code è il livello più alto di indirezione — sotto vivono i fail silenziosi.

### Meta: Path-dependence trap (zsh/SSH/launchd)

**Supported by**: #9 (SSH non-interactive PATH), #10 (SSH remote claude absolute path), #14 (heredoc escape), #17 (venv symlink), #18 (plist worktree path).

Ogni layer (zsh -c, ssh non-interactive, launchd plist, ssh -t with .zshrc, docker container WORKDIR, worktree symlink venv) ha **PATH e working-dir diversi**. Default: usa path assoluti per ogni binario critico (`/opt/homebrew/bin/...`), mai aliases, mai assumere `.zshrc` venga sourcato. Per launchd e cron: `EnvironmentVariables` block esplicito (VADEMECUM §11). Pattern positivo: env var (`WR2_REPO_ROOT`, `GARUDA_REDIS_HOST`) >> symlink relativo.

### Meta: Cross-host async drift

**Supported by**: #11 (NordVPN block Tailscale), #12 (Pro↔Mini subnet split), #13 (fly CLI cascade — Fly proxy host resolve).

LAN, Tailscale, NordVPN, Fly proxy, AWS region: assumere "host raggiungibile" è false. Pattern di mitigation: **always fallback chain** (LAN → Tailscale → DERP relay), never assume. Per cross-host sync daemons (5 attivi Pro↔Mini): patch tutti per LAN-first/Tailscale-fallback (cf. `~/scripts/mini-setup/memory-sync-bidirectional.sh`). Per consumers cross-host (Redis, PG): env var override hostname (`GARUDA_REDIS_HOST=100.93.236.6`), no mDNS hardcode.

### Meta: Premise staleness

**Supported by**: #1 (verify-not-trust), #5 (close-out numbers unverified), #15 (brief stale premise).

Numeri, file content, output Bash letti N turni fa **non sono validi adesso**. Sibling process possono averli modificati. Pattern: **re-derive in this turn** prima di buildare decisione critica. Soglia pratica: ≥5 messaggi da quando hai letto un fact = sospetto stale. Per close-out report: 60s pre-derive empirica per ogni numero quantitativo (launchctl list count, sqlite SELECT count(\*), wc -l, gh pr view --json). Per Read citation: hard rule "this turn or re-Read".

### Meta: Self-induced load

**Supported by**: #8 (fs_usage trap fonde Mac), cicatrix `fs_usage -w -f filesys 24/7` (P0-3 plist corruption rearm).

Tool diagnostici diventano **la causa** del problema che diagnosticano. fs_usage trap forensic = il trap stesso diventa hot daemon. Pattern di mitigation: **time-cap a priori** ogni forensic trap (window 24h max), auto-kill watchdog su RSS>2GB o CPU%>50% sostenuto, preferire kernel-side filter (eslogger) a userspace firehose. Lezione generale: aumentare osservabilità ha costo — cap esplicito always, never "let it run and see what we catch".
