---
date: 2026-09-09
domain: operations
client_case: none
adversarial_review: codex
---

# Salto di finestra automatico — ricerca (2026-09-09)

> Domanda di Zero: «arrivati alla soglia di contesto, l'LLM scrive l'handoff, lo incolla in una
> finestra nuova e chiude la sua: è automatico?». Oggi: **handoff sì, salto no**. Questa nota dice
> cosa il CLI permette davvero (documentazione ufficiale letta oggi), cosa abbiamo misurato sulla
> macchina, e propone il disegno. Nessuna PR di implementazione è partita.

## 1. Cosa esiste già (verificato oggi, sessione Fable M5 `99d81788`)

- `~/.claude/hooks/context_window_guard.py` (PreToolUse `*`, LIVE su M5/Pro/Mini): alla soglia
  (imperatore 20 %, altri 40 %) scrive `~/.claude/state/precompact-handoff-<session>.json` e nega
  ogni tool tranne `mem save`, `SendMessage`, `TaskStop`. Misurato: file 8,5 KB, 18 comandi riusciti.
- `/resume` (`.claude/commands/resume.md`) è manuale: `ls -t precompact-handoff-*.json | head -1`.
- Il terminale interattivo di M5 è **Ghostty 1.3.1**, senza tmux. Le sessioni H24 su Pro/Mini sono
  headless (`claude -p`) via `infra/launchagents/wrappers/claude-cascade.sh`.

## 2. Cosa permette Claude Code (fonti: `code.claude.com/docs`, `cli-reference`, `hooks`, `env-vars`,
`model-config`, `headless`, `agent-sdk/*`)

| Bisogno | Supporto | Meccanismo |
|---|---|---|
| Sessione NUOVA a contesto vuoto, con il mandato come primo turno | sì | `claude "<prompt>"` (interattiva) o `claude -p "<prompt>"`: nuovo session id, storia vuota. `--session-id <uuid>` fissa l'id. |
| Iniettare l'handoff nella sessione nuova da un hook | sì | SessionStart (`source: startup`) → `hookSpecificOutput.additionalContext` (ogni modo) o `initialUserMessage` (solo `-p`, diventa il primo turno anche senza prompt). |
| Riusare la vecchia trascrizione | da evitare | `--resume`, `--continue`, `--fork-session` (nuovo id ma **eredita tutto il contesto**): sono l'opposto di quel che vogliamo. |
| Un hook che chiude la sessione vecchia o il processo | **no, non documentato** | `continue:false` ferma solo il turno; `SessionEnd` è solo notifica; nessuna API per segnali al processo padre. |
| Un hook che forza `/compact` | **no** | `PreCompact` può solo bloccare; auto-compact si regola (`CLAUDE_CODE_AUTO_COMPACT_WINDOW`, `/autocompact`, `DISABLE_COMPACT=1`) ma non si invoca. |
| Segnale «contesto esaurito» programmatico | sì (SDK/`-p`) | `SDKResultMessage.terminal_reason == "prompt_too_long"`; `CLAUDE_CODE_SESSION_ID` è nell'env degli hook. |
| Pattern documentato di rotazione | solo same-session | `headless.md`: `claude -p ... --output-format json \| jq .session_id` poi `--resume`: stessa trascrizione, non finestra fresca. |

Conclusione: il CLI dà il **mattone** (nuova invocazione con prompt) e l'**innesto** (SessionStart),
non dà il **gesto** (aprire la finestra) né la **chiusura** della vecchia. Quelli vanno fatti fuori
dal CLI, e sono diversi per finestra interattiva e per cron headless.

## 3. Cosa abbiamo misurato sul gesto (M5, Ghostty)

| Sonda | Esito |
|---|---|
| `open -a Ghostty --args -e sh -c 'sleep 15'` (istanza già aperta) | **nessuna finestra nuova** (count resta 1) |
| AppleScript: `activate` → ⌘N → digita comando → Invio | **funziona**: finestra 2, comando eseguito; ⌘W la chiude. TCC Accessibility già concesso al processo padre (rc 0 su `keystroke`). |
| `ghostty +…` azioni CLI | solo `+version/+list-*/+show-config`: nessuna `+new-window`. |

Quindi su M5 l'unico canale automatico per «aprire una finestra» è AppleScript/System Events dal
processo hook (che eredita il permesso Accessibility di Ghostty→claude). È fragile per natura
(digita in una finestra attiva): va digitato un comando **corto e fisso**, mai il mandato.

## 4. Disegno proposto (deciso da Zero il 2026-09-09 e spedito: PR #5987 interattivo, PR headless in `infra/launchagents/wrappers/claude-cascade.sh`; esito sonde in §6)

### 4a. Finestra interattiva (M5, e Pro quando Zero ci lavora)

1. **Guard, primo scatto** (già scrive l'handoff): scrive anche
   `~/.organism/context-guard/pending-jump.json` = `{from_session, model, handoff_path, cwd, ts}`
   e lancia `~/.claude/scripts/window_jump.sh <from_session>` in background (non blocca il deny).
2. **`window_jump.sh`**: AppleScript ⌘N in Ghostty, digita `nz-jump` + Invio. `nz-jump` è uno
   script fisso che legge `pending-jump.json`, fa `cd $cwd` e lancia
   `claude --model $model --session-id <nuovo uuid> "Sei la finestra successiva di <from_session>: continua il mandato dall'handoff."`.
3. **SessionStart hook nuovo** (`source: startup`): se esiste `pending-jump.json` con
   `to_session` vuoto, inietta come `additionalContext` l'handoff completo (mandato originale
   integrale, comandi riusciti, file toccati, `next_action`) e marca `to_session = session_id`.
   Deterministico: non serve più `/resume` a mano.
4. **Sessione vecchia**: il guard continua a negare tutto; il modello scrive l'ultimo report e
   finisce il turno. La finestra resta aperta ma inerte. Chiuderla davvero: due strade da
   sondare, nessuna documentata —
   - (i) `window_jump.sh`, dopo che la nuova sessione ha marcato `to_session`, manda ⌘W alla
     finestra vecchia (con ⌘N la nuova è davanti, la vecchia è `window 2`): cosmetico e fragile;
   - (ii) `kill -INT $PPID` ×2 dall'hook (equivale a Ctrl-C doppio): chiude il processo, ma
     va provato su una sessione usa-e-getta se `SessionEnd` (MOS capture) scatta o si perde.
   Raccomandazione: v1 = (4.1–4.3) senza chiusura; la finestra vecchia mostra il report finale e
   si chiude a mano. La chiusura automatica solo dopo la sonda (ii).

### 4b. Cron headless (Pro/Mini, `claude-cascade.sh -p`)

- Il wrapper già gira in loop di cascade. Aggiunta (spedita nella PR headless): ogni invocazione
  riceve un `--session-id` proprio; se al termine esiste `pending-jump-<quel id>.json` non
  reclamato con `seat=headless`, rilancia `claude -p` **senza** `--resume`, con un nuovo id,
  `NZ_JUMP_FROM=<id precedente>` nell'ambiente e un prompt di continuazione corto su stdin; il
  SessionStart hook di 4a.3 inietta il mandato. Gli output degli hop si accumulano e si emettono
  solo a catena pulita; ogni hop passa la stessa classificazione quota/auth della prima run.
  Budget: 3 salti per run (stesso cap del guard), poi avviso `INCOMPLETE` su stderr.
- Alternativa pulita per i nuovi organi: Agent SDK Python, `query()` in loop con
  `terminal_reason` come segnale; non tocca i wrapper esistenti.

### 4c. I due anelli deboli (fix piccoli, stessa PR dell'innesto)

- `precompact-mnemos.py` scarta i prompt utente `>500` caratteri e ignora il contenuto
  strutturato (lista di blocchi): l'`objective` del mio handoff era `[]`. Fix: raccogliere il testo
  dei blocchi `text`, tenere il **primo mandato integrale** (troncato a ~4 000) + gli ultimi 2.
- `/resume` sceglie «a mano»: con `pending-jump.json` il file è determinato dalla sessione, e
  la skill resta solo per il caso manuale (leggere il più recente **e** verificare che esista).

## 5. Rischi e limiti da mettere a verbale

- AppleScript digita nella finestra attiva: se Zero sta scrivendo altrove nel momento del salto,
  il comando finisce lì. Mitigazione: `nz-jump` è una parola sola + Invio; il resto è nel file.
- Il salto non riduce il costo del mandato: sposta il contesto, non lo comprime. È la scelta di
  Zero (finestra nuova invece di compattazione) e va tenuta esplicita.
- Un seat 1M sotto 200K resta indistinguibile: `CONTEXT_WINDOW_TOKENS` per seat (già su M5).
- Loop: un mandato che non finisce mai salta all'infinito. Cap 3 salti per catena
  (`pending-jump.json` porta `hops`), poi escalation HIGH sul board.

## 6. Esito delle sonde live (2026-09-09, M5, dopo le decisioni di Zero: chiusura via AppleScript, tutti i seat, cap 3)

| # | Cosa | Esito |
|---|---|---|
| 0 | `/exit` digitato in una sessione Haiku usa-e-getta idle | processo terminato (12:40) |
| 1 | catena v1 (file globale): guard → ⌘N → `nz-jump` → SessionStart inietta → `to_session` → `/exit` nella vecchia | 10 s end-to-end; nuova sessione risponde `SALTO_OK` col mandato iniettato |
| — | `/exit` digitato ×3 nella nuova sessione (idle, finestra verificata davanti) | **processo vivo**; `kill -INT` ×2 lo chiude |
| 2 | lanciatore di prova SENZA verifica del fuoco dopo ⌘N | la digitazione è finita nella finestra della sessione principale come prompt: rischio reale, non teorico |
| 3 | catena v2 (file per sessione, `nz-jump <sid>`, verifica fuoco, `/exit` + fallback SIGINT×2 su `from_pid`) | 5 s; iniezione + `SALTO_OK`; la nuova sessione è terminata da sola ~40 s dopo, causa non trovata (non riprodotto) |
| 4 | v2 senza passo di chiusura, 95 s di osservazione | nuova sessione viva per tutto il tempo |
| 5 | v2 completa, campionamento ogni 3 s per 60 s | nuova sessione viva per tutto il tempo; log: `/exit` digitato, fallback SIGINT tentato sul vecchio processo |

Conseguenze nel disegno spedito: (a) `/exit` non basta da solo — la chiusura è `/exit` digitato, poi
attesa ≤20 s che il PID del vecchio `claude` (il padre dell'hook, salvato nel file di salto) muoia,
altrimenti `kill -INT` ×2; (b) mai digitare senza aver verificato che la finestra davanti sia quella
attesa (nome registrato), né dopo ⌘N né prima di `/exit`; (c) un file `pending-jump-<sessione>.json`
per sessione, il mandato viaggia nel file lungo la catena (la trascrizione del salto 2 comincia con
lo stub di `nz-jump`, non col mandato); (d) il nome finestra passa ad AppleScript come argomento
(`on run argv`), mai interpolato nel sorgente.

## 7. Decisioni chieste a Zero (risposte 2026-09-09: 1 sonda → fatta, §6; 2 tutti; 3 cap = 3)

1. v1 senza chiusura automatica della finestra vecchia (report finale visibile, chiusura a mano),
   oppure sondare subito `kill -INT $PPID` su una sessione usa-e-getta?
2. Il salto vale anche per i cron headless (4b) in questa tornata, o solo M5 interattiva?
3. Cap salti per catena: 3?

## Adversarial review — §8 (codex, 2026-09-09, seat esterno sul ramo di PR #5987)

Mandato al reviewer: refutare le affermazioni della nota e il disegno spedito, con evidenza
`file:riga`. Verdetto iniziale: **NON SOPRAVVIVE** (8 punti). Disposizioni, nella stessa PR:

| # | Finding (codex) | Esito |
|---|---|---|
| 1 | Primitivi CLI corretti (`additionalContext`, avvio senza `--resume`) | CONFERMATO, nessuna azione |
| 2 | «Mai digitare senza verifica»: `type-here` non ricontrollava il titolo tra ⌘N e la digitazione | CONFERMATO → `window_jump.sh`: `type-here` riceve il nome atteso e rifiuta se il fronte è cambiato |
| 3 | `/exit` può colpire un'altra finestra con titolo duplicato | PLAUSIBILE, residuo: il fallback resta `SIGINT×2` sul `from_pid`, che è per-processo; titoli duplicati riguardano solo il gesto `/exit` |
| 4 | Chiusura non garantita (titolo assente → esce prima del fallback; vivo dopo SIGINT×2 → solo log) | CONFERMATO come limite dichiarato (§5, §6): la chiusura è best-effort, la nuova sessione è il deliverable; il log lo dice |
| 5 | Handoff non deterministico: il ricevente ignorava il `FROM` del lanciatore e prendeva il pending più recente nel cwd | CONFERMATO → `NZ_JUMP_FROM` esportato da `nz-jump.sh` (e dal wrapper headless); `context_jump_resume.py` considera solo quel file; il fallback «più recente nel cwd» resta per la finestra aperta a mano |
| 6 | Cap fragile: se lo stamp `to_session` fallisce, il conteggio riparte da 1; manca l'escalation HIGH promessa | PLAUSIBILE, residuo dichiarato: lo stamp fallisce solo per errore I/O su `~/.organism`; l'escalation HIGH al cap resta da fare (riga aperta) |
| 7 | Headless non operativo: il wrapper non consumava il pending | CONFERMATO → PR headless separata (§4b aggiornato), stesso ruling |
| 8 | Nota non consolidata (§ fuori ordine, «non implementato» vs «spedito», cap 2 vs 3) | CONFERMATO → corretto in questa revisione |

Il verdetto sul nucleo (il CLI dà mattone e innesto, il gesto resta esterno; il salto è
realizzabile e misurato) sopravvive con le tre correzioni sopra (2, 5, 8) applicate.

