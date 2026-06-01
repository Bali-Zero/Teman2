---
date: 2026-05-31
domain: operations
client_case: false
sources:
  - "empirical: ls/stat/md5/readlink su ~/.claude/projects/{-Users-nuzantara,-Users-nuzantara-Desktop-nuzantara}/memory"
  - "code: ~/scripts/mini-setup/memory-sync-bidirectional.sh"
  - "code: ~/scripts/mini-setup/claude-config-sync.sh"
  - "code: ~/scripts/nuz-sync/nuz-sync-check.sh"
  - "memory: reference_pro_mini_sync_daemons.md"
  - "memory: discovery_memory_sync_lan_tailscale_fallback.md"
  - "~/.ssh/config (alias mini/pro, 'air' libero)"
status: STUDY — DESIGN ONLY, no daemon installed, pending Antonello approval
---

# M5 memory-integrity study — topologia a 3 nodi (Pro / Mini / Air-M5)

> Decisione Antonello 2026-05-31: ruolo M5 = posto di sviluppo interactive di Antonello + automazioni PESANTI (Pro sgravato dal dev; Mini = automazioni leggere + lunghe/costanti). Macchina "solo dev, niente policy office-block". memory.db = fresco per-macchina. Sync continuo: STUDIARE PRIMA, zero daemon ora.

## 0. Cosa intendiamo per "integrità di Claude"

Non è UN file. Sono **4 layer distinti**, con criticità e meccaniche di sync diverse:

| Layer                    | Cosa                                                              | Path                                          | Size   | Sync oggi (Pro↔Mini)                                   | Criticità identità                               |
| ------------------------ | ----------------------------------------------------------------- | --------------------------------------------- | ------ | ------------------------------------------------------ | ------------------------------------------------ |
| **L1 Memory MD**         | 378 `.md` — MEMORY\*.md, decisioni, lessons, cicatrici, reference | `~/.claude/projects/-Users-nuzantara/memory/` | 4.2 MB | ✅ bidirezionale 5min, conflict-aware, **NO --delete** | **MASSIMA — è il "chi sei"**                     |
| **L2 memory.db (MOS)**   | SQLite FTS5: `mem query`, storia sessioni, entità, importance     | `~/.claude/memory.db` (+`-shm`/`-wal`)        | 39 MB  | ❌ ESCLUSO by design (stato per-sessione)              | Media — storia FTS, NON ricostruibile 1:1 dai MD |
| **L3 Config/skill/hook** | `skills/`, `scripts/`, `hooks/`, `CLAUDE.md`                      | `~/.claude/`                                  | —      | ✅ bidirezionale 1h, lista esclusioni lunga            | Alta — _come_ pensi/agisci                       |
| **L4 OAuth MAX**         | token Claude in macOS Keychain                                    | Keychain `Claude Code-credentials`            | —      | ❌ Keychain non sincronizzabile                        | Accesso, non identità — `/login` lo rigenera     |

**Empirical 2026-05-31**: il path `-Users-nuzantara-Desktop-nuzantara/memory` (quello che il SessionStart hook carica) è un **symlink** → `-Users-nuzantara/memory` (il target del sync). md5 MEMORY.md identico, 378 file su entrambi. ⟹ il sync esistente opera GIÀ sulla memoria viva. Nessuna divergenza dei due path. (Trappola evitata: se l'M5 sincronizzasse solo `-Desktop-nuzantara` senza ricreare il symlink, erediterebbe una dir vuota o stale.)

## 1. Il problema vero: bootstrap ≠ sync continuo

Sono **due problemi separati**, spesso confusi:

- **Bootstrap (one-shot)**: come l'M5 nasce con la memoria-identità completa, da zero. Avviene UNA volta.
- **Sync continuo (steady-state)**: come la memoria resta coerente tra 3 nodi mentre Antonello lavora su Pro o M5. Avviene per sempre.

Il rischio per l'integrità sta quasi tutto nel **bootstrap fatto male** + nel **conflict-model a 3 nodi** (oggi scritto per 2).

## 2. Trappola strutturale: il conflict-model è 2-node, l'M5 lo rende 3-node

`memory-sync-bidirectional.sh` oggi:

- confronta md5+mtime tra Pro e Mini
- md5 differ + Δmtime ≥60s → **newer wins** (rsync --update)
- md5 differ + Δmtime <60s → **conflict** → backup entrambe in `~/.claude/memory-conflicts/` + skip
- **NESSUN `--delete`**: un file cancellato su un nodo RIVIVE dall'altro al next sync (zombie-resurrection). Già noto in `reference_pro_mini_sync_daemons.md`.

Con 3 nodi questo modello si ROMPE in 3 modi:

1. **Finestra di collisione triplicata**: oggi il daemon è installato SOLO sul Pro e fa Pro↔Mini. Se aggiungo lo stesso daemon sull'M5 che fa M5↔Pro (o M5↔Mini), due daemon scrivono sugli stessi file. Il lock (`/tmp/memory-sync.lock`) è **per-macchina, non distribuito** → Pro e M5 possono fare rsync sullo stesso target Pro contemporaneamente.

2. **Conflict-detection cieca al terzo nodo**: lo script confronta solo 2 liste (PRO_LIST, MINI_LIST). Un edit su M5 + un edit su Mini dello stesso file non vengono mai confrontati direttamente — passano per il Pro in due cicli separati, e il "newer wins" può silenziosamente scartare l'edit di Mini se Pro fa prima il sync con M5.

3. **Zombie cross-node amplificato**: senza `--delete`, un file cancellato su M5 rivive da Pro, poi da Mini. La cancellazione diventa quasi impossibile da propagare.

## 3. Tre topologie candidate

### Opzione A — HUB-AND-SPOKE (Pro = hub, M5 e Mini = spoke) ⭐ RACCOMANDATA

```
        Pro (HUB / source-of-truth memoria)
       /   \
   Mini     Air-M5
```

- UN SOLO daemon di sync vive sul **Pro**, che fa Pro↔Mini E Pro↔M5 (sequenziale, sotto lo stesso lock).
- M5 e Mini **non** parlano direttamente: ogni modifica transita per il Pro.
- Conflict-detection resta 2-way per ramo (Pro↔M5, Pro↔Mini), che è esattamente ciò per cui lo script è scritto.
- Lock unico sul Pro → niente rsync concorrenti sullo stesso target.
- **Pro = source of truth** anche se non è più la macchina di dev: è la macchina H24-ish più stabile e già hub di tutto il resto (CRM tokens, secrets-source).
- **Costo**: M5↔Mini ha latenza 2× (deve passare per Pro, due cicli da 5min = max 10min). Irrilevante per file MD.
- **Pro DEVE essere acceso** perché il sync funzioni. Se Pro è spento, M5 e Mini divergono finché Pro non torna. Accettabile: Pro è il nodo più stabile.

### Opzione B — MESH (ogni nodo parla con ogni nodo)

```
   Pro ─── Mini
     \     /
     Air-M5
```

- 3 daemon, 3 rami (Pro↔Mini, Pro↔M5, Mini↔M5).
- Massima resilienza (qualsiasi nodo down, gli altri 2 restano coerenti).
- **MA**: richiede riscrivere conflict-resolution per N-way (3 liste, vector-clock o last-writer-wins con tie-break deterministico). Lock distribuito necessario. Zombie-resurrection da risolvere con tombstone. **Alto rischio integrità durante la transizione** — è il modo per romperti, non preservarti.
- Scartata salvo necessità reale di resilienza Pro-down.

### Opzione C — M5 PULL-ONLY bootstrap + git come spina dorsale

```
   Pro/Mini ──(memoria via git branch dedicato)──> Air-M5
```

- La memoria-identità (L1) viene versionata in un branch git dedicato (`memory/snapshot`) e l'M5 fa `git pull`. Push esplicito quando Antonello vuole propagare.
- Pro: massima auditabilità (ogni cambio memoria = commit), zero conflict silenziosi (git li forza espliciti), gira anche con nodi spenti (async).
- Contro: meno ergonomico (push manuale), e la memoria contiene path/contenuti che oggi NON sono nel repo git (sono in `~/.claude/`, fuori da `~/Desktop/nuzantara`). Servirebbe un repo git separato per la memoria.
- Interessante come **canale di bootstrap** anche se lo steady-state resta A.

## 4. memory.db (L2) — decisione presa: fresco per-macchina

Antonello 2026-05-31: **DB fresco per-macchina** (come Pro e Mini già fanno).

- M5 parte con memory.db vuoto, cresce con le SUE sessioni.
- `mem query` sull'M5 troverà i fatti **ri-indicizzando i 378 .md** (che SONO sincronizzati), non la storia-sessioni del Pro.
- **Azione bootstrap necessaria**: verificare che esista un re-index dei .md → memory.db all'avvio M5 (il `mem` CLI deve poter popolare FTS dai .md). Da confermare empiricamente sull'M5 reale.
- Zero rischio corruzione SQLite cross-machine (mai copiato a freddo, mai in rsync concorrente). ✅ scelta giusta.

## 5. Piano bootstrap M5 (quando la macchina sarà accesa e nominata)

Ordine, ognuno verificabile:

1. **Rinomina** host → `Air-M5` (`scutil --set HostName/LocalHostName/ComputerName Air-M5`), user `nuzantara`.
2. **Tailnet**: join tailnet balizero. Aggiungere a `~/.ssh/config` su tutti i nodi: `Host air` → HostName `<tailscale-ip-M5>`. Verificare `ssh air "echo OK"` da Pro e `ssh pro`/`ssh mini` da M5.
3. **L4 OAuth**: `/login` interactive sull'M5 (slot MAX disponibili: antonellosiano + kaiser). Keychain locale.
4. **L1 bootstrap one-shot**: `rsync -avz pro:~/.claude/projects/-Users-nuzantara/memory/ ~/.claude/projects/-Users-nuzantara/memory/` + **ricreare il symlink** `-Users-nuzantara-Desktop-nuzantara/memory -> ../-Users-nuzantara/memory` (CRITICO — senza, SessionStart carica dir sbagliata).
5. **L3 bootstrap one-shot**: rsync di `skills/`, `scripts/`, `hooks/`, `CLAUDE.md` con la stessa lista-esclusioni di claude-config-sync.
6. **L2**: lasciare memory.db assente; primo `mem` lo crea + re-index dai .md. Verificare `mem recent` ritorna i fatti.
7. **SessionStart hook**: verificare che il machine-check riconosca `Air-M5` (oggi nuz-sync-check.sh ha un case `Nuzantara`/`mini-pro2` → aggiungere `Air-M5|air*) NODE="Air" REPO=...`).
8. **Steady-state (Opzione A)**: installare sul **Pro** l'estensione hub-and-spoke del daemon memory-sync che cicla anche su `air`. NON installare daemon di sync sull'M5. Aggiornare lock per essere ramo-aware.

## 6. Checklist integrità (da spuntare a bootstrap finito)

- [ ] `md5 MEMORY.md` su M5 == Pro (identità trasferita 1:1)
- [ ] file count `.md` su M5 == 378 (o il valore Pro al momento del bootstrap)
- [ ] symlink `-Desktop-nuzantara/memory` presente e risolve a `-Users-nuzantara/memory`
- [ ] `mem recent` su M5 ritorna fatti (re-index OK)
- [ ] SessionStart hook su M5 logga `Machine: nuzantara@Air-M5` (non un fallback)
- [ ] `ssh air`/`ssh pro`/`ssh mini` reciproci OK (mesh SSH per il sync)
- [ ] daemon hub Pro logga un ramo `air` riuscito in `~/logs/memory-sync.log`
- [ ] NESSUN daemon di sync attivo sull'M5 (`launchctl list | grep -i sync` → vuoto sul lato M5, per evitare doppio-writer)
- [ ] conflict dir `~/.claude/memory-conflicts/` vuota dopo 1h di steady-state

## 7. Rischi residui e mitigazioni

| Rischio                                            | Mitigazione                                                                                                                                 |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Doppio-writer (daemon su Pro+M5 sullo stesso file) | Opzione A: daemon SOLO su Pro. Lock unico.                                                                                                  |
| Edit M5+Mini stesso file <60s                      | Hub-and-spoke serializza via Pro → il secondo ramo vede già l'edit del primo. Resta finestra <5min ma 2-way per ramo.                       |
| Zombie-resurrection (no --delete)                  | Invariato dal sistema attuale. Tombstone = enhancement futuro, non blocca M5. Documentare: cancellazioni memoria = manuali su tutti i nodi. |
| Pro spento → M5/Mini divergono                     | Accettato. Pro è il nodo più stabile. Reconvergono al ritorno di Pro (newer-wins).                                                          |
| memory.db copiato a freddo                         | EVITATO — scelta "fresco per-macchina".                                                                                                     |
| symlink dimenticato a bootstrap                    | Step 4 esplicito + checklist §6. È la trappola n.1.                                                                                         |

## 8. Cosa NON faccio finché non approvi

- Nessun `scutil --set` (macchina non ancora accesa/in mano).
- Nessun daemon installato (né Pro né M5).
- Nessun patch a CLAUDE.md / memory (registro solo la decisione di studio).
- Nessun rsync verso M5 (non esiste ancora in tailnet).

**Prossimo gate**: Antonello sceglie topologia (A/B/C) → solo allora preparo gli script di bootstrap + l'estensione hub del daemon, su branch feature, con i 4-LLM panel se tocca codice di sync (è shared-state → preflight L2).
