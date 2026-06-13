# SPEC — Phase-Aware Guardrails (pensa-libero / agisci-blindato)

> **Stato:** DRAFT — da sottomettere al panel 4-LLM (CLAUDE.md §6) prima di toccare un hook.
> **Autore:** Opus 4.8 (M5) · **Data:** 2026-06-13 · **Branch:** worktree `docs-system-shapes-agent-4llm`
> **Origine:** decisione Antonello — "in pianificazione/architettura i modelli liberi (ma non incasinano la codebase reale); in implementazione si tiene così com'è." Discende dal verdetto `2026-06-13-system-shapes-the-agent-4llm.md`: lo scaffold è un *capability equalizer* che comprime il tetto esplorativo del frontier. Questa spec recupera quel tetto SOLO nella fase dove non c'è danno reale.

---

## 0. Tesi in una riga

Un agente frontier rende al massimo quando **pensa libero** (esplora, ragiona, prova vicoli ciechi) e **agisce blindato** (non scrive sul main, non distrugge dati, non perde PII). Oggi i guardrail L1 trattano le due fasi identiche → tassano anche il pensiero. Questa spec rende i guardrail **consapevoli della fase**: si fanno da parte in plan, restano duri in implementazione — **automaticamente**, senza toggle manuale.

## 1. Il segnale di fase (verificato su disco — NON assunto)

| Fatto | Evidenza |
|---|---|
| Claude Code locale = `2.1.177` | `claude --version` |
| Il payload PreToolUse porta il modo permessi | docs ufficiale: campo `permission_mode` ∈ {`default`,`plan`,`acceptEdits`,`auto`,`dontAsk`,`bypassPermissions`} |
| Nei transcript locali il campo è **camelCase `permissionMode`**, top-level, con valore `plan` osservato (12×) | grep su `~/.claude/projects/-Users-balizero-Desktop-nuzantara/*.jsonl` |
| **NON provato** direttamente sullo stdin del PreToolUse (settings non hot-reload a metà sessione) | subagent probe non scattato → vedi §6 gate-di-validazione |
| `ExitPlanMode`/`EnterPlanMode` NON sono segnali affidabili (rari/non-osservabili come tool_use) | 3 soli `tool_use` ExitPlanMode in tutto il progetto; `type:"mode"` è output-style (`normal`), non plan |
| Nessuno dei 5 gate legge oggi `permission_mode` | grep sui hook — leggono solo `tool_name`/`tool_input`/`cwd`/`transcript_path` |

**Conseguenza:** il segnale primario è `permissionMode == "plan"`, letto con doppia grafia + fail-safe.

## 2. Lo switch — automatico e naturale

L'utente entra in plan-mode con **Shift+Tab** (gesto nativo che già fa quando pianifica). Quel gesto setta `permissionMode = "plan"` nel payload. I gate "verdi" leggono il campo e si auto-disarmano. Uscire da plan (parte a implementare) → il campo torna `default`/`acceptEdits` → i gate tornano duri. **Zero variabili d'ambiente da ricordare, zero comandi.**

Helper condiviso (`~/.claude/hooks/_phase.py`, nuovo):

```python
import os, json
def is_plan_phase(payload: dict) -> bool:
    """True SOLO se la sessione è in plan-mode. Fail-safe: campo assente → False (guardrail ON)."""
    mode = payload.get("permissionMode") or payload.get("permission_mode") or ""
    if mode == "plan":
        return True
    # escape manuale esplicito, per fasi-plan fuori dalla UI plan-mode (es. brainstorm in chat)
    if os.environ.get("NUZ_PHASE") == "plan":
        return True
    return False
```

I gate 🟢 aggiungono in cima, dopo il parse del payload:
```python
from _phase import is_plan_phase
if is_plan_phase(payload):
    sys.exit(0)   # plan: l'hook si fa da parte
```
I gate 🔴 **non importano `_phase`** — restano identici a oggi.

## 3. Cosa si rilassa in PLAN — e perché è sicuro (🟢)

In plan-mode l'agente è read-only by design (non scrive comunque); rilassare questi gate non aggiunge rischio, toglie solo attrito al pensiero.

| Gate | Blocca oggi | In plan | Razionale |
|---|---|---|---|
| `orchestrate_gate.py` | exit 2: vieta Bash/Read/Grep diretti dopo 300 righe finché non dispatci un subagent | **off** | forzare la delega durante l'esplorazione amputa le "manovre laterali" del frontier (critica DeepSeek, verdetto §5). Esplorare a mano È il lavoro del cervello in fase plan |
| `dispatch_nudge.py` | nudge a delegare dopo 500 righe | **off** | idem — l'esplorazione profonda mono-agente è legittima in plan |
| `stadio_zero_nudge.py` | nudge a fare STADIO-0 prima di editare | **off** | in plan SEI nello studio; il nudge è ridondante |
| `worktree_isolation.py` — SOLO su scratch worktree | blocca `git checkout/stash/reset/rebase` anche su branch-esperimento | **rilassa su scratch** | in plan vuoi creare/buttare branch-esperimento liberamente. **NB: la protezione sul MAIN checkout resta — vedi §4** |

## 4. Cosa resta DURO sempre — anche in plan (🔴)

Questi non toccano la libertà di ragionare: toccano l'integrità del mondo reale. Invariati in entrambe le fasi.

| Gate | Protegge | Perché immutabile |
|---|---|---|
| `worktree_file_write_check.py` | vieta Edit/Write nel **main checkout** `~/Desktop/nuzantara` | "pensare libero" ≠ "scrivere sul reale". Plan è read-only; questa è la cintura ridondante |
| `worktree_isolation.py` — parte git-distruttivi su **MAIN** | `git reset/merge/rebase/pull/commit -a` sul main | cancella lavoro di sessioni sibling (W59/W62), danno irreversibile cross-agente |
| `guardrails-static.py` | pattern MCP distruttivi (`drop_*`,`delete_*`,`truncate_*`,`wipe_*`) | distruggono dati clienti; nessuna ragione di pianificazione li richiede |
| PII boundary (SYMBIOSIS Law 2) | nessun dato cliente verso cloud/paid API | sovranità (UU PDP); un brief con un KTP dentro è violazione anche "mentre pianifichi" |
| `stop_verify.py` | Stop con git dirty senza intent marker | protegge da perdere lavoro non committato |
| `m5_block_heavy_brew.py` | install pesanti su M5 thin | operativo, ortogonale alle fasi |

## 5. Zona grigia

- `seam_verify.py`: già advisory (Stop, non-bloccante) → invariato.
- 4-LLM panel su spec (CLAUDE.md §6): **tieni in plan** — è lo strumento della fase plan, non un freno.
- Preflight SDD (3+ file → federation): rilassa in plan, tieni in implement.

## 6. Gate di validazione — DA CHIUDERE PRIMA DEL MERGE (anti-W64)

Il claim "`permissionMode` arriva sullo stdin del PreToolUse" è **indiziato, non provato**. Prima di disarmare QUALSIASI gate:

1. In sessione interattiva owner: registra un probe `/tmp/nuz_payload_probe.py` come `PreToolUse` matcher in `~/.claude/settings.json`, `/hooks` reload, entra in plan (Shift+Tab), esegui UN Bash, leggi `/tmp/nuz_payload_capture.jsonl`.
2. Conferma: il campo è presente sullo stdin? Con quale grafia (`permissionMode` vs `permission_mode`)? Quale valore in plan vs normale?
3. Solo se confermato → ship. Se il campo NON arriva sullo stdin → lo switch ricade sul solo `NUZ_PHASE=plan` manuale (degradazione fail-safe, MAI disarmo per campo assente).

## 7. Rollback

Ogni gate 🟢 modificato è ripristinabile rimuovendo le 2 righe `if is_plan_phase(...)`. Kill-switch globale: `export NUZ_PHASE_AWARE_OFF=1` letto da `_phase.py` (`is_plan_phase` ritorna sempre False → comportamento = oggi). Zero modifiche ai gate 🔴 → blast radius limitato ai 4 gate verdi.

## 8. Domande aperte per il panel 4-LLM

1. La classificazione 🟢/🔴 è corretta? In particolare: `orchestrate_gate` off-in-plan è giusto, o la delega serve anche in esplorazione?
2. Il fail-safe (missing → guardrail ON) è la scelta giusta, o introduce un buco se `permissionMode` arriva vuoto per un bug Claude Code?
3. C'è un modo di confondere lo switch (es. un agente che resta in `permissionMode:plan` ma di fatto scrive)? Plan-mode è davvero read-only enforced lato Claude Code, o è solo un suggerimento?
4. Manca un gate 🔴 dall'elenco (qualcosa che protegge il reale e che ho dimenticato)?
