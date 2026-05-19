# 4-LLM Panel Synthesis — WR2 + Intel Lake Fixes

**Date**: 2026-05-19 ~10:00 WITA
**Quorum**: 2/3 (Gemini 3.1 Pro + DeepSeek Reasoner converged; Codex still running)
**Note**: Cicatrix scar 2026-04-29 Wave 2 Pro precedent: 2/4 con DeepSeek solido > stallo

## Convergent fixes (both panelists)

| #   | Fix                                            | Sev | ROI         | Both LLMs agree?                                   |
| --- | ---------------------------------------------- | --- | ----------- | -------------------------------------------------- |
| 1   | Venv-presence watchdog in WR2 wrapper          | P0  | High        | ✅ Both #1                                         |
| 2   | Purge legacy canva-renderer plist + script     | P0  | High        | ✅ Both #2 (DeepSeek: "PANEL_DECISION ship first") |
| 3   | Log-size threshold alerter (Telegram >1MB)     | P1  | Medium-High | ✅ Both #3                                         |
| 4   | Git branch-hijack guard on ~/Desktop/nuzantara | P1  | High-Medium | ✅ Both #4                                         |
| 5   | Supervisor uptime healthcheck (Telegram)       | P1  | Medium      | ✅ Both #5                                         |
| 6   | Stderr→stdout for outbox-drain logger          | P2  | Low         | ✅ Both #6                                         |
| 7   | Rimuovere plist-watchdog se zombie             | P2  | Low         | DeepSeek only                                      |

## Divergences (worth noting)

| Aspect           | Gemini approach                           | DeepSeek approach                                                      | Synthesis                                                                                                      |
| ---------------- | ----------------------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Venv missing fix | **Fail-fast** + Telegram alert + exit 1   | **Auto-heal** (python -m venv + pip install) + alert if creation fails | **Both**: alert+exit on first miss → manual fix per audit trail; auto-heal post-second-miss to avoid 84h again |
| Branch hijack    | Pre-checkout git hook BLOCKS all checkout | Wrapper `git-safe` ASKS confirmation                                   | **Hook** wins for autonomous-agent collision (no human at terminal to confirm)                                 |
| Canva-renderer   | bootout + rm plist + archive script       | Stessa via, + update CICATRIX log explicitly                           | DeepSeek's CICATRIX update is the cicatrix-antibody contract                                                   |

## Priority ship order (synthesized)

### Wave 1 — P0 (today, ~10 min total)

**1A. Purge canva-renderer (Fix #2, ~2 min, ZERO risk)**

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-renderer.plist 2>/dev/null
mv ~/Library/LaunchAgents/com.balizero.wr2.canva-renderer.plist \
   ~/Library/LaunchAgents/.disabled-2026-05-19/com.balizero.wr2.canva-renderer.plist.purged-1019
mkdir -p ~/Desktop/nuzantara/scripts/.disabled-2026-05-13/
git -C ~/Desktop/nuzantara mv scripts/wr2_canva_apply.py \
   scripts/.disabled-2026-05-13/wr2_canva_apply.py.purged-1019
echo "2026-05-19 10:19 PURGED com.balizero.wr2.canva-renderer + wr2_canva_apply.py" >> ~/Desktop/nuzantara/.claude/rules/cicatrix-scars.md
```

Verification: `launchctl list | grep canva-renderer` → empty.

**1B. Venv-presence guard in wrapper (Fix #1, ~5 min)**

- Edit `~/.openclaw/bin/wr2/wr2-script-wrapper.sh`
- Before `exec "$VENV_PY"`: check `[[ ! -x "$VENV_PY" ]]` → Telegram alert + exit 75
- Cron `~/Library/LaunchAgents/com.balizero.wr2.venv-watchdog.plist` every 15min: `[[ -x "$VENV" ]] || alert`
- **Both alert + exit**: prima esecuzione manca → alert, NON auto-heal (audit-trail prima istanza). Watchdog cron auto-heal solo dopo seconda miss in <1h (heuristic: real disappearance vs git pull race).

**1C. Log-size watchdog (Fix #3, ~5 min)**

- `~/Desktop/nuzantara/scripts/log_size_watchdog.sh`: find ~/logs -size +5M → Telegram (5MB threshold vs Gemini's 1MB — avoid spam on legitimate growth)
- Plist `com.balizero.nuzantara.log-size-watchdog.plist`, StartInterval=3600 (hourly)
- Auto-truncate via `logrotate` script per file >50MB

### Wave 2 — P1 (this week, ~30 min)

**2A. Git pre-checkout hook on ~/Desktop/nuzantara**

- Hook che richiede env var `NUZANTARA_BRANCH_CHANGE_ALLOWED=1` o esce con error
- Documenta in CLAUDE.md: "Branch switch sul worktree principale richiede flag esplicito"

**2B. Supervisor uptime healthcheck**

- Cron 5-min: check `launchctl print com.balizero.wr2.supervisor | grep "state = running"` + `pid != 0` AND last_exit_code in {0, never}
- Stato fail → Telegram con `runs=N last_exit=X` per debug

### Wave 3 — P2 (nice-to-have, opportunistic)

- Outbox-drain logger stderr→stdout
- plist-watchdog audit (kill if zombie)
- Cicatrix-antibody enforcer: pre-commit hook che blocca `git mv` di plist in `.disabled-*` senza touching `cicatrix-scars.md`

## Decision: which to ship FIRST?

| Panelist                    | Vote                                                                                                                                                                                             |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Gemini                      | Fix #1 (venv watchdog) — "single point of failure for tutto l'ecosistema Python"                                                                                                                 |
| DeepSeek                    | Fix #2 (purge canva-renderer) — "Costo zero (10 secondi), risolve 1122 traceback/giorno"                                                                                                         |
| Synthesis (Claude Opus 4.7) | **Fix #2 first**, then Fix #1, then #3 — Fix #2 è 30 sec, ferma il leak, lascia spazio per testare Fix #1 senza noise. Cf. Symbiosis Legge 7: "Numeri prima" — 1122 traceback evitati immediati. |

**Ship-first**: **Fix #2 (purge canva-renderer)** — atomic 30s operation, zero rollback risk because DB kill-switch già OFF da 4 giorni.

**Ship-second**: **Fix #1 (venv watchdog)** — l'antibody fondamentale, copre la classe di failure più costosa (84h downtime).

**Ship-third**: **Fix #3 (log-size watchdog)** — meta-antibody che PREVERREBBE future istanze di "supervisor crashloop silenzioso" perché 6.3MB log avrebbe triggered alert.

---

## CODEX UPDATE (3/3 quorum reached)

Codex GPT-5.5 finally completed. CONFIRMS the convergence + adds 2 unique critical insights:

### Codex unique contribution #1: Supervisor heartbeat file

```python
# supervisor main loop
HEARTBEAT = Path.home() / "logs/wr2-supervisor.heartbeat.json"
def write_heartbeat(status): HEARTBEAT.write_text(json.dumps({"status":status,"ts":time.time(),"pid":os.getpid()}))
```

- watchdog: `check_heartbeat.py $HB --max-age 600 || alert`

**Why this matters**: detects the INVISIBLE crashloop pattern — `launchctl print` shows `runs=154, state=running` but the process is actually doing nothing useful (events_outbox grows, drafts stuck). Only a self-emitted heartbeat catches this. Gemini+DeepSeek missed this nuance.

### Codex unique contribution #2: launchd cicatrix lint

```bash
# scripts/ops/lint_launchd_cicatrix.sh
BAD='wr2_canva_apply.py|Desktop/nuzantara/scripts/.*wr2_.*\.py'
for plist in ~/Library/LaunchAgents/*.plist; do
  plutil -p "$plist" | rg -q "$BAD" && echo "FORBIDDEN legacy: $plist" && exit 1
done
```

**Why this matters**: this is the **cicatrix antibody at the system level**. Prevents the "decommissioned script resurrected by re-bootstrapping" pattern that caused canva-renderer to come back. Runs as pre-push hook + daily ops gate.

### Codex unique contribution #3: cooperative repo lock (.repo-owner)

vs Gemini's global pre-checkout block (heavy-handed) vs DeepSeek's `git-safe` interactive wrapper (requires human terminal).

Codex's `.repo-owner` file approach: lightweight, cooperative, kicks in only when 2+ agents try to touch `~/Desktop/nuzantara` simultaneously.

## FINAL FIX SHIP ORDER (3/3 quorum)

| Wave   | Fix                                                                       | Owner agreement       | Effort        |
| ------ | ------------------------------------------------------------------------- | --------------------- | ------------- |
| **1A** | **Purge canva-renderer**                                                  | 3/3 P0 High           | 30 sec        |
| **1B** | **Venv-preflight in wrapper** (auto-heal flavor per Codex+DeepSeek)       | 3/3 P0 High           | 5 min         |
| **1C** | **Log-size watchdog Telegram** (1MB threshold per Codex, NOT 5MB)         | 3/3 P1 High           | 5 min         |
| **2A** | **Supervisor heartbeat** (Codex unique, critical for invisible crashloop) | NEW from Codex        | 15 min        |
| **2B** | **launchd cicatrix lint** (Codex unique, anti-resurrection)               | NEW from Codex        | 10 min        |
| **2C** | Git pre-checkout / .repo-owner lock                                       | 3/3 P1 mixed approach | 10 min        |
| **3A** | Stderr→stdout outbox-drain                                                | 3/3 P2 Low            | 5 min         |
| **3B** | Plist-watchdog audit                                                      | DeepSeek+Codex        | opportunistic |

**Convergent PANEL_DECISION**:

- Gemini: Fix #1 (venv)
- DeepSeek: Fix #2 (purge canva-renderer) — ship first because zero-risk
- Codex: Fix #1 (venv preflight)
- **Claude Opus 4.7 synthesis**: ship in order **1A → 1B → 1C → 2A** (purge first because atomic, then venv guard, then proactive surveillance, then heartbeat for invisible-crashloop detection)

Cicatrix scar EventBus 2026-04-29 precedent: outbox replay design saved 84h downtime from data loss. Now we add: **prevention** (venv guard), **detection** (heartbeat + log size), **recovery** (cicatrix antibody enforcer).
