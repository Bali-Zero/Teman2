---
name: window-jump
description: "Il salto di finestra quando scatta il context guard: catena, verifica, recupero manuale in 2 comandi, kill switch. USA quando una sessione è al guard (ogni tool negato), quando jump.log dice «nothing typed», o quando un compagno chiede «scrivi nz-jump nella finestra nuova»."
---

# Window jump — la sessione che finisce il contesto ne apre un'altra

Ruling Zero 2026-09-09: «arrivati al contesto, scrivi l'handoff, incollalo in una finestra
nuova e chiudi la tua» — **automatico, senza umano**. Il CLI non sa aprire una finestra né
chiudere una sessione da dentro un hook, quindi il gesto si fa da fuori (AppleScript +
Ghostty, solo macOS). Dettaglio storico:
`research/operations/2026-09-09-window-jump-automatic-handoff-it.md`.

## La catena (7 anelli, in ordine)

1. **`context_window_guard.py`** (PreToolUse) supera la soglia di ruolo → nega ogni tool.
2. Scrive `~/.claude/state/precompact-handoff-<sid>.json` (handoff) e
   `~/.organism/context-guard/pending-jump-<sid>.json` (mandato originale, `from_pid`,
   `model`, `cwd`, `hops`, `seat`, `gesture_attempts`, `to_session: null`).
3. Se il seat è Ghostty su macOS lancia **`window_jump.sh <sid>`** staccato (mai attende).
4. **Il gesto**, in **due rotte**. Prima di tutto lo **snapshot** dei nomi finestra (prima
   di qualsiasi gesto: è la regola di entrambe le rotte).
   - **NATIVE** (default, Ghostty ≥ 1.3 con `macos-applescript = true`): il dizionario
     AppleScript di Ghostty crea la finestra e la indirizza per **id** (`new window`,
     `input text`, `send key`, `close window`) — non si digita mai «in quello che sta
     davanti», che è il modo in cui il gesto morì due volte il 2026-09-09 (Ghostty non era
     l'app attiva, System Events cieco). L'id però è solo una maniglia: **il nome** della
     finestra restituita viene confrontato con lo snapshot **prima** di digitare.
   - **KEYSTROKE** (fallback, Ghostty < 1.3 o dizionario chiuso): System Events, ⌘N →
     **poll ogni 0,3s fino a 8s** finché compare un nome che **non era nello snapshot** →
     AXRaise su QUELLA finestra per nome → digita.
     In entrambe: solo un nome **assente dallo snapshot** autorizza la digitazione di
     `nz-jump <sid>` + Invio. Se lo snapshot è illeggibile (Accessibility negata) ogni nome
     sembrerebbe nuovo, e se cambia solo la finestra frontale è un riordino, non una nascita.
     In entrambi i casi: **niente digitato**.
5. **`nz-jump`** (`~/.claude/scripts/nz-jump`) entra nel `cwd` vecchio e lancia un `claude`
   **fresco** — mai `--resume/--continue/--fork-session`, che riporterebbero il contesto.
6. **`context_jump_resume.py`** (SessionStart della nuova finestra) inietta mandato +
   handoff come `additionalContext` e timbra `to_session` nel file pending — **solo** nella
   finestra aperta PER quel salto: `nz-jump` (e l'hop del wrapper cascade) esportano
   `NZ_JUMP_FROM=<sid>`, e il hook legge solo quel file. Un `claude` aperto a mano, senza
   `NZ_JUMP_FROM`, non è mai una continuazione: resta muto anche con un pending fresco nello
   stesso cwd (fino al 2026-09-09 pescava «il più fresco non reclamato» e per 15 minuti dopo
   ogni guard una finestra di Zero partiva da sola sul mandato vecchio).
7. `window_jump.sh` vede `to_session` (poll 1s, max `JUMP_WAIT_S`) e chiude la vecchia:
   `/exit` nel terminale vecchio **per id** (rotta native) o rialzando la finestra per nome
   (rotta keystroke); se il PID sopravvive, `SIGINT` ×2 su `from_pid`; e solo quando quel
   claude è morto, `close window` sull'id vecchio — solo native, la rotta keystroke non può
   chiudere in sicurezza.

Misurato 2026-09-09: **~6s** dal keystroke a `to_session`. Cap: 3 hop per catena
(`JUMP_MAX_HOPS`), 3 gesti per sessione (`gesture_attempts`, il guard ritenta da solo e
lo dice: «gesto ritentato (n/3)»).

## Verificare (tre comandi, sempre questi)

```bash
tail -20 ~/.organism/context-guard/jump.log
cat ~/.organism/context-guard/pending-jump-<sid>.json   # to_session != null = atterrato
osascript -e 'tell application "Ghostty" to get name of every window'   # lista della rotta native
osascript -e 'tell application "System Events" to tell process "ghostty" to get name of every window'
```

`jump.log` è l'unica verità sull'esito: il guard stampa «TENTATO», non «avviato», proprio
perché non aspetta. Righe che contano: `windows before (native|keys): [...]` /
`keys: windows after: [...]` (la diagnosi di un miss, con la rotta che l'ha prodotta),
`native: … name='<nome>' (absent from the snapshot), 'nz-jump <sid>' sent` oppure
`keys: new window '<nome>' opened, 'nz-jump <sid>' typed` (atterrato),
`nothing typed` (mancato — è la riga che fa scattare il ritento, ma solo se il processo
del gesto precedente è morto: un osascript appeso non viene raddoppiato).

## Recupero manuale — 2 comandi (usati davvero il 2026-09-09)

Serve quando i 3 gesti sono esauriti o Accessibility ha negato i keystroke. **La sessione
al guard non può eseguirli**: può solo mandare messaggi. Li esegue un agente vivo o Zero.

```bash
SID=<from_session>; AS=~/.organism/context-guard/window_jump.applescript
osascript "$AS" raise-type "~/nuzantara" "nz-jump $SID"     # nome ESATTO della finestra nuova
```

Se il dizionario di Ghostty è aperto c'è anche la via per **id**, che non dipende da chi sta
davanti (`AS_N=~/.organism/context-guard/window_jump_native.applescript`):
`osascript -e 'tell application "Ghostty" to get id of every window'` per l'id, poi
`osascript "$AS_N" type-into <id> "nz-jump $SID"`.

Poi, **solo dopo** che `to_session` è timbrato nel file pending, si chiude la vecchia:

```bash
osascript "$AS" raise-type "◑ Interactive" "/exit"          # nome ESATTO della finestra vecchia
```

I nomi finestra **collidono**: Claude Code mette come titolo il titolo di sessione, quindi
due sessioni sono entrambe «Interactive» e cambia solo il glifo (`◑` vs `✳`). Copia il nome
dalla lista dell'AppleScript, carattere per carattere: digitare nella finestra sbagliata è
peggio che non digitare. Se `raise-type` dà «front window changed» **non ritentare alla
cieca** — rileggi la lista finestre e riporta cosa c'era davanti.

## Regola: chi è al guard delega

Una sessione oltre soglia ha ogni tool negato tranne `mem save`, la scrittura del proprio
handoff e `SendMessage`/`TaskStop`. Quindi: **manda il comando a un agente vivo** (o a Zero)
e non provare a curarti da sola con i tool — non ne hai. L'unica via diretta è la prompt bar
con `!` (bypassa i tool-hook), che però è un gesto umano.

## Kill switch e variabili

| Variabile                                                        | Effetto                                                      |
| ---------------------------------------------------------------- | ------------------------------------------------------------ |
| `CONTEXT_JUMP_OFF=1`                                             | niente file, niente gesto (la **negazione** del guard resta) |
| `CONTEXT_JUMP_NO_SPAWN=1`                                        | file sì, gesto no — usalo in ogni test                       |
| `CONTEXT_GUARD_OFF=1`                                            | disarma il guard stesso (ultima risorsa)                     |
| `JUMP_WAIT_S` (120) · `JUMP_POLL_MAX_S` (8) · `EXIT_WAIT_S` (20) | attese del gesto                                             |

## Installare / provare

```bash
bash infra/claude-hooks/install_window_jump.sh --check  # cosa cambierebbe, non scrive
bash infra/claude-hooks/install_window_jump.sh          # le 4 coppie in ~/.claude, 0700
bash infra/claude-hooks/test_window_jump_gesture.sh     # osascript shimmato, nessuna finestra vera
CONTEXT_JUMP_NO_SPAWN=1 python3 -m pytest infra/claude-hooks/test_context_window_jump.py -q
```

**Mai** aprire una finestra Ghostty vera in un test: lo schermo di Zero è quello vivo.
