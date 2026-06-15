#!/usr/bin/env bash
# harness_sota_cleanup.sh — TAC Mythos 2026-06-15: cura la "Sindrome da Discarica Architetturale"
# del harness Claude Code (~/.claude/). OPERATOR-RUN ONLY: tocca il control-plane (~/.claude/),
# quindi host_boundary.py lo blocca dentro l'agente by-design. Eseguilo TU, fuori dall'agente.
#
# Idempotente. Default = DRY-RUN (mostra, non tocca). Apply con: APPLY=1 bash harness_sota_cleanup.sh
# Ogni step è indipendente e ri-eseguibile. Backup-before-delete per i pezzi a rischio.
#
# Genesi: opus-mythos TAC del harness. Meta-pattern (Gemini 3.5 Flash trova → Opus falsifica →
# DeepSeek refuter depura): "COLLASSO SILENZIOSO PER DELEGA INVISIBILE DEL LIFECYCLE" — gli artefatti
# (permessi, memoria) crescono senza limite perché il TOOL e' append-by-default senza garbage-collector,
# e l'utente non POSSIEDE quel lifecycle → non lo cura → saturazione → troncamento silenzioso.
# La cura NON e' "pulisci di piu'" (STEP 1-4 = igiene), e' STEP 5: un guardrail che POSSIEDE il lifecycle
# al posto dell'utente. Firebreak (.bak/_archive/legacy) NON sono malattia → si spostano, non si curano.
# Famiglia cicatrix #1 (HOME-fork, dir-dup) + #4 (secret) + #2 (warning troncato = green-but-disarmed).
set -uo pipefail

CLAUDE_DIR="$HOME/.claude"
MEM_MAIN="$CLAUDE_DIR/projects/-Users-balizero-Desktop-nuzantara/memory"
MEM_DUP="$CLAUDE_DIR/projects/-Users-balizero/memory"
PROJ_SETTINGS="$HOME/Desktop/nuzantara/.claude/settings.local.json"
APPLY="${APPLY:-0}"
TS="$(date +%Y%m%d-%H%M%S)"
QUARANTINE="$CLAUDE_DIR/_sota-quarantine-$TS"

run() { if [ "$APPLY" = "1" ]; then echo "  APPLY> $*"; eval "$@"; else echo "  dry > $*"; fi; }
hdr() { echo ""; echo "=== $1 ==="; }

[ "$APPLY" = "1" ] && mkdir -p "$QUARANTINE" && echo "Quarantena: $QUARANTINE (recuperabile, NON git-deleted)"

# ── STEP 1: .bak graveyard → quarantine (NON delete: firebreak rispettati, ma fuori dalle dir attive) ──
# Gemini diceva "discarica"; DeepSeek refuter raffina: sono rollback intenzionali → li SPOSTO, non cancello.
hdr "STEP 1 — .bak fuori dalle dir attive (quarantine, non delete)"
for d in "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/skills" "$CLAUDE_DIR"; do
  find "$d" -maxdepth 1 -name '*.bak*' -type f 2>/dev/null | while read -r f; do
    run "mv '$f' '$QUARANTINE/'"
  done
done

# ── STEP 2: MEMORY.md sotto soglia → il fix P0 (tail troncato torna a caricarsi) ──
# Compatta solo l'INDICE (righe >200 char già linkate a file dedicati). Contenuto preservato nei .md.
hdr "STEP 2 — MEMORY.md trim sotto 24KB (sblocca il tail troncato)"
SZ=$(wc -c < "$MEM_MAIN/MEMORY.md" 2>/dev/null || echo 0)
echo "  MEMORY.md attuale: $SZ byte (limite hardcoded 25600, target <24000)"
echo "  → 14 righe-indice >400 char vanno COMPRESSE a 1-liner (titolo+hook+link)."
echo "  → contenuto già nei file .md linkati: nessuna perdita. Editane a mano o usa il sed-helper sotto."
echo "  AZIONE MANUALE consigliata (l'indice è giudizio editoriale, non meccanico):"
echo "    \$EDITOR $MEM_MAIN/MEMORY.md  # comprimi L12,L15,L23,L32,L49,L53,L63 + tail orfano"
echo "  Verifica post-edit: wc -c $MEM_MAIN/MEMORY.md  (deve essere <24000)"

# ── STEP 3: dir memory DUPLICATA → questo è P0 vero (è nel path-resolution, non solo storage) ──
# host_boundary.py risolve verso -Users-balizero (il clone), non verso il main. Famiglia #1 HOME-fork.
hdr "STEP 3 — dir memory duplicata (P0: nel path-resolution, non solo storage)"
if [ -d "$MEM_DUP" ] && [ ! -L "$MEM_DUP" ]; then
  echo "  TROVATA dir clone fisica: $MEM_DUP (498 file, md5 MEMORY.md identico al main, NON symlink)"
  echo "  RISCHIO: edit divergenti tra le due copie. SCELTA OPERATORE:"
  echo "    (a) symlink-ize: rm -rf clone && ln -s MAIN clone  (1 sola SSOT)"
  echo "    (b) investiga il sync daemon che la crea (memory-sync-bidirectional) → fixa il target"
  echo "  NON auto-eseguo: serve capire quale daemon la scrive prima di romperlo (Legge degradation)."
  M_MAIN=$(md5 -q "$MEM_MAIN/MEMORY.md" 2>/dev/null)
  M_DUP=$(md5 -q "$MEM_DUP/MEMORY.md" 2>/dev/null)
  echo "  md5 main=$M_MAIN dup=$M_DUP  $([ "$M_MAIN" = "$M_DUP" ] && echo IDENTICI || echo DIVERGED!)"
else
  echo "  OK: nessun clone fisico (o è già symlink)."
fi

# ── STEP 4: settings.local.json — secret-purge + permission consolidation (P0 famiglia #4) ──
hdr "STEP 4 — settings.local.json: PGPASSWORD cleartext + 909 allow"
if [ -f "$PROJ_SETTINGS" ]; then
  N_PW=$(grep -c "PGPASSWORD" "$PROJ_SETTINGS" 2>/dev/null || echo 0)
  N_ALLOW=$(python3 -c "import json;print(len(json.load(open('$PROJ_SETTINGS')).get('permissions',{}).get('allow',[])))" 2>/dev/null || echo '?')
  echo "  PGPASSWORD cleartext: $N_PW occorrenze  |  allow entries: $N_ALLOW (0 deny, 0 ask)"
  echo "  P0: rimuovi le entry con PGPASSWORD (il password va in env/Keychain, MAI nel config)."
  echo "  P1: consolida i ~750 Bash(...) literali in pattern (es Bash(psql:*), Bash(git*:*))."
  echo "  Helper (DRY): entry con secret da rimuovere:"
  grep -n "PGPASSWORD" "$PROJ_SETTINGS" 2>/dev/null | sed -E 's/(PGPASSWORD=.?")[^"]+/\1****/g' | head
  echo "  ⚠️ Se queste password sono state world-readable storicamente → RUOTALE (famiglia #4)."
else
  echo "  settings.local.json non trovato a $PROJ_SETTINGS"
fi

# ── STEP 5: LA CURA STRUTTURALE — il guardrail che POSSIEDE il lifecycle (uccide la famiglia) ──
# Installa un hook SessionStart che, a ogni avvio, MISURA la saturazione e AVVISA prima del collasso.
# E' il garbage-collector che il tool non dà: trasferisce la proprietà del lifecycle dall'utente
# (che non la cura) al harness (che la controlla a ogni sessione). Idempotente.
hdr "STEP 5 — installa harness_lifecycle_guard.py (la cura del meta-pattern)"
GUARD="$CLAUDE_DIR/hooks/harness_lifecycle_guard.py"
echo "  Genera: $GUARD (SessionStart hook, fail-open, soft-warn a 23KB / hard a 25KB)"
if [ "$APPLY" = "1" ]; then
  cat > "$GUARD" << 'GUARDEOF'
#!/usr/bin/env python3
"""harness_lifecycle_guard.py — SessionStart hook. Cura "Delega Invisibile del Lifecycle".
Misura la saturazione degli artefatti append-by-default del harness e AVVISA prima del
troncamento silenzioso. Fail-OPEN (mai blocca una sessione per un errore proprio). Genesi:
opus-mythos TAC harness 2026-06-15."""
import json, os, sys, glob

HOME = os.path.expanduser("~")
MEM = f"{HOME}/.claude/projects/-Users-balizero-Desktop-nuzantara/memory/MEMORY.md"
PROJ_SETTINGS = f"{HOME}/Desktop/nuzantara/.claude/settings.local.json"
MEM_HARD = 25600      # limite #40614: oltre = troncamento silenzioso
MEM_SOFT = 23000      # avviso preventivo
ALLOW_SOFT = 600      # permessi: oltre = discarica

def main():
    warns = []
    try:
        sz = os.path.getsize(MEM) if os.path.exists(MEM) else 0
        if sz >= MEM_HARD:
            warns.append(f"🔴 MEMORY.md = {sz}B ≥ {MEM_HARD} (#40614): IL TAIL E' TRONCATO. Comprimi l'indice ORA.")
        elif sz >= MEM_SOFT:
            warns.append(f"🟡 MEMORY.md = {sz}B (soglia {MEM_HARD}). Avvicini il troncamento — compatta l'indice.")
    except Exception:
        pass
    try:
        if os.path.exists(PROJ_SETTINGS):
            d = json.load(open(PROJ_SETTINGS))
            allow = d.get("permissions", {}).get("allow", [])
            if len(allow) >= ALLOW_SOFT:
                warns.append(f"🟡 settings.local.json = {len(allow)} allow (discarica): consolida in pattern.")
            sec = [a for a in allow if isinstance(a, str) and ("PGPASSWORD" in a or "PASSWORD=" in a)]
            if sec:
                warns.append(f"🔴 {len(sec)} permessi con SECRET in cleartext (famiglia #4): rimuovi+ruota.")
    except Exception:
        pass
    if warns:
        print("## ⚕️ Harness lifecycle guard\n" + "\n".join(f"- {w}" for w in warns))
    sys.exit(0)  # fail-open SEMPRE

if __name__ == "__main__":
    main()
GUARDEOF
  chmod 0755 "$GUARD"
  echo "  APPLY> creato $GUARD"
  echo "  ⚠️ WIRING MANUALE: aggiungi a ~/.claude/settings.json sotto hooks.SessionStart:"
  echo '       {"type":"command","command":"python3 ~/.claude/hooks/harness_lifecycle_guard.py"}'
  echo "  (il settings.json e' host-boundary: editalo TU. host_boundary.py NON tocca questo hook nuovo.)"
else
  echo "  dry > (APPLY=1 per generare l'hook). Poi wiring manuale in settings.json SessionStart."
fi

hdr "FATTO (APPLY=$APPLY)"
[ "$APPLY" != "1" ] && echo "Questo era un DRY-RUN. Per applicare gli step automatici (1+5): APPLY=1 bash $0"
echo "Step 2/3/4 = giudizio operatore (vedi sopra). Step 5 = la cura strutturale. §Solo-operatore della TAC."
