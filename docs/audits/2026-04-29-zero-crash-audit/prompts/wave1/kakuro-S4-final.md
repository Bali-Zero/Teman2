# kakuro-S4-final — Plist corruption: identify writer + permanent fix

> Single-file prompt for one Claude Code Max x20 session.
> Macchina: **Pro** (`nuzantara@Nuzantara`). Worktree: usa quello esistente p0-3 oppure ricreane uno.
> Session command: in your tmux pane:
>
>     leggi kakuro-S4-final e esegui

---

## Contesto

Il 2026-04-29 ~15:09 WITA un writer non identificato ha corrotto **51 dei 54 plist project** in `~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist`. Pattern di corruzione: ogni file diventa l'output JSON di un `plutil -extract <key> json` redirect lethal sopra il file stesso.

S4 wave1 ha già fatto:
- ✅ 53/54 plist ricostruiti (in memoria via `launchctl print` + `plistlib.dump` atomico)
- ✅ 9 secret leakati identificati (TELEGRAM, GH_TOKEN, FLY_API_TOKEN, GOOGLE_API_KEY, ecc.)
- ✅ Branch `feat/p0-3-launchagents` commit `c3218dba5` pushato su origin (NON merged)
- ✅ Scripts `lint_launchagents.sh` + `patch_launchagents.sh` committati nel branch
- ✅ Cattura `fs_usage` attiva sotto root (`~/p0-3-recovery/fs_usage_trap/capture-*.log`)
- ✅ canary lite watching `cell.organism` size

S4 NON ha ancora:
- ❌ identificato il writer (cattura in corso)
- ❌ disabilitato writer (perché non sa quale è)
- ❌ aperto PR per i lint/patch scripts
- ❌ rotato i 9 secret leakati
- ❌ chiuso definitivamente la cicatrix STRUCTURAL

## Goal

**Identificare il writer + disabilitarlo + chiudere il caso** in un'unica sessione end-to-end. Output finale: cicatrix marcata RESOLVED, PR aperta+mergeded, secret rotati.

## Phase 1 — Verify cattura fs_usage produced evidence

```bash
cd /Users/nuzantara/Desktop/nuzantara
source docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh

# Check capture file
ls -lah ~/p0-3-recovery/fs_usage_trap/capture-*.log
wc -l ~/p0-3-recovery/fs_usage_trap/capture-*.log

# If size > 100KB or > 1000 lines: cattura ha visto eventi
# If size ~0: cattura non ha visto nulla (writer non ha ricolpito)
```

If cattura ha eventi (writer ha colpito di nuovo dopo Wave 1): grep per scritture su `*.plist`:

```bash
grep -E "(WrData|O_TRUNC|open.*LaunchAgents)" ~/p0-3-recovery/fs_usage_trap/capture-*.log | head -50
```

If nessun evento di corruzione (canary lite NON ha rilevato): fai forensics retroattivo.

## Phase 2 — Forensics retroattivo (se cattura non ha visto wave nuovo)

Caccia il writer dai pattern indiretti:

### 2a. Script che fanno redirect lethal pattern

```bash
# Pattern A: plutil -extract con redirect verso lo stesso file (lethal)
rg --no-ignore-vcs 'plutil[^>]*-extract[^>]*>[^"]*plist' ~/ 2>/dev/null --max-depth 8 | head -20

# Pattern B: redirect su $plist o $LABEL.plist
rg --no-ignore-vcs '> *"?\$\{?(plist|LABEL|file|f)\}?[^"]*\.plist' ~/Desktop/nuzantara ~/scripts ~/.claude ~/.agent 2>/dev/null | head -20

# Pattern C: validate-and-rewrite without read first (cmd > file pattern)
rg --no-ignore-vcs '(plutil|defaults read).*>\s*"?(\$|/|~)' ~/Desktop/nuzantara ~/scripts ~/.claude 2>/dev/null --max-depth 5 | head -20
```

### 2b. Script modificati nelle 24h prima di 15:09

```bash
find ~/scripts ~/.claude/scripts ~/Desktop/nuzantara/scripts -type f \
  \( -name "*.sh" -o -name "*.py" \) \
  -newer /tmp/_baseline_2026_04_28 \
  ! -newer /tmp/_baseline_2026_04_29_1500 2>/dev/null
# (crea i baseline file `touch -t 202604281500 /tmp/_baseline_2026_04_28` e
#  `touch -t 202604291500 /tmp/_baseline_2026_04_29_1500`)
```

### 2c. macOS log show retrospettivo

```bash
log show --predicate 'eventMessage CONTAINS "plist" OR eventMessage CONTAINS "LaunchAgents"' \
  --start "2026-04-29 15:08:00" --end "2026-04-29 15:11:00" 2>&1 | head -50
```

### 2d. Cron OpenClaw e LaunchAgents fired ~15:09

Quale daemon era schedulato/in esecuzione alle 15:09?

```bash
# Cron OpenClaw
grep "15:0[7-9]\|15:1[0-2]" ~/logs/cron-agent/*.log 2>/dev/null | head -20
grep "$(date -u -j -f '%Y-%m-%d %H:%M' '2026-04-29 07:09' '+%s')" ~/logs/openclaw/*.log 2>/dev/null | head -10

# LaunchAgents fired in window
log show --predicate 'subsystem CONTAINS "com.apple.launchd"' \
  --start "2026-04-29 15:08:00" --end "2026-04-29 15:11:00" 2>&1 | grep -E "spawned|exited" | head -30
```

### 2e. Sospetti specifici

Verifica questi sospetti (in ordine di probabilità):

1. **`scripts/launchd_compliance.py`** o simili compliance check (se esiste)
2. **`system_doctor.py`** Pro local — è stato patchato il 20/04, possibili bug
3. **automap-server / automap-watchdog / automap-telegram** (i 3 plist superstiti — sospetto: forse i 3 stessi sono il writer)
4. **scripts/cron-wrapper.sh** (modificato di recente)
5. **agent autonomous fix** che gira via OpenClaw

```bash
# Per ogni sospetto, grep per accesso a LaunchAgents e plutil
for f in ~/scripts/system_doctor.py ~/scripts/cron-wrapper.sh \
         ~/.local/bin/automap-* \
         ~/Desktop/nuzantara/scripts/cron-agent-python/*.py; do
    [ -f "$f" ] || continue
    if grep -lE "LaunchAgents|plutil.*extract.*>" "$f" 2>/dev/null; then
        echo "=== $f ==="
        grep -nE "LaunchAgents|plutil" "$f" 2>&1 | head -10
        echo ""
    fi
done
```

## Phase 3 — Cross-LLM brainstorm (se Phase 2 non identifica)

```bash
cat > /tmp/kakuro-S4-final-brief.txt <<'BRIEF'
INVESTIGATION: 51 of 54 macOS LaunchAgent plist files (~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist) on Pro Mac were corrupted at 2026-04-29 15:09:15-17 WITA. All files have mtime within 2 seconds — single writer, programmatic.

CORRUPTION PATTERN: Each plist file became the JSON output of `plutil -extract <key> json`. Examples:
- `com.balizero.intel.nightly.plist` content: `{"Hour":1,"Minute":0}` (was StartCalendarInterval value)
- `com.cell.organism.plist` content: `{"PATH":"...","HOME":"...","TELEGRAM_BOT_TOKEN":"..."}` (was EnvironmentVariables value)
- File size dropped from ~700-1200 bytes to 20-1100 bytes

WRITER SIGNATURE: 
- Touches all loaded labels at once (3-second window)
- Reads + writes (NOT just reads)
- Uses plutil -extract internally
- The 3 surviving plist (com.nuzantara.prime-tunnel, com.nuzantara.zombie-hunter, com.cell.organism — wait com.cell.organism IS corrupted; let me re-verify) have a common property — they're either NOT loaded OR they were the writer's "self-exception"

PROD ENVIRONMENT:
- macOS 14 (Pro)
- launchd, launchctl, plutil, system_doctor.py, automap-server suite
- ~14 cron OpenClaw jobs running daily
- 19 Claude Code Max sessions concurrent during corruption window

YOUR TASK: Hypothesize 3 most-likely culprits + 3 detection scripts + 1 permanent prevention. Be specific to macOS launchd model.

CONSTRAINTS:
- No reboot allowed (would lose remaining loaded daemon memory)
- Write-only solution acceptable; can't recover from old corruption
- File mode 0644 = world-readable, must reduce to 0600 for sensitive plist
BRIEF

mkdir -p /tmp/kakuro-S4-final-brainstorms
coord_brainstorm "plist corruption forensics" /tmp/kakuro-S4-final-brief.txt /tmp/kakuro-S4-final-brainstorms

for llm in codex gemini deepseek notebooklm; do
    echo "=== $llm ==="; head -100 /tmp/kakuro-S4-final-brainstorms/$llm.md
done
```

Sintetizzare i 3 sospetti più convergenti tra le 4 LLM analyses.

## Phase 4 — Identify + disable writer

Una volta identificato il writer (Phase 2 o 3):

### 4a. Disable

```bash
# Caso 1: writer è un cron OpenClaw → disabilita la entry in OpenClaw config
# Caso 2: writer è un LaunchAgent → unload + add Disabled key
launchctl unload ~/Library/LaunchAgents/<label>.plist
plutil -insert Disabled -bool true -- ~/Library/LaunchAgents/<label>.plist

# Caso 3: writer è un Python script standalone → muovilo in ~/scripts/QUARANTINE/
mkdir -p ~/scripts/QUARANTINE
mv ~/scripts/<offender>.py ~/scripts/QUARANTINE/<offender>.py.disabled-2026-04-29

# Caso 4: writer è dentro repo Nuzantara → apri PR con fix immediato
cd /Users/nuzantara/Desktop/nuzantara
git checkout -b fix/plist-corruption-writer
# fix the redirect lethal pattern
```

### 4b. Verifica disabilitazione

```bash
# Re-arm canary (se non già attivo)
~/p0-3-recovery/canary_lite.sh &  # se esiste

# Aspetta 1 ora (o 2x cycle del sospetto), verifica nessuna nuova corruzione
ls -la ~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist | awk '{print $9, $6, $7, $8}' | head -10
```

## Phase 5 — Open PR with all the work

Branch `feat/p0-3-launchagents` è già su origin. Ora apri PR + merge:

```bash
cd /Users/nuzantara/Desktop/nuzantara
git fetch origin
git checkout feat/p0-3-launchagents
git rebase origin/main 2>&1 || git rebase --abort  # if conflict, resolve manually

# Add the writer-fix commit (if Phase 4 produced one)
# Then push
coord_push origin feat/p0-3-launchagents

gh pr create \
  --title "fix(p0-3): plist corruption recovery + writer identified + scripts" \
  --body "$(cat <<'EOF'
Resolves cicatrix STRUCTURAL 2026-04-29 P0-3 part 2 (writer identified + disabled).

## Summary

- 51 of 54 plist corrupted at 2026-04-29 15:09 by [WRITER NAME, identified in Phase 2/3]
- Writer disabled via [method from Phase 4a]
- All 53 plist reconstructed (Phase 1 of S4 wave1)
- Lint script `scripts/lint_launchagents.sh` enforces VADEMECUM §11
- Patch script `scripts/patch_launchagents.sh` auto-fixes violations with --dry-run|--apply
- 8 secrets leaked in world-readable plist; rotation list in ~/p0-3-recovery/secrets_to_rotate.txt
  (rotation pending — Antonello manual approval per secret class)

## Test plan
- [x] All 53 plist now plutil -lint OK
- [x] Daemon respawn verified (kill -9 cell.organism → respawned in 15s)
- [x] Writer identified: <NAME>
- [x] Writer disabled, canary 1h wait — no new corruption
- [x] lint script exits 0 on current state
- [ ] Secret rotation tracked separately (not in this PR)

## Cicatrix
STRUCTURAL 2026-04-29 P0-3 "51 LaunchAgent plist corrupted" → resolved (recovery + writer disabled).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"

gh pr merge --auto --squash
```

## Phase 6 — Secret rotation tracking

Crea task list dei 9 secret da rotare. NON ruotare automaticamente — Antonello deve approvare ogni rotation perché può rompere downstream services.

Salva in `~/p0-3-recovery/secrets_rotation_plan.md`:

```markdown
# Secrets rotation plan — post-plist-corruption 2026-04-29

| # | Secret | File location | Owner | Priority | Rotation procedure |
|---|---|---|---|---|---|
| 1 | TELEGRAM_BOT_TOKEN | dlq-autopilot, sentinel, cell.organism | @BotFather | High | /token in @BotFather, update plist + Fly secrets |
| 2 | GH_TOKEN | post-publish-poller | github.com | High | Settings → Personal access tokens → regenerate |
| 3 | FLY_API_TOKEN | cell.organism | fly.io | High | flyctl tokens create / revoke old |
| 4 | GOOGLE_API_KEY | cell.organism | console.cloud | Med | Restrict by IP first, then regenerate |
| 5 | CELL_DATABASE_URL | cell.organism | local PG | Low | rotate PG user password |
| 6 | FIREWORKS_API_KEY | post-publish-poller | fireworks.ai | Med | dashboard → API keys → regenerate |
| 7 | SCRAPER_API_KEY | post-publish-poller | internal | Low | grep service, rotate, redeploy |
| 8 | POST_PUBLISH_SECRET | post-publish-webhook | internal | Low | rotate, update endpoint |
| 9 | CLAUDE_CODE_OAUTH_TOKEN | balizero.intel.nightly | claude.ai | High | /logout claude CLI, re-auth |

## Status
- [ ] #1 TELEGRAM (rotation pending Antonello approval)
- [ ] #2 GH_TOKEN
... etc
```

Telegram alert per Antonello con link al file:
```bash
# Use existing hotfix-notify.sh
~/.claude/scripts/hotfix-notify.sh "🔐 Plist corruption secret rotation plan ready: ~/p0-3-recovery/secrets_rotation_plan.md (9 secrets, no auto-rotation, manual approval needed)"
```

## Phase 7 — Cicatrix update + close

Edit `.claude/rules/cicatrix-scars.md`:
- Find entry "51 LaunchAgent plist corrupted by unidentified writer 2026-04-29 15:09"
- Change to "✅ RESOLVED: ..." 
- Add "Patched: 2026-04-29 via PR #<num>, writer identified as <NAME>, disabled via <method>"

Save MOS:
```bash
~/.claude/scripts/mem save decision "P0-3 final closure 2026-04-29: writer identified as <NAME>, disabled, 51 plist recovered, lint+patch scripts merged in PR #<num>. Cicatrix STRUCTURAL P0-3 RESOLVED. Secret rotation plan in ~/p0-3-recovery/secrets_rotation_plan.md (9 secrets, manual rotation pending Antonello)." 9
```

## Phase 8 — Cleanup

```bash
# Worktree (only if PR merged)
cd /Users/nuzantara/Desktop/nuzantara
git worktree remove /Users/nuzantara/Desktop/nuzantara-wt/p0-3 2>/dev/null || true

# Recovery dir: keep until secret rotation done, then archive
# Don't delete ~/p0-3-recovery yet
```

## Reporting

```
[kakuro-S4-final DONE]
- Writer identified: <NAME>
- Method of corruption: <pattern>
- Disable mechanism: <how>
- PR #<num> merged
- Cicatrix STRUCTURAL P0-3 marked RESOLVED
- 9 secrets rotation plan ready, NOT yet rotated (Antonello manual)
- All 53 plist plutil -lint OK; daemon respawn verified
- fs_usage capture stopped; canary lite stopped
- Brainstorms in /tmp/kakuro-S4-final-brainstorms
- Recovery dir ~/p0-3-recovery preserved for forensics + secret rotation
```

## Failure modes

- **Phase 2 finds nothing + Phase 3 brainstorm inconclusive**: lascia la cattura `fs_usage` attiva indefinitivamente, schedula wakeup ogni 6h per ispezionare. Cicatrix resta UNRESOLVED. Apri solo PR con scripts (no writer disabled).
- **Phase 4 disabilita ma writer ricorre dopo**: la canary lite catturerà — re-investigate. Possibile multi-actor.
- **Phase 5 PR fail CI**: standard fix loop.
- **Secret rotation fail per uno specifico secret**: traccia in plan, non blocca.

## Autonomy boundary

L2 autonomous EXCEPT:
- Disable di un sistema critico (es. system_doctor.py) → escalate Telegram + wait Antonello go
- Secret rotation → SEMPRE manual, Antonello approva ogni rotation
- Modifica `~/.claude/settings.json` → escalate

In tutti gli altri scenari, procedi.
