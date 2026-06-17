---
allowed-tools: Bash(command -v:*), Bash(grep:*), Bash(rg:*), Bash(ls:*), Bash(sed:*), Bash(git log:*), Bash(git blame:*), Bash(find:*), Read, Glob
description: STADIO-0 STUDY — pre-task ENTRY GATE of the meta-dev-loop. Ground the terrain BEFORE the first Edit/Write — memory-hits, hot-files verified on disk, PII-risk scope, falsifiable criteria. Prevents the "build a plan on a file:line that doesn't exist" class of error.
disable-model-invocation: false
---

# STADIO-0 STUDY — il gate d'ingresso

> _"Errare è umano, allucinare è diabolico."_ L'errore più costoso del loop non è scrivere codice
> sbagliato — è **costruire un piano su un file:line che non esiste**. Sei pezzi a valle pagano ciò che
> questo gate previene a monte. È l'anello mancante: lo studio del terreno PRIMA di muovere.

Eseguilo **PRIMA del primo Edit/Write** di qualunque task non-triviale (feature, fix, refactor,
investigation). **Costo**: 2-10 min. **Salta** SOLO per veri one-liner (typo, rename, fix a causa
nota) — e dichiaralo in una riga ("STADIO-0 skip: triviale, <perché>").

**Arguments:** `$ARGUMENTS` (la descrizione del task da studiare; se vuoto, usa il task corrente della sessione).

L'output è un **blocco strutturato in chat** (le 4 sezioni in fondo), il tuo ragionamento reso esplicito —
NON un file obbligatorio (un file vuoto creato per sbloccare è reward-hacking, non studio).

---

## Steps che DEVI seguire (eseguili in QUESTO turn, non a memoria)

### 1. Memory-hits — cosa sa già il passato

Il context buffer NON è autoritativo. Interroga la memoria reale e le cicatrici versionate del repo:

```bash
# MOS personale (se presente nel PATH) — decisioni/scoperte sul dominio:
command -v mem >/dev/null 2>&1 && mem query "<keyword-del-task>" && mem recent 10
# Cicatrici del repo (SEMPRE disponibili, versionate):
grep -niE "<keyword-del-task>" .claude/rules/cicatrix-scars.md
```

> `mem` è il Memory Operating System personale dell'operatore (non versionato nel repo). Se non è nel
> PATH **non è un errore** — usa le cicatrici versionate (`.claude/rules/cicatrix-scars.md`) +
> `git log`/`git blame` sul dominio come memoria condivisa.

Sintetizza in 2-4 righe cosa la memoria dice di rilevante per QUESTO task + cita le cicatrici che si
applicano. Se la memoria contraddice il tuo piano, **fermati**: la memoria di solito ha ragione (è
world-state passato osservato).

### 2. Hot-files VERIFICATI sul disco — l'anti-allucinazione

Per OGNI file che memory / spec / handoff / report citano come load-bearing, verificalo **adesso**:

```bash
ls -la <path>                 # esiste?
sed -n '<N>p' <path>          # la riga citata dice davvero quello?
grep -rn "<symbol>" <dir>     # il simbolo esiste dove pensi?
```

**Mai fidarsi di un path citato.** Spec, report multi-agente e perfino gli handoff citano path
imprecisi o inesistenti (cicatrice "autopsy phantom file:line": 3 file:line allucinati con precisione
che _leggeva_ come ground-truth). Output: lista dei file **confermati-esistenti** (path reale) + flag
esplicito di ogni citato-ma-assente. Se un report dice `foo.py:63` e `ls foo.py` fallisce — è un LEAD,
non un fatto. Registra gate/componenti per path verificato, mai per nome-da-spec.

### 3. Rischi-PII — il confine Law 2 (sovranità)

Il task tocca dati cliente (KTP / passport / NPWP / akta / WhatsApp / CRM / OSINT) o `apps/backend-rag`?

- **Sì** → confine assoluto: **nessuna PII/OSINT in chiaro negli output persistenti o condivisi**
  (Symbiosis Law 2 / UU PDP). Un LLM puo' processare contesto operativo autorizzato quando serve, ma
  report, memorie, skill, log, alert, prompt salvati per riuso e artefatti condivisi devono usare
  `client_id`, hash, placeholder o redazione. Primitive di redazione: `scripts/_redact_pii.py` —
  ATTENZIONE: ha bug noti documentati, non fidarti ciecamente; verifica lo stato corrente in
  `.claude/rules/cicatrix-scars.md`. Aggiungi il criterio "zero PII/OSINT in chiaro negli output".
- **No** → dichiaralo esplicito ("STADIO-0 PII: nessuno — task non tocca dati cliente"). Scope-vuoto è
  una risposta valida, ma va detta, non assunta.

### 4. Criteri-accettazione FALSIFICABILI — come saprò che è fatto

Definisci come si **testa** che il task è finito, in modo binario/oggettivo:

- ✅ "exit 0 di `pytest <file>`" · "endpoint risponde 401 non 503" · "N test verdi" · "`grep X` = 0 hit"
- ❌ "il codice è pulito" · "funziona meglio" · "sembra a posto"

Se non riesci a scrivere un criterio falsificabile, il task è mal-formato → riformulalo finché lo è.
Questi criteri diventano la tua verifica finale.

---

## Output atteso (incolla in chat all'inizio del task)

```
## STADIO-0 STUDY — <task>
1. Memory-hits: <2-4 righe + cicatrici applicabili>
2. Hot-files verificati: <lista path confermati su disco | flag dei citati-assenti>
3. PII-risk: <scope + confine Law 2, oppure "nessuno — perché">
4. Criteri-accettazione: <1-3 check falsificabili>
```

---

## Discipline contigue (questo gate PRECEDE, non duplica)

Principi che operano DOPO lo STUDY, su terreno già verificato (descritti inline perché lo STADIO-0 deve
reggersi da solo; alcuni operatori hanno skill personali omonime che li approfondiscono — companion, non prerequisito):

- **Reuse-first** — prima di scrivere codice nuovo, cerca quello esistente (`grep`/`rg` per simbolo +
  funzione affine + endpoint). Lo STUDY trova il terreno; reuse-first evita di ri-pavimentarlo.
- **Think-before / surgical / goal-driven** — pensa prima di toccare, tocca il minimo, parti dal goal.
  Lo STUDY _è_ il "think-before" reso checklist falsificabile.
- **Worktree isolation** — quando passi dallo STUDY al BUILD e stai per committare, fallo in un worktree
  isolato (`scripts/agent_start.py`), mai sul checkout principale (cicatrici sibling-race: untracked-lost,
  W62 stale-worktrees). Vedi `docs/runbooks/agent-worktree-broker.md`.

Lo STADIO-0 è il gate **a monte di tutti**: stabilisci il terreno, poi le altre discipline operano su terreno verificato.
